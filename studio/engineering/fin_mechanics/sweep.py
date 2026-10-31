"""Sweep an ASSUMED, log-spaced range of bending stiffness EI over a declared load and report validity.

EI of a fish fin ray is UNKNOWN to this package.  The sweep range is an explicit assumption with no
biological calibration.  The only sourced EI number read (Alben, Madden & Lauder 2007, bluegill sunfish,
three-point bending: B = EI ~ 1e-6 to 1e-5 J m = N m^2) is carried as CONTEXT ONLY, for a different
species, scale, medium (water) and boundary condition; it is not used to set any result.

CLI:  python -m engineering.fin_mechanics.sweep REQUEST.json RESULT.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import MODEL_VERSION, SCHEMA_REQUEST, SCHEMA_RESULT
from . import beam
from .load_bridge import Refusal, bridge, exact

PKG = Path(__file__).resolve().parent

SOURCES_READ = [
    {"ref": "Alben S, Madden PG, Lauder GV (2007) The mechanics of active fin-shape control in ray-finned "
            "fishes. J R Soc Interface 4(13):243-256, doi:10.1098/rsif.2006.0181 (PMC2359861)",
     "read": "FULL-TEXT PAGE on PMC, fetched through a summarising fetch tool (not raw PDF); abstract and "
             "sections 3.4, 5.2, 5.3 consulted through that tool's answers. Numbers below are as relayed "
             "by the tool and should be re-checked against the PDF before any publication use.",
     "used_for": ["context-only EI scale: B = EI ~ 1e-6 to 1e-5 J m (N m^2) for bluegill sunfish rays via "
                  "three-point bending (composite E ~ 1e8-1e9 N/m^2, I ~ 1e-6 cm^4)",
                  "boundary-condition sensitivity: cantilever force-displacement slope with both "
                  "hemitrichs clamped ~1.98 N/m, about 12x the one-hemitrich-free value",
                  "the paper's model is a BILAMINAR elastica with intraray shear, not a single "
                  "Euler-Bernoulli beam; this package's single-beam EI is an effective-stiffness proxy"],
     "not_used_for": "any numerical result, calibration or validation of this surrogate"},
    {"ref": "Wikipedia, 'Euler-Bernoulli beam theory' (secondary source)",
     "read": "first ~100,000 of ~135,811 characters via summarising fetch tool: governing equation, "
             "cantilever point-load curve, small-deflection assumptions. Uniform-load formula NOT confirmed "
             "from it; verified by independent integration in tests. Textbook primary references it cites "
             "(Timoshenko; Gere) were NOT read.",
     "used_for": ["beam equation d2/dx2(EI d2w/dx2)=q; w=F(3Lx^2-x^3)/(6EI) for tip load"]},
]

NOT_ESTABLISHED = [
    "biological feasibility of any fin, ray or flight design",
    "the stiffness EI of any real fish fin ray (it is an assumed range here)",
    "fluid-structure interaction: the load is a fixed mean pressure proxy, not coupled to deformation",
    "fin membrane, bilaminar hemitrich shear, active muscle control, ray taper, joints or viscoelasticity",
    "large-deformation (elastica) behaviour: results beyond the declared small-deformation limit are flagged invalid",
    "calibration of rho, CL, tributary width or ray length (all declared, none measured)",
    "that the glide package's candidate is flyable (owned by the glide receipt, not by this package)",
]

MEASUREMENT_QUESTION = {
    "question": ("What is the effective flexural rigidity EI (N m^2) of an excised ray of the target fin, "
                 "as a function of distance from its base, under the clamping condition that matches its "
                 "in-fin boundary condition, and is it above or below EI_crit_Nm2 of this request?"),
    "apparatus": ("Clamp the ray base (state whether both hemitrichs or one is clamped; Alben et al. 2007 "
                  "report ~12x stiffness difference between these), load the free end with a calibrated "
                  "micro-force transducer (resolution <= 1 microN) or a calibrated cantilever probe, "
                  "track tip displacement optically (resolution <= 1 micrometre), keep the specimen "
                  "hydrated, record force-displacement for tip/L < 0.1 (inside the linear range), and "
                  "repeat with the clamp moved along the ray to get EI(x). Cross-check with micro-CT "
                  "second moment of area."),
    "analysis": "EI = P L^3 / (3 delta) from the linear slope of tip force P vs tip displacement delta.",
    "decision_rule": ("If measured EI >= EI_crit_Nm2 the declared load stays inside the small-deformation "
                      "limit for this geometry; if EI < EI_crit_Nm2 the linear model is invalid at the "
                      "declared load and a large-deformation model (or a lower load) is required."),
    "turns": "the ASSUMED EI range in this package into measured data (>= several rays, with spread)",
}

CONTEXT_EI_BLUEGILL_NM2 = [1e-6, 1e-5]  # context only, see SOURCES_READ


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def code_hashes() -> dict:
    files = sorted(p for p in PKG.glob("*.py"))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def code_sha256() -> str:
    return sha256_bytes(canonical(code_hashes()))


def _frac(req, section, key, default=None):
    d = req.get(section, {})
    if key not in d:
        if default is None:
            raise Refusal("MISSING_FIELD", f"{section}.{key}")
        return exact(default, key)
    return exact(d[key], f"{section}.{key}")


def ei_grid(EI_min: Fraction, EI_max: Fraction, n: int) -> np.ndarray:
    if not (0 < EI_min < EI_max) or n < 2:
        raise Refusal("BAD_EI_RANGE", "need 0 < EI_min < EI_max and n >= 2")
    return np.logspace(np.log10(float(EI_min)), np.log10(float(EI_max)), n)


def critical_EI(q: Fraction, L: Fraction, tip_lim: Fraction, slope_lim: Fraction) -> dict:
    """Exact smallest EI with the UNIFORM-load linear solution inside both declared limits."""
    ei_tip = q * L**3 / (8 * tip_lim)      # q L^4/(8 EI) <= tip_lim*L
    ei_slope = q * L**3 / (6 * slope_lim)  # q L^3/(6 EI) <= slope_lim
    ei = max(ei_tip, ei_slope)
    return {"EI_crit_tip_Nm2_exact": str(ei_tip), "EI_crit_slope_Nm2_exact": str(ei_slope),
            "EI_crit_Nm2_exact": str(ei), "EI_crit_Nm2_float": float(ei),
            "binding_limit": "tip_over_L" if ei_tip >= ei_slope else "slope"}


def convergence_study(q, L, EI, ns=(2, 4, 8, 16, 32)) -> dict:
    """Grid refinement for the declared uniform load: sup-norm error of the interpolated FE profile
    versus the closed form, observed order between successive halvings.  Static problem: there is no
    time step, hence no time-step convergence to report."""
    xs = np.linspace(0, L, 401)
    exact_w = beam.w_uniform(xs, q, L, EI)
    errs, tips = [], []
    for n in ns:
        sol = beam.solve_cantilever(L, EI, q, n)
        w, _ = sol.evaluate(xs)
        errs.append(float(np.max(np.abs(w - exact_w)) / abs(exact_w[-1])))
        tips.append(abs(sol.tip - beam.tip_deflection_uniform(q, L, EI)) / beam.tip_deflection_uniform(q, L, EI))
    orders = [float(np.log2(errs[i] / errs[i + 1])) if errs[i + 1] > 0 and errs[i] > 0 else None
              for i in range(len(errs) - 1)]
    # Variable-EI case (non-trivial discretisation error): EI(x)=EI0 (1-0.5 x/L)^3, tip load,
    # reference by independent quadrature of the unit-load integral.
    from scipy.integrate import quad
    P = 1.0
    ref = quad(lambda s: P * (L - s) ** 2 / (EI * (1 - 0.5 * s / L) ** 3), 0, L, epsabs=0, epsrel=1e-13)[0]
    tn = (4, 8, 16, 32, 64)
    terr = [abs(beam.solve_cantilever(L, lambda x: EI * (1 - 0.5 * x / L) ** 3, 0.0, n, tip_force=P).tip - ref) / ref
            for n in tn]
    torders = [float(np.log2(terr[i] / terr[i + 1])) for i in range(len(terr) - 1)]
    return {
        "uniform_constant_EI": {"n_elements": list(ns), "profile_sup_rel_error": errs,
                                "tip_rel_error_nodal": tips, "observed_order_profile": orders,
                                "expected_order_profile": 4,
                                "note": "nodal values are exact for constant EI; the profile error is Hermite interpolation error, O(h^4)"},
        "tapered_EI_midpoint_rule": {"n_elements": list(tn), "tip_rel_error": terr,
                                     "observed_order": torders, "expected_order": 2,
                                     "taper": "EI(x)=EI0*(1-0.5 x/L)^3, tip force 1 N, illustrative; reference = scipy quad unit-load integral"},
        "time_step": "not applicable: static solution, no time integration",
    }


def run(request: dict) -> dict:
    """Execute a frontier.finmech.request/1 and return a frontier.finmech.result/1 dict."""
    inputs_sha = sha256_bytes(canonical(request))
    base = {"schema": SCHEMA_RESULT, "model_version": MODEL_VERSION, "evidence_kind": "simulated",
            "inputs_sha256": inputs_sha, "code_sha256": code_sha256(), "code_files_sha256": code_hashes(),
            "not_established": NOT_ESTABLISHED, "sources_read": SOURCES_READ}
    try:
        if request.get("schema") != SCHEMA_REQUEST:
            raise Refusal("BAD_SCHEMA", f"expected {SCHEMA_REQUEST}")
        br = bridge(request)
        el = request.get("elastic", {})
        ei_min, ei_max = exact(el.get("EI_min_Nm2"), "EI_min_Nm2"), exact(el.get("EI_max_Nm2"), "EI_max_Nm2")
        n_ei = int(el.get("n_points", 61))
        if el.get("EI_status") != "ASSUMED_RANGE_NOT_MEASURED":
            raise Refusal("EI_STATUS", "elastic.EI_status must be exactly 'ASSUMED_RANGE_NOT_MEASURED'")
        grid = ei_grid(ei_min, ei_max, n_ei)
        tip_lim = _frac(request, "validity", "tip_over_L_max", "1/10")
        slope_lim = _frac(request, "validity", "slope_max_rad", "1/5")
        n_el = int(request.get("numerics", {}).get("n_elements", 64))
        q = Fraction(br["exact"]["q_line_N_per_m"])
        L = Fraction(br["exact"]["L_ray_m"])
        qf, Lf, F = float(q), float(L), br["F_total_N"]
        crit = critical_EI(q, L, tip_lim, slope_lim)
        rows = []
        max_rel = 0.0
        for EI in grid:
            sol_u, chk_u = beam.solve_checked(Lf, EI, qf, n_el, 0.0, float(tip_lim), float(slope_lim))
            sol_t, chk_t = beam.solve_checked(Lf, EI, 0.0, n_el, F, float(tip_lim), float(slope_lim))
            au = beam.tip_deflection_uniform(qf, Lf, EI)
            at = beam.tip_deflection_point_load(F, Lf, EI)
            max_rel = max(max_rel, abs(sol_u.tip - au) / au, abs(sol_t.tip - at) / at)
            rows.append({"EI_Nm2": float(EI),
                         "uniform": {"tip_m": sol_u.tip, "tip_over_L": chk_u["tip_over_L"],
                                     "max_slope_rad": chk_u["max_slope_rad"], "valid": chk_u["valid"],
                                     "flag": chk_u["flag"], "analytic_tip_m": au},
                         "tip_equivalent": {"tip_m": sol_t.tip, "tip_over_L": chk_t["tip_over_L"],
                                            "max_slope_rad": chk_t["max_slope_rad"], "valid": chk_t["valid"],
                                            "flag": chk_t["flag"], "analytic_tip_m": at}})
        n_valid = sum(r["uniform"]["valid"] for r in rows)
        EI_mid = float(np.sqrt(float(ei_min) * float(ei_max)))
        conv = convergence_study(qf, Lf, EI_mid)
        ctrl = beam.control_residuals()
        ctrl_max = max(v for c in ctrl.values() for k, v in c.items() if k.endswith("residual"))
        res = dict(base)
        res.update({
            "verdict": "ok",
            "request_echo": {"candidate_witness": request["candidate"]["solver_result"]["witness"],
                             "fin": request.get("fin"), "elastic": el,
                             "validity_limits": {"tip_over_L_max": str(tip_lim), "slope_max_rad": str(slope_lim)},
                             "n_elements": n_el},
            "assumptions": [
                "Euler-Bernoulli (no shear deformation), linear elastic, static, constant EI along the ray",
                "single clamped-free cantilever ray; clamped base; free tip",
                "load = mean aerodynamic lift-pressure proxy p = 0.5*rho*V^2*CL from DECLARED rho, V, CL; "
                "uniform along the ray and normal to it; NOT a measured fin pressure",
                "line load q_line = p * tributary width (width declared, see load_bridge.inputs)",
                "EI swept over an ASSUMED log-spaced range [%s, %s] N m^2, %d points; no biological calibration" %
                (ei_min, ei_max, n_ei),
                "small-deformation validity limits are DECLARED thresholds, not derived from material",
            ],
            "load_bridge": br,
            "EI_assumed_range": {"status": "ASSUMED_RANGE_NOT_MEASURED", "min_Nm2": str(ei_min),
                                 "max_Nm2": str(ei_max), "n_points": n_ei, "spacing": "log10-uniform"},
            "EI_context_only": {"bluegill_sunfish_B_range_Nm2": CONTEXT_EI_BLUEGILL_NM2,
                                "warning": "different species, length, medium, boundary condition; context only, "
                                           "see sources_read; not a calibration of this surrogate"},
            "critical_stiffness": crit,
            "sweep": {"rows": rows,
                      "n_points": len(rows), "n_valid_uniform": int(n_valid),
                      "n_invalid_uniform": len(rows) - int(n_valid),
                      "EI_mid_for_convergence_Nm2": EI_mid},
            "validity": {"policy": "FLAG: every row carries valid/flag; invalid rows are reported, not hidden; "
                                   "beam.require_valid()/solve_checked(strict=True) raise SmallDeformationViolation",
                         "any_invalid": bool(len(rows) - n_valid),
                         "fraction_of_assumed_range_valid_uniform": n_valid / len(rows)},
            "convergence": conv,
            "controls": {"analytic_residuals_vs_independent_quadrature": ctrl, "max_rel_residual": ctrl_max,
                         "fem_vs_analytic_max_rel_diff_over_sweep": max_rel},
            "measurement_question": MEASUREMENT_QUESTION,
            "units": {"EI": "N m^2", "q_line": "N/m", "p": "Pa", "L": "m", "tip": "m", "slope": "rad"},
        })
        return res
    except Refusal as r:
        out = dict(base)
        out.update(r.to_json())
        return out


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    req = json.loads(Path(argv[0]).read_text())
    res = run(req)
    Path(argv[1]).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    return 0 if res.get("verdict") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
