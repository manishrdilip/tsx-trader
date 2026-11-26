"""Detached local watchdog for a multi-job profit-first engineering campaign."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time

from eodhd import atomic_json


def watch(root, config, directory):
    directory.mkdir(parents=True, exist_ok=True)
    lab = Path(__file__).parent
    env = {**os.environ, "NUMBA_CACHE_DIR": str(root / "feature_cache/numba")}
    args = [sys.executable, "-B", str(lab / "profit_campaign.py"), str(root), str(config), str(directory)]
    for attempt in range(1, 4):
        if (directory / "PAUSE").exists():
            return 0
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        with (root / "logs" / f"profit-watch-{stamp}.log").open("xb") as log:
            process = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT)
            atomic_json(directory / "watchdog.json", {"state": "running", "attempt": attempt, "pid": process.pid})
            result = process.wait()
        atomic_json(directory / "watchdog.json", {"state": "exited", "attempt": attempt, "exit_code": result})
        if not result:
            return 0
        if attempt < 3:
            time.sleep(attempt * 3)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    root, config, out = (x.resolve() for x in (args.root, args.config, args.out))
    if not config.is_relative_to(root / "config") or not out.is_relative_to(root / "results"):
        parser.error("Use the dedicated configuration and results directories")
    raise SystemExit(watch(root, config, out))
