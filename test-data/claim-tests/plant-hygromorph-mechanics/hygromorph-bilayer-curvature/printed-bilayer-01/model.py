#!/usr/bin/env python3
"""Prediction model for the printed hygromorph bilayer (printed-bilayer-01).

Three jobs, all with numpy only:

  python3 model.py selfcheck
      The closed-form Timoshenko coefficient used by the claim
      `hygromorph-bilayer-curvature` is compared with an independent solve of force balance,
      moment balance and strain compatibility for two bonded layers. They must agree to
      machine precision for random layer thicknesses and moduli, otherwise nothing else here
      is trusted.

  python3 model.py design [--out design-sweep.json]
      Sizes the specimens BEFORE anything is printed. The input ranges in DESIGN_ASSUMPTIONS are
      assumptions used only to choose strip thickness, width and length so the experiment can
      work (curvature large enough to see, small enough for small-strain beam theory, strip
      narrow enough that it does not curl across its width). They are not data and are never
      used to score the claim.

  python3 model.py predict inputs.json [--out prediction.json]
      The pre-registered prediction. `inputs.json` holds the independently MEASURED layer
      thicknesses, moduli and swelling strains of the specimens (with uncertainties) and nothing
      about their curvature. Predicted curvature and its uncertainty are written out and
      committed before the curvature of any bilayer is measured.
"""
import json
import sys
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------------------------
# The law
# ----------------------------------------------------------------------------------------------

def timoshenko_coefficient(h1, h2, E1, E2):
    """Curvature per unit swelling mismatch, kappa / delta_eps, from the claim's closed form.

    kappa = 6(1+m)^2 / (h [3(1+m)^2 + (1+mn)(m^2 + 1/(mn))]) * delta_eps,
    m = h1/h2, n = E1/E2, h = h1 + h2   (layer 1 is the more-swelling, convex-side layer).
    """
    h1, h2, E1, E2 = map(np.asarray, (h1, h2, E1, E2))
    m, n, h = h1 / h2, E1 / E2, h1 + h2
    return 6 * (1 + m) ** 2 / (h * (3 * (1 + m) ** 2 + (1 + m * n) * (m ** 2 + 1 / (m * n))))


def bilayer_curvature(h1, h2, E1, E2, eps1, eps2):
    return timoshenko_coefficient(h1, h2, E1, E2) * (np.asarray(eps1) - np.asarray(eps2))


def bilayer_curvature_equilibrium(h1, h2, E1, E2, eps1, eps2):
    """Independent route: Euler-Bernoulli strain eps(z) = e0 + k z - eps_i in layer i, z measured
    from the interface (layer 1 on z in [0, h1], layer 2 on [-h2, 0]); zero net force and zero net
    moment about the interface. Solves the 2x2 linear system for (e0, k)."""
    A = np.array([[E1 * h1 + E2 * h2, E1 * h1 ** 2 / 2 - E2 * h2 ** 2 / 2],
                  [E1 * h1 ** 2 / 2 - E2 * h2 ** 2 / 2, E1 * h1 ** 3 / 3 + E2 * h2 ** 3 / 3]])
    b = np.array([E1 * h1 * eps1 + E2 * h2 * eps2,
                  E1 * h1 ** 2 / 2 * eps1 - E2 * h2 ** 2 / 2 * eps2])
    return np.linalg.solve(A, b)[1]


def selfcheck(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    worst = worst_common = 0.0
    for _ in range(n):
        h1, h2 = 10 ** rng.uniform(-1, 1, 2)          # arbitrary units
        E1, E2 = 10 ** rng.uniform(-3, 3, 2)          # six decades of modulus contrast
        e1, e2 = rng.uniform(-0.2, 0.3, 2)
        coef = timoshenko_coefficient(h1, h2, E1, E2)
        # Closed form against the equilibrium solve, per unit mismatch (avoids dividing by a
        # near-zero curvature when e1 is close to e2).
        a = bilayer_curvature_equilibrium(h1, h2, E1, E2, 1.0, 0.0)
        worst = max(worst, abs(a - coef) / coef)
        # A strain common to both layers is free expansion: it must not bend the strip.
        b = bilayer_curvature_equilibrium(h1, h2, E1, E2, e1, e1)
        worst_common = max(worst_common, abs(b) / coef)
        # And the full formula with arbitrary eigenstrains.
        c = bilayer_curvature_equilibrium(h1, h2, E1, E2, e1, e2)
        worst = max(worst, abs(c - coef * (e1 - e2)) / coef)
    ok_ref = abs(timoshenko_coefficient(1, 1, 1, 1) - 1.5 / 2.0) < 1e-12   # m = n = 1, h = 2: 3/(2h)
    print(f"max relative difference, closed form vs equilibrium solve, {n} random bilayers: {worst:.2e}")
    print(f"max |kappa| from a common eigenstrain, relative to the coefficient: {worst_common:.2e}")
    print(f"m = n = 1 reference value 3/(2h) with h = 2: {ok_ref}")
    assert worst < 1e-7 and worst_common < 1e-7 and ok_ref
    return worst


# ----------------------------------------------------------------------------------------------
# Design stage (assumptions, not data)
# ----------------------------------------------------------------------------------------------

DESIGN_ASSUMPTIONS = {
    "note": "Order-of-magnitude placeholders for sizing only. Replace by measurement; never used to score the claim.",
    "layer_thickness_mm": [0.3, 0.6, 1.2],              # total h = 2x this when m = 1
    "thickness_ratio_m": [0.5, 1.0, 2.0],
    "modulus_ratio_n": [0.1, 1.0, 10.0],
    "swelling_mismatch": [0.02, 0.05, 0.10],            # linear strain difference
    "strip_width_mm": [3.0, 5.0, 8.0],
    "strip_length_mm": [20.0, 30.0],
}

CHECKS = {
    "small_strain": "swelling mismatch <= 0.10 (beam theory is linear in small strain)",
    "slender": "h / R <= 0.1, with R = 1/kappa",
    "no_anticlastic": "w^2 / (R h) <= 1: wider strips curl across their width and leave the 1-D theory",
    "visible": "tip angle L*kappa >= 0.2 rad, and L*kappa <= 2*pi (less than one full turn)",
}


def design(out=None):
    A = DESIGN_ASSUMPTIONS
    rows = []
    for h_half in A["layer_thickness_mm"]:
        for m in A["thickness_ratio_m"]:
            h2 = h_half
            h1 = m * h2
            for n in A["modulus_ratio_n"]:
                E2 = 1.0
                E1 = n * E2
                for de in A["swelling_mismatch"]:
                    k = float(bilayer_curvature(h1, h2, E1, E2, de, 0.0))      # 1/mm
                    R = 1 / k
                    h = h1 + h2
                    for w in A["strip_width_mm"]:
                        for L in A["strip_length_mm"]:
                            ok = {
                                "small_strain": de <= 0.10,
                                "slender": h / R <= 0.1,
                                "no_anticlastic": w ** 2 / (R * h) <= 1.0,
                                "visible": 0.2 <= L * k <= 2 * np.pi,
                            }
                            rows.append({"h1_mm": h1, "h2_mm": h2, "m": m, "n": n, "d_eps": de, "w_mm": w, "L_mm": L,
                                         "kappa_per_mm": k, "radius_mm": R, "tip_angle_rad": L * k,
                                         "ok": all(ok.values()), "failed": [c for c, v in ok.items() if not v]})
    ok_rows = [r for r in rows if r["ok"]]
    summary = {
        "assumptions": A, "checks": CHECKS, "n_candidates": len(rows), "n_pass": len(ok_rows),
        "pass_by_width_mm": {str(w): sum(1 for r in ok_rows if r["w_mm"] == w) for w in A["strip_width_mm"]},
        "pass_by_length_mm": {str(L): sum(1 for r in ok_rows if r["L_mm"] == L) for L in A["strip_length_mm"]},
        "pass_by_modulus_ratio": {str(n): sum(1 for r in ok_rows if r["n"] == n) for n in A["modulus_ratio_n"]},
        "pass_by_mismatch": {str(d): sum(1 for r in ok_rows if r["d_eps"] == d) for d in A["swelling_mismatch"]},
        "pass_by_total_thickness_mm": {f"{r:.2f}": 0 for r in sorted({round(x['h1_mm'] + x['h2_mm'], 2) for x in rows})},
    }
    for r in ok_rows:
        summary["pass_by_total_thickness_mm"][f"{r['h1_mm'] + r['h2_mm']:.2f}"] += 1
    print(json.dumps({k: v for k, v in summary.items() if k.startswith("pass") or k == "n_candidates"}, indent=1))
    if out:
        Path(out).write_text(json.dumps({**summary, "rows": rows}, indent=1))
        print("wrote", out)
    return summary


# ----------------------------------------------------------------------------------------------
# Pre-registered prediction from MEASURED inputs
# ----------------------------------------------------------------------------------------------

def predict(inputs_path, out=None, n_mc=20000, seed=1):
    """inputs.json: {"specimens": [{"id", "h1_mm", "h2_mm", "E1_MPa", "E2_MPa", "eps1", "eps2",
                                   "sd": {"h1_mm", "h2_mm", "E1_MPa", "E2_MPa", "eps1", "eps2"}}]}
    Every field is measured independently of the bilayer's curvature. The Monte Carlo draws each
    input from a normal distribution with the stated standard deviation (moduli on a log scale),
    so the prediction carries the uncertainty the measurements imply."""
    rng = np.random.default_rng(seed)
    data = json.loads(Path(inputs_path).read_text())
    rows = []
    for s in data["specimens"]:
        sd = s["sd"]
        h1 = rng.normal(s["h1_mm"], sd["h1_mm"], n_mc)
        h2 = rng.normal(s["h2_mm"], sd["h2_mm"], n_mc)
        E1 = s["E1_MPa"] * np.exp(rng.normal(0, sd["E1_MPa"] / s["E1_MPa"], n_mc))
        E2 = s["E2_MPa"] * np.exp(rng.normal(0, sd["E2_MPa"] / s["E2_MPa"], n_mc))
        e1 = rng.normal(s["eps1"], sd["eps1"], n_mc)
        e2 = rng.normal(s["eps2"], sd["eps2"], n_mc)
        keep = (h1 > 0) & (h2 > 0)
        k = bilayer_curvature(h1[keep], h2[keep], E1[keep], E2[keep], e1[keep], e2[keep])
        k0 = float(bilayer_curvature(s["h1_mm"], s["h2_mm"], s["E1_MPa"], s["E2_MPa"], s["eps1"], s["eps2"]))
        rows.append({"id": s["id"], "kappa_pred_per_mm": k0,
                     "kappa_p16": float(np.percentile(k, 16)), "kappa_p84": float(np.percentile(k, 84)),
                     "radius_pred_mm": 1 / k0 if k0 else None})
    res = {"model": "Timoshenko bilayer (hygromorph-bilayer-curvature)", "specimens": rows,
           "note": "Computed from measured inputs only; commit before measuring any bilayer curvature."}
    if out:
        Path(out).write_text(json.dumps(res, indent=1))
        print("wrote", out)
    else:
        print(json.dumps(res, indent=1))
    return res


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    if cmd == "selfcheck":
        selfcheck()
    elif cmd == "design":
        design(out)
    elif cmd == "predict":
        predict(argv[2], out)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
