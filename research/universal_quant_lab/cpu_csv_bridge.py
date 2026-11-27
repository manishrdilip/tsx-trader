"""Bridge local LibreHardwareMonitor CSV samples to the CPU resource guard."""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import time

from eodhd import atomic_json


def sample(directory):
    latest = max(directory.glob("LibreHardwareMonitorLog-*.csv"), key=lambda p: p.stat().st_mtime)
    with latest.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        ids, labels = next(reader), next(reader)
        # Small tail read keeps long-running logs out of memory.
    with latest.open("rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - 16384))
        lines = f.read().decode("utf-8", errors="replace").splitlines()
    for row in reversed(list(csv.reader(lines[1:] if size > 16384 else lines[2:]))):
        if len(row) != len(ids):
            continue
        try:
            stamp = datetime.strptime(row[0], "%m/%d/%Y %H:%M:%S").astimezone(timezone.utc)
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            if not 0 <= age <= 15:
                raise ValueError("CPU log reading is stale")
            values = {label: float(row[i]) for i, (identifier, label) in enumerate(zip(ids, labels))
                      if re.match(r"^/(intel|amd)cpu/\d+/temperature/", identifier)
                      and (label == "CPU Package" or re.fullmatch(r"(?:[PE]-|CPU )?Core #\d+", label))}
            cores = {k: v for k, v in values.items() if k != "CPU Package"}
            if not cores or "CPU Package" not in values or not all(0 < v <= 125 for v in values.values()):
                raise ValueError("Incomplete CPU package or core readings")
            return dict(updated_utc=stamp.isoformat(), cpu_celsius=max(values.values()),
                        package_celsius=values["CPU Package"], cores=cores, source="LibreHardwareMonitor CSV")
        except (ValueError, IndexError):
            continue
    raise ValueError("No complete, fresh CPU sample")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            reading = sample(args.root / "tools/LHM-0.9.6/app")
            atomic_json(args.root / "logs/cpu-thermal.json", reading)
            if args.once:
                print(reading)
                break
        except (OSError, ValueError, StopIteration) as error:
            if args.once:
                raise SystemExit(str(error))
        time.sleep(3)
