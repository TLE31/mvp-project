"""Risk scoring with centralized, reviewable factor weights."""

from __future__ import annotations

from pathlib import Path

WEIGHTS = {
    "impacted_endpoints": 25,
    "call_depth_and_fan_in": 20,
    "config_key_touched": 20,
    "changed_method_without_test": 25,
    "repository_layer_touched": 10,
}
ENDPOINT_POINTS = 10


def score_risk(impact: dict, changed_files: list[str] | None = None) -> dict:
    """Return a 0-100 risk score and weighted per-factor contribution."""
    endpoint_count = len(impact.get("impacted_endpoints", []))
    depth = min(impact.get("max_call_depth", 0), 5)
    fan_in = min(impact.get("max_fan_in", 0), 5)
    repository_touched = any(
        any(part in Path(file).stem.lower() for part in ("repository", "dao", "jdbc"))
        for file in changed_files or []
    )
    factors = {
        "impacted_endpoints": {
            "weight": WEIGHTS["impacted_endpoints"],
            "observed": endpoint_count,
            "points": min(endpoint_count * ENDPOINT_POINTS, WEIGHTS["impacted_endpoints"]),
        },
        "call_depth_and_fan_in": {
            "weight": WEIGHTS["call_depth_and_fan_in"],
            "observed": {"max_depth": depth, "max_fan_in": fan_in},
            "points": round(WEIGHTS["call_depth_and_fan_in"] * (depth / 5 + fan_in / 5) / 2),
        },
        "config_key_touched": {
            "weight": WEIGHTS["config_key_touched"],
            "observed": len(impact.get("impacted_configs", [])),
            "points": WEIGHTS["config_key_touched"] if impact.get("impacted_configs") else 0,
        },
        "changed_method_without_test": {
            "weight": WEIGHTS["changed_method_without_test"],
            "observed": len(impact.get("untested_changes", [])),
            "points": WEIGHTS["changed_method_without_test"] if impact.get("untested_changes") else 0,
        },
        "repository_layer_touched": {
            "weight": WEIGHTS["repository_layer_touched"],
            "observed": repository_touched,
            "points": WEIGHTS["repository_layer_touched"] if repository_touched else 0,
        },
    }
    score = min(100, sum(item["points"] for item in factors.values()))
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"
    return {"level": level, "score": score, "breakdown": factors}
