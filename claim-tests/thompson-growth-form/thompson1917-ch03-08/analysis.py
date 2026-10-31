#!/usr/bin/env python3
"""thompson1917-ch03-08: boys' and girls' growth-velocity curves differ mainly in phase (NHANES 2007-2018).

Builds sex-specific smoothed stature- and weight-velocity curves from NHANES monthly medians,
locates takeoff, peak and end of the adolescent spurt in each sex, bootstraps the sex difference
in peak age, and measures shape similarity after aligning the curves. Writes derived/measured.json
and derived/files.json.
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
BANDWIDTH_YR = 0.5
GRID = np.arange(0.5, 19.51, 1.0 / 12)


def fetch(url, dest):
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
        if "RIDEXAGM" in d.columns:
            agem = d["RIDEXAGM"].where(d["RIDEXAGM"].notna(), d["RIDAGEMN"])
        else:
            agem = d["RIDAGEMN"]
        d = pd.DataFrame({"SEQN": d["SEQN"], "sex": d["RIAGENDR"], "agem": agem})
        frames.append(d.merge(parts["BMX"][["SEQN", "BMXWT", "BMXHT", "BMXRECUM"]], on="SEQN", how="inner"))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["agem"].notna() & (df["agem"] < 240)].copy()
    df["ht"] = np.where(df["agem"] < 24, df["BMXRECUM"], df["BMXHT"])
    df["wt"] = df["BMXWT"]
    df["month"] = df["agem"].astype(int)
    return df, files


def monthly_medians(values, months):
    s = pd.Series(values).groupby(months).median()
    n = pd.Series(values).groupby(months).size()
    return s.index.values, s.values, n.values.astype(float)


def local_linear_velocity(x, y, n, grid, h=BANDWIDTH_YR):
    """Local-linear Gaussian-kernel smoother; returns fitted level and slope (velocity) on grid."""
    fit = np.empty(len(grid))
    vel = np.empty(len(grid))
    for j, t in enumerate(grid):
        w = n * np.exp(-0.5 * ((x - t) / h) ** 2)
        X = np.column_stack([np.ones_like(x), x - t])
        W = np.sqrt(w)
        beta, *_ = np.linalg.lstsq(X * W[:, None], y * W, rcond=None)
        fit[j], vel[j] = beta
    return fit, vel


def phases(grid, vel, kind):
    """Takeoff (pre-spurt minimum from 6 yr), peak (8-17 yr) and end of the adolescent spurt."""
    sel_peak = (grid >= 8) & (grid <= 17)
    i_peak = np.where(sel_peak)[0][np.argmax(vel[sel_peak])]
    peak_age = float(grid[i_peak])
    sel_take = (grid >= 6) & (grid <= peak_age)
    i_take = np.where(sel_take)[0][np.argmin(vel[sel_take])]
    threshold = 1.0 if kind == "ht" else 0.5 * vel[i_peak]
    after = np.where((grid > peak_age) & (vel < threshold))[0]
    end_age = float(grid[after[0]]) if len(after) else None
    return {"takeoff_age": float(grid[i_take]), "takeoff_velocity": float(vel[i_take]),
            "peak_age": peak_age, "peak_velocity": float(vel[i_peak]), "end_age": end_age}


def velocity_curve(sub, kind):
    s = sub[sub[kind].notna()]
    m, med, n = monthly_medians(s[kind].values, s["month"].values)
    x = (m + 0.5) / 12.0
    return local_linear_velocity(x, med, n, GRID)[1]


def shape_similarity(grid, v_boys, v_girls, shift):
    """Pearson r between boys' velocity (ages 6-17) and girls' velocity shifted later by `shift` years."""
    sel = (grid >= 6) & (grid <= 17)
    tb = grid[sel]
    vg_shifted = np.interp(tb - shift, grid, v_girls)
    r = float(np.corrcoef(v_boys[sel], vg_shifted)[0, 1])
    # amplitude scaling: regress boys' on shifted girls' velocity
    slope, intercept = np.polyfit(vg_shifted, v_boys[sel], 1)
    return r, float(slope), float(intercept)


def main():
    df, files = load_nhanes()
    out = {"n_total": int(len(df)), "n_boot": N_BOOT, "bandwidth_yr": BANDWIDTH_YR}
    curves = {}
    for kind in ("ht", "wt"):
        res = {}
        for sex, code in (("boys", 1.0), ("girls", 2.0)):
            sub = df[df["sex"] == code]
            vel = velocity_curve(sub, kind)
            curves[(kind, sex)] = vel
            res[sex] = phases(GRID, vel, kind)
            res[sex]["n"] = int(sub[kind].notna().sum())
            res[sex]["velocity_by_year"] = {str(round(float(g), 2)): round(float(v), 3) for g, v in zip(GRID, vel) if abs(g - round(g)) < 1e-6}
        res["peak_age_lead_girls_yr"] = res["boys"]["peak_age"] - res["girls"]["peak_age"]
        res["takeoff_lead_girls_yr"] = res["boys"]["takeoff_age"] - res["girls"]["takeoff_age"]
        if res["boys"]["end_age"] is not None and res["girls"]["end_age"] is not None:
            res["end_lead_girls_yr"] = res["boys"]["end_age"] - res["girls"]["end_age"]
        else:
            res["end_lead_girls_yr"] = None
        r, slope, intercept = shape_similarity(GRID, curves[(kind, "boys")], curves[(kind, "girls")], res["peak_age_lead_girls_yr"])
        res["shape_r_after_shift"] = r
        res["amplitude_slope_boys_on_girls"] = slope
        res["amplitude_intercept"] = intercept
        res["peak_velocity_ratio_boys_over_girls"] = res["boys"]["peak_velocity"] / res["girls"]["peak_velocity"]
        out[kind] = res

    # Bootstrap over individuals: peak-age lead for stature and weight.
    boots = {"ht": [], "wt": []}
    groups = {}
    for sex, code in (("boys", 1.0), ("girls", 2.0)):
        sub = df[df["sex"] == code]
        groups[sex] = {kind: sub[sub[kind].notna()][[kind, "month"]].to_numpy() for kind in ("ht", "wt")}
    for _ in range(N_BOOT):
        for kind in ("ht", "wt"):
            peaks = {}
            for sex in ("boys", "girls"):
                arr = groups[sex][kind]
                samp = arr[RNG.integers(0, len(arr), len(arr))]
                m, med, n = monthly_medians(samp[:, 0], samp[:, 1].astype(int))
                vel = local_linear_velocity((m + 0.5) / 12.0, med, n, GRID)[1]
                peaks[sex] = phases(GRID, vel, kind)["peak_age"]
            boots[kind].append(peaks["boys"] - peaks["girls"])
    for kind in ("ht", "wt"):
        out[kind]["peak_age_lead_ci95"] = [float(np.percentile(boots[kind], 2.5)), float(np.percentile(boots[kind], 97.5))]

    ht, wt = out["ht"], out["wt"]
    crit = {
        "i_stature_peak_lead_ge_1yr_ci_excl_0": (ht["peak_age_lead_girls_yr"] >= 1.0) and (ht["peak_age_lead_ci95"][0] > 0),
        "ii_takeoff_and_end_earlier_in_girls": (ht["takeoff_lead_girls_yr"] > 0) and (ht["end_lead_girls_yr"] is not None and ht["end_lead_girls_yr"] > 0),
        "iii_shape_r_ge_0.8": ht["shape_r_after_shift"] >= 0.8,
        "weight_peak_lead_ge_1yr": wt["peak_age_lead_girls_yr"] >= 1.0,
    }
    out["criteria"] = crit
    if all(crit.values()):
        verdict = "supports"
    elif (ht["peak_age_lead_girls_yr"] <= 0) or (ht["peak_age_lead_ci95"][0] <= 0) or (ht["shape_r_after_shift"] < 0.5):
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["verdict_by_prereg_rule"] = verdict
    with open(os.path.join(DERIVED, "measured.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(DERIVED, "files.json"), "w") as fh:
        json.dump(files, fh, indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
