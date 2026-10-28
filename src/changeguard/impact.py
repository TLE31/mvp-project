"""Map changed lines to Java methods and calculate reverse dependency impact."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import networkx as nx

from changeguard.diff import DiffResult
from changeguard.graph import method_id
from changeguard.parser import JavaProject


def analyze_impact(project: JavaProject, graph: nx.DiGraph, changes: DiffResult, max_depth: int = 5) -> dict:
    changed_methods: set[str] = set()
    changed_test_classes: set[str] = set()
    changed_config_files: set[str] = set()
    changed_config_keys: set[str] = set()
    changed_paths = {file.path: file for file in changes.files}
    for class_info in project.classes:
        changed_file = changed_paths.get(class_info.file)
        if changed_file is None:
            continue
        matching_methods = [
            method
            for method in class_info.methods
            if any(method.start_line <= span.end and method.end_line >= span.start for span in changed_file.ranges)
        ]
        if matching_methods:
            changed_methods.update(method_id(method) for method in matching_methods)
        elif any(class_info.start_line <= span.end and class_info.end_line >= span.start for span in changed_file.ranges):
            changed_methods.update(method_id(method) for method in class_info.methods)
        if class_info.name.endswith(("Test", "Tests")) and any(
            class_info.start_line <= span.end and class_info.end_line >= span.start for span in changed_file.ranges
        ):
            changed_test_classes.add(class_info.name)
    for file in changes.files:
        if Path(file.path).name.startswith("application") and Path(file.path).suffix in {".yml", ".yaml", ".properties"}:
            changed_config_files.add(file.path)
    for key, files in project.config_keys.items():
        if changed_config_files.intersection(files):
            changed_config_keys.add(key)

    config_users = {
        predecessor
        for key in changed_config_keys
        for predecessor in graph.predecessors(f"config:{key}")
        if graph.edges[predecessor, f"config:{key}"].get("kind") == "uses_config"
    }
    seed_methods = changed_methods | config_users
    impacted_depth: dict[str, int] = {node: 0 for node in seed_methods}
    queue = deque(seed_methods)
    while queue:
        node = queue.popleft()
        depth = impacted_depth[node]
        if depth >= max_depth:
            continue
        for predecessor in graph.predecessors(node):
            if graph.edges[predecessor, node].get("kind") != "calls":
                continue
            if predecessor not in impacted_depth:
                impacted_depth[predecessor] = depth + 1
                queue.append(predecessor)

    methods = sorted(impacted_depth)
    endpoints = sorted(
        graph.nodes[target]["name"]
        for target in {target for node in methods for target in graph.successors(node) if graph.nodes[target].get("kind") == "Endpoint"}
    )
    impacted_configs = sorted(changed_config_keys | {
        graph.nodes[target]["name"]
        for node in methods
        for target in graph.successors(node)
        if graph.nodes[target].get("kind") == "ConfigKey"
    })
    tests: set[str] = set(changed_test_classes)
    for test_node, target in graph.edges:
        if graph.nodes[test_node].get("kind") == "Test" and target in impacted_depth and graph.edges[test_node, target].get("kind") == "tests":
            tests.add(graph.nodes[test_node]["name"])
    covered_methods = {target for test_node, target, attrs in graph.edges(data=True) if graph.nodes[test_node].get("kind") == "Test" and attrs.get("kind") == "tests"}
    untested = sorted(
        graph.nodes[node]["name"]
        for node in seed_methods
        if node not in covered_methods and not graph.nodes[node].get("class_name", "").endswith(("Test", "Tests"))
    )

    trees = []
    impact_paths: dict[str, list[str]] = {}
    for changed in sorted(changed_methods):
        changed_name = graph.nodes[changed]["name"]
        branches = []
        for target in sorted(impacted_depth):
            try:
                path = nx.shortest_path(graph, target, changed)
            except nx.NetworkXNoPath:
                continue
            route = [graph.nodes[item]["name"] for item in reversed(path)]
            impact_paths[target] = route
            endpoint_nodes = [
                successor
                for successor in graph.successors(target)
                if graph.nodes[successor].get("kind") == "Endpoint"
            ]
            test_nodes = [
                predecessor
                for predecessor in graph.predecessors(target)
                if graph.nodes[predecessor].get("kind") == "Test"
            ]
            leaves = sorted({graph.nodes[node]["name"] for node in endpoint_nodes + test_nodes})
            for context_node in endpoint_nodes + test_nodes:
                impact_paths[context_node] = route + [graph.nodes[context_node]["name"]]
            for config_node in graph.successors(target):
                if graph.nodes[config_node].get("kind") == "ConfigKey":
                    impact_paths[config_node] = route + [graph.nodes[config_node]["name"]]
            if leaves:
                for leaf in leaves:
                    branches.append({"method": graph.nodes[target]["name"], "depth": len(path) - 1, "path": route + [leaf]})
            elif target != changed:
                branches.append({"method": graph.nodes[target]["name"], "depth": len(path) - 1, "path": route})
        trees.append({"changed": changed_name, "dependents": branches})

    changed_display = sorted(graph.nodes[node]["name"] for node in changed_methods)
    changed_classes = sorted({graph.nodes[node].get("class_name", "") for node in changed_methods if graph.nodes[node].get("class_name")})
    return {
        "changed": changed_display,
        "changed_classes": changed_classes,
        "changed_method_ids": sorted(changed_methods),
        "impacted_method_ids": methods,
        "impacted_endpoints": endpoints,
        "impacted_configs": impacted_configs,
        "tests_to_run": sorted(tests),
        "untested_changes": untested,
        "tree": trees,
        "impact_paths": impact_paths,
        "max_call_depth": max(impacted_depth.values(), default=0),
        "max_fan_in": max(
            (sum(1 for predecessor in graph.predecessors(node) if graph.edges[predecessor, node].get("kind") == "calls") for node in changed_methods),
            default=0,
        ),
        "graph": graph,
    }
