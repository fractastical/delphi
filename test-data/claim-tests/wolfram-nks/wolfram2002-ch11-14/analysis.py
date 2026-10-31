#!/usr/bin/env python3
"""Component test for wolfram2002-ch11-14 (rule 110 universality): does rule 110
naturally produce the ether and the gliders, with the space-time periods tabulated
by Cook (2004, Figure 5), that the universality construction is built from?

Run: python3 analysis.py   (needs numpy, requests)
"""
import datetime
import hashlib
import json
import os
from collections import Counter

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
WIDTH = 1200
T = 4000
N_RUNS = 60
SAMPLE_ROWS = list(range(3000, 3901, 100))
MAX_STRUCT_WIDTH = 60
P_MAX = 100
S_MAX = 50
MARGIN = 14
COOK_PDF = "https://content.wolfram.com/sites/13/2023/02/15-1-1.pdf"
# Cook 2004, Figure 5: (time, horizontal displacement) period of each glider class
COOK = {"A": (3, 2), "B": (4, -2), "Bbar/Bhat": (12, -6), "C": (7, 0), "D": (10, 2),
        "E": (15, -4), "Ebar": (30, -8), "F": (36, -4), "G": (42, -14), "H": (92, -18)}
RULE = 110


def evolve(rule, init, steps):
    table = np.array([(rule >> k) & 1 for k in range(8)], dtype=np.uint8)
    grid = np.zeros((steps + 1, len(init)), dtype=np.uint8)
    row = init.copy()
    grid[0] = row
    for t in range(1, steps + 1):
        row = table[(np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1)]
        grid[t] = row
    return grid


def ether_mask(grid, t):
    """Cells x at time t whose 7 x 14 neighbourhood (rows t..t+6, columns x-7..x+6)
    is invariant under (t, x) -> (t + 1, x - 4)."""
    ok = np.ones(grid.shape[1], dtype=bool)
    for i in range(7):
        a = grid[t + i]
        b = np.roll(grid[t + i + 1], 4)  # b[x] = grid[t+i+1, x-4]
        eq = a == b
        for dx in range(-7, 7):
            ok &= np.roll(eq, -dx)
    return ok


def structures(mask):
    """Maximal runs of non-ether cells on the ring, as (start, width)."""
    non = ~mask
    if non.all() or not non.any():
        return []
    n = len(non)
    # rotate so that position 0 is ether
    k = int(np.argmax(mask))
    r = np.roll(non, -k)
    d = np.diff(np.concatenate([[0], r.astype(np.int8), [0]]))
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]
    return [((int(s) + k) % n, int(e - s)) for s, e in zip(starts, ends)]


def find_period(grid, t, start, width):
    n = grid.shape[1]
    xs = (np.arange(start - MARGIN, start + width + MARGIN)) % n
    ref = grid[t, xs]
    # also require the next few rows to match, to avoid accidental single-row matches
    ref_block = np.stack([grid[t + i, xs] for i in range(3)])
    for P in range(1, P_MAX + 1):
        # |s| <= P: a displacement faster than one cell per step cannot be a period of a
        # single structure (it would be a match with a neighbouring identical glider)
        for s in sorted(range(-min(S_MAX, P), min(S_MAX, P) + 1), key=abs):
            if not np.array_equal(grid[t + P, (xs + s) % n], ref):
                continue
            blk = np.stack([grid[t + P + i, (xs + s) % n] for i in range(3)])
            if not np.array_equal(blk, ref_block):
                continue
            # a genuine period repeats again one period later
            blk2 = np.stack([grid[t + 2 * P + i, (xs + 2 * s) % n] for i in range(3)])
            if np.array_equal(blk2, ref_block):
                return P, s
    return None


def is_combination(P, s):
    """Positive integer combination a*(3,2) + b*(4,-2) with a, b >= 0, not both 0."""
    for a in range(0, P // 3 + 1):
        rem = P - 3 * a
        if rem % 4:
            continue
        b = rem // 4
        if 2 * a - 2 * b == s and (a or b):
            return a, b
    return None


def classify(P, s):
    """Exact match of the minimal period to a table entry first (so a minimal period of
    (30, -8) is an E-bar, not two E periods), then integer multiples (packets)."""
    for name, (pt, px) in COOK.items():
        if (pt, px) == (P, s):
            return name
    for name, (pt, px) in COOK.items():
        if P % pt == 0 and px * (P // pt) == s:
            return name + "-multiple"
    return None


def main():
    rng = np.random.default_rng(SEED)
    t_fetch = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(COOK_PDF, timeout=120)
    r.raise_for_status()
    pdf_meta = {"download_url": COOK_PDF, "retrieved_at": t_fetch, "byte_size": len(r.content),
                "sha256": hashlib.sha256(r.content).hexdigest()}

    ether_fraction = []
    n_struct = 0
    not_isolated = 0
    resolved = Counter()
    unresolved = 0
    classes = Counter()
    non_cook = Counter()
    non_lattice = Counter()
    for run in range(N_RUNS):
        init = rng.integers(0, 2, WIDTH).astype(np.uint8)
        grid = evolve(RULE, init, T + 2 * P_MAX + 8)
        fr = []
        for t in SAMPLE_ROWS:
            mask = ether_mask(grid, t)
            fr.append(float(mask.mean()))
            for start, width in structures(mask):
                if width > MAX_STRUCT_WIDTH:
                    continue
                n_struct += 1
                margin_idx = np.concatenate([np.arange(start - MARGIN, start),
                                             np.arange(start + width, start + width + MARGIN)]) % WIDTH
                if not mask[margin_idx].all():
                    not_isolated += 1
                    continue
                per = find_period(grid, t, start, width)
                if per is None:
                    unresolved += 1
                    continue
                resolved[per] += 1
                c = classify(*per)
                if c is None:
                    non_cook[per] += 1
                else:
                    classes[c] += 1
                if is_combination(*per) is None:
                    non_lattice[per] += 1
        ether_fraction.append(min(fr))
        print(run, "min ether fraction %.3f" % min(fr), "structures so far", n_struct,
              "resolved", sum(resolved.values()), flush=True)

    res = {
        "runs": N_RUNS, "ring_width": WIDTH, "steps": T, "sample_rows": SAMPLE_ROWS,
        "min_ether_fraction_per_run_min": min(ether_fraction),
        "min_ether_fraction_per_run_median": float(np.median(ether_fraction)),
        "runs_with_ether_fraction_below_0.5": int(sum(1 for f in ether_fraction if f <= 0.5)),
        "structures": n_struct, "not_isolated": not_isolated,
        "isolated": n_struct - not_isolated,
        "resolved": int(sum(resolved.values())), "unresolved": unresolved,
        "resolved_fraction_of_isolated": round(sum(resolved.values()) / (n_struct - not_isolated), 4)
        if n_struct > not_isolated else None,
        "periods_found": {"%d,%d" % k: v for k, v in sorted(resolved.items())},
        "classes": dict(classes),
        "periods_not_matching_cook_table": {"%d,%d" % k: v for k, v in non_cook.items()},
        "periods_not_on_AB_lattice": {"%d,%d" % k: v for k, v in non_lattice.items()},
        "cook_table": {k: list(v) for k, v in COOK.items()},
        "cook_pdf": pdf_meta,
    }
    print(json.dumps(res, indent=1))
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
