"""Validate and seal the exact job allocation for a future official campaign."""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re

from daily_engine import space
from eodhd import atomic_json

TARGET = 1_000_000_000


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a SHA-256 fingerprint")
    return value


def seal(plan):
    dates = [plan[key] for key in ("train_start", "validation_start", "holdout_start")]
    if dates != sorted(set(dates)) or any(date.fromisoformat(day).isoformat() != day for day in dates):
        raise ValueError("Expected three increasing, aligned ISO split dates")
    require_sha(plan["holdout_protocol_sha256"])
    require_sha(plan["engine_sha256"])
    roles = set()
    total = 0
    jobs = []
    for job in plan["jobs"]:
        require_sha(job["data_sha256"])
        require_sha(job["eligibility_audit_sha256"])
        currency = job["currency"]
        if currency not in {"CAD", "USD"}:
            raise ValueError("Separate CAD or USD comparator required")
        require_sha(plan["vmm_comparator_sha256"][currency])
        if job["interval"] != "1d" or job["instrument"] not in {"equity", "etf"}:
            raise ValueError("This engine supports daily cash equities and ETFs")
        cash, cost, depth = job["cash"], job["cost_per_side"], job["depth"]
        if cash != 5000 or not math.isfinite(cost) or not 0 <= cost < 1:
            raise ValueError("Invalid campaign execution assumptions")
        if type(depth) is not int or type(job["seed"]) is not int:
            raise ValueError("Depth and seed must be integers")
        _, capacity = space(depth)
        budget = job["budget"]
        if type(budget) is not int or not 1 <= budget <= capacity:
            raise ValueError("Search budget exceeds a canonical strategy space")
        # An alternate seed or a repeat of a dataset under an alias cannot add capacity.
        identity = {
            "data_sha256": job["data_sha256"], "depth": depth, "dates": dates,
            "cash": cash, "currency": currency, "cost_per_side": cost,
        }
        role = hashed(identity)
        if role in roles:
            raise ValueError("An execution scope appears more than once")
        roles.add(role)
        total += budget
        jobs.append({**job, "job_id": role, "capacity": capacity})
    if total != TARGET:
        raise ValueError(f"Official quotas must sum to exactly {TARGET:,}")
    sealed = {**plan, "target": TARGET, "jobs": jobs}
    return {**sealed, "plan_sha256": hashed(sealed)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("sealed", type=Path)
    args = parser.parse_args()
    plan = seal(json.loads(args.draft.read_bytes()))
    if args.sealed.exists():
        if json.loads(args.sealed.read_bytes()) != plan:
            raise SystemExit("Existing sealed allocation differs")
    else:
        atomic_json(args.sealed, plan)
    print(plan["plan_sha256"])
