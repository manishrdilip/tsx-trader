"""Run a pinned sequence of disjoint, bounded provisional CPU searches."""
import argparse
import base64
from datetime import datetime, timezone
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import time

import duckdb

from campaign_watchdog import guard, health
from daily_campaign import exclusive
from eodhd import atomic_json
from profit_admission import cpu_guard

TARGET = 1_000_000_000
CHUNK = 3_000_000
BRANCH = "research/universal-quant-lab"
ENDPOINT = "repos/manishrdilip/tsx-trader/contents/research/universal_quant_lab/CONTINUOUS_DEVELOPMENT.json"


def read(path):
    return json.loads(path.read_bytes())


def publish(report):
    read_remote = subprocess.run(["gh", "api", ENDPOINT + "?ref=" + BRANCH, "--jq", ".sha"],
                                 capture_output=True, text=True, timeout=30, check=True)
    payload = {
        "branch": BRANCH, "sha": read_remote.stdout.strip(),
        "message": "Update continuous provisional research progress",
        "content": base64.b64encode(json.dumps(report, indent=2).encode()).decode(),
    }
    subprocess.run(["gh", "api", "-X", "PUT", ENDPOINT, "--input", "-"], input=json.dumps(payload),
                   text=True, stdout=subprocess.DEVNULL, timeout=45, check=True)


def leaders(directory):
    try:
        with duckdb.connect(str(directory / "global.duckdb"), read_only=True) as db:
            rows = db.execute("""
                SELECT scope, job, strategy_id, profit, drawdown FROM top_candidates
                WHERE category='profit'
                QUALIFY row_number() OVER (PARTITION BY job ORDER BY profit DESC, drawdown, job, strategy_id) <= 10
                ORDER BY scope, profit DESC, drawdown, job, strategy_id
            """).fetchall()
    except duckdb.IOException:
        return []
    symbols = {j["id"]: (j["symbol"], j["currency"]) for j in read(directory / "manifest.json")["jobs"]}
    return [dict(symbol=symbols[job][0], currency=symbols[job][1], strategy_id=identifier,
                 net_profit=round(profit, 2), drawdown_pct=round(100 * drawdown, 2))
            for _, job, identifier, profit, drawdown in rows]


def idle(directory):
    try:
        with exclusive(directory / "runner.lock"):
            return True
    except OSError:
        return False


def supervise(root, folder):
    baseline = read(folder / "scope.json")
    previous = 0
    last_publish = -float("inf")
    retained = []
    lab = Path(__file__).parent
    for index, start in enumerate(range(0, TARGET, CHUNK)):
        size = min(CHUNK, TARGET - start)
        directory = folder / f"batch-{index:04d}"
        directory.mkdir(exist_ok=True)
        config_path = directory / "config.json"
        if config_path.exists():
            config = read(config_path)
            if config["target"] != size or config.get("mode") != "engineering":
                raise ValueError("Invalid frozen batch allocation")
        else:
            scopes = [baseline]
            scopes.extend(read(path) for path in sorted(folder.glob("scope-[0-9]*.json")))
            frozen = scopes[index % len(scopes)]
            count = len(frozen["jobs"])
            if not 1 <= count <= 3:
                raise ValueError("Use one to three instruments per bounded scope")
            config = dict(frozen, mode="engineering", batch=4000, threads=2, target=size)
            config["jobs"] = [
                dict(job, quota=size // count + (i < size % count), depth=6, seed=249731,
                     sample_offset=index * CHUNK)
                for i, job in enumerate(frozen["jobs"])
            ]
            atomic_json(config_path, config)
        progress_file = directory / "progress.json"
        healthy = 0
        worker = None
        attempts = 0
        last_rows = 0
        log = None
        while True:
            progress = read(progress_file) if progress_file.exists() else {}
            complete = progress.get("status") == "complete"
            if complete and worker is not None and worker.poll() is None:
                time.sleep(1)
                continue
            if complete and progress["engineering_completed"] != size:
                raise ValueError("Completed batch has the wrong count")
            if worker is not None and worker.poll() is not None:
                rows = progress.get("engineering_completed", 0)
                if worker.returncode == 0 and progress.get("status") == "paused":
                    attempts = 0
                elif rows > last_rows:
                    attempts = 0
                last_rows = rows
                log.close()
                worker = None
            blocked = guard(health(root)) or cpu_guard(root, 85) == "cpu_temperature"
            manually_paused = (folder / "PAUSE").exists() or (directory / "PAUSE").exists()
            healthy = 0 if blocked or manually_paused else healthy + 1
            if not complete and worker is None and healthy >= 3 and attempts < 8 and idle(directory):
                log = (directory / "worker.log").open("ab")
                worker = subprocess.Popen([sys.executable, "-B", str(lab / "continuous_development.py"),
                                           str(root), "--worker", str(config_path)], stdout=log, stderr=log,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                attempts += 1
                healthy = 0
            if complete:
                by_symbol = defaultdict(list)
                for candidate in retained + leaders(directory):
                    by_symbol[candidate["currency"], candidate["symbol"]].append(candidate)
                retained = [candidate for key in sorted(by_symbol)
                            for candidate in sorted(by_symbol[key],
                                key=lambda x: (-x["net_profit"], x["drawdown_pct"], x["strategy_id"]))[:5]]
            report = dict(campaign=folder.name, provisional_target=TARGET, official_completed=0,
                          completed=previous + progress.get("engineering_completed", 0),
                          batch=index, worker_pid=worker.pid if worker else None,
                          status=("complete" if previous + size == TARGET else "batch_complete") if complete
                          else ("running" if worker or not idle(directory) else "waiting"),
                          resource_pause=bool(blocked or manually_paused),
                          retry_limit_reached=attempts >= 8 and worker is None and not complete,
                          updated_utc=datetime.now(timezone.utc).isoformat(), promising=retained)
            atomic_json(folder / "progress.json", report)
            now = time.monotonic()
            if now - last_publish >= 900 or report["completed"] == TARGET:
                try:
                    publish(report)
                    last_publish = now
                except (OSError, subprocess.SubprocessError) as error:
                    print("Progress publication failed:", error, flush=True)
                    last_publish = now
            if complete:
                previous += size
                break
            time.sleep(10 if attempts == 0 or worker is not None else 20)


def run_worker(root, config_path):
    import numba
    from profit_campaign import run
    connect = duckdb.connect

    def limited(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connection.execute("SET threads=1")
        connection.execute("SET memory_limit='192MB'")
        return connection

    duckdb.connect = limited
    numba.config.CACHE_DIR = str(root / "feature_cache/numba")
    run(root, read(config_path), config_path.parent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker:
        run_worker(args.root, args.worker)
    else:
        folder = args.root / "results/continuous-development-v1"
        with exclusive(folder / "supervisor.lock"):
            supervise(args.root, folder)
