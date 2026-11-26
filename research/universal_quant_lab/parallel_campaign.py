"""Run independent campaign jobs concurrently with separate manifests and checkpoints."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
from uuid import uuid4


def run(config, output, workers, minutes):
    jobs = json.loads(config.read_bytes())["jobs"]
    ids = [job["id"] for job in jobs]
    if not jobs or len(set(ids)) != len(ids) or any(
        not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id) for job_id in ids
    ):
        raise ValueError("Expected nonempty jobs with unique, safe IDs")
    output.mkdir(parents=True, exist_ok=True)
    campaign = Path(__file__).with_name("campaign.cjs")

    def run_job(job):
        directory = output / job["id"]
        directory.mkdir(exist_ok=True)
        job = {**job, "file": str((config.parent / job["file"]).resolve())}
        payload = json.dumps({"jobs": [job]})
        digest = hashlib.sha256(payload.encode()).hexdigest()
        job_config = directory / f"job-{digest}.json"
        if not job_config.exists():
            temp = directory / f".job-{uuid4().hex}.tmp"
            try:
                temp.write_text(payload, encoding="utf-8")
                temp.replace(job_config)
            finally:
                temp.unlink(missing_ok=True)
        process = subprocess.run(
            ["node", str(campaign), "run", str(job_config), str(directory / "batches"), str(minutes)],
            check=True, stdout=subprocess.PIPE, text=True,
        )
        result = json.loads(process.stdout.splitlines()[-1])
        return {"job": job["id"], **result}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(run_job, jobs):
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--minutes-per-job", type=float, default=15)
    args = parser.parse_args()
    run(args.config.resolve(), args.output.resolve(), args.workers, args.minutes_per_job)
