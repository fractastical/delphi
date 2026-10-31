#!/usr/bin/env python3
"""Test of levin-2023-competency-06: in mixed populations of the Shreesha & Levin (2023) 1D
artificial-embryo model, the competency a competent minority needs to dominate falls as its
initial share rises (75 at 10%, 40 at 20%, 10 at 30%); at 2.5% it does not dominate even at
competency 95; dominance takes two or three generations.

Mixed-population variant of the Experiment 1 re-implementation in
../levin-2023-competency-04/analysis.py (fitness() and develop() are imported from there).
200 embryos; each carries a heritable type label that travels with the left crossover segment,
as in the authors' Exp2-MixedPrevalence.py. Competent embryos are selected on phenotypic
fitness, hardwired ones on genotypic fitness, top 10% (20) kept.

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

SIZE, LOW, HIGH = c04.SIZE, c04.LOW, c04.HIGH
N_ORG, N_SEL = 200, 20
P_MUT = c04.P_MUT
GENERATIONS = 20
SHARES = [0.025, 0.10, 0.20, 0.30]
LEVELS = list(range(5, 100, 5))
CLAIMED = {"0.1": 75, "0.2": 40, "0.3": 10}
COMP, HW = -1, -2
SEED = 20261031_06


def reproduce(genes, labels, rng):
    """Single-point crossover on [label | genes]: cut in [11, 50) of the 51-long array, so the
    label goes with the left segment and the structural cut is in [10, 49)."""
    g, lab = list(genes), list(labels)
    n = len(genes)
    while len(g) < N_ORG:
        i, j = rng.integers(n), rng.integers(n)
        if i == j:
            continue
        cut = rng.integers(LOW + 10, SIZE) - 1
        c1, c2 = genes[i].copy(), genes[j].copy()
        c1[:cut], c2[:cut] = genes[j][:cut], genes[i][:cut]
        g += [c1, c2]
        lab += [labels[j], labels[i]]
    return np.array(g), np.array(lab)


def mutate(genes, labels, rng, authors_quirk):
    genes, labels = genes.copy(), labels.copy()
    for k in range(len(genes)):
        if rng.random() <= P_MUT:
            if authors_quirk:
                # authors' code: position drawn from [0, 50) of [label | genes], so the label can
                # be overwritten and the last structural gene is never mutated
                pos, val = rng.integers(0, SIZE), rng.integers(LOW, HIGH)
                if pos == 0:
                    labels[k] = val
                else:
                    genes[k, pos - 1] = val
            else:
                genes[k, rng.integers(0, SIZE)] = rng.integers(LOW, HIGH)
    return genes, labels


def run(args):
    share, level, seed, quirk = args
    rng = np.random.default_rng(seed)
    n_comp = int(round(share * N_ORG))
    genes = rng.integers(LOW, HIGH, size=(N_ORG, SIZE))
    labels = np.array([HW] * (N_ORG - n_comp) + [COMP] * n_comp)
    shares = []
    for _ in range(GENERATIONS):
        shares.append(float((labels == COMP).mean()))
        limit = np.where(labels != HW, level, 0)
        fit = c04.fitness(c04.develop(genes, limit, rng))
        keep = np.argsort(-fit, kind="stable")[:N_SEL]
        genes, labels = mutate(*reproduce(genes[keep], labels[keep], rng), rng, quirk)
    return share, level, quirk, shares


def threshold(dominates):
    """Smallest tested level from which dominance holds at it and every higher level."""
    c = 100
    for lvl in reversed(LEVELS):
        if not dominates[lvl]:
            break
        c = lvl
    return c


def analyse(curves, repeats):
    table, cstar, takeover = {}, {}, {}
    for s in SHARES:
        row, dom = {}, {}
        for lvl in LEVELS:
            arr = np.array(curves[(s, lvl)])
            m = arr.mean(axis=0)
            over = np.nonzero(m > 0.5)[0]
            dom[lvl] = bool(m[-1] > 0.5)
            row[str(lvl)] = {"mean_share_gen1": round(float(m[0]), 4),
                             "mean_share_gen2": round(float(m[1]), 4),
                             "mean_share_gen3": round(float(m[2]), 4),
                             "mean_share_gen4": round(float(m[3]), 4),
                             "mean_share_gen20": round(float(m[-1]), 4),
                             "sd_share_gen20": round(float(arr[:, -1].std(ddof=1)), 4),
                             "runs_competent_majority_gen20": int((arr[:, -1] > 0.5).sum()),
                             "first_gen_mean_share_gt_0.5": int(over[0] + 1) if len(over) else None}
        table[str(s)] = row
        cstar[str(s)] = threshold(dom)
        takeover[str(s)] = [row[str(l)]["first_gen_mean_share_gt_0.5"] for l in LEVELS if l >= cstar[str(s)]]
    return table, cstar, takeover


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--repeats", type=int, default=50)
    a = ap.parse_args()

    conds = [(s, lvl) for s in SHARES for lvl in LEVELS]
    seeds = np.random.SeedSequence(SEED).generate_state(2 * a.repeats * len(conds))
    tasks = [(s, lvl, int(seeds[(q * a.repeats + r) * len(conds) + k]), bool(q))
             for q in (0, 1) for r in range(a.repeats) for k, (s, lvl) in enumerate(conds)]
    with Pool(a.jobs) as pool:
        results = pool.map(run, tasks, chunksize=4)

    out_by_variant = {}
    for quirk in (False, True):
        curves = {c: [sh for s, l, q, sh in results if (s, l) == c and q == quirk] for c in conds}
        out_by_variant[quirk] = analyse(curves, a.repeats)

    table, cstar, takeover = out_by_variant[False]
    p25_95 = table["0.025"]["95"]["mean_share_gen20"]
    P1 = cstar["0.1"] > cstar["0.2"] > cstar["0.3"]
    P2 = abs(cstar["0.1"] - 75) <= 20 and abs(cstar["0.2"] - 40) <= 20 and cstar["0.3"] <= 20
    P3 = p25_95 <= 0.6
    P4 = all(t is not None and t <= 4 for s in ("0.1", "0.2", "0.3") for t in takeover[s])
    fail = (cstar["0.3"] >= cstar["0.1"] or any(abs(cstar[s] - CLAIMED[s]) > 40 for s in CLAIMED)
            or p25_95 > 0.75)
    verdict = "refutes" if fail else ("supports" if P1 and P2 and P3 and P4 else "mixed")

    q_table, q_cstar, _ = out_by_variant[True]
    out = {
        "value": cstar,
        "unit": "smallest tested competency (5-swap grid, 5-95; 100 = none) from which the mean competent share at generation 20 exceeds 0.5, by initial competent share",
        "n": a.repeats,
        "uncertainty": "Monte Carlo; fixed seed, deterministic for a given numpy version; threshold resolution 5 swaps",
        "extra": {
            "claimed_thresholds": CLAIMED,
            "share_2.5pct_competency_95_mean_share_gen20": p25_95,
            "max_mean_share_gen20_at_2.5pct": max(table["0.025"][str(l)]["mean_share_gen20"] for l in LEVELS),
            "takeover_first_gen_mean_share_gt_0.5_for_levels_ge_cstar": takeover,
            "mean_share_gen20": {s: {l: table[s][l]["mean_share_gen20"] for l in table[s]} for s in table},
            "authors_code_quirk_variant": {
                "cstar": q_cstar,
                "share_2.5pct_competency_95_mean_share_gen20": q_table["0.025"]["95"]["mean_share_gen20"],
                "mean_share_gen20": {s: {l: q_table[s][l]["mean_share_gen20"] for l in q_table[s]} for s in q_table}},
            "criteria": {"P1_threshold_decreasing": P1, "P2_thresholds_within_20": P2,
                         "P3_no_dominance_at_2.5pct_c95": P3, "P4_takeover_within_3_rounds": P4,
                         "fail_rule_triggered": fail},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    with open(os.path.join(HERE, "derived", "conditions.json"), "w") as fh:
        json.dump({"main": table, "authors_code_quirk": q_table}, fh)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
