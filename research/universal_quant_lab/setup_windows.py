"""Windows setup for the research-only Universal Quant Lab. Run with Python 3.10+.
No credentials are read or printed. No live trading modules are imported or run.
Requires Git, Node.js 20+, Python and network access. No administrator privileges.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

BRANCH = "research/universal-quant-lab"
URL = "https://github.com/manishrdilip/tsx-trader.git"
FOLDERS = ("database", "database/TSX", "database/TSXV", "database/US",
           "database/Forex", "database/Metals", "database/Crypto",
           "database/Commodities", "database/Options", "feature_cache",
           "strategies", "backtests", "checkpoints", "results", "logs", "reports", "config")
RESERVE = 150 * 1024**3

def run(args, **kw):
    return subprocess.run([str(x) for x in args], check=True, **kw)

def capture(args):
    return run(args, stdout=subprocess.PIPE, text=True).stdout.strip()

def check_disk(root):
    if shutil.disk_usage(root).free < RESERVE:
        raise RuntimeError("Insufficient free disk: keep at least 150 GiB")

def setup(root, pilot):
    if sys.platform != "win32":
        raise RuntimeError("Run on the actual Windows laptop, not a cloud machine")
    if not root.is_absolute() or not root.anchor or not Path(root.anchor).exists():
        raise RuntimeError("Existing absolute Windows drive required")
    root.mkdir(parents=True, exist_ok=True)
    check_disk(root)
    for name in FOLDERS:
        (root / name).mkdir(parents=True, exist_ok=True)
    git, node = shutil.which("git"), shutil.which("node")
    if not git or not node or int(capture([node, "--version"]).lstrip("v").split(".")[0]) < 20:
        raise RuntimeError("Install Git and Node.js 20+ from official sources first")
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10+ required")
    repo = root / "repository"
    if not repo.exists():
        run([git, "clone", "--depth=1", "--single-branch", "--branch", BRANCH,
             "--filter=blob:none", URL, repo])
    if capture([git, "-C", repo, "remote", "get-url", "origin"]) != URL:
        raise RuntimeError("Unexpected repository; refusing to modify it")
    if capture([git, "-C", repo, "branch", "--show-current"]) != BRANCH:
        raise RuntimeError("Wrong branch; refusing to modify it")
    if capture([git, "-C", repo, "status", "--porcelain"]):
        raise RuntimeError("Dedicated checkout is dirty; preserve local changes before continuing")
    run([git, "-C", repo, "pull", "--ff-only"])
    lab = repo / "research" / "universal_quant_lab"
    env = root / "venv"
    if not (env / "Scripts" / "python.exe").exists():
        run([sys.executable, "-m", "venv", env])
    py = env / "Scripts" / "python.exe"
    run([py, "-m", "pip", "install", "numpy", "pandas", "pyarrow", "duckdb", "polars"])
    (root / "reports" / "requirements-installed.txt").write_text(capture([py, "-m", "pip", "freeze"]) + "\n", encoding="utf-8")
    run([node, lab / "engine.cjs", "selftest"])
    run([node, lab / "campaign.cjs", "selftest"])
    result = {"branch": BRANCH, "commit": capture([git, "-C", repo, "rev-parse", "HEAD"]),
              "node": capture([node, "--version"]), "python": capture([py, "--version"]),
              "free_gib": round(shutil.disk_usage(root).free / 1024**3, 2),
              "pilot_requested": pilot, "pilot_completed": False,
              "eodhd_key_present_in_environment": any(bool(__import__("os").environ.get(k)) for k in ("EODHD_API_KEY","EODHD_API_TOKEN","EODHD_TOKEN")),
              "live_trading": False}
    (root / "reports" / "setup.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not pilot:
        print(json.dumps(result, indent=2))
        return
    check_disk(root)
    # Fetch known research sample only. Git show is binary-safe via subprocess stdout.
    run([git, "-C", repo, "fetch", "--depth=1", "origin",
         "refs/heads/micro-test:refs/remotes/origin/micro-test"])
    source = root / "database" / "TSX" / "micro-test-bars_5m.parquet"
    if not source.exists():
        temp = source.with_suffix(".tmp")
        with temp.open("wb") as out:
            run([git, "-C", repo, "show", "refs/remotes/origin/micro-test:lab/micro/data/bars_5m.parquet"], stdout=out)
        with temp.open("rb") as f:
            if f.read(4) != b"PAR1":
                raise RuntimeError("Source is not a Parquet file (possible LFS pointer)")
        temp.replace(source)
    bars = root / "database" / "TSX" / "RY_5m.json"
    run([py, lab / "import_bars.py", source, bars, "--symbol", "RY.TO", "--timezone", "America/Toronto"])
    config = root / "config" / "pilot.json"
    jobs = [{"id": "tsx_ry_5m_depth" + str(depth), "market": "TSX", "symbol": "RY.TO",
             "interval": "5m", "currency": "CAD", "source": "Prior micro-test Yahoo sample; NOT independent holdout",
             "file": str(bars), "depth": depth, "budget": "200", "batch": "50",
             "hold": 3, "cash": 5000, "sideCost": 0.0005, "direction": 1}
            for depth in (1, 2, 3)]
    config.write_text(json.dumps({"jobs": jobs}, indent=2), encoding="utf-8")
    # Unique output per pilot, so code/input changes do not overwrite earlier evidence.
    out = root / "results" / ("pilot-" + time.strftime("%Y%m%d-%H%M%S"))
    start = time.monotonic()
    run([node, lab / "campaign.cjs", "run", config, out, "15"])
    completed = list(out.glob("*/batch-*.json"))
    rows = [r for f in completed for r in json.loads(f.read_text(encoding="utf-8"))["results"]]
    result.update({"pilot_completed": len(rows) == 600, "processed": len(rows),
                   "screened": sum("status" not in r for r in rows),
                   "unsupported": sum("status" in r for r in rows),
                   "seconds": round(time.monotonic()-start, 2), "output": str(out),
                   "evidence": "Previously researched sample; engineering pilot only"})
    (root / "reports" / "setup.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=r"D:\UniversalQuantLab")
    p.add_argument("--pilot", action="store_true")
    a = p.parse_args()
    setup(Path(a.root), a.pilot)
