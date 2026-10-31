#!/usr/bin/env python3
"""Test of wolfram2002-ch03-02: census of the 256 elementary cellular automata started
from a single black cell (about 2/3 fixed size, 1/3 growing, 14% more complicated than
repetition).

Run: python3 analysis.py   (needs numpy)
"""
import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 4096
T_SHORT = 2048
MARGIN = 32
P_MAX = 16
S_MAX = 16
EDGE = 16


def evolve(rule, steps, width):
    table = np.array([(rule >> k) & 1 for k in range(8)], dtype=np.uint8)
    grid = np.zeros((steps + 1, width), dtype=np.uint8)
    row = np.zeros(width, dtype=np.uint8)
    row[width // 2] = 1
    grid[0] = row
    for t in range(1, steps + 1):
        idx = (np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1)
        row = table[idx]
        grid[t] = row
    return grid


def widths(grid, centre):
    """Extent of cells differing from the uniform background in each row."""
    bg = grid[:, 0]  # column 0 is far outside the light cone, so it carries the background
    diff = grid != bg[:, None]
    any_diff = diff.any(axis=1)
    w = np.zeros(len(grid), dtype=np.int64)
    if any_diff.any():
        xs = np.arange(grid.shape[1])
        left = np.where(diff, xs[None, :], grid.shape[1]).min(axis=1)
        right = np.where(diff, xs[None, :], -1).max(axis=1)
        w[any_diff] = right[any_diff] - left[any_diff] + 1
    return w


def is_fixed_size(w, steps):
    return int(w[steps // 2:steps + 1].max()) == int(w[steps // 4:steps // 2 + 1].max())


def interior_mask(grid, t0, n, centre, mode):
    """Cells over which periodicity is required, for rows t0..t0+n-1.
    mode 'lightcone': |x| <= t - EDGE (as pre-registered).
    mode 'extent': inside the pattern's own extent at time t, minus EDGE cells on each
    side (needed for patterns that grow slower than one cell per step)."""
    xs = np.arange(grid.shape[1])
    ts = np.arange(t0, t0 + n)
    if mode == "lightcone":
        return np.abs(xs - centre)[None, :] <= (ts[:, None] - EDGE)
    bg = grid[:, 0]
    diff = grid[t0:t0 + n] != bg[t0:t0 + n, None]
    left = np.where(diff, xs[None, :], grid.shape[1]).min(axis=1) + EDGE
    right = np.where(diff, xs[None, :], -1).max(axis=1) - EDGE
    return (xs[None, :] >= left[:, None]) & (xs[None, :] <= right[:, None])


def find_periodicity(grid, steps, centre, mode):
    """Smallest (P, s) with grid[t+P, x+s] == grid[t, x] for all t in [steps/2, steps-P]
    and all x in the interior mask, or None."""
    t0 = steps // 2
    probe = 64
    mask_probe = interior_mask(grid, t0, probe, centre, mode)
    masks_full = {}
    for P in range(1, P_MAX + 1):
        for s in sorted(range(-S_MAX, S_MAX + 1), key=abs):
            # cheap probe on the first rows of the window
            A = grid[t0:t0 + probe]
            B = np.roll(grid[t0 + P:t0 + P + probe], -s, axis=1)
            if ((A != B) & mask_probe).any():
                continue
            n = steps - P - t0 + 1
            if n not in masks_full:
                masks_full[n] = interior_mask(grid, t0, n, centre, mode)
            A = grid[t0:t0 + n]
            B = np.roll(grid[t0 + P:t0 + P + n], -s, axis=1)
            if not ((A != B) & masks_full[n]).any():
                return P, s
    return None


def classify(grid, steps, centre, mode):
    w = widths(grid[:steps + 1], centre)
    if is_fixed_size(w, steps):
        return "fixed", int(w[steps // 2:steps + 1].max()), None
    per = find_periodicity(grid, steps, centre, mode)
    if per is not None:
        return "repetitive", int(w[steps]), per
    return "complicated", int(w[steps]), None


def main():
    width = 2 * T + 2 * MARGIN
    centre = width // 2
    rows = []
    for rule in range(256):
        grid = evolve(rule, T, width)
        w = widths(grid, centre)
        row = {"rule": rule, "width_T1024": int(w[1024]), "width_T2048": int(w[T_SHORT]),
               "width_T4096": int(w[T]), "background_alternates": int(grid[1, 0] != grid[2, 0])}
        for mode in ("extent", "lightcone"):
            cls_long, _, per_long = classify(grid, T, centre, mode)
            cls_short, _, _ = classify(grid, T_SHORT, centre, mode)
            row["class_%s_T4096" % mode] = cls_long
            row["class_%s_T2048" % mode] = cls_short
            row["period_shift_%s_T4096" % mode] = "" if per_long is None else "%d,%d" % per_long
        rows.append(row)
        print(rule, row["class_extent_T4096"], row["class_lightcone_T4096"], row["width_T4096"],
              row["period_shift_extent_T4096"], flush=True)

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "eca_census.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    def share(cls, key):
        n = sum(1 for r in rows if r[key] == cls)
        return n, n / 256

    res = {"rules": 256, "T": T, "T_short": T_SHORT, "ring_width": width}
    for mode in ("extent", "lightcone"):
        for steps in (T, T_SHORT):
            key = "class_%s_T%d" % (mode, steps)
            fixed = share("fixed", key)
            rep = share("repetitive", key)
            comp = share("complicated", key)
            res[key] = {"fixed": fixed[0], "fixed_fraction": round(fixed[1], 4),
                        "growing": rep[0] + comp[0], "growing_fraction": round((rep[1] + comp[1]), 4),
                        "repetitive": rep[0], "complicated": comp[0],
                        "complicated_fraction": round(comp[1], 4)}
        res["rules_changing_class_between_T2048_and_T4096_%s" % mode] = [
            r["rule"] for r in rows if r["class_%s_T4096" % mode] != r["class_%s_T2048" % mode]]
        res["complicated_rules_T4096_%s" % mode] = [
            r["rule"] for r in rows if r["class_%s_T4096" % mode] == "complicated"]
    res["repetitive_rules_T4096_extent"] = [r["rule"] for r in rows if r["class_extent_T4096"] == "repetitive"]
    res["rules_classified_differently_by_mask"] = [
        r["rule"] for r in rows if r["class_extent_T4096"] != r["class_lightcone_T4096"]]
    # exploratory: Wolfram's 24 nested rules are the complicated rules outside the
    # equivalence classes of rules 30, 45 and 110 (random / complex behaviour)
    non_nested = {30, 86, 135, 149, 45, 75, 89, 101, 110, 124, 137, 193}
    res["complicated_rules_outside_classes_30_45_110_extent"] = [
        r for r in res["complicated_rules_T4096_extent"] if r not in non_nested]
    res["rule_225_width_T1024_T2048_T4096"] = [rows[225]["width_T1024"], rows[225]["width_T2048"],
                                               rows[225]["width_T4096"]]
    print(json.dumps(res, indent=1))
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
