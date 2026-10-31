#!/usr/bin/env python3
"""Test of wolfram2002-ch05-07: neighbour-independent substitution systems always give
nested patterns.

For all 256 two-colour 2x2 rules and seeded samples of three-colour 2x2 and two-colour 3x3
rules, grows the pattern from a single cell and checks (1) the exact nesting identity
P_n = sigma^j(P_{n-j}) at every scale j, and (2) the block-complexity bound
N(k) <= s^4 b^2 k^2 for k = 4, 8. Neighbour-dependent rules and a random image are controls.

Run: python3 analysis.py   (needs numpy)
Writes derived/measured.json and prints it.
"""
import itertools
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
N_SAMPLE = 2000
KS = (4, 8)
HASH_MULT = np.uint64(0x9E3779B97F4A7C15)


def substitute(P, blocks):
    m = P.shape[0]
    b = blocks.shape[1]
    return blocks[P].transpose(0, 2, 1, 3).reshape(m * b, m * b)


def grow_indep(blocks, c, n):
    P = np.array([[c]], dtype=np.uint8)
    for _ in range(n):
        P = substitute(P, blocks)
    return P


def step_dep(P, rule):
    """rule: (8, 2, 2); context = 4*own + 2*right + below, outside = 0."""
    R = np.zeros_like(P)
    R[:, :-1] = P[:, 1:]
    D = np.zeros_like(P)
    D[:-1, :] = P[1:, :]
    ctx = 4 * P + 2 * R + D
    m = P.shape[0]
    return rule[ctx].transpose(0, 2, 1, 3).reshape(2 * m, 2 * m)


def grow_dep(rule, c, n):
    P = np.array([[c]], dtype=np.uint8)
    for _ in range(n):
        P = step_dep(P, rule)
    return P


def nesting_ok(grow, s, n):
    Pn = grow(1, n)
    for j in range(1, n):
        Bj = np.stack([grow(c, j) for c in range(s)])
        if not np.array_equal(substitute(grow(1, n - j), Bj), Pn):
            return False, j
    return True, None


def n_distinct(P, k, s):
    bpc = 1 if s == 2 else 2
    H, W = P.shape
    p = P.astype(np.uint64)
    rc = np.zeros((H, W - k + 1), dtype=np.uint64)
    for d in range(k):
        rc |= p[:, d:d + W - k + 1] << np.uint64(bpc * d)
    exact = bpc * k * k <= 64
    mult = np.uint64(1 << (bpc * k)) if exact and bpc * k < 64 else HASH_MULT
    h = np.zeros((H - k + 1, W - k + 1), dtype=np.uint64)
    with np.errstate(over="ignore"):
        for d in range(k):
            h = h * mult + rc[d:d + H - k + 1]
    return int(np.unique(h).size), exact


def bound(s, b, k):
    return s ** 4 * b * b * k * k


def evaluate(grow, s, b, n):
    ok, bad_j = nesting_ok(grow, s, n)
    P = grow(1, n)
    Nk, within, hashed = {}, True, False
    for k in KS:
        v, exact = n_distinct(P, k, s)
        Nk[k] = v
        hashed |= not exact
        within &= v <= bound(s, b, k)
    return {"nesting_ok": ok, "first_failing_j": bad_j, "N": Nk, "within_bound": within,
            "hashed": hashed, "density_nonzero": float((P > 0).mean())}


def family_summary(results, s, b):
    return {"n_rules": len(results),
            "n_nesting_fail": sum(not r["nesting_ok"] for r in results),
            "n_bound_fail": sum(not r["within_bound"] for r in results),
            "max_N4": max(r["N"][4] for r in results), "bound_N4": bound(s, b, 4),
            "max_N8": max(r["N"][8] for r in results), "bound_N8": bound(s, b, 8),
            "max_N8_over_bound": round(max(r["N"][8] for r in results) / bound(s, b, 8), 4),
            "n_nontrivial": sum(0.0 < r["density_nonzero"] < 1.0 for r in results),
            "hashed_counts": any(r["hashed"] for r in results)}


def main():
    rng = np.random.default_rng(SEED)
    out = {"seed": SEED, "n_sample": N_SAMPLE, "ks": list(KS)}
    t0 = time.time()

    all_blocks_2 = np.array(list(itertools.product([0, 1], repeat=4)), dtype=np.uint8).reshape(16, 2, 2)
    F1 = [np.stack([all_blocks_2[i], all_blocks_2[j]]) for i in range(16) for j in range(16)]
    F2 = [rng.integers(0, 3, size=(3, 2, 2), dtype=np.uint8) for _ in range(N_SAMPLE)]
    F3 = [rng.integers(0, 2, size=(2, 3, 3), dtype=np.uint8) for _ in range(N_SAMPLE)]
    fams = {"F1_2colour_2x2_all": (F1, 2, 2, 9), "F2_3colour_2x2_sample": (F2, 3, 2, 9),
            "F3_2colour_3x3_sample": (F3, 2, 3, 6)}
    verdict_fail = 0
    for name, (rules, s, b, n) in fams.items():
        res = [evaluate(lambda c, m, B=B: grow_indep(B, c, m), s, b, n) for B in rules]
        out[name] = family_summary(res, s, b)
        verdict_fail += sum(1 for r in res if not r["within_bound"] or not r["nesting_ok"])
        print(name, json.dumps(out[name]), round(time.time() - t0, 1))

    ctrl_rules = [rng.integers(0, 2, size=(8, 2, 2), dtype=np.uint8) for _ in range(N_SAMPLE)]
    cres = [evaluate(lambda c, m, R=R: grow_dep(R, c, m), 2, 2, 9) for R in ctrl_rules]
    cs = family_summary(cres, 2, 2)
    cs["n_flagged"] = sum(1 for r in cres if not r["nesting_ok"] or not r["within_bound"])
    out["control_neighbour_dependent"] = cs
    print("control", json.dumps(cs))

    img = (rng.random((512, 512)) < 0.5).astype(np.uint8)
    rn = {k: n_distinct(img, k, 2)[0] for k in KS}
    out["control_bernoulli_image"] = {"N": rn, "bound": {k: bound(2, 2, k) for k in KS},
                                      "flagged": any(rn[k] > bound(2, 2, k) for k in KS)}
    controls_ok = cs["n_flagged"] >= 20 and out["control_bernoulli_image"]["flagged"]
    if not controls_ok:
        verdict = "inconclusive"
    elif verdict_fail > 0:
        verdict = "refutes"
    else:
        verdict = "supports"
    out["summary"] = {"neighbour_independent_rules": sum(len(f[0]) for f in fams.values()),
                      "neighbour_independent_failures": verdict_fail, "controls_ok": controls_ok,
                      "verdict_by_rule": verdict, "seconds": round(time.time() - t0, 1)}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("control_bernoulli_image", "summary")}, indent=1))


if __name__ == "__main__":
    main()
