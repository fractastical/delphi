"""Tests for frontier_adapters.morpholib.

Run (bounded):  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
                   python3 -m pytest frontier_adapters/tests/test_morpholib.py -q
Unit tests are offline. The rest read a clone of fractastical/morpholib (env MORPHOLIB_REPO, default the reference clone) and are SKIPPED, with the
reason, when it is absent. They build a throwaway git repository from REAL upstream blobs for two models (the audit and manifest JSON are reduced
copies), so every refusal has a must-fail control that edits a copy. Nothing here touches a live store; the PG test needs FRONTIER_TEST_DSN.
"""
import json
import os
import subprocess

import pytest

from frontier_adapters import morpholib as ml
from frontier_adapters.artifacts import find_abs_paths

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.environ.get("MORPHOLIB_REPO", "/data/worktrees/reference/morpholib-20261028")
PIN = "35d30f4cfd5397ee1ed769f96494e018603e293d"
EXAMPLE = os.path.join(ROOT, "frontier_adapters", "examples", "morpholib_import")
TWO = ["gierer-hydra-activator-inhibitor", "odell-apical-constriction-invagination"]   # one with remediation items, one without


def have_pin() -> bool:
    return os.path.isdir(REPO) and subprocess.run(["git", "-C", REPO, "cat-file", "-e", PIN + "^{commit}"], capture_output=True).returncode == 0


needs_pin = pytest.mark.skipif(not have_pin(), reason=f"upstream clone with {PIN[:12]} not found (set MORPHOLIB_REPO)")


# ------------------------------------------------------------------ unit tests, offline
TRIG = '''@prefix this: <https://w3id.org/np/RAexample> .
sub1:assertion {
  <x> pk:hasAssessment <y> .
  <y> a pk:LLMClaimAssessment ;
    rdfs:label "A \\"quoted\\" label" ;
    dcterms:date "2026-10-20"^^xsd:date ;
    dcterms:description "Overall 90.0/100. Dimension assessments: Model fidelity 91. Output judged: docs/media/a.png: rendered output, image/png, 12 B, artifact_sha256 %s (sha256 x). Claim boundary: reported_in_source: P says X | Q says Y; transfer_boundary: calibrated; does_not_claim: Z." ;
    pk:evidenceAgainst "item one, with a comma",
        "item two \\"q\\"" ;
    pk:assessedBy <https://example.org/model/m> ;
    pk:hasScore "0.9"^^xsd:double ;
    pk:hasVerdict "faithful" .
}
sub1:pubinfo { sub1:sig npx:hasSignature "AAA" ; npx:signedBy orcid:0000-0000-0000-0001 . }
''' % ("ab" * 32)


def test_parse_assessment_reads_escapes_lists_and_boundary_sections():
    a = ml.parse_assessment(TRIG)
    assert a["np_uri"] == "https://w3id.org/np/RAexample" and a["label"] == 'A "quoted" label' and a["score"] == "0.9" and a["verdict"] == "faithful"
    assert a["evidence_against"] == ["item one, with a comma", 'item two "q"']                        # a comma inside a literal does not split it
    assert a["output_judged"] == {"path": "docs/media/a.png", "artifact_sha256": "ab" * 32}
    assert a["claim_boundary"] == {"reported_in_source": "P says X | Q says Y", "transfer_boundary": "calibrated", "does_not_claim": "Z."}
    assert a["signature_block_present"] is True and a["signed_by"] == "orcid:0000-0000-0000-0001" and a["dimension_text"] == "Model fidelity 91"
    # control: the same text with the signature block removed must read as unsigned and with no remediation list
    b = ml.parse_assessment(TRIG.replace("npx:hasSignature", "npx:hasNothing").replace("pk:evidenceAgainst", "pk:other"))
    assert b["signature_block_present"] is False and b["evidence_against"] == []


def test_chunks_lose_nothing_and_respect_the_limit():
    s = " | ".join(f"sentence number {i} with some words" for i in range(200))
    parts = ml._chunks(s, 500)
    assert all(len(p) <= 500 for p in parts) and len(parts) > 3
    assert " | ".join(parts).replace("  ", " ") == s or "".join(parts).replace(" ", "").replace("|", "") == s.replace(" ", "").replace("|", "")


def test_audit_versions_orders_by_suffix_and_keeps_both_copies():
    base = "morphoeval/kg/2026-10-19-x-audit"
    tree = [f"{base}{v}/{s}m-overall.trig" for v in ("", "-v3", "-v2") for s in ("", "signed/")] + [f"{base}-v2/signed/other-overall.trig"]
    vs = ml.audit_versions(tree, "m")
    assert [v["version"] for v in vs] == [1, 2, 3] and all({"signed", "unsigned"} <= set(v) for v in vs) and ml.audit_versions(tree, "nope") == []


LEAN = "namespace A\ndef f (x : Int) : Int := x\ntheorem t1 : 1 < 2 := by decide\ntheorem t2 (x : Int) : f x = x := by simp [f]\n-- sorry in a comment\ntheorem t3 : True := by sorry\nend A\n"


def test_lean_flags_are_mechanical_and_never_claim_a_proof():
    f1 = ml._lean_flags(LEAN, "a.lean#L3-L3", {})
    assert f1["only_trivial_tactics"] is True and f1["has_sorry"] is False and f1["compiled_by_frontier"] is False and f1["spec009_anti_triviality_gate_run"] is False
    f2 = ml._lean_flags(LEAN, "a.lean#L4-L4", {})
    assert f2["only_trivial_tactics"] is False and f2["tactics_named_in_range"] == ["simp"]
    assert ml._lean_flags(LEAN, "a.lean#L5-L6", {})["has_sorry"] is True                              # real sorry; the comment on L5 alone is not one
    assert ml._lean_flags(LEAN, "a.lean#L5-L5", {})["has_sorry"] is False
    assert ml._lean_flags(LEAN, "a.lean#L1-L1", {"lean_decl": "X.law1_invariant"})["upstream_template_marker"] is True
    assert ml._lean_flags(LEAN, "a.lean#L1-L1", {"lean_code": ml.TEMPLATE_MARKERS[1]})["upstream_template_marker"] is True
    assert ml._lean_flags(LEAN, "a.lean#L1-L1", {"lean_decl": "X.gm_activator"})["upstream_template_marker"] is False


def test_scales_cover_the_whole_slice_and_use_the_stores_vocabulary():
    from frontier.models import Problem
    allowed = set(Problem.model_fields["scales"].annotation.__args__[0].__args__)
    assert len(ml.SCALES) == 25 and all(v and set(v) <= allowed for v in ml.SCALES.values())


def test_filename_index_keeps_unparsed_names_and_marks_tier():
    audit = {"counted": [{"sim_id": "gierer-hydra"}], "promotable_first_100": [{"sim_id": "b-model"}]}
    tree = ["models/1972-gierer-hydra.py", "models/1900-planformDB_parser.py", "models/2000-x-b-model.py", "models/2001-y-other.py", "models/sub/z.py", "README.md"]
    rows = {r["path"]: r for r in ml.filename_index(tree, audit)}
    assert set(rows) == {"models/1972-gierer-hydra.py", "models/1900-planformDB_parser.py", "models/2000-x-b-model.py", "models/2001-y-other.py"}
    assert rows["models/1972-gierer-hydra.py"]["imported"] and rows["models/1972-gierer-hydra.py"]["audit_tier"] == "A"
    assert rows["models/1900-planformDB_parser.py"]["filename_parse"].startswith("unparsed") and rows["models/1900-planformDB_parser.py"]["year_from_filename"] is None
    assert rows["models/2000-x-b-model.py"]["audit_tier"].startswith("B") and not rows["models/2000-x-b-model.py"]["imported"]
    assert rows["models/2001-y-other.py"]["audit_tier"] == "not itemised by the audit file"


def test_module_never_executes_upstream_or_writes_a_store():
    import ast
    src = open(ml.__file__).read()
    names = {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Name)}
    assert not ({"submit", "import_bundle", "lease", "transition", "review", "exec", "eval", "import_module", "__import__"} & names)
    assert "shell=True" not in src and "rdflib" not in src


# ------------------------------------------------------------------ fixture repo of real blobs
def _git(repo, *args, data=None):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True, input=data, timeout=120,
                          env={**os.environ, "GIT_AUTHOR_DATE": "2026-10-31T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-31T00:00:00Z"}).stdout


def _needed(tree, sims):
    keep = {ml.AUDIT_PATH, "morphoeval/runs/lean_proof_audit.json", "morphoeval/runs/tier_c_deletion_manifest.json"}
    audit = json.loads(ml.git_blob_text(REPO, PIN, ml.AUDIT_PATH))
    for it in audit["counted"]:
        if it["sim_id"] in sims:
            s = it["sim_id"]
            keep |= {f"morphoeval/math_kg_loops/{s}.yaml"} | {t for t in tree if t.startswith(it["dataset_dir"] + "/") or t.endswith(f"-{s}.py") and t.startswith("models/")
                                                              or t.startswith("morphoeval/kg/") and f"/{s}-" in t}
            spec = ml.yaml.safe_load(ml.git_blob_text(REPO, PIN, f"morphoeval/math_kg_loops/{s}.yaml"))
            keep |= {e["lean_locus"].split("#")[0] for e in spec["equations"] if e.get("lean_locus")}
    return sorted(keep & set(tree)), audit


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory):
    if not have_pin():
        pytest.skip("upstream clone not found")
    tree = ml.list_tree(REPO, PIN)
    paths, audit = _needed(tree, TWO)
    d = str(tmp_path_factory.mktemp("morpholib_fixture"))
    _git(d, "init", "-q")
    for p in paths:
        data = ml.git_blob_text(REPO, PIN, p).encode() if p.endswith((".json", ".yaml", ".trig", ".py", ".lean", ".md", ".bib")) else subprocess.check_output(["git", "-C", REPO, "cat-file", "blob", f"{PIN}:{p}"])
        if p == ml.AUDIT_PATH:   # reduced copy: only the two models stay in `counted`
            a = json.loads(data)
            a["counted"] = [x for x in a["counted"] if x["sim_id"] in TWO]
            data = json.dumps(a).encode()
        if p.endswith("tier_c_deletion_manifest.json"):   # reduced copy: the 105k path list is dropped
            m = json.loads(data)
            m.pop("paths", None)
            m.pop("slots", None)
            data = json.dumps(m).encode()
        os.makedirs(os.path.dirname(os.path.join(d, p)) or d, exist_ok=True)
        open(os.path.join(d, p), "wb").write(data)
    _git(d, "add", "-f", "."), _git(d, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "fixture"), _git(d, "tag", "base")
    return d


@pytest.fixture(scope="module")
def built(fixture_repo):
    return ml.build_all(fixture_repo, "HEAD", models=TWO)


def rec(built, rid):
    return next(r for ch in built["chains"] for r in ch.records if r["id"] == rid)


@needs_pin
def test_two_model_slice_has_the_expected_shape_and_counts(built):
    rep = ml.report(built)
    c = rep["counts"]
    assert [r["kind"] for ch in built["chains"] for r in ch.records] == ["Claim", "Evidence", "Problem", "Claim", "Evidence"]
    assert (c["unique_models_imported"], c["claims"], c["claim_versions"], c["evidence"], c["problems"], c["actions"], c["records"]) == (2, 2, 2, 2, 1, 0, 5)
    assert c["equations_as_mathematical_representations"] == 10 and c["equations_compiled_by_frontier"] == 0 and c["equations_l2_or_proof_claimed"] == 0
    assert c["equations_with_upstream_template_marker"] == 0 and c["artifact_bytes_available"] == 0 and c["nanopub_signature_verified"] == 0
    assert c["nanopub_signature_block_present"] == 2 and c["nanopub_published_to_registry_checked"] == 0
    assert c["artifact_references"] == c["artifact_references_referenced"] + c["artifact_references_unavailable"] and c["artifact_references_unavailable"] == 2
    assert all(x["ok"] for x in rep["link_checks"])


@needs_pin
def test_kinds_origin_relation_and_independence_are_conservative(built):
    claim = rec(built, f"morpholib-{TWO[0]}-claim")["payload"]
    ev = rec(built, f"morpholib-{TWO[0]}-evidence-morphoeval")["payload"]
    assert claim["origin"] == "source_statement" and claim["prior_review"] == {"status": "none: not reviewed by anyone"} and "has not checked it against the paper" in claim["statement"]
    assert ev["evidence_kind"] == "source_assessment" and ev["relation"] == "context_only" and ev["produced_by"] is None
    assert ev["source_dependence"]["independent_of_claim"] is False and ev["provider_assessment"]["independent"] is False
    nano = ev["provenance"]["nanopub"]
    assert nano["signature_block_present"] is True and nano["signature_verified"].startswith("unknown") and nano["published_to_registry"].startswith("unknown")
    assert ev["provenance"]["lean"]["compiled_by_frontier"] == 0 and ev["provenance"]["lean"]["l2_claimed"] == 0
    assert "NOT biological validity" in ev["context"] or "not biological validity" in ev["context"].lower()
    assert ev["provenance"]["score_history_0_1"][-1]["version"] == 3 and ev["provider_assessment"]["overall_0_1"] == 0.895


@needs_pin
def test_unavailable_judged_output_is_listed_with_the_stated_digest_and_no_licence(built):
    ev = rec(built, f"morpholib-{TWO[0]}-evidence-morphoeval")["payload"]
    un = [a for a in ev["artifacts"] if a["availability"] == "unavailable"]
    assert len(un) == 1 and un[0]["sha256"] == "e0c4e97130d2627ad31b6cf098d20e0b26bcc7658a7b2fcd94ffe4d9c9d8bc3d" and un[0]["license"] is None and un[0]["byte_size"] == 1290720
    assert "NOT recomputed" in un[0]["title"]
    for a in ev["artifacts"]:
        if a["availability"] == "referenced":
            assert a["uri"] == "urn:sha256:" + a["sha256"]


@needs_pin
def test_a_model_without_remediation_items_gets_no_problem_and_the_index_says_so(built):
    ids = {r["id"] for ch in built["chains"] for r in ch.records}
    assert f"morpholib-{TWO[1]}-problem-remediation" not in ids and f"morpholib-{TWO[0]}-problem-remediation" in ids
    rows = {r["model"]: r for r in built["index"]}
    assert rows[TWO[1]]["remediation_items"] == 0 and rows[TWO[1]]["record_ids"]["problem"] is None and rows[TWO[0]]["remediation_items"] == 7


@needs_pin
def test_problem_quotes_the_assessors_items_in_full_and_stays_recorded(built):
    p = rec(built, f"morpholib-{TWO[0]}-problem-remediation")["payload"]
    assert p["completeness"] == "recorded" and p["acceptance_criteria"] == [] and p["falsifiers"] == [] and p["next_action"] is None
    assert p["known_state"].count("\n- ") == 7 and "remediation needed:" in p["known_state"] and p["problem_kind"] == "project_gap"


@needs_pin
def test_equation_rows_are_mathematical_representations_not_proofs(built):
    rows = built["equations"]
    assert len(rows) == 10 and all(r["kind"] == "mathematical_representation" and "not compiled" in r["proof_status"] for r in rows)
    assert all(r["lean_flags"]["compiled_by_frontier"] is False and r["locator"].startswith("git:morpholib@" + built["commit"]) for r in rows)
    assert sum(r["lean_flags"]["only_trivial_tactics"] for r in rows) == 2      # the two `decide` ranges are flagged, not counted as proof


@needs_pin
def test_no_absolute_paths_and_build_is_deterministic(fixture_repo, built):
    assert find_abs_paths(built["bundles"]) == [] and find_abs_paths(built["index"]) == [] and find_abs_paths(built["equations"]) == []
    again = ml.build_all(fixture_repo, "HEAD", models=TWO)
    assert [b["bundle_sha256"] for b in again["bundles"]] == [b["bundle_sha256"] for b in built["bundles"]]


# ------------------------------------------------------------------ must-fail controls: edit a COPY, expect a refusal that names the check
def _commit_edit(repo, path, fn):
    _git(repo, "reset", "-q", "--hard", "base")      # every mutation starts from the pristine fixture, never from another mutation
    p = os.path.join(repo, path)
    old = open(p, "rb").read()
    new = fn(old)
    assert new != old, "the mutation changed nothing, so the control proves nothing"
    open(p, "wb").write(new)
    _git(repo, "add", "-f", path), _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "mutate " + path)
    open(p, "wb").write(old)
    return _git(repo, "rev-parse", "HEAD").decode().strip()


def _refusal(repo, commit, check_id):
    with pytest.raises(ml.Refused) as e:
        ml.build_all(repo, commit, models=[TWO[0]])
    assert check_id in str(e.value), str(e.value)[:300]


@needs_pin
@pytest.mark.parametrize("path,fn,check_id", [
    ("datasets/hydra_activator_inhibitor/hydra_vulgaris_specimen.jpg", lambda b: b + b"\0", "specimen.hydra_vulgaris_specimen"),
    ("datasets/hydra_activator_inhibitor/paper_citations.bib", lambda b: b + b"\n", "specimen.paper_citations"),
    ("morphoeval/math_kg_loops/gierer-hydra-activator-inhibitor.yaml",
     lambda b: b.replace(b"gm_activator_num_residual\"", b"law1_invariant\"", 1), "lean.no_template"),
    ("morphoeval/math_kg_loops/gierer-hydra-activator-inhibitor.yaml", lambda b: b.replace(b"sim_id: gierer-hydra-activator-inhibitor", b"sim_id: other", 1), "spec.sim_id"),
])
def test_refuses_when_a_stated_hash_or_a_template_marker_or_the_spec_identity_does_not_hold(fixture_repo, path, fn, check_id):
    _refusal(fixture_repo, _commit_edit(fixture_repo, path, fn), check_id)


@needs_pin
def test_refuses_a_model_that_the_audit_does_not_count_as_tier_a(fixture_repo):
    with pytest.raises(ml.Refused) as e:
        ml.build_all(fixture_repo, "HEAD", models=["richman-cortical-gyrification-buckling"])
    assert "not in the audit's Tier A" in str(e.value)


@needs_pin
def test_refuses_when_the_signed_assessment_is_missing(fixture_repo):
    _git(fixture_repo, "reset", "-q", "--hard", "base")
    tree = ml.list_tree(fixture_repo, "HEAD")
    signed = [t for t in tree if "/signed/" in t and t.endswith(f"{TWO[0]}-overall.trig")]
    for t in signed:
        os.remove(os.path.join(fixture_repo, t))
    _git(fixture_repo, "add", "-A"), _git(fixture_repo, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "drop signed")
    try:
        _refusal(fixture_repo, "HEAD", "audit.has_signed_copy")
    finally:
        _git(fixture_repo, "reset", "-q", "--hard", "base")


@needs_pin
def test_a_dangling_pointer_fails_the_link_checks(built):
    recs = [json.loads(json.dumps(r)) for ch in built["chains"] for r in ch.records]
    ev = next(r for r in recs if r["kind"] == "Evidence")
    ev["payload"]["target"]["version"] = "0" * 64
    bad = [x for x in ml.link_checks(recs) if not x["ok"]]
    assert bad and bad[0]["id"].endswith(".target")


# ------------------------------------------------------------------ the committed freeze
def test_committed_freeze_is_the_full_tier_a_slice_pinned_to_an_upstream_commit():
    rep = json.load(open(os.path.join(EXAMPLE, "chain.json")))
    c = rep["counts"]
    assert rep["source"]["commit"] == PIN and c["unique_models_imported"] == 25 and c["claims"] == 25 and c["evidence"] == 25 and c["records"] == c["claims"] + c["evidence"] + c["problems"]
    assert c["equations_with_upstream_template_marker"] == 0 and c["equations_compiled_by_frontier"] == 0 and c["nanopub_signature_verified"] == 0
    assert all(x["ok"] for x in rep["link_checks"]) and len(c["organisms_explicit_in_audit"]) == 17
    man = json.load(open(os.path.join(EXAMPLE, "manifest.json")))
    import hashlib
    for name, sha in man["file_sha256"].items():
        assert hashlib.sha256(open(os.path.join(EXAMPLE, name), "rb").read()).hexdigest() == sha, name


@needs_pin
def test_committed_freeze_is_reproduced_from_the_pinned_upstream_commit(tmp_path):
    out = ml.build_all(REPO, PIN)
    ml.write_frozen(str(tmp_path), out)
    for name in os.listdir(EXAMPLE):
        assert open(os.path.join(tmp_path, name), "rb").read() == open(os.path.join(EXAMPLE, name), "rb").read(), name


# ------------------------------------------------------------------ the frozen bundle imports into a THROWAWAY store
@pytest.fixture
def pgstore():
    dsn = os.environ.get("FRONTIER_TEST_DSN")
    if not dsn:
        pytest.skip("run through scripts/test_postgres.sh (own ephemeral cluster; never the live service)")
    from uuid import uuid4
    from frontier.store import Store
    st = Store(dsn, "node-z", "test_" + uuid4().hex)
    st.initialize()
    st.provision("test-only-local-token-for-alice", "alice", "operator-a", ["contributor", "coordinator"], ["node-z", "node-a"], 1000)
    return st


def test_frozen_bundle_imports_into_an_ephemeral_store_unreviewed(pgstore):
    b = json.load(open(os.path.join(EXAMPLE, "bundle-001.frontier-bundle-0.1.json")))
    out = pgstore.import_bundle("test-only-local-token-for-alice", "morpholib-import", b)
    assert len(out["inserted"]) == len(b["records"]) and out["forks"] == []
