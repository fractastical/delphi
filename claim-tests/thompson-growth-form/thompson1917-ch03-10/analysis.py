"""Test of thompson1917-ch03-10: do fishes approach a maximal size only asymptotically?

Run `python3 fetch.py` first (downloads ~11 MB of zipped DATRAS CA records into data/).
`python3 analysis.py` writes derived/*.csv, derived/summary.json and prints the measured values.

Data: ICES DATRAS NS-IBTS age records (CA), 2000-2024, quarters 1 and 3. Each row is a length class x age
x sex x maturity cell within a haul, with CANoAtLngt aged fish in it.
"""
import glob
import json
import os
import zipfile

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)

MIN_N_PER_AGE = 50
MIN_CONSECUTIVE_AGES = 7
N_LATE = 4  # last four included age classes -> three late-age increments

USECOLS = ["Quarter", "Year", "LengthCode", "LengthClass", "AgePlusGroup", "IndividualAge", "CANoAtLngt", "AphiaID", "Species"]


def load():
    frames = []
    for path in sorted(glob.glob(os.path.join(DATA, "CA_*.zip"))):
        with zipfile.ZipFile(path) as z:
            name = [n for n in z.namelist() if n.endswith(".csv")][0]
            with z.open(name) as f:
                frames.append(pd.read_csv(f, usecols=USECOLS, dtype={"LengthCode": str, "AgePlusGroup": str}, low_memory=False))
    df = pd.concat(frames, ignore_index=True)
    n_raw = len(df)
    df["IndividualAge"] = pd.to_numeric(df["IndividualAge"], errors="coerce")
    df["CANoAtLngt"] = pd.to_numeric(df["CANoAtLngt"], errors="coerce")
    df["LengthClass"] = pd.to_numeric(df["LengthClass"], errors="coerce")
    # DATRAS length codes: '.' and '0' -> length class in mm; '1', '2', '5' -> cm.
    mm = df["LengthCode"].isin([".", "0"])
    df["length_cm"] = np.where(mm, df["LengthClass"] / 10.0, df["LengthClass"])
    plus = df["AgePlusGroup"].fillna("-9").astype(str).str.strip()
    keep = (df["IndividualAge"] >= 0) & (df["CANoAtLngt"] > 0) & (df["length_cm"] > 0) & plus.isin(["-9", "", "nan"])
    df = df[keep].copy()
    df["IndividualAge"] = df["IndividualAge"].astype(int)
    return df, n_raw


def mean_length_at_age(df):
    g = df.groupby(["Species", "IndividualAge"])
    out = g.apply(lambda d: pd.Series({"n": d["CANoAtLngt"].sum(),
                                       "mean_length_cm": np.average(d["length_cm"], weights=d["CANoAtLngt"])}),
                  include_groups=False).reset_index()
    return out


def select_ages(sp):
    """Ages 1..A where every class from 1 up to A has >= MIN_N_PER_AGE fish; A = oldest such class in the run."""
    sp = sp.sort_values("IndividualAge")
    ages = []
    for a in range(1, int(sp["IndividualAge"].max()) + 1):
        row = sp[sp["IndividualAge"] == a]
        if len(row) == 1 and row["n"].iloc[0] >= MIN_N_PER_AGE:
            ages.append(a)
        else:
            break
    return sp[sp["IndividualAge"].isin(ages)] if len(ages) >= MIN_CONSECUTIVE_AGES else None


def wls_aic(resid, w, k):
    n = len(resid)
    rss = float(np.sum(w * resid ** 2))
    return n * np.log(rss / n) + 2 * k, rss


def fit_vb(a, L, w):
    sw = np.sqrt(w)

    def res(p):
        Linf, K, t0 = p
        return sw * (Linf * (1 - np.exp(-K * (a - t0))) - L)

    best = None
    for K0 in (0.1, 0.3, 0.6):
        for t00 in (-1.0, 0.0):
            r = least_squares(res, [L.max() * 1.2, K0, t00], bounds=([0, 1e-4, -10], [10 * L.max(), 5, a.min()]))
            if best is None or r.cost < best.cost:
                best = r
    aic, rss = wls_aic(best.fun / sw, w, 3)
    return {"Linf": best.x[0], "K": best.x[1], "t0": best.x[2], "aic": aic, "rss_w": rss}


def fit_plateau(a, L, w):
    """Quadratic rise to a maximum Lmax reached at age tc, then constant. tc <= max(a) - 1 (>= 2 classes on plateau)."""
    sw = np.sqrt(w)

    def model(p, a):
        Lmax, c, tc = p
        return np.where(a < tc, Lmax - c * (tc - a) ** 2, Lmax)

    def res(p):
        return sw * (model(p, a) - L)

    best = None
    for tc0 in np.linspace(a.min() + 1, a.max() - 1, 5):
        c0 = max((L.max() - L.min()) / max((tc0 - a.min()) ** 2, 1), 1e-3)
        r = least_squares(res, [L.max(), c0, tc0], bounds=([0, 0, a.min() + 0.5], [10 * L.max(), np.inf, a.max() - 1]))
        if best is None or r.cost < best.cost:
            best = r
    aic, rss = wls_aic(best.fun / sw, w, 3)
    return {"Lmax": best.x[0], "c": best.x[1], "tc": best.x[2], "aic": aic, "rss_w": rss}


def main():
    df, n_raw = load()
    mla = mean_length_at_age(df)
    mla.round(3).to_csv(os.path.join(DERIVED, "mean_length_at_age_all_species.csv"), index=False)

    rows, incs = [], []
    for species, sp in mla.groupby("Species"):
        sel = select_ages(sp)
        if sel is None:
            continue
        a = sel["IndividualAge"].to_numpy(float)
        L = sel["mean_length_cm"].to_numpy(float)
        w = sel["n"].to_numpy(float)
        vb = fit_vb(a, L, w)
        pl = fit_plateau(a, L, w)
        d = np.diff(L)
        late = d[-(N_LATE - 1):]
        for i, inc in enumerate(late):
            incs.append({"Species": species, "age_from": int(a[-(N_LATE) + i]), "age_to": int(a[-(N_LATE) + i + 1]),
                         "increment_cm": inc, "n_from": int(w[-(N_LATE) + i]), "n_to": int(w[-(N_LATE) + i + 1])})
        rows.append({"Species": species, "n_ages": len(a), "oldest_age": int(a.max()), "n_fish": int(w.sum()),
                     "L_at_age1_cm": L[0], "L_at_oldest_cm": L[-1],
                     "vb_Linf": vb["Linf"], "vb_K": vb["K"], "vb_t0": vb["t0"], "aic_vb": vb["aic"],
                     "pl_Lmax": pl["Lmax"], "pl_tc": pl["tc"], "aic_plateau": pl["aic"],
                     "dAIC_plateau_minus_vb": pl["aic"] - vb["aic"],
                     "late_increments_positive": int((late > 0).sum()), "late_increments": len(late),
                     "all_increments_positive": bool((d > 0).all()),
                     "L_oldest_over_Linf": L[-1] / vb["Linf"]})
    res = pd.DataFrame(rows).sort_values("Species")
    inc = pd.DataFrame(incs)
    res.round(4).to_csv(os.path.join(DERIVED, "species_model_comparison.csv"), index=False)
    inc.round(4).to_csv(os.path.join(DERIVED, "late_age_increments.csv"), index=False)

    n_sp = len(res)
    summary = {
        "n_rows_raw": int(n_raw), "n_rows_used": int(len(df)), "n_aged_fish_used": float(df["CANoAtLngt"].sum()),
        "n_species_with_age_data": int(mla["Species"].nunique()), "n_qualifying_species": n_sp,
        "species": res["Species"].tolist(),
        "n_species_vb_favoured_dAIC_gt_2": int((res["dAIC_plateau_minus_vb"] > 2).sum()),
        "n_species_plateau_favoured_dAIC_lt_minus2": int((res["dAIC_plateau_minus_vb"] < -2).sum()),
        "fraction_species_vb_favoured": float((res["dAIC_plateau_minus_vb"] > 2).mean()) if n_sp else None,
        "fraction_species_plateau_favoured": float((res["dAIC_plateau_minus_vb"] < -2).mean()) if n_sp else None,
        "median_dAIC": float(res["dAIC_plateau_minus_vb"].median()) if n_sp else None,
        "n_late_increments": int(len(inc)), "n_late_increments_positive": int((inc["increment_cm"] > 0).sum()),
        "fraction_late_increments_positive": float((inc["increment_cm"] > 0).mean()) if len(inc) else None,
        "median_late_increment_cm": float(inc["increment_cm"].median()) if len(inc) else None,
        "n_species_all_increments_positive": int(res["all_increments_positive"].sum()),
        "median_L_oldest_over_Linf": float(res["L_oldest_over_Linf"].median()) if n_sp else None,
    }
    if n_sp < 5:
        verdict = "inconclusive (underpowered)"
    elif summary["fraction_species_vb_favoured"] >= 2 / 3 and summary["fraction_late_increments_positive"] >= 0.75:
        verdict = "supports"
    elif summary["fraction_species_plateau_favoured"] >= 0.5 or summary["fraction_late_increments_positive"] <= 0.5:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary["verdict_by_preregistered_rule"] = verdict
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    print(res.round(3).to_string())


if __name__ == "__main__":
    main()
