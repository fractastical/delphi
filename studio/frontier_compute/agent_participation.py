"""Bounded, text-free participation receipts from explicitly scoped local transcripts.

A transcript is evidence of recorded activity, not an assertion of successful work,
current liveness, paid API calls, or scientific acceptance. Raw content stays local.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

MAX_LINE = 16 * 1024 * 1024
MAX_FILE = 1024 * 1024 * 1024
FRONTIER_MARKERS = (
    "/data/worktrees/delphi-frontier/",
    "/data/artifacts/delphi-evolve-rethink/",
    "delphi frontier",
)


def epoch(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def text_parts(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(p.get("text", "") for p in content if isinstance(p, dict))


def records(path, receipt):
    """Capture complete lines within the initial byte boundary; never emit raw text."""
    size = path.stat().st_size
    if size > MAX_FILE:
        raise ValueError("transcript exceeds bounded scan size")
    digest = hashlib.sha256()
    consumed = lines = malformed = 0
    with path.open("rb") as stream:
        while consumed < size:
            line = stream.readline(min(MAX_LINE + 1, size - consumed))
            if len(line) > MAX_LINE:
                raise ValueError("transcript line exceeds bounded scan size")
            if not line.endswith(b"\n"):
                break
            consumed += len(line)
            digest.update(line)
            lines += 1
            try:
                row = json.loads(line)
            except ValueError:
                malformed += 1
                continue
            if isinstance(row, dict):
                yield row
    receipt.update(
        captured_bytes=consumed,
        captured_lines=lines,
        incomplete_tail_bytes=size - consumed,
        malformed_lines=malformed,
        captured_prefix_sha256=digest.hexdigest(),
    )


def in_window(timestamp, start, end):
    try:
        return start <= epoch(timestamp) <= end
    except (ValueError, AttributeError, TypeError):
        return False


def scan_claude(path, start, end):
    receipt = {"source": path.name, "parent_session": path.parent.parent.name}
    task_seen = False
    task_scoped = False
    task_time = None
    agents, models, messages, tools = set(), set(), set(), set()
    event_times = []
    for row in records(path, receipt):
        stamp = row.get("timestamp")
        message = row.get("message", {})
        if not isinstance(message, dict):
            continue
        if row.get("type") == "user" and not task_seen:
            task_seen = True
            task = text_parts(message.get("content")).lower()
            task_scoped = any(marker in task for marker in FRONTIER_MARKERS)
            task_time = stamp
        if not in_window(stamp, start, end) or row.get("type") != "assistant":
            continue
        if row.get("agentId"):
            agents.add(row["agentId"])
        if message.get("model"):
            models.add(message["model"])
        if message.get("id"):
            messages.add(message["id"])
        for block in message.get("content", []):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("id")
            ):
                tools.add(block["id"])
        event_times.append(stamp)
    expected = path.stem.removeprefix("agent-")
    reason = (
        "initial task outside window"
        if not in_window(task_time, start, end)
        else "initial task lacks explicit Frontier marker"
        if not task_scoped
        else "missing or inconsistent child identity"
        if agents != {expected}
        else "no recorded assistant activity"
        if not event_times
        else "malformed transcript lines"
        if receipt["malformed_lines"]
        else None
    )
    return {
        **receipt,
        "included": reason is None,
        "exclusion": reason,
        "identity": expected,
        "kind": "claude_nested_child",
        "provider_metadata": "Anthropic model IDs in Claude transcript",
        "models_recorded": sorted(models),
        "task_created_utc": task_time,
        "first_assistant_utc": min(event_times, default=None),
        "last_assistant_utc": max(event_times, default=None),
        "assistant_message_ids": len(messages),
        "tool_invocation_ids": len(tools),
        "successful_task_count": None,
        "active_now": None,
    }


def scan_codex(path, start, end, allowed_parents):
    receipt = {"source": path.name}
    meta = None
    identity = parent = None
    created = None
    models, calls, turns_started, turns_complete = set(), set(), set(), set()
    event_times = []
    for index, row in enumerate(records(path, receipt)):
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if row.get("type") == "session_meta":
            if meta is not None:
                # Full-history forks embed the parent's session_meta after their
                # own. It must not replace the child's identity or time boundary.
                continue
            meta = payload
            source = payload.get("source", {})
            spawn = (
                source.get("subagent", {}).get("thread_spawn", {})
                if isinstance(source, dict)
                else {}
            )
            identity, parent = spawn.get("agent_path"), spawn.get("parent_thread_id")
            created = payload.get("timestamp")
            continue
        # A fork can carry earlier history. Only count events after its creation,
        # and after the explicit inherited-history boundary where one is recorded.
        if (
            not meta
            or not created
            or index < meta.get("subagent_history_start_ordinal", 0)
        ):
            continue
        stamp = row.get("timestamp")
        if not in_window(stamp, max(start, epoch(created)), end):
            continue
        typ = row.get("type")
        if typ == "turn_context" and payload.get("model"):
            models.add(payload["model"])
        if typ == "event_msg" and payload.get("type") in (
            "task_started",
            "task_complete",
        ):
            target = (
                turns_started if payload["type"] == "task_started" else turns_complete
            )
            target.add(payload.get("turn_id") or row.get("timestamp"))
        if typ == "response_item" and payload.get("type") in (
            "function_call",
            "custom_tool_call",
        ):
            calls.add(payload.get("call_id") or payload.get("id") or str(index))
            event_times.append(stamp)
    reason = (
        "not an attested Frontier child"
        if parent not in allowed_parents or not identity
        else "child created outside window"
        if not in_window(created, start, end)
        else "no recorded tool activity"
        if not event_times
        else "malformed transcript lines"
        if receipt["malformed_lines"]
        else None
    )
    return {
        **receipt,
        "included": reason is None,
        "exclusion": reason,
        "identity": identity,
        "session_id": meta.get("id") if meta else None,
        "parent_thread_id": parent,
        "kind": "codex_native_child",
        "provider_metadata": meta.get("model_provider") if meta else None,
        "models_recorded": sorted(models),
        "task_created_utc": created,
        "first_tool_utc": min(event_times, default=None),
        "last_tool_utc": max(event_times, default=None),
        "tool_invocation_ids": len(calls),
        "task_turns_started": len(turns_started),
        "task_turns_complete_events": len(turns_complete),
        "successful_task_count": None,
        "active_now": None,
    }


def summarize(rows, start, end, live):
    included = [r for r in rows if r["included"]]
    identities = {(r["kind"], r["identity"]) for r in included}
    if len(identities) != len(included):
        raise ValueError("duplicate identity requires explicit resume deduplication")
    counts = collections.Counter(r["kind"] for r in included)
    return {
        "schema": "frontier.agent-participation/1",
        "window": {"start_utc": start, "observed_utc": end},
        "scope": "Explicit Frontier initial-task marker for Claude children; reviewed Frontier root thread for Codex children. Initial task and actual activity must be in window.",
        "counts": {
            "claude_nested_participants": counts["claude_nested_child"],
            "codex_native_participants": counts["codex_native_child"],
            "distinct_scoped_child_participants": len(identities),
            "claude_task_transcripts": counts["claude_nested_child"],
            "codex_task_turns_started": sum(
                r.get("task_turns_started", 0) for r in included
            ),
            "codex_task_complete_events": sum(
                r.get("task_turns_complete_events", 0) for r in included
            ),
            "scanned_transcripts": len(rows),
            "excluded_transcripts": len(rows) - len(included),
        },
        "participants": included,
        "exclusions": [
            {
                "source_name_sha256": hashlib.sha256(r["source"].encode()).hexdigest(),
                "exclusion": r["exclusion"],
                "captured_prefix_sha256": r["captured_prefix_sha256"],
            }
            for r in rows
            if not r["included"]
        ],
        "models_recorded": sorted({m for r in included for m in r["models_recorded"]}),
        "live_native_api": live,
        "limitations": [
            "Historical child participants include completed/retired agents; live API is a separate timestamped observation.",
            "Task-complete events are completed turns, not proof of successful outputs or scientific acceptance.",
            "Model metadata is not an independently billed provider-call ledger; cost and token totals are unknown here.",
            "Nested Claude identities and native Codex identities are distinct; native children must not be added again to the earlier native contributor floor.",
            "No global agent census, total simultaneous concurrency, or platform limit is inferred.",
            "Raw prompts, encrypted content, tool arguments, account identifiers and credentials are not published.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-project", type=Path, required=True)
    parser.add_argument("--codex-sessions", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    scope = json.loads(args.scope.read_text())
    start = scope["window_start_utc"]
    end = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    lower, upper = epoch(start), epoch(end)
    rows = [
        scan_claude(p, lower, upper)
        for p in sorted(args.claude_project.glob("*/subagents/agent-*.jsonl"))
    ]
    # Only dates intersecting the requested UTC window, not all historical sessions.
    day = dt.datetime.fromtimestamp(lower, dt.timezone.utc).date()
    last = dt.datetime.fromtimestamp(upper, dt.timezone.utc).date()
    while day <= last:
        for path in sorted(
            (args.codex_sessions / day.strftime("%Y/%m/%d")).glob("*.jsonl")
        ):
            rows.append(
                scan_codex(path, lower, upper, scope["frontier_root_thread_ids"])
            )
        day += dt.timedelta(days=1)
    result = summarize(rows, start, end, scope["native_api_observation"])
    result["scope_sha256"] = hashlib.sha256(args.scope.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
