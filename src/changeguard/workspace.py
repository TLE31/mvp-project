"""Resolve and validate the Java/Maven workspace used by MCP tools."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


WORKSPACE_ERROR = (
    "Could not find a workspace. Open a Java Maven Git repository or pass repo_path."
)


class WorkspaceResolutionError(ValueError):
    """Raised when an MCP tool cannot select a usable Java/Maven repository."""


def _file_uri_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = url2pathname(unquote(parsed.path))
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return Path(path)


def _git_root(path: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise WorkspaceResolutionError("Git executable 'git' was not found.") from exc
    if result.returncode:
        raise WorkspaceResolutionError(f"The resolved path is not a Git repository: {path}.")
    return Path(result.stdout.strip()).resolve()


def _resolve_candidate(candidate: Path, source: str, explicit: bool) -> tuple[Path, str]:
    repo = _git_root(candidate.expanduser().resolve())
    if not explicit and (repo / "src" / "changeguard").is_dir():
        raise WorkspaceResolutionError(
            "The ChangeGuard source repository was selected implicitly; pass repo_path."
        )
    if not (repo / "pom.xml").is_file():
        raise WorkspaceResolutionError(f"The resolved Git repository has no pom.xml: {repo}.")
    return repo, source


def resolve_repo(
    repo_path: str | os.PathLike[str] | None = None,
    *,
    env_value: str | None = None,
    roots: list[str] | tuple[str, ...] | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> tuple[Path, str]:
    """Return a validated repository root and the source used to select it."""
    if repo_path is not None and str(repo_path).strip():
        return _resolve_candidate(Path(repo_path), "argument", explicit=True)

    if env_value is None:
        env_value = os.environ.get("CHANGEGUARD_REPO")
    if env_value and env_value.strip() and "${workspaceFolder}" not in env_value:
        return _resolve_candidate(Path(env_value.strip()), "env", explicit=False)

    for root in roots or ():
        candidate = _file_uri_path(root)
        if candidate is not None:
            return _resolve_candidate(candidate, "roots", explicit=False)

    working_directory = Path(cwd) if cwd is not None else Path.cwd()
    try:
        return _resolve_candidate(working_directory, "cwd", explicit=False)
    except WorkspaceResolutionError as exc:
        if "not a Git repository" in str(exc):
            raise WorkspaceResolutionError(WORKSPACE_ERROR) from exc
        raise
