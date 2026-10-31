#!/usr/bin/env python3
"""thompson1917-ch11-08: are successive whorl breadths / diameters in geometric progression?

Data (derived/ tables produced by fetch.py, shared with thompson1917-ch11-10):
  * nautilus_dm_45deg.csv   : Nautilus pompilius conch diameter every 45 deg (Tajika et al. 2018)
  * ammonoid_dm_halfwhorl.csv: ammonoid conch diameter every half whorl (Walton & Korn 2018)
  * gastropod_aperture_radii.csv (optional): aperture-centroid distance from coiling axis every
    180 deg (Collins et al. 2021)
For each specimen the series s_k (k = station index, equal angular steps) is fitted by
  geometric:  log s = a + b k      (logarithmic spiral; constant ratio per step)
  arithmetic: s = c + d k          (constant increment per step)
and compared by residual sum of squares on the original scale. The per-revolution ratio
r_k = s_{k+m} / s_k (m stations per revolution) gives the whorl expansion through ontogeny.
"""
import json
import math
import os

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")


def fit_series(s, m):
    """s: sizes at equal angular steps (ontogenetic order); m: stations per revolution."""
    s = np.asarray(s, dtype=float)
    k = np.arange(len(s), dtype=float)
    if len(s) < 4 or np.any(s <= 0):
        return None
    b1, b0 = np.polyfit(k, np.log(s), 1)
    pred_geo = np.exp(b0 + b1 * k)
    ss_res_log = float(np.sum((np.log(s) - (b0 + b1 * k)) ** 2))
    ss_tot_log = float(np.sum((np.log(s) - np.log(s).mean()) ** 2))
    r2_log = 1 - ss_res_log / ss_tot_log if ss_tot_log > 0 else float("nan")
    d1, d0 = np.polyfit(k, s, 1)
    pred_ari = d0 + d1 * k
    rss_geo = float(np.sum((s - pred_geo) ** 2))
    rss_ari = float(np.sum((s - pred_ari) ** 2))
    out = {"n_stations": int(len(s)), "r2_loglinear": r2_log, "geometric_beats_arithmetic": rss_geo < rss_ari,
           "rss_ratio_geo_over_ari": rss_geo / rss_ari if rss_ari > 0 else float("nan"),
           "r_fit": float(math.exp(b1 * m))}
    if len(s) > m:
        r = s[m:] / s[:-m]
        out["r_median"] = float(np.median(r))
        out["r_rel_range"] = float((r.max() - r.min()) / np.median(r))
        out["r_n"] = int(r.size)
        if r.size >= 4:
            rho = spearmanr(np.arange(r.size), r).statistic
            out["r_trend_spearman"] = float(rho) if not np.isnan(rho) else 0.0
    return out


def summarise(fits, label):
    f = pd.DataFrame(fits)
    res = {"group": label, "n_specimens": int(len(f)),
           "median_r2_loglinear": round(float(f["r2_loglinear"].median()), 4),
           "min_r2_loglinear": round(float(f["r2_loglinear"].min()), 4),
           "frac_geometric_beats_arithmetic": round(float(f["geometric_beats_arithmetic"].mean()), 3),
           "median_rss_ratio_geo_over_ari": round(float(f["rss_ratio_geo_over_ari"].median()), 4)}
    if "r_median" in f:
        g = f.dropna(subset=["r_median"])
        res.update({"median_r": round(float(g["r_median"].median()), 3),
                    "median_within_specimen_r_rel_range": round(float(g["r_rel_range"].median()), 3),
                    "frac_r_rel_range_le_0.20": round(float((g["r_rel_range"] <= 0.20).mean()), 3)})
        if "r_trend_spearman" in g:
            t = g["r_trend_spearman"].dropna()
            res.update({"median_r_trend_spearman": round(float(t.median()), 3),
                        "frac_r_trend_negative": round(float((t < 0).mean()), 3), "n_with_trend": int(len(t))})
    return res


def main():
    out = {}
    n = pd.read_csv(os.path.join(DERIVED, "nautilus_dm_45deg.csv"))
    fits = [dict(fit_series(g.sort_values("step")["dm"], 8), specimen=s) for s, g in n.groupby("specimen")]
    out["nautilus"] = summarise([f for f in fits if f], "Nautilus pompilius, dm every 45 deg, 8 stations/revolution")

    a = pd.read_csv(os.path.join(DERIVED, "ammonoid_dm_halfwhorl.csv"))
    fits = []
    for sp, g in a.groupby("species"):
        g = g.sort_values("whorl")
        g = g[g["dm"] >= 5.0]
        f = fit_series(g["dm"], 2)
        if f:
            fits.append(dict(f, species=sp))
    out["ammonoids"] = summarise(fits, "ammonoids (177 spp.), dm every half whorl (dm >= 5 mm), 2 stations/revolution")

    gpath = os.path.join(DERIVED, "gastropod_aperture_radii.csv")
    if os.path.exists(gpath):
        gd = pd.read_csv(gpath)
        fits = []
        for sid, g in gd.groupby("id"):
            g = g.sort_values("aperture")
            f = fit_series(g["r_px"], 2)
            if f:
                fits.append(dict(f, id=sid))
        out["gastropods"] = summarise(fits, "gastropods (Collins et al. 2021), aperture radius every 180 deg, 2 stations/revolution")
    else:
        out["gastropods"] = {"status": "data-unavailable (Collins_et_al_data.zip not processed)"}

    groups = [out[k] for k in ("nautilus", "ammonoids", "gastropods") if "n_specimens" in out[k]]
    med_r2 = min(g["median_r2_loglinear"] for g in groups)
    frac_geo = min(g["frac_geometric_beats_arithmetic"] for g in groups)
    strict = all(g["median_within_specimen_r_rel_range"] <= 0.20 and -0.5 <= g["median_r_trend_spearman"] <= 0.5 for g in groups)
    naut_r = out["nautilus"]["median_r"]
    approx = med_r2 >= 0.99 and frac_geo >= 0.75 and 2.6 <= naut_r <= 3.5
    fail = frac_geo < 0.5 or med_r2 < 0.95 or not (2.2 <= naut_r <= 4.0)
    verdict = "refutes" if fail else ("supports" if approx and strict else ("mixed" if approx else "mixed"))
    out["decision"] = {"min_group_median_r2": med_r2, "min_group_frac_geometric_beats_arithmetic": frac_geo,
                       "strict_constancy_all_groups": strict, "nautilus_median_r": naut_r,
                       "approximate_geometric_progression": approx, "verdict": verdict}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
