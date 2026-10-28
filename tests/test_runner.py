import subprocess

from changeguard.runner import run_impacted_tests


def test_runner_parses_surefire_results_and_selects_only_impacted_classes(tmp_path, monkeypatch):
    (tmp_path / "pom.xml").write_text("<project/>")
    reports = tmp_path / "target" / "surefire-reports"
    reports.mkdir(parents=True)
    (reports / "TEST-example.ServiceTest.xml").write_text(
        '<testsuite name="example.ServiceTest" tests="1" failures="1" errors="0" skipped="0"/>'
    )
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, "failed", "")

    monkeypatch.setattr("changeguard.runner.subprocess.run", fake_run)

    result = run_impacted_tests(tmp_path, ["ServiceTest"])

    assert commands == [["mvn", "-q", "-Dtest=ServiceTest", "test"]]
    assert result["tests"][0]["name"] == "ServiceTest"
    assert result["tests"][0]["result"] == "failed"
    assert result["returncode"] == 1
