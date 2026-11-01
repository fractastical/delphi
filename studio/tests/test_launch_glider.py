"""Launchable fish glider (SPEC-010): print requirements, controls and mutants."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from engineering.launch_glider import print_requirements as pr

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "artifacts/fish3d/fish3d-v3a-fan/panels.json"
COMPS = ROOT / "artifacts/fish3d/fish3d-v3a-fan/components.json"
CARD = ROOT / "data/materials/formlabs-studio-2026-10-31.json"
MAT = {"flexural_modulus_Pa": 2.0e9, "solid_density_kg_m3": 1200.0, "ultimate_tensile_strength_Pa": 40e6}


def _rect_fin(span=0.08, chord=0.02, n=41):
    """A rectangular fin in the x-y plane: root at y = 0, chord along +x."""
    return {"fin_plane": {"origin_m": [0, 0, 0], "e_u": [0, 1, 0], "e_w": [1, 0, 0]},
            "outline_m": [[0, 0, 0], [chord, 0, 0], [chord, span, 0], [0, span, 0]],
            "area_flat_m2": span * chord}


def test_planform_matches_declared_areas_and_dihedral():
    panels = json.loads(PANELS.read_text())
    for name in ("pectoral_L", "pelvic_L"):
        pf = pr.planform(panels["fins"][name], n=401)
        assert pf["area_m2"] == pytest.approx(pf["area_declared_m2"], rel=2e-3)
    pf = pr.planform(panels["fins"]["pectoral_L"])
    assert pf["dihedral_deg"] == pytest.approx(7.0, abs=0.05)


def test_rectangle_planform_and_mac():
    pf = pr.planform(_rect_fin(), n=21)
    assert np.allclose(pf["chord_m"], 0.02) and pf["span_m"] == pytest.approx(0.08)
    m = pr.mac(pf)
    assert m["mac_m"] == pytest.approx(0.02) and m["x_ac_m"] == pytest.approx(0.005)
    assert m["span_centroid_m"] == pytest.approx(0.04)


def test_section_reduces_to_rectangle_and_parallel_axis():
    s = pr.section(0.01, 0.001, 1e-12, 1e-12)
    assert s["I_m4"] == pytest.approx(0.01 * 0.001**3 / 12, rel=1e-6)
    # membrane + spar of equal area: centroids t/2 and -h/2 -> neutral axis halfway
    c, t, ws, hs = 0.002, 0.001, 0.001, 0.002
    s = pr.section(c, t, ws, hs)
    A1, A2 = c * t, ws * hs
    yb = (A1 * t / 2 - A2 * hs / 2) / (A1 + A2)
    Iref = c * t**3 / 12 + A1 * (t / 2 - yb) ** 2 + ws * hs**3 / 12 + A2 * (hs / 2 + yb) ** 2
    assert s["I_m4"] == pytest.approx(Iref, rel=1e-12)


def test_uniform_rectangular_fin_matches_closed_form():
    """Constant chord, no spar, no inertia: tip = q L^4/(8EI), root moment = q L^2/2, sigma = M/Z."""
    pr.SCENARIO["effective_flange_over_t"]["value"] = 1e6  # full chord effective for this control
    try:
        L, c, t, p = 0.08, 0.02, 0.001, 50.0
        pf = pr.planform(_rect_fin(L, c), n=41)
        r = pr.fin_case(pf, MAT, t, 1e-9, 1e-9, p, 0.0, n_el=64)
        q, EI = p * c, MAT["flexural_modulus_Pa"] * c * t**3 / 12
        assert r["tip_m"] == pytest.approx(q * L**4 / (8 * EI), rel=1e-3)
        assert r["root_moment_N_m"] == pytest.approx(q * L * L / 2, rel=1e-4)
        assert r["sigma_root_Pa"] == pytest.approx((q * L * L / 2) / (c * t * t / 6), rel=1e-3)
    finally:
        pr.SCENARIO["effective_flange_over_t"]["value"] = 20.0


def test_inertia_load_equals_pressure_of_same_areal_weight():
    pf = pr.planform(_rect_fin(), n=41)
    t, a = 0.0005, 300.0
    r_in = pr.fin_case(pf, MAT, t, 1e-9, 1e-9, 0.0, a)
    r_p = pr.fin_case(pf, MAT, t, 1e-9, 1e-9, MAT["solid_density_kg_m3"] * t * a, 0.0)
    assert r_in["tip_m"] == pytest.approx(r_p["tip_m"], rel=1e-6)


def test_shear_lag_flange_is_conservative():
    pf = pr.planform(_rect_fin(0.08, 0.03), n=41)
    narrow = pr.fin_case(pf, MAT, 0.0005, 0.0016, 0.002, 50.0, 0.0)
    pr.SCENARIO["effective_flange_over_t"]["value"] = 1e6
    try:
        full = pr.fin_case(pf, MAT, 0.0005, 0.0016, 0.002, 50.0, 0.0)
    finally:
        pr.SCENARIO["effective_flange_over_t"]["value"] = 20.0
    assert narrow["tip_m"] > full["tip_m"] and narrow["sigma_max_Pa"] > full["sigma_max_Pa"]


def test_inplane_root_closed_form():
    pf = pr.planform(_rect_fin(0.08, 0.02), n=401)
    t, a = 0.001, 1000.0
    r = pr.inplane_root(pf, MAT, t, 1e-9, 1e-9, t, 0.0, a)
    q = MAT["solid_density_kg_m3"] * 0.02 * t * a
    M = q * 0.08**2 / 2
    assert r["moment_N_m"] == pytest.approx(M, rel=1e-4)
    assert r["sigma_Pa"] == pytest.approx(M / (t * 0.02**2 / 6), rel=1e-3)


def test_loads_and_mass_budget_arithmetic():
    ld = pr.loads(0.02)
    assert ld["V_design_m_s"] == pytest.approx(10.0)
    assert ld["a_mean_m_s2"] == pytest.approx(10.0**2 / (2 * 0.1))
    assert ld["a_peak_m_s2"] == pytest.approx(2 * ld["a_mean_m_s2"])
    assert ld["hook_force_peak_N"] == pytest.approx(0.02 * 1000.0)
    row = next(r for r in pr.mass_budget(0.00529) if r["V_m_s"] == 8.0 and r["CL_trim"] == 0.5)
    assert row["mass_max_kg"] == pytest.approx(0.5 * 1.225 * 64 * 0.5 * 0.00529 / pr.G)


def test_hook_stem_meets_allowable_exactly():
    mat = pr.load_material(CARD)
    h = pr.hook(0.02, mat, 6e-3, 4e-3)
    sig = 6 * h["design_force_N"] * 6e-3 / (4e-3 * h["min_stem_depth_m"] ** 2)
    assert sig == pytest.approx(mat["ultimate_tensile_strength_Pa"], rel=1e-9)


def test_material_card_pinned_values():
    m = pr.load_material(CARD)
    assert m["id"] == "alpha-grey-v1-default-post-cure"
    assert m["solid_density_kg_m3"] == 1220 and m["flexural_modulus_Pa"] == 2.08e9
    assert m["ultimate_tensile_strength_Pa"] == 43e6 and len(m["card_sha256"]) == 64


def test_helmbold_limits():
    assert pr.helmbold(1e6) == pytest.approx(2 * math.pi, rel=1e-5)
    assert pr.helmbold(1e-4) == pytest.approx(math.pi * 1e-4 / 2, rel=1e-3)


def test_munk_moves_np_forward_and_downwash_moves_it_forward():
    panels = json.loads(PANELS.read_text())
    pect, pelv = pr.planform(panels["fins"]["pectoral_L"]), pr.planform(panels["fins"]["pelvic_L"])
    npb = pr.neutral_point(pect, pelv, 48.7e-6, 0.0136)
    for c in npb["cases"]:
        assert c["x_np_m"] < c["x_np_fins_only_m"]
    by = {(c["downwash_deps_dalpha"], c["munk_k2_minus_k1"]): c for c in npb["cases"]}
    assert by[(0.6, 0.8)]["x_np_fins_only_m"] < by[(0.2, 0.8)]["x_np_fins_only_m"]
    assert pect["area_m2"] and npb["pectoral"]["x_ac_m"] < npb["x_np_min_m"] < npb["pelvic"]["x_ac_m"]


def test_mutant_no_pelvics_puts_np_at_pectoral_ac():
    """Removing the rear surface must collapse the fins-only NP to the pectoral a.c. (stability is lost)."""
    panels = json.loads(PANELS.read_text())
    pect = pr.planform(panels["fins"]["pectoral_L"])
    tiny = pr.planform(_rect_fin(1e-4, 1e-4), n=5)
    npb = pr.neutral_point(pect, tiny, 1e-30, 0.0136)
    assert npb["cases"][0]["x_np_fins_only_m"] == pytest.approx(npb["pectoral"]["x_ac_m"], abs=1e-6)


def test_requirements_artifact_reproduces():
    r = pr.requirements(PANELS, CARD, COMPS)
    art = json.loads((ROOT / "artifacts/launch-glider/print-requirements.json").read_text())
    assert json.loads(json.dumps(r, sort_keys=True)) == art
    pect = {s["membrane_t_m"]: s for s in r["fin_sizing"]["pectoral"]}
    assert pect[0.0005]["min_spar_h_m"] == pytest.approx(0.0012)
    rec = next(row for row in pect[0.0005]["rows"] if abs(row["spar_h_m"] - 0.002) < 1e-9)
    assert rec["pass"] and rec["worst"]["sigma_max_Pa"] < r["fin_sizing"]["pectoral"][0]["allowable_Pa"]
    bare = pect[0.0005]["rows"][0]
    assert bare["spar_h_m"] == pytest.approx(0.0004) and not bare["pass"]   # retained failing design
