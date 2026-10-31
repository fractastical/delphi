#!/usr/bin/env python3
"""Does the coefficient of variation of stature and weight track growth velocity?
Pre-registered tests T1-T3 (see result.json) on the CDC 2000 LMS references,
with WHO 2007 height and CDC infant tables as secondary checks.

Deviation from the pre-registration (recorded in result.json): the "exact" CV of
the Box-Cox (LMS) distribution has infinite variance whenever L <= -0.5, which is
the case for weight at most ages (L down to -1.87), so the LMS S parameter (Cole's
coefficient of variation) is used as the CV for the verdict; the quadrature CV is
still reported where it exists (L > -0.5) as a check.
Run after fetch.py; prints a JSON summary."""
import json, os

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
Z = np.linspace(-4, 4, 8001)
PHI = np.exp(-0.5 * Z ** 2); PHI /= np.trapezoid(PHI, Z)


def lms_cv_exact(L, M, S):
    """CV of the Box-Cox (LMS) distribution by quadrature over z in [-4, 4]; NaN where undefined."""
    if L <= -0.5 or np.any(1 + L * S * Z <= 0):
        return float("nan")
    X = M * np.exp(S * Z) if abs(L) < 1e-9 else M * np.power(1 + L * S * Z, 1.0 / L)
    mean = np.trapezoid(X * PHI, Z)
    var = np.trapezoid(X ** 2 * PHI, Z) - mean ** 2
    return float(np.sqrt(max(var, 0.0)) / mean)


def series_table(d):
    d = d.sort_values("age_years").reset_index(drop=True).copy()
    d["cv"] = d["S"]
    d["cv_exact"] = [lms_cv_exact(l, m, s) for l, m, s in zip(d["L"], d["M"], d["S"])]
    d["velocity"] = np.gradient(d["M"].to_numpy(), d["age_years"].to_numpy())
    return d


def tests(d, lo=2.5, hi=19.5, cv="cv"):
    d = d[(d.age_years >= lo - 1e-9) & (d.age_years <= hi + 1e-9)]
    rho, p = spearmanr(d[cv], d["velocity"])
    t1 = bool(rho > 0 and p < 0.01)
    ado = d[(d.age_years >= 8) & (d.age_years <= 19)]
    age_phv = float(ado.loc[ado["velocity"].idxmax(), "age_years"])
    age_cvmax = float(ado.loc[ado[cv].idxmax(), "age_years"])
    cv_peak = float(ado[cv].max())
    pre = d[(d.age_years >= 4) & (d.age_years <= 11)]
    cv_min = float(pre[cv].min()); age_cvmin = float(pre.loc[pre[cv].idxmin(), "age_years"])
    t2 = bool(abs(age_cvmax - age_phv) <= 1.5 and cv_peak >= 1.05 * cv_min)
    before = d[d.age_years <= age_phv]
    age_vmin = float(before.loc[before["velocity"].idxmin(), "age_years"])
    child = d[d.age_years <= age_vmin]
    if len(child) >= 3:
        rho3, p3 = spearmanr(child[cv], child["velocity"])
        t3 = bool(rho3 > 0); t3_sig_neg = bool(rho3 < 0 and p3 < 0.01)
        rho3 = round(float(rho3), 4); p3 = float(f"{p3:.3g}")
    else:  # velocity never decelerates before the spurt: no childhood segment exists
        rho3 = p3 = None; t3 = False; t3_sig_neg = False
    return {
        "n_ages": int(len(d)), "age_range": [float(d.age_years.min()), float(d.age_years.max())],
        "cv_at_start": round(float(d[cv].iloc[0]), 4), "cv_min_4_11": round(cv_min, 4), "age_cv_min_4_11": age_cvmin,
        "cv_peak_8_19": round(cv_peak, 4), "age_cv_peak_8_19": age_cvmax, "cv_at_end": round(float(d[cv].iloc[-1]), 4),
        "age_peak_velocity_8_19": age_phv, "peak_velocity": round(float(ado["velocity"].max()), 3),
        "age_min_velocity_before_spurt": age_vmin, "min_velocity_before_spurt": round(float(before["velocity"].min()), 3),
        "T1_spearman_rho": round(float(rho), 4), "T1_p": float(f"{p:.3g}"), "T1": t1,
        "T2": t2,
        "T3_childhood_rho": rho3, "T3_childhood_p": p3, "T3_childhood_n": int(len(child)),
        "T3": t3, "T3_significant_negative": t3_sig_neg,
    }


def main():
    lms = pd.read_csv(os.path.join(HERE, "derived", "lms.csv"))
    out = {"primary": {}, "exact_cv_check": {}, "secondary": {}}
    for series in ("cdc_stature", "cdc_weight"):
        for sex in ("M", "F"):
            d = series_table(lms[(lms.series == series) & (lms.sex == sex)])
            out["primary"][f"{series}_{sex}"] = tests(d)
            if d["cv_exact"].notna().all():
                out["exact_cv_check"][f"{series}_{sex}"] = tests(d, cv="cv_exact")
            else:
                out["exact_cv_check"][f"{series}_{sex}"] = {"undefined_ages": int(d["cv_exact"].isna().sum()), "L_min": float(d.L.min())}
    for sex in ("M", "F"):
        d = series_table(lms[(lms.series == "who_height") & (lms.sex == sex)])
        out["secondary"][f"who_height_{sex}"] = tests(d, lo=5.5, hi=18.5)
    for series in ("cdc_infant_length", "cdc_infant_weight"):
        for sex in ("M", "F"):
            d = series_table(lms[(lms.series == series) & (lms.sex == sex)])
            rho, p = spearmanr(d["cv"], d["velocity"])
            out["secondary"][f"{series}_{sex}"] = {
                "cv_birth": round(float(d["cv"].iloc[0]), 4), "cv_36mo": round(float(d["cv"].iloc[-1]), 4),
                "spearman_cv_velocity": round(float(rho), 4), "p": float(f"{p:.3g}"), "n_ages": int(len(d))}
    prim = out["primary"]
    n_all = sum(all(v[k] for k in ("T1", "T2", "T3")) for v in prim.values())
    n_t1_fail = sum(not v["T1"] for v in prim.values())
    n_t3_signeg = sum(v["T3_significant_negative"] for v in prim.values())
    if n_all >= 3:
        verdict = "supports"
    elif n_t1_fail >= 3 or n_t3_signeg >= 3:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["summary"] = {"series_passing_T1_T2_T3": n_all, "series_failing_T1": n_t1_fail,
                      "series_with_significant_negative_T3": n_t3_signeg,
                      "series_passing_T1": sum(v["T1"] for v in prim.values()),
                      "series_passing_T2": sum(v["T2"] for v in prim.values()),
                      "verdict": verdict}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
