"""scripts/submit_drafts.py: credential-file submission of drafts as PROPOSED records, idempotent and stop-on-surprise.
Run bounded: systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash scripts/test_postgres.sh tests/test_submit_drafts.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import TOKENS
from frontier.models import ref

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import import_register as ir  # noqa: E402
import submit_drafts as sd  # noqa: E402


def problems(n=4, statement="Does X cause Y?"):
    return [{"slug": f"q-{i}", "statement": f"{statement} ({i})", "why_it_matters": "Because Z.", "tags": [],
             "attestations": [{"pmcid": f"PMC{i + 1}", "locator": "Results", "quote": f"quote {i}", "stance": "open", "kind": "research"}]} for i in range(n)]


def write_drafts(tmp_path, n=4, statement="Does X cause Y?"):
    path = tmp_path / "drafts.jsonl"
    path.write_text("".join(json.dumps(ir.to_draft(p), sort_keys=True) + "\n" for p in problems(n, statement)))
    return path


def cred(tmp_path, token, mode=0o600):
    f = tmp_path / "cred.token"
    f.write_text(token + "\n")
    f.chmod(mode)
    return f


def cli(store, tmp_path, drafts, credential, *extra, actor="alice", operator="operator-a"):
    env = {**os.environ, "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(REPO), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    receipt = tmp_path / "receipt.json"
    done = subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "submit_drafts.py"), str(drafts), "--namespace", store.namespace,
                           "--schema", store.schema, "--credential-file", str(credential), "--expect-actor", actor, "--expect-operator", operator,
                           "--receipt", str(receipt), "--register-sha256", "ab" * 32, *extra], env=env, capture_output=True, text=True, timeout=120)
    return done, (json.loads(receipt.read_text()) if receipt.exists() else None)


def counts(store):
    with store.connection() as c:
        return {t: c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in ("record_versions", "write_receipts", "idempotency", "heads")}


def test_dry_run_writes_nothing_and_reports_the_plan(store, tmp_path):
    drafts, c = write_drafts(tmp_path), cred(tmp_path, TOKENS["alice"])
    before = counts(store)
    done, receipt = cli(store, tmp_path, drafts, c)
    assert done.returncode == 0, done.stdout + done.stderr
    assert counts(store) == before
    assert receipt["mode"] == "dry_run" and receipt["planned"] == {"create": 4, "revise": 0, "unchanged": 0}
    assert receipt["independent_reviewer"] is False and receipt["records_are"] == "proposed, not accepted"


def test_execute_creates_proposed_records_with_read_back_and_never_prints_the_credential(store, tmp_path):
    drafts, c = write_drafts(tmp_path), cred(tmp_path, TOKENS["alice"])
    done, receipt = cli(store, tmp_path, drafts, c, "--execute")
    assert done.returncode == 0, done.stdout + done.stderr
    assert TOKENS["alice"] not in done.stdout + done.stderr + json.dumps(receipt) + (tmp_path / "receipt.json").read_text()
    assert [r["action"] for r in receipt["records"]] == ["create"] * 4 and all(r["local_status"] == "proposed" for r in receipt["records"])
    assert receipt["read_back"] == {"checked": 4, "not_head_or_not_proposed": []}
    for r in receipt["records"]:
        got = store.get({"namespace": store.namespace, "kind": "Problem", "id": r["id"], "version": r["version"]})
        assert got["is_head"] and got["local_review"]["status"] == "proposed" and got["record"]["issuer"] == "alice"
        sub = got["record"]["payload"]["original"]["submission"]
        assert sub["role"].startswith("proposer; not an independent reviewer") and sub["register_sha256"] == "ab" * 32 and len(sub["draft_content_sha256"]) == 64
        assert got["record"]["payload"]["completeness"] == "recorded" and got["record"]["payload"]["problem_kind"] == "curated_question"


def test_rerun_makes_no_new_version_and_a_changed_source_revises_the_exact_head(store, tmp_path):
    drafts, c = write_drafts(tmp_path), cred(tmp_path, TOKENS["alice"])
    _, first = cli(store, tmp_path, drafts, c, "--execute")
    before = counts(store)
    done, again = cli(store, tmp_path, drafts, c, "--execute")
    assert done.returncode == 0 and again["planned"] == {"create": 0, "revise": 0, "unchanged": 4}
    assert counts(store) == before, "an unchanged re-run writes nothing: no phony new version"
    assert [r["version"] for r in again["records"]] == [r["version"] for r in first["records"]]
    changed = write_drafts(tmp_path, statement="Does X cause Y, revised?")
    done, rev = cli(store, tmp_path, changed, c, "--execute")
    assert done.returncode == 0 and rev["planned"] == {"create": 0, "revise": 4, "unchanged": 0}
    for old, new in zip(first["records"], rev["records"]):
        assert new["predecessor"] == old["version"] and new["version"] != old["version"]
        assert store.get({"namespace": store.namespace, "kind": "Problem", "id": new["id"], "version": old["version"]})["is_head"] is False
    mid = counts(store)
    done, same = cli(store, tmp_path, changed, c, "--execute")
    assert same["planned"]["unchanged"] == 4 and counts(store) == mid


def test_stop_on_unexpected_author_state_writes_nothing_at_all(store, tmp_path):
    from conftest import claim  # noqa: F401
    other = ir.to_draft(problems(1)[0]) | {"issuer": "bob", "namespace": store.namespace}
    other["source_uri"] = "urn:frontier:other-source"
    store.submit(TOKENS["bob"], "someone-else", other)
    drafts, c = write_drafts(tmp_path), cred(tmp_path, TOKENS["alice"])
    before = counts(store)
    done, receipt = cli(store, tmp_path, drafts, c, "--execute")
    assert done.returncode == sd.EXIT_STOP and "not this actor and source" in done.stdout
    assert counts(store) == before and receipt is None, "q-0 collides with another author's record: not even q-1..q-3 were written"


def test_stop_when_the_head_has_been_reviewed(store, tmp_path):
    from conftest import assessment
    drafts, c = write_drafts(tmp_path), cred(tmp_path, TOKENS["alice"])
    _, first = cli(store, tmp_path, drafts, c, "--execute")
    target = {"namespace": store.namespace, "kind": "Problem", "id": first["records"][0]["id"], "version": first["records"][0]["version"]}
    store.review(TOKENS["bob"], "rev", assessment(target, decision="disputed"))
    changed = write_drafts(tmp_path, statement="Does X cause Y, revised?")
    done, _ = cli(store, tmp_path, changed, c, "--execute")
    assert done.returncode == sd.EXIT_STOP and "not proposed" in done.stdout


def test_wrong_principal_unsafe_credential_file_and_quota_all_stop_before_any_write(store, tmp_path):
    drafts = write_drafts(tmp_path)
    before = counts(store)
    done, _ = cli(store, tmp_path, drafts, cred(tmp_path, TOKENS["alice"]), "--execute", actor="bob")
    assert done.returncode == sd.EXIT_STOP and "expected 'bob'" in done.stdout
    done, _ = cli(store, tmp_path, drafts, cred(tmp_path, TOKENS["alice"], 0o644), "--execute")
    assert done.returncode == sd.EXIT_STOP and "readable by group or others" in done.stdout and TOKENS["alice"] not in done.stdout + done.stderr
    store.provision("test-only-small-quota-token", "erin", "operator-e", ["contributor"], [store.namespace], 3)
    done, _ = cli(store, tmp_path, drafts, cred(tmp_path, "test-only-small-quota-token"), "--execute", actor="erin", operator="operator-e")
    assert done.returncode == sd.EXIT_STOP and "daily quota" in done.stdout
    done, _ = cli(store, tmp_path, drafts, cred(tmp_path, "test-only-not-a-provisioned-token"), "--execute")
    assert done.returncode == 2 and "test-only-not-a-provisioned-token" not in done.stdout + done.stderr
    assert counts(store) == before


def test_idempotency_key_replays_the_same_request_and_is_derived_from_content(store, tmp_path):
    drafts, c = write_drafts(tmp_path, 2), cred(tmp_path, TOKENS["alice"])
    _, r1 = cli(store, tmp_path, drafts, c, "--execute")
    keys = [x["idempotency_key"] for x in r1["records"]]
    assert all(k.startswith("reg-import:") and len(k) <= 128 for k in keys) and len(set(keys)) == 2
    d = json.loads(drafts.read_text().splitlines()[0]) | {"issuer": "alice", "namespace": store.namespace, "predecessor": None}
    replay = store.submit(TOKENS["alice"], keys[0], {**d, "payload": store.get({"namespace": store.namespace, "kind": "Problem", "id": d["id"], "version": r1["records"][0]["version"]})["record"]["payload"]})
    assert replay["record"]["version"] == r1["records"][0]["version"], "same key and same request returns the stored response"


@pytest.mark.skipif(not Path("/home/ubuntu/git/morphoswarm/data/problems/register.yaml").exists(), reason="register not on this host")
def test_assessments_mark_exactly_the_15_sample_quotes_and_leave_the_rest_unreviewed(tmp_path):
    out = tmp_path / "d.jsonl"
    done = subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "import_register.py"), "/home/ubuntu/git/morphoswarm/data/problems/register.yaml",
                           "--out", str(out), "--assessments", str(REPO / "findings")], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["quote_review"] == {"sample_checked": 15, "unreviewed": 450}
    sample = json.loads((REPO / "findings" / "attestation-sample-15.json").read_text())["items"]
    want = {(i["slug"], i["index"]) for i in sample}
    got = set()
    for line in out.read_text().splitlines():
        d = json.loads(line)
        for x in d["payload"]["original"]["register_provenance"]["attestations"]:
            if x["quote_review"]["status"] == "sample_checked":
                got.add((d["id"], x["index"]))
                assert x["quote_review"]["facet_review"]["quote_supports_stance"] in ("yes", "partly", "no")
                assert "not independently reviewed" in x["quote_review"]["reviewer"].lower() and "Says nothing about any other quote" in x["quote_review"]["scope"]
            else:
                assert x["quote_review"]["status"] == "unreviewed"
    assert got == want
    plain = subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "import_register.py"), "/home/ubuntu/git/morphoswarm/data/problems/register.yaml"],
                           capture_output=True, text=True, timeout=300)
    assert json.loads(plain.stdout)["quote_review"] == {"sample_checked": 0, "unreviewed": 465}
