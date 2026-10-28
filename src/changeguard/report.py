"""Generate a self-contained offline HTML impact graph."""

from __future__ import annotations

import html
import re
from pathlib import Path

import networkx as nx
from pyvis.network import Network


COLORS = {
    "changed": "#dc2626",
    "impacted": "#f97316",
    "endpoint": "#2563eb",
    "config": "#9333ea",
    "test": "#16a34a",
    "failed_test": "#7f1d1d",
    "test_unrun": "#94a3b8",
    "untested": "#9ca3af",
    "class": "#64748b",
}


def generate_report(result: dict, output_path: str | Path = "changeguard-report.html", verification: dict | None = None) -> Path:
    graph: nx.DiGraph = result["graph"]
    changed = set(result["changed_method_ids"])
    impacted = set(result["impacted_method_ids"])
    selected = changed | impacted
    visible = set(selected)
    for node in tuple(selected):
        visible.update(graph.predecessors(node))
        visible.update(graph.successors(node))
    for node in tuple(visible):
        if graph.nodes[node].get("kind") == "Class":
            visible.update(graph.successors(node))
    visible = {node for node in visible if node in graph}

    failed = {
        item["name"]
        for item in (verification or {}).get("tests", [])
        if item["result"] in {"failed", "error"}
    }
    test_results = {item["name"]: item["result"] for item in (verification or {}).get("tests", [])}
    net = Network(height="650px", width="100%", directed=True, bgcolor="#ffffff", font_color="#172033", cdn_resources="in_line")
    for node in sorted(visible):
        attrs = graph.nodes[node]
        kind = attrs.get("kind", "")
        is_changed = node in changed
        is_impacted = node in impacted
        test_name = attrs.get("name", "")
        if is_changed:
            color = COLORS["changed"]
        elif kind == "Method" and test_name in result["untested_changes"]:
            color = COLORS["untested"]
        elif is_impacted and kind == "Method":
            color = COLORS["impacted"]
        elif kind == "Endpoint":
            color = COLORS["endpoint"]
        elif kind == "ConfigKey":
            color = COLORS["config"]
        elif kind == "Test":
            color = COLORS["failed_test"] if test_name in failed else COLORS["test"] if test_results.get(test_name) == "passed" else COLORS["test_unrun"]
        else:
            color = COLORS["class"]
        location = f"{attrs.get('file', '')}:{attrs.get('start_line', '')}-{attrs.get('end_line', '')}".strip(":")
        route = result.get("impact_paths", {}).get(node, [])
        why = "Changed in this diff" if is_changed else f"Impacted via {' -> '.join(route)}" if route else "One-hop context"
        tooltip = html.escape(f"{attrs.get('name', node)} | {location} | {why}")
        net.add_node(
            node,
            label=attrs.get("name", node),
            title=tooltip,
            color={"background": color, "border": "#334155"},
            shape="dot" if kind != "Endpoint" else "diamond",
            dashes=bool(is_impacted and kind == "Method" and attrs.get("name") in result["untested_changes"]),
            size=24 if is_changed else 18,
        )
    for source, target, attrs in graph.edges(data=True):
        if source in visible and target in visible:
            net.add_edge(source, target, label=attrs.get("kind", ""), arrows="to", color="#94a3b8")
    net.set_options(
        '{"physics":{"enabled":true,"hierarchicalRepulsion":{"nodeDistance":170}},"layout":{"improvedLayout":true},"interaction":{"hover":true,"navigationButtons":true}}'
    )
    graph_html = net.generate_html()
    graph_html = re.sub(
        r'<link\b[^>]*href="https?://[^"]+"[^>]*>\s*',
        "",
        graph_html,
        flags=re.IGNORECASE,
    )
    graph_html = re.sub(
        r'<script\b[^>]*src="https?://[^"]+"[^>]*>\s*</script>\s*',
        "",
        graph_html,
        flags=re.IGNORECASE,
    )

    risk = result["risk"]
    bars = "".join(
        f'<div class="factor"><span>{html.escape(name.replace("_", " "))}</span>'
        f'<div class="track"><i style="width:{item["points"] / max(item["weight"], 1) * 100:.0f}%"></i></div>'
        f'<b>{item["points"]}/{item["weight"]}</b></div>'
        for name, item in risk["breakdown"].items()
    )
    endpoint_list = "".join(f"<li>{html.escape(item)}</li>" for item in result["impacted_endpoints"]) or "<li>None</li>"
    config_list = "".join(f"<li>{html.escape(item)}</li>" for item in result["impacted_configs"]) or "<li>None</li>"
    rows = ""
    for item in (verification or {}).get("tests", []):
        rows += f"<tr><td>{html.escape(item['name'])}</td><td>{'Yes' if item['predicted'] else 'No'}</td><td>{html.escape(item['result'])}</td></tr>"
    result_table = (
        "<h2>Predicted vs actual tests</h2><table><tr><th>Test</th><th>Predicted</th><th>Result</th></tr>"
        + (rows or "<tr><td colspan='3'>Tests have not been run</td></tr>")
        + "</table>"
    )
    legend = "".join(
        f'<span><i style="background:{color}"></i>{label}</span>'
        for label, color in [
            ("Changed", COLORS["changed"]), ("Impacted", COLORS["impacted"]),
            ("Endpoint", COLORS["endpoint"]), ("Config", COLORS["config"]),
            ("Test passed", COLORS["test"]), ("Test failed", COLORS["failed_test"]),
            ("Test not run", COLORS["test_unrun"]),
            ("Untested", COLORS["untested"]),
        ]
    )
    extra = f"""
    <style>
      body{{font-family:Arial,sans-serif;color:#172033;margin:0;padding:24px;background:#f8fafc}}
      h1{{margin:0}} .badge{{display:inline-block;padding:6px 12px;border-radius:20px;background:#fef3c7;font-weight:bold}}
      .panels{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin:20px 0}}
      section{{background:white;border:1px solid #e2e8f0;border-radius:10px;padding:16px}}
      .factor{{display:grid;grid-template-columns:1fr 2fr auto;gap:8px;align-items:center;margin:10px 0;font-size:13px}}
      .track{{height:10px;border-radius:10px;background:#e2e8f0;overflow:hidden}} .track i{{display:block;height:100%;background:#f97316}}
      ul{{padding-left:20px}} table{{width:100%;border-collapse:collapse;background:white}} th,td{{padding:8px;border:1px solid #e2e8f0;text-align:left}}
      .legend{{display:flex;flex-wrap:wrap;gap:16px;margin:12px 0}} .legend i{{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:5px}}
    </style>
    <header><h1>ChangeGuard impact report</h1><p><span class="badge">{risk["level"]} RISK · {risk["score"]}/100</span></p></header>
    <div class="panels"><section><h2>Risk breakdown</h2>{bars}</section>
    <section><h2>Impacted endpoints</h2><ul>{endpoint_list}</ul><h2>Impacted config keys</h2><ul>{config_list}</ul></section></div>
    {result_table}<h2>Dependency graph</h2><div class="legend">{legend}</div>
    """
    graph_html = graph_html.replace("<body>", "<body>" + extra, 1)
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(graph_html, encoding="utf-8")
    return destination
