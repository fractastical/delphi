"""Conservative print requirements for the first 1:1 launchable prototype, before any aero optimisation.

    python -m engineering.launch_glider.print_requirements \
        artifacts/fish3d/fish3d-v3a-fan/panels.json data/materials/formlabs-studio-2026-10-31.json \
        artifacts/launch-glider/print-requirements.json

What it computes, all from the pinned v3a planform and the pinned material card:
  * each paired fin as a cantilever along its span axis e_u (root at the body), chord c(u) sliced from the
    panels.json outline, loaded by a normal pressure and by the launch inertia normal to the fin;
  * the smallest leading-edge spar (one printed ridge of declared width under the membrane) and the root
    doubler that keep root stress <= UTS / SF and tip deflection within declared limits;
  * the slingshot hook stem section and peak hook force over the SPEC-010 launch scenarios;
  * a hand neutral-point bracket (Helmbold lift slopes, declared downwash bracket, Munk body couple) and the CG
    window and ballast travel that window implies. VLM (cfd04) replaces the bracket; it is not a VLM result.

Beam theory is reused from engineering/fin_mechanics/beam.py (Hermite FE, checked there against closed forms).
Every load is a declared scenario (SPEC-010 rules 3-4); no launcher force profile has been measured.
Torsion, membrane wrinkling, layer anisotropy, notches, fatigue, impact and hand handling are NOT modelled; the
strength safety factor SF is declared for that reason, not derived.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from engineering.fin_mechanics import beam

from . import SCHEMA_REQUIREMENTS

G = 9.80665
RHO_AIR = 1.225  # kg/m3, ISA sea level; declared, room air not measured

# ---------------------------------------------------------------- declared scenario envelope (SPEC-010)
SCENARIO = {
    "release_speed_m_s": {"values": [4.0, 6.0, 8.0], "status": "SPEC-010 rule 3 chosen scenarios"},
    "speed_overshoot_factor": {"value": 1.25, "status": "assumed: launcher speed is unmeasured"},
    "stroke_m": {"values": [0.1, 0.2, 0.3], "status": "SPEC-010 rule 4 chosen scenarios"},
    "peak_over_mean_force": {"values": {"constant": 1.0, "half_sine": math.pi / 2, "linear_decay": 2.0},
                             "status": "bracket of unknown force-time profiles; linear decay = ideal elastic band"},
    "misalignment_deg": {"value": 10.0, "status": "assumed: band line vs fin plane at launch, puts a_peak*sin() normal to fins"},
    "mass_kg": {"range": [0.008, 0.020], "status": "bracket: 8 g (light target) to 20 g (claude-05 plan upper estimate)"},
    "cn_max": {"value": 1.2, "status": "assumed flat-plate normal-force bound at large incidence during launch transients"},
    "strength_safety_factor": {"value": 3.0, "status": "declared; covers notches, layer lines, thin-feature cure, handling"},
    "tip_deflection_over_span_cruise_max": {"value": 0.03, "status": "declared shape-retention limit at 1 g trim load"},
    "tip_deflection_over_span_worst_max": {"value": 0.10, "status": "beam small-deformation validity bound (fin_mechanics)"},
    "effective_flange_over_t": {"value": 20.0, "status": "declared shear-lag bound: membrane counted only within 20 t "
                                                       "of the spar; the rest carries load but adds no stiffness"},
}


REPO = Path(__file__).resolve().parents[2]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except ValueError:
        return str(p)


def load_material(card_path: Path, material_id: str | None = None) -> dict:
    card = json.loads(card_path.read_text())
    mid = material_id or card["default_scenario_material"]
    m = next(x for x in card["materials"] if x["id"] == mid)
    return {**m, "card_path": _rel(card_path), "card_sha256": _sha(card_path)}


# ---------------------------------------------------------------- planform
def planform(fin: dict, n: int = 81) -> dict:
    """Chord c(u) and leading-edge w_le(u) of one fin, sliced from its outline in its own plane.

    u runs along e_u from the root (u = 0 at the most inboard outline point); w along e_w (= +x, aft)."""
    fp = fin["fin_plane"]
    o, eu, ew = (np.array(fp[k], float) for k in ("origin_m", "e_u", "e_w"))
    P = np.array(fin["outline_m"], float)
    uw = np.stack([(P - o) @ eu, (P - o) @ ew], axis=1)
    u0, u1 = uw[:, 0].min(), uw[:, 0].max()
    us = np.linspace(u0, u1, n)
    chord, wle = np.zeros(n), np.zeros(n)
    seg = np.stack([uw, np.roll(uw, -1, axis=0)], axis=1)
    for i, u in enumerate(us):
        uu = np.clip(u, u0 + 1e-9 * (u1 - u0), u1 - 1e-9 * (u1 - u0))
        a, b = seg[:, 0], seg[:, 1]
        hit = (a[:, 0] - uu) * (b[:, 0] - uu) < 0
        t = (uu - a[hit, 0]) / (b[hit, 0] - a[hit, 0])
        ws = np.sort(a[hit, 1] + t * (b[hit, 1] - a[hit, 1]))
        if len(ws) % 2:
            raise ValueError(f"outline slice at u={u:.4g} has an odd crossing count {len(ws)}")
        chord[i] = float(np.sum(ws[1::2] - ws[0::2]))
        wle[i] = float(ws[0])
    s = us - u0
    area = float(np.trapezoid(chord, s))
    return {"s_m": s, "chord_m": chord, "w_le_m": wle, "span_m": float(u1 - u0), "area_m2": area,
            "x0_m": float(o[0] + u0 * eu[0]), "w0_x_m": float(o[0]), "e_u": eu.tolist(),
            "dihedral_deg": math.degrees(math.asin(eu[2])),
            "area_declared_m2": fin["area_flat_m2"]}


def mac(pf: dict) -> dict:
    s, c, wle = pf["s_m"], pf["chord_m"], pf["w_le_m"]
    S = np.trapezoid(c, s)
    mac_ = np.trapezoid(c * c, s) / S
    x_ac = pf["w0_x_m"] + np.trapezoid(c * (wle + 0.25 * c), s) / S   # chord-weighted quarter-chord, body x
    s_c = np.trapezoid(c * s, s) / S
    return {"mac_m": float(mac_), "x_ac_m": float(x_ac), "span_centroid_m": float(s_c), "area_m2": float(S)}


# ---------------------------------------------------------------- section and beam
def section(c: float, t: float, ws: float, hs: float) -> dict:
    """Membrane strip (c x t) with one spar ridge (ws x hs) under it; bending about the chordwise axis.

    Exact composite neutral axis (parallel-axis theorem), single material."""
    A1, y1, I1 = c * t, t / 2, c * t**3 / 12
    A2, y2, I2 = ws * hs, -hs / 2, ws * hs**3 / 12
    A = A1 + A2
    yb = (A1 * y1 + A2 * y2) / A
    Ib = I1 + A1 * (y1 - yb) ** 2 + I2 + A2 * (y2 - yb) ** 2
    ymax = max(t - yb, yb + hs)
    return {"A_m2": A, "I_m4": Ib, "y_max_m": ymax, "Z_m3": Ib / ymax}


def fin_case(pf: dict, mat: dict, t_m: float, ws: float, hs: float, p: float, a_n: float,
             t_root: float | None = None, root_len: float = 0.0, n_el: int = 64) -> dict:
    """Root stress, max stress along span and tip deflection for pressure p [Pa] plus normal inertia a_n [m/s2]."""
    s, c = pf["s_m"], pf["chord_m"]
    L = pf["span_m"]
    E, rho = mat["flexural_modulus_Pa"], mat["solid_density_kg_m3"]

    def t_of(x):
        x = np.asarray(x, float)
        return np.where(x < root_len, t_root if t_root else t_m, t_m)

    def c_of(x):
        return np.interp(x, s, c)

    k_f = SCENARIO["effective_flange_over_t"]["value"]

    def b_eff(ci, ti):
        return max(min(ci, ws + k_f * ti), 1e-6)

    def EI(x):
        return np.array([E * section(b_eff(ci, ti), ti, ws, hs)["I_m4"]
                         for ci, ti in zip(np.atleast_1d(c_of(x)), np.atleast_1d(t_of(x)))])

    def q(x):   # N/m: pressure on the chord plus the inertia of the section's own mass
        return p * c_of(x) + rho * (c_of(x) * t_of(x) + ws * hs) * a_n

    sol = beam.solve_cantilever(L, EI, q, n_el=n_el)
    xs = np.linspace(0, L, 401)
    qs = q(xs)
    # bending moment M(x) = int_x^L q(xi) (xi - x) dxi
    M = np.array([np.trapezoid(qs[i:] * (xs[i:] - x), xs[i:]) if i < len(xs) - 1 else 0.0 for i, x in enumerate(xs)])
    sig = np.array([M[i] / section(b_eff(float(c_of(x)), float(t_of(x))), float(t_of(x)), ws, hs)["Z_m3"]
                    for i, x in enumerate(xs)])
    k = int(np.argmax(sig))
    chk = beam.check_small_deformation(sol.tip, sol.max_abs_slope, L,
                                       SCENARIO["tip_deflection_over_span_worst_max"]["value"])
    return {"root_moment_N_m": float(M[0]), "root_shear_N": float(np.trapezoid(qs, xs)),
            "sigma_root_Pa": float(sig[0]), "sigma_max_Pa": float(sig[k]), "sigma_max_at_s_m": float(xs[k]),
            "tip_m": float(sol.tip), "tip_over_span": float(abs(sol.tip) / L), "small_deformation": chk}


def inplane_root(pf: dict, mat: dict, t_m: float, ws: float, hs: float, t_root: float, root_len: float,
                 a_ip: float, root_chord: float | None = None) -> dict:
    """Launch inertia along body x lies in the fin plane (e_w = +x): in-plane bending of the root section.

    Section: membrane depth c0 (chordwise) x t_root, plus the spar (ws chordwise x hs) at the leading edge."""
    s, c = pf["s_m"], pf["chord_m"]
    rho = mat["solid_density_kg_m3"]
    t = np.where(s < root_len, t_root, t_m)
    qn = rho * (c * t + ws * hs) * a_ip
    M = float(np.trapezoid(qn * s, s))
    c0 = root_chord or float(c[0])
    A1, x1, I1 = c0 * t_root, c0 / 2, t_root * c0**3 / 12
    A2, x2, I2 = ws * hs, ws / 2, hs * ws**3 / 12
    xb = (A1 * x1 + A2 * x2) / (A1 + A2)
    Ib = I1 + A1 * (x1 - xb) ** 2 + I2 + A2 * (x2 - xb) ** 2
    sig = M * max(xb, c0 - xb) / Ib
    return {"a_inplane_m_s2": a_ip, "root_chord_m": c0, "moment_N_m": M, "shear_N": float(np.trapezoid(qn, s)),
            "sigma_Pa": float(sig)}


def loads(m_max: float) -> dict:
    V = max(SCENARIO["release_speed_m_s"]["values"]) * SCENARIO["speed_overshoot_factor"]["value"]
    s_min = min(SCENARIO["stroke_m"]["values"])
    k_pk = max(SCENARIO["peak_over_mean_force"]["values"].values())
    a_avg = V * V / (2 * s_min)
    a_pk = k_pk * a_avg
    a_n = a_pk * math.sin(math.radians(SCENARIO["misalignment_deg"]["value"]))
    p_w = 0.5 * RHO_AIR * V * V * SCENARIO["cn_max"]["value"]
    return {"V_design_m_s": V, "stroke_min_m": s_min, "a_mean_m_s2": a_avg, "a_peak_m_s2": a_pk,
            "a_normal_to_fin_m_s2": a_n, "p_worst_Pa": p_w, "hook_force_peak_N": m_max * a_pk}


def size_fin(pf: dict, mat: dict, S_paired: float, m_max: float, t_m: float, ws: float,
             t_root: float, root_len: float, hs_grid=None) -> dict:
    """Smallest spar height hs on hs_grid meeting stress (worst case) and both deflection limits."""
    ld = loads(m_max)
    allow = mat["ultimate_tensile_strength_Pa"] / SCENARIO["strength_safety_factor"]["value"]
    p_cruise = m_max * G / S_paired
    hs_grid = hs_grid if hs_grid is not None else np.round(np.arange(0.4, 4.01, 0.2), 2) * 1e-3
    rows = []
    for hs in hs_grid:
        w = fin_case(pf, mat, t_m, ws, hs, ld["p_worst_Pa"], ld["a_normal_to_fin_m_s2"], t_root, root_len)
        cr = fin_case(pf, mat, t_m, ws, hs, p_cruise, 0.0, t_root, root_len)
        ok = (w["sigma_max_Pa"] <= allow and w["small_deformation"]["valid"]
              and cr["tip_over_span"] <= SCENARIO["tip_deflection_over_span_cruise_max"]["value"])
        rows.append({"spar_h_m": float(hs), "worst": w, "cruise": cr, "pass": bool(ok)})
    first = next((r for r in rows if r["pass"]), None)
    hs_ip = first["spar_h_m"] if first else float(hs_grid[-1])
    ip = inplane_root(pf, mat, t_m, ws, hs_ip, t_root, root_len, ld["a_peak_m_s2"])
    c_need = None
    for c0 in np.arange(float(pf["chord_m"][0]), 0.0601, 0.0005):
        if inplane_root(pf, mat, t_m, ws, hs_ip, t_root, root_len, ld["a_peak_m_s2"], root_chord=c0)["sigma_Pa"] <= allow:
            c_need = float(c0)
            break
    return {"membrane_t_m": t_m, "spar_w_m": ws, "root_doubler_t_m": t_root, "root_doubler_len_m": root_len,
            "allowable_Pa": allow, "p_cruise_Pa": p_cruise, "loads": ld, "rows": rows,
            "min_spar_h_m": first["spar_h_m"] if first else None,
            "inplane_root_at_min_spar": ip, "min_root_chord_inplane_m": c_need}


def hook(m_max: float, mat: dict, stem_len: float, stem_b: float) -> dict:
    ld = loads(m_max)
    sf = SCENARIO["strength_safety_factor"]["value"]
    F = ld["hook_force_peak_N"]
    d = math.sqrt(6 * sf * F * stem_len / (stem_b * mat["ultimate_tensile_strength_Pa"]))
    return {"peak_force_N": F, "design_force_N": sf * F, "stem_len_m": stem_len, "stem_b_m": stem_b,
            "min_stem_depth_m": d, "rule": "rectangular cantilever stem, sigma = 6 F l / (b d^2) <= UTS/SF"}


def helmbold(A: float) -> float:
    return 2 * math.pi * A / (2 + math.sqrt(A * A + 4))


def neutral_point(pect: dict, pelv: dict, body_volume_m3: float, body_half_width_m: float,
                  downwash=(0.2, 0.6), munk_k=(0.80, 0.95)) -> dict:
    """Hand NP bracket on the paired-fin reference: Helmbold lift slopes on exposed span plus body width, a
    declared downwash factor on the pelvics, and Munk's slender-body couple dM/dalpha = 2 q V (k2-k1),
    a pure couple that moves the NP forward. Not a VLM result; cfd04 replaces it."""
    out = []
    mp, mv = mac(pect), mac(pelv)
    S1, S2 = 2 * mp["area_m2"], 2 * mv["area_m2"]
    b1 = 2 * (pect["span_m"] + body_half_width_m)
    b2 = 2 * (pelv["span_m"] + body_half_width_m)
    a1, a2 = helmbold(b1 * b1 / S1), helmbold(b2 * b2 / S2)
    S = S1 + S2
    for eps in downwash:
        for k in munk_k:
            w1, w2 = a1 * S1, a2 * S2 * (1 - eps)
            CLa = (w1 + w2) / S
            x_np_fins = (w1 * mp["x_ac_m"] + w2 * mv["x_ac_m"]) / (w1 + w2)
            dx = 2 * body_volume_m3 * k / (S * CLa)
            out.append({"downwash_deps_dalpha": eps, "munk_k2_minus_k1": k, "CL_alpha_per_rad": CLa,
                        "x_np_fins_only_m": x_np_fins, "munk_shift_m": dx, "x_np_m": x_np_fins - dx})
    xs = [r["x_np_m"] for r in out]
    return {"pectoral": {**mp, "AR_pair": b1 * b1 / S1, "CL_alpha": a1},
            "pelvic": {**mv, "AR_pair": b2 * b2 / S2, "CL_alpha": a2},
            "S_ref_m2": S, "cases": out, "x_np_min_m": min(xs), "x_np_max_m": max(xs),
            "method": "hand bracket: Helmbold + declared downwash + Munk couple; not VLM, not measured"}


def cg_window(npb: dict, sm_nominal=(0.10, 0.20), sm_floor=0.05) -> dict:
    c = npb["pectoral"]["mac_m"]
    lo, hi = npb["x_np_min_m"], npb["x_np_max_m"]
    return {"mac_ref_m": c,
            "cg_x_for_sm_floor_everywhere_max_m": lo - sm_floor * c,
            "cg_x_nominal_window_m": [lo - sm_nominal[1] * c, hi - sm_nominal[0] * c],
            "ballast_must_reach_m": [lo - sm_nominal[1] * c - 0.002, hi - sm_nominal[0] * c],
            "rule": "SM = (x_np - x_cg)/MAC_pect; print a ballast bay that can put the MEASURED CG anywhere in "
                    "ballast_must_reach_m, so trim can follow the VLM NP without a reprint"}


def mass_budget(S_paired: float) -> list[dict]:
    rows = []
    for V in SCENARIO["release_speed_m_s"]["values"]:
        for CL in (0.4, 0.5, 0.6):
            rows.append({"V_m_s": V, "CL_trim": CL, "mass_max_kg": 0.5 * RHO_AIR * V * V * CL * S_paired / G})
    return rows


def requirements(panels_path: Path, card_path: Path, components_path: Path | None = None) -> dict:
    panels = json.loads(panels_path.read_text())
    mat = load_material(card_path)
    pect, pelv = planform(panels["fins"]["pectoral_L"]), planform(panels["fins"]["pelvic_L"])
    S_paired = 2 * (panels["fins"]["pectoral_L"]["area_flat_m2"] + panels["fins"]["pelvic_L"]["area_flat_m2"])
    m_max = SCENARIO["mass_kg"]["range"][1]
    body_vol, half_w = None, None
    if components_path:
        comps = json.loads(components_path.read_text())
        b = comps["components"]["body"]["check"]
        body_vol = b["volume_mm3"] * 1e-9
        half_w = b["bbox_mm"][1][1] * 1e-3
    sizing = {}
    for name, pf in (("pectoral", pect), ("pelvic", pelv)):
        sizing[name] = [size_fin(pf, mat, S_paired, m_max, t, 1.6e-3, t_root=1.2e-3, root_len=0.012,
                                 hs_grid=np.round(np.arange(0.4, 4.01, 0.2), 2) * 1e-3)
                        for t in (0.4e-3, 0.5e-3, 0.6e-3, 0.8e-3)]
    npb = neutral_point(pect, pelv, body_vol, half_w) if body_vol else None

    def _pf(pf):
        return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in pf.items()}
    return {"schema": SCHEMA_REQUIREMENTS, "evidence_kind": "analytic_requirements",
            "inputs": {"panels": {"path": _rel(panels_path), "sha256": _sha(panels_path),
                                  "candidate_sha256": panels.get("candidate_sha256")},
                       "components": ({"path": _rel(components_path), "sha256": _sha(components_path)}
                                      if components_path else None),
                       "material": {k: mat[k] for k in ("id", "card_path", "card_sha256", "source_url",
                                                         "source_sha256", "solid_density_kg_m3",
                                                         "flexural_modulus_Pa", "ultimate_tensile_strength_Pa",
                                                         "printer", "test_conditions")}},
            "scenario": SCENARIO, "planform": {"pectoral": _pf(pect), "pelvic": _pf(pelv)},
            "S_paired_m2": S_paired, "mass_budget": mass_budget(S_paired),
            "fin_sizing": sizing, "hook": hook(m_max, mat, stem_len=6e-3, stem_b=4e-3),
            "neutral_point_bracket": npb, "cg_window": cg_window(npb) if npb else None,
            "limits": ["no torsion of the fin about its span axis; the quarter-chord load is aft of the spar",
                       "no layer anisotropy, notch factor, cure variation, fatigue, impact or hand-handling loads",
                       "launch force profile, speed and alignment are unmeasured scenarios (SPEC-010 rule 4)",
                       "NP is a hand bracket, not a VLM or measurement; body lift beyond the Munk couple ignored",
                       "coupon properties are not fin-level verification (SPEC-010 analysis contract)"]}


def main(argv):
    panels, card, out = Path(argv[1]), Path(argv[2]), Path(argv[3])
    comps = Path(argv[4]) if len(argv) > 4 else panels.parent / "components.json"
    r = requirements(panels, card, comps if comps.exists() else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
    print(out, _sha(out))


if __name__ == "__main__":
    main(sys.argv)
