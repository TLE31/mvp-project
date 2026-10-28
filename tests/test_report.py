from changeguard.diff import ChangedFile, DiffResult, LineRange
from changeguard.graph import build_graph
from changeguard.impact import analyze_impact
from changeguard.parser import parse_project
from changeguard.report import generate_report
from changeguard.risk import score_risk
import re


def test_report_is_self_contained_and_contains_summary(tmp_path):
    root = "tests/fixtures/sample-service"
    project = parse_project(root)
    graph = build_graph(project)
    impact = analyze_impact(
        project,
        graph,
        DiffResult(
            [ChangedFile("src/main/java/example/AttributeService.java", "modified", [LineRange(15, 16)])],
            "",
        ),
    )
    result = {key: value for key, value in impact.items() if key != "graph"}
    result.update(
        {
            "graph": graph,
            "risk": score_risk(impact),
            "tests_total": 2,
            "tests_selected": len(impact["tests_to_run"]),
        }
    )
    path = generate_report(result, tmp_path / "report.html")
    content = path.read_text(encoding="utf-8")

    assert "ChangeGuard impact report" in content
    assert "GET /attributes" in content
    assert "vis-network.min.js" in content
    assert not re.search(r'(?:src|href)="https?://', content)
