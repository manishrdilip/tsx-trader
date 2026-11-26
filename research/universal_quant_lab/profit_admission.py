"""Verify the sealed evidence required before admitting official evaluations."""
from datetime import datetime, timezone
import json

from campaign_plan import TARGET, hashed, require_sha
from daily_campaign import digest

REQUIRED = (
    "eligible_universe", "cost_and_liquidity", "prospective_holdout_protocol", "comparison_protocol",
    "resource_guardrails", "unattended_recovery", "statistical_retention",
)


def admit(root, config):
    if config.get("mode") != "official" or type(config.get("target")) is not int or config["target"] != TARGET:
        raise ValueError("Official allocation must be exactly one billion")
    if config.get("phase") != "discovery" or config.get("allow_holdout_access") is not False:
        raise ValueError("Discovery requires explicit holdout exclusion")
    proof_root = root / "reports" / "launch"
    proof_file = proof_root / "acceptance.json"
    if not proof_file.is_file():
        raise ValueError("Official run blocked: no sealed launch evidence")
    index = json.loads(proof_file.read_bytes())
    fingerprint = hashed(config)
    if index.get("config_sha256") != fingerprint or set(index.get("evidence", {})) != set(REQUIRED):
        raise ValueError("Official run blocked: evidence belongs to another configuration")
    for gate in REQUIRED:
        path = proof_root / f"{gate}.json"
        expected = require_sha(index["evidence"][gate])
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Official evidence missing or changed: {gate}")
        proof = json.loads(path.read_bytes())
        if proof.get("status") != "passed" or proof.get("config_sha256") != fingerprint:
            raise ValueError(f"Official acceptance check remains open: {gate}")
    for job in config["jobs"]:
        if job.get("instrument") not in ("equity", "etf"):
            raise ValueError("This official execution model supports cash equities and ETFs")
        require_sha(job.get("action_snapshot_sha256"))
    return digest(proof_file)


def cpu_guard(root, limit):
    """A timestamped sensor sample is mandatory during an admitted official run."""
    if not isinstance(limit, (int, float)) or not 40 <= limit <= 100:
        return "invalid_cpu_temperature_limit"
    try:
        data = json.loads((root / "logs" / "cpu-thermal.json").read_bytes())
        stamp = datetime.fromisoformat(data["updated_utc"])
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        reading = float(data["cpu_celsius"])
        if not 0 <= age <= 20 or not 0 < reading <= 125:
            return "cpu_telemetry_stale"
        if reading >= limit:
            return "cpu_temperature"
    except (OSError, ValueError, KeyError, TypeError):
        return "cpu_telemetry_unavailable"
    return None
