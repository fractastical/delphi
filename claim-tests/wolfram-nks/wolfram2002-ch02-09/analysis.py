#!/usr/bin/env python3
"""Test of wolfram2002-ch02-09: one rule (ECA rule 110), many kinds of behaviour.

Computational "dataset": elementary cellular automaton rule 110 (Wolfram numbering,
neighbourhood (left, centre, right) -> bit 4*l+2*c+r of 110), cyclic lattice of W cells,
random initial conditions of density 0.5 (numpy default_rng seeds 0..NRUNS-1), T steps.

Part A: find the periodic background (ether) as a 14-cell ring configuration that rule 110
maps after 7 steps onto a rotation of itself, and measure the fraction of cells in the
random runs whose 14-cell neighbourhood matches that background in some phase.

Part B: cluster non-background cells, track clusters through time, and keep tracks that
persist >= MIN_TRACK steps and are exactly periodic up to a shift (window at t equals window
at t+p shifted by s, for NPERIODS consecutive periods).  Distinct velocities s/p count as
distinct localized structures.

Writes measured values to stdout as JSON; result.json copies them verbatim.
"""
import json
import sys
from fractions import Fraction

import numpy as np

RULE = 110
W = 700
T = 3000
T_MEASURE_FROM = 1000
NRUNS = 20
ETHER_RING = 14
ETHER_PERIOD = 7
MIN_TRACK = 300
NPERIODS = 5
MAX_PERIOD = 60
MARGIN = 10
GAP = 3          # defect cells closer than this are one cluster
MATCH_DIST = 6   # max centre movement per step when linking clusters


def step(row, rule=RULE):
    l = np.roll(row, 1)
    r = np.roll(row, -1)
    idx = (l.astype(np.int64) << 2) | (row.astype(np.int64) << 1) | r
    return ((rule >> idx) & 1).astype(np.uint8)


def evolve(row, t):
    out = np.empty((t + 1, row.size), dtype=np.uint8)
    out[0] = row
    for i in range(t):
        out[i + 1] = step(out[i])
    return out


def ints_to_rows(n, width):
    return ((np.arange(n)[:, None] >> np.arange(width - 1, -1, -1)) & 1).astype(np.uint8)


def find_ether():
    """All 14-cell ring configurations x with rule110^7(x) == rotation(x), excluding the
    uniform ones; returns the candidate with the largest basin among the 2^14 states."""
    n = 2 ** ETHER_RING
    rows = ints_to_rows(n, ETHER_RING)
    cur = rows.copy()
    for _ in range(ETHER_PERIOD):
        cur = step_batch(cur)
    weights = 1 << np.arange(ETHER_RING - 1, -1, -1)
    target = rows @ weights
    periodic = np.zeros(n, dtype=bool)
    shift_of = np.full(n, -1)
    for s in range(ETHER_RING):
        rolled = np.roll(cur, s, axis=1) @ weights
        hit = (rolled == target) & ~periodic
        periodic |= hit
        shift_of[hit] = s
    periodic[0] = False
    periodic[n - 1] = False
    # basin sizes: iterate every state forward 200 steps and see which periodic orbit it lands in
    cur = rows.copy()
    for _ in range(200):
        cur = step_batch(cur)
    landed = cur @ weights
    # orbit id: canonical = min over rotations and over the 7-step cycle of the integer code
    cand = np.where(periodic)[0]
    orbit_id = {}
    for c in cand:
        if c in orbit_id:
            continue
        orbit = set()
        x = rows[c].copy()
        for _ in range(ETHER_PERIOD * ETHER_RING):
            for s in range(ETHER_RING):
                orbit.add(int(np.roll(x, s) @ weights))
            x = step(x)
        key = min(orbit)
        for o in orbit:
            orbit_id[o] = key
    basin = {}
    for v in landed:
        k = orbit_id.get(int(v))
        if k is not None:
            basin[k] = basin.get(k, 0) + 1
    best = max(basin, key=basin.get)
    ether_rows = []
    x = rows[best].copy()
    for _ in range(ETHER_PERIOD):
        ether_rows.append(x.copy())
        x = step(x)
    return {
        "n_periodic_nonuniform_configs": int(periodic.sum()),
        "n_orbits": len(set(orbit_id.values())),
        "basin_fraction_of_best": basin[best] / n,
        "ether_row": "".join(map(str, rows[best])),
        "ether_shift_after_7_steps": int(shift_of[best]),
    }, ether_rows


def step_batch(rows):
    l = np.roll(rows, 1, axis=1)
    r = np.roll(rows, -1, axis=1)
    idx = (l.astype(np.int64) << 2) | (rows.astype(np.int64) << 1) | r
    return ((RULE >> idx) & 1).astype(np.uint8)


def window_codes(st, width):
    """Integer code of the `width`-cell window starting at each position (cyclic)."""
    codes = np.zeros(st.shape, dtype=np.int64)
    for k in range(width):
        codes = (codes << 1) | np.roll(st, -k, axis=1).astype(np.int64)
    return codes


def background_mask(st, ether_codes):
    codes = window_codes(st, ETHER_RING)
    return np.isin(codes, ether_codes)


def clusters_of(defect_row):
    xs = np.where(defect_row)[0]
    if xs.size == 0:
        return []
    out = []
    start = xs[0]
    prev = xs[0]
    for x in xs[1:]:
        if x - prev > GAP:
            out.append((start, prev))
            start = x
        prev = x
    out.append((start, prev))
    # cyclic merge
    if len(out) > 1 and out[0][0] <= GAP - 1 and out[-1][1] >= defect_row.size - GAP:
        a, b = out[0], out[-1]
        out = out[1:-1] + [(b[0], a[1] + defect_row.size)]
    return out


def track_clusters(defect):
    """Link clusters across consecutive steps; a track ends on merge/split/loss."""
    tracks = []
    active = []  # dicts: t0, centres list, extents list
    for t in range(defect.shape[0]):
        cl = clusters_of(defect[t])
        centres = [((a + b) / 2.0) % W for a, b in cl]
        used_prev = {}
        assign = [-1] * len(cl)
        for i, c in enumerate(centres):
            best = -1
            bestd = MATCH_DIST + 1
            for j, tr in enumerate(active):
                d = abs((c - tr["centres"][-1] + W / 2) % W - W / 2)
                if d < bestd:
                    bestd = d
                    best = j
            if best >= 0:
                used_prev.setdefault(best, []).append(i)
                assign[i] = best
        new_active = []
        for j, tr in enumerate(active):
            claimants = used_prev.get(j, [])
            if len(claimants) == 1:
                i = claimants[0]
                tr["centres"].append(centres[i])
                tr["extents"].append(cl[i])
                new_active.append(tr)
            else:
                tracks.append(tr)
                for i in claimants:
                    assign[i] = -1
        for i, a in enumerate(assign):
            if a == -1 or len(used_prev.get(a, [])) != 1:
                new_active.append({"t0": t, "centres": [centres[i]], "extents": [cl[i]]})
        active = new_active
    tracks.extend(active)
    return [tr for tr in tracks if len(tr["centres"]) >= MIN_TRACK]


def exact_period(st, tr):
    """Find (p, s) with window(t+p) == shift(window(t), s) for NPERIODS consecutive periods."""
    t0 = tr["t0"] + 20
    a, b = tr["extents"][20]
    width = (b - a) + 2 * MARGIN + 1
    if width > W // 2:
        return None
    x0 = (a - MARGIN) % W
    base = np.take(st[t0], (x0 + np.arange(width)) % W)
    for p in range(1, MAX_PERIOD + 1):
        if t0 + NPERIODS * p >= st.shape[0] or t0 + NPERIODS * p - tr["t0"] >= len(tr["centres"]):
            break
        for s in range(-p, p + 1):
            ok = True
            for k in range(1, NPERIODS + 1):
                seg = np.take(st[t0 + k * p], (x0 + k * s + np.arange(width)) % W)
                if not np.array_equal(seg, base):
                    ok = False
                    break
            if ok:
                return p, s
    return None


def main():
    ether_info, ether_rows = find_ether()
    ether_codes = set()
    for r in ether_rows:
        for s in range(ETHER_RING):
            ether_codes.add(int(window_codes(np.roll(r, s)[None, :], ETHER_RING)[0, 0]))
    ether_codes = np.array(sorted(ether_codes), dtype=np.int64)

    bg_fracs = []
    structures = {}  # (p, s) -> count of tracks
    n_tracks_total = 0
    n_tracks_periodic = 0
    for seed in range(NRUNS):
        rng = np.random.default_rng(seed)
        init = rng.integers(0, 2, W).astype(np.uint8)
        st = evolve(init, T)
        bg = background_mask(st, ether_codes)
        bg_fracs.append(float(bg[T_MEASURE_FROM:].mean()))
        defect = ~bg[T_MEASURE_FROM:]
        sub = st[T_MEASURE_FROM:]
        tracks = track_clusters(defect)
        n_tracks_total += len(tracks)
        for tr in tracks:
            ps = exact_period(sub, tr)
            if ps is None:
                continue
            n_tracks_periodic += 1
            p, s = ps
            structures[(p, s)] = structures.get((p, s), 0) + 1

    velocities = {}
    for (p, s), cnt in structures.items():
        v = Fraction(s, p)
        velocities.setdefault(v, []).append({"period": p, "shift": s, "tracks": cnt})
    vel_sorted = sorted(velocities.keys())
    # distinct velocities differing pairwise by > 0.05
    distinct = []
    for v in vel_sorted:
        if all(abs(float(v) - float(u)) > 0.05 for u in distinct):
            distinct.append(v)

    mean_bg = float(np.mean(bg_fracs))
    passA = ether_info["n_periodic_nonuniform_configs"] > 0 and mean_bg >= 0.5
    passB = len(distinct) >= 3
    if passA and passB:
        verdict = "supports"
    elif mean_bg < 0.25 or len(distinct) < 2:
        verdict = "refutes"
    else:
        verdict = "mixed"

    out = {
        "ether": ether_info,
        "ether_rows": ["".join(map(str, r)) for r in ether_rows],
        "n_ether_window_codes": int(ether_codes.size),
        "background_fraction_per_run": [round(f, 4) for f in bg_fracs],
        "mean_background_fraction": round(mean_bg, 4),
        "n_tracks_ge_%d_steps" % MIN_TRACK: n_tracks_total,
        "n_tracks_exactly_periodic": n_tracks_periodic,
        "structures_by_velocity": [
            {"velocity": str(v), "velocity_float": round(float(v), 4), "signatures": velocities[v]}
            for v in vel_sorted
        ],
        "n_distinct_velocities": len(distinct),
        "distinct_velocities": [str(v) for v in distinct],
        "pass_A_background": bool(passA),
        "pass_B_structures": bool(passB),
        "verdict": verdict,
        "parameters": {"rule": RULE, "W": W, "T": T, "measure_from": T_MEASURE_FROM, "runs": NRUNS,
                        "seeds": "numpy default_rng(0..%d)" % (NRUNS - 1), "min_track": MIN_TRACK,
                        "periods_checked": NPERIODS, "max_period": MAX_PERIOD},
    }
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
