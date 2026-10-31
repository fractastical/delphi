#!/usr/bin/env python3
"""Test of wolfram2002-ch02-08: rule 110 from one black cell becomes periodic with
period 240 after about 2780 steps.

Part A (pre-registered primary test). Evolve rule 110 from a single black cell at x = 0
for T = 8000 steps; the pattern occupies x in [-t, 0]. For each P in 1..2000 test whether
a(t+P, x) = a(t, x) for all x in the light cone [-t, 0] over the last 2000 steps; report
the minimal such P and its onset, and the same on fixed right-edge windows [-W, 0].

Part B (diagnostics, added after Part A returned no full-cone period). The light cone
comparison necessarily fails at the leading edge (cells at x ~ -t are the edge at time t
but interior at t+P), so the P = 240 mismatch is recounted excluding the 300 cells
nearest the leading edge; the remaining mismatching cells are located, and their
cluster (the surviving localized structure) is tracked. For a window of +-40 and +-150
cells around the structure, the exact space-time period (P, s) with
a(t+P, x+s) = a(t, x) is searched, and the onset times of (i) the structure's periodic
regime, (ii) 240-periodicity of the right-edge windows and (iii) the drop of the
P = 240 mismatch count to its final level are measured. The lattice vectors of the
stripe region are also listed.

Run: python3 analysis.py   (needs numpy)
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RULE = 110
T = 8000
LEFT = 8010   # cells x = -LEFT .. RIGHT
RIGHT = 200
PMAX = 2000
TAIL = 2000   # the periodic relation must hold at least over the last TAIL steps
EDGE_EXCL = 300


def evolve(rule, steps, left, right):
    width = left + right + 1
    rule_bits = np.array([(rule >> k) & 1 for k in range(8)], dtype=np.uint8)
    row = np.zeros(width, dtype=np.uint8)
    row[left] = 1  # x = 0
    grid = np.zeros((steps, width), dtype=np.uint8)
    grid[0] = row
    for t in range(1, steps):
        l = np.concatenate(([0], row[:-1]))
        r = np.concatenate((row[1:], [0]))
        row = rule_bits[4 * l + 2 * row + r]
        grid[t] = row
    return grid


def cone_mismatch(grid, t, P, left, excl=0):
    """Cells x in [-t + excl, 0] where a(t+P, x) != a(t, x)."""
    lo = left - t + excl
    hi = left + 1
    return int((grid[t + P, lo:hi] != grid[t, lo:hi]).sum())


def window_mismatch(grid, t, P, left, W):
    lo = left - W
    hi = left + 1
    return int((grid[t + P, lo:hi] != grid[t, lo:hi]).sum())


def onset(grid, P, left, mismatch):
    """Smallest t0 such that mismatch(t, P) == 0 for all t in [t0, T-P-1]; None if
    even the last step mismatches."""
    last = T - P - 1
    if mismatch(grid, last, P, left) != 0:
        return None
    t = last
    while t - 1 >= 0 and mismatch(grid, t - 1, P, left) == 0:
        t -= 1
    return t


def structure_position(grid, t, left):
    """Median x of the cells (excluding the leading-edge zone) that differ between
    rows t and t+240; after the transient these are the surviving structure."""
    lo = left - t + EDGE_EXCL
    d = np.nonzero(grid[t + 240, lo:left + 1] != grid[t, lo:left + 1])[0] - t + EDGE_EXCL
    return int(round(float(np.median(d)))) if len(d) else None


def main():
    grid = evolve(RULE, T, LEFT, RIGHT)
    assert grid[:, 0].sum() == 0, "left boundary reached"
    assert grid[:, LEFT + 1:].sum() == 0, "cells right of the origin should stay white"
    first_rows = ["".join(str(int(c)) for c in grid[t, LEFT - t:LEFT + 1]) for t in range(6)]
    assert first_rows[:5] == ["1", "11", "111", "1101", "11111"], first_rows

    out = {"rule": RULE, "steps": T, "pmax": PMAX, "tail": TAIL, "first_rows": first_rows}

    # ---------------- Part A: pre-registered primary test ----------------
    probe_times = list(range(T - TAIL - PMAX, T - PMAX, 97)) + [T - PMAX - 1]
    candidates = [P for P in range(1, PMAX + 1)
                  if all(cone_mismatch(grid, t, P, LEFT) == 0 for t in probe_times)]
    out["A_candidate_periods_full_cone"] = candidates[:20]
    out["A_minimal_period_full_cone"] = candidates[0] if candidates else None
    out["A_onset_minimal_period_full_cone"] = onset(grid, candidates[0], LEFT, cone_mismatch) if candidates else None
    out["A_period_240_full_cone_onset"] = onset(grid, 240, LEFT, cone_mismatch)
    windows = {}
    for W in (500, 1000, 2000):
        def wm(g, t, P, left, W=W):
            return window_mismatch(g, t, P, left, W)
        cand_w = [P for P in range(1, PMAX + 1)
                  if all(window_mismatch(grid, t, P, LEFT, W) == 0 for t in probe_times)]
        windows[W] = {"minimal_period": cand_w[0] if cand_w else None,
                      "onset_minimal_period": onset(grid, cand_w[0], LEFT, wm) if cand_w else None,
                      "onset_period_240": onset(grid, 240, LEFT, wm)}
    out["A_fixed_windows_500_1000_2000"] = windows

    # ---------------- Part B: diagnostics ----------------
    # B1: P = 240 mismatch excluding the leading-edge zone, as a function of time.
    ts = np.arange(EDGE_EXCL, T - 240)
    cnt = np.array([cone_mismatch(grid, t, 240, LEFT, EDGE_EXCL) for t in ts])
    final_max = int(cnt[ts >= 3200].max())
    final_min = int(cnt[ts >= 3200].min())
    above = ts[cnt > final_max]
    out["B1_P240_mismatch_excluding_edge"] = {
        "samples": {int(t): int(cnt[t - EDGE_EXCL]) for t in (1000, 2000, 2500, 2700, 2780, 2800, 2850, 3000, 4000, 6000, 7700)},
        "final_regime_min_max_cells_t_ge_3200": [final_min, final_max],
        "last_t_with_mismatch_above_final_max": int(above.max()) if len(above) else None,
    }
    # B2: location of those mismatching cells at late times (the surviving structure).
    locs = {}
    for t in (4000, 5000, 6000, 7000, 7700):
        lo = LEFT - t + EDGE_EXCL
        d = np.nonzero(grid[t + 240, lo:LEFT + 1] != grid[t, lo:LEFT + 1])[0] - t + EDGE_EXCL
        locs[t] = {"cells": int(len(d)), "x_min": int(d.min()), "x_max": int(d.max())}
    out["B2_P240_mismatch_locations"] = locs
    tpos = np.arange(3000, T - 240, 100)
    xpos = np.array([structure_position(grid, t, LEFT) for t in tpos], dtype=float)
    slope, intercept = np.polyfit(tpos, xpos, 1)
    out["B2_structure_drift_cells_per_step_fit_t3000_7700"] = round(float(slope), 5)

    # B3: exact space-time period of the structure in co-moving windows.
    struct = {}
    for t in (3500, 5000, 7000):
        X = structure_position(grid, t, LEFT)
        for W in (40, 150):
            lo, hi = LEFT + X - W, LEFT + X + W
            found = [(P, s) for P in range(1, 900) for s in range(-100, 1)
                     if t + P < T and (grid[t + P, lo + s:hi + s] == grid[t, lo:hi]).all()]
            struct[f"t={t},W={W}"] = {"structure_x": X, "exact_(P,shift)_first_4": found[:4]}
    out["B3_structure_space_time_periods"] = struct
    P_s, s_s = None, None
    f = struct["t=5000,W=150"]["exact_(P,shift)_first_4"]
    if f:
        P_s, s_s = f[0]
    out["B3_structure_minimal_period"] = P_s
    out["B3_structure_shift_per_period"] = s_s
    # mismatch of (240, -20), (240, 0) and (P_s, s_s) in the +-150 window
    cmp = {}
    for t in (4000, 5000, 6000):
        X = structure_position(grid, t, LEFT)
        lo, hi = LEFT + X - 150, LEFT + X + 150
        cmp[t] = {"(240,0)": int((grid[t + 240, lo:hi] != grid[t, lo:hi]).sum()),
                  "(240,-20)": int((grid[t + 240, lo - 20:hi - 20] != grid[t, lo:hi]).sum())}
        if P_s is not None:
            cmp[t][f"({P_s},{s_s})"] = int((grid[t + P_s, lo + s_s:hi + s_s] != grid[t, lo:hi]).sum())
    out["B3_structure_window_mismatch"] = cmp
    # onset of the structure's periodic regime
    if P_s is not None:
        tt = np.arange(2000, T - 240)
        ok = []
        for t in tt:
            X = structure_position(grid, t, LEFT)
            if X is None:
                ok.append(False)
                continue
            lo, hi = LEFT + X - 40, LEFT + X + 40
            ok.append(bool((grid[t + P_s, lo + s_s:hi + s_s] == grid[t, lo:hi]).all()))
        ok = np.array(ok)
        out["B3_structure_regime_onset"] = int(tt[~ok].max() + 1) if (~ok).any() else int(tt[0])

    # B4: fixed-frame periodicity of right-edge windows and of the stripe region.
    tw = np.arange(0, T - 480)
    wall = {}
    for W in (50, 100, 150):
        lo, hi = LEFT - W, LEFT + 1
        res = {}
        for P in (7, 71, 80, 213, 240, 480):
            okw = np.array([bool((grid[t + P, lo:hi] == grid[t, lo:hi]).all()) for t in tw])
            res[P] = {"holds_for_all_t_ge_4000": bool(okw[tw >= 4000].all()),
                      "onset": int(tw[~okw].max() + 1) if (~okw).any() else 0}
        wall[W] = res
    out["B4_right_edge_windows"] = wall
    t = 6000
    lo, hi = LEFT - 5000, LEFT - 1000
    out["B4_stripe_region_fixed_frame_periods_le_400"] = [P for P in range(1, 401) if (grid[t + P, lo:hi] == grid[t, lo:hi]).all()]
    out["B4_stripe_region_lattice_vectors_(P,shift)"] = [(P, s) for P in range(1, 10) for s in range(-30, 31)
                                                         if (grid[t + P, lo + s:hi + s] == grid[t, lo:hi]).all()]

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
