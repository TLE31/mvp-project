"""Compare predicted tests with actual Surefire results."""

from __future__ import annotations


def compare_tests(predicted: list[str], actual: dict) -> dict:
    selected = set(predicted)
    tests = [
        {
            "name": item["name"],
            "predicted": item["name"] in selected,
            "result": item["result"],
            "failures": item.get("failures", 0),
        }
        for item in actual["tests"]
    ]
    failed_unpredicted = [item["name"] for item in tests if item["result"] == "failed" and not item["predicted"]]
    return {
        "tests": tests,
        "failed_unpredicted": failed_unpredicted,
        "predicted_count": len(selected),
        "actual_failed_count": sum(item["result"] == "failed" for item in tests),
    }
