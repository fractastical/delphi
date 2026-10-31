#!/usr/bin/env python3
"""Test of wolfram2002-ch11-27: Wolfram's 2-state 5-colour Turing machine emulates rule 110.

Rule table transcribed from NKS p. 707, figure "The rule for the simplest Turing machine
currently known to be universal" (fig-a.png).  Colours: white=0, grey levels 204,153,102,51 =
1,2,3,4.  States: up-pointing head = 1, down-pointing head = 2.  Each case maps
(state, colour) -> (new colour, new state, move), move -1 = left, +1 = right.

Initial condition from NKS note p. 1119 ("Rule 110 Turing machines"): the tape is
Prepend[4 list, 0] with 1's on the left and 0's on the right.  The head position is not given
in the note; the p. 707 figure shows it on the first white cell to the right of the data, and
that is the start used here (state 1).  The pre-registration guessed "head on the first tape
element"; that variant is also run (START_VARIANTS) and reported, see result.json caveats.

Snapshots are taken whenever the head reaches a position further right than ever before
(the convention of Wolfram's compressed picture).
"""
import hashlib
import json
import sys

import numpy as np

RULE = {
    (1, 0): (1, 1, -1), (1, 1): (0, 1, 1), (1, 2): (0, 1, 1), (1, 3): (4, 2, 1), (1, 4): (3, 2, -1),
    (2, 0): (3, 1, -1), (2, 1): (0, 1, 1), (2, 2): (4, 1, 1), (2, 3): (4, 2, 1), (2, 4): (2, 2, -1),
}
START_VARIANTS = {
    "figure: head on first white cell right of the data, state 1": ("after_data", 1),
    "pre-registration guess: head on the prepended 0, state 1": ("prepended", 1),
    "pre-registration guess: head on the prepended 0, state 2": ("prepended", 2),
}
NSWEEPS = 200
NRANDOM = 40
K_MIN = 2        # snapshots 0 and 1 are the initial tape and the first partial sweep
FIG_URL = "https://www.wolframscience.com/nks/pages/p707--universality-in-turing-machines-and-other-systems/fig-a.png"


def rule110_step(row):
    l = np.concatenate([[0], row[:-1]])
    r = np.concatenate([row[1:], [0]])
    idx = (l.astype(int) << 2) | (row.astype(int) << 1) | r
    return ((110 >> idx) & 1).astype(np.uint8)


def run_tm(init_list, nsweeps, start=("after_data", 1)):
    """Return (snapshots, x0) where snapshots[k] is the tape at the k-th new-rightmost moment
    (k = 0 is the initial tape) and x0 is the tape index of the first list element."""
    n = len(init_list)
    left = nsweeps + 8
    right = nsweeps + 8
    tape = np.concatenate([np.ones(left, int), [0], 4 * np.asarray(init_list, int), np.zeros(right, int)])
    x0 = left + 1
    pos = x0 + n if start[0] == "after_data" else left
    state = start[1]
    maxright = pos
    snaps = [tape.copy()]
    steps = 0
    while len(snaps) <= nsweeps:
        c = tape[pos]
        nc, ns, d = RULE[(state, c)]
        tape[pos] = nc
        state = ns
        pos += d
        steps += 1
        if pos > maxright:
            maxright = pos
            snaps.append(tape.copy())
        if pos <= 0 or pos >= tape.size - 1:
            raise RuntimeError("head left the allocated tape")
    return snaps, x0, steps


def compare(init_list, nsweeps, offset, shift, start):
    """Compare snapshot k (k >= K_MIN) with rule-110 iterate k - offset, displaced by `shift`
    cells, over the whole rule-110 pattern plus a 3-cell margin on each side."""
    snaps, x0, steps = run_tm(init_list, nsweeps, start)
    n = len(init_list)
    W = snaps[0].size
    ca = np.zeros(W, np.uint8)
    ca[x0:x0 + n] = init_list
    matches = 0
    total = 0
    first_mismatch = None
    for it in range(K_MIN - offset):
        ca = rule110_step(ca)
    for k in range(K_MIN, nsweeps + 1):
        it = k - offset
        lo = max(0, x0 - it - 3)
        hi = min(W, x0 + n + 3)
        dec = (snaps[k][lo + shift:hi + shift] == 4).astype(np.uint8)
        ok = np.array_equal(dec, ca[lo:hi])
        total += 1
        matches += ok
        if not ok and first_mismatch is None:
            first_mismatch = {"snapshot": k, "iterate": it}
        ca = rule110_step(ca)
    return {"n_snapshots_compared": total, "n_matching": matches, "first_mismatch": first_mismatch, "tm_steps": steps}


def find_offset(start):
    """Time offset c and spatial shift sigma such that snapshot k == iterate k-c displaced by
    sigma cells, for all k in K_MIN..30 of the single-cell run."""
    snaps, x0, _ = run_tm([1], 30, start)
    W = snaps[0].size
    ca = np.zeros(W, np.uint8)
    ca[x0] = 1
    its = [ca]
    for _ in range(40):
        its.append(rule110_step(its[-1]))
    for c in range(0, 10):
        for sigma in range(-3, 4):
            ok = True
            for k in range(K_MIN, 31):
                if k - c < 0:
                    ok = False
                    break
                dec = (snaps[k] == 4).astype(np.uint8)
                if not np.array_equal(dec[5:W - 5], its[k - c][5 - sigma:W - 5 - sigma]):
                    ok = False
                    break
            if ok:
                return c, sigma
    return None


def fig_hash():
    try:
        import requests
        r = requests.get(FIG_URL, timeout=30)
        r.raise_for_status()
        return {"url": FIG_URL, "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    except Exception as e:  # network optional
        return {"url": FIG_URL, "error": str(e)}


def test_variant(start):
    found = find_offset(start)
    out = {"offset_and_shift": found, "first_snapshot_compared": K_MIN}
    if found is None:
        out.update({"n_snapshot_comparisons": 0, "n_matching": 0, "note": "single-cell run does not match rule 110"})
        return out
    results = []
    offset, shift = found
    res = compare([1], NSWEEPS, offset, shift, start)
    res["init"] = "single cell"
    results.append(res)
    for seed in range(NRANDOM):
        rng = np.random.default_rng(seed)
        n = int(rng.integers(10, 61))
        init = rng.integers(0, 2, n).tolist()
        res = compare(init, NSWEEPS, offset, shift, start)
        res["init"] = "seed %d, length %d" % (seed, n)
        results.append(res)
    total = sum(r["n_snapshots_compared"] for r in results)
    match = sum(r["n_matching"] for r in results)
    out.update({
        "n_initial_lists": len(results),
        "n_snapshot_comparisons": total,
        "n_matching": match,
        "fraction_matching": match / total,
        "n_lists_with_mismatch": sum(1 for r in results if r["first_mismatch"] is not None),
        "example_mismatches": [r for r in results if r["first_mismatch"] is not None][:3],
        "tm_steps_per_run_min_max": [min(r["tm_steps"] for r in results), max(r["tm_steps"] for r in results)],
    })
    return out


def main():
    states = sorted({k[0] for k in RULE} | {v[1] for v in RULE.values()})
    colours = sorted({k[1] for k in RULE} | {v[0] for v in RULE.values()})
    out = {"n_states": len(states), "n_colours": len(colours), "n_cases": len(RULE), "variants": {}}
    for name, start in START_VARIANTS.items():
        out["variants"][name] = test_variant(start)
    main_v = out["variants"]["figure: head on first white cell right of the data, state 1"]
    out["verdict"] = ("supports" if main_v["n_snapshot_comparisons"] > 0
                      and main_v["n_matching"] == main_v["n_snapshot_comparisons"] else "refutes")
    out["figure"] = fig_hash()
    out["rule_table"] = {"%d,%d" % k: list(v) for k, v in sorted(RULE.items())}
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
