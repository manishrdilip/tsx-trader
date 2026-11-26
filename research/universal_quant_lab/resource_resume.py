"""Resume a resource-paused provisional run after three healthy samples."""
import json
from pathlib import Path
import sys
import time

from campaign_watchdog import health, guard
from profit_watchdog import watch

if __name__ == "__main__":
    root, config, out = (Path(x).resolve() for x in sys.argv[1:])
    if not config.is_relative_to(root / "config") or not out.is_relative_to(root / "results"):
        raise SystemExit("Expected research workspace paths")
    if json.loads(config.read_bytes()).get("mode","engineering") != "engineering":
        raise SystemExit("Only provisional work is supported")
    healthy = 0
    while not (out / "PAUSE").exists():
        state = json.loads((out / "progress.json").read_bytes())["status"]
        if state != "paused":
            break
        healthy = 0 if guard(health(root)) else healthy + 1
        if healthy >= 3:
            if watch(root, config, out):
                raise SystemExit("Worker failed")
            healthy = 0
        time.sleep(20)
