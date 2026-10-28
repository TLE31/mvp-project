import subprocess
from pathlib import Path

import pytest

from changeguard.workspace import WORKSPACE_ERROR, WorkspaceResolutionError, resolve_repo


def _git_repo(path: Path, *, pom: bool = True) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if pom:
        (path / "pom.xml").write_text("<project />", encoding="utf-8")
    return path


def test_argument_repo_has_highest_priority(tmp_path, monkeypatch):
    argument_repo = _git_repo(tmp_path / "argument")
    env_repo = _git_repo(tmp_path / "environment")
    monkeypatch.setenv("CHANGEGUARD_REPO", str(env_repo))

    assert resolve_repo(argument_repo) == (argument_repo.resolve(), "argument")


def test_env_repo_is_used_when_no_argument(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "environment")
    monkeypatch.setenv("CHANGEGUARD_REPO", str(repo))

    assert resolve_repo() == (repo.resolve(), "env")


def test_env_repo_has_priority_over_client_roots_and_cwd(tmp_path):
    env_repo = _git_repo(tmp_path / "environment")
    root_repo = _git_repo(tmp_path / "root")
    cwd_repo = _git_repo(tmp_path / "working")

    assert resolve_repo(
        env_value=str(env_repo),
        roots=[root_repo.as_uri()],
        cwd=cwd_repo,
    ) == (env_repo.resolve(), "env")


@pytest.mark.parametrize(
    "env_value",
    ["", "   ", "${workspaceFolder}", "${workspaceFolder}\\"],
)
def test_empty_or_unresolved_env_value_is_ignored(tmp_path, monkeypatch, env_value):
    repo = _git_repo(tmp_path / "working")
    monkeypatch.setenv("CHANGEGUARD_REPO", env_value)

    assert resolve_repo(cwd=repo) == (repo.resolve(), "cwd")


def test_first_file_root_is_used(tmp_path):
    repo = _git_repo(tmp_path / "root")
    cwd_repo = _git_repo(tmp_path / "working")

    assert resolve_repo(roots=["https://example.test", repo.as_uri()], cwd=cwd_repo) == (
        repo.resolve(),
        "roots",
    )


def test_cwd_is_used_as_last_resolution_step(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "working")
    monkeypatch.delenv("CHANGEGUARD_REPO", raising=False)
    monkeypatch.chdir(repo)

    assert resolve_repo() == (repo.resolve(), "cwd")


def test_no_workspace_returns_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("CHANGEGUARD_REPO", raising=False)
    with pytest.raises(WorkspaceResolutionError, match="^" + WORKSPACE_ERROR):
        resolve_repo(cwd=tmp_path)


def test_implicit_changeguard_source_repo_is_rejected(monkeypatch):
    source_repo = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("CHANGEGUARD_REPO", raising=False)

    with pytest.raises(WorkspaceResolutionError, match="pass repo_path"):
        resolve_repo(cwd=source_repo)


def test_non_git_path_reports_what_is_missing(tmp_path):
    with pytest.raises(WorkspaceResolutionError, match="not a Git repository"):
        resolve_repo(tmp_path)


def test_git_repo_without_pom_reports_what_is_missing(tmp_path):
    repo = _git_repo(tmp_path / "without-pom", pom=False)

    with pytest.raises(WorkspaceResolutionError, match="has no pom.xml"):
        resolve_repo(repo)
