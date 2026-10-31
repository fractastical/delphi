#!/usr/bin/env python3
"""Test of levin-2023-competency-04: higher cellular competency accelerates evolutionary
search in the Shreesha & Levin (2023) 1D artificial-embryo model.

Independent re-implementation of Experiment 1 (Supplement S2.1): a hardwired population and
competent populations with 20, 100 and 400 bubble-sort swaps, 100 repeats of 250
generations each. Model details not stated in the paper follow the authors' code
(github.com/Niwhskal/CellularCompetency, commit 2be29f96), see result.json.

Run: python3 analysis.py [--jobs N] [--repeats R]   (needs numpy)
"""
import argparse
import json
import math
import os
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE, LOW, HIGH = 50, 1, 51
N_ORG, N_SEL = 100, 10
P_MUT = 0.6
GENERATIONS = 250
LEVELS = [0, 20, 100, 400]
THRESHOLDS = [0.65, 0.75, 0.8, 0.9, 0.97, 1.0]
TEST_GENERATIONS = [2, 10, 20]
SEED = 20230131
NCR = SIZE * (SIZE - 1) // 2
IU, JU = np.triu_indices(SIZE, k=1)


def inversions(pop):
    return (pop[:, IU] > pop[:, JU]).sum(axis=1)


def fitness(pop):
    x = (NCR - inversions(pop)) / NCR
    return 9.0 ** x / 9.0


def develop(pop, limit, rng):
    """Restricted bubble sort: up to `limit` swaps of strictly inverted adjacent pairs,
    visiting the 49 positions in a fresh random order on every sweep."""
    q = pop.copy()
    rows = np.arange(len(q))
    budget = np.minimum(limit, inversions(q))
    done = np.zeros(len(q), dtype=int)
    active = budget > 0
    while active.any():
        order = np.argsort(rng.random((len(q), SIZE - 1)), axis=1)
        swapped = np.zeros(len(q), dtype=bool)
        for k in range(SIZE - 1):
            pos = order[:, k]
            a, b = q[rows, pos], q[rows, pos + 1]
            do = active & (a > b)
            q[rows[do], pos[do]], q[rows[do], pos[do] + 1] = b[do], a[do]
            done += do
            swapped |= do
            active &= done < budget
        active &= swapped
    return q


def reproduce(parents, rng):
    pop = list(parents)
    n = len(parents)
    while len(pop) < N_ORG:
        i, j = rng.integers(n), rng.integers(n)
        if i == j:
            continue
        cut = rng.integers(LOW + 10, SIZE)
        c1, c2 = parents[i].copy(), parents[j].copy()
        c1[:cut], c2[:cut] = parents[j][:cut], parents[i][:cut]
        pop += [c1, c2]
    return np.array(pop)


def mutate(pop, rng):
    pop = pop.copy()
    for k in range(len(pop)):
        if rng.random() <= P_MUT:
            pop[k, rng.integers(0, SIZE)] = rng.integers(LOW, HIGH)
    return pop


def run(args):
    level, seed = args
    rng = np.random.default_rng(seed)
    pop = rng.integers(LOW, HIGH, size=(N_ORG, SIZE))
    geno, pheno = [], []
    for _ in range(GENERATIONS):
        g = fitness(pop)
        p = fitness(develop(pop, level, rng)) if level else g
        geno.append(float(g.max()))
        pheno.append(float(p.max()))
        parents = pop[np.argsort(-p, kind="stable")[:N_SEL]]
        pop = mutate(reproduce(parents, rng), rng)
    return level, geno, pheno


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b) by Lentz's continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1.0 - betainc(b, a, 1 - x)
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)) / a
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    f = d
    for m in range(1, 500):
        for num in (m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
                    -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))):
            d = 1.0 + num * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + num / c
            c = c if abs(c) > tiny else tiny
            f *= c * d
        if abs(c * d - 1.0) < 1e-15:
            break
    return front * f


def welch_greater(x, y):
    """One-sided Welch t-test of mean(x) > mean(y)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = math.sqrt(vx + vy)
    diff = x.mean() - y.mean()
    if se == 0:
        return diff, (0.0 if diff > 0 else 1.0)
    t = diff / se
    df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    tail = 0.5 * betainc(df / 2, 0.5, df / (df + t * t))
    return t, (tail if t > 0 else 1.0 - tail)


def first_crossing(curve, threshold):
    hit = np.nonzero(curve >= threshold)[0]
    return int(hit[0] + 1) if len(hit) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--repeats", type=int, default=100)
    a = ap.parse_args()

    seeds = np.random.SeedSequence(SEED).generate_state(a.repeats * len(LEVELS))
    tasks = [(lvl, int(seeds[r * len(LEVELS) + k])) for r in range(a.repeats) for k, lvl in enumerate(LEVELS)]
    with Pool(a.jobs) as pool:
        results = pool.map(run, tasks, chunksize=1)

    pheno = {lvl: np.array([p for l, _, p in results if l == lvl]) for lvl in LEVELS}
    geno = {lvl: np.array([g for l, g, _ in results if l == lvl]) for lvl in LEVELS}
    name = lambda lvl: "hardwired" if lvl == 0 else f"competency_{lvl}"

    crossings = {name(l): {str(t): first_crossing(pheno[l].mean(axis=0), t) for t in THRESHOLDS} for l in LEVELS}
    big = GENERATIONS + 1
    gen = lambda l, t: crossings[name(l)][str(t)] or big

    strict_1 = all(gen(LEVELS[i], 1.0) > gen(LEVELS[i + 1], 1.0) for i in range(len(LEVELS) - 1))
    weak_all = all(gen(LEVELS[i], t) >= gen(LEVELS[i + 1], t) for t in THRESHOLDS for i in range(len(LEVELS) - 1))
    reversed_high = any(gen(LEVELS[i], t) < gen(LEVELS[j], t)
                        for t in (0.97, 1.0) for i in range(len(LEVELS)) for j in range(i + 1, len(LEVELS)))

    tests = {}
    for lvl in LEVELS[1:]:
        for g in TEST_GENERATIONS:
            t, p = welch_greater(pheno[lvl][:, g - 1], pheno[0][:, g - 1])
            tests[f"{name(lvl)}_vs_hardwired_gen{g}"] = {
                "mean_competent": round(float(pheno[lvl][:, g - 1].mean()), 6),
                "mean_hardwired": round(float(pheno[0][:, g - 1].mean()), 6),
                "t": round(float(t), 4), "p_one_sided": float(f"{p:.3e}")}

    c400_by_10 = gen(400, 1.0) <= 10
    hw_after_100 = gen(0, 1.0) > 100
    all_sig = all(v["p_one_sided"] < 1e-3 for v in tests.values())
    gen10_worse = any(v["p_one_sided"] >= 0.05 for k, v in tests.items() if k.endswith("gen10"))

    if reversed_high or gen10_worse:
        verdict = "refutes"
    elif strict_1 and weak_all and c400_by_10 and hw_after_100 and all_sig:
        verdict = "supports"
    else:
        verdict = "mixed"

    paper_table1 = {"hardwired": [10, 18, 24, 42, 72, 250], "competency_20": [9, 16, 21, 36, 55, 93],
                    "competency_100": [5, 9, 12, 19, 26, 37], "competency_400": [2, 2, 2, 2, 3, 5]}
    out = {
        "value": gen(400, 1.0) if gen(400, 1.0) <= GENERATIONS else None,
        "unit": "generations for the mean best phenotypic fitness of the competency-400 population to reach 1.0",
        "n": a.repeats,
        "uncertainty": "Monte Carlo; fixed seed, deterministic for a given numpy version",
        "extra": {
            "generations_to_threshold": crossings,
            "paper_table1_generations_to_threshold": {k: dict(zip(map(str, THRESHOLDS), v)) for k, v in paper_table1.items()},
            "mean_best_phenotypic_fitness_at_gen": {name(l): {str(g): round(float(pheno[l][:, g - 1].mean()), 6)
                                                              for g in (1, 2, 5, 10, 20, 50, 100, 200, 250)} for l in LEVELS},
            "mean_best_genotypic_fitness_at_gen": {name(l): {str(g): round(float(geno[l][:, g - 1].mean()), 6)
                                                             for g in (1, 10, 50, 100, 250)} for l in LEVELS},
            "welch_tests": tests,
            "criteria": {"strict_order_at_1.0": strict_1, "weak_order_all_thresholds": weak_all,
                         "competency_400_reaches_1.0_by_gen_10": c400_by_10,
                         "hardwired_reaches_1.0_after_gen_100": hw_after_100,
                         "all_t_tests_p_lt_0.001": all_sig,
                         "higher_competency_slower_at_0.97_or_1.0": reversed_high,
                         "some_competent_not_better_at_gen_10": gen10_worse},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    curves = {name(l): {"mean_best_phenotypic": [round(float(v), 6) for v in pheno[l].mean(axis=0)],
                        "mean_best_genotypic": [round(float(v), 6) for v in geno[l].mean(axis=0)]} for l in LEVELS}
    with open(os.path.join(HERE, "derived", "mean_curves.json"), "w") as fh:
        json.dump(curves, fh)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
