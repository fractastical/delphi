"""Focused tests for engineering.bioelectric_tissue. Expected values are worked by hand. Fixtures built in code are labelled as such and are not data;
the integration tests recompute the committed checks from the committed BETSE trajectories (no BETSE needed)."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from engineering.bioelectric_tissue import analysis as A

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "bioelectric-tissue"
needs_art = pytest.mark.skipif(not (ART / "summary.json").exists(), reason="artifacts not generated in this checkout")


def test_charge_density_hand_worked():
    # one time, ions Na+(z=+1) 10, K+(+1) 5, P-(-1) 12, M-(-1) 2 mol/m^3 -> (10+5-12-2)=1 mol/m^3 * F
    cc = np.array([[[10.0], [5.0], [12.0], [2.0]]])
    assert A.charge_from_concentrations(cc, np.array([1, 1, -1, -1.0]))[0, 0] == pytest.approx(A.FARADAY * 1.0, rel=1e-12)


def test_ghk_reduces_to_nernst_and_to_zero_at_equal_concentrations():
    T = 310.0
    v = A.ghk_voltage({"K": 140.0}, {"K": 5.0}, {"K": 1.0}, {"K": 1.0}, T)
    assert v == pytest.approx(A.R_GAS * T / A.FARADAY * np.log(5.0 / 140.0), rel=1e-12) and v == pytest.approx(-0.0892, abs=5e-4)       # K+ Nernst, 310 K
    assert A.ghk_voltage({"Na": 20.0}, {"Na": 20.0}, {"Na": 2.0}, {"Na": 1.0}, T) == pytest.approx(0.0, abs=1e-15)
    va = A.ghk_voltage({"M": 16.0}, {"M": 140.0}, {"M": 1.0}, {"M": -1.0}, T)               # anion Nernst: V = (RT/F) ln(c_in / c_out) -> negative inside for c_in < c_out ... sign: (RT/-F) ln(out/in)
    assert va == pytest.approx(A.R_GAS * T / A.FARADAY * np.log(16.0 / 140.0), rel=1e-12)


def _fixture(n_t=6, n_c=5):
    """CODE FIXTURE (not data): a minimal trajectory set with a known effect so the check logic can be exercised."""
    t = np.linspace(0.0, 5.0, n_t)
    base = dict(time_s=t, vm_cell_V=np.full((n_t, n_c), -0.020), vm_mem_V=np.full((n_t, n_c * 2), -0.020), cc_mol_m3=np.zeros((n_t, 4, n_c)), gj_open_fraction_mem=np.full((n_t, n_c * 2), 0.9),
                rho_cell_C_m3=np.zeros((n_t, n_c)), cell_vol_m3=np.full(n_c, 1e-15), cell_sa_m2=np.full(n_c, 3e-10), cm_F_m2=np.array(0.05), z=np.array([1, 1, -1, -1.0]),
                spot_cells=np.array([0, 1]), ion_order=np.array(["Na", "K", "P", "M"]), dt_s=np.array(1e-3), n_cells=np.array(n_c), n_mems=np.array(n_c * 2), temperature_K=np.array(310.0))
    base["cc_mol_m3"][:, 0, :] = 12.0; base["cc_mol_m3"][:, 1, :] = 139.0; base["cc_mol_m3"][:, 2, :] = 135.0; base["cc_mol_m3"][:, 3, :] = 16.0 + 0.0031
    rho = A.charge_from_concentrations(base["cc_mol_m3"], base["z"]); base["rho_cell_C_m3"] = rho
    base["vm_cell_V"] = rho * base["cell_vol_m3"] / (0.05 * base["cell_sa_m2"])
    base["cc_env_mol_m3"] = np.array([145.0, 5.0, 10.0, 140.0])
    return base


def test_effect_peaks_are_found_inside_the_window_for_the_right_cells():
    b = _fixture(); d = copy.deepcopy(b)
    d["vm_cell_V"][2, 0] -= 0.004          # t=2.0 s (window 1..3), targeted cell 0: -4 mV
    d["vm_cell_V"][3, 4] += 0.001          # t=3.0 s, other cell: +1 mV
    d["vm_cell_V"][5, 1] += 0.0005         # t=5.0 s, after the window: shows up only in the late column
    d["vm_cell_V"][0, 0] -= 0.010          # t=0.0 s, BEFORE the window: larger, and must not be reported as the in-window peak
    e = A.effect(d, b)
    assert e["targeted_peak_dVm_mV"] == pytest.approx(-4.0) and e["targeted_peak_time_s"] == pytest.approx(2.0)
    assert e["other_peak_dVm_mV"] == pytest.approx(1.0) and e["late_max_abs_dVm_mV"] == pytest.approx(0.5) and (e["n_targeted_cells"], e["n_other_cells"]) == (2, 3)


def shift(d, rows, cols, dv):
    """Change Vm by dv [V] consistently: the charge follows from the capacitor relation and is carried by Na+ so every saved field still agrees."""
    for r in np.atleast_1d(np.arange(d["time_s"].size)[rows]):
        for c in np.atleast_1d(np.arange(d["vm_cell_V"].shape[1])[cols]):
            drho = dv * float(d["cm_F_m2"]) * d["cell_sa_m2"][c] / d["cell_vol_m3"][c]
            d["vm_cell_V"][r, c] += dv; d["rho_cell_C_m3"][r, c] += drho; d["cc_mol_m3"][r, 0, c] += drho / A.FARADAY


def test_must_fail_controls_on_the_check_logic():
    b = _fixture(); D = {n: copy.deepcopy(b) for n in A.NAMES}
    # a consistent set where K control hyperpolarizes targeted cells and recovers, GJ block closes and reopens, half-step is identical
    shift(D["k_up"], slice(2, 4), slice(0, 2), -0.004); shift(D["k_up"], slice(2, 4), slice(2, 5), -0.001)
    D["gj_block"]["gj_open_fraction_mem"][1:4] = 0.0
    shift(D["k_up_gj_block"], slice(2, 4), slice(0, 2), -0.004); D["k_up_gj_block"]["gj_open_fraction_mem"][1:4] = 0.0
    D["baseline_dt"]["dt_s"] = np.array(5e-4)
    checks, _, _ = A.compute(D)
    assert all(c["ok"] for c in checks.values()), {k: v for k, v in checks.items() if not v["ok"]}
    # each broken variant must fail exactly the check that guards it
    bad = copy.deepcopy(D); shift(bad["k_up"], slice(2, 4), slice(0, 2), +0.008)             # K up now depolarizes
    assert not A.compute(bad)[0]["k_control_direction_and_reversal"]["ok"]
    bad = copy.deepcopy(D); bad["gj_block"]["gj_open_fraction_mem"][:] = 0.9                  # block did nothing
    assert not A.compute(bad)[0]["gj_block_control"]["ok"]
    bad = copy.deepcopy(D); bad["k_up"]["cc_mol_m3"][3, 2, 0] += 1.0                          # impermeant P created
    assert not A.compute(bad)[0]["impermeant_P_total_conserved"]["ok"]
    bad = copy.deepcopy(D); bad["baseline"]["rho_cell_C_m3"] = bad["baseline"]["rho_cell_C_m3"] * 1.01     # saved charge disagrees with concentrations
    assert not A.compute(bad)[0]["charge_consistency"]["ok"]
    bad = copy.deepcopy(D); bad["baseline"]["vm_cell_V"] = bad["baseline"]["vm_cell_V"] * (1 + 1e-6)       # Vm no longer equals rho*V/(Cm*A) (1e-6 relative)
    assert not A.compute(bad)[0]["charge_consistency"]["ok"]
    bad = copy.deepcopy(D); shift(bad["baseline_dt"], slice(None), slice(None), 0.0005)   # half-step run differs by 0.5 mV
    assert not A.compute(bad)[0]["time_step_sensitivity"]["ok"]
    bad = copy.deepcopy(D); bad["k_up"]["cc_mol_m3"][2, 1, 0] = -1.0; bad["k_up"]["rho_cell_C_m3"][2, 0] = A.charge_from_concentrations(bad["k_up"]["cc_mol_m3"], bad["k_up"]["z"])[2, 0]
    assert not A.compute(bad)[0]["finite_and_physical"]["ok"]
    bad = copy.deepcopy(D); bad["k_up"]["vm_cell_V"][2, 0] = np.nan
    assert not A.compute(bad)[0]["finite_and_physical"]["ok"]


@needs_art
def test_committed_summary_is_recomputed_from_committed_trajectories_and_hashes_match():
    s = json.loads((ART / "summary.json").read_text())
    for n, f in s["files"].items():
        assert A.sha256_file(ART / f["trajectory"]) == f["trajectory_sha256"] and A.sha256_file(ART / f["config"]) == f["config_sha256"], n
    D = {n: A.load(ART / s["files"][n]["trajectory"]) for n in A.NAMES}
    checks, eff, ref = A.compute(D)
    assert json.loads(json.dumps(checks, default=lambda o: o.item() if hasattr(o, "item") else str(o))) == s["checks"]
    assert json.loads(json.dumps(eff, default=lambda o: o.item() if hasattr(o, "item") else str(o))) == s["effects"]
    assert s["all_checks_ok"] == all(c["ok"] for c in s["checks"].values()) and s["label"].startswith("SIMULATED")


@needs_art
def test_scenarios_differ_only_by_the_intervention_and_share_the_world():
    s = json.loads((ART / "summary.json").read_text())
    D = {n: A.load(ART / s["files"][n]["trajectory"]) for n in A.NAMES}
    for n in A.NAMES[1:]:
        assert np.array_equal(D[n]["cell_centres_m"], D["baseline"]["cell_centres_m"]) and np.array_equal(D[n]["cell_vol_m3"], D["baseline"]["cell_vol_m3"])
    for n in A.NAMES[1:4]:                                                                            # before the first event ramp the runs agree to the solver's tail of the ramp
        assert np.abs(D["baseline"]["vm_cell_V"][0] - D[n]["vm_cell_V"][0]).max() * 1e3 < 1e-6, n     # < 1e-6 mV at t=0.1 s (measured about 3e-8 mV)
    cfg = {n: (ART / s["files"][n]["config"]).read_text() for n in A.NAMES}
    assert cfg["baseline"] != cfg["k_up"] != cfg["gj_block"]
    import re
    def ev(text, key):
        m = re.search(rf"^{key}:[^\n]*\n\s+event happens: (\w+)", text, re.M); return m.group(1)
    assert [ev(cfg["baseline"], "change K mem"), ev(cfg["k_up"], "change K mem"), ev(cfg["gj_block"], "change K mem")] == ["false", "true", "false"]
    assert [ev(cfg["baseline"], "block gap junctions"), ev(cfg["k_up"], "block gap junctions"), ev(cfg["gj_block"], "block gap junctions"), ev(cfg["k_up_gj_block"], "block gap junctions")] == ["false", "false", "true", "true"]


@needs_art
def test_outputs_state_what_they_are_not():
    s = json.loads((ART / "summary.json").read_text())
    assert "not a fish fin" in s["label"] and "not calibrated" in s["label"]
    assert (ART / "bioelectric_tissue.mp4").stat().st_size > 10_000 and (ART / "poster.png").stat().st_size > 5_000
