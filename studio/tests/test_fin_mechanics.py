"""Tests for engineering/fin_mechanics (SIMULATED Euler-Bernoulli cantilever fin-ray surrogate)."""
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from engineering.fin_mechanics import beam, sweep
from engineering.fin_mechanics.load_bridge import Refusal, bridge

PKG = Path(beam.__file__).resolve().parent
REQ = json.loads((PKG / "example_request.json").read_text())


def req(**patch):
    r = copy.deepcopy(REQ)
    for path, v in patch.items():
        d = r
        keys = path.split(".")
        for k in keys[:-1]:
            d = d[k]
        d[keys[-1]] = v
    return r


# ------------------------------------------------------------------ analytic controls
def test_tip_load_control_fem_matches_PL3_over_3EI():
    P, L, EI = 0.37, 0.15, 2.5e-4
    sol = beam.solve_cantilever(L, EI, 0.0, 16, tip_force=P)
    assert sol.tip == pytest.approx(P * L**3 / (3 * EI), rel=1e-9)
    assert sol.max_abs_slope == pytest.approx(P * L**2 / (2 * EI), rel=1e-9)


def test_uniform_load_control_fem_matches_qL4_over_8EI():
    q, L, EI = 0.153125, 0.15, 3e-3
    sol = beam.solve_cantilever(L, EI, q, 16)
    assert sol.tip == pytest.approx(q * L**4 / (8 * EI), rel=1e-9)
    assert sol.max_abs_slope == pytest.approx(q * L**3 / (6 * EI), rel=1e-9)


def test_profile_matches_closed_form_curves():
    q, L, EI = 2.0, 1.0, 5.0
    xs = np.linspace(0, L, 41)
    w, s = beam.solve_cantilever(L, EI, q, 32).evaluate(xs)
    tip = beam.tip_deflection_uniform(q, L, EI)
    assert np.max(np.abs(w - beam.w_uniform(xs, q, L, EI))) < 1e-6 * tip  # O(h^4) interpolation error
    # slope is the derivative of the closed form
    dx = 1e-6
    num = (beam.w_uniform(xs + dx, q, L, EI) - beam.w_uniform(xs - dx, q, L, EI)) / (2 * dx)
    assert np.allclose(s, num, rtol=1e-4, atol=1e-6)
    w2, _ = beam.solve_cantilever(L, EI, 0.0, 4, tip_force=3.0).evaluate(xs)
    assert np.allclose(w2, beam.w_point_load(xs, 3.0, L, EI), rtol=1e-9, atol=1e-12)


def test_closed_forms_agree_with_independent_quadrature():
    res = beam.control_residuals()
    assert max(v for c in res.values() for k, v in c.items() if k.endswith("residual")) < 1e-12


def test_mutated_formulas_fail_the_controls():
    mutant_tip = lambda P, L, EI: P * L**2 / (3 * EI)       # L^3 -> L^2
    mutant_uni = lambda q, L, EI: q * L**4 / (6 * EI)        # 8 -> 6
    bad = beam.control_residuals(tip_fn=mutant_tip, uniform_fn=mutant_uni)
    assert max(c["tip_load_rel_residual"] for c in bad.values()) > 0.1
    assert max(c["uniform_rel_residual"] for c in bad.values()) > 0.1
    # case0 (L=1) hides the L-exponent mutation, which is why more than one L is used
    assert bad["case0"]["tip_load_rel_residual"] < 1e-12


def test_mutated_fem_load_vector_fails_control(monkeypatch):
    real = beam.solve_cantilever
    sol = real(0.15, 1e-3, 0.5, 8)
    exact = beam.tip_deflection_uniform(0.5, 0.15, 1e-3)
    assert abs(sol.tip - exact) / exact < 1e-9
    wrong = real(0.15, 1e-3, 0.5 * 1.01, 8)  # 1 % load error is far above the control tolerance
    assert abs(wrong.tip - exact) / exact > 1e-3


# ------------------------------------------------------------------ convergence
def test_grid_refinement_orders():
    c = sweep.convergence_study(0.153125, 0.15, 1e-3)
    ords = c["uniform_constant_EI"]["observed_order_profile"]
    assert all(abs(o - 4.0) < 0.15 for o in ords[:3])  # Hermite interpolation, O(h^4)
    t = c["tapered_EI_midpoint_rule"]["observed_order"]
    assert all(1.9 < o < 2.1 for o in t)               # midpoint-EI rule, O(h^2)
    errs = c["tapered_EI_midpoint_rule"]["tip_rel_error"]
    assert all(errs[i + 1] < errs[i] for i in range(len(errs) - 1))
    assert "not applicable" in c["time_step"]


# ------------------------------------------------------------------ validity
def test_validity_flag_fires_on_deliberately_large_load():
    L, EI = 0.15, 1e-3
    sol, chk = beam.solve_checked(L, EI, q=5.0, n_el=16)  # tip/L = 5 L^3/(8 EI) >> 0.1
    assert chk["valid"] is False and not chk["tip_ok"]
    assert chk["flag"].startswith("LINEAR_MODEL_INVALID")
    with pytest.raises(beam.SmallDeformationViolation):
        beam.solve_checked(L, EI, q=5.0, n_el=16, strict=True)
    _, ok = beam.solve_checked(L, EI, q=0.01, n_el=16, strict=True)
    assert ok["valid"] and ok["flag"] == "OK"


def test_slope_limit_can_bind_independently():
    chk = beam.check_small_deformation(tip=0.001, max_slope=0.5, L=1.0)
    assert chk["tip_ok"] and not chk["slope_ok"] and not chk["valid"]


def test_critical_EI_is_the_exact_boundary():
    q, L = Fraction(49, 320), Fraction(3, 20)
    crit = sweep.critical_EI(q, L, Fraction(1, 10), Fraction(1, 5))
    ec = float(Fraction(crit["EI_crit_Nm2_exact"]))
    _, at = beam.solve_checked(float(L), ec * (1 + 1e-9), float(q), 32)
    _, below = beam.solve_checked(float(L), ec * (1 - 1e-6), float(q), 32)
    assert at["valid"] and not below["valid"]
    assert crit["binding_limit"] == "tip_over_L"


def test_sweep_reports_invalid_rows_not_silently_dropped():
    res = sweep.run(REQ)
    rows = res["sweep"]["rows"]
    crit = res["critical_stiffness"]["EI_crit_Nm2_float"]
    assert len(rows) == 61
    for r in rows:
        assert r["uniform"]["valid"] == (r["EI_Nm2"] >= crit * (1 - 1e-9))
        assert r["uniform"]["flag"] != "OK" or r["uniform"]["valid"]
    assert res["validity"]["any_invalid"] is True
    assert 0 < res["sweep"]["n_invalid_uniform"] < 61
    # uniform load is the milder case: tip-equivalent deflects 8/3 times more (qL^4/8EI vs qL^4/3EI)
    r0 = rows[10]
    assert r0["tip_equivalent"]["tip_m"] / r0["uniform"]["tip_m"] == pytest.approx(8 / 3, rel=1e-6)


# ------------------------------------------------------------------ units / scaling
def test_dimensional_scaling_laws():
    base = beam.tip_deflection_point_load(1.0, 1.0, 1.0)
    assert beam.tip_deflection_point_load(1.0, 2.0, 1.0) / base == pytest.approx(8.0)   # L^3
    assert beam.tip_deflection_point_load(1.0, 1.0, 2.0) / base == pytest.approx(0.5)   # 1/EI
    assert beam.tip_deflection_point_load(2.0, 1.0, 1.0) / base == pytest.approx(2.0)   # P
    ub = beam.tip_deflection_uniform(1.0, 1.0, 1.0)
    assert beam.tip_deflection_uniform(1.0, 2.0, 1.0) / ub == pytest.approx(16.0)       # L^4
    # unit-consistency: [N][m]^3/[N m^2] = [m] checked via SI-scale invariance: mm-N units give same physical w
    L_m, EI_Nm2, P = 0.15, 1e-3, 0.02
    w_si = beam.tip_deflection_point_load(P, L_m, EI_Nm2)
    w_mm = beam.tip_deflection_point_load(P, L_m * 1e3, EI_Nm2 * 1e6)  # N, mm, N mm^2
    assert w_mm == pytest.approx(w_si * 1e3, rel=1e-12)
    res = sweep.run(REQ)
    assert res["units"] == {"EI": "N m^2", "q_line": "N/m", "p": "Pa", "L": "m", "tip": "m", "slope": "rad"}


# ------------------------------------------------------------------ load bridge
def test_load_bridge_exact_numbers():
    b = bridge(REQ)
    assert b["exact"]["p_Pa"] == "245/16"                  # 0.5*1.225*25*1 = 15.3125 Pa
    assert b["exact"]["q_line_N_per_m"] == "49/320"        # 15.3125 * 0.01
    assert b["exact"]["L_ray_m"] == "3/20"                 # (1/5) * 3/2 / 2
    assert b["exact"]["F_total_N"] == "147/6400"
    assert b["q_line_N_per_m"] == pytest.approx(0.153125)
    assert b["evidence_kind"] == "simulated"
    assert "NOT a measured fin pressure" in b["load_proxy_statement"] or "not a measured fin pressure" in b["load_proxy_statement"]
    assert [s["unit"] for s in b["steps"]] == ["Pa", "Pa", "m", "N/m", "m", "N"]


def test_load_bridge_scales_as_V_squared_and_tributary_width():
    q1 = bridge(REQ)["q_line_N_per_m"]
    r2 = req(**{"candidate.solver_result.witness": {"m": "1/2", "S": "3/8", "b": "3/2", "V": "10"}})
    assert bridge(r2)["q_line_N_per_m"] == pytest.approx(4 * q1)
    r3 = req(**{"fin.tributary_width_m": "1/50"})
    assert bridge(r3)["q_line_N_per_m"] == pytest.approx(2 * q1)


def test_load_bridge_n_rays_alternative_and_exclusivity():
    r = req()
    del r["fin"]["tributary_width_m"]
    r["fin"]["n_rays"] = "150"
    assert bridge(r)["exact"]["w_t_m"] == "1/100"          # b/n = 1.5/150
    r["fin"]["tributary_width_m"] = "1/100"
    with pytest.raises(Refusal) as e:
        bridge(r)
    assert e.value.code == "TRIBUTARY_WIDTH"


@pytest.mark.parametrize("patch,code", [
    ({"candidate.solver_result.status": "infeasible"}, "NOT_FEASIBLE"),
    ({"candidate.units.V": "km/h"}, "UNIT_MISMATCH"),
    ({"candidate.solver_result.witness": {"m": "1/2", "S": "3/8", "b": "3/2", "V": "0"}}, "NON_POSITIVE"),
    ({"candidate.solver_result.witness": {"m": 0.5, "S": "3/8", "b": "3/2", "V": "5"}}, "FLOAT_INPUT"),
    ({"fin.ray_length_fraction_of_semispan": "3/2"}, "RAY_LONGER_THAN_SEMISPAN"),
    ({"fin.CL": "4"}, "CL_OUT_OF_RANGE"),
])
def test_load_bridge_refusals(patch, code):
    with pytest.raises(Refusal) as e:
        bridge(req(**patch))
    assert e.value.code == code


def test_missing_assumption_refused_and_result_is_structured():
    r = req()
    del r["candidate"]["flight_assumptions"]["rho"]
    out = sweep.run(r)
    assert out["verdict"] == "refused" and out["code"] == "MISSING_ASSUMPTION"
    assert out["evidence_kind"] == "simulated"


def test_EI_must_be_declared_assumed():
    out = sweep.run(req(**{"elastic.EI_status": "measured"}))
    assert out["verdict"] == "refused" and out["code"] == "EI_STATUS"


# ------------------------------------------------------------------ result / determinism / manifest
def test_result_contract_fields():
    res = sweep.run(REQ)
    assert res["schema"] == "frontier.finmech.result/1" and res["verdict"] == "ok"
    assert res["evidence_kind"] == "simulated"
    assert len(res["inputs_sha256"]) == 64 and len(res["code_sha256"]) == 64
    assert any("biological feasibility" in s for s in res["not_established"])
    assert any("ASSUMED" in a for a in res["assumptions"])
    assert res["EI_assumed_range"]["status"] == "ASSUMED_RANGE_NOT_MEASURED"
    assert "EI" in res["measurement_question"]["question"]
    assert res["controls"]["max_rel_residual"] < 1e-12
    assert res["controls"]["fem_vs_analytic_max_rel_diff_over_sweep"] < 1e-6
    assert res["convergence"]["uniform_constant_EI"]["observed_order_profile"][0] == pytest.approx(4.0, abs=0.1)
    assert any("bluegill" in s["ref"].lower() or "Alben" in s["ref"] for s in res["sources_read"])


def test_determinism_and_input_sensitivity():
    a, b = sweep.run(REQ), sweep.run(copy.deepcopy(REQ))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    c = sweep.run(req(**{"fin.tributary_width_m": "1/50"}))
    assert c["inputs_sha256"] != a["inputs_sha256"]
    assert c["critical_stiffness"]["EI_crit_Nm2_exact"] != a["critical_stiffness"]["EI_crit_Nm2_exact"]


def test_frame_computation_is_deterministic_and_matches_closed_form():
    from engineering.fin_mechanics import render
    res = sweep.run(REQ)
    plan = render.frame_plan(res)
    assert len(plan) == render.FPS * render.SECONDS
    sub = plan[::40]
    f1, f2 = render.compute_frames(res, sub), render.compute_frames(res, sub)
    assert render.frames_sha256(f1) == render.frames_sha256(f2)
    for f in f1:
        assert np.allclose(f["w"], f["analytic_w"], rtol=1e-5, atol=1e-12)
    assert any(not f["valid"] for f in render.compute_frames(res, plan[::10]))  # flag appears in video frames


def test_committed_artifacts_match_manifest_and_current_code():
    man_path = PKG / "artifacts" / "manifest.json"
    if not man_path.exists():
        pytest.skip("artifacts not rendered yet")
    man = json.loads(man_path.read_text())
    assert man["code_files_sha256"] == sweep.code_hashes(), "re-run render after changing code"
    for name, meta in man["outputs"].items():
        p = PKG / "artifacts" / name
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
        assert p.stat().st_size == meta["bytes"]
    assert man["outputs"]["fin_mechanics.mp4"]["bytes"] < 8_000_000
    assert 10 <= man["video"]["duration_s"] <= 20
    assert man["request_file"]["sha256"] == hashlib.sha256((PKG / "example_request.json").read_bytes()).hexdigest()
    res = json.loads((PKG / "artifacts" / "result.json").read_text())
    assert res["inputs_sha256"] == sweep.sha256_bytes(sweep.canonical(REQ))
