#!/usr/bin/env python3
"""wolfram2002-ch06-15: additivity of rule 90 and persistence of a low initial density
(rule 90) versus loss of memory (rule 22).  Deterministic; prints JSON to stdout.

Parts (see result.json pass_criterion):
  A  exhaustive linearity check of the local rules 90 and 22 over GF(2)
  B  exact superposition of shifted single-cell evolutions on random cyclic configurations
  C  nested structure of the rule-90 single-cell pattern (Pascal mod 2)
  D  rule 90: density at t = 2^k versus 2p(1-p) for Bernoulli(p) initial conditions
  E  rule 22: late-time density independent of p
"""
import json
import sys

import numpy as np

STEPS = 1024
WINDOW = 100000
PAD = STEPS
PS_90 = [0.05, 0.1, 0.2]
PS_22 = [0.05, 0.1, 0.2, 0.5]
SEEDS = {0.05: 100, 0.1: 101, 0.2: 102, 0.5: 103}


def table(rule):
    return np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)


def step_cyclic(x, tab):
    idx = (np.roll(x, 1).astype(np.intp) << 2) | (x.astype(np.intp) << 1) | np.roll(x, -1).astype(np.intp)
    return tab[idx]


def step_open(x, tab):
    """Zero boundary; cells at the array edges are kept 0 (they are padding)."""
    idx = (x[:-2].astype(np.intp) << 2) | (x[1:-1].astype(np.intp) << 1) | x[2:].astype(np.intp)
    y = np.zeros_like(x)
    y[1:-1] = tab[idx]
    return y


def part_a():
    out = {}
    for rule in (90, 22):
        tab = table(rule)
        fails = 0
        for a in range(8):
            for b in range(8):
                if tab[a ^ b] != tab[a] ^ tab[b]:
                    fails += 1
        out["rule%d" % rule] = {"pairs": 64, "linearity_failures": int(fails), "additive": fails == 0}
    return out


def part_b():
    tab = table(90)
    W, T, N = 513, 256, 50
    single = np.zeros((T + 1, W), np.uint8)
    single[0, 0] = 1
    for t in range(T):
        single[t + 1] = step_cyclic(single[t], tab)
    rows = 0
    equal = 0
    for seed in range(N):
        rng = np.random.default_rng(seed)
        x0 = rng.integers(0, 2, W).astype(np.uint8)
        sup = np.zeros((T + 1, W), np.uint8)
        for i in np.flatnonzero(x0):
            sup ^= np.roll(single, int(i), axis=1)
        x = x0.copy()
        for t in range(T + 1):
            rows += 1
            equal += int(np.array_equal(x, sup[t]))
            x = step_cyclic(x, tab)
    return {"n_configurations": N, "width": W, "steps": T, "rows_compared": rows, "rows_equal": equal,
            "exact_superposition": rows == equal}


def part_c():
    tab = table(90)
    W = 2 * STEPS + 3  # one extra padding cell each side: step_open keeps the edge cells 0
    x = np.zeros(W, np.uint8)
    x[STEPS + 1] = 1
    counts = {}
    for t in range(STEPS + 1):
        counts[t] = int(x.sum())
        x = step_open(x, tab)
    ok = True
    rows = []
    for k in range(11):
        t = 2 ** k
        c_t, c_tm1 = counts[t], counts[t - 1]
        rows.append({"k": k, "t": t, "black_at_t": c_t, "black_at_t_minus_1": c_tm1, "expected": [2, 2 ** k]})
        ok &= (c_t == 2 and c_tm1 == 2 ** k)
    return {"rows": rows, "nested_counts_exact": ok}


def density_runs(rule, ps):
    tab = table(rule)
    out = {}
    for p in ps:
        rng = np.random.default_rng(SEEDS[p])
        x = (rng.random(WINDOW + 2 * PAD) < p).astype(np.uint8)
        dens = np.empty(STEPS + 1)
        for t in range(STEPS + 1):
            dens[t] = x[PAD:PAD + WINDOW].mean()
            if t < STEPS:
                x = step_open(x, tab)
        out[p] = dens
    return out


def part_d(d90):
    rows = []
    ok = True
    for p in PS_90:
        for k in range(11):
            t = 2 ** k
            expected = 2 * p * (1 - p)
            d = float(d90[p][t])
            rows.append({"p": p, "k": k, "t": t, "density": round(d, 5), "expected_2p(1-p)": round(expected, 5),
                         "abs_dev": round(abs(d - expected), 5)})
            ok &= abs(d - expected) < 0.01
    d_half = float(d90[0.5][STEPS])
    diffs = {str(p): round(abs(float(d90[p][STEPS]) - d_half), 5) for p in PS_90}
    all_far = all(v > 0.1 for v in diffs.values())
    return {"rows": rows, "all_within_0.01": ok, "density_p0.5_at_1024": round(d_half, 5),
            "abs_diff_from_p0.5_at_1024": diffs, "all_differ_by_more_than_0.1": all_far,
            "refutation_check_p0.1_within_0.05_of_p0.5": diffs["0.1"] < 0.05,
            "density_series_t_2k": {str(p): [round(float(d90[p][2 ** k]), 5) for k in range(11)] for p in PS_90 + [0.5]}}


def part_e(d22):
    late = {str(p): round(float(d22[p][512:STEPS + 1].mean()), 5) for p in PS_22}
    spread = max(late.values()) - min(late.values())
    sampled = {str(p): [round(float(d22[p][t]), 5) for t in (0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)] for p in PS_22}
    return {"late_time_mean_density_t512_1024": late, "spread": round(spread, 5), "spread_below_0.01": spread < 0.01,
            "refutation_check_spread_above_0.05": spread > 0.05, "density_at_sampled_times": sampled}


def main():
    out = {"params": {"steps": STEPS, "window": WINDOW, "pad": PAD, "seeds": {str(k): v for k, v in SEEDS.items()}}}
    out["A_additivity"] = part_a()
    out["B_superposition"] = part_b()
    out["C_single_cell_nested"] = part_c()
    d90 = density_runs(90, PS_90 + [0.5])
    d22 = density_runs(22, PS_22)
    out["D_rule90_density_persistence"] = part_d(d90)
    out["E_rule22_density_memory_loss"] = part_e(d22)
    a_ok = out["A_additivity"]["rule90"]["additive"] and not out["A_additivity"]["rule22"]["additive"]
    b_ok = out["B_superposition"]["exact_superposition"]
    c_ok = out["C_single_cell_nested"]["nested_counts_exact"]
    d = out["D_rule90_density_persistence"]
    e = out["E_rule22_density_memory_loss"]
    d_ok = d["all_within_0.01"] and d["all_differ_by_more_than_0.1"]
    e_ok = e["spread_below_0.01"]
    if a_ok and b_ok and c_ok and d_ok and e_ok:
        verdict = "supports"
    elif (not out["A_additivity"]["rule90"]["additive"]) or (not b_ok) or d["refutation_check_p0.1_within_0.05_of_p0.5"] \
            or e["refutation_check_spread_above_0.05"]:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["criteria"] = {"A": a_ok, "B": b_ok, "C": c_ok, "D": d_ok, "E": e_ok}
    out["verdict"] = verdict
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
