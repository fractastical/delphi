"""Tests for frontier_adapters.run_bundles (fish3d, scales, behavior, lifecycle).

Run (bounded):  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
                   python3 -m pytest frontier_adapters/tests/test_run_bundles.py -q
The PG test needs scripts/test_postgres.sh (its own ephemeral cluster) and is SKIPPED, with that reason, otherwise. Nothing here touches a live store.
Every refusal has a must-fail control built by editing a COPY of the producer files in a throwaway git repository, and the unedited copy is the
positive control (it must build), so a refusal cannot come from the copy itself.
"""
import json
import os
import subprocess

import pytest

from frontier_adapters import engineering_manifest as em
from frontier_adapters import run_bundles as rb
from frontier_adapters.artifacts import find_abs_paths

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMMIT = "10cde736c0d15971b97c35692b0de8ddeea2299b"          # the root tip the producer files were read from
EXAMPLE = os.path.join(ROOT, "frontier_adapters", "examples", "run_bundles")
COMMIT_BETSE = "b53e0cd5399f6d7a6657b86f33052cb1ffda00b5"      # root tip that integrated BETSE (4daceb5) and the earlier producers
EXAMPLE_BETSE = os.path.join(ROOT, "frontier_adapters", "examples", "run_bundles_betse")
BETSE_PATHS = ["artifacts/bioelectric-tissue", "engineering/bioelectric_tissue", "tests/test_bioelectric_tissue.py"]
PRODUCER_PATHS = ["artifacts/fish3d", "artifacts/scales", "artifacts/behavior", "data/fish-lifecycle", "engineering/fish3d", "engineering/geometry",
                  "engineering/scales", "engineering/behavior", "engineering/lifecycle", "docs/fish-lifecycle.md"]


def have_commit() -> bool:
    return subprocess.run(["git", "-C", ROOT, "cat-file", "-e", COMMIT + "^{commit}"], capture_output=True).returncode == 0


needs_commit = pytest.mark.skipif(not have_commit(), reason=f"source commit {COMMIT[:12]} not present in this checkout")
needs_betse = pytest.mark.skipif(subprocess.run(["git", "-C", ROOT, "cat-file", "-e", COMMIT_BETSE + "^{commit}"], capture_output=True).returncode != 0,
                                 reason=f"BETSE source commit {COMMIT_BETSE[:12]} not present in this checkout")


@pytest.fixture(scope="module")
def chains():
    if not have_commit():
        pytest.skip("source commit not present")
    return [fn(ROOT, COMMIT) for fn in rb.CHAINS.values()]


def by_name(chains, name):
    return next(c for c in chains if c.name == name)


def rec(chains, rid):
    return next(r for ch in chains for r in ch.records if r["id"] == rid)


# ------------------------------------------------------------------ shape
@needs_commit
def test_counts_kinds_and_no_invented_kinds(chains):
    got = {c.name: {k: sum(1 for r in c.records if r["kind"] == k) for k in ("Claim", "Action", "Evidence")} for c in chains}
    assert got == {"fish3d": {"Claim": 1, "Action": 2, "Evidence": 2}, "scales": {"Claim": 2, "Action": 3, "Evidence": 3},
                   "behavior": {"Claim": 2, "Action": 6, "Evidence": 6}, "lifecycle": {"Claim": 2, "Action": 0, "Evidence": 2}}
    assert {r["kind"] for c in chains for r in c.records} == {"Claim", "Action", "Evidence"}      # no Equation / Model kind
    assert all(r["namespace"] == "node-a" and r["visibility"] == "public" and r["predecessor"] is None for c in chains for r in c.records)


@needs_commit
def test_compute_and_render_are_separate_actions_and_render_is_never_support(chains):
    for c in chains:
        for r in c.records:
            if r["kind"] != "Evidence":
                continue
            p = r["payload"]
            if r["id"].endswith("-render"):
                assert p["relation"] == "context_only" and p["evidence_kind"] == "simulated"
                act = next(a for a in c.records if a["kind"] == "Action" and a["version"] == p["produced_by"]["version"])
                assert act["id"].endswith("-action-render") and act["payload"]["inputs"], "render Action must pin the computed Evidence it draws"
            else:
                assert p["relation"] in {"unspecified", "context_only"} and p["relation"] != "supports"


@needs_commit
def test_lifecycle_is_a_source_assessment_with_no_simulator_action(chains):
    lc = by_name(chains, "lifecycle")
    evs = [r for r in lc.records if r["kind"] == "Evidence"]
    assert [e["payload"]["evidence_kind"] for e in evs] == ["source_assessment", "predicted"]
    assert all(e["payload"]["produced_by"] is None for e in evs) and not [r for r in lc.records if r["kind"] == "Action"]
    assert "no simulator" in evs[0]["payload"]["context"].lower() or "no simulator action" in evs[0]["payload"]["context"].lower()


@needs_commit
def test_every_action_says_what_its_receipt_does_and_does_not_record(chains):
    for c in chains:
        for a in (r for r in c.records if r["kind"] == "Action"):
            t = a["payload"]["title"]
            assert "NOT executed by Frontier" in t or "not re-run by Frontier" in t, a["id"]
    assert "NO exit code" in rec(chains, "run-fish3d-action-build")["payload"]["title"]
    assert "NO exit code" in rec(chains, "run-scales-action-sim")["payload"]["title"]
    assert "exit status 0" in rec(chains, "run-behavior-action-sim-baseline")["payload"]["title"]


# ------------------------------------------------------------------ honesty: what must stay visible
@needs_commit
def test_the_scale_models_miss_and_the_failed_control_are_in_the_record(chains):
    cl = rec(chains, "run-scales-claim-measured-comparison")["payload"]
    assert "rise_10_90_h: simulated 1.16 vs band 1.5-6.0 (OUT of band)" in cl["statement"]
    assert "reproduces_measured_impairment is False" in cl["statement"]
    assert any("rise_10_90_h" in x for x in cl["limitations"])
    assert "ASSUMED" in " ".join(rec(chains, "run-scales-claim-erk-wave-growth")["payload"]["assumptions"])


@needs_commit
def test_the_behavior_render_hash_drift_is_recorded_not_hidden(chains):
    lim = " ".join(rec(chains, "run-behavior-claim-cpg-baseline")["payload"]["limitations"])
    assert "Provenance wrinkle" in lim and "e44442685e86" in lim and "e61fb3b98044406f" in lim and "simulation is unaffected" in lim


@needs_commit
def test_nothing_claims_a_calibrated_fish(chains):
    for c in chains:
        for r in c.records:
            if r["kind"] in ("Claim", "Evidence"):
                text = json.dumps(r["payload"]["limitations"])
                assert "Not calibrated to any fish" in text or "Danio rerio" in text or "not a flying fish" in text, r["id"]


@needs_commit
def test_behavior_open_problems_are_carried_in_the_report_not_invented_as_records(chains):
    assert [p["id"] for p in by_name(chains, "behavior").open_problems] == ["behavior-target-cpg-calibration", "behavior-neuromuscular-transfer",
                                                                            "behavior-moving-fluid-bridge", "behavior-genotype-to-circuit"]
    assert not [r for c in chains for r in c.records if r["kind"] == "Problem"]


# ------------------------------------------------------------------ bundle, links, artifacts
@needs_commit
def test_build_is_deterministic_and_the_committed_bundles_are_reproduced(chains, tmp_path):
    again = [fn(ROOT, COMMIT) for fn in rb.CHAINS.values()]
    assert [r["version"] for c in chains for r in c.records] == [r["version"] for c in again for r in c.records]
    rb.write_frozen(str(tmp_path), chains)
    frozen = sorted(n for n in os.listdir(EXAMPLE) if n != "README.md")          # README.md is hand-written, not generated
    for n in frozen:
        assert open(os.path.join(EXAMPLE, n), "rb").read() == open(tmp_path / n, "rb").read(), f"{n} differs from a fresh build; refreeze with --source-commit {COMMIT[:12]}"
    assert frozen == sorted(os.listdir(tmp_path))


@needs_commit
def test_every_pointer_resolves_by_exact_version_inside_each_bundle(chains):
    for c in chains:
        bundle = em.build_bundle([c], limit=rb.AssetChain.max_records)
        assert bundle["schema_version"] == "frontier-bundle-0.1" and bundle["review_claims"] == []
        checks = em.link_checks(bundle["records"])
        assert checks and all(x["ok"] for x in checks), [x for x in checks if not x["ok"]][:3]
        for e in (r for r in bundle["records"] if r["kind"] == "Evidence"):
            act = next((a for a in bundle["records"] if a["version"] == (e["payload"]["produced_by"] or {}).get("version")), None)
            if act:
                assert act["payload"]["target"]["version"] == e["payload"]["target"]["version"]


@needs_commit
def test_artifacts_are_referenced_only_with_no_url_no_licence_no_local_path(chains):
    n = 0
    for c in chains:
        assert find_abs_paths(c.records) == []
        for r in c.records:
            for a in r["payload"].get("artifacts", []):
                n += 1
                assert a["uri"] == "urn:sha256:" + a["sha256"] and a["availability"] == "referenced" and a["license"] is None
    assert n > 40


@needs_commit
def test_media_types_are_typed_not_octet_stream(chains):
    types = {a["media_type"] for c in chains for r in c.records for a in r["payload"].get("artifacts", [])}
    assert {"video/mp4", "image/png", "model/gltf-binary", "model/stl", "application/x-npz", "image/gif"} <= types


def test_secret_guard_flags_presigned_urls_and_secret_fields_and_passes_clean_text():
    for bad in ("https://h/p?X-Amz-Signature=abc", "https://h/p?x=1", '{"api_key": "x"}', "Authorization: Bearer abc", "sk-" + "a" * 20):
        assert rb.find_secretish(bad), bad                                  # positive controls: each must be flagged
    assert rb.find_secretish("git:delphi-frontier@10cde736:artifacts/scales/erk-wave/receipt.json urn:sha256:" + "0" * 64) == []


@needs_commit
def test_frozen_outputs_contain_no_secret_like_text():
    assert {n: rb.find_secretish(open(os.path.join(EXAMPLE, n)).read()) for n in os.listdir(EXAMPLE)} == {n: [] for n in os.listdir(EXAMPLE)}


@needs_commit
def test_module_never_writes_to_a_store():
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "frontier_adapters", "run_bundles.py")).read())
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
    subprocess.run(f"git -C {ROOT} archive {COMMIT} {' '.join(PRODUCER_PATHS)} | tar -x -C {d}", shell=True, check=True)
    _git(d, "init", "-q"); _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "base")
    base = _git(d, "rev-parse", "HEAD")

    def go(fn=None):
        if fn is None:
            return d, base
        fn(d)
        _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "mutated")
        return d, _git(d, "rev-parse", "HEAD")
    return go


def edit_json(path, fn):
    d = json.load(open(path)); fn(d); json.dump(d, open(path, "w"))


def append_byte(path):
    open(path, "ab").write(b" ")


F3, SC, BH, LC = "artifacts/fish3d/fish3d-N1-cypselurus-baseline", "artifacts/scales/erk-wave", "artifacts/behavior", "data/fish-lifecycle"


@needs_commit
@pytest.mark.parametrize("name", sorted(rb.CHAINS))
def test_positive_control_the_unedited_copy_builds(mutate, name):
    d, commit = mutate()
    assert len(rb.CHAINS[name](d, commit).records) > 0


@needs_commit
@pytest.mark.parametrize("chain,fn,failed_check", [
    ("fish3d", lambda d: append_byte(f"{d}/{F3}/components/body.stl"), "file.components/body.stl"),
    ("fish3d", lambda d: append_byte(f"{d}/{F3}/candidate.json"), "candidate"),
    ("fish3d", lambda d: append_byte(f"{d}/engineering/fish3d/build.py"), "code.build_hash"),
    ("fish3d", lambda d: append_byte(f"{d}/engineering/geometry/mesh.py"), "code.build_hash"),
    ("fish3d", lambda d: append_byte(f"{d}/engineering/fish3d/blender_render.py"), "code.build_hash"),     # the build hash covers every *.py in the directory
    ("fish3d", lambda d: edit_json(f"{d}/{F3}/render/render.json", lambda m: m.update(present_code_sha256="0" * 64)), "code.present"),
    ("fish3d", lambda d: append_byte(f"{d}/{F3}/render/turntable.mp4"), "render.video"),
    ("fish3d", lambda d: edit_json(f"{d}/{F3}/render/render.json", lambda m: m.update(glb_sha256="0" * 64)), "render.same_candidate"),
    ("fish3d", lambda d: edit_json(f"{d}/{F3}/build.json", lambda m: m.update(all_closed=False)), "build.schema"),
    ("scales", lambda d: append_byte(f"{d}/{SC}/states.npz"), "file.states.npz"),
    ("scales", lambda d: append_byte(f"{d}/engineering/scales/run.py"), "code.hash"),
    ("scales", lambda d: edit_json(f"{d}/{SC}/receipt.json", lambda m: m.update(controls_pass=False)), "receipt.schema"),
    ("scales", lambda d: edit_json(f"{d}/{SC}/receipt.json", lambda m: m.update(measured_comparison_misses=[])), "misses.consistent"),
    ("behavior", lambda d: append_byte(f"{d}/{BH}/baseline.json"), "file.baseline.json"),
    ("behavior", lambda d: append_byte(f"{d}/engineering/behavior/model.py"), "code.model.py"),
    ("behavior", lambda d: edit_json(f"{d}/{BH}/manifest.json", lambda m: m.update(exit_status=1)), "manifest.schema"),
    ("behavior", lambda d: edit_json(f"{d}/{BH}/manifest.json", lambda m: m["files"]["behavior.mp4"].update(sha256="0" * 64)), "file.behavior.mp4"),
    ("lifecycle", lambda d: append_byte(f"{d}/{LC}/assurance.json"), f"file.{LC}/assurance.json"),
    ("lifecycle", lambda d: edit_json(f"{d}/{LC}/manifest.json", lambda m: m.update(status="accepted")), "manifest.schema"),
])
def test_chain_refuses_when_a_producer_hash_or_label_does_not_hold(mutate, chain, fn, failed_check):
    d, commit = mutate(fn)
    with pytest.raises(em.Refused) as e:
        rb.CHAINS[chain](d, commit)
    assert f"check failed: {failed_check}:" in str(e.value), str(e.value)[:300]


@needs_commit
def test_a_missing_producer_file_and_a_missing_commit_are_refused(mutate):
    d, commit = mutate(lambda d: os.remove(f"{d}/{BH}/controls.json"))
    with pytest.raises(em.Refused, match="not in the pinned commit"):
        rb.behavior_chain(d, commit)
    with pytest.raises(em.Refused, match="cannot resolve"):
        em.resolve_commit(ROOT, "0" * 40)


# ------------------------------------------------------------------ the frozen bundles import into a THROWAWAY store and become searchable
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


@needs_commit
def test_frozen_bundles_import_into_an_ephemeral_store_with_zero_forks_and_are_searchable(chains, pgstore):
    from frontier.artifacts import ArtifactIndex
    total = 0
    for c in chains:
        out = pgstore.import_bundle("test-only-local-token-for-alice", "run-import-" + c.name, em.build_bundle([c], limit=rb.AssetChain.max_records))
        assert len(out["inserted"]) == len(c.records) and out["forks"] == []
        total += len(out["inserted"])
    assert total == sum(len(c.records) for c in chains)
    idx = ArtifactIndex(pgstore)
    geo = idx.search("", role="geometry")["items"]
    assert geo and all(i["artifact"]["availability"] == "referenced" and i["artifact_bytes_verified"] is False and i["local_status"] == "imported_unreviewed" for i in geo)
    assert [i["evidence_kind"] for i in idx.search("states.npz")["items"]] == ["simulated"]


# ------------------------------------------------------------------ BETSE tissue chain (own frozen set, own source commit)
@pytest.fixture(scope="module")
def betse():
    return rb.betse_chain(ROOT, COMMIT_BETSE)


@pytest.fixture
def mutate_betse(tmp_path):
    d = str(tmp_path)
    subprocess.run(f"git -C {ROOT} archive {COMMIT_BETSE} {' '.join(BETSE_PATHS)} | tar -x -C {d}", shell=True, check=True)
    _git(d, "init", "-q"); _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "base")
    base = _git(d, "rev-parse", "HEAD")

    def go(fn=None):
        if fn is None:
            return d, base
        fn(d)
        _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "mutated")
        return d, _git(d, "rev-parse", "HEAD")
    return go


BT = "artifacts/bioelectric-tissue"


@needs_betse
def test_betse_shape_kinds_and_separate_render(betse):
    kinds = [r["kind"] for r in betse.records]
    assert (kinds.count("Claim"), kinds.count("Action"), kinds.count("Evidence")) == (2, 3, 3)
    ev = {r["id"]: r["payload"] for r in betse.records if r["kind"] == "Evidence"}
    assert ev["run-betse-evidence-render"]["relation"] == "context_only" and ev["run-betse-evidence-sim"]["relation"] != "supports"
    assert {r["kind"] for r in betse.records} == {"Claim", "Action", "Evidence"}


@needs_betse
def test_betse_keeps_generic_tissue_no_fin_calibration_and_the_ghk_gap_visible(betse):
    lim = " ".join(" ".join(r["payload"]["limitations"]) for r in betse.records if r["kind"] in ("Claim", "Evidence"))
    for must in ("GENERIC 2-D tissue patch", "Fin applicability: UNKNOWN", "Not calibrated to any fish", "310 K", "-23.5 mV", "0.70 mV", "not decomposed", "Kcnj13",
                 "used_to_set_any_parameter False"):
        assert must in lim, must


@needs_betse
def test_betse_actions_say_what_the_receipt_lacks_and_hashes_are_labelled(betse):
    titles = {r["id"]: r["payload"]["title"] for r in betse.records if r["kind"] == "Action"}
    assert "NO exit code, command or wall time" in titles["run-betse-action-sim"]
    assert "NO hash for either" in titles["run-betse-action-render"] and "computed by this adapter" in titles["run-betse-action-render"]
    cl = {r["id"]: r["payload"] for r in betse.records if r["kind"] == "Claim"}["run-betse-claim-checks"]
    assert "7 tests" in " ".join(cl["limitations"]) and "did not run them" in " ".join(cl["limitations"])


@needs_betse
def test_betse_numbers_in_the_claim_come_from_the_summary(betse):
    sm = json.loads(subprocess.run(["git", "-C", ROOT, "cat-file", "blob", f"{COMMIT_BETSE}:{BT}/summary.json"], capture_output=True, check=True).stdout)
    st = {r["id"]: r["payload"] for r in betse.records if r["kind"] == "Claim"}["run-betse-claim-k-gap-junction-contrast"]["statement"]
    assert f"{sm['effects']['k_up']['targeted_peak_dVm_mV']:.2f} mV" in st and f"{sm['effects']['k_up_gj_block']['targeted_peak_dVm_mV']:.1f} mV" in st
    assert f"{sm['reference_ghk']['simulated_mean_resting_Vm_mV']:.1f} mV" in st


@needs_betse
def test_betse_bundle_is_deterministic_linked_referenced_and_the_committed_one_is_reproduced(betse, tmp_path):
    again = rb.betse_chain(ROOT, COMMIT_BETSE)
    assert [r["version"] for r in betse.records] == [r["version"] for r in again.records]
    bundle = em.build_bundle([betse], limit=rb.AssetChain.max_records)
    assert all(x["ok"] for x in em.link_checks(bundle["records"]))
    assert find_abs_paths(betse.records) == [] and all(a["uri"] == "urn:sha256:" + a["sha256"] and a["availability"] == "referenced" and a["license"] is None
                                                       for r in betse.records for a in r["payload"].get("artifacts", []))
    rb.write_frozen(str(tmp_path), [betse])
    assert sorted(n for n in os.listdir(EXAMPLE_BETSE) if n != "README.md") == sorted(os.listdir(tmp_path))
    for n in (n for n in os.listdir(EXAMPLE_BETSE) if n != "README.md"):
        assert open(os.path.join(EXAMPLE_BETSE, n), "rb").read() == open(tmp_path / n, "rb").read(), f"{n} differs; refreeze with --source-commit {COMMIT_BETSE[:12]}"
    assert all(rb.find_secretish(open(os.path.join(EXAMPLE_BETSE, n)).read()) == [] for n in os.listdir(EXAMPLE_BETSE))


@needs_betse
def test_betse_positive_control_the_unedited_copy_builds(mutate_betse):
    d, commit = mutate_betse()
    assert len(rb.betse_chain(d, commit).records) == 8


@needs_betse
@pytest.mark.parametrize("fn,failed_check", [
    (lambda d: append_byte(f"{d}/{BT}/trajectories/k_up.npz"), "trajectory.k_up"),
    (lambda d: append_byte(f"{d}/{BT}/configs/gj_block.yaml"), "config.gj_block"),
    (lambda d: edit_json(f"{d}/{BT}/summary.json", lambda m: m.update(all_checks_ok=False)), "summary.schema"),
    (lambda d: edit_json(f"{d}/{BT}/summary.json", lambda m: m.update(label="OBSERVED tissue")), "summary.schema"),
    (lambda d: edit_json(f"{d}/{BT}/summary.json", lambda m: m["checks"]["time_step_sensitivity"].update(ok=False)), "summary.checks"),
    (lambda d: edit_json(f"{d}/{BT}/summary.json", lambda m: m["files"].pop("baseline_dt")), "summary.scenarios"),
    (lambda d: edit_json(f"{d}/{BT}/model_interface.json", lambda m: m.update(status="calibrated fin model")), "interface.status"),
])
def test_betse_refuses_when_a_hash_label_or_check_does_not_hold(mutate_betse, fn, failed_check):
    d, commit = mutate_betse(fn)
    with pytest.raises(em.Refused) as e:
        rb.betse_chain(d, commit)
    assert f"check failed: {failed_check}:" in str(e.value), str(e.value)[:300]


@needs_betse
def test_betse_bundle_imports_into_an_ephemeral_store_with_zero_forks(betse, pgstore):
    out = pgstore.import_bundle("test-only-local-token-for-alice", "run-import-betse", em.build_bundle([betse], limit=rb.AssetChain.max_records))
    assert len(out["inserted"]) == 8 and out["forks"] == []
