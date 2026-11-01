"""Audit public default-branch commit activity in an explicit UTC window.

Use GitHub's authenticated read API through gh; never retain commit author emails,
messages, credentials or repository settings. Counts describe commit objects, not
people, agent runs, useful work or scientific results. Shared history is deduplicated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, urlencode


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Audit timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def api(endpoint: str):
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError("GitHub read failed; raw response omitted")
    if len(result.stdout) > 8 * 1024 * 1024:
        raise ValueError("GitHub response exceeded the audit size limit")
    return json.loads(result.stdout)


def normalize_commits(rows: list, since: str, until: str) -> list[dict]:
    start, end = timestamp(since), timestamp(until)
    if start >= end:
        raise ValueError("since must precede until")
    unique = {}
    for row in rows:
        sha = row["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Unexpected commit ID")
        date = row["commit"]["committer"]["date"]
        if not start <= timestamp(date) <= end:
            continue
        record = {"sha": sha, "committed_at": date,
                  "parent_count": len(row["parents"]),
                  "author_login": (row.get("author") or {}).get("login")}
        if sha in unique and unique[sha] != record:
            raise ValueError("Conflicting metadata for a commit")
        unique[sha] = record
    return sorted(unique.values(), key=lambda r: (r["committed_at"], r["sha"]))


def repository(repo: str, since: str, until: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Expected owner/repository")
    meta = api(f"repos/{repo}")
    if meta.get("private") is not False:
        raise ValueError("This publication auditor accepts public repositories only")
    branch = meta["default_branch"]
    head = api(f"repos/{repo}/commits/{quote(branch, safe='')}")["sha"]
    rows = []
    for page in range(1, 101):
        query = urlencode({"sha": head, "since": since, "until": until,
                           "per_page": 100, "page": page})
        batch = api(f"repos/{repo}/commits?{query}")
        if not isinstance(batch, list):
            raise ValueError("Expected a commit list")
        rows.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError("Pagination bound reached; refuse an incomplete count")
    commits = normalize_commits(rows, since, until)
    return {"repository": repo, "url": f"https://github.com/{repo}",
            "default_branch": branch, "head_sha": head,
            "queried_at": datetime.now(timezone.utc).isoformat(),
            "pagination_complete": True, "commits": commits,
            "counts": counts(commits)}


def counts(commits: list[dict]) -> dict:
    return {"commit_objects": len(commits),
            "merge_commits": sum(r["parent_count"] > 1 for r in commits),
            "non_merge_commits": sum(r["parent_count"] <= 1 for r in commits),
            "distinct_linked_author_accounts": len({r["author_login"] for r in commits if r["author_login"]}),
            "commits_without_linked_author": sum(r["author_login"] is None for r in commits)}


def combine(repositories: list[dict], since: str, until: str) -> dict:
    commits, membership = {}, {}
    if len({r["repository"] for r in repositories}) != len(repositories):
        raise ValueError("Duplicate repository")
    for repo in repositories:
        for row in repo["commits"]:
            if row["sha"] in commits and commits[row["sha"]] != row:
                raise ValueError("Conflicting metadata across repositories")
            commits[row["sha"]] = row
            membership.setdefault(row["sha"], []).append(repo["repository"])
    return {"schema": "frontier.repository-activity/1",
            "since_utc": since, "until_utc": until,
            "scope": "Public default-branch ancestry at each recorded HEAD; inclusive committer-date window. Shared full SHA IDs counted once. Not all branches, all hackathon history, human or agent counts, or scientific achievement.",
            "repositories": repositories, "deduplicated_counts": counts(list(commits.values())),
            "sum_of_repository_commit_counts": sum(len(r["commits"]) for r in repositories),
            "shared_commit_membership": {k: v for k, v in sorted(membership.items()) if len(v) > 1}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if timestamp(args.since) >= timestamp(args.until):
        raise ValueError("since must precede until")
    repos = [repository(repo, args.since, args.until) for repo in args.repo]
    report = combine(repos, args.since, args.until)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Immutable audit files: a rerun must choose another destination.
    with args.output.open("x") as target:
        json.dump(report, target, indent=2)
        target.write("\n")
    print(json.dumps({"path": str(args.output), "counts": report["deduplicated_counts"]}))


if __name__ == "__main__":
    main()
