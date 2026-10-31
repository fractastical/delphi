#!/usr/bin/env python3
"""Test of wolfram2002-ch03-06: basic mobile automata never exceed repetition/nesting.

Rule conventions (NKS p. 71/73).  Case index k = 4*left + 2*active + right.
Basic rule (16 bits): outcome o_k = (rule >> 2k) & 3; new active colour = o_k >> 1,
move right iff o_k & 1.  Extended rule (32 bits): o_k = (rule >> 4k) & 15; move
right iff o_k & 1; new (right, active, left) colours = bits 1, 2, 3 of o_k.
Step symbol = o_k.  Initial condition: all white, active cell at the centre.

Writes derived/summary.json and prints the measured block.
"""
import json
import lzma
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20260306
T1, T2, T3 = 2000, 16000, 64000
TAIL1, PMAX = 1000, 500
N_EXT = 100_000
CHUNK = 20_000


def rho(seq, alphabet):
    seq = np.ascontiguousarray(seq, dtype=np.uint8)
    return 8 * len(lzma.compress(seq.tobytes(), preset=9)) / (len(seq) * math.log2(alphabet))


# ----------------------------------------------------------------------------- reference sequences
def thue_morse(n):
    t = np.zeros(1, dtype=np.uint8)
    while len(t) < n:
        t = np.concatenate([t, 1 - t])
    return t[:n]


def period_doubling(n):
    # substitution 0 -> 01, 1 -> 00
    s = np.array([0], dtype=np.uint8)
    while len(s) < n:
        s = np.concatenate([[0, 1] if x == 0 else [0, 0] for x in s]).astype(np.uint8)
    return s[:n]


def fibonacci_word(n):
    a, b = np.array([0], dtype=np.uint8), np.array([0, 1], dtype=np.uint8)
    while len(b) < n:
        a, b = b, np.concatenate([b, a])
    return b[:n]


def paper_folding(n):
    s = np.array([1], dtype=np.uint8)
    while len(s) < n:
        mid = np.array([1], dtype=np.uint8)
        s = np.concatenate([s, mid, 1 - s[::-1]])
    return s[:n]


def ruler(n):
    idx = np.arange(1, n + 1)
    v = np.zeros(n, dtype=np.uint8)
    for t in range(n):
        x = idx[t]
        c = 0
        while x % 2 == 0:
            x //= 2
            c += 1
        v[t] = c
    return v


def rule30_bits(n):
    # centre column of rule 30 from one black cell, n bits (small direct simulation)
    w = 2 * n + 3
    row = np.zeros(w, dtype=np.uint8)
    row[n + 1] = 1
    out = np.zeros(n, dtype=np.uint8)
    for t in range(n):
        out[t] = row[n + 1]
        row = np.roll(row, 1) ^ (row | np.roll(row, -1))
    return out


def bits_to_symbols(bits, k):
    n = len(bits) // k
    b = bits[: n * k].reshape(n, k).astype(np.int64)
    return b.dot(1 << np.arange(k - 1, -1, -1)).astype(np.uint8)


def calibrate(alphabet, rng, L=8000):
    k = int(math.log2(alphabet))
    nonrandom, random = {}, {}
    for p in (1, 2, 3, 4, 5, 7, 10, 13, 20, 50, 100, 200, 333, 500):
        pat = rng.integers(0, alphabet, p).astype(np.uint8)
        nonrandom[f"periodic_{p}"] = rho(np.tile(pat, L // p + 1)[:L], alphabet)
    nbits = L * k + k
    for name, gen in (("thue_morse", thue_morse), ("period_doubling", period_doubling),
                      ("fibonacci", fibonacci_word), ("paper_folding", paper_folding)):
        bits = gen(nbits)
        # overlapping k-bit windows keep the sequence nested while using the alphabet
        win = np.lib.stride_tricks.sliding_window_view(bits.astype(np.int64), k)[:L]
        nonrandom[f"nested_{name}"] = rho(win.dot(1 << np.arange(k - 1, -1, -1)).astype(np.uint8), alphabet)
    nonrandom["nested_ruler"] = rho(ruler(L) % alphabet, alphabet)
    random["numpy_random"] = rho(rng.integers(0, alphabet, L).astype(np.uint8), alphabet)
    random["rule30_centre"] = rho(bits_to_symbols(rule30_bits(L * k), k), alphabet)
    tau = math.sqrt(max(nonrandom.values()) * min(random.values()))
    ok = max(nonrandom.values()) < min(random.values())
    return {"nonrandom": nonrandom, "random": random, "tau": tau, "separated": ok}


# ----------------------------------------------------------------------------- simulation
def simulate(rules, T, extended):
    rules = np.asarray(rules, dtype=np.uint64)
    R = len(rules)
    W = 2 * T + 3
    tape = np.zeros((R, W), dtype=np.uint8)
    pos = np.full(R, T + 1, dtype=np.int64)
    ar = np.arange(R)
    if extended:
        table = np.stack([(rules >> np.uint64(4 * k)) & np.uint64(15) for k in range(8)], axis=1).astype(np.uint8)
    else:
        table = np.stack([(rules >> np.uint64(2 * k)) & np.uint64(3) for k in range(8)], axis=1).astype(np.uint8)
    syms = np.zeros((R, T), dtype=np.uint8)
    for t in range(T):
        l = tape[ar, pos - 1]
        c = tape[ar, pos]
        r = tape[ar, pos + 1]
        o = table[ar, 4 * l + 2 * c + r]
        syms[:, t] = o
        if extended:
            tape[ar, pos + 1] = (o >> 1) & 1
            tape[ar, pos] = (o >> 2) & 1
            tape[ar, pos - 1] = (o >> 3) & 1
        else:
            tape[ar, pos] = o >> 1
        pos += 2 * (o & 1).astype(np.int64) - 1
    return syms


def periodic_tail(syms, tail, pmax):
    t = syms[:, -tail:]
    per = np.zeros(len(syms), dtype=bool)
    period = np.zeros(len(syms), dtype=np.int64)
    for p in range(1, pmax + 1):
        m = ~per & np.all(t[:, p:] == t[:, :-p], axis=1)
        period[m] = p
        per |= m
    return per, period


def classify(rules, extended, alphabet, tau):
    """Three-stage classification; returns dict with counts and lists."""
    nonperiodic = []
    periods = {}
    for start in range(0, len(rules), CHUNK):
        chunk = rules[start:start + CHUNK]
        syms = simulate(chunk, T1, extended)
        per, period = periodic_tail(syms, TAIL1, PMAX)
        nonperiodic.extend(int(r) for r in chunk[~per])
        for r, p in zip(chunk[per], period[per]):
            periods[int(p)] = periods.get(int(p), 0) + 1
    rhos = {}
    flagged = []
    if nonperiodic:
        syms = simulate(nonperiodic, T2, extended)
        for i, r in enumerate(nonperiodic):
            v = rho(syms[i, T2 // 2:], alphabet)
            rhos[r] = v
            if v > tau:
                flagged.append(r)
    confirmed = []
    rhos3 = {}
    if flagged:
        syms = simulate(flagged, T3, extended)
        for i, r in enumerate(flagged):
            v = rho(syms[i, T3 // 2:], alphabet)
            rhos3[r] = v
            if v > tau:
                confirmed.append(r)
    return {"n_rules": len(rules), "n_nonperiodic_stage1": len(nonperiodic),
            "period_histogram_stage1": periods,
            "nonperiodic_rules": nonperiodic if len(nonperiodic) <= 500 else nonperiodic[:500],
            "rho_stage2": {str(k): round(v, 4) for k, v in rhos.items()},
            "max_rho_stage2": max(rhos.values()) if rhos else None,
            "flagged_stage2": flagged, "rho_stage3": {str(k): round(v, 4) for k, v in rhos3.items()},
            "complex_confirmed": confirmed}


def main():
    rng = np.random.default_rng(SEED)
    cal4 = calibrate(4, rng)
    cal16 = calibrate(16, rng)
    print("calibration 4:", json.dumps(cal4, indent=None))
    print("calibration 16:", json.dumps(cal16, indent=None))
    if not (cal4["separated"] and cal16["separated"]):
        verdict = "inconclusive"
        basic = ext = None
    else:
        basic = classify(np.arange(65536, dtype=np.uint64), False, 4, cal4["tau"])
        ext_rules = rng.integers(0, 2 ** 32, N_EXT, dtype=np.uint64)
        ext = classify(ext_rules, True, 16, cal16["tau"])
        n_complex_basic = len(basic["complex_confirmed"])
        frac_ext = len(ext["complex_confirmed"]) / N_EXT
        if n_complex_basic > 0:
            verdict = "refutes"
        elif frac_ext <= 0.01:
            verdict = "supports"
        else:
            verdict = "mixed"

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump({"calibration_4": cal4, "calibration_16": cal16, "basic": basic, "extended": ext}, f, indent=1)

    if basic is None:
        print(json.dumps({"verdict": verdict}))
        return
    measured = {
        "value": {"basic_rules_complex": len(basic["complex_confirmed"]),
                  "basic_rules_nonperiodic_2000_steps": basic["n_nonperiodic_stage1"],
                  "extended_sample_complex_fraction": round(len(ext["complex_confirmed"]) / N_EXT, 5)},
        "unit": "rule counts; fraction of 100000 sampled extended rules",
        "n": {"basic_rules": 65536, "extended_sample": N_EXT},
        "uncertainty": "basic family exhaustive; extended fraction has binomial sampling error",
        "extra": {"tau_4": round(cal4["tau"], 4), "tau_16": round(cal16["tau"], 4),
                  "calibration_4": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in cal4.items() if isinstance(v, dict)},
                  "calibration_16": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in cal16.items() if isinstance(v, dict)},
                  "basic_max_rho_stage2": basic["max_rho_stage2"],
                  "basic_flagged_stage2": basic["flagged_stage2"],
                  "basic_rho_stage3": basic["rho_stage3"],
                  "extended_nonperiodic_2000_steps": ext["n_nonperiodic_stage1"],
                  "extended_max_rho_stage2": ext["max_rho_stage2"],
                  "extended_flagged_stage2": len(ext["flagged_stage2"]),
                  "extended_complex_confirmed": ext["complex_confirmed"][:50],
                  "extended_nested_or_slow_fraction": round((ext["n_nonperiodic_stage1"] - len(ext["complex_confirmed"])) / N_EXT, 5)},
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
