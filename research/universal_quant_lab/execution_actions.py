"""Validate and map point-in-time splits and cash dividends to daily sessions."""
from datetime import date
import hashlib
import json

import numpy as np


def actions(root, job, sessions, stop):
    factors = np.ones(len(sessions), dtype=np.float64)
    cash = np.zeros(len(sessions), dtype=np.float64)
    claim = np.full(len(sessions), -1, dtype=np.int64)
    pay = claim.copy()
    checksum = job.get("action_snapshot_sha256")
    if not checksum:
        return factors, cash, claim, pay, 0
    if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
        raise ValueError("Invalid action snapshot identifier")
    file = root / "database/eodhd/corporate-actions" / f"{checksum}.json"
    snapshot = json.loads(file.read_bytes())
    if hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest() != checksum:
        raise ValueError("Action snapshot hash mismatch")
    if (snapshot["symbol"], snapshot["data_sha256"]) != (job["symbol"], job["data_sha256"]):
        raise ValueError("Action snapshot belongs to another data revision")
    if snapshot["from"] > sessions[0] or snapshot["to"] < stop:
        raise ValueError("Action snapshot does not cover the full development and warm-up range")
    events = snapshot["events"]
    if set(events) != {"splits", "div"}:
        raise ValueError("Incomplete corporate-action responses")
    for row in events["splits"]:
        day = row["date"]
        if not sessions[0] <= day <= sessions[-1]:
            continue
        location = sessions.get_indexer([day])[0]
        ratio_parts = row["split"].split("/")
        if len(ratio_parts) != 2:
            raise ValueError("Unsupported split ratio format")
        numerator, denominator = map(float, ratio_parts)
        if denominator <= 0:
            raise ValueError("Invalid split ratio")
        ratio = numerator / denominator
        if location == -1 or ratio < 1 or not ratio.is_integer() or not np.isfinite(ratio):
            raise ValueError("Split is not an on-session integer forward split")
        factors[location] *= ratio
    slots = {}
    for row in events["div"]:
        day = row["date"]
        if not sessions[0] <= day <= sessions[-1]:
            continue
        if job["currency"] != row.get("currency"):
            raise ValueError("Dividend currency is missing or requires FX conversion")
        payment = row.get("paymentDate")
        if not payment or date.fromisoformat(payment) < date.fromisoformat(day):
            raise ValueError("Dividend payment date is not verified")
        location = sessions.get_indexer([day])[0]
        if location == -1:
            raise ValueError("Ex-dividend date is not a verified session")
        value = float(row["unadjustedValue"])
        if not np.isfinite(value) or value < 0:
            raise ValueError("Invalid unadjusted dividend value")
        # Credit spendable proceeds at the next session open after the pay date.
        pay_index = sessions.searchsorted(payment, side="right")
        slot = slots.setdefault(pay_index, len(slots))
        if claim[location] not in (-1, slot):
            raise ValueError("Multiple payment dates for one ex-date")
        claim[location] = slot
        cash[location] += value
        if pay_index < len(sessions):
            pay[pay_index] = slot
    return factors, cash, claim, pay, len(slots)
