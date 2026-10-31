#!/usr/bin/env python3
"""Test of wolfram2002-ch05-15: any satisfiable one-dimensional local constraint can be
satisfied by a purely repetitive (periodic) arrangement.

A constraint system is a set A of allowed words of length w over k colours (bitmask over
the k^w words). Two independent computations per system:
  (1) satisfiability: does a valid word of length 4V + w exist, V = k^(w-1)? Computed by
      iterating the reachability vector over the de Bruijn vertices (words of length
      w-1) for 4V + 1 edge steps; no cycle search is involved.
  (2) periodic solution: brute-force enumeration of all period words u with |u| <= V;
      u^infinity is a solution iff all its cyclic windows of length w are in A.
The claim predicts (1) <=> (2) with zero exceptions; the interesting direction is
(1) => (2).

Run: python3 analysis.py   (needs numpy)
"""
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
FAMILIES = [  # (k, w, number of sets or None for exhaustive)
    (2, 2, None), (2, 3, None), (2, 4, None), (3, 2, None), (4, 2, None),
    (2, 5, 2000), (3, 3, 5000),
]


def word_index(letters, k):
    x = 0
    for a in letters:
        x = x * k + a
    return x


def candidates(k, w, V):
    """All period words u with 1 <= |u| <= V: returns (window masks uint64, periods)."""
    masks, periods = [], []
    for p in range(1, V + 1):
        for idx in range(k ** p):
            u = [(idx // k ** (p - 1 - i)) % k for i in range(p)]
            m = 0
            for i in range(p):
                win = [u[(i + j) % p] for j in range(w)]
                m |= 1 << word_index(win, k)
            masks.append(m)
            periods.append(p)
    return np.array(masks, dtype=np.uint64), np.array(periods, dtype=np.int64)


def run_family(k, w, nsets, rng):
    t0 = time.time()
    W = k ** w
    V = k ** (w - 1)
    nbits = W
    if nsets is None:
        sets = np.arange(1 << nbits, dtype=np.uint64)
    else:
        if nbits >= 63:
            raise ValueError("mask too wide")
        sets = rng.integers(0, 1 << nbits, size=nsets, dtype=np.uint64)
    S = len(sets)
    xs = np.arange(W, dtype=np.int64)
    pre = xs // k
    suf = xs % V
    allowed = ((sets[:, None] >> xs.astype(np.uint64)[None, :]) & np.uint64(1)).astype(bool)  # (S, W)
    adj = np.zeros((S, V, V), dtype=bool)
    adj[:, pre, suf] = allowed
    # (1) reachability for E = 4V + 1 edges -> valid word of length 4V + w
    reach = np.ones((S, V), dtype=bool)
    E = 4 * V + 1
    for _ in range(E):
        reach = np.einsum("su,suv->sv", reach.astype(np.int64), adj.astype(np.int64)) > 0
    satisfiable = reach.any(axis=1)
    # (2) periodic solutions
    cmask, cper = candidates(k, w, V)
    not_allowed = ~sets  # complement masks (bits above W irrelevant because cmask only uses bits < W)
    has_periodic = np.zeros(S, dtype=bool)
    min_period = np.full(S, -1, dtype=np.int64)
    chunk = max(1, 20_000_000 // len(cmask))
    for i in range(0, S, chunk):
        na = not_allowed[i:i + chunk]
        ok = (cmask[None, :] & na[:, None]) == 0  # (chunk, C)
        has_periodic[i:i + chunk] = ok.any(axis=1)
        per = np.where(ok, cper[None, :], np.iinfo(np.int64).max).min(axis=1)
        min_period[i:i + chunk] = np.where(ok.any(axis=1), per, -1)
    viol_sat_no_periodic = int((satisfiable & ~has_periodic).sum())
    viol_periodic_not_sat = int((~satisfiable & has_periodic).sum())
    mp = min_period[has_periodic]
    hist = np.bincount(mp, minlength=V + 1)[1:].tolist() if len(mp) else []
    return {
        "k": k, "w": w, "V": V, "sets": S, "exhaustive": nsets is None,
        "satisfiable_sets_(valid_word_of_length_4V+w_exists)": int(satisfiable.sum()),
        "sets_with_periodic_solution_period_le_V": int(has_periodic.sum()),
        "violations_satisfiable_but_no_periodic_solution": viol_sat_no_periodic,
        "violations_periodic_solution_but_not_satisfiable": viol_periodic_not_sat,
        "max_minimal_period": int(mp.max()) if len(mp) else None,
        "minimal_period_histogram_1..V": hist,
        "seconds": round(time.time() - t0, 1),
    }


def main():
    rng = np.random.default_rng(SEED)
    fams = [run_family(k, w, n, rng) for (k, w, n) in FAMILIES]
    for f in fams:
        print(json.dumps(f))
    total_sets = sum(f["sets"] for f in fams)
    total_sat = sum(f["satisfiable_sets_(valid_word_of_length_4V+w_exists)"] for f in fams)
    v1 = sum(f["violations_satisfiable_but_no_periodic_solution"] for f in fams)
    v2 = sum(f["violations_periodic_solution_but_not_satisfiable"] for f in fams)
    out = {"constraint_systems": total_sets, "satisfiable_systems": total_sat,
           "satisfiable_without_periodic_solution": v1,
           "periodic_solution_without_satisfiability": v2,
           "fraction_satisfiable_with_periodic_solution": (total_sat - v1) / total_sat,
           "families": fams}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "families"}, indent=1))


if __name__ == "__main__":
    main()
