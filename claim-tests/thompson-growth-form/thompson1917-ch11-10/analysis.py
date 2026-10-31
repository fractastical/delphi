#!/usr/bin/env python3
"""thompson1917-ch11-10: constant angle of the shell spiral.

alpha = arccot(ln r / 2 pi), where r is the per-revolution expansion ratio of the radius vector
(Thompson, Ch. XI, table of r against alpha). Data (from fetch.py, in derived/):
  * Nautilus pompilius: conch diameter every 45 deg (Tajika et al. 2018), r = dm[i] / dm[i-8].
  * Ammonoids: conch diameter every half whorl (Walton & Korn 2018), r = dm[n] / dm[n-1].
  * Gastropods: aperture-centroid distance from the coiling axis at 180-deg steps
    (Collins et al. 2021), r = r_ap[k+2] / r_ap[k]  (only if derived/gastropod_aperture_radii.csv exists).
Per specimen/species a single r is the median over post-embryonic stations; alpha is then
computed from that r.
"""
import json
import math
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")


def alpha_deg(r):
    return math.degrees(math.atan2(2 * math.pi, math.log(r)))  # arccot(ln r / 2pi)


def band_stats(alphas):
    a = np.asarray(alphas, dtype=float)
    return {"n": int(a.size), "median_alpha": round(float(np.median(a)), 2),
            "q1_alpha": round(float(np.percentile(a, 25)), 2), "q3_alpha": round(float(np.percentile(a, 75)), 2),
            "frac_in_80_85": round(float(np.mean((a >= 80) & (a <= 85))), 3),
            "frac_below_80": round(float(np.mean(a < 80)), 3),
            "frac_above_85": round(float(np.mean(a > 85)), 3)}


def nautilus():
    d = pd.read_csv(os.path.join(DERIVED, "nautilus_dm_45deg.csv"))
    per = []
    for spec, g in d.groupby("specimen"):
        g = g.sort_values("step")
        dm = g["dm"].to_numpy()
        # all stations are post-hatching (first dm > 18 mm); one revolution = 8 stations
        if len(dm) < 9:
            continue
        r = dm[8:] / dm[:-8]
        per.append({"specimen": spec, "population": g["population"].iloc[0], "r_median": float(np.median(r)),
                    "n_revolution_pairs": int(r.size)})
    p = pd.DataFrame(per)
    p["alpha"] = p["r_median"].map(alpha_deg)
    return p


def ammonoids(min_dm=5.0, last_only=False):
    d = pd.read_csv(os.path.join(DERIVED, "ammonoid_dm_halfwhorl.csv"))
    per = []
    for sp, g in d.groupby("species"):
        g = g.sort_values("whorl")
        g = g[g["dm"] >= min_dm]  # default excludes the embryonic/earliest juvenile conch (ammonitella ~1 mm)
        w = dict(zip(g["whorl"].round(2), g["dm"]))
        ks = sorted(k for k in w if round(k - 1.0, 2) in w)
        rs = [w[k] / w[round(k - 1.0, 2)] for k in ks]
        if len(rs) < 1:
            continue
        if last_only:
            rs = rs[-1:]
        per.append({"species": sp, "family": g["family"].iloc[0], "period": g["period"].iloc[0],
                    "r_median": float(np.median(rs)), "n_revolution_pairs": len(rs),
                    "dm_max": float(g["dm"].max())})
    p = pd.DataFrame(per)
    p["alpha"] = p["r_median"].map(alpha_deg)
    return p


def gastropods():
    path = os.path.join(DERIVED, "gastropod_aperture_radii.csv")
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    meta = pd.read_csv(os.path.join(DERIVED, "gastropod_specimens.csv")) if os.path.exists(
        os.path.join(DERIVED, "gastropod_specimens.csv")) else None
    per = []
    for sid, gid in d.groupby("id"):
        ratios = []
        for _, g in gid.groupby("block"):  # replicate digitisations of one specimen are pooled
            r = g.sort_values("aperture")["r_px"].to_numpy()
            if len(r) >= 3:
                ratios.extend(r[2:] / r[:-2])  # apertures are 180 deg apart: two steps = one revolution
        if ratios:
            per.append({"id": str(sid), "r_median": float(np.median(ratios)), "n_revolution_pairs": len(ratios)})
    p = pd.DataFrame(per)
    if meta is not None:
        meta["ID"] = meta["ID"].astype(str)
        p = p.merge(meta[["ID", "Genus", "species"]].rename(columns={"ID": "id"}), on="id", how="left")
        p["taxon"] = p["Genus"].fillna("?") + " " + p["species"].fillna("?")
    else:
        p["taxon"] = p["id"]
    p = p[p["r_median"] > 1.0]  # a shrinking "spiral" cannot be converted to an angle
    sp = p.groupby("taxon", as_index=False).agg(r_median=("r_median", "median"), n_specimens=("id", "size"))
    sp["alpha"] = sp["r_median"].map(alpha_deg)
    return p, sp


def main():
    out = {"formula": "alpha = arccot(ln r / 2 pi); band 80-85 deg <=> r in [1.72, 3.00]; alpha < 80 <=> r > 3.00"}
    n = nautilus()
    out["nautilus"] = band_stats(n["alpha"])
    out["nautilus"].update({"median_r": round(float(n["r_median"].median()), 3),
                            "r_iqr": [round(float(n["r_median"].quantile(.25)), 3), round(float(n["r_median"].quantile(.75)), 3)],
                            "by_population_median_alpha": {k: round(float(v), 2) for k, v in n.groupby("population")["alpha"].median().items()}})
    a = ammonoids()
    out["ammonoids"] = band_stats(a["alpha"])
    out["ammonoids"].update({"median_r": round(float(a["r_median"].median()), 3),
                             "by_period": {k: band_stats(g["alpha"]) for k, g in a.groupby("period")},
                             "species_with_alpha_in_band": sorted(a.loc[(a.alpha >= 80) & (a.alpha <= 85), "species"].tolist())[:40]})
    out["ammonoids"]["sensitivity_not_preregistered"] = {
        **{f"min_dm_{t}": band_stats(ammonoids(min_dm=t)["alpha"]) for t in (0, 2, 10, 20)},
        "last_revolution_only_min_dm_5": band_stats(ammonoids(last_only=True)["alpha"])}
    g = gastropods()
    if g is None:
        out["gastropods"] = {"status": "data-unavailable (Collins_et_al_data.zip not processed)"}
        gast_ok, gast_fail = None, None
    else:
        spec, sp = g
        out["gastropods"] = band_stats(sp["alpha"])
        out["gastropods"].update({"n_specimens": int(len(spec)), "median_r": round(float(sp["r_median"].median()), 3),
                                  "per_species": {r.taxon: {"r": round(r.r_median, 3), "alpha": round(r.alpha, 2), "n": int(r.n_specimens)}
                                                  for r in sp.itertuples()}})
        gast_ok = out["gastropods"]["frac_in_80_85"] >= 0.5 and out["gastropods"]["frac_below_80"] <= 0.10
        gast_fail = out["gastropods"]["frac_in_80_85"] < 0.4 or out["gastropods"]["frac_below_80"] > 0.20

    na = out["nautilus"]["median_alpha"]
    naut_ok, naut_fail = 78 <= na <= 82, not (76 <= na <= 84)
    am = out["ammonoids"]
    amm_ok = am["frac_in_80_85"] >= 0.5 and am["frac_below_80"] <= 0.10
    amm_fail = am["frac_in_80_85"] < 0.4 or am["frac_below_80"] > 0.20
    if naut_fail or amm_fail or gast_fail:
        verdict = "refutes"
    elif naut_ok and amm_ok and (gast_ok is None or gast_ok):
        verdict = "supports"
    else:
        verdict = "mixed"
    out["decision"] = {"nautilus_pass": naut_ok, "nautilus_fail": naut_fail, "ammonoid_pass": amm_ok,
                       "ammonoid_fail": amm_fail, "gastropod_pass": gast_ok, "gastropod_fail": gast_fail, "verdict": verdict}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
