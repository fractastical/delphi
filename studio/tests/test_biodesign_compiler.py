import copy
import json
from pathlib import Path

from engineering import coupling as cp
from engineering.biodesign_compiler import compile as bc
from engineering.biodesign_compiler import run as bcrun

ROOT = Path(__file__).resolve().parents[1]


def _r(cache=None):
    return bc.run(ROOT, cache)


def test_three_pinned_assemblies_with_exact_hashes_and_no_genome_claim():
    r = _r()
    assert [a["id"] for a in r["assemblies"]] == ["fish3d-v3a", "fish3d-v3b", "fish3d-v3c"]
    for a in r["assemblies"]:
        for k in bc.LAYERS:
            p = a["components"][k]
            assert bc.sha((ROOT / p["path"]).read_bytes()) == p["sha256"]
        assert "no whole-genome design is implied" in a["scope"]


def test_v3b_unconverged_vlm_is_a_retained_failure_and_others_are_not_called_converged():
    c = {x["assembly"]: x["axes"] for x in _r()["compiled"]}
    assert c["fish3d-v3b"]["numerical"]["status"].startswith("fail") and c["fish3d-v3b"]["model_domain"]["status"] == "fail"
    assert "NOT CONVERGED" in c["fish3d-v3b"]["numerical"]["reason"]
    for v in ("fish3d-v3a", "fish3d-v3c"):
        assert "not called converged" in c[v]["numerical"]["status"]


def test_missing_bridges_stay_unresolved_and_axes_are_separate():
    for x in _r()["compiled"]:
        assert set(x["axes"]) == set(bc.AXES) and "status" not in x
        b = {y["bridge"]: y for y in x["unresolved_bridges"]}
        assert b["expression->growth"]["status"] == b["growth->EI"]["status"] == "unresolved"
        assert x["axes"]["empirical"]["status"] == x["axes"]["implementation"]["status"] == "unresolved"


def test_comparison_flags_the_unconverged_variant_unusable():
    rows = {r["assembly"]: r for r in _r()["comparison"]["rows"]}
    assert rows["fish3d-v3b"]["usable_for_comparison"] is False and rows["fish3d-v3a"]["usable_for_comparison"] is True


def test_broken_hash_fixture_is_reported_with_its_reason():
    c = _r()["controls"]["broken_hash"]
    assert c["got"] == "fail" and "pinned 000000000000" in c["reason"][0]["reason"] and c["reason"][0]["layer"] == "geometry"


def test_broken_unit_fixture_is_refused_with_a_dimension_reason():
    c = _r()["controls"]["broken_unit"]
    assert c["got"] == "refused" and any("dimension" in x for x in c["reason"])
    # positive control: the unbroken coupling is not refused for dimension
    good = next(x for x in cp.default_couplings() if x.id.startswith("c13"))
    assert cp.validate_coupling(cp.default_registry(), good).checks["dimension"] == "pass"


def test_changed_pin_invalidates_exactly_the_stages_that_read_it_and_cache_otherwise_reused():
    r = _r()
    a = r["assemblies"][0]
    h = copy.deepcopy(a)
    h["components"]["aero"]["sha256"] = "2" * 64
    imp = bc.impact(a, h)
    assert imp["invalidated_stages"] == ["structural_refs", "units_context", "model_domain", "numerical"]
    assert set(imp["kept_stages"]) == {"empirical", "implementation"}
    cache = {}
    bc.compile_assembly(ROOT, a, cache=cache)
    again = bc.compile_assembly(ROOT, a, cache=cache)
    assert set(again["reused_from_cache"]) == set(bc.AXES)
    third = bc.compile_assembly(ROOT, h, cache=cache)
    assert set(third["reused_from_cache"]) == {"empirical", "implementation"}
    assert third["axes"]["structural_refs"]["status"] == "fail"


def test_layer_diff_finds_the_geometry_change_between_siblings():
    d = {(x["a"], x["b"]): x for x in _r()["layer_revision_diff"]}
    x = d[("fish3d-v3a", "fish3d-v3b")]
    assert "geometry" in x["changed_layers"] and "genetic_blueprint" not in x["changed_layers"] and x["geometry_knob_changes"]


def test_committed_artifacts_match_a_fresh_build():
    for k, v in bcrun.build().items():
        assert (bcrun.OUT / k).read_text() == v, k
    json.loads((bcrun.OUT / "report.json").read_text())


def _cached(a):
    cache = {}
    bc.compile_assembly(ROOT, a, cache=cache)
    return cache


def test_changed_panels_or_path_pin_is_not_served_from_cache():
    a = _r()["assemblies"][0]
    cache = _cached(a)
    h = copy.deepcopy(a)
    h["components"]["geometry_panels"]["sha256"] = "3" * 64
    out = bc.compile_assembly(ROOT, h, cache=cache)
    assert "structural_refs" not in out["reused_from_cache"] and out["axes"]["structural_refs"]["status"] == "fail"
    h = copy.deepcopy(a)
    h["components"]["aero"]["path"] = "artifacts/cfd3d/vlm/fish3d-v3b-glide-pose/vlm.json"
    out = bc.compile_assembly(ROOT, h, cache=cache)
    assert {"structural_refs", "units_context", "model_domain", "numerical"}.isdisjoint(out["reused_from_cache"])
    assert bc.impact(a, h)["changed_layers"] == ["aero"]
    h = copy.deepcopy(a)
    h["components"]["geometry_components"]["sha256"] = "4" * 64
    assert "structural_refs" in bc.impact(a, h)["invalidated_stages"]


def test_changed_dependency_file_content_invalidates_dependent_stages(tmp_path):
    import shutil
    a = _r()["assemblies"][0]
    for f in ("engineering/biodesign_compiler/compile.py", "engineering/coupling.py", "engineering/COUPLING_MANIFEST.json"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, tmp_path / f)
    shutil.copytree(ROOT / "engineering/model_interfaces", tmp_path / "engineering/model_interfaces")
    base = {s: bc.stage_key(tmp_path, a, s) for s in bc.AXES}
    with open(tmp_path / "engineering/COUPLING_MANIFEST.json", "a") as f:
        f.write(" ")
    after = {s: bc.stage_key(tmp_path, a, s) for s in bc.AXES}
    assert {s for s in bc.AXES if base[s] != after[s]} == {"units_context", "empirical"}
    with open(tmp_path / "engineering/model_interfaces/glide_pointmass.json", "a") as f:
        f.write(" ")
    assert bc.stage_key(tmp_path, a, "units_context") != after["units_context"]
    assert bc.stage_key(tmp_path, a, "numerical") == after["numerical"]
    with open(tmp_path / "engineering/biodesign_compiler/compile.py", "a") as f:
        f.write("\n")
    assert all(bc.stage_key(tmp_path, a, s) != after[s] for s in bc.AXES)


def _tree(tmp_path):
    """Bounded fixture: only the pinned files of the three assemblies, STAGE_FILES and model_interfaces."""
    import shutil
    want = {p["path"] for a in bc.run(ROOT)["assemblies"] for p in a["components"].values()}
    want |= {f for fs in bc.STAGE_FILES.values() for f in fs}
    want |= {str(f.relative_to(ROOT)) for f in (ROOT / "engineering/model_interfaces").glob("*.json")}
    for rel in want:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    assert sum(f.stat().st_size for f in tmp_path.rglob("*") if f.is_file()) < 5_000_000
    return tmp_path


def test_externally_changed_bytes_with_unchanged_manifest_are_not_served_from_cache(tmp_path):
    t = _tree(tmp_path)
    a = bc.run(t)["assemblies"][0]
    cache = {}
    assert bc.compile_assembly(t, a, cache=cache)["axes"]["structural_refs"]["status"] == "pass"
    f = t / a["components"]["geometry_panels"]["path"]
    f.write_bytes(f.read_bytes() + b" ")
    out = bc.compile_assembly(t, a, cache=cache)
    assert "structural_refs" not in out["reused_from_cache"] and out["axes"]["structural_refs"]["status"] == "fail"


def test_empirical_and_implementation_read_the_pinned_file_not_a_hardcoded_path(tmp_path):
    t = _tree(tmp_path)
    a = bc.run(t)["assemblies"][0]
    b = copy.deepcopy(a)
    b["components"]["genetic_blueprint"].update(path="artifacts/fish-regulatory-map/map.json", sha256=bc.sha((t / "artifacts/fish-regulatory-map/map.json").read_bytes()))
    out = bc.compile_assembly(t, b)["axes"]
    assert out["implementation"]["status"] == "blocked" and out["implementation"]["blocked_by"] == ["genetic_blueprint"]
    assert "malformed" in out["implementation"]["reason"]
    c = copy.deepcopy(a)
    c["components"]["behavior"].update(path="artifacts/fish-regulatory-map/map.json", sha256=bc.sha((t / "artifacts/fish-regulatory-map/map.json").read_bytes()))
    assert bc.compile_assembly(t, c)["axes"]["empirical"]["status"] == "blocked"


def test_missing_or_malformed_pinned_file_returns_blocked_not_a_crash(tmp_path):
    t = _tree(tmp_path)
    a = bc.run(t)["assemblies"][0]
    (t / a["components"]["aero"]["path"]).unlink()
    ax = bc.compile_assembly(t, a)["axes"]
    assert set(ax) == set(bc.AXES) and ax["structural_refs"]["status"] == "fail"
    assert ax["model_domain"]["status"] == ax["numerical"]["status"] == "blocked" and ax["model_domain"]["blocked_by"] == ["aero"]
    assert ax["empirical"]["status"] == "unresolved"  # does not read aero: positive control, not blocked
    f = t / a["components"]["behavior"]["path"]
    f.write_text("{not json")
    ax = bc.compile_assembly(t, a)["axes"]
    assert ax["empirical"]["status"] == "blocked" and "behavior" in ax["empirical"]["blocked_by"]
    assert bc.compare(t, [a])["rows"][0]["usable_for_comparison"] is False and "blocked" in bc.compare(t, [a])["rows"][0]


def test_overridden_registry_or_couplings_do_not_reuse_default_cache():
    a = _r()["assemblies"][0]
    cache = {}
    bc.compile_assembly(ROOT, a, cache=cache)
    few = cp.default_couplings()[:2]
    out = bc.compile_assembly(ROOT, a, couplings=few, cache=cache)
    assert "units_context" not in out["reused_from_cache"] and sum(out["axes"]["units_context"]["counts"].values()) == 2
    assert "units_context" in bc.compile_assembly(ROOT, a, couplings=few, cache=cache)["reused_from_cache"]
    reg = cp.default_registry()
    assert bc.registry_fingerprint(reg, few) != bc.registry_fingerprint(reg, cp.default_couplings())


def test_non_string_status_and_non_numeric_refinement_are_blocked_not_a_crash(tmp_path):
    t = _tree(tmp_path)
    a = bc.run(t)["assemblies"][0]
    f = t / a["components"]["aero"]["path"]
    o = json.loads(f.read_bytes())
    o["status"] = 7
    f.write_text(json.dumps(o))
    a2 = copy.deepcopy(a)
    a2["components"]["aero"]["sha256"] = bc.sha(f.read_bytes())
    ax = bc.compile_assembly(t, a2)["axes"]
    assert ax["model_domain"]["status"] == ax["numerical"]["status"] == "blocked"
    assert "status is int, expected str" in ax["model_domain"]["reason"]
    o["status"] = "ok"
    o["refinement"]["CL_rel_change"] = "0.2"
    f.write_text(json.dumps(o))
    a2["components"]["aero"]["sha256"] = bc.sha(f.read_bytes())
    ax = bc.compile_assembly(t, a2)["axes"]
    assert ax["numerical"]["status"] == "blocked" and "expected number" in ax["numerical"]["reason"]
    assert ax["model_domain"]["status"] == "unassessed"  # positive control: a valid string status still runs


def test_missing_required_pin_or_bad_pin_shape_is_a_typed_failure_with_six_axes():
    a = _r()["assemblies"][0]
    for mut, msg in ((lambda x: x["components"].pop("behavior"), "missing required pin behavior"),
                     (lambda x: x["components"]["aero"].update(sha256="abc"), "64-character sha256"),
                     (lambda x: x.update(components=[]), "no components object")):
        b = copy.deepcopy(a)
        mut(b)
        out = bc.compile_assembly(ROOT, b, cache={})
        assert set(out["axes"]) == set(bc.AXES) and out["axes"]["structural_refs"]["status"] == "fail"
        assert any(msg in f["reason"] for f in out["axes"]["structural_refs"]["failures"])
        assert all(out["axes"][s]["status"] == "blocked" for s in bc.AXES if s != "structural_refs")
    assert bc.compile_assembly(ROOT, a)["axes"]["structural_refs"]["status"] == "pass"


def test_malformed_designs_are_blocked(tmp_path):
    t = _tree(tmp_path)
    a = bc.run(t)["assemblies"][0]
    f = t / a["components"]["genetic_blueprint"]["path"]
    for bad in ([1], [{"expression_kinetics": {"status": "UNKNOWN"}}], "x", []):
        o = json.loads(f.read_bytes())
        o["designs"] = bad
        f.write_text(json.dumps(o))
        a2 = copy.deepcopy(a)
        a2["components"]["genetic_blueprint"]["sha256"] = bc.sha(f.read_bytes())
        assert bc.compile_assembly(t, a2)["axes"]["implementation"]["status"] == "blocked", bad


def test_empty_couplings_list_is_not_replaced_by_defaults():
    a = _r()["assemblies"][0]
    out = bc.compile_assembly(ROOT, a, couplings=[])
    assert out["axes"]["units_context"]["counts"] == {}
