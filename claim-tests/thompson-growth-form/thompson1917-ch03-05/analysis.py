#!/usr/bin/env python3
"""thompson1917-ch03-05: phases of the human stature-velocity curve, tested on NHANES 2007-2018.

Downloads the NHANES demographic (DEMO) and body-measures (BMX) files for six survey cycles,
records their checksums, builds sex-specific median stature by month of age, and derives
model-free yearly velocities plus a kernel-smoothed velocity curve. Writes derived/measured.json
and derived/files.json; every number in result.json#measured comes from here.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

CYCLES = [("2007", "E"), ("2009", "F"), ("2011", "G"), ("2013", "H"), ("2015", "I"), ("2017", "J")]
BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}_{suffix}.xpt"
RNG = np.random.default_rng(20261031)
N_BOOT = 1000


def fetch(url, dest):
    """Download url to dest (if absent) and return provenance record."""
    if not os.path.exists(dest):
        r = requests.get(url, timeout=300, headers={"User-Agent": "delphi-claim-tests/1.0"})
        r.raise_for_status()
        with open(dest, "wb") as fh:
            fh.write(r.content)
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        retrieved = datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = hashlib.sha256()
    with open(dest, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"download_url": url, "retrieved_at": retrieved, "byte_size": os.path.getsize(dest), "sha256": h.hexdigest()}


def load_nhanes():
    files = {"demo": [], "bmx": []}
    frames = []
    for year, suf in CYCLES:
        parts = {}
        for name in ("DEMO", "BMX"):
            url = BASE.format(year=year, name=name, suffix=suf)
            dest = os.path.join(DATA, f"{name}_{suf}.xpt")
            files[name.lower()].append(fetch(url, dest))
            parts[name] = pd.read_sas(dest, format="xport")
        d = parts["DEMO"]
        # Exam age in months (RIDEXAGM, 0-19 yr) exists from 2011 on; 2007-2010 give screening age in months for all.
        if "RIDEXAGM" in d.columns:
            agem = d["RIDEXAGM"].where(d["RIDEXAGM"].notna(), d["RIDAGEMN"])
        else:
            agem = d["RIDAGEMN"]
        d = pd.DataFrame({"SEQN": d["SEQN"], "sex": d["RIAGENDR"], "agem": agem, "cycle": suf})
        m = d.merge(parts["BMX"][["SEQN", "BMXWT", "BMXHT", "BMXRECUM"]], on="SEQN", how="inner")
        frames.append(m)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["agem"].notna() & (df["agem"] < 240)].copy()
    # Recumbent length below 24 months, standing height from 24 months on.
    df["ht"] = np.where(df["agem"] < 24, df["BMXRECUM"], df["BMXHT"])
    df = df[df["ht"].notna()].copy()
    df["agey"] = df["agem"] / 12.0
    return df, files


def yearly_velocity(sub):
    """Model-free velocity v(a) = median height at completed age a+1 minus that at age a (cm/yr), a = 0..18."""
    med = sub.groupby(np.floor(sub["agey"]).astype(int))["ht"].median()
    # Heights are recorded to 0.1 cm; round differences to avoid float noise at criterion thresholds.
    v = {a: round(float(med[a + 1] - med[a]), 6) for a in range(0, 19) if a in med.index and (a + 1) in med.index}
    return med, v


BANDWIDTH_YR = 0.5  # Gaussian kernel SD, fixed a priori


def smooth_velocity(sub, grid, h=BANDWIDTH_YR):
    """Local-linear kernel regression of monthly median height on age (weights = bin size x Gaussian kernel).

    The local slope at each grid age is the smoothed velocity (cm/yr). A smoothing spline was
    pre-registered, but its derivative on monthly medians was numerically unstable (see
    result.json caveats), so this fixed-bandwidth local-linear smoother is used instead.
    """
    g = sub.groupby(sub["agem"].astype(int))["ht"]
    med = g.median().values
    n = g.size().values.astype(float)
    x = (g.size().index.values + 0.5) / 12.0
    fit = np.empty(len(grid))
    vel = np.empty(len(grid))
    for j, t in enumerate(grid):
        w = n * np.exp(-0.5 * ((x - t) / h) ** 2)
        X = np.column_stack([np.ones_like(x), x - t])
        W = np.sqrt(w)
        beta, *_ = np.linalg.lstsq(X * W[:, None], med * W, rcond=None)
        fit[j], vel[j] = beta[0], beta[1]
    return fit, vel


def summarize(v):
    child = [v[a] for a in range(4, 10)]
    return {
        "v0_infancy": v[0],
        "child_mean_v4_9": float(np.mean(child)),
        "child_range_v4_9": round(float(np.max(child) - np.min(child)), 6),
        "adolescent_peak_v10_16": float(max(v[a] for a in range(10, 17))),
        "adolescent_peak_age_bin": int(max(range(10, 17), key=lambda a: v[a])),
        "v18_arrest": v[18],
    }


def analyse_sex(df, sex_code):
    sub = df[df["sex"] == sex_code]
    med, v = yearly_velocity(sub)
    s = summarize(v)
    s["n_individuals"] = int(len(sub))
    s["excess_peak_over_child"] = s["adolescent_peak_v10_16"] - s["child_mean_v4_9"]

    grid = np.arange(0.5, 19.51, 1.0 / 12)
    ht_s, vel_s = smooth_velocity(sub, grid)
    sel_child = (grid >= 4) & (grid <= 10)
    sel_teen = (grid >= 10) & (grid <= 17)
    sel_min = (grid >= 6) & (grid <= 10)
    child_v = vel_s[sel_child]
    s["smooth_child_cv_4_10"] = float(np.std(child_v) / np.mean(child_v))
    s["smooth_child_min_6_10"] = float(np.min(vel_s[sel_min]))
    s["smooth_teen_peak_10_17"] = float(np.max(vel_s[sel_teen]))
    s["smooth_teen_peak_age"] = float(grid[sel_teen][np.argmax(vel_s[sel_teen])])
    s["smooth_peak_to_childmin_ratio"] = s["smooth_teen_peak_10_17"] / s["smooth_child_min_6_10"]
    s["smooth_v_at_19"] = float(vel_s[np.argmin(np.abs(grid - 19.0))])
    s["bandwidth_sensitivity"] = {}
    for h in (0.75, 1.0):
        _, v_h = smooth_velocity(sub, grid, h)
        s["bandwidth_sensitivity"][str(h)] = {
            "child_cv_4_10": float(np.std(v_h[sel_child]) / np.mean(v_h[sel_child])),
            "peak_to_childmin_ratio": float(np.max(v_h[sel_teen]) / np.min(v_h[sel_min])),
            "teen_peak_age": float(grid[sel_teen][np.argmax(v_h[sel_teen])]),
        }

    # Bootstrap over individuals for the model-free quantities.
    boots = {"v0_infancy": [], "excess_peak_over_child": [], "v18_arrest": []}
    ages = np.floor(sub["agey"].values).astype(int)
    ht = sub["ht"].values
    idx_by_age = {a: np.where(ages == a)[0] for a in range(0, 20)}
    for _ in range(N_BOOT):
        meds = {}
        for a, idx in idx_by_age.items():
            samp = ht[RNG.choice(idx, size=len(idx), replace=True)]
            meds[a] = np.median(samp)
        vb = {a: meds[a + 1] - meds[a] for a in range(0, 19)}
        sb = summarize(vb)
        boots["v0_infancy"].append(sb["v0_infancy"])
        boots["excess_peak_over_child"].append(sb["adolescent_peak_v10_16"] - sb["child_mean_v4_9"])
        boots["v18_arrest"].append(sb["v18_arrest"])
    s["ci95"] = {k: [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))] for k, b in boots.items()}

    crit = {
        "a_infancy": s["v0_infancy"] >= 2 * s["child_mean_v4_9"],
        "b_steady": (s["smooth_child_cv_4_10"] < 0.15) and (s["child_range_v4_9"] <= 2.0),
        "c_quickening": (s["smooth_peak_to_childmin_ratio"] >= 1.2)
        and (s["excess_peak_over_child"] >= 1.0)
        and (s["ci95"]["excess_peak_over_child"][0] > 0),
        "d_arrest": (s["v18_arrest"] < 1.5) and (s["v18_arrest"] < s["child_mean_v4_9"] / 3),
    }
    s["criteria"] = crit
    s["yearly_velocity_cm_per_yr"] = {str(a): round(val, 3) for a, val in v.items()}
    s["yearly_median_height_cm"] = {str(int(a)): round(float(h), 2) for a, h in med.items()}
    s["smooth_velocity_by_year"] = {str(round(float(g), 2)): round(float(vv), 3) for g, vv in zip(grid, vel_s) if abs(g - round(g)) < 1e-6}
    return s


def main():
    df, files = load_nhanes()
    out = {"boys": analyse_sex(df, 1.0), "girls": analyse_sex(df, 2.0), "n_total": int(len(df)), "n_boot": N_BOOT}
    boys = out["boys"]["criteria"]
    if all(boys.values()):
        verdict = "supports"
    elif not boys["c_quickening"] or not boys["a_infancy"]:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["verdict_by_prereg_rule_boys"] = verdict
    with open(os.path.join(DERIVED, "measured.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(DERIVED, "files.json"), "w") as fh:
        json.dump(files, fh, indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
