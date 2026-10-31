#!/usr/bin/env python3
"""Test of levin-2023-competency-05: in the Shreesha & Levin (2023) 1D artificial-embryo model,
competent populations' genotypic fitness plateaus below hardwired, with wider spread at higher
competency, while phenotypic fitness stays high.

Re-runs Experiment 1 (hardwired and competency 20/100/400, 100 repeats x 250 generations) with
the re-implementation in ../levin-2023-competency-04/analysis.py and fresh seeds.

Run: python3 analysis.py [--jobs N] [--repeats R]   (needs numpy)
"""
import argparse
import importlib.util
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "competency04", os.path.join(HERE, "..", "levin-2023-competency-04", "analysis.py"))
c04 = importlib.util.module_from_spec(_spec)
sys.modules["competency04"] = c04
_spec.loader.exec_module(c04)

LEVELS = c04.LEVELS
GENERATIONS = c04.GENERATIONS
SEED = 20261031_05


def window(curve, a, b):
    """Mean of a 1-indexed generation window [a, b]."""
    return float(np.mean(curve[a - 1:b]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--repeats", type=int, default=100)
    a = ap.parse_args()

    seeds = np.random.SeedSequence(SEED).generate_state(a.repeats * len(LEVELS))
    tasks = [(lvl, int(seeds[r * len(LEVELS) + k])) for r in range(a.repeats) for k, lvl in enumerate(LEVELS)]
    with Pool(a.jobs) as pool:
        results = pool.map(c04.run, tasks, chunksize=1)

    geno = {lvl: np.array([g for l, g, _ in results if l == lvl]) for lvl in LEVELS}
    pheno = {lvl: np.array([p for l, _, p in results if l == lvl]) for lvl in LEVELS}
    name = lambda lvl: "hardwired" if lvl == 0 else f"competency_{lvl}"
    comp = LEVELS[1:]

    welch, plateau, spread, pheno250, diverge = {}, {}, {}, {}, {}
    for lvl in LEVELS:
        m = geno[lvl].mean(axis=0)
        early, late = window(m, 126, 150), window(m, 226, 250)
        plateau[name(lvl)] = {"mean_126_150": round(early, 6), "mean_226_250": round(late, 6),
                              "change": round(late - early, 6)}
        spread[name(lvl)] = round(float(geno[lvl][:, 50:].std(axis=0, ddof=1).mean()), 6)
        pheno250[name(lvl)] = round(float(pheno[lvl][:, -1].mean()), 6)
    hw = geno[0].mean(axis=0)
    for lvl in comp:
        t, p = c04.welch_greater(geno[0][:, -1], geno[lvl][:, -1])
        welch[name(lvl)] = {"mean_competent": round(float(geno[lvl][:, -1].mean()), 6),
                            "mean_hardwired": round(float(geno[0][:, -1].mean()), 6),
                            "t": round(float(t), 4), "p_one_sided": float(f"{p:.3e}")}
        gap = np.nonzero(hw - geno[lvl].mean(axis=0) > 0.02)[0]
        diverge[name(lvl)] = int(gap[0] + 1) if len(gap) else None

    A = all(welch[name(l)]["mean_competent"] < welch[name(l)]["mean_hardwired"] and welch[name(l)]["p_one_sided"] < 1e-3
            for l in comp)
    B = all(abs(plateau[name(l)]["change"]) < 0.03 for l in comp)
    C = spread["competency_20"] < spread["competency_100"] < spread["competency_400"]
    D = all(pheno250[name(l)] >= 0.95 for l in comp)
    fail = (any(welch[name(l)]["mean_competent"] >= welch[name(l)]["mean_hardwired"] for l in comp)
            or spread["competency_400"] < spread["competency_20"]
            or any(plateau[name(l)]["change"] > 0.1 for l in comp))
    verdict = "refutes" if fail else ("supports" if A and B and C and D else "mixed")

    out = {
        "value": welch["competency_400"]["mean_competent"],
        "unit": "mean best genotypic fitness at generation 250, competency 400 (hardwired: see extra)",
        "n": a.repeats,
        "uncertainty": "Monte Carlo; fixed seed, deterministic for a given numpy version",
        "extra": {
            "welch_gen250_hardwired_gt_competent": welch,
            "genotypic_plateau_windows": plateau,
            "mean_across_repeat_sd_best_genotypic_gen51_250": spread,
            "mean_best_phenotypic_fitness_gen250": pheno250,
            "first_gen_competent_genotypic_mean_below_hardwired_by_0.02": diverge,
            "mean_best_genotypic_fitness_at_gen": {name(l): {str(g): round(float(geno[l][:, g - 1].mean()), 6)
                                                             for g in (1, 2, 3, 5, 10, 20, 50, 100, 150, 200, 250)}
                                                   for l in LEVELS},
            "criteria": {"A_below_hardwired_p_lt_0.001": A, "B_plateau_change_lt_0.03": B,
                         "C_spread_increases_with_competency": C, "D_phenotypic_ge_0.95": D,
                         "fail_rule_triggered": fail},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    curves = {name(l): {"mean_best_genotypic": [round(float(v), 5) for v in geno[l].mean(axis=0)],
                        "sd_best_genotypic": [round(float(v), 5) for v in geno[l].std(axis=0, ddof=1)],
                        "mean_best_phenotypic": [round(float(v), 5) for v in pheno[l].mean(axis=0)]}
              for l in LEVELS}
    with open(os.path.join(HERE, "derived", "genotypic_curves.json"), "w") as fh:
        json.dump(curves, fh)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
