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
