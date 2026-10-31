#!/usr/bin/env python3
"""Test of wolfram2002-ch06-14: statistical randomness of the rule 30 centre column from a
single black cell, versus rule 30 from a random initial row, a PRNG, and Thue-Morse.

Fetches the OEIS A051023 b-file to validate the generator. Writes derived/measurements.json.
"""
import datetime
import hashlib
import json
import lzma
import math
import os
import sys

import numpy as np
from scipy.special import erfc, gammaincc
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1 << 20
SEED = 20261031
OEIS_URL = "https://oeis.org/A051023/b051023.txt"


# --------------------------------------------------------------- sequences
def rule30_centre_column(n, init_int, origin):
    mask = ~(-1 << (2 * origin + 1))
    x = init_int & mask
    col = np.zeros(n, dtype=np.uint8)
    for t in range(n):
        col[t] = (x >> origin) & 1
        x = ((x << 1) ^ (x | (x >> 1))) & mask
    return col


def thue_morse(n):
    idx = np.arange(n, dtype=np.uint64)
    v = idx.copy()
    par = np.zeros(n, dtype=np.uint64)
    while v.any():
        par ^= v & 1
        v >>= np.uint64(1)
    return par.astype(np.uint8)


# ---------------------------------------------------------------- the tests
def t_monobit(b):
    s = 2.0 * b.sum() - len(b)
    return erfc(abs(s) / math.sqrt(2 * len(b)))


def t_block_frequency(b, M=128):
    nb = len(b) // M
    pi = b[:nb * M].reshape(nb, M).mean(axis=1)
    chi = 4 * M * np.sum((pi - 0.5) ** 2)
    return gammaincc(nb / 2, chi / 2)


def t_runs(b):
    n = len(b)
    pi = b.mean()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return 0.0
    v = 1 + np.count_nonzero(b[1:] != b[:-1])
    return erfc(abs(v - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi)))


def longest_run_ones(block):
    if not block.any():
        return 0
    d = np.diff(np.concatenate([[0], block, [0]]).astype(np.int8))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return int((ends - starts).max())


def t_longest_run(b, M=10000):
    pi = np.array([0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727])
    nb = len(b) // M
    runs = np.array([longest_run_ones(b[i * M:(i + 1) * M]) for i in range(nb)])
    cats = np.clip(runs, 10, 16) - 10
    nu = np.bincount(cats, minlength=7)
    chi = np.sum((nu - nb * pi) ** 2 / (nb * pi))
    return gammaincc(6 / 2, chi / 2)


def overlapping_counts(b, m):
    """Counts of all 2^m overlapping m-bit patterns with wraparound."""
    n = len(b)
    ext = np.concatenate([b, b[:m - 1]]).astype(np.int64)
    code = np.zeros(n, dtype=np.int64)
    for k in range(m):
        code = (code << 1) | ext[k:k + n]
    return np.bincount(code, minlength=1 << m)


def psi_sq(b, m):
    if m <= 0:
        return 0.0
    c = overlapping_counts(b, m)
    return (2 ** m / len(b)) * float(np.sum(c.astype(np.float64) ** 2)) - len(b)


def t_serial(b, m=16):
    p_m, p_m1, p_m2 = psi_sq(b, m), psi_sq(b, m - 1), psi_sq(b, m - 2)
    d1, d2 = p_m - p_m1, p_m - 2 * p_m1 + p_m2
    return min(gammaincc(2 ** (m - 2), d1 / 2), gammaincc(2 ** (m - 3), d2 / 2))


def phi(b, m):
    c = overlapping_counts(b, m).astype(np.float64)
    pr = c[c > 0] / len(b)
    return float(np.sum(pr * np.log(pr)))


def t_approx_entropy(b, m=10):
    apen = phi(b, m) - phi(b, m + 1)
    chi = 2 * len(b) * (math.log(2) - apen)
    return gammaincc(2 ** (m - 1), chi / 2)


def cusum_p(z, n):
    sq = math.sqrt(n)
    s1 = sum(norm.cdf((4 * k + 1) * z / sq) - norm.cdf((4 * k - 1) * z / sq)
             for k in range(int(math.floor((-n / z + 1) / 4)), int(math.floor((n / z - 1) / 4)) + 1))
    s2 = sum(norm.cdf((4 * k + 3) * z / sq) - norm.cdf((4 * k + 1) * z / sq)
             for k in range(int(math.floor((-n / z - 3) / 4)), int(math.floor((n / z - 1) / 4)) + 1))
    return 1 - s1 + s2


def t_cusum(b):
    x = 2 * b.astype(np.int64) - 1
    zf = int(np.abs(np.cumsum(x)).max())
    zb = int(np.abs(np.cumsum(x[::-1])).max())
    return min(cusum_p(zf, len(b)), cusum_p(zb, len(b)))


def t_dft(b):
    n = len(b)
    x = 2.0 * b - 1
    s = np.abs(np.fft.rfft(x))[: n // 2]
    thr = math.sqrt(math.log(1 / 0.05) * n)
    n0, n1 = 0.95 * n / 2, int(np.count_nonzero(s < thr))
    d = (n1 - n0) / math.sqrt(n * 0.95 * 0.05 / 4)
    return erfc(abs(d) / math.sqrt(2))


def t_autocorrelation(b, max_lag=64):
    x = 2.0 * b - 1
    n = len(x)
    z = [np.dot(x[:-k], x[k:]) / math.sqrt(n - k) for k in range(1, max_lag + 1)]
    zmax = max(abs(v) for v in z)
    return min(1.0, max_lag * 2 * (1 - norm.cdf(zmax)))


def t_block16_uniformity(b, m=16):
    nb = len(b) // m
    codes = np.packbits(b[:nb * m].reshape(nb, m), axis=1, bitorder="big")
    vals = codes[:, 0].astype(np.int64) * 256 + codes[:, 1]
    c = np.bincount(vals, minlength=1 << m).astype(np.float64)
    e = nb / (1 << m)
    chi = float(np.sum((c - e) ** 2 / e))
    return gammaincc(((1 << m) - 1) / 2, chi / 2)


TESTS = [
    ("monobit", t_monobit), ("block_frequency_M128", t_block_frequency), ("runs", t_runs),
    ("longest_run_M10000", t_longest_run), ("serial_m16", t_serial), ("approximate_entropy_m10", t_approx_entropy),
    ("cumulative_sums", t_cusum), ("dft_spectral", t_dft), ("autocorrelation_lags1to64", t_autocorrelation),
    ("block16_uniformity_chi2", t_block16_uniformity),
]


def battery(b):
    out = {}
    for name, fn in TESTS:
        out[name] = float(fn(b))
    out["n_passed"] = int(sum(v >= 0.01 for k, v in out.items()))
    raw = np.packbits(b).tobytes()
    out["lzma_ratio"] = len(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME)) / len(raw)
    out["ones_fraction"] = float(b.mean())
    return out


# -------------------------------------------------------------------- OEIS
def fetch_oeis():
    import requests
    r = requests.get(OEIS_URL, timeout=60, headers={"User-Agent": "delphi-claim-tests/1.0"})
    r.raise_for_status()
    data = r.content
    terms = []
    for line in data.decode().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        i, v = line.split()
        terms.append((int(i), int(v)))
    return {
        "download_url": OEIS_URL, "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "final_url": r.url,
    }, terms


def main():
    rng = np.random.default_rng(SEED)
    print("generating S1 (rule 30, single cell)", flush=True)
    s1 = rule30_centre_column(N, 1 << N, N)
    print("generating S2 (rule 30, random row)", flush=True)
    rand_row = int.from_bytes(rng.bytes((2 * N + 1) // 8 + 1), "little")
    s2 = rule30_centre_column(N, rand_row, N)
    s3 = rng.integers(0, 2, N, dtype=np.uint8)
    s4 = thue_morse(N)

    oeis = {"status": None}
    try:
        meta, terms = fetch_oeis()
        offset0 = terms[0][0]
        k = min(len(terms), N)
        gen = s1[[i - offset0 for i, _ in terms[:k]]]
        pub = np.array([v for _, v in terms[:k]], dtype=np.uint8)
        oeis = {"status": "ok", "file": meta, "n_terms_in_bfile": len(terms), "first_index": offset0, "n_compared": int(k),
                "n_mismatch": int(np.count_nonzero(gen != pub)), "exact_match": bool(np.array_equal(gen, pub))}
    except Exception as e:  # noqa: BLE001
        oeis = {"status": "fetch-failed", "error": str(e)}
    print("OEIS:", {k: v for k, v in oeis.items() if k != "file"}, flush=True)

    seqs = {"S1_rule30_single_cell": s1, "S2_rule30_random_row": s2, "S3_pcg64": s3, "S4_thue_morse": s4}
    res = {}
    for name, b in seqs.items():
        print("testing", name, flush=True)
        res[name] = battery(b)
        print(json.dumps(res[name], indent=1), flush=True)

    r1 = res["S1_rule30_single_cell"]
    crit = {
        "S1_passed": r1["n_passed"], "S1_lzma_ratio": r1["lzma_ratio"],
        "S2_passed": res["S2_rule30_random_row"]["n_passed"], "S3_passed": res["S3_pcg64"]["n_passed"],
        "S4_failed": 10 - res["S4_thue_morse"]["n_passed"],
        "oeis_exact_match": oeis.get("exact_match"), "oeis_status": oeis["status"],
    }
    if oeis["status"] == "ok" and not oeis["exact_match"]:
        verdict = "inconclusive"
    elif crit["S1_passed"] <= 7 or crit["S1_lzma_ratio"] < 0.98:
        verdict = "refutes"
    elif crit["S1_passed"] >= 9 and crit["S1_lzma_ratio"] >= 0.99 and crit["S2_passed"] >= 9 and crit["S3_passed"] >= 9 and crit["S4_failed"] >= 4:
        verdict = "supports"
    else:
        verdict = "mixed"
    out = {"N": N, "results": res, "oeis": oeis, "criteria": crit, "verdict": verdict,
           "S1_first_64": "".join(map(str, s1[:64].tolist()))}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({"criteria": crit, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
