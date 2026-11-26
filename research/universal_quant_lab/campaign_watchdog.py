"""Launch a bounded local engineering job and retry interrupted checkpoints."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from eodhd import atomic_json

RESERVE = 150 * 1024**3


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
        (field, ctypes.c_uint64) for field in (
            "total_physical", "available_physical", "total_pagefile", "available_pagefile",
            "total_virtual", "available_virtual", "available_extended_virtual",
        )
    ]


def health(root):
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    memory_ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    temperatures = []
    gpu = shutil.which("nvidia-smi")
    if gpu:
        try:
            sample = subprocess.run(
                [gpu, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, check=True, text=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            temperatures = [int(line) for line in sample.stdout.splitlines() if line.strip().isdigit()]
        except (OSError, subprocess.SubprocessError):
            pass
    return {
        "free_bytes": shutil.disk_usage(root).free,
        "memory_available_bytes": memory.available_physical if memory_ok else None,
        "max_gpu_celsius": max(temperatures, default=None),
        "cpu_celsius": None,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }


def guard(snapshot):
    if snapshot["free_bytes"] < RESERVE + 256 * 1024**2:
        return "disk"
    if snapshot["memory_available_bytes"] is not None and snapshot["memory_available_bytes"] < 1024**3:
        return "memory"
    if snapshot["max_gpu_celsius"] is not None and snapshot["max_gpu_celsius"] >= 85:
        return "gpu_temperature"
    return None


def supervise(root, config):
    settings = json.loads(config.read_bytes())
    spec = (root / "config" / settings["spec"]).resolve()
    out = (root / "results" / settings["run"]).resolve()
    if not spec.is_relative_to(root / "config") or not out.is_relative_to(root / "results"):
        raise ValueError("Job paths must stay in the lab workspace")
    out.mkdir(parents=True, exist_ok=True)
    status_file = out / "watchdog.json"
    env = {**os.environ, "NUMBA_CACHE_DIR": str(root / "feature_cache/numba")}
    lab = Path(__file__).parent
    cmd = [sys.executable, "-B", str(lab / "daily_campaign.py"), str(root), str(spec), str(out),
           "--budget", str(settings["budget"]), "--batch", str(settings["batch"]),
           "--threads", str(settings["threads"])]
    for attempt in range(1, 4):
        sample = health(root)
        atomic_json(out / "resources.json", sample)
        reason = guard(sample)
        if (out / "PAUSE").exists() or reason:
            atomic_json(status_file, {"status": "paused", "reason": reason or "operator"})
            return 0
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        with (root / "logs" / f"daily-watchdog-{stamp}.log").open("xb") as log:
            child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
            atomic_json(status_file, {"status": "running", "attempt": attempt, "pid": child.pid, "utc": stamp})
            while True:
                try:
                    result = child.wait(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    sample = health(root)
                    atomic_json(out / "resources.json", sample)
                    reason = guard(sample)
                    if reason:
                        try:
                            with (out / "PAUSE").open("x", encoding="utf-8") as marker:
                                marker.write(reason + "\n")
                        except FileExistsError:
                            pass
        atomic_json(status_file, {"status": "exited", "attempt": attempt, "exit_code": result, "utc": stamp})
        if not result:
            return 0
        if attempt < 3:
            time.sleep(5 * attempt)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    raise SystemExit(supervise(args.root.resolve(), args.config.resolve()))
