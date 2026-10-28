from git import Actor, Repo

from changeguard.diff import collect_changes


def test_collect_changes_includes_committed_and_untracked(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / "Main.java").write_text("class Main {\n void old() {}\n}\n")
    repo.index.add(["Main.java"])
    actor = Actor("ChangeGuard Test", "changeguard@example.invalid")
    repo.index.commit("base", author=actor, committer=actor)
    base = repo.head.commit.hexsha
    (tmp_path / "Main.java").write_text("class Main {\n void changed() {}\n}\n")
    (tmp_path / "New.java").write_text("class New {}\n")
    (tmp_path / "notes.txt").write_text("review the updated implementation\n")

    changes = collect_changes(tmp_path, base)

    assert {item.path for item in changes.files} == {"Main.java", "New.java", "notes.txt"}
    assert next(item for item in changes.files if item.path == "New.java").status == "added"
    assert next(item for item in changes.files if item.path == "Main.java").ranges


def test_collect_changes_includes_deletions(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / "Removed.java").write_text("class Removed {}\n")
    repo.index.add(["Removed.java"])
    actor = Actor("ChangeGuard Test", "changeguard@example.invalid")
    repo.index.commit("base", author=actor, committer=actor)
    base = repo.head.commit.hexsha
    (tmp_path / "Removed.java").unlink()

    changes = collect_changes(tmp_path, base)

    assert [(item.path, item.status) for item in changes.files] == [("Removed.java", "deleted")]


def test_collect_changes_reports_renames_as_delete_and_add(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / "Old.java").write_text("class Old {}\n")
    repo.index.add(["Old.java"])
    actor = Actor("ChangeGuard Test", "changeguard@example.invalid")
    repo.index.commit("base", author=actor, committer=actor)
    base = repo.head.commit.hexsha
    (tmp_path / "Old.java").rename(tmp_path / "New.java")

    changes = collect_changes(tmp_path, base)

    assert {(item.path, item.status) for item in changes.files} == {
        ("New.java", "added"),
        ("Old.java", "deleted"),
    }
