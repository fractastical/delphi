#!/usr/bin/env python3
"""Test of wolfram2002-ch06-17: spatially periodic initial conditions (a block of n
cells repeated forever) always give repetitive behaviour with period at most k^n.

Part 1 (period bound): for each rule family, every block of n cells is treated as an
n-cell ring; the ring's transition map on all k^n states is built and the eventual
period of every state's orbit computed. Count violations of period <= k^n.
  - all 256 ECA, n = 1..12 (k = 2)
  - all 2187 three-colour totalistic nearest-neighbour rules, n = 1..6 (k = 3)
  - 500 random range-2 binary rules (seeded), n = 1..10 (k = 2)
Part 2 (reduction check): for all 256 ECA and all blocks with n = 1..6, a long line of
repeated copies of the block (white ends) is evolved and the central copy compared with
the ring evolution at every step.

Run: python3 analysis.py   (needs numpy)
"""
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def orbit_periods(f):
    """Eventual period of every state's orbit under the map f (int array)."""
    f = np.asarray(f, dtype=np.int64)
    N = len(f)
    indeg = np.bincount(f, minlength=N)
    on_cycle = np.ones(N, dtype=bool)
    stack = list(np.nonzero(indeg == 0)[0])
    while stack:
        v = stack.pop()
        on_cycle[v] = False
        w = f[v]
        indeg[w] -= 1
        if indeg[w] == 0:
            stack.append(w)
    period = np.zeros(N, dtype=np.int64)
    seen = np.zeros(N, dtype=bool)
    for v in np.nonzero(on_cycle)[0]:
        if seen[v]:
            continue
        cyc = [v]
        seen[v] = True
        w = f[v]
        while w != v:
            cyc.append(w)
            seen[w] = True
            w = f[w]
        period[cyc] = len(cyc)
    pending = ~on_cycle
    while pending.any():
        ready = pending & (period[f] > 0)
        period[ready] = period[f[ready]]
        pending &= ~ready
    return period


def ring_states(k, n):
    N = k ** n
    states = np.arange(N, dtype=np.int64)
    digits = np.zeros((N, n), dtype=np.int64)
    s = states.copy()
    for i in range(n):
        digits[:, i] = s % k
        s //= k
    return digits


def pack(digits, k):
    n = digits.shape[1]
    return (digits * (k ** np.arange(n))).sum(axis=1)


def eca_ring_map(rule, digits):
    left = np.roll(digits, 1, axis=1)
    right = np.roll(digits, -1, axis=1)
    rule_bits = (rule >> np.arange(8)) & 1
    return pack(rule_bits[4 * left + 2 * digits + right], 2)


def tot3_ring_map(code, digits):
    left = np.roll(digits, 1, axis=1)
    right = np.roll(digits, -1, axis=1)
    s = left + digits + right  # 0..6
    code_digits = np.array([(code // 3 ** j) % 3 for j in range(7)], dtype=np.int64)
    return pack(code_digits[s], 3)


def range2_ring_map(rule, digits):
    l2 = np.roll(digits, 2, axis=1)
    l1 = np.roll(digits, 1, axis=1)
    r1 = np.roll(digits, -1, axis=1)
    r2 = np.roll(digits, -2, axis=1)
    idx = 16 * l2 + 8 * l1 + 4 * digits + 2 * r1 + r2
    rule_bits = (rule >> np.arange(32, dtype=np.int64)) & 1
    return pack(rule_bits[idx], 2)


def check_family(name, k, sizes, rules, ring_map):
    t0 = time.time()
    pairs = 0
    violations = 0
    max_ratio = 0.0
    max_at = None
    hist_ratio_bins = np.zeros(10, dtype=np.int64)  # period / k^n in [0,0.1), ... [0.9,1.0]
    for n in sizes:
        digits = ring_states(k, n)
        N = k ** n
        for r in rules:
            per = orbit_periods(ring_map(r, digits))
            pairs += N
            violations += int((per > N).sum())
            pm = int(per.max())
            if pm / N > max_ratio:
                max_ratio, max_at = pm / N, {"rule": int(r), "n": n, "max_period": pm, "k^n": N}
            hist_ratio_bins += np.bincount(np.minimum((per * 10) // N, 9), minlength=10)
    return {"family": name, "k": k, "sizes": list(sizes), "rules": len(rules), "rule_block_pairs": pairs,
            "violations_period_gt_k_pow_n": violations,
            "max_period_over_k_pow_n": round(max_ratio, 6), "max_at": max_at,
            "histogram_period_over_k_pow_n_tenths": hist_ratio_bins.tolist(),
            "seconds": round(time.time() - t0, 1)}


def eca_line_step(row, rule_bits):
    l = np.concatenate(([0], row[:-1]))
    r = np.concatenate((row[1:], [0]))
    return rule_bits[4 * l + 2 * row + r]


def equivalence_check(sizes):
    t0 = time.time()
    pairs = 0
    bad_pairs = 0
    cells = 0
    for n in sizes:
        steps = 2 * (2 ** n)
        copies = 2 * steps // n + 6
        digits = ring_states(2, n)
        for rule in range(256):
            rule_bits = np.array([(rule >> j) & 1 for j in range(8)], dtype=np.int64)
            fmap = eca_ring_map(rule, digits)
            for b in range(2 ** n):
                block = digits[b]
                line = np.tile(block, copies)
                c0 = (copies // 2) * n  # start of the central copy
                state = b
                ok = True
                for _ in range(steps):
                    line = eca_line_step(line, rule_bits)
                    state = int(fmap[state])
                    cells += n
                    if not np.array_equal(line[c0:c0 + n], digits[state]):
                        ok = False
                        break
                pairs += 1
                if not ok:
                    bad_pairs += 1
    return {"sizes": list(sizes), "rule_block_pairs": pairs, "pairs_with_mismatch": bad_pairs,
            "cells_compared": cells, "seconds": round(time.time() - t0, 1)}


def main():
    rng = np.random.default_rng(20261031)
    range2_rules = rng.integers(0, 2 ** 32, size=500, dtype=np.int64)
    fams = [
        check_family("eca-repeated-blocks-n1-12", 2, range(1, 13), list(range(256)), eca_ring_map),
        check_family("totalistic-3colour-repeated-blocks-n1-6", 3, range(1, 7), list(range(3 ** 7)), tot3_ring_map),
        check_family("range2-binary-sample-repeated-blocks-n1-10", 2, range(1, 11), list(range2_rules), range2_ring_map),
    ]
    for f in fams:
        print(json.dumps(f, indent=1))
    eq = equivalence_check(range(1, 7))
    print(json.dumps(eq, indent=1))
    out = {
        "rule_block_pairs_total": sum(f["rule_block_pairs"] for f in fams),
        "violations_total": sum(f["violations_period_gt_k_pow_n"] for f in fams),
        "fraction_pairs_period_le_k_pow_n": 1.0 - sum(f["violations_period_gt_k_pow_n"] for f in fams) / sum(f["rule_block_pairs"] for f in fams),
        "families": fams,
        "line_vs_ring_equivalence": eq,
        "range2_sample_first_rules": [int(x) for x in range2_rules[:5]],
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "families"}, indent=1))


if __name__ == "__main__":
    main()
