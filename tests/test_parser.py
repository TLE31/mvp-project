from changeguard.parser import parse_project


def test_parses_methods_calls_endpoints_and_config():
    project = parse_project("tests/fixtures/sample-service")
    classes = {item.name: item for item in project.classes}

    service = classes["AttributeService"]
    method = next(item for item in service.methods if item.name == "filterByContext")
    assert "findAll" in method.calls
    assert service.config_keys == ["business.context.enabled"]
    controller = classes["AttributeController"]
    assert next(item for item in controller.methods if item.name == "list").endpoints == [("GET", "/attributes")]
    assert "business.context.enabled" in project.config_keys
