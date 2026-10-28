"""stdio MCP server exposing local ChangeGuard analysis tools."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from changeguard.analysis import analyze_repo
from changeguard.explain import explain_impact as explain_locally
from changeguard.render_text import render_summary, render_test_comparison
from changeguard.report import generate_report as create_report
from changeguard.runner import run_impacted_tests as run_maven_tests
from changeguard.verify import compare_tests

mcp = FastMCP("ChangeGuard")


def _clean(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "graph"}


@mcp.tool()
def analyze_change(repo_path: str, base_ref: str = "main") -> str:
    """Analyze current Java changes; return impact JSON and a Markdown summary."""
    result, _ = analyze_repo(repo_path, base_ref)
    return json.dumps({"impact": _clean(result), "summary": render_summary(result)}, indent=2)


@mcp.tool()
def run_impacted_tests(repo_path: str, base_ref: str = "main") -> str:
    """Run predicted impacted Maven tests and compare the results."""
    result, _ = analyze_repo(repo_path, base_ref)
    actual = run_maven_tests(repo_path, result["tests_to_run"])
    verification = compare_tests(result["tests_to_run"], actual)
    persisted_actual = {
        "tests": actual["tests"],
        "returncode": actual["returncode"],
        "tests_total": actual["tests_total"],
    }
    (Path(repo_path).resolve() / ".changeguard-last-run.json").write_text(
        json.dumps({"actual": persisted_actual, "verification": verification}, indent=2),
        encoding="utf-8",
    )
    return json.dumps(
        {
            "actual": persisted_actual,
            "verification": verification,
            "markdown": render_summary(result) + "\n\n" + render_test_comparison(verification),
        },
        indent=2,
    )


@mcp.tool()
def generate_report(repo_path: str, base_ref: str = "main") -> str:
    """Create and open the standalone HTML impact graph report."""
    result, _ = analyze_repo(repo_path, base_ref)
    root = Path(repo_path).resolve()
    saved_results = root / ".changeguard-last-run.json"
    verification = None
    if saved_results.is_file():
        verification = json.loads(saved_results.read_text(encoding="utf-8")).get("verification")
    path = create_report(result, root / "changeguard-report.html", verification)
    webbrowser.open(path.as_uri())
    return f"ChangeGuard report created: {path} (opened in the default browser when available)."


@mcp.tool()
def explain_impact(repo_path: str, base_ref: str = "main") -> str:
    """Explain predicted impact in plain English; Ollama is optional and local."""
    result, _ = analyze_repo(repo_path, base_ref)
    return explain_locally(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
