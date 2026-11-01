"""Tests for the live Delphi ingestion (`delphi_live`) and the two mapping fixes it needed in `delphi_claim`.

Offline: the claim-test fixture is the real rows of one Delphi nanopub, saved with its receipt. Every rule has a must-fail control.
Run (bounded):
  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
    python3 -m pytest frontier_adapters/tests/test_delphi_live.py -q
"""
import copy
import json
import os
import unittest

from frontier.models import Draft, make_record
from frontier_adapters import delphi_claim as dc, delphi_live as dl
from frontier_adapters.common import validate_draft

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples")
CID = "thompson1917-ch07-04"
TARGET = {"namespace": "node-a", "kind": "Claim", "id": CID, "version": "a" * 64}
AT = "2026-10-31T20:30:00+00:00"


def rows():
    with open(os.path.join(EX, "delphi_live", "fixtures", f"claim-test-{CID}.rows.json")) as fh:
        return json.load(fh)["rows"]


def claim_draft(cid="darwin1859-ch02-04"):
    with open(os.path.join(EX, "delphi_snapshots", cid + ".json")) as fh:
        return dc.to_claim_draft(json.load(fh)["snapshot"])


class ClaimTest(unittest.TestCase):
    def test_real_claim_test_nanopub_is_read_whole(self):
        ts = dl.test_snapshot(CID, rows())
        self.assertEqual((ts["verdict"], ts["confidence"], ts["data_kind"], ts["preregistered"]), ("mixed", 0.35, "biological", "false"))
        self.assertEqual(ts["assessment_type"], "claim-test/0.1.0")
        self.assertEqual(len(ts["datasets"]), 5)
        self.assertTrue(all(len(d["declared_sha256"]) == 64 and d["bytes_checked"] is False for d in ts["datasets"]))
        self.assertEqual(len(ts["revisions"]), 1)                                  # the upstream revision is kept, not flattened
        self.assertEqual(len(ts["caveats"]), 6)
        self.assertRegex(ts["result_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(ts["nanopub_path"], f"test-data/claim-tests/nanopubs/unsigned/{CID}.trig")
        self.assertTrue(ts["fail_criterion"] and ts["pass_criterion"] and ts["admissible_datasets"])

    def test_partial_read_is_refused_not_mapped(self):
        part = [r for r in rows() if not r["g"].endswith("#pubinfo")]
        with self.assertRaises(LookupError):
            dl.test_snapshot(CID, part)
        with self.assertRaises(LookupError):                                       # rows of another claim are not this claim
            dl.test_snapshot("thompson1917-ch07-05", rows())

    def test_evidence_draft_is_valid_and_keeps_the_verdict_raw(self):
        ts = dl.test_snapshot(CID, rows())
        ev = dl.to_evidence_draft(ts, TARGET, AT)
        rec = validate_draft(ev)
        self.assertEqual(rec["licence_gate_offenders"], [])
        p = ev["payload"]
        self.assertEqual(p["evidence_kind"], "source_assessment")
        self.assertEqual(p["relation"], "unspecified")                              # `mixed` is not mapped to `qualifies`
        self.assertEqual(p["provider_assessment"]["verdict"], "mixed")
        self.assertIn("NOT local acceptance", p["provider_assessment"]["label"])
        self.assertEqual(p["artifacts"] if "artifacts" in p else [], [])            # no ArtifactRef without checked bytes
        self.assertEqual(p["source"]["source_version"], ts["result_commit"])
        self.assertEqual(p["created_time"]["basis"], "declared")
        self.assertEqual(p["retrieved_time"], {"value": AT, "basis": "witnessed"})
        self.assertTrue(any("did not re-run" in x for x in p["limitations"]))

    def test_relation_only_for_literal_supports_or_refutes(self):
        ts = dl.test_snapshot(CID, rows())
        for verdict, rel in (("supports", "supports"), ("refutes", "refutes"), ("inconclusive", "unspecified"), ("mixed", "unspecified")):
            self.assertEqual(dl.to_evidence_draft({**ts, "verdict": verdict}, TARGET, AT)["payload"]["relation"], rel)

    def test_evidence_must_pin_the_tested_claim(self):
        ts = dl.test_snapshot(CID, rows())
        with self.assertRaises(ValueError):
            dl.to_evidence_draft(ts, {**TARGET, "id": "darwin1859-ch02-04"}, AT)
        with self.assertRaises(ValueError):
            dl.to_evidence_draft({**ts, "verdict": None}, TARGET, AT)


class Diff(unittest.TestCase):
    def setUp(self):
        self.d = claim_draft()
        self.ref = {"namespace": "node-a", "kind": "Claim", "id": self.d["id"],
                    "version": make_record(Draft.model_validate(self.d), created_at=dl.created_at_of(self.d))["version"]}

    def classify(self, now):
        return dl.classify({self.d["id"]: self.d}, {self.d["id"]: now}, {self.d["id"]: self.ref})["rows"][self.d["id"]]

    def test_identical_is_unchanged(self):
        self.assertEqual(self.classify(copy.deepcopy(self.d))["status"], "unchanged")

    def test_path_move_is_relocated_not_an_update(self):
        now = copy.deepcopy(self.d)
        o = now["payload"]["prior_review"]["delphi_original"]
        o["nanopub_path"], o["domain_dir"] = "claim-sources/darwin-origin/nanopubs/unsigned/x.trig", "darwin-origin"
        r = self.classify(now)
        self.assertEqual((r["status"], r["changed_location"], r["changed_content"]), ("relocated", ["domain_dir", "nanopub_path"], []))
        self.assertEqual(dl.increment({"rows": {self.d["id"]: r}}, {self.d["id"]: now}), {"new": [], "updates": []})

    def test_label_move_is_labels_changed_and_makes_no_fork(self):
        now = copy.deepcopy(self.d)
        now["payload"]["prior_review"]["delphi_original"]["delphi_graph"]["truth"] = 0.1
        r = self.classify(now)
        self.assertEqual((r["status"], r["changed_labels"]), ("labels_changed", ["delphi_graph.truth"]))
        self.assertEqual(dl.increment({"rows": {self.d["id"]: r}}, {self.d["id"]: now})["updates"], [])

    def test_statement_change_is_an_update_with_the_imported_predecessor(self):
        now = copy.deepcopy(self.d)
        now["payload"]["statement"] += " (revised)"
        r = self.classify(now)
        self.assertEqual((r["status"], r["changed_content"]), ("content_changed", ["statement"]))
        inc = dl.increment({"rows": {self.d["id"]: r}}, {self.d["id"]: now})
        self.assertEqual(inc["updates"][0]["predecessor"], self.ref["version"])
        validate_draft(inc["updates"][0])

    def test_new_removed_and_withheld(self):
        other = claim_draft("thompson1917-ch03-05")
        c = dl.classify({self.d["id"]: self.d}, {other["id"]: other}, {self.d["id"]: self.ref}, {"x-1": "ValueError: bad"})["counts"]
        self.assertEqual(c, {"new": 1, "removed_upstream": 1, "withheld": 1})

    def test_baseline_must_reproduce_the_imported_version(self):
        self.assertEqual(dl.reproduce_imported({self.d["id"]: self.d}, {self.d["id"]: self.ref})["reproduced_exactly"], 1)
        bad = copy.deepcopy(self.d)
        bad["payload"]["title"] += "!"
        rep = dl.reproduce_imported({self.d["id"]: bad}, {self.d["id"]: self.ref})
        self.assertEqual((rep["reproduced_exactly"], len(rep["mismatched"])), (0, 1))


class ClaimMappingFixes(unittest.TestCase):
    def test_domain_dir_in_both_repository_layouts(self):
        self.assertEqual(dc.domain_dir_of("books/darwin-origin/nanopubs/unsigned/x.trig"), "darwin-origin")
        self.assertEqual(dc.domain_dir_of("math-bio-claims/nanopubs/unsigned/x.trig"), "math-bio-claims")
        self.assertEqual(dc.domain_dir_of("claim-sources/darwin-origin/nanopubs/unsigned/x.trig"), "darwin-origin")
        self.assertIsNone(dc.domain_dir_of(None))

    def _rows(self, with_model: bool, with_isbn: bool):
        g = "https://w3id.org/delphi/local/claim-sources/x/nanopubs/unsigned/c-1.trig"
        iri = dc.CLAIM_PREFIX + "c-1"
        rs = [{"g": g + "#Head", "s": g, "p": "p", "o": "o"}, {"g": g + "#pubinfo", "s": g, "p": "p", "o": "o"},
              {"g": g + "#assertion", "s": iri, "p": "http://www.w3.org/2000/01/rdf-schema#label", "o": "T"},
              {"g": g + "#assertion", "s": iri, "p": "http://purl.org/dc/terms/description", "o": "S"},
              {"g": g + "#assertion", "s": iri, "p": "https://w3id.org/delphi/ontology/context", "o": "C"},
              {"g": g + "#assertion", "s": "q", "p": "https://schema.org/text", "o": "a quote"},
              {"g": g + "#provenance", "s": "q", "p": "http://www.w3.org/ns/prov#hadPrimarySource",
               "o": "https://www.gutenberg.org/x.txt#line=1,2"}]
        if with_model:
            m = "https://w3id.org/delphi/resource/model/claude-fable-5-1"
            rs += [{"g": g + "#provenance", "s": m, "p": dc.RDF_TYPE, "o": dc.LANGUAGE_MODEL},
                   {"g": g + "#provenance", "s": m, "p": "http://purl.org/dc/terms/identifier", "o": "claude-fable-5.1"}]
        if with_isbn:
            rs.append({"g": g + "#provenance", "s": "https://example.org/book", "p": "http://purl.org/dc/terms/identifier", "o": "978-0"})
        return rs

    def test_a_language_model_identifier_is_not_a_source_identifier(self):
        snap, _ = dc.snapshot_from_rows("c-1", self._rows(True, False), {"nanopub": None, "registry": None})
        self.assertEqual((snap["kind"], snap["source"]["isbn"], snap["domain_dir"]), ("literature", None, "x"))
        snap, _ = dc.snapshot_from_rows("c-1", self._rows(True, True), {"nanopub": None, "registry": None})     # model row comes first
        self.assertEqual(snap["source"]["isbn"], "978-0")
        snap, _ = dc.snapshot_from_rows("c-1", self._rows(False, True), {"nanopub": None, "registry": None})    # positive control
        self.assertEqual(snap["source"]["isbn"], "978-0")

    def test_local_unsigned_claim_is_never_labelled_production(self):
        snap, _ = dc.snapshot_from_rows("c-1", self._rows(False, False), {"nanopub": None, "registry": None})
        state = dc.to_claim_draft(snap)["payload"]["prior_review"]["delphi_original"]["publication_state"]
        self.assertTrue(state.startswith("delphi_local_unsigned_nanopub"))
        snap2 = {**snap, "registry": "production", "nanopub_uri": "https://w3id.org/np/RAx"}
        self.assertEqual(dc.to_claim_draft(snap2)["payload"]["prior_review"]["delphi_original"]["publication_state"],
                         "delphi_production_registry")


class Readable(unittest.TestCase):
    def test_context_row_carries_math_conditions_and_deep_link_without_quote_text(self):
        d = claim_draft("darwin1859-ch02-04")
        row = dl.readable_context(d, {"namespace": "node-a", "kind": "Claim", "id": d["id"], "version": "b" * 64})
        self.assertEqual(row["conditions"], d["payload"]["context"])
        self.assertFalse(row["source"]["quote"]["stored"])
        self.assertNotIn("quote_text", json.dumps(row))
        if d["payload"]["source"]["locator"].startswith("line="):
            self.assertTrue(row["source"]["deep_link"].endswith("#" + d["payload"]["source"]["locator"]))
        self.assertIn("never Frontier acceptance", row["upstream_labels"]["label"])


if __name__ == "__main__":
    unittest.main()


DSN, RUN_DIR = os.environ.get("FRONTIER_TEST_DSN"), os.environ.get("DELPHI_LIVE_RUN")


@unittest.skipUnless(DSN and RUN_DIR, "FRONTIER_TEST_DSN and DELPHI_LIVE_RUN not both set: the trial import of a live run into a "
                                      "scratch store is NOT run (scripts/test_postgres.sh, and DELPHI_LIVE_RUN=<run dir>)")
class TrialImportOfALiveRun(unittest.TestCase):
    """Rebuild what Frontier imported (880 Claims), import it into a scratch store, then import the live run's plan on top:
    nothing forks, every record lands as imported_unreviewed and head, every Evidence target resolves, and a re-run writes nothing."""

    def test_live_plan_imports_on_top_of_the_imported_baseline(self):
        import glob
        from uuid import uuid4

        from frontier.store import Store
        from frontier_adapters import import_cli as ic
        tok = "test-only-coordinator-token-" + uuid4().hex
        store = Store(DSN, "delphi-frontier", "test_" + uuid4().hex)
        store.initialize()
        store.provision(tok, "corpus-importer", "local-fleet", ["contributor", "coordinator"], ["delphi-frontier"], 1000)
        prev, imp, created = dl.load_baseline(sorted(glob.glob(os.path.join(os.environ["DELPHI_BASELINE_GLOB"]))) if os.environ.get("DELPHI_BASELINE_GLOB") else [],
                                              [os.path.join(EX, "live_import", "plan-claims.json")], [os.path.join(EX, "nca_chain", "records.json")])
        if len(prev) < len(imp):
            self.skipTest("DELPHI_BASELINE_GLOB (the frozen bulk drafts) not set; baseline cannot be rebuilt")
        base = [make_record(Draft.model_validate(prev[i]), created_at=created.get(i) or dl.created_at_of(prev[i])) for i in imp]
        self.assertTrue(all(b["version"] == imp[b["id"]]["version"] for b in base))
        for b in ic.make_bundles(base, "node-a"):
            store.import_bundle(tok, ic.key_for(b), b)
        plan, bundles = ic.load_bundles(os.path.join(RUN_DIR, "plan-new", "plan.json"))
        pre = ic.preflight(store, tok, bundles)
        self.assertEqual((pre["would_fork"], pre["gates"]["refused"]), ([], []))
        res = ic.run_import(store, tok, bundles, execute=True, receipt_path=None)
        self.assertFalse([r for r in res if r.get("error") or r.get("forks")])
        rep = ic.verify(store, bundles)
        self.assertEqual((rep["problems"], rep["verified_ok"]), ([], plan["total_records"]))
        before = ic.counts(store)
        ic.run_import(store, tok, bundles, execute=True, receipt_path=None)       # idempotent: replays the stored response
        after = ic.counts(store)
        self.assertEqual({k: v for k, v in after.items() if k != "write_receipts_24h"},
                         {k: v for k, v in before.items() if k != "write_receipts_24h"})
        with open(os.path.join(RUN_DIR, "plan-new", "trial-import.json"), "w") as fh:
            json.dump({"plan_sha256": plan["plan_sha256"], "baseline_records": len(base), "preflight_would_fork": pre["would_fork"],
                       "inserted": sum(r.get("inserted", 0) for r in res), "rerun_changed_counts": before != after and
                       {k: (before[k], after[k]) for k in after if before.get(k) != after[k]}, "verify": {k: rep[k] for k in ("verified_ok", "status_counts")},
                       "counts_now": rep["counts_now"]}, fh, indent=1, sort_keys=True, default=str)
