"""Test of kimura-heterozygosity: does nucleotide diversity rise with census population size across metazoa?

Reads data/combined_data.tsv (run fetch.py first). Writes derived/species_table.csv and derived/summary.json.
Primary analysis excludes class Aves (held out); bird rows are reported separately and are not fitted.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "combined_data.tsv")
DERIVED = os.path.join(HERE, "derived")


def fit(d):
    x = d["log10_popsize"].to_numpy()
    y = np.log10(d["diversity"].to_numpy())
    rho, p_rho = stats.spearmanr(x, y)
    ols = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, len(d) - 2)
    return {
        "n_species": int(len(d)),
        "spearman_rho": float(rho),
        "spearman_p": float(p_rho),
        "ols_slope": float(ols.slope),
        "ols_slope_se": float(ols.stderr),
        "ols_slope_ci95": [float(ols.slope - tcrit * ols.stderr), float(ols.slope + tcrit * ols.stderr)],
        "ols_intercept": float(ols.intercept),
        "pearson_r": float(ols.rvalue),
        "log10_N_range": [float(x.min()), float(x.max())],
        "log10_pi_range": [float(y.min()), float(y.max())],
    }


def main():
    os.makedirs(DERIVED, exist_ok=True)
    d = pd.read_csv(DATA, sep="\t")
    d = d[(d["kingdom"] == "Animalia") & d["diversity"].notna() & d["log10_popsize"].notna()].copy()
    d = d[(d["diversity"] > 0)]
    d = d.drop_duplicates(subset="species")
    birds = d[d["class"] == "Aves"].copy()
    main_d = d[d["class"] != "Aves"].copy()
    res = fit(main_d)
    # Holdout: class Aves is exam data. Bird rows are never fitted, and their residuals from the main fit are computed only
    # when the holdout thread runs this script with --exam, after building has stopped.
    holdout = {"n_bird_species_held_out": int(len(birds)), "note": "class Aves excluded from fitting at the holdout thread's request; scored only with --exam"}
    if "--exam" in sys.argv[1:]:
        pred_birds = res["ols_intercept"] + res["ols_slope"] * birds["log10_popsize"].to_numpy()
        holdout["bird_mean_residual_log10_pi_from_main_fit"] = float(np.mean(np.log10(birds["diversity"].to_numpy()) - pred_birds)) if len(birds) else None
        holdout["bird_species"] = birds[["species", "diversity", "log10_popsize"]].to_dict("records")
    # Pre-registered decision rule.
    lo, hi = res["ols_slope_ci95"]
    if res["n_species"] < 50:
        verdict = "inconclusive"
    elif res["spearman_rho"] > 0.5 and res["spearman_p"] < 0.001 and res["ols_slope"] >= 0.3 and hi >= 0.5:
        verdict = "supports"
    elif hi < 0.25 or res["spearman_rho"] <= 0:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {"main": res, "holdout_aves": holdout, "verdict": verdict,
               "diversity_sources": main_d["diversity_data_source"].value_counts(dropna=False).to_dict(),
               "classes_in_main": main_d["class"].value_counts(dropna=False).to_dict()}
    cols = ["species", "phylum", "class", "diversity", "diversity_data_source", "log10_popsize", "log10_range", "log10_body_mass", "log10_density"]
    d.assign(held_out=(d["class"] == "Aves"))[cols + ["held_out"]].sort_values("log10_popsize").to_csv(os.path.join(DERIVED, "species_table.csv"), index=False)
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
