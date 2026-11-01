"""scripts/mcp_demo.py: the MCP contribution round trip as a software protocol test, against an isolated database.
Run bounded: systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash scripts/test_postgres.sh tests/test_mcp_demo.py
"""
import json
import os
import subprocess
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from conftest import TOKENS, claim
from frontier.models import ref

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import mcp_demo as md  # noqa: E402


def cred(tmp_path, token, mode=0o600):
    f = tmp_path / "cred.token"
    f.write_text(token + "\n")
    f.chmod(mode)
    return f


def demo(store, tmp_path, credential, *extra, actor="alice", operator="operator-a"):
    env = {**os.environ, "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(REPO), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    out = tmp_path / "out"
    done = subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "mcp_demo.py"), "--namespace", store.namespace, "--schema", store.schema,
                           "--credential-file", str(credential), "--expect-actor", actor, "--expect-operator", operator, "--out-dir", str(out),
                           "--allow-dirty-code", *extra], env=env, capture_output=True, text=True, timeout=240)
    return done, out


def counts(store):
    with store.connection() as c:
        return {t: c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in ("record_versions", "write_receipts", "idempotency", "events")}


def head(store, kind, rid):
    with store.connection() as c:
        r = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s", (store.namespace, kind, rid)).fetchone()
    return r["version"] if r else None


# ---- the check is a pure function ----------------------------------------------------------------------------------
def good_snapshot():
    tools = lambda names, ro: [{"name": n, "read_only": n in ro, "input_properties": ["query"]} for n in sorted(names)]  # noqa: E731
    return {"read_only": {"manifest_tools": sorted(md.READ_TOOLS), "tools": tools(md.READ_TOOLS, md.READ_TOOLS), "search_sample": {"n": 3, "public": 3},
                          "principal_is_null": True, "principal_is_set": False, "principal_has_secretish_key": False},
            "write_enabled": {"manifest_tools": sorted(md.READ_TOOLS | md.WRITE_TOOLS), "tools": tools(md.READ_TOOLS | md.WRITE_TOOLS, md.READ_TOOLS),
                              "search_sample": {"n": 1, "public": 1}, "principal_is_null": False, "principal_is_set": True, "principal_has_secretish_key": False}}


def test_check_passes_on_a_good_snapshot_and_each_invariant_can_fail():
    snap = good_snapshot()
    v = md.run_check(snap)
    assert [x["id"] for x in v] == ["I1", "I2", "I3", "I4", "I5", "I6"] and all(x["passed"] for x in v) and md.check_relation(v) == "supports"
    assert md.run_check(deepcopy(snap)) == v, "deterministic"
    def broken(mutate):
        s = deepcopy(snap); mutate(s)
        return {x["id"]: x["passed"] for x in md.run_check(s)}
    assert broken(lambda s: s["read_only"]["tools"].append({"name": "frontier_propose", "read_only": True, "input_properties": []}))["I1"] is False
    assert broken(lambda s: s["write_enabled"]["tools"][0].update(read_only=False))["I2"] is False
    assert broken(lambda s: s["write_enabled"]["tools"][0]["input_properties"].append("api_key"))["I3"] is False
    assert broken(lambda s: s["write_enabled"]["tools"].append({"name": "frontier_review", "read_only": False, "input_properties": []}))["I4"] is False
    assert broken(lambda s: s["read_only"]["search_sample"].update(public=2))["I5"] is False
    assert broken(lambda s: s["read_only"]["search_sample"].update(n=0, public=0))["I5"] is False, "an empty sample must not pass vacuously"
    assert broken(lambda s: s["read_only"].update(principal_is_null=False))["I6"] is False
    assert md.check_relation(md.run_check({**snap, "read_only": {**snap["read_only"], "search_sample": {"n": 3, "public": 1}}})) == "refutes"


# ---- the round trip ------------------------------------------------------------------------------------------------
def test_dry_run_writes_nothing(store, tmp_path):
    store.submit(TOKENS["alice"], "sample", claim(store, "a-public-record-for-the-search-sample"))  # I5 refuses to pass on an empty sample
    before = counts(store)
    done, out = demo(store, tmp_path, cred(tmp_path, TOKENS["alice"]))
    assert done.returncode == 0, done.stdout + done.stderr
    r = json.loads(done.stdout)
    assert r["outcome"] == "would_run" and r["written"] is False and r["invariants_passed"] == "6 of 6"
    assert counts(store) == before and not out.exists()


def test_full_round_trip_through_mcp_then_a_rerun_writes_nothing(store, tmp_path):
    scientific = store.submit(TOKENS["alice"], "sci", claim(store, "an-existing-scientific-claim"))["record"]
    c = cred(tmp_path, TOKENS["alice"])
    done, out = demo(store, tmp_path, c, "--execute")
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["outcome"] == "completed"
    receipt = json.loads((out / "2026-10-31-mcp-roundtrip-receipt.json").read_text())
    refs = receipt["records"]
    # records: proposed, never accepted; the Action ended 'submitted'
    for name in ("claim", "action", "evidence"):
        got = store.get(refs[name])
        assert got["is_head"] and got["local_review"]["status"] == "proposed"
    assert store.get(refs["action"])["action"]["state"] == "submitted"
    assert [s["step"] for s in receipt["steps"]] == ["propose_claim", "propose_action", "ready", "lease", "start", "propose_evidence", "complete"]
    assert [s.get("state") for s in receipt["steps"] if s["step"] in ("ready", "lease", "start", "complete")] == ["ready", "leased", "running", "submitted"]
    # evidence: produced_by the Action, same target, exact input/output/code digests that match the files and the script
    ev = store.get(refs["evidence"])["record"]["payload"]
    assert ev["produced_by"] == refs["action"] and ev["target"] == refs["claim"] and ev["relation"] == "supports"
    by_role = {a["role"]: a for a in ev["artifacts"]}
    assert by_role["input"]["sha256"] == sha256((out / "mcp-demo-input.json").read_bytes()).hexdigest()
    assert by_role["output"]["sha256"] == sha256((out / "mcp-demo-output.json").read_bytes()).hexdigest()
    assert by_role["code"]["sha256"] == sha256((REPO / "scripts" / "mcp_demo.py").read_bytes()).hexdigest()
    assert all(a["availability"] == "referenced" and a["uri"] == "urn:sha256:" + a["sha256"] for a in ev["artifacts"])
    action = store.get(refs["action"])["record"]["payload"]
    assert action["cache_key"]["code"] == by_role["code"]["sha256"] and action["proposal"]["intent"] == "analysis"
    # labelled as a software protocol test, not a biological finding
    claim_payload = store.get(refs["claim"])["record"]["payload"]
    assert "Software protocol test" in claim_payload["title"] and "not a biological finding" in claim_payload["title"]
    assert any("not a biological" in x.lower() for x in claim_payload["limitations"] + ev["limitations"])
    assert all(v["passed"] for v in receipt["invariants"])
    # read-back through MCP agrees, including the artifact index
    idx = receipt["read_back"]["artifact_index"]
    assert {x["role"] for x in idx} == {"input", "output", "code"} and all(x["produced_by"] == md.ACTION_ID and x["local_status"] == "proposed" and x["artifact_bytes_verified"] is False for x in idx)
    # events: the lifecycle, and no review/accept anywhere
    types = [e["envelope"]["payload"]["event_type"] for e in store.events(limit=50)["events"]]
    assert {"action_ready", "action_leased", "action_running", "action_submitted"} <= set(types) and not any("review" in t or "accept" in t for t in types)
    # neighbourhood has the produced_by edge
    edges = store.neighborhood(refs["evidence"])["edges"]
    assert any(e["relation"] == "produced_by" for e in edges)
    # nothing leaks: credential, lease id, database location
    blob = done.stdout + done.stderr + "".join(p.read_text() for p in out.iterdir())
    import re
    assert TOKENS["alice"] not in blob and store.dsn not in blob
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", blob), "a lease id (a uuid) must not be recorded"
    assert "held in memory only" in json.dumps(receipt["steps"])
    # the existing scientific record is untouched
    assert head(store, "Claim", "an-existing-scientific-claim") == scientific["version"]
    # a rerun only re-verifies
    before = counts(store)
    again, _ = demo(store, tmp_path, c, "--execute")
    assert again.returncode == 0 and json.loads(again.stdout)["outcome"] == "already_complete" and json.loads(again.stdout)["written"] is False
    assert counts(store) == before


def test_wrong_principal_and_unsafe_credential_file_stop_before_any_write(store, tmp_path):
    before = counts(store)
    done, out = demo(store, tmp_path, cred(tmp_path, TOKENS["alice"]), "--execute", actor="bob")
    assert done.returncode == md.EXIT_STOP and "expected 'bob'" in done.stdout
    done, _ = demo(store, tmp_path, cred(tmp_path, TOKENS["alice"], 0o644), "--execute")
    assert done.returncode == md.EXIT_STOP and "readable by group or others" in done.stdout and TOKENS["alice"] not in done.stdout + done.stderr
    store.provision("test-only-contributor-no-coord", "dora", "operator-d", ["contributor"], [store.namespace], 100)
    done, _ = demo(store, tmp_path, cred(tmp_path, "test-only-contributor-no-coord"), "--execute", actor="dora", operator="operator-d")
    assert done.returncode == md.EXIT_STOP and "coordinator" in done.stdout
    assert counts(store) == before and not out.exists()


def test_a_head_by_another_author_stops_the_run(store, tmp_path):
    other = claim(store, md.CLAIM_ID, issuer="bob")
    other["source_uri"] = md.SOURCE_URI
    store.submit(TOKENS["bob"], "squat", other)
    before = counts(store)
    done, _ = demo(store, tmp_path, cred(tmp_path, TOKENS["alice"]), "--execute")
    assert done.returncode == md.EXIT_STOP and "unexpected author" in done.stdout
    assert counts(store) == before
