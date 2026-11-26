"""Run the configured, bounded local research campaign and retain its log."""
from contextlib import redirect_stdout
from datetime import datetime
import os
from pathlib import Path
import traceback

from parallel_campaign import run


def main():
    root = Path(__file__).resolve().parents[3]
    node = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs"
    os.environ["PATH"] = str(node) + os.pathsep + os.environ["PATH"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    with (root / "logs" / f"scheduled-{stamp}.log").open("x", encoding="utf-8") as log:
        try:
            with redirect_stdout(log):
                run(root / "config/scheduled-research.json",
                    root / "results/scheduled-research", workers=2, minutes=15)
        except Exception:
            traceback.print_exc(file=log)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
