#!/usr/bin/env python3
"""Evidence-backed count of distinct hackathon contributors. Read-only; emits ids, counts, times and hashes, never message text.

    python3 scripts/agent_contributors.py [--messages DIR] [--repo DIR] [--out FILE] [--window-start ISO]

Layers are kept apart because they are different things: harness IDs (a named tmux/CLI identity), roles (names in
handoff filenames), worker jobs (branches and provider jobs), models (commit trailers) and git identities. Nothing here is
summed into one "agents" number. A harness counts as SUPPORTED only with authored evidence in the window.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

SCHEMA = "frontier.agent-contributors/1"
WINDOW_START = "2026-10-31T00:00:00-07:00"  # Frontier repo's first commit and the usage ledgers' "created October 31" scope
HARNESS = re.compile(r"(?<![a-z0-9])(claude|codex)[- ]?(\d{2})(?![\d]|-[A-Z])", re.I)
TITLE_SENDER = re.compile(r"^#\s*(?:READY:\s*)?(claude|codex)[- ]?(\d{2})\s*(?:→|->|to\b)", re.I)
SUFFIX = re.compile(r"\.(md|json|txt|log)$")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_harness(name: str) -> str:
    """claude13 / claude-13 / Claude 13 -> claude-13; a '-retired-N' suffix is a rename of the same session."""
    m = re.fullmatch(r"(claude|codex)[- ]?(\d{2})", name.strip(), re.I)
    if m:
        return f"{m.group(1).lower()}-{m.group(2)}"
    return re.sub(r"-retired-\d+$", "", name.strip().lower())


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s).timestamp()


def iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def scan_messages(files: dict[str, tuple[bytes, float]], window_start: float, sessions: set[str]) -> dict:
    """files: basename -> (bytes, mtime). Returns per-harness evidence and role names. Text is read, never returned."""
    authored, referenced, roles, unresolved, pre = {}, {}, {}, {}, 0
    for name, (data, mtime) in sorted(files.items()):
        if mtime < window_start:
            pre += 1
            continue
        stem = SUFFIX.sub("", name)
        ev = {"file": name, "sha256": sha(data), "mtime_utc": iso(mtime)}
        sender = stem.split("-to-")[0] if "-to-" in stem else None
        text = data.decode("utf-8", "replace")
        first = next((l for l in text.splitlines() if l.strip()), "")
        sid = None
        m = HARNESS.fullmatch(sender or "") or HARNESS.match(sender or "")
        if m and norm_harness(sender) == f"{m.group(1).lower()}-{m.group(2)}":
            sid = norm_harness(sender)
        t = TITLE_SENDER.match(first)
        if sid is None and t:
            sid = f"{t.group(1).lower()}-{t.group(2)}"
        if sid:
            authored.setdefault(sid, []).append({**ev, "basis": "filename sender" if sender and norm_harness(sender) == sid else "title sender"})
        elif sender:
            roles.setdefault(sender, []).append(ev)
        for g in {f"{x.group(1).lower()}-{x.group(2)}" for x in HARNESS.finditer(text)}:
            if g == sid:
                continue
            if g in sessions:
                referenced.setdefault(g, []).append(ev)
            else:
                unresolved.setdefault(g, []).append(ev)
    return {"authored": authored, "referenced": referenced, "roles": roles, "unresolved_mentions": unresolved, "pre_window_files_skipped": pre}


def tier_for_roles(roles: dict, sessions: set[str]) -> dict:
    """A role name equal to a tmux session is SUPPORTED (exact); equal after stripping 'dx-' is PROBABLE (alias, unproven)."""
    exact, probable, plain = {}, {}, {}
    for r, ev in roles.items():
        n = norm_harness(r)
        if n in sessions:
            exact[n] = ev
        elif f"dx-{n}" in sessions:
            probable[f"dx-{n}"] = {"role_name": r, "evidence": ev}
        else:
            plain[r] = len(ev)
    return {"exact": exact, "probable": probable, "plain_roles": plain}


def scan_tmux(panes: list[dict], ps_rows: list[tuple[int, int, str]]) -> dict:
    """panes: {session, pid, activity, created}; ps_rows: (pid, ppid, comm). A session is ACTIVE-VERIFIED when a claude/codex
    process is a descendant of its pane. session_activity is NOT evidence: a poller can touch every session."""
    kids = {}
    for pid, ppid, comm in ps_rows:
        kids.setdefault(ppid, []).append((pid, comm))
    out = {}
    for p in panes:
        stack, found = [p["pid"]], set()
        while stack:
            x = stack.pop()
            for pid, comm in kids.get(x, []):
                if comm.startswith(("claude", "codex")):
                    found.add(comm)
                stack.append(pid)
        out[norm_harness(p["session"])] = {"session": p["session"], "created_utc": iso(p["created"]), "harness_process": sorted(found), "active_verified": bool(found)}
    acts = sorted(p["activity"] for p in panes)
    burst = max((sum(1 for y in acts if x <= y < x + 180) for x in acts), default=0)
    return {"sessions": out, "raw_session_names": len(panes), "max_sessions_active_within_180s": burst, "activity_poller_suspected": burst >= 10}


def scan_git(log_lines: list[tuple[str, str, str, str]], window_start: float) -> dict:
    """log_lines: (author_name, committed_epoch, co-author trailers, ref-agnostic). In-window commits only."""
    ids, models, n = {}, {}, 0
    for author, epoch, trailers, _ in log_lines:
        if float(epoch) < window_start:
            continue
        n += 1
        ids[author] = ids.get(author, 0) + 1
        for t in filter(None, trailers.split(";")):
            m = re.match(r"\s*(.+?)\s*<", t)
            if m:
                models[m.group(1)] = models.get(m.group(1), 0) + 1
    return {"commits_in_window": n, "git_identities": ids, "models_in_trailers": models}


def git_log(repo: str) -> list[tuple[str, str, str, str]]:
    out = subprocess.run(["git", "-C", repo, "log", "--remotes", "--format=%an%x1f%ct%x1f%(trailers:key=Co-Authored-By,valueonly,separator=;)%x1e"], capture_output=True, text=True, check=True).stdout
    rows = []
    for rec in out.split("\x1e"):
        p = rec.strip("\n").split("\x1f")
        if len(p) == 3:
            rows.append((p[0], p[1], p[2].replace("\n", ""), ""))
    return rows


def branches(repo: str) -> list[str]:
    out = subprocess.run(["git", "-C", repo, "branch", "-r", "--format=%(refname:short)"], capture_output=True, text=True, check=True).stdout.split()
    return sorted({b.split("/", 1)[1] for b in out if "/" in b and not b.endswith("HEAD")})


def build(messages: dict, tmux: dict, git: dict, branch_names: list[str], jobs: dict, window_start: float, observed: float) -> dict:
    sessions = set(tmux["sessions"])
    sc = scan_messages(messages, window_start, sessions)
    rl = tier_for_roles(sc["roles"], sessions)
    supported = {h: {"basis": "authored handoff in window", "evidence": ev} for h, ev in sc["authored"].items() if h in sessions}
    for h, ev in rl["exact"].items():
        supported.setdefault(h, {"basis": "handoff sender equals the session name", "evidence": ev})
    probable = {h: v for h, v in rl["probable"].items() if h not in supported}
    named_only = {h: len(ev) for h, ev in sc["referenced"].items() if h not in supported and h not in probable}
    authored_not_session = sorted(set(sc["authored"]) - sessions)
    work = [b for b in branch_names if b.startswith(("work/", "codex/"))]
    return {
        "schema": SCHEMA,
        "window": {"start_utc": iso(window_start), "observed_utc": iso(observed), "basis": "handoff mtimes, commit times and provider job times inside the window; earlier evidence is skipped, not counted"},
        "counts": {
            "distinct_contributing_harness_ids_supported_minimum": len(supported),
            "harness_ids_probable_not_counted": len(probable),
            "harness_ids_named_by_others_only": len(named_only),
            "tmux_session_names_raw": tmux["raw_session_names"],
            "tmux_sessions_after_rename_dedup": len(sessions),
            "tmux_sessions_with_live_harness_process_now": sum(v["active_verified"] for v in tmux["sessions"].values()),
            "roles_in_handoff_filenames": len(rl["plain_roles"]),
            "worker_branches": len(work),
            "provider_jobs_own": jobs.get("own_jobs"),
            "git_identities_in_window": len(git["git_identities"]),
            "models_in_trailers": len(git["models_in_trailers"]),
        },
        "not_summed": "these are different units; no total 'agents' number is given or implied",
        "supported_harnesses": {k: supported[k] for k in sorted(supported)},
        "probable_aliases": {k: probable[k] for k in sorted(probable)},
        "named_by_others_only": dict(sorted(named_only.items())),
        "authored_ids_without_a_session": authored_not_session,
        "unresolved_mentions": {k: len(v) for k, v in sorted(sc["unresolved_mentions"].items())},
        "tmux": tmux["sessions"],
        "activity_poller_suspected": tmux["activity_poller_suspected"],
        "max_sessions_active_within_180s": tmux["max_sessions_active_within_180s"],
        "roles": rl["plain_roles"],
        "worker_branch_names": work,
        "git": git,
        "dedup_rules": ["claude13, claude-13 and Claude 13 are one ID", "'-retired-N' suffix is a rename of the same session",
                        "'-rN' sessions stay distinct (separate process) and are flagged as possibly the same role", "a model name is not an agent",
                        "the shared git identity 'SciDEX Bot' cannot distinguish agents"],
        "unknowns": ["which roles map to which harness except where a handoff names its own ID", "work by agents that wrote no handoff and no commit under a distinct identity",
                     "whether tmux sessions created before the window were reused for hackathon work (reported only if they authored in the window)",
                     "the 'four native agents' reference count is not reconstructed here"],
        "privacy": "private handoff files were read for ids only; only names, sha256 and times are published",
    }


def live_inputs(messages_dir: str, repo: str):
    mdir = Path(messages_dir)
    files = {f.name: (f.read_bytes(), f.stat().st_mtime) for f in sorted(mdir.iterdir()) if f.is_file()}
    raw = subprocess.run(["tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_pid}\t#{session_activity}\t#{session_created}"], capture_output=True, text=True).stdout
    panes = [{"session": a, "pid": int(b), "activity": float(c), "created": float(d)} for a, b, c, d in (l.split("\t") for l in raw.splitlines())]
    psr = subprocess.run(["ps", "-eo", "pid,ppid,comm"], capture_output=True, text=True).stdout.splitlines()[1:]
    ps_rows = [(int(x.split()[0]), int(x.split()[1]), x.split()[2]) for x in psr]
    return files, panes, ps_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--messages", default="/data/artifacts/delphi-evolve-rethink/messages")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="results/resources/agent-contributors.json")
    ap.add_argument("--window-start", default=WINDOW_START)
    a = ap.parse_args()
    ws = ts(a.window_start)
    files, panes, ps_rows = live_inputs(a.messages, a.repo)
    tm = scan_tmux(panes, ps_rows)
    g = scan_git(git_log(a.repo), ws)
    usage = json.load(open(Path(a.repo) / "results/resources/hackathon-usage.json"))
    jobs = {"own_jobs": len(usage["own_jobs"]), "source": "results/resources/hackathon-usage.json", "source_sha256": sha((Path(a.repo) / "results/resources/hackathon-usage.json").read_bytes())}
    out = build(files, tm, g, branches(a.repo), jobs, ws, dt.datetime.now(dt.timezone.utc).timestamp())
    out["worker_jobs_source"] = jobs
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["counts"], indent=1))


if __name__ == "__main__":
    main()
