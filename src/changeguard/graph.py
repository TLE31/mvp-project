"""Build a directed dependency graph from parsed Java sources."""

from __future__ import annotations

import networkx as nx

from changeguard.parser import JavaProject, MethodInfo


def method_id(method: MethodInfo) -> str:
    return f"method:{method.qualified_name}"


def build_graph(project: JavaProject) -> nx.DiGraph:
    graph = nx.DiGraph()
    methods_by_name: dict[str, list[str]] = {}
    methods_by_class: dict[str, list[str]] = {}

    for class_info in project.classes:
        class_id = f"class:{class_info.name}"
        graph.add_node(class_id, kind="Class", name=class_info.name, file=class_info.file, start_line=class_info.start_line, end_line=class_info.end_line)
        methods_by_class[class_info.name] = []
        for method in class_info.methods:
            node_id = method_id(method)
            methods_by_name.setdefault(method.name, []).append(node_id)
            methods_by_class[class_info.name].append(node_id)
            graph.add_node(node_id, kind="Method", name=method.qualified_name, class_name=method.class_name, method_name=method.name, file=method.file, start_line=method.start_line, end_line=method.end_line)
            graph.add_edge(class_id, node_id, kind="contains")
            for key in set(method.config_keys + class_info.config_keys):
                config_id = f"config:{key}"
                graph.add_node(config_id, kind="ConfigKey", name=key)
                graph.add_edge(node_id, config_id, kind="uses_config")
            for verb, path in method.endpoints:
                endpoint_id = f"endpoint:{verb} {path}"
                graph.add_node(endpoint_id, kind="Endpoint", name=f"{verb} {path}")
                graph.add_edge(node_id, endpoint_id, kind="exposes")

    for class_info in project.classes:
        if class_info.name.endswith(("Test", "Tests")):
            continue
        for method in class_info.methods:
            caller = method_id(method)
            for called_name in method.calls:
                matches = methods_by_name.get(called_name, [])
                if len(matches) == 1:
                    graph.add_edge(caller, matches[0], kind="calls")
                elif matches:
                    same_class = [node for node in matches if graph.nodes[node].get("class_name") == method.class_name]
                    for callee in same_class or matches:
                        graph.add_edge(caller, callee, kind="calls")

    for class_info in project.classes:
        if not class_info.name.endswith("Test") and not class_info.name.endswith("Tests"):
            continue
        test_class_id = f"test:{class_info.name}"
        graph.add_node(test_class_id, kind="Test", name=class_info.name, file=class_info.file, start_line=class_info.start_line, end_line=class_info.end_line, result="not_run")
        target_class_name = class_info.name.removesuffix("Tests").removesuffix("Test")
        for production_method in methods_by_class.get(target_class_name, []):
            graph.add_edge(test_class_id, production_method, kind="tests")
        for method in class_info.methods:
            for called_name in method.calls:
                for production_method in methods_by_name.get(called_name, []):
                    if not graph.nodes[production_method].get("class_name", "").endswith(("Test", "Tests")):
                        graph.add_edge(test_class_id, production_method, kind="tests")

    for key, files in project.config_keys.items():
        config_id = f"config:{key}"
        graph.add_node(config_id, kind="ConfigKey", name=key, files=files)
    return graph
