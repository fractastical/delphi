"""Test of thompson1917-ch10-02: can the suture of a Turritella be a geodesic of its enveloping right cone?

A geodesic on a right circular cone of half-angle b (apical angle alpha = 2b) is a straight line on the
developed sector of angle 2*pi*sin(b). A straight line sweeps exactly pi of polar angle about the apex, so the
geodesic winds at most N_geo = pi / (2*pi*sin b) = 1 / (2 sin b) times round the cone in total, and at most
half of that while approaching the apex. A suture with more whorls than N_geo cannot be such a geodesic.

Reads derived/pandita2013_turritellidae.csv (transcribed by fetch.py from Pandita et al. 2013, Tables 2-6).
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")


def main():
    df = pd.read_csv(os.path.join(DERIVED, "pandita2013_turritellidae.csv"))
    # transcription check: the published ratio columns must agree with the measurements they were computed from
    chk = np.abs(df["Wang_mm"] / df["L_mm"] - df["Wang_L"]) < 2e-3
    chk &= np.abs(df["Wsut_mm"] / df["L_mm"] - df["Wsut_L"]) < 2e-3
    d = df[df["alpha_deg"].notna() & df["whorl_number"].notna()].copy()
    b = np.radians(d["alpha_deg"] / 2)
    d["N_geo_total"] = 1 / (2 * np.sin(b))
    d["N_geo_approaching_apex"] = d["N_geo_total"] / 2
    d["R"] = d["whorl_number"] / d["N_geo_total"]
    d["R_minus2whorls"] = (d["whorl_number"] - 2) / d["N_geo_total"]
    d["alpha_required_deg_for_observed_whorls"] = np.degrees(2 * np.arcsin(1 / (2 * d["whorl_number"])))
    d.round(4).to_csv(os.path.join(DERIVED, "geodesic_bound_per_specimen.csv"), index=False)

    frac_gt1 = float((d["R"] > 1).mean())
    out = {
        "n_rows_transcribed": int(len(df)), "n_rows_passing_ratio_check": int(chk.sum()),
        "n_specimens_with_alpha_and_whorls": int(len(d)), "n_species": int(d["species"].nunique()),
        "alpha_deg_range": [float(d["alpha_deg"].min()), float(d["alpha_deg"].max())],
        "whorl_number_range": [float(d["whorl_number"].min()), float(d["whorl_number"].max())],
        "N_geo_total_range": [round(float(d["N_geo_total"].min()), 3), round(float(d["N_geo_total"].max()), 3)],
        "R_median": round(float(d["R"].median()), 3), "R_min": round(float(d["R"].min()), 3), "R_max": round(float(d["R"].max()), 3),
        "fraction_R_gt_1": round(frac_gt1, 3),
        "fraction_R_gt_1_after_subtracting_2_whorls": round(float((d["R_minus2whorls"] > 1).mean()), 3),
        "fraction_whorls_gt_apex_approaching_bound": round(float((d["whorl_number"] > d["N_geo_approaching_apex"]).mean()), 3),
        "median_alpha_deg_that_would_permit_observed_whorls": round(float(d["alpha_required_deg_for_observed_whorls"].median()), 2),
        "per_species_median_R": {k: round(float(v), 3) for k, v in d.groupby("species")["R"].median().items()},
    }
    if frac_gt1 >= 0.9:
        verdict = "refutes"
    elif (1 - frac_gt1) >= 0.9:
        verdict = "supports"
    else:
        verdict = "mixed"
    out["verdict_by_preregistered_rule"] = verdict
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
