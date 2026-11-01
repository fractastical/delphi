#!/usr/bin/env python3
"""Test of wolfram2002-ch04-11: the digits of pi are random for practical purposes.

1. Downloads 1,000,000 published decimal digits of pi (angio.net) to data/ (not committed;
   URL, size and SHA-256 recorded) and the OEIS b-files A000796 (decimal) and A062964 (hex).
2. Computes pi independently (Chudnovsky series, binary splitting, exact integers) in base 10
   and base 16 and checks the published and OEIS digits against it.
3. Runs the pre-registered 10-test battery in each base and applies the verdict rule.

Run: python3 analysis.py   (needs numpy, scipy, requests; standard-library lzma)
Writes derived/measured.json and prints it.
"""
import datetime as dt
import hashlib
import json
import lzma
import math
import os
import sys
import time

import numpy as np
import requests
from scipy.stats import chi2, norm

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1_000_000
SEED = 20261031
N_REF = 20
PI_URL = "https://www.angio.net/pi/digits/pi1000000.txt"
A000796_URL = "https://oeis.org/A000796/b000796.txt"
A062964_URL = "https://oeis.org/A062964/b062964.txt"

sys.set_int_max_str_digits(0)


# ---------------------------------------------------------------------------
# Independent computation of pi
# ---------------------------------------------------------------------------
def _bs(a, b):
    if b - a == 1:
        if a == 0:
            P = Q = 1
        else:
            P = (6 * a - 5) * (2 * a - 1) * (6 * a - 1)
            Q = a * a * a * 10939058860032000
        T = P * (13591409 + 545140134 * a)
        if a & 1:
            T = -T
        return P, Q, T
    m = (a + b) // 2
    P1, Q1, T1 = _bs(a, m)
    P2, Q2, T2 = _bs(m, b)
    return P1 * P2, Q1 * Q2, Q2 * T1 + P1 * T2


def pi_digits(base, n_digits, guard=20):
    """First n_digits digits of pi after the point in `base`, as a uint8 array."""
    D = n_digits + guard
    n_terms = int(D * math.log(base) / math.log(151931373056000)) + 2
    _, Q, T = _bs(0, n_terms)
    S = base ** D
    sqrt_c = math.isqrt(10005 * S * S)
    val = (426880 * sqrt_c * Q) // T  # floor(pi * base^D) up to guard-digit error
    if base == 10:
        s = str(val)
        digs = np.frombuffer(s.encode(), dtype=np.uint8) - ord("0")
    else:
        h = format(val, "x")
        digs = np.array([int(c, 16) for c in h], dtype=np.uint8)
    assert digs[0] == 3
    return digs[1:1 + n_digits]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fetch(url, name):
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(url, timeout=180, headers={"User-Agent": "delphisci-claim-test/1.0"})
    r.raise_for_status()
    raw = r.content
    with open(os.path.join(HERE, "data", name), "wb") as fh:
        fh.write(raw)
    return raw, {"download_url": url, "retrieved_at": t, "byte_size": len(raw),
                 "sha256": hashlib.sha256(raw).hexdigest()}


def parse_bfile(raw):
    vals = {}
    for line in raw.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("#"):
            vals[int(parts[0])] = int(parts[1])
    return vals


def check_bfile(vals, digits_after_point):
    """b-file term n=1 is the integer part 3; term n (n >= 2) is digit n-1 after the point."""
    ks = sorted(k for k in vals if k >= 2 and k - 2 < len(digits_after_point))
    mism = sum(1 for k in ks if vals[k] != int(digits_after_point[k - 2]))
    return {"terms": len(vals), "first_term": vals.get(min(vals)), "first_index": min(vals),
            "compared": len(ks), "mismatches": mism}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def chisq_p(obs, exp, df):
    stat = float(((obs - exp) ** 2 / exp).sum())
    return stat, float(chi2.sf(stat, df))


def t_freq(d, b):
    c = np.bincount(d, minlength=b)
    return chisq_p(c, np.full(b, len(d) / b), b - 1)


def t_blocks(d, b, k):
    n = len(d) // k
    idx = np.zeros(n, dtype=np.int64)
    for j in range(k):
        idx = idx * b + d[j:n * k:k]
    c = np.bincount(idx, minlength=b ** k)
    return chisq_p(c, np.full(b ** k, n / b ** k), b ** k - 1)


def t_poker(d, b):
    n = len(d) // 5
    hands = d[:n * 5].reshape(n, 5)
    srt = np.sort(hands, axis=1)
    r = 1 + (np.diff(srt, axis=1) != 0).sum(axis=1)
    stirling = {1: 1, 2: 15, 3: 25, 4: 10, 5: 1}
    probs = np.array([math.perm(b, k) * stirling[k] / b ** 5 for k in range(1, 6)])
    obs = np.bincount(r, minlength=6)[1:].astype(float)
    exp = n * probs
    # merge categories with expected < 5 into the next one
    o2, e2, acc_o, acc_e = [], [], 0.0, 0.0
    for o, e in zip(obs, exp):
        acc_o += o
        acc_e += e
        if acc_e >= 5:
            o2.append(acc_o)
            e2.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0:
        o2[-1] += acc_o
        e2[-1] += acc_e
    return chisq_p(np.array(o2), np.array(e2), len(o2) - 1)


def t_gap(d, b, digit=0):
    pos = np.nonzero(d == digit)[0]
    g = np.diff(pos) - 1
    G = 3 * b
    p = 1 / b
    obs = np.bincount(np.minimum(g, G), minlength=G + 1).astype(float)
    probs = np.array([p * (1 - p) ** k for k in range(G)] + [(1 - p) ** G])
    return chisq_p(obs, len(g) * probs, G)


def t_serial(d, lag):
    x = d.astype(np.float64)
    r = float(np.corrcoef(x[:-lag], x[lag:])[0, 1])
    z = r * math.sqrt(len(x) - lag)
    return r, float(2 * norm.sf(abs(z)))


def t_spectral(d):
    x = d.astype(np.float64)
    x -= x.mean()
    n = len(x)
    I = np.abs(np.fft.rfft(x)[1:n // 2]) ** 2 / n
    m = float(I.max() / x.var())
    K = len(I)
    p = -math.expm1(K * math.log1p(-math.exp(-m)))
    return m, float(p)


def lz_size(d):
    return len(lzma.compress(d.astype(np.uint8).tobytes(), preset=9 | lzma.PRESET_EXTREME))


def t_compression(d, b, rng):
    s = lz_size(d)
    refs = np.array([lz_size(rng.integers(0, b, size=len(d), dtype=np.uint8)) for _ in range(N_REF)])
    z = (s - refs.mean()) / refs.std(ddof=1)
    return {"size": s, "ref_mean": round(float(refs.mean()), 1), "ref_sd": round(float(refs.std(ddof=1)), 1),
            "ref_min": int(refs.min()), "ref_max": int(refs.max()), "z": round(float(z), 3)}, float(2 * norm.sf(abs(z)))


def battery(d, b, rng):
    p, stats = {}, {}
    stats["freq_chi2"], p["frequency"] = t_freq(d, b)
    stats["pair_chi2"], p["pairs"] = t_blocks(d, b, 2)
    stats["triple_chi2"], p["triples"] = t_blocks(d, b, 3)
    stats["poker_chi2"], p["poker5"] = t_poker(d, b)
    stats["gap0_chi2"], p["gap_digit0"] = t_gap(d, b)
    for lag in (1, 2, 3):
        stats[f"serial_r_lag{lag}"], p[f"serial_lag{lag}"] = t_serial(d, lag)
    stats["max_periodogram_over_var"], p["spectral_max"] = t_spectral(d)
    stats["lzma"], p["lzma_vs_prng"] = t_compression(d, b, rng)
    stats["digit_counts"] = np.bincount(d, minlength=b).tolist()
    return p, stats


def main():
    rng = np.random.default_rng(SEED)
    out = {"N": N, "seed": SEED}

    t0 = time.time()
    dec = pi_digits(10, N)
    hexd = pi_digits(16, N)
    out["compute_seconds"] = round(time.time() - t0, 1)
    out["computed_sha256"] = {"decimal_ascii": hashlib.sha256((dec + ord("0")).astype(np.uint8).tobytes()).hexdigest()}

    raw, meta = fetch(PI_URL, "pi1000000.txt")
    txt = raw.decode("ascii")
    after = txt.split(".", 1)[1]
    pub = np.frombuffer("".join(c for c in after if c.isdigit()).encode(), dtype=np.uint8) - ord("0")
    out["published"] = {"file": meta, "head": txt[:12], "digits_after_point": int(len(pub)),
                        "mismatches_vs_computed_first_N": int((pub[:N] != dec[:len(pub[:N])]).sum()),
                        "covers_N": bool(len(pub) >= N)}
    raw796, m796 = fetch(A000796_URL, "b000796.txt")
    out["oeis_a000796"] = {"file": m796, **check_bfile(parse_bfile(raw796), dec)}
    raw964, m964 = fetch(A062964_URL, "b062964.txt")
    out["oeis_a062964"] = {"file": m964, **check_bfile(parse_bfile(raw964), hexd)}

    valid = (out["published"]["covers_N"] and out["published"]["mismatches_vs_computed_first_N"] == 0
             and out["oeis_a000796"]["mismatches"] == 0 and out["oeis_a062964"]["mismatches"] == 0)
    out["data_valid"] = valid

    pvals = {}
    for b, d in ((10, pub[:N] if valid else dec), (16, hexd)):
        p, st = battery(d, b, rng)
        out[f"base{b}"] = {"p_values": p, "stats": st}
        for k, v in p.items():
            pvals[f"b{b}_{k}"] = v
        print(json.dumps(out[f"base{b}"]))
    pv = np.array(list(pvals.values()))
    n01 = int((pv < 0.01).sum())
    mn = float(pv.min())
    if not valid:
        verdict = "inconclusive"
    elif mn < 1e-6 or n01 >= 4:
        verdict = "refutes"
    elif mn >= 1e-4 and n01 <= 2:
        verdict = "supports"
    else:
        verdict = "mixed"
    out["summary"] = {"n_p_values": int(len(pv)), "n_below_0.01": n01, "min_p": mn,
                      "argmin": min(pvals, key=pvals.get), "verdict_by_rule": verdict}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("compute_seconds", "published", "oeis_a000796", "oeis_a062964", "summary")}, indent=1))


if __name__ == "__main__":
    main()
