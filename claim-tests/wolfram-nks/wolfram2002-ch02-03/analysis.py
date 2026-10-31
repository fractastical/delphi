#!/usr/bin/env python3
"""wolfram2002-ch02-03: simple rule + simple initial condition -> complex behaviour (witness: rule 30).

  a  lzma compressibility of the first 2^16 centre-column bits versus os.urandom
  b  aperiodicity of the centre column (no period <= 2^15 from any offset <= 2^15)
  c  monobit, runs and 8-bit block chi-square tests
  d  pattern compressibility of rule 30 versus rules 90 and 250; census of all 256 rules
Deterministic apart from the os.urandom baseline.  Prints JSON to stdout.
"""
import json
import lzma
import math
import os
import sys

import numpy as np
from scipy.stats import chisquare, norm

T_COL = 2 ** 16
T_PAT = 1000
W_PAT = 2003


def step(x, rule):
    idx = (np.roll(x, 1).astype(np.int64) << 2) | (x.astype(np.int64) << 1) | np.roll(x, -1)
    return ((rule >> idx) & 1).astype(np.uint8)


def centre_column(rule, t):
    W = 2 * t + 3
    x = np.zeros(W, np.uint8)
    x[W // 2] = 1
    col = np.empty(t, np.uint8)
    for i in range(t):
        col[i] = x[W // 2]
        x = step(x, rule)
    return col


def pattern(rule, t, w):
    x = np.zeros(w, np.uint8)
    x[w // 2] = 1
    rows = [x]
    for _ in range(t):
        x = step(x, rule)
        rows.append(x)
    return np.array(rows)


def lz(bits):
    return len(lzma.compress(np.packbits(bits).tobytes(), preset=9 | lzma.PRESET_EXTREME))


def aperiodic(col, pmax, t0):
    """Pre-registered form: True if for every p <= pmax some t >= t0 has col[t] != col[t+p].
    Also returns, for every p that 'passes' (all comparisons equal), the number of comparisons
    made, since for p close to n - t0 only a handful of positions can be compared."""
    n = col.size
    passing = []
    worst = None
    for p in range(1, pmax + 1):
        diff = col[t0:n - p] != col[t0 + p:n]
        if not diff.any():
            passing.append((p, int(n - p - t0)))
            continue
        last = int(np.flatnonzero(diff)[-1]) + t0
        if worst is None or last < worst[1]:
            worst = (p, last)
    return len(passing) == 0, worst, passing


def tests(col):
    n = col.size
    ones = int(col.sum())
    s = abs(2 * ones - n) / math.sqrt(n)
    p_mono = math.erfc(s / math.sqrt(2))
    pi = ones / n
    runs = 1 + int(np.count_nonzero(col[1:] != col[:-1]))
    mu = 2 * n * pi * (1 - pi)
    sigma = math.sqrt(2 * n * pi * (1 - pi) * (2 * pi * (1 - pi) * n - 1) / (n - 1)) if n > 1 else 1
    p_runs = 2 * (1 - norm.cdf(abs(runs - mu) / sigma))
    blocks = np.packbits(col[: (n // 8) * 8])
    counts = np.bincount(blocks, minlength=256)
    p_chi = float(chisquare(counts).pvalue)
    return {"ones": ones, "monobit_p": p_mono, "runs": runs, "runs_p": float(p_runs), "block8_chi2_p": p_chi}


def main():
    col = centre_column(30, T_COL)
    rnd = np.unpackbits(np.frombuffer(os.urandom(T_COL // 8), dtype=np.uint8))
    lz30 = lz(col)
    lzr = lz(rnd)
    a_ratio = lz30 / lzr
    aper, info, passing = aperiodic(col, 2 ** 15, 2 ** 15)
    # post-hoc (see result.json caveats): periods that only pass because fewer than 64 positions
    # could be compared are not evidence of periodicity; the smallest p with >= 64 comparisons passing is reported.
    passing_64 = [pp for pp in passing if pp[1] >= 64]
    aper_64 = len(passing_64) == 0
    b = {"preregistered_aperiodic": bool(aper), "periods_passing_literal_test": passing[:20],
         "n_periods_passing_literal_test": len(passing), "min_comparisons_among_passing": min((pp[1] for pp in passing), default=None),
         "max_comparisons_among_passing": max((pp[1] for pp in passing), default=None),
         "posthoc_aperiodic_with_ge_64_comparisons": bool(aper_64), "periods_passing_with_ge_64_comparisons": passing_64[:20],
         "hardest_period_and_last_mismatch_index": info}
    c = tests(col)
    pats = {}
    census = []
    for rule in range(256):
        P = pattern(rule, T_PAT, W_PAT)
        raw = P.size // 8
        ratio = lz(P.ravel()) / raw
        census.append(ratio)
        if rule in (30, 90, 250):
            pats[str(rule)] = ratio
    census = np.array(census)
    d_ok = pats["30"] >= 5 * pats["90"] and pats["30"] >= 5 * pats["250"]
    a_ok = a_ratio >= 0.95
    c_ok = c["monobit_p"] > 0.01 and c["runs_p"] > 0.01 and c["block8_chi2_p"] > 0.01
    verdict = "supports" if (a_ok and aper and c_ok and d_ok) else ("refutes" if ((not aper) or a_ratio < 0.5) else "mixed")
    verdict_posthoc = "supports" if (a_ok and aper_64 and c_ok and d_ok) else ("refutes" if ((not aper_64) or a_ratio < 0.5) else "mixed")
    out = {
        "a_compressibility": {"lzma_bytes_rule30_centre_column": lz30, "lzma_bytes_urandom": lzr, "ratio": round(a_ratio, 4), "ok": bool(a_ok)},
        "b_aperiodicity": b,
        "c_randomness_tests": c | {"ok": bool(c_ok)},
        "d_pattern_ratio": {"rule30": round(pats["30"], 4), "rule90": round(pats["90"], 4), "rule250": round(pats["250"], 4),
                            "ratio_30_over_90": round(pats["30"] / pats["90"], 2), "ratio_30_over_250": round(pats["30"] / pats["250"], 2), "ok": bool(d_ok)},
        "census_256_rules": {"rules_with_ratio_gt_half_of_rule30": sorted(int(r) for r in np.flatnonzero(census > 0.5 * pats["30"])),
                             "n_rules_with_ratio_gt_half_of_rule30": int(np.sum(census > 0.5 * pats["30"])),
                             "median_ratio": round(float(np.median(census)), 4), "ratio_by_rule": [round(float(r), 4) for r in census]},
        "params": {"centre_column_steps": T_COL, "pattern_steps": T_PAT, "pattern_width": W_PAT},
        "preregistered_verdict": verdict,
        "verdict_with_posthoc_b": verdict_posthoc,
    }
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
