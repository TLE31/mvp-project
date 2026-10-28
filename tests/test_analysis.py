from pathlib import Path

from changeguard.analysis import analyze_repo


def test_sample_git_history_identifies_high_risk_repository_change():
    repo = Path("tests/fixtures/sample-service")
    result, _ = analyze_repo(repo, "main")

    assert result["changed"] == ["AttributeRepository.findAll()"]
    assert result["impacted_endpoints"] == ["GET /attributes"]
    assert result["tests_to_run"] == ["AttributeControllerTest", "AttributeServiceTest"]
    assert result["risk"]["level"] == "HIGH"
    assert result["risk"]["score"] >= 70
