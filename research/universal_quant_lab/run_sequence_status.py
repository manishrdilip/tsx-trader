"""Refresh the strict run status while Phase 1 acquisition workers are active."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from eodhd import atomic_json
from run_sequence_coverage import evidence, load


def utc():
    return datetime.now(timezone.utc).isoformat()


def process_running(pid):
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == 0x102
    finally:
        kernel.CloseHandle(handle)


def follow(root, daily_launcher, intraday_launcher, intraday_log):
    status_file = root / "status.json"
    started = load(status_file)["started"]
    inputs = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in ("RUN_SEQUENCE.md", "SPEC.md")}
    open_coverage = [
        "Complete the full eligible US and crypto intraday universe beyond the staged 12 symbols",
        "The provider commodity-contract directory and GC.COMM / CL.COMM returned HTTP 404",
        "Complete point-in-time fundamentals, corporate actions, earnings, macro and news inventories",
    ]
    counts = {}
    while True:
        finished, state, error = None, "running", None
        try:
            report = evidence(root)
            counts = {"daily": {scope: {
                "state": job["status"], "processed": job["completed"],
                "queued": job["queued"], "pid": job["pid"], "reason": job["reason"],
            } for scope, job in report["daily"].items()}, "intraday": report["intraday"]["totals"]}
            daily = counts["daily"]
            tail = intraday_log.read_bytes().splitlines() if intraday_log.exists() else []
            intraday_state = json.loads(tail[-1])["status"] if tail else None
            counts["intraday"]["latest_worker_state"] = intraday_state
            counts["intraday"]["launcher_pid"] = intraday_launcher
            for scope, launcher in (("canada", None), ("us_and_other", daily_launcher)):
                job = daily.get(scope)
                if job and job["state"] == "complete":
                    continue
                if not ((launcher is not None and process_running(launcher))
                        or (job and process_running(job["pid"]))):
                    raise RuntimeError(f"{scope} daily worker stopped before completion")
            if not process_running(intraday_launcher) and intraday_state != "complete":
                raise RuntimeError(f"Intraday worker stopped before completion. See {intraday_log.name}")
            if len(daily) == 2 and all(job["state"] == "complete" for job in daily.values()) and intraday_state == "complete":
                state, error = "blocked", "Phase 1 does not yet meet the full coverage and supporting-data requirements"
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            state, error = "failed", str(exc)
        if state != "running":
            finished = utc()
        result = {"phase": 1, "state": state, "counts": counts, "started": started, "finished": finished,
                  "updated": utc(), "inputs_sha256": inputs, "open_coverage": open_coverage,
                  "coverage_file": "data_coverage.json"}
        if error:
            result["error"] = error
        atomic_json(status_file, result)
        print(json.dumps({"utc": result["updated"], "state": state, "counts": counts, "error": error}), flush=True)
        if state != "running":
            return 2
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--daily-launcher", type=int, required=True)
    parser.add_argument("--intraday-launcher", type=int, required=True)
    parser.add_argument("--intraday-log", type=Path, required=True)
    raise SystemExit(follow(**vars(parser.parse_args())))
