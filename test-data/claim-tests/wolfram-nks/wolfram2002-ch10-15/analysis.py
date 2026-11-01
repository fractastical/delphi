#!/usr/bin/env python3
"""Test of wolfram2002-ch10-15: the rule 30 centre column and the binary digits of pi show
no detectable deviation from randomness under block-frequency statistics or analysis by
simple cellular automata.

(A) NIST serial increments del-psi^2_L, L = 1..12, on 2^20 bits of each sequence.
(B) Each of the 88 inequivalent elementary CAs is run for 64 steps on the first 16384 bits
    (cyclic); output density and zlib size are compared with 100 random inputs.
Controls: a fresh PRNG sequence (negative), binary Champernowne and Thue-Morse (positive),
and an m-sequence LFSR (exploratory).

Run: python3 analysis.py   (needs numpy, scipy, requests; standard-library zlib)
Writes derived/measured.json and prints it. OEIS b-files go to data/ (not committed).
"""
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
import zlib

import numpy as np
import requests
from scipy.stats import chi2

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1 << 20
W = 16384
STEPS = 64
N_REF = 100
SEED = 20261031
Z_PASS, Z_REFUTE = 5.0, 6.0
A051023_URL = "https://oeis.org/A051023/b051023.txt"
A004601_URL = "https://oeis.org/A004601/b004601.txt"

sys.set_int_max_str_digits(0)


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------
def rule30_center_column(T):
    """Bit-packed rule 30 from one black cell, restricted to the centre cell's light cone."""
    C = T + 192
    Wd = (2 * C + 1) // 64 + 8
    row = np.zeros(Wd, dtype=np.uint64)
    row[C // 64] = np.uint64(1) << np.uint64(C % 64)
    out = np.zeros(T, dtype=np.uint8)
    out[0] = 1
    one, s63 = np.uint64(1), np.uint64(63)
    for s in range(1, T):
        reach = min(s, T - 1 - s)
        lo, hi = C - reach, C + reach
        a, b = lo // 64 - 1, hi // 64 + 2
        seg = row[a - 1:b + 1]
        L = seg << one
        L[1:] |= seg[:-1] >> s63
        R = seg >> one
        R[:-1] |= seg[1:] << s63
        row[a:b] = (L ^ (seg | R))[1:-1]
        out[s] = (row[C // 64] >> np.uint64(C % 64)) & one
    return out


def _bs(a, b):
    if b - a == 1:
        if a == 0:
            P = Q = 1
        else:
            P = (6 * a - 5) * (2 * a - 1) * (6 * a - 1)
            Q = a * a * a * 10939058860032000
        T = P * (13591409 + 545140134 * a)
        return P, Q, (-T if a & 1 else T)
    m = (a + b) // 2
    P1, Q1, T1 = _bs(a, m)
    P2, Q2, T2 = _bs(m, b)
    return P1 * P2, Q1 * Q2, Q2 * T1 + P1 * T2


def pi_binary(n_bits, guard=64):
    """First n_bits binary digits of pi after the binary point (Chudnovsky, exact integers)."""
    D = n_bits + guard
    n_terms = int(D * math.log(2) / math.log(151931373056000)) + 2
    _, Q, T = _bs(0, n_terms)
    val = (426880 * math.isqrt(10005 << (2 * D)) * Q) // T
    s = format(val, "b")
    assert s[:2] == "11"
    return np.frombuffer(s[2:2 + n_bits].encode(), dtype=np.uint8) - ord("0")


def champernowne_bits(n):
    parts, total, k = [], 0, 1
    while total < n:
        s = bin(k)[2:]
        parts.append(s)
        total += len(s)
        k += 1
    return np.frombuffer("".join(parts)[:n].encode(), dtype=np.uint8) - ord("0")


def thue_morse(n):
    i = np.arange(n, dtype=np.uint64)
    out = np.zeros(n, dtype=np.uint8)
    while i.any():
        out ^= (i & np.uint64(1)).astype(np.uint8)
        i >>= np.uint64(1)
    return out


def lfsr_3_20(n):
    a = np.zeros(n, dtype=np.uint8)
    a[0] = 1
    for k in range(20, n):
        a[k] = a[k - 3] ^ a[k - 20]
    return a


# ---------------------------------------------------------------------------
# OEIS cross-checks
# ---------------------------------------------------------------------------
def fetch(url, name):
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(url, timeout=180, headers={"User-Agent": "delphisci-claim-test/1.0"})
    r.raise_for_status()
    raw = r.content
    with open(os.path.join(HERE, "data", name), "wb") as fh:
        fh.write(raw)
    terms = []
    for line in raw.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("#"):
            terms.append((int(parts[0]), int(parts[1])))
    terms.sort()
    return [v for _, v in terms], {"download_url": url, "retrieved_at": t, "byte_size": len(raw),
                                    "sha256": hashlib.sha256(raw).hexdigest(), "terms": len(terms),
                                    "first_index": terms[0][0]}


# ---------------------------------------------------------------------------
# (A) block frequencies
# ---------------------------------------------------------------------------
def psi_sq(b, m):
    n = len(b)
    if m == 0:
        return 0.0
    ext = np.concatenate([b, b[:m - 1]]).astype(np.int64)
    vals = np.zeros(n, dtype=np.int64)
    for j in range(m):
        vals = (vals << 1) | ext[j:j + n]
    counts = np.bincount(vals, minlength=1 << m).astype(np.float64)
    return float((2 ** m / n) * np.sum(counts ** 2) - n)


def block_test(b, Lmax=12):
    ps, prev = {}, 0.0
    for L in range(1, Lmax + 1):
        cur = psi_sq(b, L)
        ps[L] = float(chi2.sf(cur - prev, 2 ** (L - 1)))
        prev = cur
    return ps


# ---------------------------------------------------------------------------
# (B) CA analysis
# ---------------------------------------------------------------------------
def inequivalent_rules():
    def reflect(r):
        out = 0
        for n in range(8):
            l, c, rr = (n >> 2) & 1, (n >> 1) & 1, n & 1
            if (r >> n) & 1:
                out |= 1 << (rr * 4 + c * 2 + l)
        return out

    def complement(r):
        return sum((1 - ((r >> (7 - n)) & 1)) << n for n in range(8))

    reps = set()
    for r in range(256):
        cls = {r, reflect(r), complement(r), complement(reflect(r))}
        reps.add(min(cls))
    return sorted(reps)


def ca_stats(inits, rule):
    """inits: (k, W) uint8. Returns (k,) mean density over steps 1..STEPS and (k,) zlib sizes."""
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    x = inits.copy()
    pattern = np.zeros((inits.shape[0], STEPS, inits.shape[1]), dtype=np.uint8)
    for t in range(STEPS):
        x = table[4 * np.roll(x, 1, axis=1) + 2 * x + np.roll(x, -1, axis=1)]
        pattern[:, t] = x
    dens = pattern.mean(axis=(1, 2))
    sizes = np.array([len(zlib.compress(np.packbits(p.ravel()).tobytes(), 9)) for p in pattern])
    return dens, sizes


def zscore(x, ref):
    m, sd = ref.mean(), ref.std(ddof=1)
    if sd == 0:
        return 0.0 if x == m else math.inf
    return float((x - m) / sd)


def ca_analysis(named, rng):
    rules = inequivalent_rules()
    refs = rng.integers(0, 2, size=(N_REF, W), dtype=np.uint8)
    names = list(named)
    inits = np.vstack([refs] + [named[k][:W][None, :] for k in names])
    res = {k: {} for k in names}
    for rule in rules:
        dens, sizes = ca_stats(inits, rule)
        for i, k in enumerate(names):
            j = N_REF + i
            res[k][rule] = (zscore(dens[j], dens[:N_REF]), zscore(sizes[j], sizes[:N_REF]))
    summary = {}
    for k in names:
        zs = [(abs(zd), r, "density") for r, (zd, zc) in res[k].items()] + \
             [(abs(zc), r, "zlib") for r, (zd, zc) in res[k].items()]
        zs.sort(reverse=True)
        summary[k] = {"max_abs_z": round(zs[0][0], 3) if math.isfinite(zs[0][0]) else "inf",
                      "argmax": {"rule": zs[0][1], "statistic": zs[0][2]},
                      "n_abs_z_gt_5": sum(1 for z, _, _ in zs if z > Z_PASS),
                      "n_abs_z_gt_6": sum(1 for z, _, _ in zs if z > Z_REFUTE),
                      "top5": [{"rule": r, "stat": s, "abs_z": (round(z, 2) if math.isfinite(z) else "inf")}
                               for z, r, s in zs[:5]]}
    return len(rules), summary


def main():
    rng = np.random.default_rng(SEED)
    out = {"N": N, "W": W, "steps": STEPS, "n_ref": N_REF, "seed": SEED}
    t0 = time.time()
    r30 = rule30_center_column(N)
    pib = pi_binary(N)
    out["generation_seconds"] = round(time.time() - t0, 1)

    a051023, m1 = fetch(A051023_URL, "b051023.txt")
    m1["mismatches"] = int((np.array(a051023, dtype=np.uint8) != r30[:len(a051023)]).sum())
    a004601, m2 = fetch(A004601_URL, "b004601.txt")
    ref_pi = np.concatenate([[1, 1], pib]).astype(np.uint8)
    m2["mismatches"] = int((np.array(a004601, dtype=np.uint8) != ref_pi[:len(a004601)]).sum())
    out["oeis_a051023"], out["oeis_a004601"] = m1, m2
    valid = m1["mismatches"] == 0 and m2["mismatches"] == 0

    seqs = {"rule30_center": r30, "pi_binary": pib,
            "neg_control_pcg64": rng.integers(0, 2, size=N, dtype=np.uint8),
            "pos_control_champernowne": champernowne_bits(N),
            "pos_control_thue_morse": thue_morse(N),
            "exploratory_lfsr_3_20": lfsr_3_20(N)}
    out["sha256_packed"] = {k: hashlib.sha256(np.packbits(v).tobytes()).hexdigest() for k, v in seqs.items()}
    out["fraction_ones"] = {k: round(float(v.mean()), 5) for k, v in seqs.items()}

    out["block_test_p"] = {k: block_test(v) for k, v in seqs.items()}
    print(json.dumps(out["block_test_p"]))
    n_rules, ca = ca_analysis(seqs, rng)
    out["n_ca_rules"] = n_rules
    out["ca_analysis"] = ca
    print(json.dumps(ca))

    def block_pass(k):
        p = np.array(list(out["block_test_p"][k].values()))
        return p.min() >= 1e-4 and (p < 0.01).sum() <= 2

    neg_ok = block_pass("neg_control_pcg64") and ca["neg_control_pcg64"]["n_abs_z_gt_5"] == 0
    pos_ok = ca["pos_control_champernowne"]["n_abs_z_gt_5"] > 0 and ca["pos_control_thue_morse"]["n_abs_z_gt_5"] > 0
    p24 = np.array(list(out["block_test_p"]["rule30_center"].values()) + list(out["block_test_p"]["pi_binary"].values()))
    n01, pmin = int((p24 < 0.01).sum()), float(p24.min())
    ca_max_gt5 = ca["rule30_center"]["n_abs_z_gt_5"] + ca["pi_binary"]["n_abs_z_gt_5"]
    ca_max_gt6 = ca["rule30_center"]["n_abs_z_gt_6"] + ca["pi_binary"]["n_abs_z_gt_6"]
    if not valid or not neg_ok:
        verdict = "inconclusive"
    elif pmin < 1e-6 or n01 >= 4 or ca_max_gt6 > 0:
        verdict = "refutes"
    elif pmin >= 1e-4 and n01 <= 2 and ca_max_gt5 == 0:
        verdict = "supports" if pos_ok else "mixed"
    else:
        verdict = "mixed"
    out["summary"] = {"data_valid": valid, "negative_control_ok": neg_ok, "positive_controls_detected": pos_ok,
                      "block_n_p": int(len(p24)), "block_n_below_0.01": n01, "block_min_p": pmin,
                      "ca_n_abs_z_gt_5_S1_S2": ca_max_gt5, "ca_n_abs_z_gt_6_S1_S2": ca_max_gt6,
                      "verdict_by_rule": verdict}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("generation_seconds", "oeis_a051023", "oeis_a004601", "fraction_ones", "summary")}, indent=1))


if __name__ == "__main__":
    main()
