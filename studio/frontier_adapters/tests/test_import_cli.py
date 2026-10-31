"""Import CLI tests against a SCRATCH PostgreSQL. Run through the repo's own harness (own cluster, private socket):

  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
    bash scripts/test_postgres.sh frontier_adapters/tests/test_import_cli.py

Without FRONTIER_TEST_DSN these are SKIPPED with that reason; they are never reported as passed.
Nothing here touches any live store.
"""
import contextlib
import copy
import io
import json
import os
import stat
import tempfile
import unittest
from uuid import uuid4

from frontier import models
from frontier_adapters import delphi_claim as dc, import_cli as ic

DSN = os.environ.get("FRONTIER_TEST_DSN")
HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples")
CHAIN = os.path.join(EX, "nca_chain", "records.json")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
TOKEN = "test-only-coordinator-token-" + uuid4().hex
TOKEN_C = "test-only-contributor-token-" + uuid4().hex


def draft_files(tmp, ids=("darwin1859-ch02-04", "thompson1917-ch03-05", "wolfram2002-ch02-08", "fisher-ftns", "turing-ddi")):
    path = os.path.join(tmp, "drafts.jsonl")
    with open(path, "w") as fh:
        for cid in ids:
            with open(os.path.join(EX, "delphi_snapshots", cid + ".json")) as sf:
                d = json.load(sf)
            fh.write(json.dumps(dc.to_claim_draft(d["snapshot"], verification=d["verification"]), sort_keys=True) + "\n")
    return path


def token_file(tmp, tok=TOKEN, mode=0o600):
    p = os.path.join(tmp, "t.token")
    with open(p, "w") as fh:
        fh.write(tok + "\n")
    os.chmod(p, mode)
    return p


class BuildOffline(unittest.TestCase):
    def test_a_connector_mapping_wrapper_with_a_records_list_is_accepted_and_junk_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            recs = ic.records_from_file(CHAIN)
            wrapped = os.path.join(tmp, "w.json")
            with open(wrapped, "w") as fh:
                json.dump({"records": recs, "status": "proposed"}, fh)
            self.assertEqual([r["version"] for r in ic.records_from_file(wrapped)], [r["version"] for r in recs])
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w") as fh:
                json.dump({"nope": 1}, fh)
            with self.assertRaises(ic.ImportRefused):
                ic.records_from_file(bad)

    def test_site_ids_join_claim_action_evidence_by_exact_version_and_carry_no_path(self):
        from frontier_adapters.artifacts import find_abs_paths
        recs = ic.records_from_file(CHAIN)
        with open(os.path.join(EX, "nca_chain", "chain.json")) as fh:
            chain = json.load(fh)
        ids = ic.site_ids(recs, chain)
        self.assertEqual(len(ids["chains"]), 2)
        by_v = {r["version"]: r for r in recs}
        for c in ids["chains"]:
            self.assertEqual(by_v[c["claim"]["version"]]["id"], c["claim"]["id"])
            self.assertEqual(c["action_inputs"][0]["version"], c["claim"]["version"])
            self.assertEqual(len(c["artifacts"]), 9); self.assertTrue(all(x["passed"] for x in c["link_checks"]))
        self.assertEqual(find_abs_paths(ids), [])
        self.assertIn("imported_unreviewed", ids["status"])

    def test_receipt_is_hashed_credential_free_and_states_that_import_is_not_execution(self):
        recs = ic.records_from_file(CHAIN)
        b = ic.make_bundles(recs, "node-a")
        with tempfile.TemporaryDirectory() as tmp:
            plan = ic.write_plan(b, tmp, source={})
        ver = {"claims": {"verified_ok": 6, "problems": [], "status_counts": {"imported_unreviewed": 6}, "counts_now": {"heads": {}, "forks": 0}}}
        rep = ic.make_receipt(plans={"chain": plan}, import_receipts=[[{"bundle_sha256": b[0]["bundle_sha256"], "idempotency_key": ic.key_for(b[0]), "records": 6,
                                                                         "inserted": 6, "forks": []}]],
                              verifies=ver, counts_before={}, counts_before_note="n/a", code={}, principal={}, store={}, excluded={}, cross_namespace={}, notes=[])
        self.assertEqual(rep["inserted_total"], 6); self.assertEqual(rep["forks_recorded"], 0)
        self.assertIn("does not show any action executed locally", rep["action_semantics"])
        self.assertEqual(len(rep["receipt_sha256"]), 64)
        again = ic.make_receipt(plans={"chain": plan}, import_receipts=[[{"bundle_sha256": b[0]["bundle_sha256"], "idempotency_key": ic.key_for(b[0]), "records": 6,
                                                                           "inserted": 6, "forks": []}]],
                                verifies=ver, counts_before={}, counts_before_note="n/a", code={}, principal={}, store={}, excluded={}, cross_namespace={}, notes=[])
        self.assertNotEqual(rep["generated_at"], None); rep2 = {k: v for k, v in again.items() if k not in ("generated_at", "receipt_sha256")}
        self.assertEqual({k: v for k, v in rep.items() if k not in ("generated_at", "receipt_sha256")}, rep2)

    def test_build_is_deterministic_and_bounded_and_excludes_requested_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            dr = draft_files(tmp)
            plans = []
            for n in (1, 2):
                recs = ic.records_from_file(CHAIN) + ic.records_from_drafts([dr], exclude_ids={"turing-ddi"})
                b = ic.make_bundles(recs, "node-a", max_records=4)
                plans.append(ic.write_plan(b, os.path.join(tmp, f"o{n}"), source={}))
            self.assertEqual(plans[0]["plan_sha256"], plans[1]["plan_sha256"])
            self.assertTrue(all(f["records"] <= 4 for f in plans[0]["bundles"]))
            ids = [r["id"] for f in plans[0]["bundles"] for r in f["refs"] if r["kind"] == "Claim"]
            self.assertEqual(ids.count("turing-ddi"), 1)                # only the chain's exact version; the draft was excluded
            self.assertEqual(plans[0]["total_records"], 6 + 4)

    def test_two_versions_of_one_head_are_refused_not_silently_forked(self):
        recs = ic.records_from_file(CHAIN)
        other = copy.deepcopy(next(r for r in recs if r["kind"] == "Claim"))
        other["payload"]["title"] += " (changed)"
        other["version"] = "0" * 64
        with self.assertRaises(ic.ImportRefused):
            ic.make_bundles(recs + [other], "node-a")

    def test_bundle_size_and_count_limits(self):
        with self.assertRaises(ic.ImportRefused):
            ic.make_bundles(ic.records_from_file(CHAIN), "node-a", max_records=101)

    def test_credential_file_rules_and_no_leak_in_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = token_file(tmp)
            self.assertEqual(ic.read_token(ok), TOKEN)
            lax = token_file(tmp, mode=0o644)
            with self.assertRaises(ic.ImportRefused) as cm:
                ic.read_token(lax)
            self.assertNotIn(TOKEN, str(cm.exception))
        inside = os.path.join(REPO, ".tmp-credential-test")
        os.makedirs(inside, exist_ok=True)
        try:
            p = token_file(inside)
            with self.assertRaises(ic.ImportRefused) as cm:               # a credential inside a git work tree is refused
                ic.read_token(p)
            self.assertIn("git work tree", str(cm.exception)); self.assertNotIn(TOKEN, str(cm.exception))
        finally:
            for f in os.listdir(inside):
                os.remove(os.path.join(inside, f))
            os.rmdir(inside)


@unittest.skipUnless(DSN, "FRONTIER_TEST_DSN not set: scratch-PostgreSQL import tests NOT run (use scripts/test_postgres.sh)")
class ImportScratchStore(unittest.TestCase):
    def setUp(self):
        from frontier.store import Store
        self.store = Store(DSN, "delphi-frontier", "test_" + uuid4().hex)
        self.store.initialize()
        self.store.provision(TOKEN, "corpus-importer", "local-fleet", ["contributor", "coordinator"], ["delphi-frontier"], 1000)
        self.store.provision(TOKEN_C, "just-contributor", "other-operator", ["contributor"], ["delphi-frontier"], 1000)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def bundles(self, with_drafts=True, max_records=100):
        recs = ic.records_from_file(CHAIN)
        if with_drafts:
            recs += ic.records_from_drafts([draft_files(self.tmp.name)], exclude_ids={"turing-ddi"})
        return ic.make_bundles(recs, "node-a", max_records=max_records)

    def test_chain_imports_exactly_unreviewed_with_actions_proposed_and_heads_set(self):
        b = ic.make_bundles(ic.records_from_file(CHAIN), "node-a")
        self.assertEqual(len(b), 1)
        before = ic.counts(self.store)
        res = ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=None)
        self.assertEqual(res[0]["inserted"], 6); self.assertEqual(res[0]["forks"], [])
        self.assertIs(res[0]["imported_reviews_are_local_authority"], False)
        rep = ic.verify(self.store, b)
        self.assertEqual((rep["verified_ok"], rep["problems"]), (6, []))
        self.assertEqual(rep["status_counts"], {"imported_unreviewed": 6})
        self.assertEqual(rep["counts_now"]["heads"]["node-a/Claim"], 2); self.assertEqual(rep["counts_now"]["heads"]["node-a/Action"], 2)
        self.assertEqual(rep["counts_now"]["forks"], 0)
        with self.store.connection() as c:                                      # an import must not make an Action look executed
            self.assertEqual({r["state"] for r in c.execute("SELECT state FROM action_state").fetchall()}, {"proposed"})
        self.assertEqual(rep["counts_now"]["write_receipts_24h"], before["write_receipts_24h"] + 1)

    def test_every_imported_ref_reads_back_publicly_without_a_credential(self):
        b = self.bundles()
        ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=None)
        for bundle in b:
            for r in bundle["records"]:
                got = self.store.get(ic.ref_of(r), None)                       # no token: public read
                self.assertEqual(got["record"]["version"], r["version"])
                self.assertEqual(got["local_review"]["status"], "imported_unreviewed")

    def test_rerun_is_idempotent_and_writes_nothing(self):
        b = self.bundles()
        ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=None)
        after_first = ic.counts(self.store)
        res = ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=None)
        self.assertEqual(ic.counts(self.store), after_first)                  # same key + same bundle: stored response, no new write
        self.assertTrue(all(r["forks"] == [] for r in res))

    def test_a_changed_bundle_cannot_reuse_a_key(self):
        from frontier.store import Conflict
        b = self.bundles(with_drafts=False)[0]
        ic.run_import(self.store, TOKEN, [b], execute=True, receipt_path=None)
        b2 = ic.make_bundles(ic.records_from_file(CHAIN)[:3], "node-a")[0]
        with self.assertRaises(Conflict):
            self.store.import_bundle(TOKEN, ic.key_for(b), b2)                # MUST-FAIL control: same key, different content

    def test_dry_run_is_the_default_and_writes_nothing(self):
        b = self.bundles()
        before = ic.counts(self.store)
        res = ic.run_import(self.store, TOKEN, b, execute=False, receipt_path=None)
        self.assertTrue(all(r["executed"] is False for r in res)); self.assertEqual(ic.counts(self.store), before)

    def test_preflight_reports_a_fork_before_any_write_and_import_refuses(self):
        recs = ic.records_from_file(CHAIN)
        ic.run_import(self.store, TOKEN, ic.make_bundles(recs, "node-a"), execute=True, receipt_path=None)
        claim = next(r for r in recs if r["kind"] == "Claim")
        from frontier.models import Draft, make_record
        d = {k: claim[k] for k in ("namespace", "kind", "id", "issuer", "source_uri", "visibility")}
        d["predecessor"] = None; d["payload"] = copy.deepcopy(claim["payload"]); d["payload"]["title"] += " v2"
        newer = make_record(Draft.model_validate(d), created_at="2026-11-01T00:00:00+00:00")
        b = ic.make_bundles([newer], "node-a")
        pf = ic.preflight(self.store, TOKEN, b)
        self.assertEqual(len(pf["would_fork"]), 1); self.assertEqual(pf["new_heads"], 0)
        with tempfile.TemporaryDirectory() as out:
            ic.write_plan(b, out, source={})
            with self.assertRaises(ic.ImportRefused) as cm:                     # the REAL CLI path refuses before any write
                ic.main(["import", "--plan", os.path.join(out, "plan.json"), "--dsn", DSN, "--namespace", "delphi-frontier",
                         "--schema", self.store.schema, "--token-file", token_file(self.tmp.name), "--execute"])
            self.assertIn("would fork", str(cm.exception))
        self.assertEqual(ic.counts(self.store)["forks"], 0)

    def test_cli_end_to_end_build_preflight_dry_run_execute_verify(self):
        out = os.path.join(self.tmp.name, "plan")
        dr = draft_files(self.tmp.name)
        common = ["--dsn", DSN, "--namespace", "delphi-frontier", "--schema", self.store.schema, "--token-file", token_file(self.tmp.name)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(ic.main(["build", "--records", CHAIN, "--drafts", dr, "--exclude-id", "turing-ddi", "--out", out]), 0)
            plan = os.path.join(out, "plan.json")
            self.assertEqual(ic.main(["preflight", "--plan", plan, *common]), 0)
            before = ic.counts(self.store)
            self.assertEqual(ic.main(["import", "--plan", plan, *common]), 0)                    # no --execute: dry run
            self.assertEqual(ic.counts(self.store), before)
            rp = os.path.join(self.tmp.name, "r.jsonl")
            self.assertEqual(ic.main(["import", "--plan", plan, *common, "--execute", "--receipt", rp]), 0)
            ro = os.path.join(self.tmp.name, "verify.json")
            self.assertEqual(ic.main(["verify", "--plan", plan, "--dsn", DSN, "--namespace", "delphi-frontier", "--schema", self.store.schema, "--receipt-out", ro]), 0)
        self.assertNotIn(TOKEN, buf.getvalue())
        with open(ro) as fh:
            rep = json.load(fh)
        self.assertEqual(rep["verified_ok"], 10); self.assertEqual(rep["problems"], []); self.assertEqual(rep["status_counts"], {"imported_unreviewed": 10})
        self.assertEqual(rep["counts_now"]["heads"]["node-a/Claim"], 6)          # 2 chain + 4 non-excluded drafts
        with open(rp) as fh:
            self.assertNotIn(TOKEN, fh.read())


    def test_a_contributor_without_the_coordinator_role_cannot_import(self):
        from frontier.store import Forbidden
        b = self.bundles(with_drafts=False)
        self.assertFalse(ic.preflight(self.store, TOKEN_C, b)["can_import"])
        with self.assertRaises(Forbidden):
            self.store.import_bundle(TOKEN_C, ic.key_for(b[0]), b[0])

    def test_quota_is_checked_and_one_write_per_bundle(self):
        self.store.provision("test-only-small-quota-" + uuid4().hex, "small", "small-op", ["contributor", "coordinator"], ["delphi-frontier"], 1)
        b = self.bundles(max_records=3)
        self.assertGreater(len(b), 1)
        before = ic.counts(self.store)["write_receipts_24h"]
        ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=None)
        self.assertEqual(ic.counts(self.store)["write_receipts_24h"] - before, len(b))        # a bundle is one write however many records

    def test_verify_reports_a_record_that_was_never_imported(self):
        b = self.bundles(with_drafts=False)
        ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=None)
        ghost = copy.deepcopy(b)
        r = ghost[0]["records"][0]; r["version"] = "f" * 64
        rep = ic.verify(self.store, ghost)
        self.assertEqual(len(rep["problems"]), 1)                                   # MUST-FAIL control: the checker can say "not found"

    def test_receipts_and_cli_output_never_contain_the_credential(self):
        b = self.bundles(with_drafts=False)
        rp = os.path.join(self.tmp.name, "receipt.jsonl")
        ic.run_import(self.store, TOKEN, b, execute=True, receipt_path=rp)
        with open(rp) as fh:
            self.assertNotIn(TOKEN, fh.read())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print(json.dumps(ic.preflight(self.store, TOKEN, b), default=str))
        self.assertNotIn(TOKEN, buf.getvalue())

    def test_public_records_only_nothing_private_enters(self):
        for bundle in self.bundles():
            for r in bundle["records"]:
                self.assertEqual(r["visibility"], "public")

    def test_other_namespaces_with_the_same_id_are_reported_not_merged(self):
        from frontier.models import Draft, make_record
        local = make_record(Draft.model_validate({"namespace": "delphi-frontier", "kind": "Claim", "id": "turing-ddi", "issuer": "corpus-importer",
                                                  "source_uri": "urn:x", "visibility": "public", "predecessor": None,
                                                  "payload": next(r for r in ic.records_from_file(CHAIN) if r["kind"] == "Claim")["payload"]}),
                            created_at="2026-10-31T00:00:00+00:00")
        ic.run_import(self.store, TOKEN, ic.make_bundles([local], "delphi-frontier"), execute=True, receipt_path=None)
        pf = ic.preflight(self.store, TOKEN, ic.make_bundles(ic.records_from_file(CHAIN), "node-a"))
        self.assertEqual(pf["same_id_in_other_namespaces"].get("Claim/turing-ddi"), ["delphi-frontier"])
        self.assertEqual(pf["would_fork"], [])                                        # different namespace: no shadowing, no fork


if __name__ == "__main__":
    unittest.main()


def _rec(kind, id, payload, *, namespace="node-a", predecessor=None, created="2026-10-31T00:00:00+00:00"):
    from frontier.models import Draft, make_record
    return make_record(Draft.model_validate({"namespace": namespace, "kind": kind, "id": id, "issuer": "tester", "source_uri": "urn:t", "visibility": "public",
                                             "predecessor": predecessor, "payload": payload}), created_at=created)


def _claim_payload(title="c"):
    return {"title": title, "statement": "s", "context": "c", "assumptions": [], "limitations": [],
            "source": {"uri": None, "locator": None, "source_version": None, "content_sha256": None, "content_available": False, "access": "x", "license": None}}


def _evidence_payload(target, produced_by=None, artifacts=()):
    p = {"target": target, "evidence_kind": "simulated", "source": _claim_payload()["source"],
         "created_time": {"value": "2026-10-31T00:00:00+00:00", "basis": "declared"}, "retrieved_time": {"value": "2026-10-31T00:00:00+00:00", "basis": "declared"},
         "method": "m", "context": "c", "assumptions": [], "provenance": {}, "source_dependence": {}, "uncertainty": "u", "limitations": ["l"], "relation": "context_only"}
    if produced_by:
        p["produced_by"] = produced_by
    if artifacts:
        p["artifacts"] = list(artifacts)
    return p


def _action_payload(target, inputs=()):
    return {"target": target, "title": "a", "acceptance_criteria": ["c"], "required_capabilities": [], "cost_stop_bounds": "b", "inputs": list(inputs),
            "cache_key": {"target": target["version"], "input": "i", "code": "c", "model": "m", "environment": "e", "parameters": "p", "scope": "s",
                          "acceptance_policy": models.POLICY}}


class GraphGates(unittest.TestCase):
    def good_set(self):
        claim = _rec("Claim", "c1", _claim_payload())
        t = ic.ref_of(claim)
        action = _rec("Action", "a1", _action_payload(t, [t]))
        out = {"title": "video", "uri": "urn:sha256:" + "a" * 64, "sha256": "a" * 64, "byte_size": 10, "media_type": "video/mp4", "role": "output",
               "availability": "referenced", "license": None}
        ev = _rec("Evidence", "e1", _evidence_payload(t, ic.ref_of(action), [out]))
        return claim, action, ev

    def test_a_consistent_chain_passes_and_lineage_is_tabulated(self):
        g = ic.graph_gates(list(self.good_set()))
        self.assertTrue(g["ok"]); self.assertEqual(g["refused"], [])
        self.assertEqual(g["lineage"][0]["artifact_roles"], ["output"]); self.assertEqual(g["lineage"][0]["action_inputs"], ["c1"])

    def test_dangling_target_producer_and_input_are_refused(self):
        claim, action, ev = self.good_set()
        self.assertFalse(ic.graph_gates([action, ev])["ok"])                    # claim missing: Action target/input and Evidence target dangle
        self.assertFalse(ic.graph_gates([claim, ev])["ok"])                     # Action missing: produced_by dangles
        self.assertTrue(ic.graph_gates([claim, action, ev])["ok"])              # positive control

    def test_producer_and_evidence_must_pin_the_same_target(self):
        claim, action, ev = self.good_set()
        other = _rec("Claim", "c2", _claim_payload("other"))
        bad = _rec("Evidence", "e2", _evidence_payload(ic.ref_of(other), ic.ref_of(action)))
        g = ic.graph_gates([claim, other, action, bad])
        self.assertFalse(g["ok"]); self.assertIn("same target", g["refused"][0]["why"])

    def test_an_imported_assessment_may_not_claim_a_decision(self):
        claim = _rec("Claim", "c1", _claim_payload())
        t = ic.ref_of(claim)
        dims = {d: {"status": "unreviewed", "reviewer": "r", "rationale": "x", "evidence_links": []} for d in models.DIMENSIONS}
        base = {"target": t, "decision": "unreviewed", "dimensions": dims, "independence_rationale": "i", "limitations": ["l"]}
        self.assertTrue(ic.graph_gates([claim, _rec("Assessment", "ok", base)])["ok"])
        accepted = dict(base, decision="accepted")
        self.assertFalse(ic.graph_gates([claim, _rec("Assessment", "acc", accepted)])["ok"])        # MUST-FAIL: imports cannot manufacture review
        passed = copy.deepcopy(base); passed["dimensions"]["source_fidelity"]["status"] = "passed"
        self.assertFalse(ic.graph_gates([claim, _rec("Assessment", "pas", passed)])["ok"])

    def test_dangling_predecessor_is_refused_unless_deliberately_allowed_and_then_warned(self):
        c1 = _rec("Claim", "c1", _claim_payload("v1"))
        v2 = _rec("Claim", "c1", _claim_payload("v2"), predecessor=c1["version"], created="2026-11-01T00:00:00+00:00")
        g = ic.graph_gates([v2])
        self.assertFalse(g["ok"]); self.assertIn("dangling", g["refused"][0]["why"])
        g2 = ic.graph_gates([v2], allow_dangling_predecessor=("c1",))
        self.assertTrue(g2["ok"]); self.assertTrue(any("dangling predecessor allowed" in w["why"] for w in g2["warnings"]))
        self.assertTrue(ic.graph_gates([c1, v2]) is not None)

    def test_shared_producing_action_and_missing_output_artifact_are_flagged(self):
        claim, action, ev = self.good_set()
        ev2 = _rec("Evidence", "e2", _evidence_payload(ic.ref_of(claim), ic.ref_of(action)))          # no artifacts at all
        g = ic.graph_gates([claim, action, ev, ev2])
        why = " | ".join(w["why"] for w in g["warnings"])
        self.assertIn("share one producing Action", why); self.assertIn("no typed artifact with role 'output'", why)


@unittest.skipUnless(DSN, "FRONTIER_TEST_DSN not set: scratch-PostgreSQL submit-local tests NOT run (use scripts/test_postgres.sh)")
class SubmitLocal(unittest.TestCase):
    def setUp(self):
        from frontier.store import Store
        self.store = Store(DSN, "delphi-frontier", "test_" + uuid4().hex)
        self.store.initialize()
        self.store.provision(TOKEN, "corpus-importer", "local-fleet", ["contributor", "coordinator"], ["delphi-frontier"], 1000)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def drafts(self, **mods):
        claim = {"namespace": "frontier-fable", "kind": "Claim", "id": "claim:x-1", "issuer": "fable-lead", "source_uri": "https://example.org/src",
                 "visibility": "public", "predecessor": None, "payload": dict(_claim_payload("from a foreign namespace"), origin="source_statement")}
        problem = {"namespace": "frontier-fable", "kind": "Problem", "id": "problem:x-1", "issuer": "fable-lead", "source_uri": "https://example.org/src",
                   "visibility": "public", "predecessor": None,
                   "payload": {"title": "p", "known_state": "k", "question": "q", "problem_kind": "project_gap", "novelty_status": "n", "data_access": "d",
                               "completeness": "recorded", "required_capabilities": [], "downstream_uses": [], "source": _claim_payload()["source"]}}
        items = [claim, problem]
        for fn in mods.values():
            fn(items)
        p = os.path.join(self.tmp.name, "d.jsonl")
        with open(p, "w") as fh:
            for d in items:
                fh.write(json.dumps(d) + "\n")
        return p

    def run_cli(self, path, *extra):
        out = os.path.join(self.tmp.name, "r.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ic.main(["submit-local", "--input", path, "--dsn", DSN, "--namespace", "delphi-frontier", "--schema", self.store.schema,
                          "--token-file", token_file(self.tmp.name), "--expect-actor", "corpus-importer", "--expect-operator", "local-fleet",
                          "--receipt-out", out, *extra])
        self.assertNotIn(TOKEN, buf.getvalue())
        return rc, json.loads(buf.getvalue().strip().splitlines()[-1]), out

    def test_dry_run_default_writes_nothing_then_execute_reissues_with_provenance_in_the_right_field(self):
        p = self.drafts()
        before = ic.counts(self.store)
        rc, out, _ = self.run_cli(p)
        self.assertEqual((rc, out["mode"], out["written"]), (0, "dry_run", 0)); self.assertEqual(ic.counts(self.store), before)
        rc, out, rp = self.run_cli(p, "--execute")
        self.assertEqual((rc, out["written"]), (0, 2)); self.assertEqual(out["read_back"]["not_head_or_not_proposed"], [])
        with self.store.connection() as c:
            rows = {r["kind"]: r["envelope"] for r in c.execute("SELECT kind,envelope FROM record_versions WHERE kind IN ('Claim','Problem')").fetchall()}
        for kind, env in rows.items():
            self.assertEqual((env["namespace"], env["issuer"]), ("delphi-frontier", "corpus-importer"))
        sub_claim = rows["Claim"]["payload"]["prior_review"]["submission"]; sub_prob = rows["Problem"]["payload"]["original"]["submission"]
        for sub in (sub_claim, sub_prob):
            self.assertEqual((sub["original_namespace"], sub["original_issuer"]), ("frontier-fable", "fable-lead"))
            self.assertIn("not a review", sub["label"]); self.assertEqual(len(sub["draft_content_sha256"]), 64)
        self.assertEqual(rows["Claim"]["payload"]["origin"], "source_statement")             # their content untouched
        with open(rp) as fh:
            self.assertFalse(json.load(fh)["independent_reviewer"])

    def test_rerun_is_unchanged_and_makes_no_new_version(self):
        p = self.drafts()
        self.run_cli(p, "--execute")
        n = ic.counts(self.store)["versions"]
        rc, out, _ = self.run_cli(p, "--execute")
        self.assertEqual((rc, out["planned"]["unchanged"], out["written"]), (0, 2, 0)); self.assertEqual(ic.counts(self.store)["versions"], n)

    def test_content_available_stops_unless_allowed_by_id(self):
        def avail(items):
            items[0]["payload"]["source"].update(content_available=True, license="CC0-1.0")
        p = self.drafts(a=avail)
        rc, out, _ = self.run_cli(p, "--execute")
        self.assertEqual(rc, 3); self.assertIn("AVAILABLE", out["stopped"]); self.assertEqual(ic.counts(self.store)["versions"], 0)
        rc, out, _ = self.run_cli(p, "--execute", "--allow-content-available", "claim:x-1")
        self.assertEqual((rc, out["written"]), (0, 2))

    def test_a_foreign_pin_an_assessment_and_a_path_each_stop_everything_before_any_write(self):
        def pin(items):
            items[0]["payload"]["dependencies"] = [{"namespace": "frontier-fable", "kind": "Claim", "id": "z", "version": "a" * 64}]
        def assess(items):
            items.append({"namespace": "frontier-fable", "kind": "Assessment", "id": "rev", "issuer": "fable-lead", "source_uri": "urn:x", "visibility": "public",
                          "predecessor": None, "payload": {}})
        def path(items):
            items[0]["payload"]["context"] = "see /home/ubuntu/secret"
        for name, fn, needle in (("foreign pin", pin, "pins"), ("assessment", assess, "reviews cannot"), ("path", path, "absolute local path")):
            with self.subTest(name):
                if name == "foreign pin":                       # Claim has no `dependencies`; put the ref in a field that exists
                    fn = lambda items: items[1]["payload"].__setitem__("dependencies", [{"namespace": "frontier-fable", "kind": "Claim", "id": "z", "version": "a" * 64}])
                rc, out, _ = self.run_cli(self.drafts(m=fn), "--execute")
                self.assertEqual(rc, 3, out); self.assertIn(needle, out["stopped"]); self.assertEqual(ic.counts(self.store)["versions"], 0)

    def test_the_wrong_credential_holder_is_refused(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ic.main(["submit-local", "--input", self.drafts(), "--dsn", DSN, "--namespace", "delphi-frontier", "--schema", self.store.schema,
                          "--token-file", token_file(self.tmp.name), "--expect-actor", "someone-else", "--expect-operator", "local-fleet", "--execute"])
        self.assertEqual(rc, 3); self.assertEqual(ic.counts(self.store)["versions"], 0)

