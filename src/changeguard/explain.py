"""Optional local Ollama explanation with a deterministic fallback."""

from __future__ import annotations

import json
import os

import requests


def explain_impact(result: dict) -> str:
    model = os.environ.get("CHANGEGUARD_OLLAMA_MODEL", "qwen2.5-coder")
    prompt_data = {
        "diff_summary": result.get("diff_summary", ""),
        "impact": {key: value for key, value in result.items() if key != "graph"},
    }
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": "Explain this Java change impact briefly for a developer:\n" + json.dumps(prompt_data), "stream": False},
            timeout=8,
        )
        response.raise_for_status()
        explanation = response.json().get("response", "").strip()
        if explanation:
            return explanation
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        pass
    risk = result["risk"]
    changed = ", ".join(result["changed"]) or "unmatched changes"
    endpoints = ", ".join(result["impacted_endpoints"]) or "no REST endpoints"
    tests = ", ".join(result["tests_to_run"]) or "no mapped tests"
    return (
        f"This change affects {changed}. The analysis found {endpoints} and recommends {tests}. "
        f"Overall risk is {risk['level']} ({risk['score']}/100)."
    )
