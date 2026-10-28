"""ChangeGuard command-line interface."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Optional

import typer

from changeguard.analysis import analyze_repo
from changeguard.explain import explain_impact
from changeguard.render_text import render_summary, render_test_comparison
from changeguard.report import generate_report
from changeguard.runner import run_impacted_tests
from changeguard.verify import compare_tests

app = typer.Typer(help="Analyze Java/Maven change impact locally.", no_args_is_help=True)


def _jsonable(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "graph"}


def _emit(text: str, output: Optional[Path]) -> None:
    if output:
        output.resolve().write_text(text + "\n", encoding="utf-8")
    typer.echo(text)


@app.command()
def analyze(
    repo_path: Path = typer.Option(Path("."), "--repo", help="Path to the Java/Maven Git repository."),
    base_ref: str = typer.Option("main", "--base", help="Git base reference."),
    json_output: bool = typer.Option(False, "--json", help="Print structured JSON instead of Markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write output to this file."),
) -> None:
    """Analyze the current Git changes and recommend impacted tests."""
    result, _ = analyze_repo(repo_path, base_ref)
    _emit(json.dumps(_jsonable(result), indent=2) if json_output else render_summary(result), output)


@app.command("run-tests")
def run_tests(
    repo_path: Path = typer.Option(Path("."), "--repo", help="Path to the Java/Maven Git repository."),
    base_ref: str = typer.Option("main", "--base", help="Git base reference."),
    json_output: bool = typer.Option(False, "--json", help="Print structured JSON instead of Markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write output to this file."),
) -> None:
    """Run impacted Maven tests and compare predicted and actual results."""
    result, _ = analyze_repo(repo_path, base_ref)
    actual = run_impacted_tests(repo_path, result["tests_to_run"])
    verification = compare_tests(result["tests_to_run"], actual)
    result["tests_total"] = actual["tests_total"]
    result["tests_selected"] = len(result["tests_to_run"])
    payload = {"analysis": _jsonable(result), "actual": actual, "verification": verification}
    payload["actual"].pop("stdout", None)
    payload["actual"].pop("stderr", None)
    result_file = Path(repo_path).resolve() / ".changeguard-last-run.json"
    result_file.write_text(json.dumps({"actual": payload["actual"], "verification": verification}, indent=2), encoding="utf-8")
    text = render_summary(result) + "\n\n" + render_test_comparison(verification)
    _emit(json.dumps(payload, indent=2) if json_output else text, output)
    if actual["returncode"]:
        raise typer.Exit(code=actual["returncode"])


@app.command()
def report(
    repo_path: Path = typer.Option(Path("."), "--repo", help="Path to the Java/Maven Git repository."),
    base_ref: str = typer.Option("main", "--base", help="Git base reference."),
    output: Path = typer.Option(Path("changeguard-report.html"), "--output", help="HTML report destination."),
    open_browser: bool = typer.Option(False, "--open", help="Open the report in the default browser."),
) -> None:
    """Generate an offline, interactive impact graph report."""
    result, _ = analyze_repo(repo_path, base_ref)
    saved_results = Path(repo_path).resolve() / ".changeguard-last-run.json"
    verification = None
    if saved_results.is_file():
        saved = json.loads(saved_results.read_text(encoding="utf-8"))
        verification = saved.get("verification")
    path = generate_report(result, output, verification)
    typer.echo(str(path))
    if open_browser:
        webbrowser.open(path.as_uri())


@app.command()
def explain(
    repo_path: Path = typer.Option(Path("."), "--repo", help="Path to the Java/Maven Git repository."),
    base_ref: str = typer.Option("main", "--base", help="Git base reference."),
) -> None:
    """Explain impact using local Ollama when available."""
    result, _ = analyze_repo(repo_path, base_ref)
    typer.echo(explain_impact(result))


if __name__ == "__main__":
    app()
