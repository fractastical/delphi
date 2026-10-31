#!/usr/bin/env python3
"""Test of wolfram2002-ch04-02: digit arrays of m^t in base b (m, b in 2..9, t <= 3000).

Interior window: digit positions in [0.25 L, 0.75 L) of each row (L = row length, position 0 = least
significant digit). One byte per digit, rows concatenated, lzma-compressed.

Run: python3 analysis.py   (writes derived/pairs.csv, prints measured block)
"""
import csv
import json
import lzma
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 3000
MS = range(2, 10)
BS = range(2, 10)
COMPLEX_FRAC = 0.8
SIMPLE_FRAC = 0.1
FREQ_DEV_MAX = 0.02


def digits(x, b):
    out = []
    while x:
        x, r = divmod(x, b)
        out.append(r)
    return out  # least significant first


def is_power(m, b):
    p = b
    while p <= m:
        if p == m:
            return True
        p *= b
    return False


def shares_all_primes(m, b):
    """True if every prime factor of m divides b (so m^t ends in zeros in base b eventually, like 6^t in base 2? no: 6=2*3)."""
    def primes(n):
        s, p = set(), 2
        while p * p <= n:
            while n % p == 0:
                s.add(p)
                n //= p
            p += 1
        if n > 1:
            s.add(n)
        return s
    return primes(m) <= primes(b)


def analyse(m, b):
    buf = bytearray()
    x = 1
    for _ in range(T):
        x *= m
        d = digits(x, b)
        L = len(d)
        lo, hi = L // 4, (3 * L) // 4
        buf += bytes(d[lo:hi])
    n = len(buf)
    comp = lzma.compress(bytes(buf), preset=9 | lzma.PRESET_EXTREME)
    bits = 8.0 * len(comp) / n
    counts = np.bincount(np.frombuffer(bytes(buf), dtype=np.uint8), minlength=b)[:b] / n
    dev = float(np.max(np.abs(counts - 1.0 / b)))
    return n, bits, dev


def main():
    t0 = time.time()
    rows = []
    for m in MS:
        for b in BS:
            n, bits, dev = analyse(m, b)
            lg = math.log2(b)
            row = {
                "m": m, "b": b, "m_is_power_of_b": is_power(m, b), "m_primes_subset_of_b_primes": shares_all_primes(m, b),
                "interior_digits": n, "bits_per_digit": round(bits, 4), "log2_b": round(lg, 4),
                "ratio_to_entropy_bound": round(bits / lg, 4), "max_freq_deviation": round(dev, 5),
            }
            row["complex"] = bool(bits >= COMPLEX_FRAC * lg and dev <= FREQ_DEV_MAX)
            row["simple"] = bool(bits < SIMPLE_FRAC * lg)
            rows.append(row)
            print(f"m={m} b={b} n={n} bits/digit={bits:.4f} ({bits/lg:.3f} of bound) dev={dev:.4f} "
                  f"power={row['m_is_power_of_b']} complex={row['complex']} simple={row['simple']}", file=sys.stderr)
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "pairs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    trivial = [r for r in rows if r["m_is_power_of_b"]]
    nontrivial = [r for r in rows if not r["m_is_power_of_b"]]
    complex_nontrivial = [r for r in nontrivial if r["complex"]]
    measured = {
        "value": len(complex_nontrivial),
        "unit": "pairs (m,b) with m not a power of b whose interior digit array is 'complex' by the pre-registered criteria",
        "n": len(nontrivial),
        "uncertainty": None,
        "extra": {
            "trivial_pairs": [(r["m"], r["b"]) for r in trivial],
            "trivial_pairs_all_simple": all(r["simple"] for r in trivial),
            "trivial_bits_per_digit": {f"{r['m']}^t base {r['b']}": r["bits_per_digit"] for r in trivial},
            "nontrivial_not_complex": [(r["m"], r["b"], r["ratio_to_entropy_bound"], r["max_freq_deviation"]) for r in nontrivial if not r["complex"]],
            "min_ratio_nontrivial": min(r["ratio_to_entropy_bound"] for r in nontrivial),
            "max_freq_dev_nontrivial": max(r["max_freq_deviation"] for r in nontrivial),
            "example_3_base_2": next(r for r in rows if r["m"] == 3 and r["b"] == 2),
            "T": T,
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
