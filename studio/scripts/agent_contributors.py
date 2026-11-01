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
PAREN_ID = re.compile(r"^(.*?)\(\s*(claude|codex)[- ]?(\d{2})(?!\d)", re.I)
FROM_ID = re.compile(r"\(from\s+(claude|codex)[- ]?(\d{2})(?!\d)\)", re.I)
AUTH = re.compile(r"/login|authentication_error|invalid api key|oauth token has expired|please run /login", re.I)
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


def title_sender(first: str):
    """(harness, role|None) from the SENDER part of a handoff's first line, else None. The sender part is the text before the
    first arrow or ' to ', or before ':' when there is neither, so a recipient ID ('-> claude-04') is never taken as the author."""
    body = re.sub(r"^[#>\s]*(?:READY:\s*)?", "", first)
    parts = re.split(r"\s*(?:→|->|\bto\b)\s*", body, maxsplit=1)
    seg = parts[0] if len(parts) == 2 else body.split(":", 1)[0] if ":" in body else ""
    m = HARNESS.search(seg)
    if m:
        h = f"{m.group(1).lower()}-{m.group(2)}"
        p = PAREN_ID.match(seg)
        role = p.group(1).strip().lower() if p else ""
        return h, (role if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", role) else None)
    f = FROM_ID.search(body)
    return (f"{f.group(1).lower()}-{f.group(2)}", None) if f else None


def classify_pane(text: str) -> str:
    """A state class from a pane's last lines; the text itself is never kept. 'idle' is an empty input prompt with no busy
    marker; it says nothing about whether the harness did work earlier."""
    low = text.lower()
    if AUTH.search(low):
        return "auth_blocked"
    if "esc to interrupt" in low:
        return "working"
    if re.search(r"api error|hook error", low):
        return "error_visible"
    if any(re.fullmatch(r"\s*[❯>]\s*", line) for line in text.splitlines()[-8:]):
        return "idle"
    return "unknown"


def scan_messages(files: dict[str, tuple[bytes, float]], window_start: float, sessions: set[str]) -> dict:
    """files: basename -> (bytes, mtime). Returns per-harness evidence and role names. Text is read, never returned."""
    authored, referenced, roles, unresolved, pre = {}, {}, {}, {}, 0
    parsed, role_map = {}, {}
    for name, (data, mtime) in sorted(files.items()):
        if mtime < window_start:
            pre += 1
            continue
        text = data.decode("utf-8", "replace")
        first = next((line for line in text.splitlines() if line.strip()), "")
        parsed[name] = (data, mtime, text, title_sender(first))
        ts_ = parsed[name][3]
        if ts_ and ts_[1]:
            role_map.setdefault(ts_[1], {}).setdefault(ts_[0], []).append({"file": name, "sha256": sha(data)})
    conflicts = {r: sorted(v) for r, v in role_map.items() if len(v) > 1}
    role_map = {r: {"harness": next(iter(v)), "evidence": next(iter(v.values()))} for r, v in role_map.items() if r not in conflicts}
    for name, (data, mtime, text, tsend) in sorted(parsed.items()):
        stem = SUFFIX.sub("", name)
        ev = {"file": name, "sha256": sha(data), "mtime_utc": iso(mtime)}
        sender = stem.split("-to-")[0] if "-to-" in stem else None
        sid, basis = None, None
        m = HARNESS.match(sender or "")
        if m and norm_harness(sender) == f"{m.group(1).lower()}-{m.group(2)}":
            sid, basis = norm_harness(sender), "filename sender"
        elif tsend:
            sid, basis = tsend[0], "title sender"
        elif sender and sender.lower() in role_map:
            sid, basis = role_map[sender.lower()]["harness"], "role self-labelled in another handoff title"
        if sid:
            authored.setdefault(sid, []).append({**ev, "basis": basis})
        elif sender:
            roles.setdefault(sender, []).append(ev)
        for g in {f"{x.group(1).lower()}-{x.group(2)}" for x in HARNESS.finditer(text)}:
            if g == sid:
                continue
            if g in sessions:
                referenced.setdefault(g, []).append(ev)
            else:
                unresolved.setdefault(g, []).append(ev)
    return {"authored": authored, "referenced": referenced, "roles": roles, "unresolved_mentions": unresolved, "pre_window_files_skipped": pre,
            "role_map": role_map, "role_label_conflicts": conflicts}


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


def scan_tmux(panes: list[dict], ps_rows: list[tuple[int, int, str]], pane_text: dict | None = None) -> dict:
    """panes: {session, pid, activity, created}; ps_rows: (pid, ppid, comm). A session is LIVE when a claude/codex
    process is a descendant of its pane. That shows a process exists, not that it is working: pane_state (idle / auth_blocked / working)
    is a coarse read of the last lines, and contribution_activity stays unknown. session_activity is NOT evidence: a poller can touch every session."""
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
        out[norm_harness(p["session"])] = {"session": p["session"], "created_utc": iso(p["created"]), "harness_process": sorted(found), "live_harness_process": bool(found),
                                    "pane_state": classify_pane((pane_text or {}).get(p["session"], "")) if pane_text else "not_read"}
    acts = sorted(p["activity"] for p in panes)
    burst = max((sum(1 for y in acts if x <= y < x + 180) for x in acts), default=0)
    return {"sessions": out, "raw_session_names": len(panes), "max_sessions_active_within_180s": burst, "activity_poller_suspected": burst >= 10}


def verify_mapping(entries: list[dict], repo: str, window_start: float, files: dict) -> list[dict]:
    """Check each reviewed mapping entry against the artifact it names. verified = every evidence item resolves and is in the
    window. Commit authorship cannot separate agents (shared git identity), so a commit or branch shows the work exists and is
    in the window, and the harness link rests on the reviewed entry."""
    out = []
    for e in entries:
        checks = []
        for ev in e["evidence"]:
            k, ref = ev["kind"], ev["ref"]
            if k in ("commit", "branch"):
                r = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%H%x1f%ct", ref], capture_output=True, text=True)
                ok = r.returncode == 0 and "\x1f" in r.stdout
                sha_, ct = r.stdout.strip().split("\x1f") if ok else (None, "0")
                names = subprocess.run(["git", "-C", repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-m", "--first-parent", ref], capture_output=True, text=True).stdout.split() if ok and k == "commit" else []
                checks.append({**ev, "resolves": ok, "object": sha_, "in_window": ok and float(ct) >= window_start, "commit_time_utc": iso(float(ct)) if ok else None,
                               **({"files_changed": len(names), "sample_paths": names[:3]} if k == "commit" else {})})
            elif k == "handoff":
                f = files.get(ref)
                ok = f is not None and f[1] >= window_start
                head = next((line for line in f[0].decode("utf-8", "replace").splitlines() if line.strip()), "") if f else ""
                ts_ = title_sender(head)
                checks.append({**ev, "resolves": f is not None, "in_window": ok, "sha256": sha(f[0]) if f else None, "title_names_harness": bool(ts_ and ts_[0] == e["harness"])})
            else:
                checks.append({**ev, "resolves": False, "in_window": False, "reason": "unsupported evidence kind"})
        verified = bool(checks) and all(c["resolves"] and c["in_window"] and c.get("title_names_harness", True) for c in checks)
        out.append({("harness" if "harness" in e else "identity"): e.get("harness") or e["identity"], "role": e["role"], "verified": verified, "checks": checks})
    return out


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


def build(messages: dict, tmux: dict, git: dict, branch_names: list[str], jobs: dict, window_start: float, observed: float, mapping: list[dict] | None = None, native: list[dict] | None = None) -> dict:
    sessions = set(tmux["sessions"])
    sc = scan_messages(messages, window_start, sessions)
    rl = tier_for_roles(sc["roles"], sessions)
    supported = {h: {"basis": "authored handoff in window", "evidence": ev} for h, ev in sc["authored"].items() if h in sessions}
    for m in mapping or []:
        if m["verified"] and m["harness"] in sessions:
            cur = supported.setdefault(m["harness"], {"basis": "reviewed mapping, artifact verified", "evidence": []})
            cur["mapping"] = {"role": m["role"], "checks": m["checks"]}
    for h, ev in rl["exact"].items():
        supported.setdefault(h, {"basis": "handoff sender equals the session name", "evidence": ev})
    probable = {h: v for h, v in rl["probable"].items() if h not in supported}
    named_only = {h: len(ev) for h, ev in sc["referenced"].items() if h not in supported and h not in probable}
    authored_not_session = sorted(set(sc["authored"]) - sessions)
    nat = [n for n in (native or []) if n["verified"]]
    clash = [n["identity"] for n in (native or []) if n["identity"].lstrip("/").replace("/", "-") in sessions or n["identity"] in ("root", "/root", "codex-03")]
    assert not clash, f"native identity collides with a harness or root: {clash}"
    work = [b for b in branch_names if b.startswith(("work/", "codex/"))]
    return {
        "schema": SCHEMA,
        "window": {"start_utc": iso(window_start), "observed_utc": iso(observed), "basis": "handoff mtimes, commit times and provider job times inside the window; earlier evidence is skipped, not counted"},
        "counts": {
            "distinct_contributing_harness_ids_supported_minimum": len(supported),
            "native_contributors_supported_minimum": len(nat),
            "harness_ids_probable_not_counted": len(probable),
            "harness_ids_named_by_others_only": len(named_only),
            "tmux_session_names_raw": tmux["raw_session_names"],
            "tmux_sessions_after_rename_dedup": len(sessions),
            "live_harness_processes_now": sum(v["live_harness_process"] for v in tmux["sessions"].values()),
            "pane_state_counts": {s: sum(1 for v in tmux["sessions"].values() if v["pane_state"] == s) for s in sorted({v["pane_state"] for v in tmux["sessions"].values()})},
            "roles_in_handoff_filenames": len(rl["plain_roles"]),
            "worker_branches": len(work),
            "provider_jobs_own": jobs.get("own_jobs"),
            "git_identities_in_window": len(git["git_identities"]),
            "models_in_trailers": len(git["models_in_trailers"]),
        },
        "not_summed": "roles, jobs, branches, models and process counts are different units; only the separately documented disjoint participation identities may be summed",
        "supported_harnesses": {k: supported[k] for k in sorted(supported)},
        "probable_aliases": {k: probable[k] for k in sorted(probable)},
        "named_by_others_only": dict(sorted(named_only.items())),
        "authored_ids_without_a_session": authored_not_session,
        "unresolved_mentions": {k: len(v) for k, v in sorted(sc["unresolved_mentions"].items())},
        "native_contributors": {"class": "native collaboration agent; a separate identity class from tmux harnesses; root not counted again",
                                "supported_minimum": len(nat), "identities": [n["identity"] for n in nat], "entries": native or [],
                                "combined_with_harness_floor_if_classes_are_disjoint": len(supported) + len(nat),
                                "combined_note": "a sum across two identity classes, valid only while no native identity is an alias of a harness; neither is an estimate of everyone who contributed"},
        "contribution_activity": "unknown for every session: a live process, an idle prompt or an auth block is not work",
        "native_agents": {"count": len(nat), "status": "supported minimum from root's attestation with verified commits; not a census"},
        "role_to_harness_self_labelled": sc["role_map"],
        "role_label_conflicts": sc["role_label_conflicts"],
        "reviewed_mapping": mapping or [],
        "tmux": tmux["sessions"],
        "activity_poller_suspected": tmux["activity_poller_suspected"],
        "max_sessions_active_within_180s": tmux["max_sessions_active_within_180s"],
        "roles": rl["plain_roles"],
        "worker_branch_names": work,
        "git": git,
        "dedup_rules": ["claude13, claude-13 and Claude 13 are one ID", "'-retired-N' suffix is a rename of the same session",
                        "'-rN' sessions stay distinct (separate process) and are flagged as possibly the same role", "a model name is not an agent",
                        "the shared git identity 'SciDEX Bot' cannot distinguish agents"],
        "unknowns": ["which roles map to which harness except where a handoff title labels itself or the reviewed mapping verifies", "work by agents that wrote no handoff and no commit under a distinct identity",
                     "whether tmux sessions created before the window were reused for hackathon work (reported only if they authored in the window)",
                     "historical native participation is reconstructed separately from scoped transcripts when the participation receipt is present"],
        "privacy": "private handoff files were read for ids only; only names, sha256 and times are published",
    }


def live_inputs(messages_dir: str, repo: str):
    mdir = Path(messages_dir)
    files = {f.name: (f.read_bytes(), f.stat().st_mtime) for f in sorted(mdir.iterdir()) if f.is_file()}
    raw = subprocess.run(["tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_pid}\t#{session_activity}\t#{session_created}"], capture_output=True, text=True).stdout
    panes = [{"session": a, "pid": int(b), "activity": float(c), "created": float(d)} for a, b, c, d in (line.split("\t") for line in raw.splitlines())]
    psr = subprocess.run(["ps", "-eo", "pid,ppid,comm"], capture_output=True, text=True).stdout.splitlines()[1:]
    ps_rows = [(int(x.split()[0]), int(x.split()[1]), x.split()[2]) for x in psr]
    texts = {p["session"]: subprocess.run(["tmux", "capture-pane", "-p", "-t", p["session"], "-S", "-25"], capture_output=True, text=True).stdout for p in panes}
    return files, panes, ps_rows, texts


def attach_participation(out: dict, participation: dict, source_sha256: str):
    """Add transcript-backed participants without re-adding artifact-backed natives."""
    children = participation["participants"]
    native = {r["identity"] for r in children if r["kind"] == "codex_native_child"}
    nested = {r["identity"] for r in children if r["kind"] == "claude_nested_child"}
    if not set(out["native_contributors"]["identities"]) <= native:
        raise ValueError("participation receipt misses previously supported native identities")
    if native & set(out["supported_harnesses"]) or nested & set(out["supported_harnesses"]):
        raise ValueError("child identity overlaps a harness")
    out["participation"] = {
        "source": "results/resources/agent-participation.json",
        "source_sha256": source_sha256,
        "window": participation["window"],
        "supported_harnesses": len(out["supported_harnesses"]),
        "recorded_native_children": len(native),
        "recorded_nested_claude_children": len(nested),
        "recorded_participant_floor": len(out["supported_harnesses"]) + len(native) + len(nested),
        "basis": "Disjoint harness, native child and nested Claude child identities; native artifact floor is already included, never added again. Root/codex-03 is counted once among harnesses. Participation is not successful task completion.",
        "live_native_api": participation["live_native_api"],
        "task_units": participation["counts"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--messages", default="/data/artifacts/delphi-evolve-rethink/messages")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="results/resources/agent-contributors.json")
    ap.add_argument("--window-start", default=WINDOW_START)
    a = ap.parse_args()
    ws = ts(a.window_start)
    files, panes, ps_rows, texts = live_inputs(a.messages, a.repo)
    tm = scan_tmux(panes, ps_rows, texts)
    mp = json.load(open(Path(a.repo) / "results/resources/agent-contributor-mapping.json"))
    mapping = verify_mapping(mp["entries"], a.repo, ws, files)
    native = verify_mapping(mp.get("native_contributors", []), a.repo, ws, files)
    g = scan_git(git_log(a.repo), ws)
    usage = json.load(open(Path(a.repo) / "results/resources/hackathon-usage.json"))
    jobs = {"own_jobs": len(usage["own_jobs"]), "source": "results/resources/hackathon-usage.json", "source_sha256": sha((Path(a.repo) / "results/resources/hackathon-usage.json").read_bytes())}
    out = build(files, tm, g, branches(a.repo), jobs, ws, dt.datetime.now(dt.timezone.utc).timestamp(), mapping, native)
    out["worker_jobs_source"] = jobs
    participation = Path(a.repo) / "results/resources/agent-participation.json"
    if participation.exists():
        attach_participation(out, json.loads(participation.read_bytes()), sha(participation.read_bytes()))
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["counts"], indent=1))


if __name__ == "__main__":
    main()
