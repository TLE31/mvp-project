from changeguard.diff import ChangedFile, DiffResult, LineRange
from changeguard.graph import build_graph
from changeguard.impact import analyze_impact
from changeguard.parser import parse_project


def test_reverse_impact_finds_endpoint_and_tests():
    project = parse_project("tests/fixtures/sample-service")
    graph = build_graph(project)
    changes = DiffResult([ChangedFile("src/main/java/example/AttributeService.java", "modified", [LineRange(15, 16)])], "")

    impact = analyze_impact(project, graph, changes)

    assert impact["changed"] == ["AttributeService.filterByContext()"]
    assert impact["impacted_endpoints"] == ["GET /attributes"]
    assert impact["tests_to_run"] == ["AttributeControllerTest", "AttributeServiceTest"]


def test_config_change_finds_using_methods_and_tests():
    project = parse_project("tests/fixtures/sample-service")
    graph = build_graph(project)
    changes = DiffResult(
        [ChangedFile("src/main/resources/application.yml", "modified", [LineRange(3, 3)])],
        "",
    )

    impact = analyze_impact(project, graph, changes)

    assert "method:AttributeService.filterByContext()" in impact["impacted_method_ids"]
    assert "AttributeServiceTest" in impact["tests_to_run"]
    assert "GET /attributes" in impact["impacted_endpoints"]


def test_changed_test_file_is_included_in_test_selection():
    project = parse_project("tests/fixtures/sample-service")
    graph = build_graph(project)
    changes = DiffResult(
        [ChangedFile("src/test/java/example/AttributeServiceTest.java", "modified", [LineRange(9, 12)])],
        "",
    )

    impact = analyze_impact(project, graph, changes)

    assert "AttributeServiceTest" in impact["tests_to_run"]
