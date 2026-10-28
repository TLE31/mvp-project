from changeguard.graph import build_graph
from changeguard.parser import parse_project


def test_graph_connects_calls_endpoints_configs_and_tests():
    graph = build_graph(parse_project("tests/fixtures/sample-service"))
    assert graph.has_edge("method:AttributeController.list()", "method:AttributeService.filterByContext()")
    assert graph.has_edge("method:AttributeController.list()", "endpoint:GET /attributes")
    assert graph.has_edge("method:AttributeService.filterByContext()", "config:business.context.enabled")
    assert graph.has_edge("test:AttributeServiceTest", "method:AttributeService.filterByContext()")
    assert graph.has_edge("test:AttributeControllerTest", "method:AttributeController.list()")
