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
