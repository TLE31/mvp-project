"""Run selected Maven tests and inspect Surefire XML reports."""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from changeguard.parser import parse_project


def run_impacted_tests(repo_path: str | Path, test_classes: list[str], timeout: int = 900) -> dict:
    root = Path(repo_path).resolve()
    pom = root / "pom.xml"
    if not pom.is_file():
        raise FileNotFoundError(f"No pom.xml found at {root}")
    if not test_classes:
        raise ValueError("No impacted tests were identified; refusing to run an empty Maven selection.")
    arguments = ["-q", f"-Dtest={','.join(sorted(set(test_classes)))}", "test"]
    command: list[str] | str = ["mvn", *arguments]
    use_shell = False
    if os.name == "nt":
        maven_path = shutil.which("mvn")
        if maven_path and Path(maven_path).suffix.lower() in {".bat", ".cmd"}:
            command = subprocess.list2cmdline([maven_path, *arguments])
            use_shell = True
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=use_shell,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Maven executable 'mvn' was not found; install Maven and add it to PATH.") from exc
    reports = root / "target" / "surefire-reports"
    results: dict[str, dict] = {}
    if reports.is_dir():
        for report in sorted(reports.glob("TEST-*.xml")):
            try:
                suite = ET.parse(report).getroot()
            except ET.ParseError as exc:
                raise ValueError(f"Invalid Surefire report {report}: {exc}") from exc
            classname = suite.attrib.get("name", report.stem.removeprefix("TEST-"))
            failures = int(suite.attrib.get("failures", "0")) + int(suite.attrib.get("errors", "0"))
            skipped = int(suite.attrib.get("skipped", "0"))
            results[classname] = {
                "result": "failed" if failures else "skipped" if skipped else "passed",
                "failures": failures,
                "skipped": skipped,
            }
            results[classname.rsplit(".", 1)[-1]] = results[classname]
    requested = sorted(set(test_classes))
    test_results = [
        {"name": name, **results.get(name, {"result": "not_reported", "failures": 0, "skipped": 0})}
        for name in requested
    ]
    missing_reports = [item["name"] for item in test_results if item["result"] == "not_reported"]
    if missing_reports and completed.returncode == 0:
        raise RuntimeError(f"Maven completed without Surefire results for selected tests: {', '.join(missing_reports)}")
    if completed.returncode and not any(item["result"] == "failed" for item in test_results):
        raise RuntimeError(
            f"Maven exited with status {completed.returncode}, but no selected test failure was found.\n"
            f"{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}"
        )
    return {
        "command": command,
        "returncode": completed.returncode,
        "tests": test_results,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "tests_total": len([item for item in parse_project(root).classes if item.name.endswith(("Test", "Tests"))]),
    }
