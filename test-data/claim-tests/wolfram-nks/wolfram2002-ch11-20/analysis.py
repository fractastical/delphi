#!/usr/bin/env python3
"""Test of wolfram2002-ch11-20: power-of-two-step superposition property of additive elementary
cellular automata, additivity screens over all 256 rules, non-additivity of class-3/4 control rules
at every power-of-two step, and OEIS cross-check of the nested single-cell patterns of rules 90 and 150.
Writes derived/measurements.json.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
LINEAR = [0, 60, 90, 102, 150, 170, 204, 240]
AFFINE_COMPLEMENTS = [255 - r for r in LINEAR]
CONTROLS = [18, 22, 30, 45, 54, 73, 110, 122]
KMAX_SUPERPOSITION = 10
KMAX_CONTROL = 8
N_SCREEN = 256
N_SUPER = [1023, 2048]
N_IC = 20
T_PATTERN = 4095
OEIS = {"A001316": "https://oeis.org/A001316/b001316.txt", "A071053": "https://oeis.org/A071053/b071053.txt"}


def step(x, rule):
    """One step of elementary rule `rule` on a cyclic lattice. Cell i reads (x[i-1], x[i], x[i+1])."""
    left, right = np.roll(x, 1), np.roll(x, -1)
    idx = (left << 2) | (x << 1) | right
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    return table[idx]


def evolve(x, rule, steps):
    for _ in range(steps):
        x = step(x, rule)
    return x


def support(rule):
    """Offsets d such that the one-step response to a single 1 at the origin is 1 at position d."""
    x = np.zeros(8, np.uint8)
    x[4] = 1
    y = step(x, rule)
    return [int(i) - 4 for i in np.flatnonzero(y)]


def superposition(x, offsets, scale):
    y = np.zeros_like(x)
    for d in offsets:
        y ^= np.roll(x, d * scale)  # np.roll(x, s)[i] = x[i - s]; a response at offset d comes from cell i - d
    return y


def check_superposition(rng):
    out = {}
    for rule in LINEAR:
        offs = support(rule)
        n_checked = n_fail = 0
        for N in N_SUPER:
            ics = [rng.integers(0, 2, N, dtype=np.uint8) for _ in range(N_IC)]
            single = np.zeros(N, np.uint8)
            single[N // 2] = 1
            ics.append(single)
            for x0 in ics:
                x = x0.copy()
                t = 0
                for k in range(KMAX_SUPERPOSITION + 1):
                    x = evolve(x, rule, 2 ** k - t)
                    t = 2 ** k
                    n_checked += 1
                    if not np.array_equal(x, superposition(x0, offs, 2 ** k)):
                        n_fail += 1
        out[rule] = {"support": offs, "n_checked": n_checked, "n_fail": n_fail}
    return out


def additivity_screen(rng):
    pairs = [(rng.integers(0, 2, N_SCREEN, dtype=np.uint8), rng.integers(0, 2, N_SCREEN, dtype=np.uint8)) for _ in range(200)]
    zero = np.zeros(N_SCREEN, np.uint8)
    linear, affine = [], []
    for rule in range(256):
        t0 = step(zero, rule)
        lin = all(np.array_equal(step(x ^ y, rule), step(x, rule) ^ step(y, rule)) for x, y in pairs)
        aff = all(np.array_equal(step(x ^ y, rule), step(x, rule) ^ step(y, rule) ^ t0) for x, y in pairs)
        if lin:
            linear.append(rule)
        if aff:
            affine.append(rule)
    return {"linear_rules_found": linear, "affine_rules_found": affine,
            "linear_matches_expected": linear == sorted(LINEAR), "affine_matches_expected": affine == sorted(LINEAR + AFFINE_COMPLEMENTS)}


def control_nonadditivity(rng):
    pairs = [(rng.integers(0, 2, N_SCREEN, dtype=np.uint8), rng.integers(0, 2, N_SCREEN, dtype=np.uint8)) for _ in range(50)]
    out = {}
    for rule in CONTROLS:
        failing_pairs_per_k = {}
        for k in range(KMAX_CONTROL + 1):
            s = 2 ** k
            n_fail = sum(not np.array_equal(evolve(x ^ y, rule, s), evolve(x, rule, s) ^ evolve(y, rule, s)) for x, y in pairs)
            failing_pairs_per_k[k] = int(n_fail)
        out[rule] = {"nonadditive_pairs_of_50_per_k": failing_pairs_per_k, "nonadditive_at_every_k": all(v > 0 for v in failing_pairs_per_k.values())}
    return out


def row_populations(rule, T):
    N = 2 * T + 3
    x = np.zeros(N, np.uint8)
    x[N // 2] = 1
    pops = [int(x.sum())]
    for _ in range(T):
        x = step(x, rule)
        pops.append(int(x.sum()))
    return pops


def fetch_bfile(seq):
    import requests
    url = OEIS[seq]
    r = requests.get(url, timeout=60, headers={"User-Agent": "delphi-claim-tests/1.0"})
    r.raise_for_status()
    raw = r.content
    terms = {}
    for line in raw.decode().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        n, v = line.split()[:2]
        terms[int(n)] = int(v)
    return terms, {"download_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "n_terms": len(terms)}


def oeis_check():
    out = {}
    for rule, seq in ((90, "A001316"), (150, "A071053")):
        pops = row_populations(rule, T_PATTERN)
        try:
            terms, meta = fetch_bfile(seq)
        except Exception as e:  # network failure -> data-unavailable for this part
            out[seq] = {"rule": rule, "status": "data-unavailable", "error": str(e)[:200]}
            continue
        compared = [t for t in range(T_PATTERN + 1) if t in terms]
        mism = [t for t in compared if terms[t] != pops[t]]
        out[seq] = {"rule": rule, "status": "ok", "file": meta, "n_compared": len(compared), "n_mismatch": len(mism),
                    "first_mismatches": mism[:5], "first_16_populations": pops[:16]}
    return out


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    res = {"superposition": check_superposition(rng)}
    print("superposition:", res["superposition"], flush=True)
    res["additivity_screen"] = additivity_screen(rng)
    print("screen:", res["additivity_screen"], flush=True)
    res["controls"] = control_nonadditivity(rng)
    print("controls:", {r: v["nonadditive_at_every_k"] for r, v in res["controls"].items()}, flush=True)
    res["oeis"] = oeis_check()
    print("oeis:", {k: (v["status"], v.get("n_compared"), v.get("n_mismatch")) for k, v in res["oeis"].items()}, flush=True)
    a = all(v["n_fail"] == 0 for v in res["superposition"].values())
    b = res["additivity_screen"]["linear_matches_expected"] and res["additivity_screen"]["affine_matches_expected"]
    c = all(v["nonadditive_at_every_k"] for v in res["controls"].values())
    d_avail = all(v["status"] == "ok" for v in res["oeis"].values())
    d = d_avail and all(v["n_mismatch"] == 0 for v in res["oeis"].values())
    res["criteria"] = {"a_superposition_exact": a, "b_screen_identifies_exactly_additive_rules": b, "c_controls_nonadditive_every_k": c,
                       "d_oeis_match": d, "d_data_available": d_avail}
    if not a or (d_avail and not d):
        verdict = "refutes"
    elif a and (d or not d_avail) and b and c:
        verdict = "supports"
    else:
        verdict = "mixed"
    res["verdict"] = verdict
    res["seconds"] = time.time() - t0
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("criteria", "verdict", "seconds")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
