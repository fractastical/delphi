"""Coupling-layer tests. All SYNTHETIC fixtures are labelled 'synthetic test fixture': they exercise the rules and are
never evidence about any organism. The default registry has NO real calibration, and a test pins that."""
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction

import pytest

from engineering.coupling import (
    BASE_UNITS, Assumption, Bounds, Calibration, Coupling, CouplingError, ModelSpec, Port, Provenance, Registry,
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
    ref = None if status == "proposed" else {"repo": "synthetic", "branch": "x", "commit": "y", "path": "z"}
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
    assert m["counts"] == {"composable": 3, "scenario": 1, "refused": 4}
    by = {r["coupling"]["id"]: r["verdict"] for r in m["couplings"]}
    assert [k for k, v in by.items() if v["status"] == "composable"] == ["c01_mass", "c02_area", "c03_span"]
    assert by["c04_speed"]["status"] == "scenario" and "assumption-level" in by["c04_speed"]["label"]
    for k in ("c05_notch_to_fin_stiffness", "c06_notch_to_fin_stiffness_assumed", "c07_rd_wavelength_to_wing_span",
              "c08_fin_deflection_to_glide_speed"):
        assert by[k]["status"] == "refused"
    assert m["calibrations_registered"] == []
    assert "Registered calibrations: NONE" in m["must_display"]


def test_the_notch_to_fin_bridge_cannot_be_made_even_by_naming_an_assumption():
    reg = default_registry()
    v = validate_coupling(reg, [c for c in default_couplings() if c.id == "c06_notch_to_fin_stiffness_assumed"][0])
    assert v.status == "refused" and any("PROPOSED" in r for r in v.reasons)
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
                   "c07_rd_wavelength_to_wing_span", "c08_fin_deflection_to_glide_speed"}
    for p in m["problem_proposals"]:
        assert p["status"] == "proposed" and p["not_a_claim"] is True
        assert p["success"] and p["falsifier"] and p["action_bounds"]["gpu"] is False
        assert p["action_bounds"]["paid_calls"] is False and "GPU submission" in p["action_bounds"]["forbidden"]
        assert "frozen BEFORE" in p["success"]                       # thresholds are slots, not invented values
        assert "whole-filesystem" in " ".join(p["action_bounds"]["allowed_actions"])
    p8 = [p for p in m["problem_proposals"] if p["source_coupling"] == "c08_fin_deflection_to_glide_speed"][0]
    assert any("finbeam_euler_bernoulli is implemented" in x for x in p8["prerequisites"])


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
