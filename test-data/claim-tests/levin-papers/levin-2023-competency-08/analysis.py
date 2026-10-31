#!/usr/bin/env python3
"""Test of levin-2023-competency-08: with evolvable competency in the Shreesha & Levin (2023) 1D
artificial-embryo model, the correlation between genotypic and phenotypic fitness falls to zero
within about 20 generations.

Uses the evolvable-competency simulator in ../levin-2023-competency-07/analysis.py (itself built
on ../levin-2023-competency-04/analysis.py) with independent seeds. Primary statistic: Pearson r
across the 100 individuals of a population each generation, averaged over repeats.

Run: python3 analysis.py [--jobs N] [--repeats R]   (needs numpy)
"""
import argparse
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "competency07", os.path.join(HERE, "..", "levin-2023-competency-07", "analysis.py"))
c07 = importlib.util.module_from_spec(_spec)
sys.modules["competency07"] = c07
_spec.loader.exec_module(c07)

SEED = 20261031_08
BIN = 10


def window(curve, a, b):
    return float(np.nanmean(curve[a - 1:b]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--repeats", type=int, default=30)
    a = ap.parse_args()

    d = c07.simulate(SEED, a.repeats, a.jobs)
    r = d["r_geno_pheno"]
    undefined = int(np.isnan(r).sum())
    rm = np.nanmean(r, axis=0)
    r1, r21_40, r41_1000 = float(rm[0]), window(rm, 21, 40), window(rm, 41, 1000)
    below = np.nonzero(rm <= 0.1)[0]

    gm, pm = d["max_genotypic"].mean(axis=0), d["max_phenotypic"].mean(axis=0)
    authors = []
    for i in range(0, len(gm), BIN):
        x, y = gm[i:i + BIN], pm[i:i + BIN]
        authors.append(float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else 0.0)
    authors = np.array(authors)
    sd = d["selection_differential_genotypic"].mean(axis=0)

    passed = r1 >= 0.5 and r21_40 <= 0.1 and r41_1000 <= 0.1
    fail = r21_40 >= 0.3 or r41_1000 >= 0.3
    verdict = "refutes" if fail else ("supports" if passed else "mixed")

    out = {
        "value": round(r41_1000, 4),
        "unit": "mean across-individual Pearson r between genotypic and phenotypic fitness, generations 41-1000, averaged over repeats",
        "n": a.repeats,
        "uncertainty": f"SD across repeats of per-run generation-41-1000 mean r: {np.nanstd(np.nanmean(r[:, 40:], axis=1), ddof=1):.4f}; fixed seed",
        "extra": {
            "mean_r_gen1": round(r1, 4),
            "mean_r_gen21_40": round(r21_40, 4),
            "mean_r_gen41_1000": round(r41_1000, 4),
            "mean_r_at_gen": {str(g): round(float(rm[g - 1]), 4) for g in (1, 2, 3, 5, 10, 15, 20, 25, 30, 40, 50, 100, 500, 1000)},
            "first_gen_mean_r_le_0.1": int(below[0] + 1) if len(below) else None,
            "undefined_correlations_run_generations": undefined,
            "authors_code_statistic_binned_best_curve_correlation": {
                "bins_1_to_5": [round(float(v), 4) for v in authors[:5]],
                "mean_bins_3_to_100_gens_21_1000": round(float(authors[2:].mean()), 4)},
            "selection_differential_genotypic": {"gen1_10": round(window(sd, 1, 10), 5),
                                                 "gen41_1000": round(window(sd, 41, 1000), 5)},
            "mean_best_genotypic_fitness_41_1000": round(window(gm, 41, 1000), 4),
            "mean_best_phenotypic_fitness_41_1000": round(window(pm, 41, 1000), 4),
            "criteria": {"r_gen1_ge_0.5": r1 >= 0.5, "r_21_40_le_0.1": r21_40 <= 0.1,
                         "r_41_1000_le_0.1": r41_1000 <= 0.1, "fail_rule_triggered": fail},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    with open(os.path.join(HERE, "derived", "correlation_curves.json"), "w") as fh:
        json.dump({"mean_r_across_individuals": [round(float(v), 4) for v in rm],
                   "authors_binned_correlation": [round(float(v), 4) for v in authors],
                   "mean_selection_differential_genotypic": [round(float(v), 5) for v in sd]}, fh)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
