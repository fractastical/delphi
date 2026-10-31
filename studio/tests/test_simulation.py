import copy
import math

import numpy as np
import pytest

from engineering.simulation import evaluate as EV
from engineering.simulation import glide, sweep
from engineering.simulation.schema import G

GOOD = {"schema": "frontier.glide.candidate/1", "witness": {"m": "1/10", "S": "1/50", "b": "2/5", "V": "9"},
        "flight_assumptions": {"rho": {"value": "1.225", "unit": "kg/m^3", "source": "design_assumption"},
                               "CL_max": {"value": "6/5", "unit": "1", "source": "design_assumption"},
                               "CD0": {"value": "3/50", "unit": "1", "source": "design_assumption"},
                               "e": {"value": "4/5", "unit": "1", "source": "design_assumption"},
                               "release_height_m": {"value": "1", "unit": "m", "source": "design_assumption"}}}


def test_controls_pass():
    out = sweep.controls("/tmp/_glide_controls_test")
    assert out["all_pass"]


def test_equilibrium_is_analytic():
    CL = float(glide.cl_command(1.2, 0.06, 0.8, 8.0))
    eq = glide.equilibrium(0.1, 0.02, 8.0, 1.225, CL, 0.06, 0.8)
    assert eq["L_over_D"] == pytest.approx(0.5 * math.sqrt(math.pi * 0.8 * 8.0 / 0.06), rel=1e-12)   # (L/D)max = 1/2 sqrt(pi e AR / CD0)


def test_dt_halving_converges_second_order_or_better():
    r1 = glide.integrate(0.1, 0.02, 8.0, 1.225, 1.1, 0.06, 0.8, 1.0, 12.0, dt=0.004)["range_m"][0]
    r2 = glide.integrate(0.1, 0.02, 8.0, 1.225, 1.1, 0.06, 0.8, 1.0, 12.0, dt=0.002)["range_m"][0]
    r3 = glide.integrate(0.1, 0.02, 8.0, 1.225, 1.1, 0.06, 0.8, 1.0, 12.0, dt=0.001)["range_m"][0]
    assert abs(r2 - r3) < abs(r1 - r2) + 1e-12 and abs(r2 - r3) / r3 < 1e-4


@pytest.mark.parametrize("mutate,code", [
    (lambda c: c["flight_assumptions"].pop("CD0"), "MISSING_ASSUMPTION"),
    (lambda c: c["flight_assumptions"].pop("rho"), "MISSING_ASSUMPTION"),
    (lambda c: c["witness"].update(m="0"), "NONPHYSICAL_INPUT"),
    (lambda c: c["witness"].update(S="-1/50"), "NONPHYSICAL_INPUT"),
    (lambda c: c["witness"].pop("b"), "MISSING_INPUT"),
    (lambda c: c["witness"].update(V=9.0), "INVALID_INPUT"),                       # float refused
    (lambda c: c["flight_assumptions"]["CL_max"].update(value="5"), "NONPHYSICAL_INPUT"),
    (lambda c: c["flight_assumptions"]["e"].update(value="1.5"), "NONPHYSICAL_INPUT"),
    (lambda c: c["flight_assumptions"]["rho"].update(unit="g/cm^3"), "INVALID_ASSUMPTION"),
    (lambda c: c["flight_assumptions"]["rho"].update(source="trust me"), "INVALID_ASSUMPTION"),
    (lambda c: c.update(units={"m": "g", "S": "m^2", "b": "m", "V": "m/s"}), "UNIT_MISMATCH"),
    (lambda c: c["witness"].update(b="10"), "NONPHYSICAL_INPUT"),                  # AR = 5000
    (lambda c: c.update(schema="other/1"), "SCHEMA_MISMATCH"),
])
def test_refusals(mutate, code):
    c = copy.deepcopy(GOOD)
    mutate(c)
    r = EV.evaluate(c)
    assert r["verdict"] == "refused" and r["code"] == code


def test_solver_not_feasible_refused():
    c = copy.deepcopy(GOOD)
    c["solver_result"] = {"status": "unsat", "witness": None}
    assert EV.evaluate(c)["code"] == "SOLVER_NOT_FEASIBLE"


def test_receipt_shape_and_counterexample():
    c = copy.deepcopy(GOOD)
    c["required_glide_range_m"] = "68"
    r = EV.evaluate(c, mc_n=40)
    assert r["verdict"] == "counterexample" and r["counterexample"]["code"] == "RANGE_SHORTFALL"
    assert r["numerics"]["converged"] and r["evidence_kind"] == "simulated" and "biological feasibility of any fin or body" in r["not_established"]
    assert r["receipt_sha256"] and r["inputs"]["assumption_sources"]["CD0"] == "design_assumption"
    c2 = copy.deepcopy(GOOD)
    r2 = EV.evaluate(c2, mc_n=40)
    assert r2["verdict"] == "consistent"


def test_below_stall_counterexample_from_witness_speed():
    c = copy.deepcopy(GOOD)
    c["witness"]["V"] = "6"
    c["release_speed_from_witness"] = True
    r = EV.evaluate(c, mc_n=20)
    assert r["verdict"] == "counterexample" and r["counterexample"]["code"] == "BELOW_STALL"


def test_mass_drops_out_at_fixed_wing_loading_and_ar():
    # structural property of the point-mass model with constant coefficients (documented finding)
    WL, AR = 50.0, 8.0
    rs = []
    for m in (0.01, 0.1, 0.5):
        S = m * G / WL
        CL = float(glide.cl_command(1.2, 0.06, 0.8, AR))
        Vs = glide.stall_speed(m, S, 1.225, 1.2)
        rs.append(float(glide.integrate(m, S, AR, 1.225, CL, 0.06, 0.8, 1.0, 1.5 * Vs)["range_m"][0]))
    assert max(rs) / min(rs) - 1 < 1e-9


def test_pareto_mask_exact():
    objs = np.array([[1, 1, 1], [2, 2, 2], [0, 3, 3], [1, 1, 1.0001]], float)
    assert list(sweep.pareto_mask(objs)) == [True, False, True, False]


def test_controlled_baselines_are_dataset_grounded_and_cross_checked():
    from engineering.simulation import controlled as CT
    for M in CT.MASSES:
        b = CT.baseline("Cypselurus", M)
        assert b["WL_cross_check_rel_diff"] < 0.10 and b["WL_in_range"]          # Table I implied WL within 10% of the separate Table II fit
    assert not CT.baseline("Exocoetus", 0.4)["WL_in_range"]                    # excluded by the envelope rule, not silently kept


def test_controlled_sink_rate_falls_with_area_and_aspect_ratio_independent_of_release_speed():
    from engineering.simulation import controlled as CT
    pol = CT.POLARS["P1_nominal"]
    b = CT.baseline("Cypselurus", 0.05)
    sinks = []
    for fs in (0.85, 1.0, 1.3):
        d = {"m": 0.05, "S": b["S"] * fs, "AR": b["AR"]}
        sinks.append(CT.metrics(d, 12.0, pol)[2])
    assert sinks[0] > sinks[1] > sinks[2]
    d = {"m": 0.05, "S": b["S"], "AR": b["AR"]}
    assert CT.metrics(d, 12.0, pol)[2] == CT.metrics(d, 20.0, pol)[2]


def test_controlled_stall_constraint_marks_heavy_baseline_infeasible_at_12ms():
    from engineering.simulation import controlled as CT
    b = CT.baseline("Cypselurus", 0.4)
    assert CT.metrics(b, 12.0, CT.POLARS["P1_nominal"])[1] > 12.0               # level stall speed exceeds the release speed


def test_video_artifacts_manifest_consistent():
    import hashlib, json, pathlib
    d = pathlib.Path(__file__).resolve().parent.parent / "engineering" / "simulation" / "video"
    for man, vid in (("manifest.json", "glide_fixed_launch.mp4"), ("manifest_rd.json", "rd_fields.mp4")):
        m = json.loads((d / man).read_text())
        f = d / vid
        assert hashlib.sha256(f.read_bytes()).hexdigest() == m["video_sha256"]
        assert 10 <= m["duration_video_s"] <= 20 and f.stat().st_size < 8_000_000 and m["ffmpeg_exit"] == 0 and m["evidence_kind"] == "simulated"
        assert "glide" in json.dumps(m["time_units"]) or "tau" in json.dumps(m["time_units"])


def test_rd_rerun_reproduces_frozen_rows():
    import json, pathlib
    r = json.loads((pathlib.Path(__file__).resolve().parent.parent / "engineering" / "simulation" / "rd" / "receipt.json").read_text())
    assert all(c["reproduces_frozen_row"] and c["relative_amp_difference"] < 1e-9 for c in r["cells"])
