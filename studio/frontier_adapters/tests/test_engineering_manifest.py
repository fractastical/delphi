"""Tests for frontier_adapters.engineering_manifest.

Run (bounded):  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
                   python3 -m pytest frontier_adapters/tests/test_engineering_manifest.py -q
The PG test needs scripts/test_postgres.sh (its own ephemeral cluster) and is SKIPPED, with that reason, otherwise. Nothing here touches a live store.
Every refusal has a must-fail control built by editing a COPY of the producer files in a throwaway git repository.
"""
import ast
import json
import os
import subprocess

import pytest

from frontier_adapters import engineering_manifest as em
from frontier_adapters.artifacts import find_abs_paths

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMMIT = "a48399f60f770c0e88cf3aaf1e7e239ca1055619"          # the root integrated tip the producer receipts were read from
EXAMPLE = os.path.join(ROOT, "frontier_adapters", "examples", "engineering_manifest")


def have_commit() -> bool:
    return subprocess.run(["git", "-C", ROOT, "cat-file", "-e", COMMIT + "^{commit}"], capture_output=True).returncode == 0


needs_commit = pytest.mark.skipif(not have_commit(), reason=f"source commit {COMMIT[:12]} not present in this checkout")


@pytest.fixture(scope="module")
def chains():
    if not have_commit():
        pytest.skip("source commit not present")
    return em.build_first_slice(ROOT, COMMIT)


def rec(chains, rid):
    return next(r for ch in chains for r in ch.records if r["id"] == rid)


def ref(r):
    return {k: r[k] for k in ("namespace", "kind", "id", "version")}


# ------------------------------------------------------------------ the bundle
@needs_commit
def test_first_slice_is_valid_small_and_ordered(chains):
    fin, formal = chains
    assert [r["kind"] for r in fin.records] == ["Claim", "Action", "Evidence", "Action", "Evidence", "Problem"]
    assert [r["kind"] for r in formal.records] == ["Claim", "Action", "Evidence"]
    assert len(fin.records) + len(formal.records) == 9 <= em.MAX_RECORDS
    assert all(r["namespace"] == "node-a" and r["visibility"] == "public" and r["predecessor"] is None for ch in chains for r in ch.records)


@needs_commit
def test_build_is_deterministic_and_the_committed_bundle_is_reproduced(chains):
    again = em.build_first_slice(ROOT, COMMIT)
    assert [r["version"] for ch in chains for r in ch.records] == [r["version"] for ch in again for r in ch.records]
    b1, b2 = em.build_bundle(chains), em.build_bundle(again)
    assert b1 == b2 and b1["schema_version"] == "frontier-bundle-0.1" and b1["review_claims"] == []
    from frontier.models import digest
    assert digest({k: v for k, v in b1.items() if k != "bundle_sha256"}) == b1["bundle_sha256"]
    path = os.path.join(EXAMPLE, "bundle.frontier-bundle-0.1.json")
    if os.path.exists(path):
        assert json.load(open(path)) == b1                              # the frozen file is exactly what the code rebuilds from the pinned commit


@needs_commit
def test_every_pointer_resolves_by_exact_version_inside_the_bundle(chains):
    fin = chains[0]
    claim, a_sim, e_sim = (rec([fin], i) for i in ("eng-finmech-claim-ei-crit", "eng-finmech-action-sim", "eng-finmech-evidence-sim"))
    a_ren, e_ren, prob = (rec([fin], i) for i in ("eng-finmech-action-render", "eng-finmech-evidence-render", "eng-finmech-problem-ei-measurement"))
    assert a_sim["payload"]["target"] == ref(claim) and e_sim["payload"]["target"] == ref(claim) and e_sim["payload"]["produced_by"] == ref(a_sim)
    assert a_ren["payload"]["inputs"] == [ref(e_sim)]                                 # render consumed the simulation Evidence: exact version, not an id
    assert e_ren["payload"]["produced_by"] == ref(a_ren) and e_ren["payload"]["target"] == ref(claim)
    assert prob["payload"]["dependencies"] == [ref(claim)]
    checks = em.link_checks([r for ch in chains for r in ch.records])
    assert checks and all(c["ok"] for c in checks)


@needs_commit
def test_simulation_and_render_are_separate_actions_and_say_why(chains):
    fin = chains[0]
    a_sim, a_ren = rec([fin], "eng-finmech-action-sim"), rec([fin], "eng-finmech-action-render")
    e_sim, e_ren = rec([fin], "eng-finmech-evidence-sim"), rec([fin], "eng-finmech-evidence-render")
    assert a_sim["id"] != a_ren["id"] and a_sim["version"] != a_ren["version"]
    code_sim = {a["title"] for a in e_sim["payload"]["artifacts"] if a["role"] == "code"}
    code_ren = {a["title"] for a in e_ren["payload"]["artifacts"] if a["role"] == "code"}
    assert not any("render.py" in t for t in code_sim) and any("render.py" in t for t in code_ren)
    assert not any("result.json" in a["title"] and a["role"] == "output" for a in e_ren["payload"]["artifacts"])
    assert "creation time and order relative to the simulation are NOT recorded" in a_ren["payload"]["cache_key"]["scope"]
    assert "records no creation time" in e_ren["payload"]["provenance"]["ordering_note"]
    assert e_sim["payload"]["created_time"] == {"value": None, "basis": "unknown"} == e_ren["payload"]["created_time"]
    for a in (a_sim, a_ren):
        assert "NOT executed by Frontier" in a["payload"]["title"]


@needs_commit
def test_hashes_come_from_the_producer_and_match_the_blobs(chains):
    fin = chains[0]
    a_sim, e_ren = rec([fin], "eng-finmech-action-sim"), rec([fin], "eng-finmech-evidence-render")
    ck = a_sim["payload"]["cache_key"]
    assert "16c006be07a266f45385507a74a9d5cc37991f58617ddc6c10aaa3b807c481c5" in ck["code"]                # manifest code_sha256
    assert "943b8f645a068e76f168bd99933f09210eedd49cf2a3ec1cb0eba547df7381d4" in ck["input"]               # request file sha256
    assert "NOT RECORDED" in ck["environment"]
    shas = {a["sha256"]: a for a in e_ren["payload"]["artifacts"]}
    assert "f4080da6514b6e7a374927f7e40ac6ccff7ae33d62fe2ecd96318a2fb7c7ac17" in shas                         # mp4 per the producer's manifest
    assert "df0e4804e57cda604ac66f8bb49681a9105b930dd1a078d15ce505209030cf95" in shas                         # poster
    assert e_ren["payload"]["provenance"]["frames_invalid"] == 179 and e_ren["payload"]["provenance"]["frames_valid"] == 181
    assert any("179 of 360 frames" in x for x in e_ren["payload"]["limitations"])
    names = [c["id"] for ch in chains for c in ch.checks if c["ok"]]
    assert {"output.mp4", "output.result_json", "code.beam.py", "code.combined", "input.request_file"} <= set(names)


@needs_commit
def test_kinds_relations_origin_and_limits_are_conservative(chains):
    fin, formal = chains
    kinds = {r["id"]: (r["payload"].get("evidence_kind"), r["payload"].get("relation")) for ch in chains for r in ch.records if r["kind"] == "Evidence"}
    assert kinds == {"eng-finmech-evidence-sim": ("simulated", "unspecified"), "eng-finmech-evidence-render": ("simulated", "context_only"),
                     "eng-formal-evidence-lean-check": ("formal", "supports")}
    claims = [r for ch in chains for r in ch.records if r["kind"] == "Claim"]
    assert {c["payload"]["origin"] for c in claims} == {"derived"} and all(c["payload"]["prior_review"]["status"].startswith("none") for c in claims)
    c_fin = rec([fin], "eng-finmech-claim-ei-crit")
    assert "1323/2048000" in c_fin["payload"]["statement"]
    lim = " | ".join(c_fin["payload"]["limitations"])
    assert "DECLARED ILLUSTRATION" in lim and "not a design claim" in lim and "ASSUMED log-spaced range" in lim and "biological feasibility of any fin" in lim
    assert "not independent evidence" in lim
    p = rec([fin], "eng-finmech-problem-ei-measurement")["payload"]
    assert p["completeness"] == "recorded" and p["acceptance_criteria"] == [] and p["falsifiers"] == [] and p["approach"] == "measurement"
    e_f = rec([formal], "eng-formal-evidence-lean-check")["payload"]
    flim = " | ".join(e_f["limitations"])
    assert "not organism feasibility" in flim and "level-flight proxy" in flim and "re-checked by z3 only" in flim and "faithful reading" in flim
    assert e_f["source_dependence"]["independent_of_claim"] is False


@needs_commit
def test_formal_chain_reports_the_kernel_facts_the_receipt_states(chains):
    e = rec([chains[1]], "eng-formal-evidence-lean-check")["payload"]
    pv = e["provenance"]
    assert pv["positive"]["exit"] == 0 and pv["positive"]["axioms_used"] == ["Classical.choice", "Quot.sound", "propext"]
    assert pv["negative"]["each_block_rejected"] == {"wl_k2": True, "mass_exponent": True, "stall_k2": True, "corrupted_certificate": True}
    assert pv["solver"]["status"] == "unsat" and pv["solver"]["conflict_core"] == ["level_lift_proxy", "q_wl_min", "q_speed_max"]
    assert pv["solver"]["verdict_checked_by"].startswith("z3 only")
    a = rec([chains[1]], "eng-formal-action-lean-check")["payload"]
    assert "c91ece6845e3149d079098ccc6d7d5efa2a05d12af667804b2542ed20a9627ad" in a["cache_key"]["input"]
    assert "NOT executed by Frontier" in a["title"] and a["inputs"] == []
    roles = sorted(x["role"] for x in e["artifacts"])
    assert roles.count("certificate") == 1 and roles.count("code") == 5


@needs_commit
def test_artifacts_are_referenced_only_with_no_url_no_licence_no_local_path(chains):
    records = [r for ch in chains for r in ch.records]
    arts = [a for r in records for a in r["payload"].get("artifacts", [])]
    assert len(arts) == 16          # sim: result + request + 4 code; render: mp4 + poster + render.py + manifest; formal: receipt + 5 code
    for a in arts:
        assert a["availability"] == "referenced" and a["uri"] == "urn:sha256:" + a["sha256"] and a["license"] is None and "https://" not in a["uri"]
    for r in records:
        src = r["payload"].get("source")
        if src:
            assert src["uri"] is None and src["content_available"] is False and src["license"] is None
    assert find_abs_paths(records) == [] and "/data/" not in json.dumps(records) and "mathlib-probe" not in json.dumps(records)


def test_module_never_writes_to_a_store():
    tree = ast.parse(open(em.__file__).read())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and (m.startswith("psycopg") or m == "frontier.store" or m.startswith("urllib") or m.startswith("requests") or m == "socket") for m in imported)
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not ({"submit", "import_bundle", "lease", "transition", "review"} & called)


# ------------------------------------------------------------------ must-fail controls on a throwaway copy of the producer files
def _git(d, *a):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, env=env, check=True).stdout.strip()


@pytest.fixture
def mutate(tmp_path):
    if not have_commit():
        pytest.skip("source commit not present")
    d = str(tmp_path)
    subprocess.run(f"git -C {ROOT} archive {COMMIT} engineering | tar -x -C {d}", shell=True, check=True)
    _git(d, "init", "-q"); _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "base")

    def go(fn):
        fn(d)
        _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "mutated")
        return d, _git(d, "rev-parse", "HEAD")
    return go


def edit_json(path, fn):
    d = json.load(open(path)); fn(d); json.dump(d, open(path, "w"))


def append_byte(path):
    open(path, "ab").write(b" ")


FIN, FORMAL = "engineering/fin_mechanics", "engineering/formal"


@pytest.mark.parametrize("name,fn,failed_check", [
    ("result.json altered", lambda d: append_byte(f"{d}/{FIN}/artifacts/result.json"), "output.result_json"),
    ("video altered", lambda d: append_byte(f"{d}/{FIN}/artifacts/fin_mechanics.mp4"), "output.mp4"),
    ("poster altered", lambda d: append_byte(f"{d}/{FIN}/artifacts/poster.png"), "output.poster"),
    ("code file altered", lambda d: append_byte(f"{d}/{FIN}/beam.py"), "code.beam.py"),
    ("request altered", lambda d: append_byte(f"{d}/{FIN}/example_request.json"), "input.request_file"),
    ("combined code hash altered", lambda d: edit_json(f"{d}/{FIN}/artifacts/manifest.json", lambda m: m.update(code_sha256="0" * 64)), "code.combined"),
    ("manifest says a different kind", lambda d: edit_json(f"{d}/{FIN}/artifacts/manifest.json", lambda m: m.update(evidence_kind="observed")), "manifest.evidence_kind"),
])
def test_fin_chain_refuses_when_a_producer_hash_or_label_does_not_hold(mutate, name, fn, failed_check):
    d, rev = mutate(fn)
    with pytest.raises(em.Refused) as e:
        em.fin_mechanics_chain(d, rev)
    assert failed_check in str(e.value), (name, str(e.value))


@pytest.mark.parametrize("name,fn,failed_check", [
    ("solver says sat", lambda r: r["solver_result"].update(status="sat"), "solver.unsat"),
    ("core not minimal", lambda r: r["solver_result"].update(core_minimal=False), "solver.core_minimal"),
    ("lean did not run", lambda r: r["lean_checks"].update(lean="not_run"), "lean.ran"),
    ("positive failed", lambda r: r["lean_checks"]["positive"].update(exit=1), "lean.positive.exit0"),
    ("non-standard axiom", lambda r: r["lean_checks"]["positive"].update(axioms_used=["Classical.choice", "sorryAx"]), "lean.positive.axioms"),
    ("a negative control accepted", lambda r: r["lean_checks"]["negative"]["each_block_rejected"].update(wl_k2=False), "lean.negative.all_rejected"),
    ("certificate text changed", lambda r: r.update(lean_certificate_text=r["lean_certificate_text"] + " "), "certificate.text_hash"),
])
def test_formal_chain_refuses_when_the_receipt_does_not_hold(mutate, name, fn, failed_check):
    d, rev = mutate(lambda d: edit_json(f"{d}/{FORMAL}/RECEIPT.json", fn))
    with pytest.raises(em.Refused) as e:
        em.formal_certificate_chain(d, rev)
    assert failed_check in str(e.value), (name, str(e.value))


def test_formal_chain_refuses_when_a_hashed_lean_file_changed(mutate):
    d, rev = mutate(lambda d: append_byte(f"{d}/{FORMAL}/GeometricSimilarity.lean"))
    with pytest.raises(em.Refused) as e:
        em.formal_certificate_chain(d, rev)
    assert "file.GeometricSimilarity.lean" in str(e.value)


@needs_commit
def test_missing_commit_missing_file_and_record_limit_are_refused(chains, monkeypatch, mutate):
    with pytest.raises(em.Refused):
        em.resolve_commit(ROOT, "0" * 40)
    d, rev = mutate(lambda d: os.remove(f"{d}/{FORMAL}/RECEIPT.json"))
    with pytest.raises(em.Refused, match="not in the pinned commit"):
        em.formal_certificate_chain(d, rev)
    monkeypatch.setattr(em, "MAX_RECORDS", 5)
    with pytest.raises(em.Refused, match="more than 5 records"):
        em.fin_mechanics_chain(ROOT, COMMIT)
    monkeypatch.setattr(em, "MAX_RECORDS", 8)
    with pytest.raises(em.Refused, match="first-slice limit"):
        em.build_bundle(chains)


@needs_commit
def test_a_dangling_pointer_or_a_downloadable_artifact_fails_the_link_checks(chains):
    recs = json.loads(json.dumps([r for ch in chains for r in ch.records]))
    ev = next(r for r in recs if r["id"] == "eng-finmech-evidence-sim")
    ev["payload"]["produced_by"]["version"] = "f" * 64
    assert any(not c["ok"] for c in em.link_checks(recs))
    recs2 = json.loads(json.dumps([r for ch in chains for r in ch.records]))
    next(r for r in recs2 if r["id"] == "eng-formal-evidence-lean-check")["payload"]["artifacts"][0]["availability"] = "downloadable"
    assert any(not c["ok"] and "artifact" in c["id"] for c in em.link_checks(recs2))


@needs_commit
def test_link_checks_name_the_exact_failing_pointer_and_catch_a_wrong_but_existing_action(chains):
    base = [r for ch in chains for r in ch.records]
    # (a) a pure dangling pointer: the render Action's input points at a version that is not in the bundle
    recs = json.loads(json.dumps(base))
    next(r for r in recs if r["id"] == "eng-finmech-action-render")["payload"]["inputs"][0]["version"] = "e" * 64
    failed = {c["id"] for c in em.link_checks(recs) if not c["ok"]}
    assert failed == {"eng-finmech-action-render.inputs"}
    # (b) every pointer resolves, but the Evidence says it was produced by an Action aimed at a DIFFERENT Claim
    recs = json.loads(json.dumps(base))
    lean_action = next(r for r in recs if r["id"] == "eng-formal-action-lean-check")
    next(r for r in recs if r["id"] == "eng-finmech-evidence-sim")["payload"]["produced_by"] = {k: lean_action[k] for k in ("namespace", "kind", "id", "version")}
    failed = {c["id"] for c in em.link_checks(recs) if not c["ok"]}
    assert failed == {"eng-finmech-evidence-sim.produced_by_same_target"}


def test_cache_key_dimensions_are_bounded_to_what_the_store_accepts():
    ck = em._cache_key("a" * 64, input="x" * 1500, code="c", model="m", environment="e", parameters="p", scope="s")
    assert len(ck["input"]) == 1000 and ck["input"].endswith("...") and set(ck) == {"target", "input", "code", "model", "environment", "parameters", "scope", "acceptance_policy"}


# ------------------------------------------------------------------ the frozen bundle imports into a THROWAWAY store and becomes searchable
@pytest.fixture
def pgstore():
    dsn = os.environ.get("FRONTIER_TEST_DSN")
    if not dsn:
        pytest.skip("run through scripts/test_postgres.sh (own ephemeral cluster; never the live service)")
    from uuid import uuid4
    from frontier.store import Store
    st = Store(dsn, "node-z", "test_" + uuid4().hex)       # a receiving node that is NOT the bundle's namespace, like the live importer
    st.initialize()
    st.provision("test-only-local-token-for-alice", "alice", "operator-a", ["contributor", "coordinator"], ["node-z", "node-a"], 1000)
    return st


@needs_commit
def test_frozen_bundle_imports_into_an_ephemeral_store_and_proofs_and_models_are_searchable(chains, pgstore):
    from frontier.artifacts import ArtifactIndex
    TOKENS = {"alice": "test-only-local-token-for-alice"}
    bundle = em.build_bundle(chains)
    out = pgstore.import_bundle(TOKENS["alice"], "eng-import", bundle)
    assert len(out["inserted"]) == 9 and out["forks"] == []
    idx = ArtifactIndex(pgstore)
    cert = idx.search("", role="certificate")["items"]
    assert [i["evidence_kind"] for i in cert] == ["formal"] and cert[0]["artifact"]["availability"] == "referenced" and cert[0]["artifact_bytes_verified"] is False
    outs = idx.search("", role="output")["items"]
    assert sorted(i["artifact"]["title"].split(":")[1].split("[")[0].strip() for i in outs) == [
        "engineering/fin_mechanics/artifacts/fin_mechanics.mp4", "engineering/fin_mechanics/artifacts/poster.png", "engineering/fin_mechanics/artifacts/result.json"]
    assert [i["evidence_kind"] for i in idx.search("fin_mechanics.mp4")["items"]] == ["simulated"]
    assert all(i["local_status"] == "imported_unreviewed" for i in cert + outs)               # imported, never accepted, never "executed here"
