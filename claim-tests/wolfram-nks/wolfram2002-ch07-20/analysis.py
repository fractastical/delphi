#!/usr/bin/env python3
"""Test of wolfram2002-ch07-20: rule complexity vs behavioural complexity.

Families: F1 = 256 elementary CA; F2 = 2187 three-colour totalistic CA.
Rule complexity: ANF monomial count and minimal gate count (F1); table entropy
and non-default entries (F2).  Behaviour complexity: lzma size of space-time
diagrams from random and single-seed initial conditions.
Writes derived/table_eca.csv, derived/table_tot3.csv, derived/summary.json.
"""
import itertools
import json
import lzma
import math
import os
from collections import Counter

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20260720
WIDTH, TRANSIENT, STEPS = 300, 200, 400
SINGLE_T = 400


def lz(arr):
    return len(lzma.compress(np.ascontiguousarray(arr, dtype=np.uint8).tobytes(), preset=9))


# ----------------------------------------------------------------------------- F1
def eca_table(rule):
    return np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)


def anf_monomials(rule):
    # truth table index i = 4l + 2c + r; Moebius transform over GF(2)
    f = [(rule >> i) & 1 for i in range(8)]
    a = f[:]
    for bit in (1, 2, 4):
        for i in range(8):
            if i & bit:
                a[i] ^= a[i ^ bit]
    return sum(a)


def min_gates_all():
    """Minimal number of two-input gates (AND, OR, XOR; NOT free) for every 3-input
    Boolean function, by BFS over truth tables (8-bit masks)."""
    x = sum(1 << i for i in range(8) if (i >> 2) & 1)
    y = sum(1 << i for i in range(8) if (i >> 1) & 1)
    z = sum(1 << i for i in range(8) if i & 1)
    FULL = 0xFF
    cost = {}
    level = set()
    for v in (0, FULL, x, y, z, FULL ^ x, FULL ^ y, FULL ^ z):
        cost[v] = 0
        level.add(v)
    known = set(level)
    g = 0
    while len(cost) < 256:
        g += 1
        new = set()
        items = list(known)
        for a in items:
            for b in items:
                if cost[a] + cost[b] + 1 > g:
                    continue
                for v in (a & b, a | b, a ^ b):
                    for w in (v, FULL ^ v):
                        if w not in cost or cost[w] > cost[a] + cost[b] + 1:
                            if cost[a] + cost[b] + 1 == g:
                                new.add(w)
        for w in new:
            if w not in cost:
                cost[w] = g
        known |= new
    # cost dict keyed by truth-table mask with bit i = f(i); same as rule number
    return cost


def run_eca_random(rule, rng):
    t = eca_table(rule)
    row = rng.integers(0, 2, WIDTH).astype(np.uint8)
    out = np.zeros((STEPS, WIDTH), dtype=np.uint8)
    for s in range(TRANSIENT + STEPS):
        row = t[4 * np.roll(row, 1) + 2 * row + np.roll(row, -1)]
        if s >= TRANSIENT:
            out[s - TRANSIENT] = row
    return out


def run_eca_single(rule):
    t = eca_table(rule)
    w = 2 * SINGLE_T + 1
    row = np.zeros(w, dtype=np.uint8)
    row[SINGLE_T] = 1
    out = np.zeros((SINGLE_T, w), dtype=np.uint8)
    for s in range(SINGLE_T):
        out[s] = row
        l = np.roll(row, 1)
        r = np.roll(row, -1)
        l[0] = 0
        r[-1] = 0
        row = t[4 * l + 2 * row + r]
    return out


# ----------------------------------------------------------------------------- F2
def tot3_table(code):
    return np.array([(code // 3 ** k) % 3 for k in range(7)], dtype=np.uint8)


def run_tot3_random(code, rng):
    t = tot3_table(code)
    row = rng.integers(0, 3, WIDTH).astype(np.uint8)
    out = np.zeros((STEPS, WIDTH), dtype=np.uint8)
    for s in range(TRANSIENT + STEPS):
        row = t[np.roll(row, 1).astype(np.int16) + row + np.roll(row, -1)]
        if s >= TRANSIENT:
            out[s - TRANSIENT] = row
    return out


def run_tot3_single(code):
    t = tot3_table(code)
    w = 2 * SINGLE_T + 1
    row = np.zeros(w, dtype=np.uint8)
    row[SINGLE_T] = 1  # single gray cell (NKS convention for these rules)
    out = np.zeros((SINGLE_T, w), dtype=np.uint8)
    for s in range(SINGLE_T):
        out[s] = row
        l = np.roll(row, 1).astype(np.int16)
        r = np.roll(row, -1).astype(np.int16)
        l[0] = 0
        r[-1] = 0
        row = t[l + row + r]
    return out


def entropy_bits(vals):
    c = Counter(vals.tolist())
    n = len(vals)
    return -sum(k / n * math.log2(k / n) for k in c.values())


def main():
    rng = np.random.default_rng(SEED)
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)

    gates = min_gates_all()
    eca = []
    for r in range(256):
        eca.append({"rule": r, "anf": anf_monomials(r), "gates": gates[r],
                    "c_rand": lz(run_eca_random(r, rng)), "c_single": lz(run_eca_single(r))})
    with open(os.path.join(HERE, "derived", "table_eca.csv"), "w") as f:
        f.write("rule,anf_monomials,min_gates,lzma_random,lzma_single\n")
        for e in eca:
            f.write(f"{e['rule']},{e['anf']},{e['gates']},{e['c_rand']},{e['c_single']}\n")

    tot = []
    for code in range(2187):
        t = tot3_table(code)
        mode = Counter(t.tolist()).most_common(1)[0][1]
        tot.append({"code": code, "entropy": entropy_bits(t), "nondefault": 7 - mode,
                    "c_rand": lz(run_tot3_random(code, rng)), "c_single": lz(run_tot3_single(code))})
    with open(os.path.join(HERE, "derived", "table_tot3.csv"), "w") as f:
        f.write("code,table_entropy_bits,nondefault_entries,lzma_random,lzma_single\n")
        for e in tot:
            f.write(f"{e['code']},{e['entropy']:.4f},{e['nondefault']},{e['c_rand']},{e['c_single']}\n")

    # Spearman correlations
    rho = {}
    for fam, rows, rmeas in (("F1", eca, ("anf", "gates")), ("F2", tot, ("entropy", "nondefault"))):
        for rm in rmeas:
            for bm in ("c_rand", "c_single"):
                x = [e[rm] for e in rows]
                y = [e[bm] for e in rows]
                rho[f"{fam}:{rm}~{bm}"] = float(spearmanr(x, y).statistic)
    max_rho = max(rho.values())

    # Counterexamples
    counter = {}
    for fam, rows, rmeas in (("F1", eca, ("anf", "gates")), ("F2", tot, ("entropy", "nondefault"))):
        cr = np.array([e["c_rand"] for e in rows])
        q1, q3 = np.percentile(cr, 25), np.percentile(cr, 75)
        key = "rule" if fam == "F1" else "code"
        for rm in rmeas:
            vals = np.array([e[rm] for e in rows])
            lo_rules = [rows[i] for i in np.nonzero(vals == vals.min())[0] if cr[i] >= q3]
            hi_rules = [rows[i] for i in np.nonzero(vals == vals.max())[0] if cr[i] <= q1]
            counter[f"{fam}:{rm}"] = {
                "min_rule_complexity": float(vals.min()), "max_rule_complexity": float(vals.max()),
                "simple_rules_with_top_quartile_behaviour": [e[key] for e in lo_rules][:20],
                "n_simple_top": len(lo_rules),
                "complex_rules_with_bottom_quartile_behaviour": [e[key] for e in hi_rules][:20],
                "n_complex_bottom": len(hi_rules),
            }
    simple_top_ok = all(v["n_simple_top"] > 0 for v in counter.values())
    complex_bottom_ok = all(v["n_complex_bottom"] > 0 for v in counter.values())

    # Hamming-1 neighbours in F1
    cr = np.array([e["c_rand"] for e in eca])
    rng_c = cr.max() - cr.min()
    pairs = [(r, r ^ (1 << k)) for r in range(256) for k in range(8) if r < r ^ (1 << k)]
    big = [(a, b) for a, b in pairs if abs(int(cr[a]) - int(cr[b])) > 0.5 * rng_c]
    frac_big = len(big) / len(pairs)

    summary = {"spearman": rho, "max_rho": max_rho, "counterexamples": counter,
               "hamming1_pairs": len(pairs), "hamming1_big_difference": len(big),
               "hamming1_fraction": frac_big, "hamming1_examples": big[:20],
               "eca_c_rand_range": [int(cr.min()), int(cr.max())]}
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    if max_rho >= 0.6 or not simple_top_ok:
        verdict = "refutes"
    elif max_rho <= 0.3 and simple_top_ok and complex_bottom_ok and frac_big >= 0.05:
        verdict = "supports"
    else:
        verdict = "mixed"
    measured = {
        "value": {"max_spearman_rho": round(max_rho, 3), "hamming1_fraction_big_difference": round(frac_big, 4)},
        "unit": "Spearman rho (rule complexity vs lzma size); fraction of 1024 Hamming-1 ECA pairs differing by > half the range",
        "n": {"F1_rules": 256, "F2_codes": 2187, "hamming1_pairs": len(pairs)},
        "uncertainty": "single random initial condition per rule (seed 20260720); lzma sizes in bytes",
        "extra": {"spearman": {k: round(v, 3) for k, v in rho.items()},
                  "simple_rules_with_top_quartile_behaviour": {k: v["simple_rules_with_top_quartile_behaviour"] for k, v in counter.items()},
                  "complex_rules_with_bottom_quartile_behaviour": {k: v["complex_rules_with_bottom_quartile_behaviour"] for k, v in counter.items()},
                  "hamming1_examples": big[:10],
                  "eca_lzma_random_range_bytes": [int(cr.min()), int(cr.max())]},
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
