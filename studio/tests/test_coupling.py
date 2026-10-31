"""Coupling-layer tests. All SYNTHETIC fixtures are labelled 'synthetic test fixture': they exercise the rules and are
never evidence about any organism. The default registry has NO real calibration, and a test pins that."""
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction

import pytest

from engineering.coupling import (
    BASE_UNITS, tree_sha256, verify_reference_sources, FILES, Assumption, Bounds, Calibration, Coupling, CouplingError, ModelSpec, Port, Provenance, Registry,
    Timescale, build_manifest, default_couplings, default_registry, dim, model_from_json, model_to_json,
    problem_proposal, validate_coupling,
)

SYN = Provenance("synthetic test fixture", "assumed", "none")
SHA = "a" * 64


def port(name, direction, quantity="length", kind="dimensional", unit="m", d=None, scale="tissue", regime="r",
         context="ctx", bounds=None):
    d = dim(m=1) if (kind == "dimensional" and d is None) else (dim() if kind == "dimensionless" else d)
    return Port(name, direction, quantity, kind, unit, d, scale, regime, context, SYN, bounds)


def model(mid, ports, status="implemented", ts=Timescale("static")):
    files = {"synthetic.py": "b" * 64}
    ref = None if status == "proposed" else {"repo": "synthetic", "branch": "x", "commit": "y", "path": "synthetic.py",
                                              "files": files, "source_sha256": tree_sha256(files)}
    return ModelSpec(mid, mid, "synthetic", status, ref, tuple(ports), ts, "synthetic test fixture", ("everything",))


def pair(src_port, dst_port, src_ts=Timescale("static"), dst_ts=Timescale("static"), src_status="implemented",
         dst_status="implemented"):
    r = Registry()
    r.add_model(model("src", [src_port], src_status, src_ts))
    r.add_model(model("dst", [dst_port], dst_status, dst_ts))
    return r


IDENT = dict(mapping_kind="identity", time_relation="static_input", uncertainty_kind="exact")


def cal(**kw):
    base = dict(id="cal1", from_port="src.o", to_port="dst.i", evidence_kind="measured", source="synthetic test fixture",
                read_level="data", data_sha256=SHA, domain=Bounds(Fraction(0), Fraction(10), "fixture", "measured"),
                factor=Fraction(1000), factor_dim=dim(), uncertainty_rel=Fraction(1, 10), n_points=5, bridges={})
    base.update(kw)
    return Calibration(**base)


# ------------------------------------------------------------------ default registry: honesty about what exists

def test_default_registry_has_no_real_calibration_and_the_expected_verdict_counts():
    reg = default_registry()
    assert reg.calibrations == {}
    m = build_manifest(reg, default_couplings())
    assert m["counts"] == {"composable": 4, "scenario": 5, "refused": 4}
    by = {r["coupling"]["id"]: r["verdict"] for r in m["couplings"]}
    assert [k for k, v in by.items() if v["status"] == "composable"] == [
        "c01_mass", "c02_area", "c03_span", "c09_span_to_fin_bridge"]
    assert [k for k, v in by.items() if v["status"] == "scenario"] == [
        "c04_speed", "c10_speed_to_fin_bridge", "c11_load_proxy_to_beam", "c12_ray_length_to_beam",
        "c13_pressure_to_line_load_dimension_only"]
    for k in ("c04_speed", "c10_speed_to_fin_bridge", "c11_load_proxy_to_beam", "c12_ray_length_to_beam",
              "c13_pressure_to_line_load_dimension_only"):
        assert "assumption-level" in by[k]["label"]
    for k in ("c05_notch_to_fin_stiffness", "c06_notch_to_fin_stiffness_assumed", "c07_rd_wavelength_to_wing_span",
              "c08_fin_deflection_to_glide_speed"):
        assert by[k]["status"] == "refused"
    assert m["calibrations_registered"] == []
    assert "Registered calibrations: NONE" in m["must_display"]


def test_the_notch_to_fin_bridge_cannot_be_made_even_by_naming_an_assumption():
    reg = default_registry()
    v = validate_coupling(reg, [c for c in default_couplings() if c.id == "c06_notch_to_fin_stiffness_assumed"][0])
    assert v.status == "refused" and any("cannot stand in" in r for r in v.reasons)   # fin beam now EXISTS; still refused
    assert v.checks["scope"].startswith("fail") and v.missing_calibrations
    v5 = validate_coupling(reg, [c for c in default_couplings() if c.id == "c05_notch_to_fin_stiffness"][0])
    assert any("scope mismatch" in r for r in v5.reasons) and v5.missing_calibrations


def test_non_dimensional_model_cannot_feed_an_si_port_by_identity_or_unit_conversion():
    reg = default_registry()
    for kind, extra in (("identity", {}), ("unit_conversion", {"factor": Fraction(1), "factor_dim": dim(m=1)})):
        c = Coupling("x", "rdfield_nonlinear_sweep.dominant_mode", "glide_pointmass.b", mapping_kind=kind,
                     time_relation="unknown", uncertainty_kind="exact", **extra)
        assert validate_coupling(reg, c).status == "refused"


# ------------------------------------------------------------------ typed rules

def test_identity_requires_same_quantity_not_just_equal_dimensions():
    reg = pair(port("o", "out", quantity="glide range"), port("i", "in", quantity="wing span"))
    v = validate_coupling(reg, Coupling("c", "src.o", "dst.i", **IDENT))
    assert v.status == "refused" and any("SAME quantity" in r for r in v.reasons)
    ok = pair(port("o", "out", quantity="wing span"), port("i", "in", quantity="wing span"))
    assert validate_coupling(ok, Coupling("c", "src.o", "dst.i", **IDENT)).status == "composable"


def test_dimension_mismatch_is_refused():
    reg = pair(port("o", "out", quantity="q", d=dim(kg=1), unit="kg"), port("i", "in", quantity="q", d=dim(m=1)))
    v = validate_coupling(reg, Coupling("c", "src.o", "dst.i", **IDENT))
    assert v.status == "refused" and v.checks["dimension"] == "fail"


def test_unit_conversion_needs_a_positive_exact_dimensionless_factor():
    reg = pair(port("o", "out", quantity="mass", d=dim(kg=1), unit="g"), port("i", "in", quantity="mass", d=dim(kg=1), unit="kg"))
    mk = lambda **k: Coupling("c", "src.o", "dst.i", mapping_kind="unit_conversion", time_relation="static_input",
                              uncertainty_kind="exact", **k)
    assert validate_coupling(reg, mk(factor=Fraction(1, 1000), factor_dim=dim())).status == "composable"
    for bad in (dict(), dict(factor=Fraction(0), factor_dim=dim()), dict(factor=Fraction(-1), factor_dim=dim()),
                dict(factor=Fraction(1, 1000), factor_dim=dim(m=1))):
        assert validate_coupling(reg, mk(**bad)).status == "refused", bad
    with pytest.raises(CouplingError):
        mk(factor=0.001)  # floats refused


def test_direction_self_coupling_unknown_refs_and_proposed_endpoints_are_refused_not_raised():
    reg = pair(port("o", "out"), port("i", "in"))
    assert validate_coupling(reg, Coupling("c", "dst.i", "src.o", **IDENT)).status == "refused"       # reversed
    assert validate_coupling(reg, Coupling("c", "nope.o", "dst.i", **IDENT)).status == "refused"
    assert validate_coupling(reg, Coupling("c", "src.zzz", "dst.i", **IDENT)).status == "refused"
    r2 = Registry().add_model(model("m", [port("o", "out"), port("i", "in")]))
    assert validate_coupling(r2, Coupling("c", "m.o", "m.i", **IDENT)).status == "refused"            # self
    r3 = pair(port("o", "out"), port("i", "in"), dst_status="proposed")
    assert validate_coupling(r3, Coupling("c", "src.o", "dst.i", **IDENT)).status == "refused"


def test_scope_mismatch_needs_a_bridging_calibration_never_an_identity():
    for field_, a, b in (("scale", "cell", "organism"), ("context", "fly", "fish"), ("regime", "r1", "r2")):
        reg = pair(port("o", "out", quantity="q", **{field_: a}), port("i", "in", quantity="q", **{field_: b}))
        v = validate_coupling(reg, Coupling("c", "src.o", "dst.i", **IDENT))
        assert v.status == "refused" and v.checks["scope"].startswith("fail"), field_


def test_time_scale_rules():
    mk = lambda rel, a, b: validate_coupling(
        pair(port("o", "out", quantity="q"), port("i", "in", quantity="q"), a, b),
        Coupling("c", "src.o", "dst.i", mapping_kind="identity", time_relation=rel, uncertainty_kind="exact"))
    S = lambda x: Timescale("seconds", Fraction(x), "fixture")
    assert mk("quasi_static", S(100), S(10)).status == "composable"           # exactly the declared 10x separation
    assert mk("quasi_static", S(99), S(10)).status == "refused"
    assert mk("quasi_static", Timescale("unknown"), S(10)).status == "scenario"
    assert mk("static_input", S(100), S(10)).status == "refused"              # source is not static
    assert mk("concurrent", S(100), S(10)).status == "refused"
    assert mk("unknown", Timescale("unknown"), S(10)).status == "scenario"


def test_uncertainty_edges():
    reg = pair(port("o", "out", quantity="q"), port("i", "in", quantity="q"))
    mk = lambda **k: validate_coupling(reg, Coupling("c", "src.o", "dst.i", mapping_kind="identity",
                                                      time_relation="static_input", **k))
    assert mk(uncertainty_kind="exact").status == "composable"
    assert mk(uncertainty_kind="unknown").status == "scenario"
    assert mk(uncertainty_kind="declared_interval", uncertainty_rel=Fraction(1, 5)).status == "scenario"
    assert mk(uncertainty_kind="calibration_relative_bound").status == "refused"   # no calibration behind it


def test_assumptions_make_a_scenario_and_unknown_assumptions_are_refused():
    reg = pair(port("o", "out", quantity="q"), port("i", "in", quantity="q"))
    reg.add_assumption(Assumption("A", "fixture assumption"))
    base = dict(mapping_kind="identity", time_relation="static_input", uncertainty_kind="exact")
    v = validate_coupling(reg, Coupling("c", "src.o", "dst.i", assumption_ids=("A",), **base))
    assert v.status == "scenario" and v.assumption_ids == ["A"]
    assert validate_coupling(reg, Coupling("c", "src.o", "dst.i", assumption_ids=("ZZ",), **base)).status == "refused"
    assm = lambda **k: validate_coupling(reg, Coupling("c", "src.o", "dst.i", mapping_kind="assumed", **k))
    assert assm().status == "refused"                                          # assumed with no named assumption


def test_bounds_extrapolation_downgrades_to_scenario():
    B = lambda lo, hi: Bounds(Fraction(lo), Fraction(hi), "fixture", "assumed")
    mk = lambda fb, tb: validate_coupling(
        pair(port("o", "out", quantity="q", bounds=fb), port("i", "in", quantity="q", bounds=tb)),
        Coupling("c", "src.o", "dst.i", **IDENT))
    assert mk(B(1, 5), B(0, 10)).status == "composable"
    v = mk(B(1, 50), B(0, 10))
    assert v.status == "scenario" and v.checks["bounds"].startswith("extrapolation")


# ------------------------------------------------------------------ calibrations (SYNTHETIC fixture)

B0 = lambda lo, hi: Bounds(Fraction(lo), Fraction(hi), "synthetic test fixture", "assumed")


def cal_registry(c=None, src_bounds=B0(1, 5), dst_bounds=B0(0, 10000), dst_scale="tissue", dst_context="ctx"):
    r = pair(port("o", "out", kind="model_units", unit="model units", quantity="pattern wavelength", d=None,
                  bounds=src_bounds),
             port("i", "in", quantity="pattern wavelength", unit="mm", d=dim(m=1), scale=dst_scale,
                  context=dst_context, bounds=dst_bounds))
    r.add_calibration(c if c is not None else cal())
    return r


CAL_C = Coupling("cc", "src.o", "dst.i", mapping_kind="calibrated", calibration_id="cal1", time_relation="static_input",
                 uncertainty_kind="calibration_relative_bound")


def test_a_structurally_complete_calibration_makes_a_model_units_bridge_composable():
    v = validate_coupling(cal_registry(), CAL_C)
    assert v.status == "composable", (v.reasons, v.checks)


def test_a_calibrated_map_with_unknown_bounds_cannot_be_checked_against_its_domain_so_it_is_only_a_scenario():
    v = validate_coupling(cal_registry(src_bounds=None, dst_bounds=None), CAL_C)
    assert v.status == "scenario" and v.checks["bounds"].startswith("unknown")


@pytest.mark.parametrize("label,kw", [
    ("abstract-only source", dict(read_level="abstract")),
    ("no data hash", dict(data_sha256="")),
    ("short hash", dict(data_sha256="abc")),
    ("assumed evidence", dict(evidence_kind="assumed")),
    ("open domain", dict(domain=Bounds(Fraction(0), None, "f", "measured"))),
    ("zero factor", dict(factor=Fraction(0))),
    ("one point", dict(n_points=1)),
    ("negative uncertainty", dict(uncertainty_rel=Fraction(-1))),
    ("wrong port pair", dict(from_port="src.other")),
])
def test_each_structural_defect_in_a_calibration_refuses_the_coupling(label, kw):
    v = validate_coupling(cal_registry(cal(**kw)), CAL_C)
    assert v.status == "refused", label


def test_unregistered_calibration_is_a_missing_bridge_with_a_problem():
    reg = cal_registry()
    c = Coupling("cc", "src.o", "dst.i", mapping_kind="calibrated", calibration_id="nope", time_relation="static_input",
                 uncertainty_kind="calibration_relative_bound")
    v = validate_coupling(reg, c)
    assert v.status == "refused" and v.missing_calibrations == ["nope"]
    assert problem_proposal(reg, c, v)["kind"] == "missing_calibration"


def test_calibration_domain_and_target_bounds_are_enforced():
    B = lambda lo, hi: Bounds(Fraction(lo), Fraction(hi), "fixture", "assumed")
    v = validate_coupling(cal_registry(src_bounds=B(1, 5), dst_bounds=B(0, 10000)), CAL_C)
    assert v.status == "composable"
    v = validate_coupling(cal_registry(src_bounds=B(1, 50), dst_bounds=B(0, 100000)), CAL_C)       # leaves cal domain 0-10
    assert v.status == "scenario" and "calibration domain" in v.checks["bounds"]
    v = validate_coupling(cal_registry(src_bounds=B(1, 5), dst_bounds=B(0, 100)), CAL_C)           # 5*1000 > 100
    assert v.status == "scenario" and "target" in v.checks["bounds"]


def test_a_calibration_bridges_scale_and_context_only_if_it_says_so():
    kw = dict(dst_scale="organism", dst_context="fish")
    assert validate_coupling(cal_registry(**kw), CAL_C).status == "refused"
    declared = cal(bridges={"scale": ("tissue", "organism"), "context": ("ctx", "fish")})
    assert validate_coupling(cal_registry(declared, **kw), CAL_C).status == "composable"
    wrong = cal(bridges={"scale": ("cell", "organism"), "context": ("ctx", "fish")})
    assert validate_coupling(cal_registry(wrong, **kw), CAL_C).status == "refused"


# ------------------------------------------------------------------ interface JSON + manifest

def test_interface_json_round_trips_for_every_default_model():
    for m in default_registry().models.values():
        j = json.loads(json.dumps(model_to_json(m)))
        assert model_from_json(j) == m
        assert j["schema"] == "frontier.model.interface/1"


def test_interface_parser_is_strict():
    j = model_to_json(default_registry().models["glide_pointmass"])
    bad = lambda f: pytest.raises((CouplingError, TypeError, KeyError))
    for mut in (lambda o: o.update(schema="x"), lambda o: o.update(extra=1),
                lambda o: o["ports"][0].update(extra=1),
                lambda o: o["ports"][0].update(dim={"kg": 0, "m": 0, "s": 0}),          # dimensional with zero dim
                lambda o: o["ports"][0].update(kind="model_units"),                      # model_units must have dim None
                lambda o: o["ports"][0].update(scale="galaxy"),
                lambda o: o["ports"][0].update(direction="sideways"),
                lambda o: o["ports"][0].update(context=""),
                lambda o: o.update(status="validated"),
                lambda o: o["timescale"].update(kind="seconds", seconds=None),
                lambda o: o["ports"][0]["provenance"].update(status="guessed")):
        o = json.loads(json.dumps(j))
        mut(o)
        with pytest.raises((CouplingError, TypeError, KeyError)):
            model_from_json(o)
    o = json.loads(json.dumps(j))
    o["ports"][0]["bounds"] = {"lo": 0.003, "hi": "1", "source": "x", "status": "assumed"}      # float bound
    with pytest.raises(TypeError):
        model_from_json(o)
    o = json.loads(json.dumps(j))
    o["reference"] = None                                                                   # implemented w/o reference
    with pytest.raises(CouplingError):
        model_from_json(o)


def test_manifest_is_deterministic_self_hashed_and_scoped():
    reg = default_registry()
    a, b = build_manifest(reg, default_couplings()), build_manifest(default_registry(), default_couplings())
    assert a == b
    body = {k: v for k, v in a.items() if k != "manifest_sha256"}
    import hashlib
    assert a["manifest_sha256"] == hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    changed = build_manifest(reg, default_couplings()[:-1])
    assert changed["manifest_sha256"] != a["manifest_sha256"]
    text = json.dumps(a["must_display"]).lower()
    assert "not biology" in text and "assumption-level" in text
    assert "Lean proves the biological correspondence" in a["must_not_say"]
    with pytest.raises(CouplingError):
        build_manifest(reg, default_couplings() + default_couplings()[:1])         # duplicate ids


def test_problem_proposals_exist_for_every_non_composable_coupling_and_invent_no_numbers_or_results():
    reg = default_registry()
    m = build_manifest(reg, default_couplings())
    ids = {p["source_coupling"] for p in m["problem_proposals"]}
    assert ids == {"c04_speed", "c05_notch_to_fin_stiffness", "c06_notch_to_fin_stiffness_assumed",
                   "c07_rd_wavelength_to_wing_span", "c08_fin_deflection_to_glide_speed", "c10_speed_to_fin_bridge",
                   "c11_load_proxy_to_beam", "c12_ray_length_to_beam", "c13_pressure_to_line_load_dimension_only"}
    for p in m["problem_proposals"]:
        assert p["status"] == "proposed" and p["not_a_claim"] is True
        assert p["success"] and p["falsifier"] and p["action_bounds"]["gpu"] is False
        assert p["action_bounds"]["paid_calls"] is False and "GPU submission" in p["action_bounds"]["forbidden"]
        assert "frozen BEFORE" in p["success"]                       # thresholds are slots, not invented values
        assert "whole-filesystem" in " ".join(p["action_bounds"]["allowed_actions"])
    assert all(p["prerequisites"] == [] for p in m["problem_proposals"])         # every endpoint model now exists


def test_module_is_stdlib_only_and_units_match_the_constraint_solver():
    out = subprocess.run([sys.executable, "-I", "-c",
                          "import sys; sys.path.insert(0, '.'); import engineering.coupling; "
                          "assert 'z3' not in sys.modules, 'coupling must not import the solver'"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    pytest.importorskip("z3")
    import engineering.constraints as K
    assert K.BASE_UNITS == BASE_UNITS and K.dim(kg=1, s=-2) == dim(kg=1, s=-2)


def test_a_missing_mapping_is_refused_even_when_everything_else_is_compatible():
    """Isolates the 'no bridge is invented' rule: ports match in quantity, unit, scale, context, regime."""
    reg = pair(port("o", "out", quantity="q"), port("i", "in", quantity="q"))
    v = validate_coupling(reg, Coupling("c", "src.o", "dst.i", mapping_kind="none", time_relation="static_input",
                                        uncertainty_kind="exact"))
    assert v.status == "refused" and any("no mapping declared" in r for r in v.reasons)
    assert validate_coupling(reg, Coupling("c", "src.o", "dst.i", **IDENT)).status == "composable"  # same ports, identity


def test_committed_manifest_and_interfaces_are_not_stale(tmp_path):
    from pathlib import Path
    from engineering.coupling import write_outputs
    write_outputs(tmp_path)
    root = Path(__file__).resolve().parents[1] / "engineering"
    assert (root / "COUPLING_MANIFEST.json").read_text() == (tmp_path / "COUPLING_MANIFEST.json").read_text()
    names = sorted(p.name for p in (tmp_path / "model_interfaces").iterdir())
    assert names == sorted(p.name for p in (root / "model_interfaces").iterdir())
    for n in names:
        assert (root / "model_interfaces" / n).read_text() == (tmp_path / "model_interfaces" / n).read_text()


# ======================= fin mechanics bridge: scenario only; dimension match is not validity =====================

from engineering.coupling import NM2, NPM, PA  # noqa: E402

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]


def _verdicts():
    reg = default_registry()
    return reg, {c.id: (c, validate_coupling(reg, c)) for c in default_couplings()}


def test_load_proxy_to_beam_is_a_scenario_with_the_stated_assumptions_and_never_composable():
    reg, vs = _verdicts()
    for cid in ("c11_load_proxy_to_beam", "c12_ray_length_to_beam"):
        c, v = vs[cid]
        assert v.status == "scenario" and "assumption-level" in v.label
        assert set(v.assumption_ids) <= {"A3", "A4"} and v.assumption_ids
        assert v.checks["mapping"] == "pass" and v.checks["dimension"] == "pass"     # the interface matches ...
    # removing the named assumptions and claiming exact arithmetic does NOT make the load proxy composable:
    # the PORT CAVEATS (proxy-derived load, declared length) block composition without a calibration
    for cid in ("c10_speed_to_fin_bridge", "c11_load_proxy_to_beam", "c12_ray_length_to_beam"):
        c = vs[cid][0]
        v = validate_coupling(reg, replace(c, assumption_ids=(), uncertainty_kind="exact"))
        assert v.status == "scenario", cid
        assert v.checks["caveats"].startswith("scenario:") and "proxy" in v.checks["caveats"].lower() or \
            "declared" in v.checks["caveats"].lower() or "level-flight" in v.checks["caveats"]


def test_pressure_to_line_load_matching_dimensions_is_flagged_not_established():
    reg, vs = _verdicts()
    c13, v13 = vs["c13_pressure_to_line_load_dimension_only"]
    assert v13.status == "scenario" and v13.checks["dimension"] == "pass"
    assert v13.checks["validity"].startswith("NOT established")
    assert "necessary, NOT evidence" in c13.note
    # PA * m == N/m exactly, and a wrong factor dimension is refused (so 'dimension pass' is not vacuous)
    assert {u: PA[u] + dim(m=1)[u] for u in BASE_UNITS} == NPM
    assert validate_coupling(reg, replace(c13, factor_dim=dim(m=2))).status == "refused"
    assert validate_coupling(reg, replace(c13, factor=None)).status == "refused"       # different units need a stated factor
    # a CALIBRATED pressure -> line-load map needs a registered calibration: none exists, so it is a missing bridge
    cal_c = replace(c13, mapping_kind="calibrated", factor=None, factor_dim=None, calibration_id="ray_pressure_cal",
                    uncertainty_kind="calibration_relative_bound")
    v = validate_coupling(reg, cal_c)
    assert v.status == "refused" and v.missing_calibrations == ["ray_pressure_cal"]


def test_assumptions_never_bridge_scale_or_context_only_regime():
    reg = pair(port("o", "out", quantity="q", scale="cell"), port("i", "in", quantity="q", scale="organ"))
    reg.add_assumption(Assumption("A", "fixture"))
    mk = lambda r: validate_coupling(r, Coupling("c", "src.o", "dst.i", mapping_kind="assumed", assumption_ids=("A",),
                                                 time_relation="static_input", uncertainty_kind="unknown"))
    assert mk(reg).status == "refused"
    reg2 = pair(port("o", "out", quantity="q", context="fly"), port("i", "in", quantity="q", context="fish"))
    reg2.add_assumption(Assumption("A", "fixture"))
    assert mk(reg2).status == "refused"
    reg3 = pair(port("o", "out", quantity="q", regime="r1"), port("i", "in", quantity="q", regime="r2"))
    reg3.add_assumption(Assumption("A", "fixture"))
    v = mk(reg3)
    assert v.status == "scenario" and v.checks["scope"].startswith("scenario")


def test_biological_couplings_stay_refused_now_that_every_endpoint_model_exists():
    reg, vs = _verdicts()
    assert all(m.status != "proposed" for m in reg.models.values())
    for cid in ("c05_notch_to_fin_stiffness", "c06_notch_to_fin_stiffness_assumed", "c07_rd_wavelength_to_wing_span",
                "c08_fin_deflection_to_glide_speed"):
        assert vs[cid][1].status == "refused", cid
        assert vs[cid][1].missing_calibrations, cid


# ======================= registry facts are tied to the actual code =============================================

def test_implemented_models_need_exact_commit_files_and_a_matching_tree_hash():
    base = model_to_json(default_registry().models["glide_pointmass"])
    for mut in (lambda r: r.pop("commit"), lambda r: r.pop("files"), lambda r: r.pop("source_sha256"),
                lambda r: r.update(source_sha256="0" * 64),
                lambda r: r["files"].update({"x.py": "nothex"}), lambda r: r.update(files={})):
        o = json.loads(json.dumps(base))
        mut(o["reference"])
        with pytest.raises(CouplingError):
            model_from_json(o)
    assert model_from_json(json.loads(json.dumps(base))).reference["source_sha256"] == tree_sha256(base["reference"]["files"])


def test_default_models_point_at_the_exact_branches_and_commits_named_by_root():
    refs = {m.model_id: (m.reference["branch"], m.reference["commit"]) for m in default_registry().models.values()}
    assert refs == {
        "flying_fish_constraints": ("work/guilds-engineering", "948c2e1"),
        "glide_pointmass": ("work/nca-glide", "87e72f9"),
        "fin_load_bridge": ("work/fin-mechanics", "72df07c"),
        "finbeam_euler_bernoulli": ("work/fin-mechanics", "72df07c"),
        "rdfield_nonlinear_sweep": ("work/nca-glide", "87e72f9"),
        "collier1996_two_cell": ("work/biomodels", "abf1838")}
    rd = default_registry().models["rdfield_nonlinear_sweep"].reference
    assert rd["upstream_rows_sha256"].startswith("a32c2bf7") and rd["upstream_prereg_commit"].startswith("cb27cf2")


def _git_has(commit):
    import subprocess
    return subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", commit], capture_output=True).returncode == 0


def test_every_recorded_file_hash_matches_the_commit_when_the_commit_is_available():
    seen = 0
    for m in default_registry().models.values():
        r = verify_reference_sources(m, REPO)
        assert r["ok"] is not False, r                      # never a mismatch; None only when the commit is absent
        seen += r["ok"] is True
    if not _git_has("72df07c"):
        pytest.skip("source commits are not in this object store; hashes not re-verified")
    assert seen == 6


def test_a_tampered_file_hash_is_detected():
    if not _git_has("72df07c"):
        pytest.skip("source commits are not in this object store")
    base = model_to_json(default_registry().models["fin_load_bridge"])
    path = next(iter(base["reference"]["files"]))
    base["reference"]["files"][path] = "0" * 64
    base["reference"]["source_sha256"] = tree_sha256(base["reference"]["files"])   # internally consistent forgery
    forged = model_from_json(base)
    assert verify_reference_sources(forged, REPO)["ok"] is False


ANCHORS = {   # a string from each model's declared ports that must appear in the referenced source text
    "flying_fish_constraints": ("def solve", "level_lift_proxy"),
    "glide_pointmass": ("release_speed_from_witness", "CL_max", "1.5 *"),
    "fin_load_bridge": ("p_lift_proxy", "q_line", "L_ray", "ray_length_fraction_of_semispan", "tributary_width_m"),
    "finbeam_euler_bernoulli": ("def solve_checked", "def tip_deflection_uniform", "ASSUMED_RANGE_NOT_MEASURED"),
    "rdfield_nonlinear_sweep": ("SAVE_EVERY_TAU", "dimensionless", "zero-flux"),
    "collier1996_two_cell": ("replay_collier1996", "delta1", "delta2", "_asym"),
}


def test_declared_ports_are_anchored_in_the_referenced_source_text():
    import subprocess
    if not _git_has("72df07c"):
        pytest.skip("source commits are not in this object store")
    reg = default_registry()
    extra = {"finbeam_euler_bernoulli": ["engineering/fin_mechanics/README.md"]}
    for mid, needles in ANCHORS.items():
        ref = reg.models[mid].reference
        paths = list(ref["files"]) + extra.get(mid, [])
        text = "".join(subprocess.run(["git", "-C", str(REPO), "show", f"{ref['commit']}:{p}"], capture_output=True,
                                      text=True).stdout for p in paths)
        for n in needles:
            assert n in text, (mid, n)


def test_port_caveat_blocks_identity_composition_but_not_a_calibration():
    ok = pair(port("o", "out", quantity="q"), port("i", "in", quantity="q"))
    assert validate_coupling(ok, Coupling("c", "src.o", "dst.i", **IDENT)).status == "composable"
    for side in ("o", "i"):
        kw = {"o": dict(), "i": dict()}
        src = replace(port("o", "out", quantity="q"), caveat="proxy" if side == "o" else "")
        dst = replace(port("i", "in", quantity="q"), caveat="declared" if side == "i" else "")
        v = validate_coupling(pair(src, dst), Coupling("c", "src.o", "dst.i", **IDENT))
        assert v.status == "scenario" and v.checks["caveats"].startswith("scenario:"), side
    # a registered, structurally complete calibration CAN compose a caveated pair
    src = replace(port("o", "out", kind="model_units", unit="model units", quantity="pattern wavelength", d=None,
                       bounds=B0(1, 5)), caveat="proxy")
    dst = port("i", "in", quantity="pattern wavelength", unit="mm", d=dim(m=1), bounds=B0(0, 10000))
    reg = pair(src, dst)
    reg.add_calibration(cal())
    v = validate_coupling(reg, CAL_C)
    assert v.status == "composable" and v.checks["caveats"].startswith("noted:")


def test_caveat_round_trips_through_the_interface_json_and_defaults_to_empty():
    m = default_registry().models["fin_load_bridge"]
    j = json.loads(json.dumps(model_to_json(m)))
    assert any(p["caveat"] for p in j["ports"]) and model_from_json(j) == m
    for p in j["ports"]:
        p.pop("caveat")
    assert all(p.caveat == "" for p in model_from_json(j).ports)       # older files without the key still parse
