"""One-way static coupling: member-pressure record -> line load -> Euler-Bernoulli cantilever ray.

The flow does not see the deflection (no feedback; the verdict says so). EI is a declared interval;
because the linear beam's deflection is exactly proportional to 1/EI at fixed load, the interval
maps to [w(EI_hi), w(EI_lo)] and both ends are solved, never interpolated.
"""
from __future__ import annotations

import copy
from fractions import Fraction

import numpy as np

from engineering.fin_mechanics import beam

from . import MODEL_VERSION, SCHEMA_RESULT
from .contract import parse_pressure, parse_target
from .traction import bending_moment, element_means, mesh_resultants, resultants

_GL_X, _GL_W = np.polynomial.legendre.leggauss(4)  # exact for the degree-4 integrand below


def moment_area_tip(s, q, EI: float) -> float:
    """Independent tip reference: w(L) = int_0^L M(x) (L - x) / EI dx, M exact piecewise cubic.

    Gauss-Legendre with 4 points per station segment integrates the piecewise degree-4 integrand
    exactly up to round-off; it shares no code with the FEM."""
    L = s[-1]
    tot = 0.0
    for a, b in zip(s, s[1:]):
        fa, fb = float(a), float(b)
        for xg, wg in zip(_GL_X, _GL_W):
            x = 0.5 * (fb - fa) * xg + 0.5 * (fa + fb)
            M = float(bending_moment(s, q, Fraction(x)))
            tot += 0.5 * (fb - fa) * wg * M * (float(L) - x)
    return tot / EI


def _solve(L: Fraction, EI: float, q_el: list[Fraction], n_el: int):
    arr = np.array([float(v) for v in q_el])
    return beam.solve_checked(float(L), EI, lambda xm: arr, n_el)


def disabled_load(record: dict) -> dict:
    """Same record with every face pressure set to 0: the load-disabled control."""
    r = copy.deepcopy(record)
    for st in r["stations"]:
        st["p_pos_Pa"] = "0"
        st["p_neg_Pa"] = "0"
    r["source"] = dict(r["source"], producer=r["source"].get("producer", "") + " [LOAD DISABLED CONTROL]")
    return r


def run(record: dict, target_json: dict) -> dict:
    target = parse_target(target_json)
    p = parse_pressure(record, target)
    s, q, L = p["s_m"], p["q_N_per_m"], p["L_m"]
    n_el = target["n_elements"]
    exact_res = resultants(s, q)
    q_el = element_means(s, q, n_el)
    mesh_res = mesh_resultants(q_el, L)
    F, M = exact_res["F_N"], exact_res["M_root_Nm"]

    ends = {}
    for tag, EI in (("EI_lo", target["EI_lo"]), ("EI_hi", target["EI_hi"])):
        sol, chk = _solve(L, float(EI), q_el, n_el)
        ref = moment_area_tip(s, q, float(EI))
        ends[tag] = {
            "EI_Nm2": str(EI), "tip_m": sol.tip, "max_abs_slope_rad": sol.max_abs_slope,
            "tip_moment_area_reference_m": ref,
            "tip_rel_error_vs_reference": (abs(sol.tip - ref) / abs(ref)) if ref != 0 else abs(sol.tip),
            "validity": chk,
            "x_m": sol.x.tolist(), "w_m": sol.w.tolist(),
        }

    nodes = [Fraction(k) * L / n_el for k in range(n_el + 1)]
    xs = sorted(set(nodes) | set(s))
    Ms = [bending_moment(s, q, x) for x in xs]
    k = max(range(len(xs)), key=lambda i: abs(Ms[i]))
    stress = None
    if target["section"] is not None:
        c, inertia = target["section"]["c_m"], target["section"]["I_m4"]
        stress = {"sigma_max_Pa": float(abs(Ms[k]) * c / inertia), "c_m": str(c), "I_m4": str(inertia),
                  "section_status": target["section"]["status"],
                  "note": "sigma = |M| c / I at the station of max |M|; section declared, not measured"}

    def rel(a, b):
        return float(abs(a - b) / abs(b)) if b != 0 else float(abs(a - b))

    return {
        "schema": SCHEMA_RESULT, "model_version": MODEL_VERSION,
        "evidence_kind": p["evidence_kind"], "scope": p["scope"], "dimensionality": p["dimensionality"],
        "coupling": "one-way static: the flow field is not updated by the deflection",
        "member_id": target["id"], "frame_id": target["frame_id"], "L_m": str(L),
        "tributary_width_m": str(p["width_m"]),
        "stations": {"s_m": [str(x) for x in s], "jump_Pa": [str(x) for x in p["jump_Pa"]],
                     "q_N_per_m": [str(x) for x in q]},
        "unit_derivation": "q [N/m] = (p_neg - p_pos) [Pa] * tributary width [m]; F [N] = int q ds; "
                           "M_root [N m] = int q s ds",
        "resultants_exact": {"F_N": str(F), "M_root_Nm": str(M)},
        "resultants_float": {"F_N": float(F), "M_root_Nm": float(M)},
        "conservation": {
            "mesh_force_rel_diff": rel(mesh_res["F_N"], F),
            "mesh_root_moment_rel_diff": rel(mesh_res["M_root_Nm"], M),
            "note": "element-mean transfer keeps force exactly; the root-moment difference is O(h^2)",
        },
        "max_abs_bending_moment_Nm": float(abs(Ms[k])), "max_moment_at_m": str(xs[k]),
        "stress": stress,
        "stress_status": "computed from declared section" if stress else
                         "SECTION_NOT_DECLARED: stress needs c and I, which are not inferable from EI",
        "EI_interval": {"lo_Nm2": str(target["EI_lo"]), "hi_Nm2": str(target["EI_hi"]),
                        "status": target["EI_status"], "source": target["EI_source"]},
        "deflection": ends,
        "n_elements": n_el,
        "source": p["source"], "time": p["time"],
        "not_established": [
            "biological validity of the load, the member or EI",
            "fluid-structure feedback (one-way only)",
            "that a 2D section field describes a finite 3D fin" if p["dimensionality"] != "3d" else
            "accuracy of the 3D field beyond its own receipt's checks",
        ],
    }


def grid_study(record: dict, target_json: dict, ns=(8, 16, 32, 64, 128)) -> dict:
    """Tip error of the element-mean transfer against the moment-area reference, by mesh size."""
    out = []
    for n in ns:
        t = dict(target_json, n_elements=n)
        r = run(record, t)
        out.append({"n_elements": n, "tip_rel_error": r["deflection"]["EI_lo"]["tip_rel_error_vs_reference"],
                    "moment_rel_diff": r["conservation"]["mesh_root_moment_rel_diff"]})
    orders = []
    for a, b in zip(out, out[1:]):
        if a["tip_rel_error"] > 0 and b["tip_rel_error"] > 0:
            orders.append(float(np.log2(a["tip_rel_error"] / b["tip_rel_error"])))
    return {"levels": out, "observed_order": orders}
