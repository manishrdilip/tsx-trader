"""Acquire and test one-minute bars for the existing frozen 140-symbol cohort."""
import argparse
from datetime import date, datetime, timezone
import msvcrt
import os
from pathlib import Path

from eodhd import atomic_json
from run_all import fetch_intraday, quota
from run_universe import read


def run(root, out):
    source = root / "results/available-intraday-140-v1/plan.json"
    symbols = list(read(source)["source_windows"])
    if len(symbols) != 140 or any(not symbol.endswith(".US") for symbol in symbols):
        raise ValueError("Expected the frozen 140-symbol US cohort")
    out.mkdir(parents=True, exist_ok=True)
    progress = out / "acquisition.json"
    previous = read(progress) if progress.exists() else {}
    completed = previous.get("outcomes", {})
    coverage = read(root / "checkpoints/capped-sequence/daily.json")
    start, end = date(2023, 1, 1), date(2024, 11, 27)
    current = None
    def status(state, **extra):
        atomic_json(progress, {"state": state, "target": len(symbols), "checked": len(completed),
                               "outcomes": completed, "current": current, "pid": os.getpid(),
                               "updated_utc": datetime.now(timezone.utc).isoformat(), **extra})
    try:
        for current in symbols:
            if current in completed:
                continue
            status("running")
            first, last = coverage[current][2:4]
            if not first:
                completed[current] = "daily_missing"
            else:
                quota(root)
                fetch_intraday(root, current, ["1m"], start, end,
                               (date.fromisoformat(first), date.fromisoformat(last)),
                               lambda counts: status("running", **counts))
                completed[current] = "checked"
            status("running")
        status("acquired")
        from available_intraday_screen import run as evaluate
        evaluate(root, out, 140, interval="1m", cohort=symbols)
        status("complete")
    except Exception as error:
        status("failed", error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "worker.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        run(args.root, args.out)
