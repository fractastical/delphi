"""Test of thompson1917-ch11-06: is each growth increment of a coiled shell a gnomon (shape self-similar)?

Data: Walton & Korn (2018), Ontogenetic_Conch_Parameter_Data.xlsx. Sheets 'dm', 'CWI', 'UWI', 'WER' hold,
per species (row), values at successive half-whorls (columns 'Whorl 0' ... 'Whorl 12'). Run fetch.py first.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)

DM_MIN = 2.0          # mm; exclude embryonic/earliest post-embryonic points
MIN_POINTS = 4
MIN_DM_SPAN = 4.0     # max dm / min dm
GNOMONIC_TOL = np.log(1.25)
ALLOMETRIC_TOL = np.log(1.5)
INDICES = ["CWI", "UWI", "WER"]


def load_sheet(xl, name):
    df = pd.read_excel(xl, name, header=0)
    df["series"] = np.arange(len(df))  # two species occur twice (two specimens each); keep the series apart
    whorl_cols = [c for c in df.columns if str(c).startswith("Whorl")]
    long = df.melt(id_vars=["Species", "series"], value_vars=whorl_cols, var_name="whorl", value_name=name)
    long["whorl"] = long["whorl"].str.replace("Whorl ", "").astype(float)
    return long


def main():
    xl = pd.ExcelFile(os.path.join(DATA, "extracted", "Ontogenetic_Conch_Parameter_Data.xlsx"))
    merged = load_sheet(xl, "dm")
    for idx in INDICES:
        merged = merged.merge(load_sheet(xl, idx), on=["Species", "series", "whorl"], how="left")
    merged = merged.dropna(subset=["dm"])
    meta = pd.read_excel(xl, "Species")[["Species", "Family", "Superfamily", "Stage", "Period"]]
    meta["series"] = np.arange(len(meta))
    merged.round(5).to_csv(os.path.join(DERIVED, "ontogenetic_series_long.csv"), index=False)

    rows = []
    for (species, series), g in merged.groupby(["Species", "series"]):
        rec = {"Species": species, "series": series, "n_points_total": int(len(g))}
        g = g[g["dm"] >= DM_MIN].sort_values("dm")
        if len(g) < MIN_POINTS or g["dm"].max() / g["dm"].min() < MIN_DM_SPAN:
            rec["qualifies"] = False
            rows.append(rec)
            continue
        rec.update({"qualifies": True, "n_points": len(g), "dm_min": g["dm"].min(), "dm_max": g["dm"].max()})
        any_allo, all_gnom, any_trend = False, True, False
        for idx in INDICES:
            v = g[idx].dropna()
            v = v[v > 0]
            if len(v) < MIN_POINTS:
                rec[f"logrange_{idx}"] = np.nan
                all_gnom = False  # cannot certify constancy without data
                continue
            lr = float(np.log(v.max()) - np.log(v.min()))
            rec[f"logrange_{idx}"] = lr
            rec[f"pct_change_{idx}"] = float(np.exp(lr) - 1) * 100
            rho, p = stats.spearmanr(np.log(g.loc[v.index, "dm"]), np.log(v))
            rec[f"spearman_{idx}"] = float(rho)
            rec[f"spearman_p_{idx}"] = float(p)
            any_allo |= lr >= ALLOMETRIC_TOL
            all_gnom &= lr <= GNOMONIC_TOL
            any_trend |= (abs(rho) >= 0.7 and p < 0.05)
        rec["gnomonic"] = bool(all_gnom)
        rec["allometric"] = bool(any_allo)
        rec["monotonic_trend_any_index"] = bool(any_trend)
        rows.append(rec)
    res = pd.DataFrame(rows).merge(meta, on=["Species", "series"], how="left")
    res.round(4).to_csv(os.path.join(DERIVED, "species_self_similarity.csv"), index=False)

    q = res[res["qualifies"] == True]  # noqa: E712
    n = len(q)
    summary = {
        "n_species_in_file": int(res["Species"].nunique()), "n_series_in_file": int(len(res)), "n_qualifying_species": n,
        "n_gnomonic": int(q["gnomonic"].sum()), "n_allometric": int(q["allometric"].sum()),
        "n_intermediate": int(n - q["gnomonic"].sum() - q["allometric"].sum()),
        "fraction_gnomonic": round(float(q["gnomonic"].mean()), 3) if n else None,
        "fraction_allometric": round(float(q["allometric"].mean()), 3) if n else None,
        "fraction_with_monotonic_trend": round(float(q["monotonic_trend_any_index"].mean()), 3) if n else None,
        "median_pct_change": {idx: round(float(q[f"pct_change_{idx}"].median()), 1) for idx in INDICES},
        "fraction_species_pct_change_ge_50": {idx: round(float((q[f"logrange_{idx}"] >= ALLOMETRIC_TOL).mean()), 3) for idx in INDICES},
        "fraction_species_pct_change_le_25": {idx: round(float((q[f"logrange_{idx}"] <= GNOMONIC_TOL).mean()), 3) for idx in INDICES},
        "by_period_fraction_allometric": {k: round(float(v), 3) for k, v in q.groupby("Period")["allometric"].mean().items()},
        "by_period_n": {k: int(v) for k, v in q.groupby("Period").size().items()},
        "gnomonic_species": q.loc[q["gnomonic"], "Species"].tolist(),
    }
    # Sensitivity (not part of the verdict): stricter size cut-off, and the verdict indices without UWI.
    def frac_allometric(dm_min, indices):
        cnt = tot = 0
        for (_, _), g in merged.groupby(["Species", "series"]):
            g = g[g["dm"] >= dm_min]
            if len(g) < MIN_POINTS or g["dm"].max() / g["dm"].min() < MIN_DM_SPAN:
                continue
            tot += 1
            allo = False
            for idx in indices:
                v = g[idx].dropna()
                v = v[v > 0]
                if len(v) >= MIN_POINTS and np.log(v.max()) - np.log(v.min()) >= ALLOMETRIC_TOL:
                    allo = True
            cnt += allo
        return {"n": tot, "fraction_allometric": round(cnt / tot, 3) if tot else None}

    summary["sensitivity"] = {
        "dm_min_5mm_all_indices": frac_allometric(5.0, INDICES),
        "dm_min_2mm_CWI_and_WER_only": frac_allometric(2.0, ["CWI", "WER"]),
        "dm_min_5mm_CWI_and_WER_only": frac_allometric(5.0, ["CWI", "WER"]),
    }
    if n < 30:
        verdict = "inconclusive (underpowered)"
    elif summary["fraction_gnomonic"] >= 2 / 3:
        verdict = "supports"
    elif summary["fraction_allometric"] >= 2 / 3:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary["verdict_by_preregistered_rule"] = verdict
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
