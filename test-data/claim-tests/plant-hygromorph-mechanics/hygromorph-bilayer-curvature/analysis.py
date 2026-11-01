#!/usr/bin/env python3
"""Timoshenko bilayer prediction vs measured dry-to-wet bending of pine cone scales.

Reads derived/measurements.csv (every number there cites its paper, page, table or figure) and
writes derived/analysis_output.json, which is what result.json `measured` reports.

Claim (hygromorph-bilayer-curvature):
    kappa = 6 (1+m)^2 / ( h [ 3 (1+m)^2 + (1+mn)(m^2 + 1/(mn)) ] ) * delta_eps
    m = h1/h2 (active/passive thickness), n = E1/E2, h = h1 + h2.
f(m, n) is invariant under (m, n) -> (1/m, 1/n), so which layer is called 1 does not matter.

Two specimen sets:
  quan2021   : Pinus torreyana. Layer thicknesses (Table 1, 'from the dimensions of the pine cone'),
               moduli and swelling strains (Table 1, quoted from Dawson et al. 1997, P. radiata),
               measured rotation of one isolated scale dry -> immersed (Fig. S1, 79 deg) and the
               length of the bending region (proximal stalk, 22.4 mm, measured on the Fig. 3b
               micro-CT against its 1 cm bar).  Predicted angle = kappa_pred * L_active.
  reyssat2009: Pinus coulteri scale (angle, Fig. 1d; single-cell strain, Fig. 1c/1e) with the
               pooled geometric ratios m ~ 1 and L_a/h_a ~ 10 (Fig. 3) and n ~ 5 (Dawson 1997).
               Predicted angle = f * delta_eps * (L_a/h_a) / (1 + m)   [h cancels].

Statistic per set: r = log10(theta_pred / theta_meas) = log10(kappa_pred / kappa_meas).
Pre-registered: |r| <= 0.18 supports, 0.18 < |r| <= 0.48 mixed, |r| > 0.48 or wrong sign refutes,
applied to the primary set (quan2021, the only one with tabulated h1, h2, E1, E2, strains) and to
the median |r| over sets (no set may exceed 0.48 for 'supports').  Ranges are the formula
evaluated at the extremes of the input ranges in the CSV.
Only the standard library is used.
"""
import csv, json, math, os, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "derived", "measurements.csv"))))


def val(set_, q, which="value"):
    for r in rows:
        if r["set"] == set_ and r["quantity"] == q:
            v = r[which]
            return float(v) if v not in ("", None) else None
    raise KeyError((set_, q))


def f_mn(m, n):
    return 6 * (1 + m) ** 2 / (3 * (1 + m) ** 2 + (1 + m * n) * (m * m + 1 / (m * n)))


def timoshenko_kappa(h1, h2, E1, E2, deps):
    m, n, h = h1 / h2, E1 / E2, h1 + h2
    return f_mn(m, n) * deps / h, m, n, h


def verdict_from_r(r, sign_ok=True):
    a = abs(r)
    if not sign_ok or a > 0.48:
        return "refutes"
    return "supports" if a <= 0.18 else "mixed"


out = {"sets": {}}

# ---------------- quan2021 ----------------
S = "quan2021"
h1, h2 = val(S, "h_active"), val(S, "h_passive")
E1, E2 = val(S, "E_active"), val(S, "E_passive")
deps = val(S, "eps_active") - val(S, "eps_passive")
La = val(S, "L_active")
th_meas = val(S, "theta_meas_deg")
kappa, m, n, h = timoshenko_kappa(h1, h2, E1, E2, deps)
th_pred = math.degrees(kappa * La)
kappa_meas = math.radians(th_meas) / La
r = math.log10(th_pred / th_meas)
# ranges: predicted angle extremes over (E1, deps, La); measured curvature extremes over (theta, La)
preds, measK = [], []
for E1x, epsx, Lax in itertools.product([val(S, "E_active", "low"), val(S, "E_active", "high")],
                                        [val(S, "eps_active", "low") - val(S, "eps_passive"), val(S, "eps_active", "high") - val(S, "eps_passive")],
                                        [val(S, "L_active", "low"), val(S, "L_active", "high")]):
    preds.append(timoshenko_kappa(h1, h2, E1x, E2, epsx)[0])
for thx, Lax in itertools.product([val(S, "theta_meas_deg", "low"), val(S, "theta_meas_deg", "high")],
                                  [val(S, "L_active", "low"), val(S, "L_active", "high")]):
    measK.append(math.radians(thx) / Lax)
r_lo, r_hi = math.log10(min(preds) / max(measK)), math.log10(max(preds) / min(measK))
simple = 1.5 * deps / h  # m = n = 1 limit stated in the claim
out["sets"][S] = {
    "species": "Pinus torreyana (geometry, angle); moduli and strains from Dawson et al. 1997 (P. radiata) as tabulated by Quan et al.",
    "inputs": {"h1_active_mm": h1, "h2_passive_mm": h2, "m": round(m, 4), "E1_GPa": E1, "E2_GPa": E2, "n": round(n, 4),
               "h_mm": h, "delta_eps": round(deps, 4), "L_active_mm": La},
    "f_mn": round(f_mn(m, n), 4),
    "kappa_pred_per_mm": round(kappa, 5),
    "radius_pred_mm": round(1 / kappa, 1),
    "theta_pred_deg": round(th_pred, 1),
    "theta_meas_deg": th_meas,
    "kappa_meas_per_mm": round(kappa_meas, 5),
    "ratio_pred_over_meas": round(th_pred / th_meas, 3),
    "r_log10": round(r, 3),
    "r_log10_range": [round(r_lo, 3), round(r_hi, 3)],
    "sign_ok": True,  # wetting bends towards the fibre (low-swelling) layer in both papers
    "verdict": verdict_from_r(r),
    "secondary_m1n1_kappa_per_mm": round(simple, 5),
    "secondary_m1n1_r_log10": round(math.log10(math.degrees(simple * La) / th_meas), 3),
}

# ---------------- reyssat2009 ----------------
S = "reyssat2009"
m = val(S, "m_thickness_ratio")
n = val(S, "n_modulus_ratio")
deps = val(S, "eps_active") - val(S, "eps_passive")
Lr = val(S, "La_over_ha")
th_meas = val(S, "theta_meas_deg")
h = val(S, "h_total")
f = f_mn(m, n)
# theta = kappa * L_a = f deps / h * L_a ; with h = h_a (1 + m) and L_a = Lr h_a: theta = f deps Lr / (1 + m)
th_pred = math.degrees(f * deps * Lr / (1 + m))
kappa = f * deps / h
r = math.log10(th_pred / th_meas)
preds = [math.degrees(f_mn(mx, n) * ex * Lx / (1 + mx)) for mx, ex, Lx in itertools.product(
    [val(S, "m_thickness_ratio", "low"), val(S, "m_thickness_ratio", "high")],
    [val(S, "eps_active", "low"), val(S, "eps_active", "high")],
    [val(S, "La_over_ha", "low"), val(S, "La_over_ha", "high")])]
r_lo = math.log10(min(preds) / val(S, "theta_meas_deg", "high"))
r_hi = math.log10(max(preds) / val(S, "theta_meas_deg", "low"))
# alternative consistent pairing: humidity range 0 -> 100 % RH (strain 0.113) with the text's 100 deg
th_pred_rh = math.degrees(f * val(S, "eps_active", "low") * Lr / (1 + m))
r_rh = math.log10(th_pred_rh / val(S, "theta_meas_deg", "low"))
# the authors' reading L_a/h ~ 10 (p. 954) instead of L_a/h_a ~ 10 (Fig. 3b)
th_pred_authors = math.degrees(f * deps * Lr)
out["sets"][S] = {
    "species": "Pinus coulteri (angle, strain); m and L_a/h_a pooled over several species; n from Dawson et al. 1997",
    "inputs": {"m": m, "n": n, "delta_eps": deps, "La_over_ha": Lr, "h_mm_quoted": h},
    "f_mn": round(f, 4),
    "kappa_pred_per_mm_for_h_1mm": round(kappa, 4),
    "theta_pred_deg": round(th_pred, 1),
    "theta_meas_deg": th_meas,
    "ratio_pred_over_meas": round(th_pred / th_meas, 3),
    "r_log10": round(r, 3),
    "r_log10_range": [round(r_lo, 3), round(r_hi, 3)],
    "sign_ok": True,
    "verdict": verdict_from_r(r),
    "sensitivity": {
        "rh_pairing_theta_pred_deg": round(th_pred_rh, 1), "rh_pairing_theta_meas_deg": val(S, "theta_meas_deg", "low"),
        "rh_pairing_r_log10": round(r_rh, 3),
        "authors_La_over_h_10_theta_pred_deg": round(th_pred_authors, 1),
        "authors_La_over_h_10_r_log10": round(math.log10(th_pred_authors / th_meas), 3),
        "authors_quoted_f": val(S, "authors_f_mn"), "authors_quoted_theta_pred_deg": val(S, "authors_theta_pred_deg"),
    },
}

# ---------------- combined ----------------
rs = {k: v["r_log10"] for k, v in out["sets"].items()}
abs_rs = sorted(abs(x) for x in rs.values())
median_abs = abs_rs[len(abs_rs) // 2] if len(abs_rs) % 2 else 0.5 * (abs_rs[len(abs_rs) // 2 - 1] + abs_rs[len(abs_rs) // 2])
primary = out["sets"]["quan2021"]
if any(not v["sign_ok"] for v in out["sets"].values()) or max(abs_rs) > 0.48 or abs(primary["r_log10"]) > 0.48:
    verdict = "refutes"
elif abs(primary["r_log10"]) <= 0.18 and median_abs <= 0.18:
    verdict = "supports"
else:
    verdict = "mixed"
out["combined"] = {
    "primary_set": "quan2021",
    "r_log10_by_set": rs,
    "median_abs_r": round(median_abs, 3),
    "max_abs_r": round(max(abs_rs), 3),
    "n_sets": len(rs),
    "n_scales_with_measured_angle": 2,
    "verdict": verdict,
    "rule": "supports if primary |r| <= 0.18 and median |r| <= 0.18 and no set > 0.48; refutes if any |r| > 0.48 or wrong sign; else mixed",
}
json.dump(out, open(os.path.join(HERE, "derived", "analysis_output.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
