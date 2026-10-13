"""Report upstream reference commits that gem has not caught up with yet.

gem's parser follows three reference implementations pinned in
``upstream-refs.lock.json`` (dotabuff/manta, skadistats/clarity, odota/parser).
For each one this lists the commits between the pin and the default branch that
touch a watched path, and keeps one GitHub issue per repository labelled
``upstream``:

- the issue body lists every relevant commit since the pin and is rewritten on
  each run, so a pin bump drops the commits it covers;
- a comment is posted only for commits newer than the last report (the body's
  hidden marker records the upstream HEAD it last saw);
- the issue closes once the pin covers every relevant commit.

Usage:
    uv run python scripts/check_upstream_refs.py --dry-run
    uv run python scripts/check_upstream_refs.py --issues-repo owner/name
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCK_PATH = REPO_ROOT / "upstream-refs.lock.json"
ISSUE_LABEL = "upstream"
MAX_FILES_SHOWN = 6
# GitHub rejects issue bodies over 65,536 characters; leave room for the footer.
MAX_ROWS_CHARS = 55_000
_SHA_RE = re.compile(r"[0-9a-f]{40}")
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_MARKER_RE = re.compile(r"<!-- upstream-watch repo=(\S+) last=([0-9a-f]{40}) -->")


class UpstreamWatchError(RuntimeError):
    """Raised when the lock or a GitHub response cannot be trusted."""


@dataclass(frozen=True)
class Reference:
    """One pinned upstream repository and the paths gem follows in it."""

    repository: str
    branch: str
    commit: str
    role: str
    watch: tuple[str, ...]
    ignore: tuple[str, ...]


@dataclass(frozen=True)
class Commit:
    """An upstream commit and the watched files it touches."""

    sha: str
    date: str
    subject: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    """The relevant commits between a pin and the upstream HEAD."""

    reference: Reference
    head: str
    ahead_by: int
    commits: tuple[Commit, ...]
    shas_in_range: tuple[str, ...]


@dataclass(frozen=True)
class Issue:
    """An open upstream-watch issue."""

    number: int
    body: str


class GitHub(Protocol):
    """The GitHub operations the watcher needs (a fake replaces it in tests)."""

    def head(self, repository: str, branch: str) -> str: ...

    def compare(self, repository: str, base: str, head: str) -> tuple[str, int, list[dict]]: ...

    def commit_files(self, repository: str, sha: str) -> list[str]: ...

    def open_issues(self, repository: str, label: str) -> list[Issue]: ...

    def ensure_label(self, repository: str, label: str) -> None: ...

    def create_issue(self, repository: str, title: str, body: str, label: str) -> int: ...

    def update_issue(self, repository: str, number: int, title: str, body: str) -> None: ...

    def comment(self, repository: str, number: int, body: str) -> None: ...

    def close_issue(self, repository: str, number: int) -> None: ...


def _require_string(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UpstreamWatchError(f"{where}: {key!r} must be a non-empty string")
    return value


def _patterns(data: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(p, str) and p for p in value):
        raise UpstreamWatchError(f"{where}: {key!r} must be a list of non-empty strings")
    return tuple(value)


def load_lock(path: Path) -> list[Reference]:
    """Read and validate ``upstream-refs.lock.json``.

    Args:
        path: The lock file.

    Returns:
        The pinned references, in file order.

    Raises:
        UpstreamWatchError: When the file is missing, malformed or invalid.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UpstreamWatchError(f"lock file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UpstreamWatchError(f"lock file is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise UpstreamWatchError("lock file must be an object with schema_version 1")
    raw = data.get("references")
    if not isinstance(raw, list) or not raw:
        raise UpstreamWatchError("lock field 'references' must be a non-empty list")

    references: list[Reference] = []
    for index, entry in enumerate(raw):
        where = f"references[{index}]"
        if not isinstance(entry, dict):
            raise UpstreamWatchError(f"{where} must be an object")
        repository = _require_string(entry, "repository", where)
        if not _REPOSITORY_RE.fullmatch(repository):
            raise UpstreamWatchError(f"{where}: 'repository' must use the owner/name form")
        commit = _require_string(entry, "commit", where)
        if not _SHA_RE.fullmatch(commit):
            raise UpstreamWatchError(f"{where}: 'commit' must be a lowercase 40-character SHA")
        watch = _patterns(entry, "watch", where)
        if not watch:
            raise UpstreamWatchError(f"{where}: 'watch' must list at least one path pattern")
        references.append(
            Reference(
                repository=repository,
                branch=_require_string(entry, "branch", where),
                commit=commit,
                role=_require_string(entry, "role", where),
                watch=watch,
                ignore=_patterns(entry, "ignore", where),
            )
        )
    if len({r.repository for r in references}) != len(references):
        raise UpstreamWatchError("each repository may appear only once in the lock")
    return references


def _glob_regex(pattern: str) -> re.Pattern[str]:
    # `**` crosses directories, `*` and `?` do not, so `*.go` means top-level only.
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def watched_files(reference: Reference, files: Sequence[str]) -> tuple[str, ...]:
    """Return the files a reference watches, minus its ignored ones.

    Args:
        reference: The pinned reference and its patterns.
        files: Repository-relative paths a commit touched.

    Returns:
        The touched files that match a ``watch`` pattern and no ``ignore`` one.
    """
    watch = [_glob_regex(p) for p in reference.watch]
    ignore = [_glob_regex(p) for p in reference.ignore]
    return tuple(
        f
        for f in files
        if any(p.fullmatch(f) for p in watch) and not any(p.fullmatch(f) for p in ignore)
    )


def build_report(reference: Reference, github: GitHub) -> Report:
    """List the commits since the pin that touch a watched path.

    Args:
        reference: The pinned reference.
        github: GitHub client.

    Returns:
        The report, oldest commit first.

    Raises:
        UpstreamWatchError: When the pin is not an ancestor of the upstream HEAD.
    """
    head = github.head(reference.repository, reference.branch)
    if head == reference.commit:
        return Report(reference, head, 0, (), ())
    status, ahead_by, raw_commits = github.compare(reference.repository, reference.commit, head)
    if status not in ("ahead", "identical"):
        raise UpstreamWatchError(
            f"{reference.repository}: pin {reference.commit[:12]} is {status} relative to "
            f"{reference.branch} {head[:12]}; re-pin it to a commit on {reference.branch}"
        )
    commits: list[Commit] = []
    for raw in raw_commits:
        # A merge commit repeats changes its merged commits already list (clarity
        # merges `next` and release tags into master), so only those are shown.
        if len(raw.get("parents", [])) > 1:
            continue
        files = watched_files(reference, github.commit_files(reference.repository, raw["sha"]))
        if files:
            info = raw["commit"]
            commits.append(
                Commit(
                    sha=raw["sha"],
                    date=info["committer"]["date"][:10],
                    subject=info["message"].splitlines()[0] if info["message"] else "",
                    files=files,
                )
            )
    return Report(
        reference, head, ahead_by, tuple(commits), tuple(raw["sha"] for raw in raw_commits)
    )


def new_since(report: Report, last_reported: str | None) -> tuple[Commit, ...]:
    """Return the relevant commits made after the last reported upstream HEAD.

    Args:
        report: The current report.
        last_reported: The HEAD recorded by the previous report, if any.

    Returns:
        Every relevant commit when nothing was reported yet, or when the last
        reported HEAD is no longer in range (the pin moved past it, so all that
        remains is newer); otherwise those after it.
    """
    if last_reported is None or last_reported not in report.shas_in_range:
        return report.commits
    cutoff = report.shas_in_range.index(last_reported)
    later = set(report.shas_in_range[cutoff + 1 :])
    return tuple(c for c in report.commits if c.sha in later)


def _commit_rows(repository: str, commits: Sequence[Commit]) -> list[str]:
    rows = ["| Commit | Date | Subject | Watched files |", "|---|---|---|---|"]
    size = 0
    for index, c in enumerate(commits):
        if size > MAX_ROWS_CHARS:
            rows.append(f"| … | | {len(commits) - index} more commits; see the compare link | |")
            break
        shown = ", ".join(f"`{f}`" for f in c.files[:MAX_FILES_SHOWN])
        if len(c.files) > MAX_FILES_SHOWN:
            shown += f" and {len(c.files) - MAX_FILES_SHOWN} more"
        subject = c.subject.replace("|", "\\|")
        link = f"[`{c.sha[:8]}`](https://github.com/{repository}/commit/{c.sha})"
        rows.append(f"| {link} | {c.date} | {subject} | {shown} |")
        size += len(rows[-1])
    return rows


def issue_title(report: Report) -> str:
    """Return the issue title for a report with relevant commits."""
    n = len(report.commits)
    return f"Upstream {report.reference.repository}: {n} commit{'s' * (n != 1)} since the pin"


def render_body(report: Report) -> str:
    """Render the issue body: every relevant commit since the pin, plus the marker.

    Args:
        report: A report with at least one relevant commit.

    Returns:
        Markdown for the issue body.
    """
    ref = report.reference
    compare = f"https://github.com/{ref.repository}/compare/{ref.commit}...{report.head}"
    lines = [
        f"gem pins **{ref.repository}** ({ref.role}) at `{ref.commit[:12]}` in "
        "`upstream-refs.lock.json`. Since then its `"
        f"{ref.branch}` branch has {report.ahead_by} commits ([compare]({compare})); "
        f"{len(report.commits)} touch a path gem follows.",
        "",
        *_commit_rows(ref.repository, report.commits),
        "",
        "Review each against gem (CLAUDE.md: read the upstream source before changing "
        "parser code), port what applies, then bump the pin in "
        "`upstream-refs.lock.json` and CLAUDE.md. This issue is rewritten daily by "
        "`.github/workflows/upstream-watch.yml` and closes once the pin covers every "
        "commit listed.",
        "",
        f"Watched: {', '.join(f'`{p}`' for p in ref.watch)}"
        + (f"; ignored: {', '.join(f'`{p}`' for p in ref.ignore)}" if ref.ignore else ""),
        "",
        f"<!-- upstream-watch repo={ref.repository} last={report.head} -->",
    ]
    return "\n".join(lines) + "\n"


def render_comment(report: Report, commits: Sequence[Commit]) -> str:
    """Render the notification comment for newly seen commits."""
    n = len(commits)
    lines = [
        f"{n} new commit{'s' * (n != 1)} on {report.reference.repository} "
        f"`{report.reference.branch}` touch{'es' * (n == 1)} a watched path:",
        "",
        *_commit_rows(report.reference.repository, commits),
    ]
    return "\n".join(lines) + "\n"


def _find_issue(issues: Sequence[Issue], repository: str) -> tuple[Issue | None, str | None]:
    for issue in issues:
        match = _MARKER_RE.search(issue.body)
        if match and match.group(1) == repository:
            return issue, match.group(2)
    return None, None


def sync_issue(report: Report, github: GitHub, issues_repo: str, *, dry_run: bool) -> str:
    """Create, update, comment on or close the reference's issue.

    Args:
        report: The current report.
        github: GitHub client.
        issues_repo: The repository that holds the issues (gem's).
        dry_run: Describe the action without writing anything.

    Returns:
        A one-line description of what was (or would be) done.
    """
    repository = report.reference.repository
    issue, last = _find_issue(github.open_issues(issues_repo, ISSUE_LABEL), repository)
    prefix = "[dry run] " if dry_run else ""

    if not report.commits:
        if issue is None:
            return f"{repository}: up to date"
        if not dry_run:
            github.comment(
                issues_repo,
                issue.number,
                f"The pin now covers every watched commit (upstream `{report.head[:12]}`).",
            )
            github.close_issue(issues_repo, issue.number)
        return f"{prefix}{repository}: closed #{issue.number}"

    title, body = issue_title(report), render_body(report)
    fresh = new_since(report, last)
    if issue is None:
        if dry_run:
            return f"{prefix}{repository}: would open an issue with {len(report.commits)} commits"
        github.ensure_label(issues_repo, ISSUE_LABEL)
        number = github.create_issue(issues_repo, title, body, ISSUE_LABEL)
        return f"{repository}: opened #{number} with {len(report.commits)} commits"
    if not dry_run and issue.body != body:
        github.update_issue(issues_repo, issue.number, title, body)
    if fresh:
        if not dry_run:
            github.comment(issues_repo, issue.number, render_comment(report, fresh))
        return f"{prefix}{repository}: {len(fresh)} new commits on #{issue.number}"
    return f"{prefix}{repository}: no new commits on #{issue.number}"


class RestGitHub:
    """GitHub REST client over ``urllib``."""

    def __init__(self, token: str | None) -> None:
        self._token = token

    def _request(self, method: str, path: str, payload: dict | None = None) -> Any:
        url = path if path.startswith("https://") else f"https://api.github.com{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "gem-dota-upstream-watch",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        try:
            with urlopen(Request(url, data, headers, method=method), timeout=30) as response:
                text = response.read().decode()
                return json.loads(text) if text else None
        except HTTPError as exc:
            raise UpstreamWatchError(f"GitHub API returned HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise UpstreamWatchError(f"GitHub API request failed for {url}: {exc.reason}") from exc

    def head(self, repository: str, branch: str) -> str:
        return self._request("GET", f"/repos/{repository}/commits/{quote(branch, safe='')}")["sha"]

    def compare(self, repository: str, base: str, head: str) -> tuple[str, int, list[dict]]:
        commits: list[dict] = []
        page = 1
        while True:
            query = urlencode({"per_page": 100, "page": page})
            data = self._request("GET", f"/repos/{repository}/compare/{base}...{head}?{query}")
            commits.extend(data["commits"])
            if not data["commits"] or len(commits) >= data["ahead_by"]:
                return data["status"], data["ahead_by"], commits
            page += 1

    def commit_files(self, repository: str, sha: str) -> list[str]:
        return [
            f["filename"]
            for f in self._request("GET", f"/repos/{repository}/commits/{sha}")["files"]
        ]

    def open_issues(self, repository: str, label: str) -> list[Issue]:
        query = urlencode({"labels": label, "state": "open", "per_page": 100})
        items = self._request("GET", f"/repos/{repository}/issues?{query}")
        return [Issue(i["number"], i.get("body") or "") for i in items if "pull_request" not in i]

    def ensure_label(self, repository: str, label: str) -> None:
        try:
            self._request(
                "POST",
                f"/repos/{repository}/labels",
                {
                    "name": label,
                    "color": "5319E7",
                    "description": "Upstream reference commits gem has not reviewed yet",
                },
            )
        except UpstreamWatchError as exc:
            if "HTTP 422" not in str(exc):  # 422: the label already exists
                raise

    def create_issue(self, repository: str, title: str, body: str, label: str) -> int:
        payload = {"title": title, "body": body, "labels": [label]}
        return int(self._request("POST", f"/repos/{repository}/issues", payload)["number"])

    def update_issue(self, repository: str, number: int, title: str, body: str) -> None:
        self._request(
            "PATCH", f"/repos/{repository}/issues/{number}", {"title": title, "body": body}
        )

    def comment(self, repository: str, number: int, body: str) -> None:
        self._request("POST", f"/repos/{repository}/issues/{number}/comments", {"body": body})

    def close_issue(self, repository: str, number: int) -> None:
        payload = {"state": "closed", "state_reason": "completed"}
        self._request("PATCH", f"/repos/{repository}/issues/{number}", payload)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK_PATH, help="pin lock path")
    parser.add_argument(
        "--issues-repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="owner/name of the repository holding the issues (default: $GITHUB_REPOSITORY)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    parser.add_argument("--repository", help="check only this upstream owner/name")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    github = RestGitHub(os.environ.get("GITHUB_TOKEN"))
    try:
        references = load_lock(args.lock)
        if args.repository:
            references = [r for r in references if r.repository == args.repository]
            if not references:
                raise UpstreamWatchError(f"{args.repository} is not in {args.lock}")
        if not args.dry_run and not args.issues_repo:
            raise UpstreamWatchError("--issues-repo (or $GITHUB_REPOSITORY) is required")
        for reference in references:
            report = build_report(reference, github)
            if args.dry_run:
                print(f"## {reference.repository}\n")
                print(render_body(report) if report.commits else "Up to date.\n")
            if args.issues_repo:
                print(sync_issue(report, github, args.issues_repo, dry_run=args.dry_run))
        return 0
    except UpstreamWatchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
