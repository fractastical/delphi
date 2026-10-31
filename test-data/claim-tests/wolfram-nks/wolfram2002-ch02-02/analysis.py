#!/usr/bin/env python3
"""Test of wolfram2002-ch02-02: rule 30 from a single black cell is irregular and complex
(not uniform, repetitive or nested, and essentially incompressible) in its interior.

Run: python3 analysis.py   (needs numpy; standard-library lzma and bz2)
Writes derived/measured.json and prints it.
"""
import bz2
import json
import lzma
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 4096
SEED = 20261031
P_MAX = 64


def eca(rule, T):
    """Rows t = 0..T-1 of elementary CA `rule` from one black cell; column index = x + T."""
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    W = 2 * T + 1
    out = np.zeros((T, W), dtype=np.uint8)
    out[0, T] = 1
    row = out[0].copy()
    for t in range(1, T):
        pad = np.concatenate([[0], row, [0]])
        row = table[4 * pad[:-2] + 2 * pad[1:-1] + pad[2:]]
        out[t] = row
    return out


def window(P, t0, t1, half):
    return P[t0:t1, T - half:T + half + 1]


def shift_agreement(P):
    """Max over 1<=p<=P_MAX, |s|<=p of fraction of cells in rows [3072,4095], |x|<=512
    with a(t,x) = a(t-p, x-s)."""
    t0, t1, half = 3 * T // 4, T, T // 8
    ref = window(P, t0, t1, half)
    best, arg = 0.0, None
    for p in range(1, P_MAX + 1):
        for s in range(-p, p + 1):
            other = P[t0 - p:t1 - p, T - half - s:T + half + 1 - s]
            a = float((ref == other).mean())
            if a > best:
                best, arg = a, (p, s)
    return best, arg


def decimation_agreement(P):
    """Max over k in {2,3}, offsets (a,b) of agreement of a(k t + a, k x + b) with a(t, x),
    t in [T/(2k), T/k), |x| <= T/(4k)."""
    res = {}
    for k in (2, 3):
        t_lo, t_hi, half = T // (2 * k), T // k, T // (4 * k)
        ts = np.arange(t_lo, t_hi)
        xs = np.arange(-half, half + 1)
        small = P[np.ix_(ts, xs + T)]
        best, arg = 0.0, None
        for a in range(k):
            for b in range(k):
                big = P[np.ix_(k * ts + a, k * xs + b + T)]
                v = float((big == small).mean())
                if v > best:
                    best, arg = v, (a, b)
        res[k] = {"agreement": round(best, 4), "offset": arg}
    return max(v["agreement"] for v in res.values()), res


def comp_sizes(bits2d):
    raw = np.packbits(bits2d.ravel()).tobytes()
    return {"raw": len(raw),
            "lzma": len(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME)),
            "bz2": len(bz2.compress(raw, 9))}


def analyse(rule, rng):
    P = eca(rule, T)
    W = window(P, T // 2, T, T // 4)
    dens = float(W.mean())
    a_rep, arg_rep = shift_agreement(P)
    a_nest, nest = decimation_agreement(P)
    cs = comp_sizes(W)
    ctrl = (rng.random(W.shape) < dens).astype(np.uint8)
    cc = comp_sizes(ctrl)
    return {"rule": rule, "window_shape": list(W.shape), "black_fraction": round(dens, 4),
            "A_rep": round(a_rep, 4), "A_rep_argmax_p_s": arg_rep,
            "A_nest": round(a_nest, 4), "decimation": nest,
            "sizes": cs, "bernoulli_control_sizes": cc,
            "lzma_norm": round(cs["lzma"] / cc["lzma"], 4),
            "bz2_norm": round(cs["bz2"] / cc["bz2"], 4)}


def main():
    rng = np.random.default_rng(SEED)
    out = {"T": T, "seed": SEED}
    for rule in (30, 50, 90):
        out[f"rule{rule}"] = analyse(rule, rng)
        print(json.dumps(out[f"rule{rule}"]))
    r30 = out["rule30"]
    shape = tuple(r30["window_shape"])
    c1 = comp_sizes((rng.random(shape) < r30["black_fraction"]).astype(np.uint8))
    c2 = comp_sizes((rng.random(shape) < r30["black_fraction"]).astype(np.uint8))
    out["second_bernoulli_control"] = {"lzma_norm": round(c2["lzma"] / c1["lzma"], 4),
                                       "bz2_norm": round(c2["bz2"] / c1["bz2"], 4)}

    controls_ok = (out["rule50"]["A_rep"] >= 0.99 and out["rule90"]["A_nest"] >= 0.99
                   and out["rule50"]["lzma_norm"] <= 0.5 and out["rule90"]["lzma_norm"] <= 0.5
                   and all(0.97 <= v <= 1.03 for v in out["second_bernoulli_control"].values()))
    d, ar, an = r30["black_fraction"], r30["A_rep"], r30["A_nest"]
    ratios = (r30["lzma_norm"], r30["bz2_norm"])
    passes = {"0_not_uniform": 0.40 <= d <= 0.60, "1_not_repetitive": ar <= 0.75,
              "2_not_nested": an <= 0.60, "3_incompressible": min(ratios) >= 0.80}
    refuted = not (0.2 <= d <= 0.8) or ar >= 0.90 or an >= 0.90 or min(ratios) < 0.50
    if not controls_ok:
        verdict = "inconclusive"
    elif refuted:
        verdict = "refutes"
    elif all(passes.values()):
        verdict = "supports"
    else:
        verdict = "mixed"
    out["controls_ok"] = controls_ok
    out["pass_conditions"] = passes
    out["verdict_by_rule"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("second_bernoulli_control", "controls_ok", "pass_conditions", "verdict_by_rule")}, indent=1))


if __name__ == "__main__":
    main()
