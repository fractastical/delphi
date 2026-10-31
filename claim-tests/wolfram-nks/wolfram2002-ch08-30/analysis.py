#!/usr/bin/env python3
"""Test of wolfram2002-ch08-30: ECA market model, information propagation vs randomness of running totals.

Run: python3 analysis.py   (writes derived/rules.csv, prints measured block)
"""
import csv
import json
import lzma
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N_RING = 400
TRANSIENT = 1000
W = 4096
N_OPEN = 1601
T_DAMAGE = 400
WIDTH_MIN = 100
TRIALS = 20
TRIALS_MIN = 10
RATIO_MIN = 0.5
H_MIN = 1.0
SEED_IC = 20261031
SEED_DAMAGE = 20261032


def rule_table(rule):
    return np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)


def step_ring(x, table):
    idx = (np.roll(x, 1) << 2) | (x << 1) | np.roll(x, -1)
    return table[idx]


def step_open(x, table):
    """Open lattice: outside cells are treated as copies of the edge (never reached by the damage)."""
    left = np.concatenate(([x[0]], x[:-1]))
    right = np.concatenate((x[1:], [x[-1]]))
    return table[(left << 2) | (x << 1) | right]


def damage_width(rule, rng):
    table = rule_table(rule)
    widths = []
    for _ in range(TRIALS):
        a = rng.integers(0, 2, N_OPEN, dtype=np.uint8)
        b = a.copy()
        b[N_OPEN // 2] ^= 1
        for _ in range(T_DAMAGE):
            a = step_open(a, table)
            b = step_open(b, table)
        diff = np.flatnonzero(a != b)
        widths.append(int(diff[-1] - diff[0] + 1) if diff.size else 0)
    return widths


def price_series(rule, rng):
    table = rule_table(rule)
    x = rng.integers(0, 2, N_RING, dtype=np.uint8)
    for _ in range(TRANSIENT):
        x = step_ring(x, table)
    d = np.empty(W, dtype=np.int64)
    for t in range(W):
        x = step_ring(x, table)
        s = int(x.sum())
        d[t] = 2 * s - N_RING
    return d


def is_periodic(d):
    n = len(d)
    for p in range(1, n // 2 + 1):
        if np.array_equal(d[p:], d[:-p]):
            return p
    return 0


def randomness(d):
    D = np.diff(d).astype(np.int16)
    _, counts = np.unique(D, return_counts=True)
    p = counts / counts.sum()
    H = float(-(p * np.log2(p)).sum())
    comp = lzma.compress(D.tobytes(), preset=9 | lzma.PRESET_EXTREME)
    bps = 8.0 * len(comp) / len(D)
    ratio = bps / H if H > 0 else 0.0
    return H, bps, ratio


def main():
    t0 = time.time()
    rng_ic = np.random.default_rng(SEED_IC)
    rng_dmg = np.random.default_rng(SEED_DAMAGE)
    rows = []
    for rule in range(256):
        widths = damage_width(rule, rng_dmg)
        n_prop = sum(w >= WIDTH_MIN for w in widths)
        propagating = n_prop >= TRIALS_MIN
        d = price_series(rule, rng_ic)
        period = is_periodic(d)
        H, bps, ratio = randomness(d)
        random_ok = (period == 0) and H >= H_MIN and ratio >= RATIO_MIN
        rows.append({
            "rule": rule, "median_damage_width": float(np.median(widths)), "max_damage_width": max(widths),
            "trials_width_ge_100": n_prop, "propagating": propagating,
            "d_std": round(float(d.std()), 2), "period": period, "H_increments_bits": round(H, 3),
            "lzma_bits_per_sample": round(bps, 3), "ratio": round(ratio, 3), "significantly_random": bool(random_ok),
        })
        if rule % 32 == 31:
            print(f"rule {rule} done ({time.time()-t0:.0f}s)", file=sys.stderr)

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "rules.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    prop = [r for r in rows if r["propagating"]]
    nonprop = [r for r in rows if not r["propagating"]]
    prop_random = [r for r in prop if r["significantly_random"]]
    nonprop_random = [r for r in nonprop if r["significantly_random"]]
    measured = {
        "value": round(len(prop_random) / len(prop), 4) if prop else None,
        "unit": "fraction of propagating rules whose black-minus-white series is significantly random",
        "n": len(prop),
        "uncertainty": None,
        "extra": {
            "propagating_rules": [r["rule"] for r in prop],
            "propagating_not_random": [(r["rule"], r["period"], r["H_increments_bits"], r["ratio"]) for r in prop if not r["significantly_random"]],
            "nonpropagating_rules_n": len(nonprop),
            "nonpropagating_random_fraction": round(len(nonprop_random) / len(nonprop), 4) if nonprop else None,
            "nonpropagating_random_rules": [(r["rule"], r["median_damage_width"], r["ratio"]) for r in nonprop_random],
            "rule_90": next(r for r in rows if r["rule"] == 90),
            "params": {"N_ring": N_RING, "transient": TRANSIENT, "W": W, "N_open": N_OPEN, "T_damage": T_DAMAGE,
                       "width_min": WIDTH_MIN, "trials": TRIALS, "trials_min": TRIALS_MIN},
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    print(json.dumps(measured, indent=2, default=str))


if __name__ == "__main__":
    main()
