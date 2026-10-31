#!/usr/bin/env python3
"""Test of wolfram2002-ch02-05: rule 30 centre column, 10^6 steps.

1. Generates the centre column exactly (bit-packed numpy, restricted to the light
   cone of the centre cell at the final step).
2. Validates the first 100,000 bits against the OEIS A051023 b-file (downloaded to
   data/, not committed; URL, size and SHA-256 recorded).
3. Checks for eventual periodicity (any period p <= N/2 with >= 2 full periods
   visible at the end).
4. Runs a numpy implementation of the NIST SP 800-22 rev. 1a battery.

Writes derived/results.json and prints the measured block.
"""
import datetime as dt
import hashlib
import json
import math
import os
import time

import numpy as np
import requests
from scipy.special import erfc, gammaincc

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1_000_000
OEIS_URL = "https://oeis.org/A051023/b051023.txt"


# ----------------------------------------------------------------------------
# Generator
# ----------------------------------------------------------------------------
def rule30_center_column(T):
    C = T + 192
    W = (2 * C + 1) // 64 + 8
    row = np.zeros(W, dtype=np.uint64)
    row[C // 64] = np.uint64(1) << np.uint64(C % 64)
    out = np.zeros(T, dtype=np.uint8)
    out[0] = 1
    one = np.uint64(1)
    s63 = np.uint64(63)
    for s in range(1, T):
        reach = min(s, T - 1 - s)
        lo, hi = C - reach, C + reach
        a, b = lo // 64 - 1, hi // 64 + 2
        seg = row[a - 1:b + 1]
        L = seg << one
        L[1:] |= seg[:-1] >> s63
        R = seg >> one
        R[:-1] |= seg[1:] << s63
        new = L ^ (seg | R)
        row[a:b] = new[1:-1]
        out[s] = (row[C // 64] >> np.uint64(C % 64)) & one
    return out


# ----------------------------------------------------------------------------
# Periodicity
# ----------------------------------------------------------------------------
MIN_PERIODIC_SUFFIX = 64


def longest_periodic_suffix(bits):
    """For each p in 1..N//2, length ell(p) of the longest suffix with x[t] = x[t-p].
    A period is counted if ell(p) >= p (two full periods visible) and ell(p) >= 64
    bits.  The second condition is a deviation from the literal pre-registration,
    added after testing the function on random bits (not on rule 30): a random
    sequence ending in ...0101 has 'two full periods' of p = 2, so without a
    minimum length the criterion flags chance matches at tiny p.  A 64-bit chance
    match has probability 2^-64 per p, i.e. ~3e-14 over all p.
    Returns (max ell, argmax p, number of counted periods)."""
    n = len(bits)
    X = int.from_bytes(np.packbits(bits[::-1]).tobytes(), "big")  # bit i = bits[i]
    best_ell, best_p, n_periodic = 0, 0, 0
    for p in range(1, n // 2 + 1):
        mask = (1 << (n - p)) - 1
        D = (X >> p) ^ (X & mask)
        ell = (n - p) - D.bit_length()
        if ell >= p and ell >= MIN_PERIODIC_SUFFIX:
            n_periodic += 1
        if ell > best_ell:
            best_ell, best_p = ell, p
    return best_ell, best_p, n_periodic


# ----------------------------------------------------------------------------
# NIST SP 800-22 tests (numpy)
# ----------------------------------------------------------------------------
def t_frequency(b):
    s = np.sum(2 * b.astype(np.int64) - 1)
    return float(erfc(abs(s) / math.sqrt(len(b)) / math.sqrt(2)))


def t_block_frequency(b, M=128):
    n = len(b)
    Nb = n // M
    pi = b[:Nb * M].reshape(Nb, M).mean(axis=1)
    chi = 4 * M * np.sum((pi - 0.5) ** 2)
    return float(gammaincc(Nb / 2, chi / 2))


def t_runs(b):
    n = len(b)
    pi = b.mean()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return 0.0
    V = 1 + np.count_nonzero(b[1:] != b[:-1])
    return float(erfc(abs(V - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi))))


def longest_run_ones(block):
    # longest run of 1s in a 0/1 array
    if block.sum() == 0:
        return 0
    padded = np.concatenate([[0], block, [0]])
    d = np.diff(padded)
    starts = np.nonzero(d == 1)[0]
    ends = np.nonzero(d == -1)[0]
    return int((ends - starts).max())


def t_longest_run(b, M=10000):
    n = len(b)
    Nb = n // M
    K = 6
    V = [10, 11, 12, 13, 14, 15]
    pi = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]
    nu = np.zeros(K + 1)
    for i in range(Nb):
        r = longest_run_ones(b[i * M:(i + 1) * M])
        if r <= V[0]:
            nu[0] += 1
        elif r >= V[-1] + 1:
            nu[K] += 1
        else:
            nu[r - V[0]] += 1
    chi = np.sum((nu - Nb * np.array(pi)) ** 2 / (Nb * np.array(pi)))
    return float(gammaincc(K / 2, chi / 2))


def gf2_rank(mat):
    m = mat.copy().astype(np.uint8)
    rows, cols = m.shape
    rank = 0
    for c in range(cols):
        pivot = None
        for r in range(rank, rows):
            if m[r, c]:
                pivot = r
                break
        if pivot is None:
            continue
        m[[rank, pivot]] = m[[pivot, rank]]
        others = np.nonzero(m[:, c])[0]
        others = others[others != rank]
        m[others] ^= m[rank]
        rank += 1
        if rank == rows:
            break
    return rank


def t_matrix_rank(b, M=32, Q=32):
    n = len(b)
    Nb = n // (M * Q)
    F = np.zeros(3)
    for i in range(Nb):
        r = gf2_rank(b[i * M * Q:(i + 1) * M * Q].reshape(M, Q))
        if r == M:
            F[0] += 1
        elif r == M - 1:
            F[1] += 1
        else:
            F[2] += 1
    p = np.array([0.2888, 0.5776, 0.1336])
    chi = np.sum((F - Nb * p) ** 2 / (Nb * p))
    return float(math.exp(-chi / 2))


def t_dft(b):
    n = len(b)
    x = 2 * b.astype(np.float64) - 1
    S = np.fft.rfft(x)[: n // 2]
    mod = np.abs(S)
    T = math.sqrt(math.log(1 / 0.05) * n)
    N0 = 0.95 * n / 2
    N1 = np.count_nonzero(mod < T)
    d = (N1 - N0) / math.sqrt(n * 0.95 * 0.05 / 4)
    return float(erfc(abs(d) / math.sqrt(2)))


def t_nonoverlapping_template(b, template=(0, 0, 0, 0, 0, 0, 0, 0, 1), Nb=8):
    n = len(b)
    m = len(template)
    M = n // Nb
    mu = (M - m + 1) / 2 ** m
    var = M * (1 / 2 ** m - (2 * m - 1) / 2 ** (2 * m))
    tmpl = np.array(template, dtype=np.uint8)
    W = np.zeros(Nb)
    for i in range(Nb):
        blk = b[i * M:(i + 1) * M]
        j = 0
        count = 0
        # sliding windows; non-overlapping advance
        win = np.lib.stride_tricks.sliding_window_view(blk, m)
        matches = np.nonzero(np.all(win == tmpl, axis=1))[0]
        last = -m
        for pos in matches:
            if pos >= last + m:
                count += 1
                last = pos
        W[i] = count
    chi = np.sum((W - mu) ** 2 / var)
    return float(gammaincc(Nb / 2, chi / 2))


def t_overlapping_template(b, m=9, M=1032):
    n = len(b)
    Nb = n // M
    K = 5
    pi = np.array([0.364091, 0.185659, 0.139381, 0.100571, 0.070432, 0.139865])
    tmpl = np.ones(m, dtype=np.uint8)
    nu = np.zeros(K + 1)
    for i in range(Nb):
        blk = b[i * M:(i + 1) * M]
        win = np.lib.stride_tricks.sliding_window_view(blk, m)
        c = int(np.count_nonzero(np.all(win == tmpl, axis=1)))
        nu[min(c, K)] += 1
    chi = np.sum((nu - Nb * pi) ** 2 / (Nb * pi))
    return float(gammaincc(K / 2, chi / 2))


def t_universal(b, L=7, Q=1280):
    n = len(b)
    K = n // L - Q
    expected, variance = 6.1962507, 3.125
    blocks = b[: (Q + K) * L].reshape(Q + K, L)
    vals = blocks.dot(1 << np.arange(L - 1, -1, -1)).astype(np.int64)
    table = np.zeros(2 ** L, dtype=np.int64)
    for i in range(Q):
        table[vals[i]] = i + 1
    total = 0.0
    for i in range(Q, Q + K):
        v = vals[i]
        total += math.log2((i + 1) - table[v])
        table[v] = i + 1
    fn = total / K
    c = 0.7 - 0.8 / L + (4 + 32 / L) * K ** (-3 / L) / 15
    sigma = c * math.sqrt(variance / K)
    return float(erfc(abs((fn - expected) / sigma) / math.sqrt(2)))


def berlekamp_massey(s):
    n = len(s)
    c = np.zeros(n, dtype=np.uint8)
    bb = np.zeros(n, dtype=np.uint8)
    c[0] = bb[0] = 1
    L, m = 0, -1
    for i in range(n):
        d = (s[i] + int(np.dot(c[1:L + 1], s[i - L:i][::-1]))) & 1 if L > 0 else s[i]
        if d:
            t = c.copy()
            shift = i - m
            c[shift:] ^= bb[: n - shift]
            if L <= i / 2:
                L = i + 1 - L
                m = i
                bb = t
    return L


def t_linear_complexity(b, M=500):
    n = len(b)
    Nb = n // M
    K = 6
    pi = np.array([0.010417, 0.03125, 0.125, 0.5, 0.25, 0.0625, 0.020833])
    mu = M / 2 + (9 + (-1) ** (M + 1)) / 36 - (M / 3 + 2 / 9) / 2 ** M
    nu = np.zeros(K + 1)
    for i in range(Nb):
        Lc = berlekamp_massey(b[i * M:(i + 1) * M].astype(np.int64))
        T = (-1) ** M * (Lc - mu) + 2 / 9
        if T <= -2.5:
            nu[0] += 1
        elif T <= -1.5:
            nu[1] += 1
        elif T <= -0.5:
            nu[2] += 1
        elif T <= 0.5:
            nu[3] += 1
        elif T <= 1.5:
            nu[4] += 1
        elif T <= 2.5:
            nu[5] += 1
        else:
            nu[6] += 1
    chi = np.sum((nu - Nb * pi) ** 2 / (Nb * pi))
    return float(gammaincc(K / 2, chi / 2))


def _psi_sq(b, m):
    n = len(b)
    if m == 0:
        return 0.0
    ext = np.concatenate([b, b[: m - 1]]).astype(np.int64)
    win = np.lib.stride_tricks.sliding_window_view(ext, m)[:n]
    vals = win.dot(1 << np.arange(m - 1, -1, -1))
    counts = np.bincount(vals, minlength=2 ** m)
    return float((2 ** m / n) * np.sum(counts ** 2) - n)


def t_serial(b, m=16):
    n = len(b)
    p0, p1, p2 = _psi_sq(b, m), _psi_sq(b, m - 1), _psi_sq(b, m - 2)
    d1 = p0 - p1
    d2 = p0 - 2 * p1 + p2
    return float(gammaincc(2 ** (m - 2), d1 / 2)), float(gammaincc(2 ** (m - 3), d2 / 2))


def t_approximate_entropy(b, m=10):
    n = len(b)

    def phi(mm):
        ext = np.concatenate([b, b[:mm - 1]]).astype(np.int64)
        win = np.lib.stride_tricks.sliding_window_view(ext, mm)[:n]
        vals = win.dot(1 << np.arange(mm - 1, -1, -1))
        counts = np.bincount(vals, minlength=2 ** mm).astype(np.float64)
        pr = counts[counts > 0] / n
        return float(np.sum(pr * np.log(pr)))

    ap = phi(m) - phi(m + 1)
    chi = 2 * n * (math.log(2) - ap)
    return float(gammaincc(2 ** (m - 1), chi / 2))


def t_cusum(b):
    x = 2 * b.astype(np.int64) - 1
    n = len(b)
    out = []
    for mode in (0, 1):
        s = np.cumsum(x if mode == 0 else x[::-1])
        z = int(np.max(np.abs(s)))
        from scipy.stats import norm
        k = np.arange(int((-n / z + 1) // 4), int((n / z - 1) // 4) + 1)
        t1 = np.sum(norm.cdf((4 * k + 1) * z / math.sqrt(n)) - norm.cdf((4 * k - 1) * z / math.sqrt(n)))
        k2 = np.arange(int((-n / z - 3) // 4), int((n / z - 1) // 4) + 1)
        t2 = np.sum(norm.cdf((4 * k2 + 3) * z / math.sqrt(n)) - norm.cdf((4 * k2 + 1) * z / math.sqrt(n)))
        out.append(float(1 - t1 + t2))
    return out


def t_random_excursions(b):
    x = 2 * b.astype(np.int64) - 1
    S = np.concatenate([[0], np.cumsum(x), [0]])
    zeros = np.nonzero(S == 0)[0]
    J = len(zeros) - 1
    if J < 500:
        return None, None, J
    states = [-4, -3, -2, -1, 1, 2, 3, 4]
    # visits per cycle per state
    counts = {s: np.zeros(6) for s in states}
    cycle_id = np.repeat(np.arange(J), np.diff(zeros))
    # S values excluding the final appended zero index positions
    vals = S[:-1]
    for s in states:
        hits = vals == s
        per_cycle = np.bincount(cycle_id[hits[:len(cycle_id)]], minlength=J)
        for k in range(6):
            counts[s][k] = np.count_nonzero(per_cycle == k) if k < 5 else np.count_nonzero(per_cycle >= 5)

    def pi_k(xs, k):
        xs = abs(xs)
        if k == 0:
            return 1 - 1 / (2 * xs)
        if k < 5:
            return (1 / (4 * xs * xs)) * (1 - 1 / (2 * xs)) ** (k - 1)
        return (1 / (2 * xs)) * (1 - 1 / (2 * xs)) ** 4

    pvals = {}
    for s in states:
        pi = np.array([pi_k(s, k) for k in range(6)])
        chi = np.sum((counts[s] - J * pi) ** 2 / (J * pi))
        pvals[str(s)] = float(gammaincc(2.5, chi / 2))
    # variant
    var = {}
    for s in range(-9, 10):
        if s == 0:
            continue
        xi = int(np.count_nonzero(vals == s))
        var[str(s)] = float(erfc(abs(xi - J) / math.sqrt(2 * J * (4 * abs(s) - 2))))
    return pvals, var, J


# ----------------------------------------------------------------------------
def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main():
    t0 = time.time()
    bits = rule30_center_column(N)
    gen_time = time.time() - t0
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)

    # OEIS cross-check
    oeis = {"download_url": OEIS_URL}
    try:
        resp = requests.get(OEIS_URL, timeout=60)
        resp.raise_for_status()
        raw = resp.content
        oeis.update({"retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "byte_size": len(raw), "sha256": sha256_bytes(raw)})
        with open(os.path.join(HERE, "data", "b051023.txt"), "wb") as f:
            f.write(raw)
        terms = []
        for line in raw.decode().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            i, v = line.split()
            terms.append(int(v))
        terms = np.array(terms, dtype=np.uint8)
        oeis["n_terms"] = int(len(terms))
        oeis["agrees_with_generator"] = bool(np.array_equal(terms, bits[:len(terms)]))
    except Exception as e:  # noqa: BLE001
        oeis["error"] = str(e)
        oeis["agrees_with_generator"] = None

    # periodicity
    t1 = time.time()
    best_ell, best_p, n_periodic = longest_periodic_suffix(bits)
    per_time = time.time() - t1

    # NIST battery
    p = {}
    p["frequency"] = t_frequency(bits)
    p["block_frequency_M128"] = t_block_frequency(bits)
    p["runs"] = t_runs(bits)
    p["longest_run_M10000"] = t_longest_run(bits)
    p["matrix_rank_32"] = t_matrix_rank(bits)
    p["dft"] = t_dft(bits)
    p["nonoverlapping_template_000000001"] = t_nonoverlapping_template(bits)
    p["overlapping_template_m9"] = t_overlapping_template(bits)
    p["universal_L7_Q1280"] = t_universal(bits)
    p["linear_complexity_M500"] = t_linear_complexity(bits)
    p["serial_m16_p1"], p["serial_m16_p2"] = t_serial(bits)
    p["approximate_entropy_m10"] = t_approximate_entropy(bits)
    p["cusum_forward"], p["cusum_backward"] = t_cusum(bits)
    rex, rexv, J = t_random_excursions(bits)
    if rex is not None:
        for k, v in rex.items():
            p[f"random_excursions_state_{k}"] = v
        for k, v in rexv.items():
            p[f"random_excursions_variant_state_{k}"] = v

    pv = np.array(list(p.values()))
    n_below_001 = int(np.count_nonzero(pv < 0.01))
    min_p = float(pv.min())
    repeat_found = n_periodic > 0

    if repeat_found or min_p < 1e-6 or n_below_001 >= 4:
        verdict = "refutes"
    elif oeis.get("agrees_with_generator") is False:
        verdict = "inconclusive"
    elif min_p >= 1e-4 and n_below_001 <= 2:
        verdict = "supports"
    else:
        verdict = "mixed"

    results = {
        "n_bits": N, "generation_seconds": round(gen_time, 1), "periodicity_seconds": round(per_time, 1),
        "fraction_ones": float(bits.mean()),
        "periodicity": {"n_periods_with_two_full_periods_at_end": n_periodic,
                        "max_periodic_suffix_len_bits": best_ell, "argmax_p": best_p},
        "nist_p_values": p, "random_excursions_J": J,
        "n_p_values": int(len(pv)), "n_p_below_0.01": n_below_001, "min_p": min_p,
        "oeis": oeis, "first_64_bits": "".join(map(str, bits[:64].tolist())),
        "sha256_of_bit_string": sha256_bytes(np.packbits(bits).tobytes()),
    }
    with open(os.path.join(HERE, "derived", "results.json"), "w") as f:
        json.dump(results, f, indent=1)

    measured = {
        "value": {"periods_found": n_periodic, "min_nist_p": round(min_p, 5),
                  "n_p_below_0.01": n_below_001, "n_p_values": int(len(pv)),
                  "fraction_ones": round(float(bits.mean()), 5)},
        "unit": "count of periods p <= N/2 with >= 2 full periods at the end; NIST p-values",
        "n": N,
        "uncertainty": "deterministic sequence; p-values are the tests' own",
        "extra": {"nist_p_values": {k: round(v, 5) for k, v in p.items()},
                  "oeis_agreement_first_terms": oeis.get("agrees_with_generator"),
                  "oeis_n_terms": oeis.get("n_terms"),
                  "max_periodic_suffix_len_bits": best_ell, "argmax_p": best_p,
                  "random_excursions_J": J},
    }
    print(json.dumps({"measured": measured, "verdict": verdict, "oeis": oeis}, indent=1))


if __name__ == "__main__":
    main()
