"""stdio MCP server exposing local ChangeGuard analysis tools."""

from __future__ import annotations

import inspect
import json
import os
import sys
import webbrowser
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from mcp.shared.exceptions import McpError

from changeguard import __version__
from changeguard.analysis import analyze_repo
from changeguard.explain import explain_impact as explain_locally
from changeguard.render_text import render_summary, render_test_comparison
from changeguard.report import generate_report as create_report
from changeguard.runner import run_impacted_tests as run_maven_tests
from changeguard.verify import compare_tests
from changeguard.workspace import WorkspaceResolutionError, resolve_repo

mcp = FastMCP("ChangeGuard")


def _clean(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "graph"}


async def _client_roots(ctx: Context | None) -> list[str]:
    if ctx is None:
        return []
    session = getattr(ctx, "session", None)
    list_roots = getattr(session, "list_roots", None)
    if not callable(list_roots):
        return []
    try:
        result = list_roots()
        if inspect.isawaitable(result):
            result = await result
    except McpError:
        return []
    return [root.uri for root in getattr(result, "roots", [])]


async def _resolve_tool_repo(
    repo_path: str | None,
    ctx: Context | None,
) -> tuple[Path, str]:
    return resolve_repo(repo_path, roots=await _client_roots(ctx))


def _analysis_prefix(repo: Path, source: str) -> str:
    return f"Analyzing: {repo} (source: {source})"


@mcp.tool()
async def analyze_change(
    repo_path: str | None = None,
    base_ref: str = "main",
    ctx: Context | None = None,
) -> str:
    """Analyze current Java changes; return impact JSON and a Markdown summary."""
    try:
        root, source = await _resolve_tool_repo(repo_path, ctx)
    except WorkspaceResolutionError as exc:
        return str(exc)
    result, _ = analyze_repo(root, base_ref)
    return _analysis_prefix(root, source) + "\n" + json.dumps(
        {"impact": _clean(result), "summary": render_summary(result)}, indent=2
    )


@mcp.tool()
async def run_impacted_tests(
    repo_path: str | None = None,
    base_ref: str = "main",
    ctx: Context | None = None,
) -> str:
    """Run predicted impacted Maven tests and compare the results."""
    try:
        root, source = await _resolve_tool_repo(repo_path, ctx)
    except WorkspaceResolutionError as exc:
        return str(exc)
    result, _ = analyze_repo(root, base_ref)
    actual = run_maven_tests(root, result["tests_to_run"])
    verification = compare_tests(result["tests_to_run"], actual)
    persisted_actual = {
        "tests": actual["tests"],
        "returncode": actual["returncode"],
        "tests_total": actual["tests_total"],
    }
    (root / ".changeguard-last-run.json").write_text(
        json.dumps({"actual": persisted_actual, "verification": verification}, indent=2),
        encoding="utf-8",
    )
    return _analysis_prefix(root, source) + "\n" + json.dumps(
        {
            "actual": persisted_actual,
            "verification": verification,
            "markdown": render_summary(result) + "\n\n" + render_test_comparison(verification),
        },
        indent=2,
    )


@mcp.tool()
async def generate_report(
    repo_path: str | None = None,
    base_ref: str = "main",
    ctx: Context | None = None,
) -> str:
    """Create and open the standalone HTML impact graph report."""
    try:
        root, source = await _resolve_tool_repo(repo_path, ctx)
    except WorkspaceResolutionError as exc:
        return str(exc)
    result, _ = analyze_repo(root, base_ref)
    saved_results = root / ".changeguard-last-run.json"
    verification = None
    if saved_results.is_file():
        verification = json.loads(saved_results.read_text(encoding="utf-8")).get("verification")
    path = create_report(result, root / "changeguard-report.html", verification)
    webbrowser.open(path.as_uri())
    return f"{_analysis_prefix(root, source)}\nChangeGuard report created: {path} (opened in the default browser when available)."


@mcp.tool()
async def explain_impact(
    repo_path: str | None = None,
    base_ref: str = "main",
    ctx: Context | None = None,
) -> str:
    """Explain predicted impact in plain English; Ollama is optional and local."""
    try:
        root, source = await _resolve_tool_repo(repo_path, ctx)
    except WorkspaceResolutionError as exc:
        return str(exc)
    result, _ = analyze_repo(root, base_ref)
    return f"{_analysis_prefix(root, source)}\n{explain_locally(result)}"


@mcp.tool()
async def whoami(ctx: Context | None = None) -> str:
    """Report the workspace selection and runtime details used by ChangeGuard."""
    env_value = os.environ.get("CHANGEGUARD_REPO")
    details = {
        "repo_path": None,
        "source": None,
        "CHANGEGUARD_REPO": env_value,
        "current_working_directory": str(Path.cwd()),
        "python_executable": sys.executable,
        "changeguard_version": __version__,
    }
    try:
        root, source = await _resolve_tool_repo(None, ctx)
    except WorkspaceResolutionError as exc:
        details["error"] = str(exc)
        return json.dumps(details, indent=2)
    details["repo_path"] = str(root)
    details["source"] = source
    return _analysis_prefix(root, source) + "\n" + json.dumps(details, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
