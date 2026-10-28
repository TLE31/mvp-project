import pytest

from changeguard.runner import run_impacted_tests


def test_missing_maven_is_reported_explicitly(tmp_path, monkeypatch):
    (tmp_path / "pom.xml").write_text("<project/>")

    def missing_maven(*args, **kwargs):
        raise FileNotFoundError("mvn")

    monkeypatch.setattr("changeguard.runner.subprocess.run", missing_maven)

    with pytest.raises(RuntimeError, match="Maven executable 'mvn' was not found"):
        run_impacted_tests(tmp_path, ["SampleTest"])
