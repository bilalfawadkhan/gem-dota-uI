"""Tests for the upstream reference watch (HY-183)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import check_upstream_refs as watch

REPO_ROOT = Path(__file__).resolve().parent.parent
PIN = "a" * 40


def _sha(n: int) -> str:
    return hashlib.sha1(str(n).encode()).hexdigest()


def _listed(text: str, sha: str) -> bool:
    """Whether a commit appears as a row (its linked short SHA) in an issue table."""
    return f"[`{sha[:8]}`]" in text


class FakeGitHub:
    """In-memory upstream history and issue tracker."""

    def __init__(self, history: list[tuple[str, list[str]]], *, merges: set[str] = frozenset()):
        # history: (sha, files) oldest first; the pin is the commit before the first.
        self.history = history
        self.merges = merges
        self.issues: dict[int, dict] = {}
        self.comments: list[tuple[int, str]] = []
        self.labels: set[str] = set()
        self.calls: list[str] = []

    def head(self, repository: str, branch: str) -> str:
        return self.history[-1][0] if self.history else PIN

    def compare(self, repository: str, base: str, head: str) -> tuple[str, int, list[dict]]:
        shas = [s for s, _ in self.history]
        start = shas.index(base) + 1 if base in shas else 0
        commits = [
            {
                "sha": s,
                "parents": [{"sha": "p1"}, {"sha": "p2"}] if s in self.merges else [{"sha": "p"}],
                "commit": {
                    "message": f"change {s[-2:]}\n\nbody",
                    "committer": {"date": "2026-10-07T10:00:00Z"},
                },
            }
            for s in shas[start:]
        ]
        return ("ahead" if commits else "identical"), len(commits), commits

    def commit_files(self, repository: str, sha: str) -> list[str]:
        return dict(self.history)[sha]

    def open_issues(self, repository: str, label: str) -> list[watch.Issue]:
        return [
            watch.Issue(n, i["body"])
            for n, i in self.issues.items()
            if i["state"] == "open" and label in i["labels"]
        ]

    def ensure_label(self, repository: str, label: str) -> None:
        self.labels.add(label)

    def create_issue(self, repository: str, title: str, body: str, label: str) -> int:
        number = len(self.issues) + 1
        self.issues[number] = {"title": title, "body": body, "labels": [label], "state": "open"}
        self.calls.append("create")
        return number

    def update_issue(self, repository: str, number: int, title: str, body: str) -> None:
        self.issues[number].update(title=title, body=body)
        self.calls.append("update")

    def comment(self, repository: str, number: int, body: str) -> None:
        self.comments.append((number, body))
        self.calls.append("comment")

    def close_issue(self, repository: str, number: int) -> None:
        self.issues[number]["state"] = "closed"
        self.calls.append("close")


REF = watch.Reference(
    repository="dotabuff/manta",
    branch="master",
    commit=PIN,
    role="Primary reference",
    watch=("*.go", "src/**"),
    ignore=("*_test.go", "callbacks.go"),
)


def _run(github: FakeGitHub, ref: watch.Reference = REF) -> str:
    report = watch.build_report(ref, github)
    return watch.sync_issue(report, github, "owner/gem", dry_run=False)


def test_watched_files_star_stays_in_one_directory() -> None:
    files = [
        "field.go",
        "dota/x.pb.go",
        "field_test.go",
        "callbacks.go",
        "src/a/b.java",
        "README.md",
    ]
    assert watch.watched_files(REF, files) == ("field.go", "src/a/b.java")


def test_lock_file_is_valid_and_covers_the_three_references() -> None:
    refs = watch.load_lock(REPO_ROOT / "upstream-refs.lock.json")
    assert [r.repository for r in refs] == ["dotabuff/manta", "skadistats/clarity", "odota/parser"]


def test_claude_md_table_matches_the_lock() -> None:
    """CLAUDE.md shows the pins; the lock is the source of truth."""
    refs = {r.repository: r.commit for r in watch.load_lock(REPO_ROOT / "upstream-refs.lock.json")}
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    table = dict(
        re.findall(
            r"\| \[([\w-]+/[\w-]+)\]\(https://github\.com/[\w-]+/[\w-]+/tree/([0-9a-f]{40})\)", text
        )
    )
    assert table == refs


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            {"repository": "manta", "branch": "m", "commit": PIN, "role": "r", "watch": ["*"]},
            "owner/name",
        ),
        (
            {"repository": "a/b", "branch": "m", "commit": "abc", "role": "r", "watch": ["*"]},
            "40-character",
        ),
        (
            {"repository": "a/b", "branch": "m", "commit": PIN, "role": "r", "watch": []},
            "at least one",
        ),
    ],
)
def test_load_lock_rejects_bad_entries(tmp_path: Path, entry: dict, message: str) -> None:
    path = tmp_path / "lock.json"
    path.write_text(json.dumps({"schema_version": 1, "references": [entry]}))
    with pytest.raises(watch.UpstreamWatchError, match=message):
        watch.load_lock(path)


def test_first_run_opens_one_issue_listing_relevant_commits() -> None:
    gh = FakeGitHub(
        [(_sha(1), ["field.go"]), (_sha(2), ["README.md"]), (_sha(3), ["field_test.go"])]
    )
    assert "opened #1 with 1 commits" in _run(gh)
    body = gh.issues[1]["body"]
    assert _listed(body, _sha(1)) and not _listed(body, _sha(2)) and not _listed(body, _sha(3))
    assert f"last={_sha(3)}" in body
    assert gh.comments == [] and gh.labels == {"upstream"}


def test_second_run_without_new_commits_posts_nothing() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    _run(gh)
    gh.calls.clear()
    assert "no new commits" in _run(gh)
    assert gh.calls == []


def test_new_upstream_commit_is_commented_once() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    _run(gh)
    gh.history.append((_sha(2), ["entity.go"]))
    assert "1 new commits on #1" in _run(gh)
    assert len(gh.comments) == 1
    assert _listed(gh.comments[0][1], _sha(2)) and not _listed(gh.comments[0][1], _sha(1))
    gh.calls.clear()
    _run(gh)
    assert gh.calls == []


def test_unwatched_new_commit_updates_the_marker_without_a_comment() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    _run(gh)
    gh.history.append((_sha(2), ["README.md"]))
    _run(gh)
    assert gh.comments == [] and f"last={_sha(2)}" in gh.issues[1]["body"]


def test_pin_bump_drops_covered_commits_without_commenting() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"]), (_sha(2), ["entity.go"])])
    _run(gh)
    _run(gh, replace(REF, commit=_sha(1)))
    body = gh.issues[1]["body"]
    assert not _listed(body, _sha(1)) and _listed(body, _sha(2))
    assert gh.comments == []


def test_pin_covering_everything_closes_the_issue() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    _run(gh)
    assert "closed #1" in _run(gh, replace(REF, commit=_sha(1)))
    assert gh.issues[1]["state"] == "closed" and len(gh.comments) == 1


def test_merge_commits_are_skipped() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"]), (_sha(2), ["field.go"])], merges={_sha(2)})
    report = watch.build_report(REF, gh)
    assert [c.sha for c in report.commits] == [_sha(1)]


def test_diverged_pin_is_an_error() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    gh.compare = lambda *a: ("diverged", 1, [])  # type: ignore[method-assign]
    with pytest.raises(watch.UpstreamWatchError, match="diverged"):
        watch.build_report(REF, gh)


def test_dry_run_writes_nothing() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    report = watch.build_report(REF, gh)
    assert watch.sync_issue(report, gh, "owner/gem", dry_run=True).startswith("[dry run]")
    assert gh.calls == [] and gh.issues == {}


def test_long_reports_stay_under_githubs_body_limit() -> None:
    commits = tuple(
        watch.Commit(_sha(n), "2026-10-07", "x" * 200, ("src/" + "y" * 60 + ".java",) * 6)
        for n in range(1, 2000)
    )
    report = watch.Report(REF, _sha(1999), 1999, commits, tuple(c.sha for c in commits))
    body = watch.render_body(report)
    assert len(body) < 65_536 and "more commits; see the compare link" in body


def test_failed_comment_keeps_the_marker_so_the_next_run_retries() -> None:
    gh = FakeGitHub([(_sha(1), ["field.go"])])
    _run(gh)
    gh.history.append((_sha(2), ["entity.go"]))

    def fail(*args: object) -> None:
        raise watch.UpstreamWatchError("HTTP 502")

    real_comment = gh.comment
    gh.comment = fail  # type: ignore[method-assign]
    with pytest.raises(watch.UpstreamWatchError):
        _run(gh)
    assert f"last={_sha(1)}" in gh.issues[1]["body"]

    gh.comment = real_comment  # type: ignore[method-assign]
    assert "1 new commits on #1" in _run(gh)
    assert len(gh.comments) == 1 and _listed(gh.comments[0][1], _sha(2))
    assert f"last={_sha(2)}" in gh.issues[1]["body"]


def test_rest_commit_files_follows_pages_and_renames(monkeypatch: pytest.MonkeyPatch) -> None:
    page_one = [{"filename": f"docs/{n}.md"} for n in range(watch.FILES_PER_PAGE)]
    page_two = [{"filename": "src/new/field.go", "previous_filename": "field.go"}]
    requested: list[str] = []

    def fake_request(
        self: watch.RestGitHub, method: str, path: str, payload: object = None
    ) -> dict:
        requested.append(path)
        return {"files": page_one if path.endswith("&page=1") else page_two}

    monkeypatch.setattr(watch.RestGitHub, "_request", fake_request)
    files = watch.RestGitHub(None).commit_files("dotabuff/manta", _sha(1))
    assert len(requested) == 2
    assert "src/new/field.go" in files and "field.go" in files
    assert watch.watched_files(REF, files) == ("src/new/field.go", "field.go")
