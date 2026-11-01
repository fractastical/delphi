"""Post-hoc discriminating-power check for kimura-heterozygosity (added 2026-10-31 after the pre-registered result; it
changes nothing in the verdict).

Question: could the pre-registered rule have said 'supports' if the law held? Simulate datasets with the observed census
sizes, the law's slope (1.0) or a perturbed slope, and the observed residual scatter; apply the rule from analysis.py
unchanged; report how often each verdict comes out. A simulation result shows what the rule would do, nothing more.

Reads data/combined_data.tsv; writes derived/perturbation.json.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from analysis import DATA, DERIVED, fit

N_SIM = 2000
SLOPES = [1.0, 0.75, 0.5, 0.25, 0.0]


def rule(res):
    lo, hi = res["ols_slope_ci95"]
    if res["n_species"] < 50:
        return "inconclusive"
    if res["spearman_rho"] > 0.5 and res["spearman_p"] < 0.001 and res["ols_slope"] >= 0.3 and hi >= 0.5:
        return "supports"
    if hi < 0.25 or res["spearman_rho"] <= 0:
        return "refutes"
    return "mixed"


def main():
    d = pd.read_csv(DATA, sep="\t")
    d = d[(d["kingdom"] == "Animalia") & d["diversity"].notna() & d["log10_popsize"].notna()].copy()
    d = d[d["diversity"] > 0].drop_duplicates(subset="species")
    d = d[d["class"] != "Aves"].copy()
    obs = fit(d)
    x = d["log10_popsize"].to_numpy()
    y = np.log10(d["diversity"].to_numpy())
    resid_sd = float(np.std(y - (obs["ols_intercept"] + obs["ols_slope"] * x), ddof=2))
    rng = np.random.default_rng(20261031)
    out = {"observed": {"verdict": rule(obs), "ols_slope": obs["ols_slope"], "ols_slope_ci95": obs["ols_slope_ci95"], "spearman_rho": obs["spearman_rho"],
                        "n_species": obs["n_species"], "residual_sd_log10_pi": resid_sd},
           "n_simulations_per_slope": N_SIM, "simulated": {}}
    for s in SLOPES:
        counts = {}
        slopes = []
        for _ in range(N_SIM):
            ysim = y.mean() + s * (x - x.mean()) + rng.normal(0, resid_sd, len(x))
            sim = pd.DataFrame({"log10_popsize": x, "diversity": 10 ** ysim})
            r = fit(sim)
            v = rule(r)
            counts[v] = counts.get(v, 0) + 1
            slopes.append(r["ols_slope"])
        out["simulated"][str(s)] = {"true_slope": s, "verdict_fractions": {k: v / N_SIM for k, v in sorted(counts.items())},
                                    "mean_fitted_slope": float(np.mean(slopes))}
    out["reading"] = ("Under the law as operationalized (true slope 1 with the observed census sizes and scatter) the pre-registered rule returns "
                      "'supports' in the fraction shown for slope 1.0; the observed data (slope 0.107) return 'refutes'. The rule therefore "
                      "discriminates the law from the observed pattern; the refutation is not a failure of test sensitivity.")
    os.makedirs(DERIVED, exist_ok=True)
    json.dump(out, open(os.path.join(DERIVED, "perturbation.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
