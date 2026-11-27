"""Immutable preregistration and historical deflation for the V2 research run."""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

from eodhd import atomic_json


VERSION = "capped-discovery-forward-v2"
NORMAL = NormalDist()
EULER = 0.5772156649015329


def utc():
    return datetime.now(timezone.utc).isoformat()


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preregister(root):
    path = root / "config" / "v2_preregistration.json"
    inputs = {name: hash_file(root / name)
              for name in ("RUN_SEQUENCE.md", "SPEC.md", "config/universe.json")}
    if "V2 OVERRIDE" not in (root / "RUN_SEQUENCE.md").read_text(encoding="utf-8-sig"):
        raise RuntimeError("The authoritative sequence has no V2 override")
    if path.exists():
        plan = json.loads(path.read_bytes())
        if plan.get("version") != VERSION or plan.get("inputs_sha256") != inputs:
            raise ValueError("Preregistration changed. Start a separately registered campaign.")
        return path, plan
    plan = {
        "version": VERSION, "registered_utc": utc(), "inputs_sha256": inputs,
        "discovery": {
            "target_unique_successful": 1_000_000_000, "maximum_rule_depth": 3,
            "maximum_shortlist": 100, "seed": 6031, "optimize_win_rate": False,
            "method": "Confirm singles, combine filters and triggers, sample wildcard depth 2-3",
            "development_cutoff_inclusive": "2024-11-26", "train_end_exclusive": "2022-01-01",
            "count_policy": "Count each valid canonical dataset/split/execution/candidate once across all stages",
            "ranking_policy": "Deflated Sharpe probability then after-cost compound return then stable ID",
            "penalty": "Full scored-trial count and full scored-trial Sharpe variance. Use common-frequency Sharpe.",
        },
        "forward": {
            "minimum_trading_sessions": 60, "historical_replay": False,
            "start": "First complete eligible session strictly after the frozen shortlist timestamp",
            "require_positive_net_profit": True, "require_positive_matched_buy_and_hold_delta": True,
            "execution": "Paper only, fixed costs and risk rules. Never import a broker client.",
            "alter_shortlist_after_start": False,
        },
    }
    atomic_json(path, plan)
    return path, plan


def reference_sharpe(n_trials, trial_variance):
    if type(n_trials) is not int or n_trials < 1 or not math.isfinite(trial_variance) or trial_variance < 0:
        raise ValueError("Invalid trial count or Sharpe variance")
    if n_trials == 1 or trial_variance == 0:
        return 0.0
    # Invert the lower tail directly so 1 - 1/n never rounds to one.
    return math.sqrt(trial_variance) * (
        -(1 - EULER) * NORMAL.inv_cdf(1 / n_trials)
        - EULER * NORMAL.inv_cdf(1 / (math.e * n_trials))
    )


def probability(sharpe, observations, skew, kurtosis, benchmark):
    if type(observations) is not int or observations < 3:
        raise ValueError("Insufficient non-overlapping return observations")
    if not all(math.isfinite(value) for value in (sharpe, skew, kurtosis, benchmark)):
        raise ValueError("Invalid validation moments")
    variance = 1 - skew * sharpe + (kurtosis - 1) * (sharpe ** 2) / 4
    if variance <= 0:
        raise ValueError("Ill-conditioned Sharpe estimator")
    return NORMAL.cdf((sharpe - benchmark) * math.sqrt((observations - 1) / variance))
