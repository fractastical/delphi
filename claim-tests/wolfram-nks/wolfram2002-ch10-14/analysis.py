#!/usr/bin/env python3
"""Test of wolfram2002-ch10-14: uniform block frequencies of all lengths are not a
universal randomness test (Wolfram's counterexamples: an LFSR sequence and the
concatenated binary digits of successive integers).

Run: python3 analysis.py   (needs numpy, requests)
"""
import datetime
import hashlib
import json
import lzma
import os

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
N_CH = 1 << 20
N_RANDOM_REF = 200
BM_BITS = 4000
A030190_URL = "https://oeis.org/A030190/b030190.txt"


def lfsr_full_period(taps, r):
    """a[n] = XOR of a[n - t] for t in taps; register of r bits, initial 1,0,...,0.
    Returns the output sequence over one full period."""
    init = [1] + [0] * (r - 1)
    a = list(init)
    n = r
    limit = (1 << r) + r + 1
    while n < limit:
        a.append(a[n - taps[0]] ^ a[n - taps[1]])
        n += 1
        if a[n - r:n] == init:
            return np.array(a[:n - r], dtype=np.uint8)
    raise RuntimeError("period not found")


def champernowne_bits(n_bits):
    parts = []
    total = 0
    k = 1
    while total < n_bits:
        s = bin(k)[2:]
        parts.append(s)
        total += len(s)
        k += 1
    return np.frombuffer("".join(parts)[:n_bits].encode(), dtype=np.uint8) - ord("0")


def block_counts(bits, L):
    idx = np.zeros(len(bits) - L + 1, dtype=np.int64)
    for j in range(L):
        idx = (idx << 1) | bits[j:len(bits) - L + 1 + j]
    return np.bincount(idx, minlength=1 << L)


def chi2(counts, n_blocks):
    E = n_blocks / len(counts)
    return float(((counts - E) ** 2 / E).sum())


def max_rel_dev(counts, n_blocks):
    E = n_blocks / len(counts)
    return float(np.abs(counts / E - 1).max())


def berlekamp_massey(bits):
    bits = np.asarray(bits, dtype=np.int64)
    n = len(bits)
    c = np.zeros(n, dtype=np.int64)
    b = np.zeros(n, dtype=np.int64)
    c[0] = b[0] = 1
    L, m = 0, -1
    for i in range(n):
        d = (bits[i] + (c[1:L + 1] * bits[i - L:i][::-1]).sum()) & 1 if L > 0 else bits[i]
        if d:
            t = c.copy()
            shift = i - m
            c[shift:] ^= b[:n - shift]
            if 2 * L <= i:
                L = i + 1 - L
                m = i
                b = t
    return L


def lzma_ratio(bits):
    raw = np.packbits(bits).tobytes()
    return len(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME)) / len(raw)


def spread_percentiles(bits, Ls, rng, n_ref):
    N = len(bits)
    res = {}
    ref = {L: [] for L in Ls}
    for _ in range(n_ref):
        rb = rng.integers(0, 2, size=N, dtype=np.uint8)
        for L in Ls:
            ref[L].append(chi2(block_counts(rb, L), N - L + 1))
    for L in Ls:
        x = chi2(block_counts(bits, L), N - L + 1)
        arr = np.array(ref[L])
        res[L] = {"chi2": round(x, 2), "random_ref_p1": round(float(np.percentile(arr, 1)), 2),
                  "random_ref_median": round(float(np.median(arr)), 2),
                  "random_ref_p99": round(float(np.percentile(arr, 99)), 2),
                  "fraction_of_random_refs_below": float((arr < x).mean())}
    return res


def fetch(url):
    t = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = requests.get(url, timeout=120, headers={"User-Agent": "delphisci-claim-test/1.0"})
    resp.raise_for_status()
    data = resp.content
    vals = {}
    for line in data.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("#"):
            vals[int(parts[0])] = int(parts[1])
    return {"download_url": url, "retrieved_at": t, "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}, vals


def analyse_lfsr(taps, r, rng):
    seq = lfsr_full_period(taps, r)
    N = len(seq)
    out = {"taps": taps, "register_bits": r, "period": N, "maximal_period": N == (1 << r) - 1}
    uni = {}
    for L in range(1, r):
        c = block_counts(seq, L)
        E = (N - L + 1) / (1 << L)
        uni[L] = {"max_abs_dev_from_uniform_count": round(float(np.abs(c - E).max()), 3),
                  "all_within_1": bool(np.abs(c - E).max() <= 1.0)}
    out["block_uniformity_L_1_to_r-1"] = uni
    out["all_blocks_within_1_of_uniform_for_L_le_r-1"] = all(v["all_within_1"] for v in uni.values())
    out["linear_complexity_first_%d_bits" % BM_BITS] = int(berlekamp_massey(seq[:BM_BITS]))
    out["spread_chi2_vs_random"] = spread_percentiles(seq, [4, 5, 6, 7, 8], rng, N_RANDOM_REF)
    out["spread_below_p1_for_all_L_4_8"] = all(v["fraction_of_random_refs_below"] < 0.01 for v in out["spread_chi2_vs_random"].values())
    out["lzma_ratio"] = round(lzma_ratio(seq), 4)
    return out, seq


def main():
    rng = np.random.default_rng(SEED)
    out = {}
    out["lfsr_2_11"], _ = analyse_lfsr((2, 11), 11, rng)
    print(json.dumps(out["lfsr_2_11"]))
    out["lfsr_3_20"], _ = analyse_lfsr((3, 20), 20, rng)
    print(json.dumps(out["lfsr_3_20"]))

    ch = champernowne_bits(N_CH)
    N = len(ch)
    dev = {}
    for L in range(1, 9):
        dev[L] = {"N/4": round(max_rel_dev(block_counts(ch[:N // 4], L), N // 4 - L + 1), 4),
                  "N/2": round(max_rel_dev(block_counts(ch[:N // 2], L), N // 2 - L + 1), 4),
                  "N": round(max_rel_dev(block_counts(ch, L), N - L + 1), 4)}
        dev[L]["decreasing"] = dev[L]["N/4"] > dev[L]["N/2"] > dev[L]["N"]
        dev[L]["ones_fraction" if L == 1 else "min_count"] = float(ch.mean()) if L == 1 else int(block_counts(ch, L).min())
    chm = {"bits": N, "max_rel_dev_by_L": dev,
           "all_L_le_8_decreasing_and_le_0.5_at_N": all(v["decreasing"] and v["N"] <= 0.5 for v in dev.values()),
           "max_rel_dev_L_le_8_at_N": max(v["N"] for v in dev.values()),
           "lzma_ratio": round(lzma_ratio(ch), 4),
           "linear_complexity_first_%d_bits" % BM_BITS: int(berlekamp_massey(ch[:BM_BITS])),
           "spread_chi2_vs_random": spread_percentiles(ch, [4, 5, 6, 7, 8], rng, N_RANDOM_REF)}
    try:
        meta, vals = fetch(A030190_URL)
        # A030190 juxtaposes n = 0, 1, 2, ... so its term k (k >= 1) is our bit k - 1.
        ks = sorted(k for k in vals if 1 <= k <= N)
        mism = sum(1 for k in ks if vals[k] != int(ch[k - 1]))
        chm["oeis_a030190"] = {"file": meta, "terms_in_bfile": len(vals), "a030190_term0": vals.get(0),
                               "compared": len(ks), "mismatches": mism}
    except Exception as e:
        chm["oeis_a030190"] = {"error": repr(e)}
    out["champernowne"] = chm
    print(json.dumps(chm))

    ref = rng.integers(0, 2, size=N_CH, dtype=np.uint8)
    out["random_reference"] = {"bits": N_CH, "lzma_ratio": round(lzma_ratio(ref), 4),
                               "linear_complexity_first_%d_bits" % BM_BITS: int(berlekamp_massey(ref[:BM_BITS])),
                               "max_rel_dev_L_le_8": max(max_rel_dev(block_counts(ref, L), N_CH - L + 1) for L in range(1, 9))}
    print(json.dumps(out["random_reference"]))
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
