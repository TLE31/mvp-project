"""Orchestrate the local analysis pipeline."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from changeguard.diff import collect_changes
from changeguard.graph import build_graph
from changeguard.impact import analyze_impact
from changeguard.parser import parse_project
from changeguard.risk import score_risk


def analyze_repo(repo_path: str | Path = ".", base_ref: str = "main") -> tuple[dict, nx.DiGraph]:
    root = Path(repo_path).resolve()
    diff = collect_changes(root, base_ref)
    project = parse_project(root)
    graph = build_graph(project)
    impact = analyze_impact(project, graph, diff)
    tests_total = len([item for item in graph.nodes(data=True) if item[1].get("kind") == "Test"])
    result = {
        key: value
        for key, value in impact.items()
        if key != "graph"
    }
    result.update(
        {
            "files_changed": [item.path for item in diff.files],
            "diff_summary": diff.summary,
            "tests_selected": len(impact["tests_to_run"]),
            "tests_total": tests_total,
            "risk": score_risk(impact, [item.path for item in diff.files]),
        }
    )
    result["graph"] = graph
    return result, graph
