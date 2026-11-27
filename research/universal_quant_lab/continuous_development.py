"""Run a pinned sequence of disjoint, bounded provisional CPU searches."""
import argparse
import base64
from datetime import datetime, timezone
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
                WHERE category='profit' ORDER BY profit DESC, drawdown, job, strategy_id LIMIT 10
            """).fetchall()
    except duckdb.IOException:
        return []
    symbols = {j["id"]: (j["symbol"], j["currency"]) for j in read(directory / "manifest.json")["jobs"]}
    return [dict(symbol=symbols[job][0], currency=symbols[job][1], strategy_id=identifier,
                 net_profit=round(profit, 2), drawdown_pct=round(100 * drawdown, 2))
            for _, job, identifier, profit, drawdown in rows]


def supervise(root, folder):
    frozen = read(folder / "scope.json")
    previous = 0
    last_publish = -float("inf")
    retained = []
    lab = Path(__file__).parent
    for index, start in enumerate(range(0, TARGET, CHUNK)):
        size = min(CHUNK, TARGET - start)
        directory = folder / f"batch-{index:04d}"
        directory.mkdir(exist_ok=True)
        config = dict(frozen, mode="engineering", batch=4000, threads=2, target=size)
        config["jobs"] = [
            dict(job, quota=size // 3 + (i < size % 3), depth=6, seed=249731,
                 sample_offset=index * (CHUNK // 3))
            for i, job in enumerate(frozen["jobs"])
        ]
        config_path = directory / "config.json"
        if config_path.exists() and read(config_path) != config:
            raise ValueError("Frozen batch configuration changed")
        if not config_path.exists():
            atomic_json(config_path, config)
        progress_file = directory / "progress.json"
        healthy = 0
        worker = None
        attempts = 0
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
                log.close()
                worker = None
            blocked = guard(health(root)) or cpu_guard(root, 85) == "cpu_temperature"
            manually_paused = (folder / "PAUSE").exists() or (directory / "PAUSE").exists()
            healthy = 0 if blocked or manually_paused else healthy + 1
            if not complete and worker is None and healthy >= 3 and attempts < 8:
                log = (directory / "worker.log").open("ab")
                worker = subprocess.Popen([sys.executable, "-B", str(lab / "continuous_development.py"),
                                           str(root), "--worker", str(config_path)], stdout=log, stderr=log,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                attempts += 1
                healthy = 0
            if complete:
                retained = sorted(retained + leaders(directory), key=lambda x: -x["net_profit"])[:30]
            report = dict(campaign=folder.name, provisional_target=TARGET, official_completed=0,
                          completed=previous + progress.get("engineering_completed", 0),
                          batch=index, worker_pid=worker.pid if worker else None,
                          status="batch_complete" if complete else ("running" if worker else "waiting"),
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
