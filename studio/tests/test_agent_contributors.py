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
    tm = {"sessions": {s: {"active_verified": True} for s in sessions}, "raw_session_names": len(sessions), "activity_poller_suspected": False, "max_sessions_active_within_180s": 0}
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


def test_title_sender_counts_when_filename_has_no_id():
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
    assert tm["sessions"]["s1"]["active_verified"] and not tm["sessions"]["s2"]["active_verified"]
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
                assert ac.sha(f.read_bytes()) == e["sha256"] or f.stat().st_mtime > ac.ts(o["window"]["observed_utc"].replace("Z", "+00:00")); checked += 1
    assert checked > 0
