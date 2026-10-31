#!/usr/bin/env python3
"""Test of darwin1859-ch11-13: "the temperature of the whole world was at this period
simultaneously cooler" (the Glacial period).

Data: MARGO Project Members (2009) Nature Geoscience 2:127-132, supplementary
Table S9, the 5x5 degree gridded compilation of Last Glacial Maximum (19-23 ka)
sea-surface temperature anomalies (modern WOA98 minus LGM), archived at PANGAEA
(doi:10.1594/PANGAEA.733406). Cooling is tested globally, per hemisphere, per
30-degree latitude band and per ocean basin, all within the same dated interval.

Re-run:  python3 analysis.py   (downloads a 4 MB zip into ./data/, writes ./derived/)
"""
import hashlib
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

URL = "https://store.pangaea.de/Publications/Waelbroeck_et_al_2009/NGS-2008-09-00905_supplementary_information.zip"
MEMBER = "NGS-2008-09-00905_supplementary_information/NGS-2008-09-00905_Table_S9.txt"
MISSING = -99.99
COLS = ["lon", "lat", "woa_ann", "woa_jas", "woa_jfm", "lgm_ann", "lgm_jas", "lgm_jfm", "anom_ann", "anom_jas", "anom_jfm",
        "reliability", "n_records", "n_proxies", "perr_ann", "perr_jas", "perr_jfm", "sd_ann", "sd_jas", "sd_jfm",
        "toterr_ann", "toterr_jas", "toterr_jfm", "min_ann", "min_jas", "min_jfm", "max_ann", "max_jas", "max_jfm"]


def basin(lon, lat):
    """Crude ocean-basin assignment from longitude (0-360) and latitude."""
    if lat < -50:
        return "Southern Ocean"
    if 20 <= lon < 147 and not (lon < 30 and lat > 30):
        return "Indian" if lat < 30 else "Pacific"
    if 147 <= lon < 290:
        return "Pacific"
    return "Atlantic"


def main():
    r = requests.get(URL, timeout=300)
    r.raise_for_status()
    open(os.path.join(DATA, "margo_si.zip"), "wb").write(r.content)
    files = {"margo_si.zip": {"download_url": URL, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(MEMBER).decode("latin-1")
    lines = [l for l in raw.splitlines() if l and not l.startswith("#") and l[0] in "0123456789-."]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="\t", header=None, usecols=range(len(COLS)), names=COLS)
    df = df[(df["anom_ann"] != MISSING) & (df["woa_ann"] != MISSING) & (df["lgm_ann"] != MISSING)].copy()
    # The Table S9 header calls column 9 the "LGM anomaly"; the Table S1/S2 captions say
    # "modern - LGM", but column 9 equals LGM - modern (checked: lgm_ann - woa_ann reproduces
    # it to rounding). Cooling is therefore defined from the two temperature columns
    # directly, as modern minus LGM, so that the sign convention cannot matter.
    df["cooling"] = df["woa_ann"] - df["lgm_ann"]
    df["lon180"] = ((df["lon"] + 180) % 360) - 180
    df["weight"] = np.cos(np.radians(df["lat"]))
    df["cooler"] = df["cooling"] > 0
    df["cooler_beyond_error"] = df["cooling"] > df["toterr_ann"].where(df["toterr_ann"] != MISSING, 0)
    df["hemisphere"] = np.where(df["lat"] >= 0, "N", "S")
    df["band"] = df["hemisphere"] + pd.cut(df["lat"].abs(), [-0.1, 30, 60, 90], labels=["0-30", "30-60", "60-90"]).astype(str)
    df["basin"] = [basin(lo, la) for lo, la in zip(df["lon"], df["lat"])]

    def summarise(sub):
        w = sub["weight"].values
        a = sub["cooling"].values
        t = stats.ttest_1samp(a, 0.0, alternative="greater") if len(a) >= 2 else None
        return {"n_cells": int(len(sub)), "fraction_cooler": round(float(sub["cooler"].mean()), 4),
                "fraction_cooler_beyond_error": round(float(sub["cooler_beyond_error"].mean()), 4),
                "area_weighted_mean_cooling_C": round(float(np.average(a, weights=w)), 3),
                "median_cooling_C": round(float(np.median(a)), 3),
                "t_p_one_sided": (float(t.pvalue) if t else None)}

    glob = summarise(df)
    by_hemi = {h: summarise(g) for h, g in df.groupby("hemisphere")}
    by_band = {b: summarise(g) for b, g in df.groupby("band")}
    by_basin = {b: summarise(g) for b, g in df.groupby("basin")}

    subsets_rule = {**{f"hemisphere {k}": v for k, v in by_hemi.items()},
                    **{f"band {k}": v for k, v in by_band.items() if v["n_cells"] >= 5},
                    **{f"basin {k}": v for k, v in by_basin.items() if k in ("Atlantic", "Indian", "Pacific")}}
    fails_pass = [k for k, v in subsets_rule.items() if v["fraction_cooler"] < 0.8 or v["area_weighted_mean_cooling_C"] <= 0 or (v["t_p_one_sided"] is None or v["t_p_one_sided"] >= 0.01)]
    majority_warm = [k for k, v in subsets_rule.items() if v["fraction_cooler"] < 0.5]

    if majority_warm or glob["fraction_cooler"] < 0.6:
        verdict = "refutes"
    elif glob["fraction_cooler"] >= 0.9 and not fails_pass and glob["area_weighted_mean_cooling_C"] >= 1.0:
        verdict = "supports"
    else:
        verdict = "mixed"

    warm_cells = df[~df["cooler"]].sort_values("cooling")[["lon180", "lat", "cooling", "toterr_ann", "n_records", "n_proxies", "basin"]].round(2)
    measured = {
        "value": glob["fraction_cooler"],
        "unit": "fraction of 5x5 degree ocean grid cells with LGM (19-23 ka) annual SST below modern",
        "n": glob["n_cells"],
        "uncertainty": f"area-weighted mean cooling {glob['area_weighted_mean_cooling_C']} C; {glob['fraction_cooler_beyond_error']:.3f} of cells cooler by more than the stated total error",
        "extra": {
            "global": glob, "by_hemisphere": by_hemi, "by_latitude_band": by_band, "by_basin": by_basin,
            "subsets_failing_pass_thresholds": fails_pass, "subsets_with_majority_warming": majority_warm,
            "n_cells_warmer_than_modern": int((~df["cooler"]).sum()),
            "n_cells_warmer_than_modern_beyond_total_error": int(((df["cooling"] < 0) & (df["toterr_ann"] != MISSING) & (-df["cooling"] > df["toterr_ann"])).sum()),
            "n_cells_single_record": int((df["n_records"] == 1).sum()),
            "fraction_cooler_cells_with_2plus_records": round(float(df.loc[df["n_records"] >= 2, "cooler"].mean()), 4),
            "n_cells_with_2plus_records": int((df["n_records"] >= 2).sum()),
            "cells_warmer_than_modern": warm_cells.to_dict("records"),
            "fraction_cooler_sensitivity_beyond_error": glob["fraction_cooler_beyond_error"],
            "verdict_by_rule": verdict,
        },
    }
    df[["lon180", "lat", "woa_ann", "lgm_ann", "cooling", "toterr_ann", "reliability", "n_records", "n_proxies", "band", "basin", "cooler"]].round(3).to_csv(os.path.join(DERIVED, "cells.csv"), index=False)
    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
