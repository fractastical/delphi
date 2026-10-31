#!/usr/bin/env python3
"""Test of levin-2023-competency-07: with an evolvable competency gene (range [1, 500],
initialised in [1, 15]) the best individual's competency in the Shreesha & Levin (2023) 1D
artificial-embryo model rises rapidly and plateaus around 470, above the ~364 swaps needed.

Evolvable-competency variant of the Experiment 1 re-implementation in
../levin-2023-competency-04/analysis.py (fitness(), inversions(), develop() and reproduce() are
imported from there). Each genome is 50 structural genes plus a competency gene at index 50;
crossover cuts fall in [11, 50) so the competency gene travels with the right segment, and a
point mutation hits one of the 51 positions uniformly (the competency gene is redrawn in
[1, 500]), as in the authors' Exp3-EvolvableCompetency.py. run() is also used by
../levin-2023-competency-08/analysis.py.

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
if "competency04" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "competency04", os.path.join(HERE, "..", "levin-2023-competency-04", "analysis.py"))
    _m = importlib.util.module_from_spec(_spec)
    sys.modules["competency04"] = _m
    _spec.loader.exec_module(_m)
c04 = sys.modules["competency04"]

SIZE, LOW, HIGH = c04.SIZE, c04.LOW, c04.HIGH
N_ORG, N_SEL, P_MUT = c04.N_ORG, c04.N_SEL, c04.P_MUT
GENE_MAX, GENE_INIT_MAX = 500, 15
GENERATIONS = 1000
SEED = 20261031_07
SERIES = ["best_geno_competency", "best_geno_needed", "best_pheno_competency", "best_pheno_needed",
          "pop_min_competency", "pop_max_competency", "max_genotypic", "max_phenotypic",
          "r_geno_pheno", "n_pheno_max", "selection_differential_genotypic"]


def mutate(pop, rng):
    pop = pop.copy()
    for k in range(len(pop)):
        if rng.random() <= P_MUT:
            pos = rng.integers(0, SIZE + 1)
            pop[k, pos] = rng.integers(1, GENE_MAX + 1) if pos == SIZE else rng.integers(LOW, HIGH)
    return pop


def run(args):
    seed, generations = args
    rng = np.random.default_rng(seed)
    pop = np.concatenate([rng.integers(LOW, HIGH, size=(N_ORG, SIZE)),
                          rng.integers(1, GENE_INIT_MAX + 1, size=(N_ORG, 1))], axis=1)
    rec = {k: [] for k in SERIES}
    for _ in range(generations):
        struct, comp = pop[:, :SIZE], pop[:, SIZE]
        g = c04.fitness(struct)
        p = c04.fitness(c04.develop(struct, comp, rng))
        inv = c04.inversions(struct)
        bg = int(np.argmax(g))
        order = np.argsort(-p, kind="stable")
        bp, keep = order[0], order[:N_SEL]
        r = np.corrcoef(g, p)[0, 1] if g.std() > 0 and p.std() > 0 else np.nan
        for k, v in (("best_geno_competency", comp[bg]), ("best_geno_needed", inv[bg]),
                     ("best_pheno_competency", comp[bp]), ("best_pheno_needed", inv[bp]),
                     ("pop_min_competency", comp.min()), ("pop_max_competency", comp.max()),
                     ("max_genotypic", g.max()), ("max_phenotypic", p.max()), ("r_geno_pheno", r),
                     ("n_pheno_max", (p >= 1.0).sum()),
                     ("selection_differential_genotypic", g[keep].mean() - g.mean())):
            rec[k].append(float(v))
        pop = mutate(c04.reproduce(pop[keep], rng), rng)
    return seed, rec


def simulate(seed, repeats, jobs, generations=GENERATIONS):
    seeds = np.random.SeedSequence(seed).generate_state(repeats)
    with Pool(jobs) as pool:
        results = pool.map(run, [(int(s), generations) for s in seeds], chunksize=1)
    return {k: np.array([rec[k] for _, rec in results]) for k in SERIES}


def window(curve, a, b):
    return float(np.mean(curve[a - 1:b]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--repeats", type=int, default=30)
    a = ap.parse_args()

    d = simulate(SEED, a.repeats, a.jobs)
    m = {k: v.mean(axis=0) for k, v in d.items()}
    comp = m["best_geno_competency"]
    hit = np.nonzero(comp >= 300)[0]
    rise = int(hit[0] + 1) if len(hit) else None
    plateau = window(comp, 801, 1000)
    needed = window(m["best_geno_needed"], 801, 1000)
    shift = window(comp, 901, 1000) - window(comp, 801, 900)

    R = rise is not None and rise <= 50
    L = 440 <= plateau <= 500
    N = plateau > needed
    S = abs(shift) <= 20
    fail = plateau < 400 or plateau <= needed or rise is None
    verdict = "refutes" if fail else ("supports" if R and L and N and S else "mixed")

    tie = d["n_pheno_max"][:, 800:] >= N_SEL
    per_run_plateau = d["best_geno_competency"][:, 800:].mean(axis=1)
    out = {
        "value": round(plateau, 2),
        "unit": "mean competency gene of the best (highest-genotypic-fitness) individual over generations 801-1000, averaged over repeats",
        "n": a.repeats,
        "uncertainty": f"SD across repeats of the per-run generation-801-1000 mean: {per_run_plateau.std(ddof=1):.2f}; fixed seed",
        "extra": {
            "first_gen_mean_best_competency_ge_300": rise,
            "mean_best_competency_at_gen": {str(g): round(float(comp[g - 1]), 2)
                                            for g in (1, 2, 5, 10, 15, 20, 30, 50, 100, 200, 500, 800, 1000)},
            "mean_best_competency_801_900": round(window(comp, 801, 900), 2),
            "mean_best_competency_901_1000": round(window(comp, 901, 1000), 2),
            "mean_needed_competency_best_individual_801_1000": round(needed, 2),
            "mean_best_genotypic_fitness_801_1000": round(window(m["max_genotypic"], 801, 1000), 4),
            "mean_best_phenotypic_fitness_801_1000": round(window(m["max_phenotypic"], 801, 1000), 4),
            "secondary_best_by_phenotype": {
                "mean_competency_801_1000": round(window(m["best_pheno_competency"], 801, 1000), 2),
                "mean_needed_801_1000": round(window(m["best_pheno_needed"], 801, 1000), 2)},
            "mean_population_max_competency_801_1000": round(window(m["pop_max_competency"], 801, 1000), 2),
            "max_population_competency_any_run_any_gen": int(d["pop_max_competency"].max()),
            "mean_population_min_competency_801_1000": round(window(m["pop_min_competency"], 801, 1000), 2),
            "per_run_plateau_range": [round(float(per_run_plateau.min()), 2), round(float(per_run_plateau.max()), 2)],
            "fraction_plateau_generations_with_ge_10pct_at_phenotypic_1.0": round(float(tie.mean()), 4),
            "criteria": {"R_rise_to_300_by_gen_50": R, "L_plateau_in_440_500": L,
                         "N_plateau_above_needed": N, "S_plateau_stable_within_20": S,
                         "fail_rule_triggered": fail},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    keys = ["best_geno_competency", "best_geno_needed", "best_pheno_competency", "pop_min_competency",
            "pop_max_competency", "max_genotypic", "max_phenotypic"]
    with open(os.path.join(HERE, "derived", "mean_curves.json"), "w") as fh:
        json.dump({k: [round(float(v), 3) for v in m[k]] for k in keys}, fh)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
