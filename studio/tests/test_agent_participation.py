import hashlib
import json
from pathlib import Path

import pytest

from frontier_compute import agent_participation as ap

START = ap.epoch("2026-10-31T07:00:00Z")
END = ap.epoch("2026-11-01T05:30:00Z")
T = "2026-10-31T20:00:00Z"
SECRET = "PRIVATE-TEXT-must-not-be-published"


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def claude_rows(task="Review /data/worktrees/delphi-frontier/foundation " + SECRET):
    return [
        {"type": "user", "timestamp": T, "message": {"content": task}},
        {
            "type": "assistant",
            "timestamp": T,
            "agentId": "child1",
            "message": {
                "id": "m1",
                "model": "claude-example",
                "content": [{"type": "tool_use", "id": "tool1", "input": SECRET}],
            },
        },
    ]


def test_claude_scope_requires_initial_task_and_actual_activity(tmp_path):
    path = write(tmp_path / "parent/subagents/agent-child1.jsonl", claude_rows())
    result = ap.scan_claude(path, START, END)
    assert result["included"] and result["tool_invocation_ids"] == 1
    assert SECRET not in json.dumps(result)
    assert (
        result["captured_prefix_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    write(path, claude_rows("Unrelated earlier project with generic hackathon work"))
    assert (
        ap.scan_claude(path, START, END)["exclusion"]
        == "initial task lacks explicit Frontier marker"
    )
    write(path, claude_rows()[:1])
    assert not ap.scan_claude(path, START, END)["included"]


def test_old_task_does_not_become_frontier_work_from_later_mentions(tmp_path):
    rows = claude_rows("unrelated project")
    rows.append(
        {"type": "user", "timestamp": T, "message": {"content": "Delphi Frontier"}}
    )
    path = write(tmp_path / "parent/subagents/agent-child1.jsonl", rows)
    assert not ap.scan_claude(path, START, END)["included"]
    rows = claude_rows()
    rows[0]["timestamp"] = "2026-10-30T00:00:00Z"
    write(path, rows)
    assert (
        ap.scan_claude(path, START, END)["exclusion"] == "initial task outside window"
    )


def test_message_and_tool_ids_are_deduplicated(tmp_path):
    rows = claude_rows()
    rows.append(rows[-1])
    path = write(tmp_path / "parent/subagents/agent-child1.jsonl", rows)
    result = ap.scan_claude(path, START, END)
    assert result["assistant_message_ids"] == result["tool_invocation_ids"] == 1


def test_partial_tail_is_not_parsed_and_malformed_complete_line_fails_closed(tmp_path):
    path = write(tmp_path / "parent/subagents/agent-child1.jsonl", claude_rows())
    data = path.read_bytes()
    path.write_bytes(data + b"{incomplete")
    result = ap.scan_claude(path, START, END)
    assert result["included"] and result["incomplete_tail_bytes"] == 11
    assert result["captured_prefix_sha256"] == hashlib.sha256(data).hexdigest()
    path.write_bytes(data + b"{malformed}\n")
    assert ap.scan_claude(path, START, END)["exclusion"] == "malformed transcript lines"


def test_line_size_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "MAX_LINE", 32)
    path = write(tmp_path / "large.jsonl", [{"x": "z" * 100}])
    with pytest.raises(ValueError, match="line exceeds"):
        list(ap.records(path, {}))


def codex_rows():
    return [
        {
            "type": "session_meta",
            "payload": {
                "timestamp": T,
                "id": "session-child",
                "model_provider": "openai",
                "source": {
                    "subagent": {
                        "thread_spawn": {
                            "parent_thread_id": "frontier-root",
                            "agent_path": "/root/a",
                        }
                    }
                },
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-10-31T19:00:00Z",
            "payload": {
                "type": "function_call",
                "call_id": "inherited",
                "arguments": SECRET,
            },
        },
        {
            "type": "turn_context",
            "timestamp": T,
            "payload": {"model": "recorded-model"},
        },
        {
            "type": "event_msg",
            "timestamp": T,
            "payload": {"type": "task_started", "turn_id": "t1"},
        },
        {
            "type": "response_item",
            "timestamp": T,
            "payload": {"type": "custom_tool_call", "call_id": "c1", "input": SECRET},
        },
        {
            "type": "event_msg",
            "timestamp": T,
            "payload": {"type": "task_complete", "turn_id": "t1"},
        },
    ]


def test_codex_parent_scope_creation_boundary_turn_units_and_privacy(tmp_path):
    path = write(tmp_path / "codex.jsonl", codex_rows())
    result = ap.scan_codex(path, START, END, ["frontier-root"])
    assert result["included"] and result["tool_invocation_ids"] == 1
    assert result["task_turns_started"] == result["task_turns_complete_events"] == 1
    assert result["successful_task_count"] is None and result["active_now"] is None
    assert SECRET not in json.dumps(result)
    assert not ap.scan_codex(path, START, END, ["unrelated-root"])["included"]


def test_codex_fork_ordinal_boundary_is_respected(tmp_path):
    rows = codex_rows()
    rows[0]["payload"]["subagent_history_start_ordinal"] = 5
    result = ap.scan_codex(
        write(tmp_path / "codex.jsonl", rows), START, END, ["frontier-root"]
    )
    assert not result["included"] and result["tool_invocation_ids"] == 0


def test_embedded_parent_session_metadata_cannot_replace_child_identity(tmp_path):
    rows = codex_rows()
    rows.insert(
        1,
        {
            "type": "session_meta",
            "payload": {
                "id": "frontier-root",
                "timestamp": "2026-10-31T10:00:00Z",
                "source": "cli",
            },
        },
    )
    result = ap.scan_codex(
        write(tmp_path / "codex.jsonl", rows), START, END, ["frontier-root"]
    )
    assert result["included"] and result["identity"] == "/root/a"
    assert result["tool_invocation_ids"] == 1


def test_duplicate_child_identity_requires_explicit_resume_dedup(tmp_path):
    path = write(tmp_path / "parent/subagents/agent-child1.jsonl", claude_rows())
    row = ap.scan_claude(path, START, END)
    with pytest.raises(ValueError, match="duplicate identity"):
        ap.summarize([row, row], "start", "end", {})


def test_committed_summary_matches_actual_identities_and_keeps_units_separate():
    root = Path(__file__).resolve().parents[1]
    receipt = root / "results/resources/agent-participation.json"
    if not receipt.exists():
        pytest.skip("receipt not yet generated")
    result = json.loads(receipt.read_text())
    rows = result["participants"]
    assert len(rows) == len({(r["kind"], r["identity"]) for r in rows})
    assert result["counts"]["distinct_scoped_child_participants"] == len(rows)
    assert all(r["successful_task_count"] is None for r in rows)
    assert all(r["active_now"] is None for r in rows)
    assert result["counts"]["excluded_transcripts"] == len(result["exclusions"])
    assert "agents_total" not in result["counts"]
