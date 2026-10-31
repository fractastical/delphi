"""Pressure -> fin-ray traction -> line load -> deflection: contract, conservation and controls.

Every expected value here is computed independently of the code under test (closed forms written
out by hand, or the existing fin_mechanics bridge), so a mutated integrator is detected.
"""
import copy
from fractions import Fraction

import pytest

from engineering.coupled_mechanics import SCHEMA_PRESSURE_V2, cases, couple, traction
from engineering.coupled_mechanics.contract import canonical_sha, parse_pressure, parse_target
from engineering.fin_mechanics import beam
from engineering.fin_mechanics.load_bridge import Refusal


def refused(code, rec, tgt=None):
    with pytest.raises(Refusal) as e:
        couple.run(rec, tgt or cases.target())
    assert e.value.code == code, e.value


# ------------------------------------------------------------------ analytic integration
def test_uniform_pressure_reproduces_the_existing_bridge_exactly():
    b = cases.illustration_bridge()
    r = couple.run(cases.analytic_record("uniform"), cases.target())
    assert all(Fraction(x) == Fraction(b["exact"]["q_line_N_per_m"]) for x in r["stations"]["q_N_per_m"])
    assert Fraction(r["resultants_exact"]["F_N"]) == Fraction(b["exact"]["F_total_N"])
    L = Fraction(b["exact"]["L_ray_m"])
    assert Fraction(r["resultants_exact"]["M_root_Nm"]) == Fraction(b["exact"]["F_total_N"]) * L / 2
    q, EI = float(Fraction(b["exact"]["q_line_N_per_m"])), 1e-6
    assert r["deflection"]["EI_lo"]["tip_m"] == pytest.approx(q * float(L) ** 4 / (8 * EI), rel=1e-9)


@pytest.mark.parametrize("profile,centroid", [("root_heavy", Fraction(1, 3)), ("tip_heavy", Fraction(2, 3))])
def test_linear_pressure_keeps_force_and_puts_the_moment_at_the_centroid(profile, centroid):
    b = cases.illustration_bridge()
    F = Fraction(b["exact"]["F_total_N"])
    L = Fraction(b["exact"]["L_ray_m"])
    r = couple.run(cases.analytic_record(profile), cases.target())
    assert Fraction(r["resultants_exact"]["F_N"]) == F
    assert Fraction(r["resultants_exact"]["M_root_Nm"]) == F * centroid * L


def test_linear_load_tip_matches_hand_closed_forms():
    # q = q0 (1 - s/L): w(L) = q0 L^4 / (30 EI);  q = q0 s/L: w(L) = 11 q0 L^4 / (120 EI)
    b = cases.illustration_bridge()
    q0 = 2 * float(Fraction(b["exact"]["q_line_N_per_m"]))
    L = float(Fraction(b["exact"]["L_ray_m"]))
    EI = 1e-5
    for profile, coef in (("root_heavy", 1 / 30), ("tip_heavy", 11 / 120)):
        r = couple.run(cases.analytic_record(profile), cases.target(n_elements=128))
        ref = coef * q0 * L**4 / EI
        assert r["deflection"]["EI_hi"]["tip_moment_area_reference_m"] == pytest.approx(ref, rel=1e-12)
        assert r["deflection"]["EI_hi"]["tip_m"] == pytest.approx(ref, rel=1e-4)


def test_mesh_transfer_conserves_force_exactly_and_moment_to_second_order():
    g = couple.grid_study(cases.analytic_record("tip_heavy"), cases.target())
    for lev in g["levels"]:
        r = couple.run(cases.analytic_record("tip_heavy"), cases.target(n_elements=lev["n_elements"]))
        assert r["conservation"]["mesh_force_rel_diff"] == 0.0
    assert all(1.8 < o < 2.2 for o in g["observed_order"]), g


def test_bending_moment_is_exact_statics():
    s = [Fraction(0), Fraction(1, 2), Fraction(1)]
    q = [Fraction(3), Fraction(3), Fraction(3)]
    # uniform q on [0,1]: M(x) = q (1-x)^2 / 2
    for x in (Fraction(0), Fraction(1, 4), Fraction(3, 4), Fraction(1)):
        assert traction.bending_moment(s, q, x) == 3 * (1 - x) ** 2 / 2


# ------------------------------------------------------------------ controls
def test_disabled_load_gives_exactly_zero():
    r = couple.run(couple.disabled_load(cases.analytic_record("uniform")), cases.target())
    assert r["resultants_float"] == {"F_N": 0.0, "M_root_Nm": 0.0}
    for end in r["deflection"].values():
        assert end["tip_m"] == 0.0 and end["max_abs_slope_rad"] == 0.0


def test_EI_interval_scales_exactly_inverse():
    r = couple.run(cases.analytic_record("root_heavy"), cases.target())
    lo, hi = r["deflection"]["EI_lo"], r["deflection"]["EI_hi"]
    ratio = float(Fraction(hi["EI_Nm2"]) / Fraction(lo["EI_Nm2"]))
    assert lo["tip_m"] / hi["tip_m"] == pytest.approx(ratio, rel=1e-9)
    assert lo["tip_m"] > hi["tip_m"] > 0


def test_small_deformation_flag_is_carried_not_repaired():
    r = couple.run(cases.analytic_record("uniform"), cases.target())
    lo = r["deflection"]["EI_lo"]
    tip_over_L = abs(lo["tip_m"]) / float(Fraction(r["L_m"]))
    assert lo["validity"]["valid"] == (tip_over_L <= 0.1 and lo["max_abs_slope_rad"] <= 0.2)


def test_stress_needs_a_declared_section():
    r = couple.run(cases.analytic_record("uniform"), cases.target())
    assert r["stress"] is None and r["stress_status"].startswith("SECTION_NOT_DECLARED")
    sec = {"c_m": "1/2000", "I_m4": "1e-14", "status": "assumed"}
    r = couple.run(cases.analytic_record("uniform"), cases.target(section=sec))
    b = cases.illustration_bridge()
    M = float(Fraction(b["exact"]["F_total_N"]) * Fraction(b["exact"]["L_ray_m"]) / 2)
    assert r["stress"]["sigma_max_Pa"] == pytest.approx(M * 5e-4 / 1e-14, rel=1e-12)


# ------------------------------------------------------------------ refusals
def _patch(path, value, profile="uniform"):
    rec = cases.analytic_record(profile)
    d = rec
    keys = path.split(".")
    for k in keys[:-1]:
        d = d[int(k)] if isinstance(d, list) else d[k]
    d[keys[-1]] = value
    return rec


@pytest.mark.parametrize("path,value,code", [
    ("pressure.unit", "lattice", "WRONG_PRESSURE_UNIT"),
    ("pressure.kind", "model_units", "WRONG_PRESSURE_UNIT"),
    ("frame.length_unit", "mm", "WRONG_LENGTH_UNIT"),
    ("frame.id", "windtunnel/sagittal-xz", "FRAME_MISMATCH"),
    ("member.tip_m", ["0.1", "0", "0"], "GEOMETRY_MISMATCH"),
    ("member.root_m", ["0", "0", "1/1000"], "GEOMETRY_MISMATCH"),
    ("member.normal", ["1", "0", "0"], "BAD_NORMAL"),
    ("member.normal", ["0", "0", "2"], "BAD_NORMAL"),
    ("stations.0.p_neg_Pa", 1.5, "FLOAT_INPUT"),
    ("tributary.status", "guessed", "TRIBUTARY_WIDTH"),
    ("tributary.width_m", "0", "NON_POSITIVE"),
    ("time.kind", "concurrent", "BAD_TIME"),
    ("schema", "frontier.coupled.member-pressure/0", "BAD_SCHEMA"),
])
def test_wrong_unit_or_geometry_is_refused(path, value, code):
    refused(code, _patch(path, value))


def test_stations_must_cover_exactly_the_member():
    rec = cases.analytic_record()
    rec["stations"] = rec["stations"][:-1]
    refused("STATION_COVERAGE", rec)
    rec = cases.analytic_record()
    rec["stations"][0]["s_m"] = "1/1000"
    refused("STATION_COVERAGE", rec)
    rec = cases.analytic_record()
    rec["stations"][2], rec["stations"][3] = rec["stations"][3], rec["stations"][2]
    refused("STATION_COVERAGE", rec)


def test_a_2d_section_cannot_stand_in_for_a_whole_3d_fin():
    rec = cases.analytic_record()
    rec["source"].update(evidence_kind="simulated", fields_sha256="a" * 64, geometry_sha256="b" * 64)
    rec["dimensionality"] = "2d-extrusion"
    rec["resolution"]["cells_across_member_thickness"] = 4
    refused("SAGITTAL_2D_NOT_3D", rec, cases.target(claim="whole_fin_3d"))
    r = couple.run(rec, cases.target())
    assert r["scope"].startswith("2d-extrusion section scenario")


def test_simulated_field_must_resolve_the_member():
    rec = cases.analytic_record()
    rec["source"].update(evidence_kind="simulated", fields_sha256="a" * 64, geometry_sha256="b" * 64)
    rec["dimensionality"] = "3d"
    for across in (None, 0, 1):
        rec["resolution"]["cells_across_member_thickness"] = across
        refused("MEMBER_UNRESOLVED", copy.deepcopy(rec))
    rec["resolution"]["cells_across_member_thickness"] = 2
    assert couple.run(rec, cases.target(claim="whole_fin_3d"))["scope"] == "3d member traction"


def test_simulated_source_needs_field_and_geometry_hashes():
    rec = cases.analytic_record()
    rec["source"]["evidence_kind"] = "simulated"
    rec["dimensionality"] = "3d"
    rec["resolution"]["cells_across_member_thickness"] = 3
    refused("BAD_HASH", rec)


def test_target_refuses_bad_EI_and_units():
    t = cases.target()
    t["EI"] = dict(t["EI"], lo_Nm2="1e-4", hi_Nm2="1e-6")
    with pytest.raises(Refusal, match="BAD_EI_RANGE"):
        parse_target(t)
    t = cases.target()
    t["frame_length_unit"] = "mm"
    with pytest.raises(Refusal, match="WRONG_LENGTH_UNIT"):
        parse_target(t)


def test_parse_pressure_converts_Pa_times_m_to_N_per_m():
    rec = cases.analytic_record("uniform")
    p = parse_pressure(rec, parse_target(cases.target()))
    b = cases.illustration_bridge()
    assert p["q_N_per_m"][0] == Fraction(b["exact"]["p_Pa"]) * Fraction(b["exact"]["w_t_m"])


def test_beam_module_is_the_existing_one():
    # The coupling must reuse fin_mechanics' FEM, not a second solver.
    assert couple.beam is beam


# ------------------------------------------------------------------ member-pressure/2: per-station widths
# Closed forms below are written out by hand for q(s) = jump(s) * w(s) with w linear in s:
#   w(s) = w0 + (w1 - w0) u,  u = s/L
#   uniform jump p:      F = p L (w0 + w1)/2,             M = p L^2 (w0/6 + w1/3)
#   tip-heavy 2 p u:     F = 2 p L (w0/2 + (w1 - w0)/3),  M = 2 p L^2 (w0/3 + (w1 - w0)/4)
# The tip-heavy q is quadratic, so the contract's linear-between-stations F has the trapezoid error
# L h^2 q''/12 exactly, with q'' = 4 p (w1 - w0)/L^2.
def _bridge_pwL():
    b = cases.illustration_bridge()
    return Fraction(b["exact"]["p_Pa"]), Fraction(b["exact"]["w_t_m"]), Fraction(b["exact"]["L_ray_m"])


def v2(rec, width_of_u, s_labels=None):
    """A /1 analytic record rewritten as /2 with w(u) at each station (test helper, not a producer)."""
    rec = copy.deepcopy(rec)
    L = Fraction(rec["member"]["tip_m"][0])
    s = [st["s_m"] for st in rec["stations"]]
    widths = [{"s_m": lab, "width_m": str(width_of_u(Fraction(x) / L))} for x, lab in zip(s, s_labels or s)]
    rec["schema"] = SCHEMA_PRESSURE_V2
    rec["tributary"] = {"status": "declared", "unit": "m", "source": "test: linear width",
                        "geometry_sha256": "a" * 64, "widths": widths, "widths_sha256": canonical_sha(widths)}
    return rec


def _linear_width():
    _, w, _ = _bridge_pwL()
    w0, w1 = w / 2, 3 * w / 2
    return w0, w1, (lambda u: w0 + (w1 - w0) * u)


def test_v2_variable_width_matches_closed_form_force_and_moment():
    p, _, L = _bridge_pwL()
    w0, w1, wf = _linear_width()
    r = couple.run(v2(cases.analytic_record("uniform", n_stations=4), wf), cases.target())
    assert Fraction(r["resultants_exact"]["F_N"]) == p * L * (w0 + w1) / 2
    assert Fraction(r["resultants_exact"]["M_root_Nm"]) == p * L * L * (w0 / 6 + w1 / 3)
    assert r["tributary_width_m"] == [str(wf(Fraction(i, 3))) for i in range(4)]


@pytest.mark.parametrize("n", [5, 9, 17])
def test_v2_curved_load_error_is_the_trapezoid_term_exactly(n):
    p, _, L = _bridge_pwL()
    w0, w1, wf = _linear_width()
    r = couple.run(v2(cases.analytic_record("tip_heavy", n_stations=n), wf), cases.target())
    F_closed = 2 * p * L * (w0 / 2 + (w1 - w0) / 3)
    h = L / (n - 1)
    assert Fraction(r["resultants_exact"]["F_N"]) - F_closed == L * h * h * (4 * p * (w1 - w0) / (L * L)) / 12
    M_closed = 2 * p * L * L * (w0 / 3 + (w1 - w0) / 4)
    assert abs(Fraction(r["resultants_exact"]["M_root_Nm"]) / M_closed - 1) < Fraction(1, (n - 1) ** 2)


def test_v2_constant_width_reduces_to_v1_exactly():
    _, w, _ = _bridge_pwL()
    for profile in ("uniform", "root_heavy", "tip_heavy"):
        a = couple.run(cases.analytic_record(profile), cases.target())
        b = couple.run(v2(cases.analytic_record(profile), lambda u: w), cases.target())
        assert a["stations"] == b["stations"] and a["resultants_exact"] == b["resultants_exact"]
        assert a["deflection"]["EI_lo"]["tip_m"] == b["deflection"]["EI_lo"]["tip_m"]
        assert a["tributary_width_m"] == str(w) and b["tributary_width_m"] == [str(w)] * 9


def test_v2_mutated_width_pairing_is_caught():
    p, _, L = _bridge_pwL()
    w0, w1, wf = _linear_width()
    base = cases.analytic_record("uniform", n_stations=4)
    # values reversed against their stations, labels kept: the contract cannot know, the closed form does
    rev = v2(base, lambda u: wf(1 - u))
    r = couple.run(rev, cases.target())
    assert Fraction(r["resultants_exact"]["M_root_Nm"]) != p * L * L * (w0 / 6 + w1 / 3)
    # labels that travel with the reversed values no longer align with the stations: refused
    s = [st["s_m"] for st in base["stations"]]
    refused("TRIBUTARY_ALIGNMENT", v2(base, wf, s_labels=s[::-1]))
    short = v2(base, wf)
    short["tributary"]["widths"] = short["tributary"]["widths"][:-1]
    short["tributary"]["widths_sha256"] = canonical_sha(short["tributary"]["widths"])
    refused("TRIBUTARY_ALIGNMENT", short)


@pytest.mark.parametrize("edit,code", [
    (lambda t: t["widths"][1].update(width_m="0"), "NON_POSITIVE"),
    (lambda t: t["widths"][2].update(width_m="-1/1000"), "NON_POSITIVE"),
    (lambda t: t["widths"][0].update(width_m=0.001), "FLOAT_INPUT"),
    (lambda t: t.update(unit="mm"), "WRONG_LENGTH_UNIT"),
    (lambda t: t.update(geometry_sha256=None), "BAD_HASH"),
    (lambda t: t.update(width_m="1/1000"), "TRIBUTARY_WIDTH"),
])
def test_v2_widths_must_be_positive_exact_metres_with_provenance(edit, code):
    rec = v2(cases.analytic_record("uniform", n_stations=4), _linear_width()[2])
    edit(rec["tributary"])
    rec["tributary"]["widths_sha256"] = canonical_sha(rec["tributary"]["widths"])
    refused(code, rec)


def test_v2_widths_hash_is_checked():
    rec = v2(cases.analytic_record("uniform", n_stations=4), _linear_width()[2])
    rec["tributary"]["widths"][1]["width_m"] = "1/100"  # edited after hashing
    refused("BAD_HASH", rec)


# ------------------------------------------------------------------ the actual 2D flow receipt
import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

from engineering.coupled_mechanics import windtunnel_receipt as wt  # noqa: E402

ART = Path(wt.ROOT) / "artifacts" / "coupled-mechanics"


@pytest.fixture(scope="module")
def receipt():
    return wt.load()


def test_receipt_pins_are_checked_and_fail_closed(tmp_path):
    d = tmp_path / "baseline"
    shutil.copytree(wt.RECEIPT_DIR, d)
    res = json.loads((d / "result.json").read_text())
    res["mean_Cl_last20pct"] = 9.0
    (d / "result.json").write_text(json.dumps(res))
    with pytest.raises(wt.ReceiptError, match="manifest pin"):
        wt.load(d, wt.MANIFEST)


def test_Pa_mapping_is_the_receipts_own(receipt):
    req = receipt["request"]
    assert receipt["pa_per_lattice_density"] == pytest.approx(
        req["density_kg_m3"] * (req["speed_m_s"] / receipt["result"]["lattice_speed"]) ** 2 / 3, rel=1e-15)
    assert receipt["window"].sum() == 17  # convective time 3.2..4.0, the last 20 percent


def test_tail_strip_is_rederived_from_the_mask(receipt):
    s = receipt["solid"]
    one_cell = [i for i in range(s.shape[0]) if s[i].sum() == 1 and s[i, wt.TAIL_ROW]
                and not s[i, wt.TAIL_ROW + 1] and not s[i, wt.TAIL_ROW - 1]]
    assert tuple(one_cell) == wt.TAIL_COLUMNS
    strip = wt.tail_strip(receipt)
    assert strip["cells_across"] == 1 and strip["fluid_on_both_faces"]


def test_actual_field_is_refused_for_every_fin_member(receipt):
    rec, tgt = wt.tail_record_and_target(receipt)
    assert rec["pressure"]["unit"] == "Pa" and rec["source"]["fields_sha256"] == receipt["sha256"]["fields"]
    refused("MEMBER_UNRESOLVED", rec, tgt)
    refused("SAGITTAL_2D_NOT_3D", rec, dict(tgt, claim="whole_fin_3d"))
    refused("FRAME_MISMATCH", rec, cases.target(claim="whole_fin_3d"))
    # Only the resolution blocks the 2D-section scenario: a mutated record claiming 2 cells passes,
    # which is why the count must come from the mask and not from the producer's say-so.
    fake = copy.deepcopy(rec)
    fake["resolution"]["cells_across_member_thickness"] = 2
    assert couple.run(fake, tgt)["scope"].startswith("2d-extrusion")


def test_pressure_face_integral_has_the_receipts_lift_sign_and_scale(receipt):
    f = wt.surface_pressure_force(receipt)
    assert f["pressure_lift_N_per_m"] > 0 and f["receipt_lift_N_per_m"] > 0
    assert f["pressure_drag_N_per_m"] > 0
    # Diagnostic only: pressure-only is not expected to equal the momentum-exchange total.
    assert 0.1 < f["pressure_over_receipt_lift"] < 10


def test_committed_artifacts_are_current(receipt):
    from engineering.coupled_mechanics import run as runner
    result, _ = runner.build()
    committed = json.loads((ART / "result.json").read_text())
    assert committed["actual_flow_receipt"]["attempts"] == result["actual_flow_receipt"]["attempts"]
    assert committed["one_way_comparison"] == json.loads(json.dumps(result["one_way_comparison"]))
    manifest = json.loads((ART / "manifest.json").read_text())
    for name, pin in manifest["outputs"].items():
        assert hashlib.sha256((ART / name).read_bytes()).hexdigest() == pin["sha256"], name
    for name, pin in manifest["inputs"].items():
        assert hashlib.sha256((Path(wt.ROOT) / name).read_bytes()).hexdigest() == pin, name
    for name, pin in manifest["code_files"].items():
        assert hashlib.sha256((Path(wt.ROOT) / name).read_bytes()).hexdigest() == pin, name
    assert np.isfinite(committed["actual_flow_receipt"]["surface_pressure_force_diagnostic"]["pressure_lift_N_per_m"])
