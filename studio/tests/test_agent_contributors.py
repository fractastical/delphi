import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ac", ROOT / "scripts" / "agent_contributors.py")
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)

W = ac.ts("2026-10-31T00:00:00-07:00")
IN, OUT = W + 3600, W - 86400
SECRET_TEXT = "PRIVATE-SENTENCE-do-not-publish"


def msg(body, t=IN):
    return (body.encode(), t)


def run(files, sessions=("claude-05", "claude-13", "dx-submit", "dx-corpus", "claude-02")):
    tm = {"sessions": {s: {"live_harness_process": True, "pane_state": "idle"} for s in sessions}, "raw_session_names": len(sessions), "activity_poller_suspected": False, "max_sessions_active_within_180s": 0}
    git = {"git_identities": {"SciDEX Bot": 5}, "models_in_trailers": {"Claude Sonnet 5.5": 5}, "commits_in_window": 5}
    return ac.build(files, tm, git, ["work/a", "codex/b", "main"], {"own_jobs": 3}, W, W + 7200)


def test_id_spellings_are_one_harness_and_retired_suffix_is_a_rename():
    assert {ac.norm_harness(x) for x in ("claude13", "claude-13", "Claude 13")} == {"claude-13"}
    assert ac.norm_harness("dx-submit-retired-1") == "dx-submit"
    assert ac.norm_harness("dx-market-r1") == "dx-market-r1"  # a second-round session stays distinct
    out = run({"claude13-to-site.md": msg(f"# x\n{SECRET_TEXT}"), "claude-13-to-root.md": msg("# y")})
    assert list(out["supported_harnesses"]) == ["claude-13"] and len(out["supported_harnesses"]["claude-13"]["evidence"]) == 2


def test_out_of_window_evidence_is_skipped_not_counted():
    out = run({"claude05-to-site.md": msg("# a", OUT)})
    assert out["supported_harnesses"] == {} and out["counts"]["distinct_contributing_harness_ids_supported_minimum"] == 0


def test_mention_is_not_authorship_and_doc_names_are_not_ids():
    out = run({"site-to-root.md": msg("see claude-02 and CODEX-21-CLAIM-FREEZE-REVIEW.md and codex-24")})
    assert "claude-02" not in out["supported_harnesses"] and out["named_by_others_only"] == {"claude-02": 1}
    assert "codex-21" not in out["unresolved_mentions"] and out["unresolved_mentions"] == {"codex-24": 1}


def test_role_equal_to_session_is_supported_and_dx_alias_is_only_probable():
    out = run({"dx-submit-to-director.md": msg("# a"), "corpus-to-site.md": msg("# b"), "market-to-site.md": msg("# c")})
    assert "dx-submit" in out["supported_harnesses"] and "dx-corpus" not in out["supported_harnesses"]
    assert "dx-corpus" in out["probable_aliases"] and "market" in out["roles"]
    assert out["counts"]["harness_ids_probable_not_counted"] == 1


def test_title_sender_counts_when_filename_has_no_id():  # superseded by the table test below, kept as the simple case
    out = run({"handoff.md": msg("# claude-05 → codex-03 handoff\nbody")})
    assert out["supported_harnesses"]["claude-05"]["evidence"][0]["basis"] == "title sender"


def test_published_output_has_hashes_but_no_message_text():
    data = f"# claude13 → x\n{SECRET_TEXT}"
    out = run({"claude13-to-x.md": msg(data)})
    s = json.dumps(out)
    assert SECRET_TEXT not in s and ac.sha(data.encode()) in s


def test_active_requires_a_live_harness_descendant_and_burst_activity_is_flagged():
    panes = [{"session": "s1", "pid": 1, "activity": 100.0, "created": 0.0}, {"session": "s2", "pid": 9, "activity": 100.0, "created": 0.0}]
    ps = [(1, 0, "bash"), (2, 1, "node"), (3, 2, "claude"), (9, 0, "bash")]
    tm = ac.scan_tmux(panes, ps)
    assert tm["sessions"]["s1"]["live_harness_process"] and not tm["sessions"]["s2"]["live_harness_process"]
    burst = [{"session": f"c{i}", "pid": 100 + i, "activity": 1000.0 + 7 * i, "created": 0.0} for i in range(12)]
    assert ac.scan_tmux(burst, [])["activity_poller_suspected"] is True
    assert ac.scan_tmux(panes, ps)["activity_poller_suspected"] is False


def test_git_window_counts_identities_and_models_separately():
    g = ac.scan_git([("SciDEX Bot", str(IN), "Claude Opus 5 <n@a>;Claude Sonnet 5.5 <n@a>", ""), ("nca", str(IN), "", ""), ("old", str(OUT), "Claude X <n@a>", "")], W)
    assert g["commits_in_window"] == 2 and set(g["git_identities"]) == {"SciDEX Bot", "nca"} and set(g["models_in_trailers"]) == {"Claude Opus 5", "Claude Sonnet 5.5"}


def test_committed_ledger_is_consistent_and_hashes_match_available_files():
    o = json.loads((ROOT / "results/resources/agent-contributors.json").read_text())
    c = o["counts"]
    assert c["distinct_contributing_harness_ids_supported_minimum"] == len(o["supported_harnesses"]) > 0
    assert c["harness_ids_probable_not_counted"] == len(o["probable_aliases"]) and c["worker_branches"] == len(o["worker_branch_names"])
    assert not set(o["supported_harnesses"]) & set(o["probable_aliases"]) and "agents_total" not in c
    assert c["tmux_session_names_raw"] >= c["tmux_sessions_after_rename_dedup"] == len(o["tmux"])
    md = Path("/data/artifacts/delphi-evolve-rethink/messages")
    if not md.is_dir():
        pytest.skip("private handoff directory not on this host")
    checked = 0
    for v in o["supported_harnesses"].values():
        for e in v["evidence"]:
            f = md / e["file"]
            if f.exists():
                assert ac.sha(f.read_bytes()) == e["sha256"] or f.stat().st_mtime > ac.ts(o["window"]["observed_utc"].replace("Z", "+00:00"))
                checked += 1
    assert checked > 0


@pytest.mark.parametrize("line,want", [
    ("# fish-glider (claude-05): reviewer claude-13's thin-wall finding", ("claude-05", "fish-glider")),
    ("# biological-fish-v3 (claude05) → cfd3d (claude-04): x", ("claude-05", "biological-fish-v3")),
    ("# claude-07: r3/r4 evaluated", ("claude-07", None)),
    ("# print v2 → codex-03 (from claude05)", ("claude-05", None)),
    ("# BioModels to codex-03: Evidence v2", None),                      # recipient only
    ("# critic -> claude02 (website)", None),                             # recipient only
    ("# Experimental design MCP contract for claude-02", None),          # no sender part
    ("> **Wording correction (claude-07):** every flown", ("claude-07", None)),  # id kept, junk role label dropped
])
def test_title_sender_takes_the_sender_side_only(line, want):
    assert ac.title_sender(line) == want


def test_role_label_from_one_title_attributes_a_role_named_file_and_conflicts_are_not_used():
    out = run({"print-to-site.md": msg("# print → site\nno id here"), "x.md": msg("# print (claude-05) → codex-03: y"),
               "a-to-b.md": msg("# dup (claude-02) → z"), "dup-to-c.md": msg("# dup (claude-05) → z")},
              sessions=("claude-05", "claude-02"))
    ev = {e["file"]: e["basis"] for e in out["supported_harnesses"]["claude-05"]["evidence"]}
    assert ev["print-to-site.md"] == "role self-labelled in another handoff title"
    assert "dup" in out["role_label_conflicts"] and "dup" not in out["role_to_harness_self_labelled"]


def test_pane_state_is_a_class_not_text_and_idle_is_not_activity():
    assert ac.classify_pane("x\n❯ \n") == "idle" and ac.classify_pane("Please run /login") == "auth_blocked"
    assert ac.classify_pane("working (esc to interrupt)\n❯ ") == "working" and ac.classify_pane("Stop hook error: API Error") == "error_visible"
    assert ac.classify_pane("nothing recognisable") == "unknown"
    tm = ac.scan_tmux([{"session": "s", "pid": 1, "activity": 0.0, "created": 0.0}], [(2, 1, "claude")], {"s": "Please run /login"})
    assert tm["sessions"]["s"]["pane_state"] == "auth_blocked" and tm["sessions"]["s"]["live_harness_process"]
    out = run({})
    assert out["contribution_activity"].startswith("unknown") and "live_harness_processes_now" in out["counts"] and "tmux_sessions_with_live_harness_process_now" not in out["counts"]


def test_reviewed_mapping_counts_only_when_the_named_artifact_resolves_in_window(tmp_path):
    import subprocess
    r = tmp_path
    subprocess.run(["git", "-C", str(r), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(r), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    now = ac.dt.datetime.now().timestamp()
    entries = [{"harness": "claude-14", "role": "r", "evidence": [{"kind": "commit", "ref": "HEAD"}]},
               {"harness": "claude-02", "role": "r", "evidence": [{"kind": "commit", "ref": "deadbeef"}]},
               {"harness": "claude-06", "role": "r", "evidence": [{"kind": "handoff", "ref": "h.md"}]},
               {"harness": "claude-07", "role": "r", "evidence": [{"kind": "handoff", "ref": "h.md"}]}]
    files = {"h.md": (b"# claude-06: x", now)}
    got = {m["harness"]: m["verified"] for m in ac.verify_mapping(entries, str(r), now - 60, files)}
    assert got == {"claude-14": True, "claude-02": False, "claude-06": True, "claude-07": False}  # unresolved ref; title names another harness
    assert ac.verify_mapping(entries[:1], str(r), now + 3600, files)[0]["verified"] is False  # commit before window
    ver = ac.verify_mapping(entries, str(r), now - 60, files)
    out = ac.build({}, {"sessions": {h: {"live_harness_process": True, "pane_state": "idle"} for h in ("claude-14", "claude-02")}, "raw_session_names": 2, "activity_poller_suspected": False, "max_sessions_active_within_180s": 0},
                   {"git_identities": {}, "models_in_trailers": {}, "commits_in_window": 0}, [], {"own_jobs": 0}, now - 60, now, ver)
    assert list(out["supported_harnesses"]) == ["claude-14"]


def test_committed_mapping_entries_are_all_verified_in_the_ledger():
    o = json.loads((ROOT / "results/resources/agent-contributors.json").read_text())
    assert o["reviewed_mapping"] and all(m["verified"] for m in o["reviewed_mapping"])
    assert set(m["harness"] for m in o["reviewed_mapping"]) <= set(o["supported_harnesses"])
    assert not (set(o["role_to_harness_self_labelled"]) & set(o["role_label_conflicts"]))


def test_mapping_requires_nonempty_supported_evidence():
    entries = [{"harness": "claude-02", "role": "r", "evidence": []},
               {"harness": "claude-03", "role": "r", "evidence": [{"kind": "unknown", "ref": "x"}]}]
    assert not any(e["verified"] for e in ac.verify_mapping(entries, str(ROOT), W, {}))


def test_native_identity_class_is_separate_verified_and_never_an_alias(tmp_path):
    import subprocess
    r = tmp_path
    subprocess.run(["git", "-C", str(r), "init", "-q"], check=True)
    (r / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(r), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(r), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"], check=True)
    now = ac.dt.datetime.now().timestamp()
    nat = ac.verify_mapping([{"identity": "/root/a", "role": "r", "evidence": [{"kind": "commit", "ref": "HEAD"}]},
                             {"identity": "/root/b", "role": "r", "evidence": [{"kind": "commit", "ref": "deadbeef"}]}], str(r), now - 60, {})
    assert [n["verified"] for n in nat] == [True, False] and nat[0]["checks"][0]["sample_paths"] == ["f.txt"]
    tm = {"sessions": {"claude-05": {"live_harness_process": True, "pane_state": "idle"}}, "raw_session_names": 1, "activity_poller_suspected": False, "max_sessions_active_within_180s": 0}
    g = {"git_identities": {}, "models_in_trailers": {}, "commits_in_window": 0}
    out = ac.build({"claude05-to-x.md": msg("# a")}, tm, g, [], {"own_jobs": 0}, W, W + 7200, None, nat)
    assert out["counts"]["native_contributors_supported_minimum"] == 1 and out["counts"]["distinct_contributing_harness_ids_supported_minimum"] == 1
    assert out["native_contributors"]["combined_with_harness_floor_if_classes_are_disjoint"] == 2 and out["native_agents"]["count"] == 1
    clash = [{"identity": "codex-03", "role": "r", "verified": True, "checks": []}]
    with pytest.raises(AssertionError):
        ac.build({}, tm, g, [], {"own_jobs": 0}, W, W + 7200, None, clash)


def test_committed_native_class_is_three_verified_and_disjoint_from_harnesses():
    o = json.loads((ROOT / "results/resources/agent-contributors.json").read_text())
    n = o["native_contributors"]
    assert n["supported_minimum"] == len(n["identities"]) == 3 and all(e["verified"] and e["identity"].startswith("/root/") for e in n["entries"])
    assert not set(n["identities"]) & (set(o["supported_harnesses"]) | set(o["tmux"]))
    assert n["combined_with_harness_floor_if_classes_are_disjoint"] == len(o["supported_harnesses"]) + 3
    assert any(c["files_changed"] > 0 for e in n["entries"] for c in e["checks"])


def test_transcript_participants_replace_native_floor_without_double_counting():
    out = run({'claude05-to-site.md': msg('# x')})
    out['native_contributors']['identities'] = ['/root/a']
    receipt = {
        'participants': [
            {'kind': 'codex_native_child', 'identity': '/root/a'},
            {'kind': 'codex_native_child', 'identity': '/root/retired'},
            {'kind': 'claude_nested_child', 'identity': 'nested-child'}],
        'window': {'start_utc': 'start', 'observed_utc': 'end'},
        'live_native_api': {'running_children': 1}, 'counts': {}}
    ac.attach_participation(out, receipt, 'a' * 64)
    assert out['participation']['recorded_participant_floor'] == 4
    assert out['participation']['recorded_native_children'] == 2
    assert out['participation']['live_native_api']['running_children'] == 1
    receipt['participants'] = receipt['participants'][1:]
    with pytest.raises(ValueError, match='misses previously supported'):
        ac.attach_participation(out, receipt, 'a' * 64)
