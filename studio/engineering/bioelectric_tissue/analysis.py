"""Checks and control-effect metrics on the saved BETSE trajectories. NumPy only; every number is computed from the npz files written by betse_stage.py.

Checks are sanity checks of one BETSE configuration (SIMULATED). They are not validation against measurements, and the thresholds below are check criteria chosen
for these checks, not statistics."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

FARADAY = 96485.33212        # C/mol
R_GAS = 8.314462618          # J/(mol K)
WINDOW = (1.0, 3.0)          # intervention window [s], as configured in betse_stage.py
LATE = 3.5                   # 'after the window' time [s]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(path: Path) -> dict:
    z = np.load(path, allow_pickle=True)
    return {k: z[k] for k in z.files}


def charge_from_concentrations(cc_mol_m3: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Net volume charge density [C/m^3] per cell and time: F * sum_i z_i c_i, c in mol/m^3 (== mmol/L)."""
    return FARADAY * np.einsum("i,tic->tc", z, cc_mol_m3)


def ghk_voltage(c_in: dict, c_out: dict, perm: dict, z: dict, temperature_K: float) -> float:
    """Goldman-Hodgkin-Katz voltage [V] (inside minus outside) for monovalent ions. Reference formula only (no pumps, no gap junctions)."""
    num = sum(perm[i] * (c_out[i] if z[i] > 0 else c_in[i]) for i in perm)
    den = sum(perm[i] * (c_in[i] if z[i] > 0 else c_out[i]) for i in perm)
    return R_GAS * temperature_K / FARADAY * float(np.log(num / den))


def effect(d: dict, base: dict) -> dict:
    """Per-scenario difference from the baseline run of the same seeded world and init (deterministic solver, so the difference is the intervention)."""
    t = d["time_s"]; dv = (d["vm_cell_V"] - base["vm_cell_V"]) * 1e3          # mV
    tgt = np.asarray(d["spot_cells"], dtype=int)
    other = np.setdiff1d(np.arange(d["vm_cell_V"].shape[1]), tgt)
    win = (t >= WINDOW[0]) & (t <= WINDOW[1]); late = t >= LATE
    def peak(cols):
        sub = dv[np.ix_(win, cols)]
        i = np.unravel_index(np.argmax(np.abs(sub)), sub.shape)
        return float(sub[i]), float(t[win][i[0]])
    pt, tt = peak(tgt) if len(tgt) else (None, None)
    po, to = peak(other)
    gj = d["gj_open_fraction_mem"].mean(axis=1)
    return {"n_targeted_cells": int(len(tgt)), "n_other_cells": int(len(other)),
            "targeted_peak_dVm_mV": pt, "targeted_peak_time_s": tt, "other_peak_dVm_mV": po, "other_peak_time_s": to,
            "late_max_abs_dVm_mV": float(np.abs(dv[late]).max()), "late_time_from_s": LATE,
            "mean_gj_open_fraction_in_window_min": float(gj[win].min()), "mean_gj_open_fraction_baseline": float(base["gj_open_fraction_mem"].mean()),
            "mean_gj_open_fraction_at_end": float(gj[-1]),
            "targeted_dK_mmol_L_at_window_end": float((d["cc_mol_m3"][win][-1, 1, tgt] - base["cc_mol_m3"][win][-1, 1, tgt]).mean()) if len(tgt) else None,
            "targeted_dNa_mmol_L_at_window_end": float((d["cc_mol_m3"][win][-1, 0, tgt] - base["cc_mol_m3"][win][-1, 0, tgt]).mean()) if len(tgt) else None}


NAMES = ["baseline", "k_up", "gj_block", "k_up_gj_block", "baseline_dt"]


def compute(D: dict) -> tuple[dict, dict, dict]:
    """(checks, effects, ghk reference) from the loaded trajectories; no file access."""
    b = D["baseline"]; t = b["time_s"]; z = b["z"]
    checks = {}
    # 1 finite and physical
    allfin = all(np.isfinite(D[n][k]).all() for n in D for k in ("vm_cell_V", "vm_mem_V", "cc_mol_m3", "gj_open_fraction_mem"))
    vmr = [float(min(D[n]["vm_cell_V"].min() for n in D) * 1e3), float(max(D[n]["vm_cell_V"].max() for n in D) * 1e3)]
    cmin = float(min(D[n]["cc_mol_m3"].min() for n in D))
    checks["finite_and_physical"] = {"ok": bool(allfin and cmin > 0 and -150 < vmr[0] and vmr[1] < 50), "vm_range_mV": vmr, "min_concentration_mmol_L": cmin,
                                      "criterion": "all values finite; every concentration > 0; -150 mV < Vm < 50 mV"}
    # 2 charge identities (BETSE defines Vm from the capacitor relation; this checks that the saved fields are consistent, it is not an independent measurement)
    rho_c = np.concatenate([charge_from_concentrations(D[n]["cc_mol_m3"], z) for n in D]); rho_s = np.concatenate([D[n]["rho_cell_C_m3"] for n in D])
    rel_rho = float(np.abs(rho_c - rho_s).max() / np.abs(rho_s).max())
    vm_cap = np.concatenate([D[n]["rho_cell_C_m3"] * D[n]["cell_vol_m3"] / (float(D[n]["cm_F_m2"]) * D[n]["cell_sa_m2"]) for n in D]); vm_s = np.concatenate([D[n]["vm_cell_V"] for n in D])
    rel_vm = float(np.abs(vm_cap - vm_s).max() / np.abs(vm_s).max())
    checks["charge_consistency"] = {"ok": bool(rel_rho < 1e-4 and rel_vm < 1e-9), "max_rel_diff_rho_vs_F_sum_z_c": rel_rho, "max_rel_diff_Vm_vs_rho_vol_over_Cm_area": rel_vm,
                                    "criterion": "rho = F*sum(z c) within 1e-4 and Vm = rho*V/(Cm*A) within 1e-9", "note": "Vm is defined this way inside BETSE; the check confirms the saved fields agree, not that the model is right"}
    # 3 conserved impermeant species: total P amount (membrane diffusion constant 0) must not change while gap junctions open, block, and reopen
    iP = [i for i, nme in enumerate(b["ion_order"]) if str(nme) == "P"][0]
    pr = {}
    for n in D:
        tot = (D[n]["cc_mol_m3"][:, iP, :] * D[n]["cell_vol_m3"][None, :]).sum(axis=1); pr[n] = float((tot.max() - tot.min()) / tot[0])
    checks["impermeant_P_total_conserved"] = {"ok": bool(max(pr.values()) < 1e-12), "relative_range_by_scenario": pr, "criterion": "relative range of total P amount < 1e-12",
                                              "note": "Na, K and M exchange with the ideal bath by design, so their totals are not conserved; only P gives a closed-budget test here"}
    # 4 solver time-step sensitivity (baseline at dt and dt/2)
    h = D["baseline_dt"]; dvm = float(np.abs(b["vm_cell_V"] - h["vm_cell_V"]).max() * 1e3); dcc = float(np.abs(b["cc_mol_m3"] - h["cc_mol_m3"]).max() / b["cc_mol_m3"].max())
    eff = {n: effect(D[n], b) for n in ("k_up", "gj_block", "k_up_gj_block")}
    ratio = dvm / abs(eff["k_up"]["targeted_peak_dVm_mV"])
    checks["time_step_sensitivity"] = {"ok": bool(dvm < 1e-3 and ratio < 0.01), "dt_s": float(b["dt_s"]), "half_dt_s": float(h["dt_s"]), "max_abs_dVm_mV": dvm, "max_rel_dConc": dcc,
                                       "ratio_to_K_control_peak": float(ratio), "criterion": "max |dVm| < 1e-3 mV and < 1 % of the K-permeability control peak effect",
                                       "note": "sample times differ by <1 microsecond between dt and dt/2; arrays are compared index by index"}
    # 5 direction/reversibility of the K-permeability control
    k = eff["k_up"]
    checks["k_control_direction_and_reversal"] = {"ok": bool(k["targeted_peak_dVm_mV"] < 0 and abs(k["targeted_peak_dVm_mV"]) > abs(k["other_peak_dVm_mV"]) and k["late_max_abs_dVm_mV"] < 0.25 * abs(k["targeted_peak_dVm_mV"])),
        "targeted_peak_dVm_mV": k["targeted_peak_dVm_mV"], "other_peak_dVm_mV": k["other_peak_dVm_mV"], "late_max_abs_dVm_mV": k["late_max_abs_dVm_mV"],
        "criterion": "raising K+ permeability makes targeted cells more negative, more than the others, and the effect after the window is < 25 % of the peak",
        "note": "direction expected from a K+ reversal potential below rest; the magnitude is not compared with any measurement"}
    g = eff["gj_block"]
    checks["gj_block_control"] = {"ok": bool(g["mean_gj_open_fraction_in_window_min"] < 0.05 and g["mean_gj_open_fraction_at_end"] > 0.9 * g["mean_gj_open_fraction_baseline"]),
        "gj_open_in_window_min": g["mean_gj_open_fraction_in_window_min"], "gj_open_baseline": g["mean_gj_open_fraction_baseline"], "gj_open_at_end": g["mean_gj_open_fraction_at_end"],
        "criterion": "mean gap-junction open fraction < 0.05 inside the window and > 90 % of baseline at the end"}
    kg = eff["k_up_gj_block"]
    checks["coupling_contrast_expectation"] = {"ok": bool(abs(kg["other_peak_dVm_mV"]) < abs(k["other_peak_dVm_mV"])), "k_up": {x: k[x] for x in ("targeted_peak_dVm_mV", "other_peak_dVm_mV")},
        "k_up_gj_block": {x: kg[x] for x in ("targeted_peak_dVm_mV", "other_peak_dVm_mV")},
        "criterion": "expectation (not a law): blocking gap junctions should reduce the voltage change seen by cells that were not targeted", "note": "ok=false would be reported as a result, not hidden"}
    # 6 GHK reference (informational; no pumps, no coupling) with the run's own concentrations
    ion = [str(x) for x in b["ion_order"]]; zc = {i: float(zz) for i, zz in zip(ion, z)}
    perm = {"Na": 2.0e-18, "K": 1.0e-18, "M": 1.0e-18}      # BETSE default Dm [m^2/s] used by this configuration for Base cells
    cin = {n_: float(b["cc_mol_m3"][0, i].mean()) for i, n_ in enumerate(ion)}; cout = {n_: float(b["cc_env_mol_m3"][i]) for i, n_ in enumerate(ion)} if "cc_env_mol_m3" in b else None
    ghk = ghk_voltage(cin, cout, perm, zc, float(b["temperature_K"])) * 1e3 if cout else None
    reference = {"ghk_leak_only_mV": ghk, "simulated_mean_resting_Vm_mV": float(b["vm_cell_V"][0].mean() * 1e3), "intracellular_mmol_L_t0": cin, "extracellular_mmol_L": cout,
                 "note": "informational only: the GHK number ignores the pump and gap junctions; the difference to the simulation is not decomposed here", "default_Dm_m2_s": perm}
    return checks, eff, reference


def run(work: Path, out: Path, betse_python: str | None = None) -> dict:
    work, out = Path(work), Path(out)
    names = NAMES
    D = {n: load(work / n / f"{n}.npz") for n in names}
    b = D["baseline"]; t = b["time_s"]
    checks, eff, reference = compute(D)
    cfgout = out / "configs"; trj = out / "trajectories"; cfgout.mkdir(parents=True, exist_ok=True); trj.mkdir(parents=True, exist_ok=True)
    files = {}
    for n in names:
        shutil.copy2(work / n / "cfg" / "run.yaml", cfgout / f"{n}.yaml"); shutil.copy2(work / n / f"{n}.npz", trj / f"{n}.npz")
        files[n] = {"config": f"configs/{n}.yaml", "config_sha256": sha256_file(cfgout / f"{n}.yaml"), "trajectory": f"trajectories/{n}.npz", "trajectory_sha256": sha256_file(trj / f"{n}.npz")}
    ver = None
    if betse_python:
        try:
            ver = subprocess.run([str(Path(betse_python).parent / "betse"), "--version"], capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[-1]
        except Exception as e:                                           # noqa: BLE001
            ver = f"unavailable: {type(e).__name__}"
    res = {"schema": "frontier.bioelectric-tissue.summary/1", "label": "SIMULATED (BETSE 1.5.0 numerical output); not observed; not calibrated; not a fish fin",
           "betse": ver, "n_cells": int(b["n_cells"]), "n_membranes": int(b["n_mems"]), "time_s": [float(t[0]), float(t[-1])], "samples": int(len(t)), "intervention_window_s": list(WINDOW),
           "files": files, "checks": checks, "effects": eff, "reference_ghk": reference, "all_checks_ok": bool(all(c["ok"] for c in checks.values()))}
    (out / "summary.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    return res
