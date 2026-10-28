"""Git diff collection, including staged, unstaged, and untracked changes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError


@dataclass(frozen=True)
class LineRange:
    start: int
    end: int


@dataclass
class ChangedFile:
    path: str
    status: str
    ranges: list[LineRange] = field(default_factory=list)


@dataclass
class DiffResult:
    files: list[ChangedFile]
    summary: str


_HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _parse_diff(diff_text: str) -> dict[str, ChangedFile]:
    changed: dict[str, ChangedFile] = {}
    current: ChangedFile | None = None
    old_path: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("--- a/"):
            old_path = line[6:].split("\t", 1)[0]
        if line.startswith("+++ "):
            name = line[4:].split("\t", 1)[0]
            if name == "/dev/null":
                if old_path is not None:
                    current = changed.setdefault(old_path, ChangedFile(old_path, "deleted"))
                    current.status = "deleted"
                continue
            path = name.removeprefix("b/")
            current = changed.setdefault(path, ChangedFile(path, "modified"))
        elif line.startswith("new file mode") and current is not None:
            current.status = "added"
        elif line.startswith("deleted file mode") and current is not None:
            current.status = "deleted"
        elif line.startswith("@@") and current is not None:
            match = _HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                if count:
                    current.ranges.append(LineRange(start, start + count - 1))
                else:
                    current.ranges.append(LineRange(max(1, start), max(1, start)))
    return changed


def collect_changes(repo_path: str | Path = ".", base_ref: str = "main") -> DiffResult:
    """Compare the working tree with base_ref and include every untracked file."""
    root = Path(repo_path).resolve()
    try:
        repo = Repo(root, search_parent_directories=True)
    except InvalidGitRepositoryError as exc:
        raise ValueError(f"{root} is not inside a Git repository") from exc
    try:
        committed_diff = repo.git.diff("--unified=0", "--no-ext-diff", "--no-renames", f"{base_ref}...HEAD", "--")
        working_diff = repo.git.diff("--unified=0", "--no-ext-diff", "--no-renames", "HEAD", "--")
    except GitCommandError as exc:
        detail = str(exc.stderr or exc).strip()
        raise ValueError(f"Cannot diff against base ref {base_ref!r}: {detail}") from exc

    changed = _parse_diff(committed_diff)
    for path, current in _parse_diff(working_diff).items():
        if path in changed:
            changed[path].ranges.extend(current.ranges)
            if current.status in {"added", "deleted"}:
                changed[path].status = current.status
        else:
            changed[path] = current
    for raw_path in repo.untracked_files:
        path = Path(raw_path)
        ranges: list[LineRange] = []
        if path.suffix.lower() in {".java", ".yml", ".yaml", ".properties"}:
            absolute = Path(repo.working_tree_dir or root) / path
            try:
                line_count = len(absolute.read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"Cannot read untracked source/config file {absolute}: {exc}") from exc
            ranges.append(LineRange(1, max(line_count, 1)))
        changed[raw_path] = ChangedFile(raw_path, "added", ranges)

    files = sorted(changed.values(), key=lambda item: item.path)
    summary = "\n".join(f"{file.status}: {file.path}" for file in files) or "No changes detected."
    return DiffResult(files, summary)
