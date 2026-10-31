"""Tests for the Claim/Evidence/Action adapters, the artifact manifest and the unsigned nanopub draft exporter.

Run (bounded):
  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
    python3 -m pytest frontier_adapters/tests -q

Offline by default. Live re-verification of the NCA chain against the producer's git repo and OpenResearch store is gated on
NCA_REPO and ORX_STORE and is reported as SKIPPED with that reason, never as passed. Every safety rule has a must-fail control.
"""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from frontier import models
from frontier_adapters import artifacts as art, delphi_claim as dc, nanopub_draft as nd, orx_evidence as oe, orx_replay
from frontier_adapters.common import sha_bytes, validate_draft
from frontier_adapters.delphi_mcp import Delphi, NonJson, RetrievalStopped, json_from_text, rows_of

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples")
RUN = os.path.join(EX, "orx_run_turing")
CHAIN = os.path.join(EX, "nca_chain")
RUN_ID = "330735e8-d32e-47cd-99ee-fb54845367d7"
NCA_RUN = "f81c0b68-ad0c-4ebe-b809-96977ad1c0f3"
NCA_REPO, ORX_STORE = os.environ.get("NCA_REPO"), os.environ.get("ORX_STORE")
COMMIT = "1067cdb7b49dcfd77102d6d9a3242cfe8cd20268"

try:
    import rdflib
except ImportError:
    rdflib = None


def snap(cid):
    with open(os.path.join(EX, "delphi_snapshots", cid + ".json")) as fh:
        return json.load(fh)


def claim_draft(cid, verified=True, **kw):
    d = snap(cid)
    return dc.to_claim_draft(d["snapshot"], verification=d["verification"] if verified else None, **kw)


def load(name):
    with open(os.path.join(CHAIN, name)) as fh:
        return json.load(fh)


TARGET = {"namespace": "node-a", "kind": "Claim", "id": "turing-ddi", "version": "a" * 64}
AUTHOR = {"assumptions": ["declared instance"], "limitations": ["one instance"], "uncertainty": "exact arithmetic"}


def facts():
    return oe.read_run(run_id=RUN_ID, export_dir=RUN, result_file="results.json")


class DelphiClient(unittest.TestCase):
    def test_sparql_row_shapes_are_normalised_and_unknown_shapes_fail_loudly(self):
        self.assertEqual(rows_of([{"a": 1}]), [{"a": 1}])
        self.assertEqual(rows_of({"1": {"b": 2}, "0": {"a": 1}}), [{"a": 1}, {"b": 2}])     # the shape the service uses now
        self.assertEqual(rows_of({}), [])
        with self.assertRaises(NonJson):                                                      # not read as "empty"
            rows_of({"error": "x"})

    def test_overview_style_markdown_preface_then_json(self):
        self.assertEqual(json_from_text("**Claim graph:** 1190 claims\n\n| t |\n\n{\n  \"files\": 3\n}"), {"files": 3})
        with self.assertRaises(NonJson):
            json_from_text("just prose")

    def test_persistent_429_stops_after_the_limit_honouring_retry_after(self):
        import urllib.error
        import urllib.request
        calls = {"n": 0}

        def boom(*a, **k):
            calls["n"] += 1
            raise urllib.error.HTTPError("u", 429, "Too Many", {"Retry-After": "7"}, None)
        real, sleeps = urllib.request.urlopen, []
        urllib.request.urlopen = boom
        try:
            with self.assertRaises(RetrievalStopped) as cm:
                Delphi(sleep=sleeps.append, persistent_429=3)
            self.assertIn("persistent", str(cm.exception))
            self.assertEqual(calls["n"], 3)                 # exactly three attempts, then it stops
            self.assertEqual([x for x in sleeps if x == 7.0], [7.0, 7.0])      # Retry-After honoured both times (other sleeps are pacing)
        finally:
            urllib.request.urlopen = real

    def test_access_denial_stops_immediately(self):
        import urllib.error
        import urllib.request
        real = urllib.request.urlopen

        def deny(*a, **k):
            raise urllib.error.HTTPError("u", 403, "no", {}, None)
        urllib.request.urlopen = deny
        try:
            with self.assertRaises(RetrievalStopped):
                Delphi(sleep=lambda s: None)
        finally:
            urllib.request.urlopen = real

    def test_query_builder_rejects_unsafe_ids(self):
        self.assertIn("turing-ddi", dc.claim_rows_query(["turing-ddi"]))
        for bad in ('x"; DROP', "a b", "a\\b", "a#b"):
            with self.assertRaises(ValueError):
                dc.claim_rows_query([bad])


class DelphiClaim(unittest.TestCase):
    def test_all_snapshots_validate_under_real_models_and_licence_gate(self):
        for cid in ("turing-ddi", "darwin1859-ch02-04", "wolfram2002-ch02-08", "thompson1917-ch03-05", "fisher-ftns", "levin-2024-anthrobots-08"):
            v = validate_draft(claim_draft(cid))
            self.assertEqual(v["licence_gate_offenders"], [], cid)

    def test_original_delphi_identifiers_and_versions_are_preserved(self):
        for cid in ("turing-ddi", "darwin1859-ch02-04", "wolfram2002-ch02-08"):
            d = claim_draft(cid)
            self.assertEqual(d["id"], cid)
            self.assertEqual(d["source_uri"], "https://w3id.org/delphi/resource/claim/" + cid)
            self.assertTrue(d["payload"]["source_record_version"].startswith("https://w3id.org/np/RA"), cid)
            self.assertIn(d["payload"]["prior_review"]["delphi_original"]["registry"], ("production", "test"))
            self.assertTrue(d["payload"]["prior_review"]["adapter"]["retrieved_at"])

    def test_unpublished_catalog_entry_is_labelled_and_mints_no_iri_or_nanopub(self):
        d = claim_draft("levin-2024-anthrobots-08")
        o = d["payload"]["prior_review"]["delphi_original"]
        self.assertIsNone(d["payload"]["source_record_version"]); self.assertIsNone(o["claim_iri"]); self.assertIsNone(o["registry"])
        self.assertEqual(o["publication_state"], "unpublished_catalog_entry")
        self.assertTrue(d["source_uri"].startswith("urn:frontier:import:delphi-claim-graph:"))
        self.assertIsNone(d["payload"]["source"]["uri"]); self.assertIsNone(d["payload"]["source"]["content_sha256"])
        self.assertIn("nanopub", o["absent_in_record"])
        with self.assertRaises(ValueError):                               # a published claim is not built as a catalog entry
            dc.snapshot_from_catalog({"id": "x", "title": "t", "statement": "s", "nanopub": "https://w3id.org/np/RAx", "registry": "production"})

    def test_upstream_labels_travel_as_labelled_assertions_and_origin_is_never_asserted(self):
        d = claim_draft("turing-ddi")
        g = d["payload"]["prior_review"]["delphi_original"]["delphi_graph"]
        self.assertIn("NEVER local acceptance", g["label"])
        self.assertNotIn("origin", d["payload"])                         # omission means unknown
        with self.assertRaises(ValueError):
            claim_draft("turing-ddi", origin="source_statement")
        self.assertEqual(claim_draft("turing-ddi", origin="derived")["payload"]["origin"], "derived")

    def test_content_never_available_and_no_licence_claimed(self):
        for cid in ("turing-ddi", "darwin1859-ch02-04", "wolfram2002-ch02-08", "fisher-ftns", "levin-2024-anthrobots-08"):
            s = claim_draft(cid)["payload"]["source"]
            self.assertFalse(s["content_available"], cid); self.assertIsNone(s["license"], cid)

    def test_quote_text_is_never_stored_only_its_digest(self):
        for cid in ("darwin1859-ch02-04", "wolfram2002-ch02-08", "thompson1917-ch03-05"):
            q = claim_draft(cid)["payload"]["prior_review"]["delphi_original"]["quote"]
            self.assertFalse(q["text_stored"]); self.assertEqual(len(q["sha256"]), 64); self.assertGreater(q["chars"], 0)
        self.assertNotIn("quote_text", json.dumps(snap("darwin1859-ch02-04")))

    def test_wolfram_rights_statement_is_carried_verbatim_and_record_licence_is_scoped(self):
        perm = claim_draft("wolfram2002-ch02-08")["payload"]["prior_review"]["delphi_original"]["permission"]
        self.assertIn("all rights reserved", perm["source_text_rights"])
        self.assertIn("NOT to the quoted source text", perm["delphi_record_license_applies_to"])
        self.assertFalse(perm["quote_text_included_in_output"])

    def test_recorded_hash_is_carried_only_after_verification(self):
        d = snap("darwin1859-ch02-04")
        recorded = d["snapshot"]["source"]["recorded_sha256"]
        self.assertEqual(dc.to_claim_draft(d["snapshot"], verification=d["verification"])["payload"]["source"]["content_sha256"], recorded)
        unverified = dc.to_claim_draft(d["snapshot"], verification=None)["payload"]
        self.assertIsNone(unverified["source"]["content_sha256"])
        self.assertEqual(unverified["prior_review"]["delphi_original"]["recorded_sha256_unverified"], recorded)
        bad = dict(d["verification"], sha256_match=False)                                   # MUST-FAIL control
        self.assertIsNone(dc.to_claim_draft(d["snapshot"], verification=bad)["payload"]["source"]["content_sha256"])

    def test_verify_source_detects_tampered_bytes_and_altered_quote(self):
        d = snap("darwin1859-ch02-04")["snapshot"]
        lines = [f"line {i}" for i in range(2000)]
        a, _ = map(int, d["source"]["locator"][5:].split(","))
        lines[a] = "an authentic sentence"
        raw = "\n".join(lines).encode()
        ver = dc.verify_source(d, {"quote": "an authentic sentence"}, fetch=lambda u: raw)
        self.assertFalse(ver["sha256_match"]); self.assertEqual(ver["quote_at_locator"], "exact")
        self.assertEqual(dc.verify_source(d, {"quote": "a sentence that is not there"}, fetch=lambda u: raw)["quote_at_locator"], "not_found")

    def test_math_claims_state_what_is_absent_and_internal_iri_is_not_a_uri(self):
        t = claim_draft("turing-ddi")["payload"]
        self.assertIsNone(t["source"]["locator"]); self.assertTrue(t["source"]["uri"].startswith("https://doi.org/"))
        self.assertIn("locator", t["prior_review"]["delphi_original"]["absent_in_record"])
        self.assertIsNone(claim_draft("fisher-ftns")["payload"]["source"]["uri"])

    def test_incomplete_graph_read_fails_loudly(self):
        rows = [{"g": "x/nanopubs/unsigned/c.trig#assertion", "s": "s", "p": "p", "o": "o"}]
        with self.assertRaises(LookupError):
            dc.snapshot_from_rows("c", rows, {})


class Artifacts(unittest.TestCase):
    def test_absolute_path_scanner_has_positive_and_must_pass_controls(self):
        self.assertEqual(art.scrub_paths("run /home/ubuntu/miniconda3/bin/python3 -I x.py"), ("run <abs-path-withheld> -I x.py", True))
        self.assertTrue(art.find_abs_paths({"a": ["see /data/worktrees/x"], "/tmp/k": 1}))                       # must be found
        self.assertEqual(art.find_abs_paths({"l": "git:kganjam/delphi-evolve@1067cdb:scopedesk/a.json", "u": "https://data.caltech.edu/records/1"}), [])

    def test_git_blob_id_matches_git(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            with open(os.path.join(d, "f"), "wb") as fh:
                fh.write(b"hello\n")
            self.assertEqual(art.git_blob_id(b"hello\n"), subprocess.run(["git", "-C", d, "hash-object", "f"], capture_output=True, text=True).stdout.strip())

    def test_artifact_ref_maps_to_the_stores_typed_model_and_is_validated_by_it(self):
        e = art.entry("report", b"abc", path="a/REPORT.md", repo_label="o/r", commit="c" * 40)
        ref = models.ArtifactRef.model_validate(art.to_artifact_ref(e))
        self.assertEqual(ref.role, "output"); self.assertEqual(ref.availability, "referenced"); self.assertTrue(ref.uri.startswith("urn:sha256:"))
        bad = dict(art.to_artifact_ref(e), uri="https://u:p@x.org/f")             # credentials in a URL are refused by the model
        with self.assertRaises(Exception):
            models.ArtifactRef.model_validate(bad)

    def test_manifest_refuses_absolute_paths_and_claims_nothing_is_hosted(self):
        e = art.entry("input", b"x", path="a/b.jsonl", where="held in the producer's store")
        m = art.manifest({"run_id": "r"}, [e], proposed_site_path="/artifacts/r/manifest.json")
        self.assertFalse(m["hosting"]["hosted"]); self.assertFalse(m["bytes_included"]); self.assertIn("MIT", m["licence_note"])
        with self.assertRaises(ValueError):
            art.manifest({"run_id": "r"}, [dict(e, path="/home/u/secret.csv")], proposed_site_path="/artifacts/r/manifest.json")


class OrxEvidence(unittest.TestCase):
    def test_export_reads_back_and_verifies_digests(self):
        f = facts()
        self.assertEqual(f["status"], "done"); self.assertEqual(f["exit_code_file"], 0); self.assertIsNone(f["db_exit_code"])
        self.assertEqual(f["result_sha256"], "b4698e56aed6496cfae6cb32dc3ef50c8b3fdd21d051f000a5de25abc74e2c45")

    def test_export_contains_no_local_absolute_paths(self):
        for n in ("run.json", "health.json"):
            with open(os.path.join(RUN, n)) as fh:
                self.assertEqual(art.find_abs_paths(fh.read()), [])

    def test_refuses_failed_nonzero_tampered_or_missing(self):
        def tamper(fn):
            tmp = tempfile.mkdtemp(); dst = os.path.join(tmp, "run"); shutil.copytree(RUN, dst); fn(dst); return tmp, dst

        def not_done(d):
            with open(d + "/run.json") as fh:
                j = json.load(fh)
            j["run"]["status"] = "failed"
            with open(d + "/run.json", "w") as fh:
                json.dump(j, fh)

        def nonzero(d):
            with open(d + "/exit_code", "w") as fh:
                fh.write("1\n")

        def no_exit(d):
            os.remove(d + "/exit_code")

        def tar(d):
            with open(d + "/source.tar", "rb") as fh:
                b = bytearray(fh.read())
            b[600] ^= 0xFF
            with open(d + "/source.tar", "wb") as fh:
                fh.write(bytes(b))

        def no_result(d):
            os.remove(d + "/outputs/results.json")
        for name, m in (("status", not_done), ("exit", nonzero), ("exit-missing", no_exit), ("tar", tar), ("result", no_result)):
            tmp, dst = tamper(m)
            with self.subTest(name), self.assertRaises(oe.Refused):
                oe.read_run(run_id=RUN_ID, export_dir=dst, result_file="results.json")
            shutil.rmtree(tmp)

    def test_refuses_observed_formal_and_assessment_kinds(self):
        for k in ("observed", "formal", "source_assessment", "anything"):
            with self.subTest(k), self.assertRaises(oe.Refused):
                oe.to_evidence_draft(facts(), target=TARGET, author=AUTHOR, kind=k)

    def test_draft_validates_and_is_digest_only(self):
        d = oe.to_evidence_draft(facts(), target=TARGET, author=AUTHOR)
        p = d["payload"]
        self.assertFalse(p["source"]["content_available"]); self.assertIsNone(p["source"]["license"])
        self.assertEqual(p["provenance"]["field_origin"]["provider_assessment"], "absent")
        self.assertNotIn("relation", p)                                            # default relation is omitted, keeping old payload bytes
        self.assertEqual(validate_draft(d)["licence_gate_offenders"], [])
        leaky = copy.deepcopy(d); leaky["payload"]["source"]["content_available"] = True      # MUST-FAIL control: the store gate refuses
        self.assertTrue(validate_draft(leaky)["licence_gate_offenders"])

    def test_replay_requires_trust_flag_and_rejects_vacuous_mutation(self):
        with self.assertRaises(PermissionError):
            orx_replay.replay(RUN, command="python3 run_modes.py", result_file="results.json", recorded_sha256="0" * 64, interpreters={"x": "/usr/bin/python3"})
        with self.assertRaises(PermissionError):
            orx_replay.replay_external(b"", inputs={}, command="x", interpreter="python3", config_key="k", output_name="o")
        with self.assertRaises(ValueError):
            orx_replay.replay(RUN, command="python3 run_modes.py", result_file="results.json", recorded_sha256="0" * 64,
                              interpreters={"x": "/usr/bin/python3"}, trust_code=True, mutation=("run_modes.py", "NOT PRESENT", "x"))


class NcaChain(unittest.TestCase):
    """The committed claim -> action -> evidence -> artifact chain for orx run f81c0b68 (local backend)."""

    def records(self):
        return {(r["kind"], r["id"]): r for r in load("records.json")}

    def test_six_records_validate_and_link_by_exact_version(self):
        recs = list(self.records().values())
        self.assertEqual(sorted(r["kind"] for r in recs), ["Action", "Action", "Claim", "Claim", "Evidence", "Evidence"])
        by_version = {r["version"]: r for r in recs}
        for r in recs:                                                      # Record.model_validate recomputes every version digest
            models.Record.model_validate(r)
        for e in (r for r in recs if r["kind"] == "Evidence"):
            t, pb = e["payload"]["target"], e["payload"]["produced_by"]
            self.assertEqual(by_version[t["version"]]["id"], t["id"])
            act = by_version[pb["version"]]
            self.assertEqual(act["payload"]["target"], t)                  # the store's own rule: producer and evidence share a target
            self.assertEqual([i["version"] for i in act["payload"]["inputs"]], [t["version"]])
            self.assertEqual(e["payload"]["relation"], "qualifies")
            self.assertEqual(e["payload"]["evidence_kind"], "simulated")

    def test_evidence_is_never_observed_and_artifacts_are_typed_referenced_and_unlicensed(self):
        for r in self.records().values():
            if r["kind"] != "Evidence":
                continue
            self.assertNotEqual(r["payload"]["evidence_kind"], "observed")
            self.assertFalse(r["payload"]["source"]["content_available"]); self.assertIsNone(r["payload"]["source"]["license"])
            arts = r["payload"]["artifacts"]
            self.assertEqual(sorted({a["role"] for a in arts}), ["code", "input", "log", "output", "protocol"])
            for a in arts:
                models.ArtifactRef.model_validate(a)
                self.assertEqual(a["availability"], "referenced"); self.assertIsNone(a["license"]); self.assertEqual(a["uri"], "urn:sha256:" + a["sha256"])

    def test_every_link_check_passed_and_controls_discriminate(self):
        for c in load("link_checks.json"):
            self.assertTrue(c["passed"], c["name"])
        rep = load("replay_report.json")
        self.assertTrue(rep["results"]["full_inputs"]["matches_recorded"]); self.assertTrue(rep["results"]["full_inputs"]["stdout_matches_recorded_log"])
        self.assertFalse(rep["control_results"]["one_row_changed"]["output_matches_expected"])      # must-fail control
        self.assertFalse(rep["missing_input_probe"]["output_matches_expected"])                     # the finding: inputs are not listed by orx
        self.assertEqual(rep["missing_input_probe"]["exit"], 0)

    def test_limitations_name_what_openresearch_did_not_record(self):
        for r in self.records().values():
            if r["kind"] == "Evidence":
                text = " ".join(r["payload"]["limitations"])
                for needle in ("execution environment", "OUTSIDE the OpenResearch snapshot", "does not list a run's inputs", "NULL", "sweep itself ran outside"):
                    self.assertIn(needle, text)

    def test_reuse_counts_keep_declared_executed_and_reviewed_apart(self):
        c = load("chain.json")
        self.assertEqual(c["counts"]["actions_declared"], 2); self.assertEqual(c["counts"]["distinct_runs_behind_the_evidence"], 1)
        self.assertEqual(c["reuse_counts"]["independently_reviewed_reuse"], 0)
        self.assertIn("benefit not measured", c["reuse_counts"]["executed_reuse"])
        self.assertTrue(all(cl["origin"] == "unknown" for cl in c["claims"]))

    def test_no_absolute_local_path_anywhere_in_the_committed_output(self):
        for n in sorted(os.listdir(CHAIN)):
            with open(os.path.join(CHAIN, n)) as fh:
                self.assertEqual(art.find_abs_paths(fh.read()), [], n)

    def test_artifact_manifest_is_digest_only_and_not_claimed_hosted(self):
        m = load("artifact-manifest.json")
        self.assertFalse(m["bytes_included"]); self.assertFalse(m["hosting"]["hosted"]); self.assertTrue(m["hosting"]["proposed_site_path"].startswith("/artifacts/"))
        self.assertTrue(all(a["content_available"] is False and a["license"] is None for a in m["artifacts"]))
        rows = next(a for a in m["artifacts"] if a["path"].endswith("rows.jsonl"))
        self.assertEqual(rows["sha256"], "a32c2bf7dd3c10162317974ae6a0ecbefa06c1c180a6886dea1bcb8ea4d4c882")

    def test_drafts_rebuild_byte_identically_from_the_committed_records(self):
        recs = self.records()
        for (kind, rid), r in recs.items():
            tc = recs[("Claim", r["payload"]["target"]["id"])] if kind == "Evidence" else None
            with open(os.path.join(CHAIN, f"{kind.lower()}--{rid}.draft.trig")) as fh:
                self.assertEqual(nd.record_to_trig(r, target_claim=tc), fh.read(), rid)

    @unittest.skipUnless(NCA_REPO, "NCA_REPO not set: live re-hash of the artifacts from the producer's git repo NOT run")
    def test_live_artifacts_still_hash_to_the_recorded_digests_and_a_tampered_blob_does_not(self):
        e = self.records()[("Evidence", f"orx-run-{NCA_RUN}--turing-ddi")]
        n = 0
        for a in e["payload"]["provenance"]["artifacts"]:
            if a.get("locator", "").startswith("git:") and "@" in a["locator"]:
                commit = a["git_commit"]
                b = art.git_blob(NCA_REPO, commit, a["path"])
                self.assertEqual(sha_bytes(b), a["sha256"], a["path"])
                flipped = bytearray(b); flipped[0] ^= 1
                self.assertNotEqual(sha_bytes(bytes(flipped)), a["sha256"])                       # must-fail control
                n += 1
        self.assertGreaterEqual(n, 6)

    @unittest.skipUnless(ORX_STORE, "ORX_STORE not set: live store read NOT run")
    def test_live_store_record_matches_the_committed_facts(self):
        f = oe.read_store_run(store_dir=ORX_STORE, run_id=NCA_RUN)
        e = self.records()[("Evidence", f"orx-run-{NCA_RUN}--turing-ddi")]
        self.assertEqual(f["source_tar_sha256"], e["payload"]["provenance"]["source_tar_sha256"]); self.assertIsNone(f["db_exit_code"])
        self.assertEqual(art.find_abs_paths(f), [])


class NanopubDraft(unittest.TestCase):
    def records(self):
        return load("records.json")

    def test_structure_check_counts_four_graphs_and_catches_a_missing_one(self):
        with open(os.path.join(CHAIN, "claim--turing-ddi.draft.trig")) as fh:
            good = fh.read()
        self.assertTrue(nd.validate_trig(good)["four_graphs"])
        i, j = good.index("sub:provenance {"), good.index("sub:pubinfo {")
        self.assertFalse(nd.validate_trig(good[:i] + good[j:])["four_graphs"])                      # MUST-FAIL control

    def test_refusals(self):
        c = next(r for r in self.records() if r["kind"] == "Claim")
        with self.assertRaises(nd.ExportRefused): nd.record_to_trig({**c, "visibility": "private"})
        leaky = copy.deepcopy(c); leaky["payload"]["source"].update(content_available=True, license=None)
        with self.assertRaises(nd.ExportRefused): nd.record_to_trig(leaky)
        stored = copy.deepcopy(c); stored["payload"]["prior_review"]["delphi_original"]["quote"]["text_stored"] = True
        with self.assertRaises(nd.ExportRefused): nd.record_to_trig(stored)
        badiri = copy.deepcopy(c); badiri["source_uri"] = "https://x.org/a b>"
        with self.assertRaises(nd.ExportRefused): nd.record_to_trig(badiri)
        e = next(r for r in self.records() if r["kind"] == "Evidence")
        dl = copy.deepcopy(e); dl["payload"]["artifacts"][0]["availability"] = "downloadable"
        with self.assertRaises(nd.ExportRefused): nd.record_to_trig(dl, target_claim=c)           # downloadable with no licence
        with self.assertRaises(nd.ExportRefused): nd.record_to_trig(e, target_claim={**c, "version": "b" * 64})
        with self.assertRaises(nd.ExportRefused): nd.refuse_publication()

    def test_drafts_carry_original_delphi_ids_limits_artifacts_and_no_signature(self):
        with open(os.path.join(CHAIN, f"evidence--orx-run-{NCA_RUN}--turing-ddi.draft.trig")) as fh:
            trig = fh.read()
        for needle in ("<https://w3id.org/delphi/resource/claim/turing-ddi>", "UNSIGNED DRAFT", "single-reader, not Codex-reviewed",
                       'de:relation "qualifies"', "de:producedBy", "de:hasArtifact sub:artifact9", "de:linkCheck",
                       "a32c2bf7dd3c10162317974ae6a0ecbefa06c1c180a6886dea1bcb8ea4d4c882"):
            self.assertIn(needle, trig)

    @unittest.skipUnless(rdflib, "rdflib not installed: independent parse NOT run (proposed optional test dependency)")
    def test_independent_rdflib_parse_finds_exactly_four_named_graphs(self):
        for n in sorted(os.listdir(CHAIN)):
            if n.endswith(".draft.trig"):
                ds = rdflib.Dataset(); ds.parse(os.path.join(CHAIN, n), format="trig")
                self.assertEqual(sorted(str(g.identifier).rsplit("/", 1)[-1] for g in ds.graphs() if len(g)), ["Head", "assertion", "provenance", "pubinfo"], n)


if __name__ == "__main__":
    unittest.main()
