"""V2 Phase 3 freezes the development inputs and the future-data boundary."""
from pathlib import Path

from eodhd import atomic_json
from forward_v2 import hash_file, preregister
from run_universe import read


def run(root, previous_hash, publish):
    marker = root / "phase2_done.json"
    if hash_file(marker) != previous_hash:
        raise RuntimeError("The Phase 2 marker no longer matches the completed cache")
    entry = read(marker)["counts"]
    manifest_path = root / "feature_cache/capped-sequence/manifest.json"
    expected = entry["feature_manifest_sha256"]
    if hash_file(manifest_path) != expected:
        raise RuntimeError("Feature cache manifest is inconsistent with Phase 2")
    _, plan = preregister(root)
    cutoff = plan["discovery"]["development_cutoff_inclusive"]
    cache = read(manifest_path)
    if cache.get("last_observation", "") > cutoff or not cache.get("datasets"):
        raise RuntimeError("Feature cache has an invalid development data boundary")
    allowed = (root / "feature_cache/capped-sequence").resolve()
    for dataset in cache["datasets"]:
        local = (allowed / dataset["path"]).resolve()
        if (not local.is_relative_to(allowed) or dataset["last_observation"] > cutoff
                or hash_file(local) != dataset["sha256"]):
            raise RuntimeError("Feature dataset fails the pinned development checks")
    fence = root / "checkpoints/capped-sequence/development_fence.json"
    atomic_json(fence, {
        "version": plan["version"], "development_cutoff_inclusive": cutoff,
        "feature_manifest_sha256": expected,
        "forward_start_rule": plan["forward"]["start"],
        "forward_inputs_registered": 0,
        "development_only": True,
    })
    return {"development_inputs": len(cache["datasets"]), "development_fence_sha256": hash_file(fence)}
