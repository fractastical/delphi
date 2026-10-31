#!/usr/bin/env python3
"""wolfram2002-ch07-07: maximal-period linear congruential generators show strong non-randomness.

  1  exact lattice structure of consecutive d-tuples (dual-lattice shortest vectors, d = 2..4)
  2  visibility at 2^20 samples: number of distinct values of the projection onto the worst dual vector
  3  two-dimensional birthday-spacings test (L'Ecuyer and Simard 2001 setting) versus os.urandom
Deterministic except for the os.urandom baseline.  Prints JSON to stdout.
"""
import json
import math
import os
import sys
from fractions import Fraction

import numpy as np
from scipy.stats import poisson

GENERATORS = [
    # name, a, c, m, note
    ("RANDU", 65539, 0, 2 ** 31, "IBM System/360; multiplicative, period 2^29 (maximal for its class)"),
    ("ANSI C example rand / glibc", 1103515245, 12345, 2 ** 31, "ISO C standard portable example; full period"),
    ("Numerical Recipes ranqd1", 1664525, 1013904223, 2 ** 32, "Knuth and H. W. Lewis parameters; full period"),
    ("Borland C/C++", 22695477, 1, 2 ** 32, "full period"),
    ("VAX MTH$RANDOM / old glibc", 69069, 1, 2 ** 32, "Marsaglia's 69069; full period"),
    ("Park-Miller minimal standard", 16807, 0, 2 ** 31 - 1, "prime modulus, primitive root; period m-1"),
    ("C++11 minstd_rand", 48271, 0, 2 ** 31 - 1, "prime modulus, primitive root; period m-1"),
    ("POSIX drand48 / java.util.Random", 25214903917, 11, 2 ** 48, "full period"),
    ("Knuth MMIX (contrast)", 6364136223846793005, 1442695040888963407, 2 ** 64, "full period; chosen with the spectral test"),
]
HISTORICAL = 8
N_PROJ = 2 ** 20
BD_N, BD_BITS, BD_REPS = 2 ** 15, 21, 32
SEED = 12345


# ---------------------------------------------------------------- lattice tools
def lll(basis, delta=Fraction(3, 4)):
    """Exact LLL on integer row vectors (small dimension)."""
    B = [list(map(int, b)) for b in basis]
    n = len(B)

    def gso():
        Bs = []
        mu = [[Fraction(0)] * n for _ in range(n)]
        for i in range(n):
            v = [Fraction(x) for x in B[i]]
            for j in range(i):
                mu[i][j] = sum(Fraction(B[i][k]) * Bs[j][k] for k in range(n)) / sum(x * x for x in Bs[j])
                v = [v[k] - mu[i][j] * Bs[j][k] for k in range(n)]
            Bs.append(v)
        return Bs, mu

    Bs, mu = gso()
    k = 1
    while k < n:
        for j in range(k - 1, -1, -1):
            q = round(mu[k][j])
            if q:
                B[k] = [B[k][i] - q * B[j][i] for i in range(n)]
                Bs, mu = gso()
        nk = sum(x * x for x in Bs[k])
        nk1 = sum(x * x for x in Bs[k - 1])
        if nk >= (delta - mu[k][k - 1] ** 2) * nk1:
            k += 1
        else:
            B[k], B[k - 1] = B[k - 1], B[k]
            Bs, mu = gso()
            k = max(k - 1, 1)
    return B


def enumerate_short(B, bound_sq):
    """All nonzero lattice vectors with squared L2 norm <= bound_sq (Fincke-Pohst)."""
    n = len(B)
    Bf = np.array(B, dtype=float)
    # Gram-Schmidt
    Bs = np.zeros((n, n))
    mu = np.zeros((n, n))
    for i in range(n):
        Bs[i] = Bf[i]
        for j in range(i):
            mu[i, j] = Bf[i] @ Bs[j] / (Bs[j] @ Bs[j])
            Bs[i] -= mu[i, j] * Bs[j]
    c = np.array([Bs[i] @ Bs[i] for i in range(n)])
    out = []
    x = [0] * n

    def rec(i, remaining):
        if i < 0:
            v = [sum(x[j] * B[j][k] for j in range(n)) for k in range(n)]
            if any(v):
                out.append(v)
            return
        centre = -sum(x[j] * mu[j, i] for j in range(i + 1, n))
        r = math.sqrt(max(remaining, 0) / c[i]) + 1e-9
        for xi in range(math.ceil(centre - r), math.floor(centre + r) + 1):
            x[i] = xi
            rec(i - 1, remaining - (xi - centre) ** 2 * c[i])
        x[i] = 0

    rec(n - 1, bound_sq * (1 + 1e-9))
    return out


def dual_lattice_minima(a, m, d):
    basis = [[m] + [0] * (d - 1)]
    for i in range(1, d):
        row = [0] * d
        row[0] = -pow(a, i, m)
        row[i] = 1
        basis.append(row)
    red = lll(basis)
    l1_bound = min(sum(abs(x) for x in v) for v in red)
    cands = enumerate_short(red, l1_bound ** 2)  # L2 <= L1 of best LLL vector covers the L1 minimiser
    l2min = min(sum(x * x for x in v) for v in cands)
    l1min_vec = min(cands, key=lambda v: (sum(abs(x) for x in v), v))
    return {"nu_squared": int(l2min), "nu": math.sqrt(l2min), "hyperplanes_L1": int(sum(abs(x) for x in l1min_vec)),
            "dual_vector": l1min_vec, "marsaglia_bound": (math.factorial(d) * m) ** (1 / d)}


# ---------------------------------------------------------------- generators
def lcg_stream(a, c, m, seed, n):
    x = seed % m
    out = np.empty(n, dtype=object)
    for i in range(n):
        x = (a * x + c) % m
        out[i] = x
    return out


def projection_distinct_fast(xs_int, m, u, n):
    # exact: s = u.x is an integer; (s / m) rounded to 1e-9 -> represent as round(s * 1e9 / m)
    vals = set()
    for i in range(n - 2):
        s = u[0] * int(xs_int[i]) + u[1] * int(xs_int[i + 1]) + u[2] * int(xs_int[i + 2])
        vals.add((s * 10 ** 9) // m if s >= 0 else -((-s * 10 ** 9) // m))
    return len(vals)


def birthday_collisions(points_2d_int, bits):
    """points: integer cell indices in [0, 2^(2 bits)); returns number of collisions among sorted spacings."""
    I = np.sort(points_2d_int)
    sp = np.sort(np.diff(I))
    return int(sp.size - np.unique(sp).size)


def birthday_test(get_values, m, reps=BD_REPS, n=BD_N, bits=BD_BITS):
    total = 0
    per = []
    for r in range(reps):
        xs = get_values(r, 2 * n)
        hi = np.array([int(v) * (1 << bits) // m for v in xs], dtype=np.int64)
        cells = hi[0::2] * (1 << bits) + hi[1::2]
        cnt = birthday_collisions(cells, bits)
        per.append(cnt)
        total += cnt
    lam = reps * n ** 3 / (4.0 * 2 ** (2 * bits))
    cdf = poisson.cdf(total, lam)
    sf = poisson.sf(total - 1, lam)
    p = float(min(1.0, 2 * min(cdf, sf)))
    return {"total_collisions": total, "expected": lam, "per_replication": per, "p_two_sided": p}


def urandom_values(n, bits=64):
    raw = os.urandom(8 * n)
    return np.frombuffer(raw, dtype=np.uint64).astype(object)


def main():
    out = {"generators": [], "n_projection": N_PROJ,
           "birthday": {"n_points": BD_N, "bits_per_coordinate": BD_BITS, "replications": BD_REPS}}
    for idx, (name, a, c, m, note) in enumerate(GENERATORS):
        rec = {"name": name, "a": a, "c": c, "m": m, "log2_m": math.log2(m), "note": note, "lattice": {}}
        for d in (2, 3, 4):
            L = dual_lattice_minima(a, m, d)
            L["normalised_spectral_S"] = L["nu"] / ({2: (4 / 3) ** 0.25, 3: 2 ** (1 / 6), 4: 2 ** 0.25}[d] * m ** (1 / d))
            rec["lattice"][str(d)] = L
        seed = SEED | 1 if c == 0 else SEED
        xs = lcg_stream(a, c, m, seed, N_PROJ)
        u = rec["lattice"]["3"]["dual_vector"]
        rec["projection_distinct_values"] = projection_distinct_fast(xs, m, u, N_PROJ)
        rec["projection_distinct_fraction"] = rec["projection_distinct_values"] / N_PROJ
        if m <= 2 ** 48:
            rec["birthday"] = birthday_test(lambda r, n: lcg_stream(a, c, m, (2 * r + 1) if c == 0 else (r + 1), n), m)
        else:
            rec["birthday"] = birthday_test(lambda r, n: lcg_stream(a, c, m, r + 1, n), m)
        out["generators"].append(rec)
        print(name, "done", file=sys.stderr)
    # cryptographic baseline under the same statistics (projection uses the RANDU dual vector and 2^64 scale)
    xs = urandom_values(N_PROJ)
    base = {"name": "os.urandom (64-bit words)", "projection_vectors": {}}
    for rec in out["generators"][:HISTORICAL]:
        u = rec["lattice"]["3"]["dual_vector"]
        base["projection_vectors"][rec["name"]] = projection_distinct_fast(xs, 2 ** 64, u, N_PROJ) / N_PROJ
    base["projection_distinct_fraction_min"] = min(base["projection_vectors"].values())
    base["birthday"] = birthday_test(lambda r, n: urandom_values(n), 2 ** 64)
    out["baseline"] = base

    hist = out["generators"][:HISTORICAL]
    small = [g for g in hist if g["m"] <= 2 ** 32]
    crit1 = all(g["lattice"]["3"]["hyperplanes_L1"] <= 3000 and g["lattice"]["2"]["hyperplanes_L1"] <= 93000 for g in small)
    crit2 = all(g["projection_distinct_values"] <= 3000 for g in small) and base["projection_distinct_fraction_min"] >= 0.99
    n_fail = sum(1 for g in hist if g["birthday"]["p_two_sided"] < 1e-6)
    mmix = out["generators"][-1]
    crit3 = bool(n_fail >= 6 and base["birthday"]["p_two_sided"] > 1e-3 and mmix["birthday"]["p_two_sided"] > 1e-3)
    refute = (not crit1) or any(g["projection_distinct_fraction"] > 0.5 for g in small) or n_fail < 3
    out["criteria"] = {"1_lattice": crit1, "2_visible": crit2, "3_birthday": crit3, "historical_failing_birthday": n_fail}
    out["verdict"] = "supports" if (crit1 and crit2 and crit3) else ("refutes" if refute else "mixed")
    json.dump(out, sys.stdout, indent=1, default=str)
    print()


if __name__ == "__main__":
    main()
