"""Markdown-friendly human-readable summaries and test comparisons."""

from __future__ import annotations


def render_summary(result: dict) -> str:
    risk = result["risk"]
    lines = [
        f"# ChangeGuard: {risk['level']} risk ({risk['score']}/100)",
        "",
        "**Changed methods:** " + (", ".join(result["changed"]) or "None detected"),
        "**Changed classes:** " + (", ".join(result.get("changed_classes", [])) or "None detected"),
        "**Changed files:** " + (", ".join(result.get("files_changed", [])) or "None detected"),
        "",
        f"**Impacted endpoints:** {', '.join(result['impacted_endpoints']) or 'None'}",
        f"**Impacted configs:** {', '.join(result['impacted_configs']) or 'None'}",
        f"**Tests to run:** {', '.join(result['tests_to_run']) or 'None'} "
        f"({result['tests_selected']} of {result['tests_total']})",
        "",
        f"**Why {risk['level']}:** {_risk_reason(risk)}",
        "",
        "## Dependency paths",
        "",
        "```text",
        render_tree_ascii(result),
        "```",
    ]
    return "\n".join(lines)


def _risk_reason(risk: dict) -> str:
    positive = [
        (name.replace("_", " "), details["points"])
        for name, details in risk["breakdown"].items()
        if details["points"]
    ]
    if not positive:
        return "no high-impact signals were detected."
    reasons = ", ".join(f"{name} (+{points})" for name, points in sorted(positive, key=lambda item: item[1], reverse=True))
    return f"score contributions: {reasons}."


def render_test_comparison(verification: dict) -> str:
    lines = [
        "## Predicted vs actual tests",
        "",
        "| Test | Predicted | Result | Failure was predicted? |",
        "|---|---:|---|---:|",
    ]
    for test in verification["tests"]:
        actual_failure = test["result"] in {"failed", "error"}
        lines.append(
            f"| {test['name']} | {'Yes' if test['predicted'] else 'No'} | "
            f"{test['result']} | {'Yes' if test['predicted'] and actual_failure else 'No'} |"
        )
    if not verification["tests"]:
        lines.append("| No test results | - | - | - |")
    return "\n".join(lines)


def render_tree_ascii(result: dict) -> str:
    lines: list[str] = []
    for tree in result.get("tree", []):
        lines.append(f"{tree['changed']}  <- changed")
        branches: dict[str, dict] = {}
        for branch in tree["dependents"]:
            current = branches
            for node in branch["path"][1:]:
                current = current.setdefault(node, {})

        def append_branches(nodes: dict[str, dict], depth: int) -> None:
            children = list(nodes.items())
            for index, (name, descendants) in enumerate(children):
                connector = "+-- " if index == len(children) - 1 else "|-- "
                lines.append("  " * depth + connector + name)
                append_branches(descendants, depth + 1)

        append_branches(branches, 0)
    if not result.get("tree"):
        return "(no dependency paths found)"
    return "\n".join(lines) or "(no dependency paths found)"
