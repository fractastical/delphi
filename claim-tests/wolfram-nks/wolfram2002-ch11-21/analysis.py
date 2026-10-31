#!/usr/bin/env python3
"""Test of wolfram2002-ch11-21: scaled census of rule 54 from initial conditions 1..65536.

Run: python3 analysis.py   (writes derived/census.csv.gz and derived/summary.json, prints measured block; ~4 min)
"""
import csv
import gzip
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RULE = 54
N_MAX = 65536
T = 256
K = 6
ROW0, ROW1 = T // 2, T + 1          # tiles with top-left rows in [T/2, T-K]
THETA = 1050
THETA_STRICT = 700
P_MAX = 16
BOOK_EXAMPLES = [1, 3, 75, 259, 291, 787, 803, 56549]


def table(rule):
    return np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)


def evolve_batch(rule, inits, steps):
    """inits (B, L) -> space-time (B, steps+1, L + 2*steps); background white; the cone never reaches the edge."""
    tb = table(rule)
    B, L = inits.shape
    W = L + 2 * steps
    x = np.zeros((B, W), dtype=np.uint8)
    x[:, steps:steps + L] = inits
    st = np.empty((B, steps + 1, W), dtype=np.uint8)
    st[:, 0] = x
    for t in range(1, steps + 1):
        idx = (np.roll(x, 1, axis=1).astype(np.int16) << 2) | (x.astype(np.int16) << 1) | np.roll(x, -1, axis=1)
        x = tb[idx]
        st[:, t] = x
    return st


def tile_count(st, t0, t1, k=K):
    """Distinct k x k tiles with top-left in rows t0..t1-k, restricted to the light cone (+2 cells)."""
    W = st.shape[1]
    c = W // 2
    sub = st[t0:t1].astype(np.int64)
    R = sub.shape[0] - k + 1
    C = W - k + 1
    code = np.zeros((R, C), dtype=np.int64)
    for i in range(k):
        for j in range(k):
            code |= sub[i:i + R, j:j + C] << (k * i + j)
    r = np.arange(R)[:, None]
    x = np.arange(C)[None, :]
    t = t0 + r
    mask = (x >= c - t - 2) & (x + k - 1 <= c + t + 2)
    return int(np.unique(code[mask]).size)


def core_period(st, t0, pmax=P_MAX):
    """Smallest p <= pmax such that rows t and t+p agree on the light cone of row t for all t in [t0, T-p]; 0 if none."""
    Tt = st.shape[0] - 1
    W = st.shape[1]
    c = W // 2
    for p in range(1, pmax + 1):
        ok = True
        for t in range(t0, Tt - p + 1):
            lo, hi = c - t - 1, c + t + 2
            if not np.array_equal(st[t, lo:hi], st[t + p, lo:hi]):
                ok = False
                break
        if ok:
            return p
    return 0


def ic_bits(n, L):
    return np.array([(n >> (L - 1 - i)) & 1 for i in range(L)], dtype=np.uint8)


def main():
    t0 = time.time()
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    rows = []
    batch = 512
    for L in range(1, 17):
        ns = np.arange(1 << (L - 1), min(1 << L, N_MAX + 1))
        for s in range(0, len(ns), batch):
            chunk = ns[s:s + batch]
            inits = ((chunk[:, None] >> (L - 1 - np.arange(L))[None, :]) & 1).astype(np.uint8)
            st = evolve_batch(RULE, inits, T)
            for b, n in enumerate(chunk):
                D = tile_count(st[b], ROW0, ROW1)
                p = core_period(st[b], T // 2) if D <= 400 else 0  # periodicity only checked for low-complexity patterns
                rows.append({"n": int(n), "bits": L, "tiles": D, "period": p})
        print(f"  L={L} done, n <= {ns[-1]} ({time.time()-t0:.0f}s)", file=sys.stderr)

    tiles = np.array([r["tiles"] for r in rows])
    above = [r for r in rows if r["tiles"] > THETA]
    above_strict = [r for r in rows if r["tiles"] > THETA_STRICT]
    # T = 512 re-run for anything above threshold (and for the 20 largest-D initial conditions, reported)
    order = np.argsort(-tiles)
    recheck_ns = sorted(set([r["n"] for r in above] + [rows[i]["n"] for i in order[:20]]))
    recheck = []
    for n in recheck_ns:
        L = n.bit_length()
        st = evolve_batch(RULE, ic_bits(n, L)[None, :], 512)[0]
        recheck.append({"n": int(n), "tiles_T256": int(tiles[n - 1]), "tiles_T512_rows_256_512": tile_count(st, 256, 513)})
    sustained = [r for r in recheck if r["tiles_T256"] > THETA and r["tiles_T512_rows_256_512"] > THETA]

    with gzip.open(os.path.join(HERE, "derived", "census.csv.gz"), "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["n", "bits", "tiles", "period"])
        w.writeheader()
        w.writerows(rows)
    periodic = int(sum(1 for r in rows if r["period"] > 0))
    hist = {str(int(b)): int(c) for b, c in zip(*np.unique(np.minimum(tiles // 100, 20) * 100, return_counts=True))}
    book = {str(n): tiles[n - 1] for n in BOOK_EXAMPLES if n <= N_MAX}
    measured = {
        "value": len(above),
        "unit": "number of initial conditions n <= 65536 whose rule-54 pattern has more than 1050 distinct 6x6 tiles in steps 128-256",
        "n": len(rows),
        "uncertainty": None,
        "extra": {
            "above_theta_1050": [(r["n"], r["tiles"]) for r in above[:50]],
            "above_theta_700_count": len(above_strict),
            "above_theta_700_examples": [(r["n"], r["tiles"]) for r in above_strict[:30]],
            "sustained_above_1050_at_T512": [(r["n"], r["tiles_T256"], r["tiles_T512_rows_256_512"]) for r in sustained],
            "recheck_T512_top20": recheck,
            "max_tiles": int(tiles.max()),
            "argmax_n": int(rows[int(order[0])]["n"]),
            "median_tiles": float(np.median(tiles)),
            "tiles_histogram_by_100": hist,
            "exactly_periodic_core_fraction": round(periodic / len(rows), 4),
            "period_distribution": {str(int(p)): int(c) for p, c in zip(*np.unique([r["period"] for r in rows], return_counts=True))},
            "book_examples_tiles": {k: int(v) for k, v in book.items()},
            "params": {"T": T, "K": K, "rows": [ROW0, ROW1 - 1], "theta": THETA, "theta_strict": THETA_STRICT, "N_max": N_MAX},
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(measured, f, indent=1, default=str)
    print(json.dumps(measured, indent=2, default=str))


if __name__ == "__main__":
    main()
