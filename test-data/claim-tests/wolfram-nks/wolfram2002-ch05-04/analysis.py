#!/usr/bin/env python3
"""Test of wolfram2002-ch05-04: overall-shape complexity of the 2D outer-totalistic
cellular automaton 'a cell becomes black when exactly 3 of its 8 neighbours are black,
otherwise unchanged' (NKS code 174826), from a row of 11 black cells.

Generates the evolution itself (no download). Writes derived/measurements.json and
prints the numbers that go into result.json's `measured`.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 1000
CHECKPOINTS = [125, 250, 375, 500, 625, 750, 875, 1000]
NBINS = 360


def moore_count(a):
    """Number of black cells among the 8 Moore neighbours (array has a white margin)."""
    c = np.zeros_like(a, dtype=np.uint8)
    c[1:, :] += a[:-1, :]
    c[:-1, :] += a[1:, :]
    c[:, 1:] += a[:, :-1]
    c[:, :-1] += a[:, 1:]
    c[1:, 1:] += a[:-1, :-1]
    c[1:, :-1] += a[:-1, 1:]
    c[:-1, 1:] += a[1:, :-1]
    c[:-1, :-1] += a[1:, 1:]
    return c


def vonneumann_count(a):
    c = np.zeros_like(a, dtype=np.uint8)
    c[1:, :] += a[:-1, :]
    c[:-1, :] += a[1:, :]
    c[:, 1:] += a[:, :-1]
    c[:, :-1] += a[:, 1:]
    return c


def step_outer_totalistic(a, code, neigh):
    """NKS outer-totalistic code: bit (2k + centre) gives the new colour of a cell with
    colour `centre` and k black neighbours."""
    k = neigh(a).astype(np.int64)
    idx = 2 * k + a.astype(np.int64)
    return ((code >> idx) & 1).astype(np.uint8)


RULES = {
    # name: (code, neighbourhood counter, seed length)
    "code174826_B3_row11": (174826, moore_count, 11),
    "control_square_any8_row11": (sum(1 << (2 * k) for k in range(1, 9)) + sum(1 << (2 * k + 1) for k in range(0, 9)), moore_count, 11),
    "control_diamond_any4_row11": (sum(1 << (2 * k) for k in range(1, 5)) + sum(1 << (2 * k + 1) for k in range(0, 5)), vonneumann_count, 11),
    "comparison_code175850_row7": (175850, moore_count, 7),
}


def pad_if_needed(a):
    """Keep a white margin of >= 2 cells around every black cell."""
    rows = np.flatnonzero(a.any(axis=1))
    cols = np.flatnonzero(a.any(axis=0))
    if rows.size == 0:
        return a
    top, bot = rows[0], a.shape[0] - 1 - rows[-1]
    left, right = cols[0], a.shape[1] - 1 - cols[-1]
    grow = 64
    pt = grow if top < 2 else 0
    pb = grow if bot < 2 else 0
    pl = grow if left < 2 else 0
    pr = grow if right < 2 else 0
    if pt or pb or pl or pr:
        a = np.pad(a, ((pt, pb), (pl, pr)))
    return a


def radial_profile(a, nbins=NBINS):
    """Normalised outer radius of the occupied set from its centroid, per angular bin."""
    ys, xs = np.nonzero(a)
    cy, cx = ys.mean(), xs.mean()
    dy, dx = ys - cy, xs - cx
    r = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    b = ((ang + np.pi) / (2 * np.pi) * nbins).astype(int) % nbins
    rho = np.zeros(nbins)
    np.maximum.at(rho, b, r)
    # a bin with no cell at all (only possible for tiny patterns) takes its neighbours' value
    empty = rho == 0
    if empty.any():
        rho[empty] = np.interp(np.flatnonzero(empty), np.flatnonzero(~empty), rho[~empty], period=nbins)
    mean_r = rho.mean()
    return rho / mean_r, mean_r, (cy, cx)


def reference_profiles(nbins=NBINS):
    """Normalised radial profiles of simple convex shapes: circle, squares, octagons."""
    th = (np.arange(nbins) + 0.5) / nbins * 2 * np.pi - np.pi
    refs = {"circle": np.ones(nbins)}

    def regular_polygon(n, rot):
        # support function of a regular n-gon with inradius 1: r(theta) = 1 / cos(delta)
        # where delta is the angle to the nearest face normal.
        d = (th - rot) % (2 * np.pi / n)
        d = np.minimum(d, 2 * np.pi / n - d)
        r = 1.0 / np.cos(d)
        return r / r.mean()

    refs["square_axis"] = regular_polygon(4, 0.0)
    refs["square_45deg"] = regular_polygon(4, np.pi / 4)
    refs["octagon_0deg"] = regular_polygon(8, 0.0)
    refs["octagon_22.5deg"] = regular_polygon(8, np.pi / 8)
    return refs


def convex_hull_area(a):
    from scipy.spatial import ConvexHull

    ys, xs = np.nonzero(a)
    pts = np.column_stack([xs, ys]).astype(float)
    if len(pts) < 3:
        return 0.0
    return float(ConvexHull(pts).volume)


def run_rule(name, code, neigh, seed_len):
    a = np.zeros((seed_len + 8, seed_len + 8), dtype=np.uint8)
    a[a.shape[0] // 2, 4:4 + seed_len] = 1
    out = {"checkpoints": {}}
    pops = {}
    for t in range(1, T + 1):
        a = pad_if_needed(a)
        a = step_outer_totalistic(a, code, neigh)
        if t >= 900:
            pops[t] = int(a.sum())
        if t in CHECKPOINTS:
            rho, mean_r, _ = radial_profile(a)
            out["checkpoints"][t] = {
                "population": int(a.sum()),
                "mean_radius": float(mean_r),
                "rho": rho.tolist(),
                "rho_std": float(rho.std()),
                "bbox": [int(x) for x in (a.any(axis=1).sum(), a.any(axis=0).sum())],
                "hull_area": convex_hull_area(a),
            }
            print(f"  {name} t={t} pop={int(a.sum())} R={mean_r:.1f} rho_std={rho.std():.3f}", flush=True)
    out["population_900_to_1000_constant"] = len(set(pops.values())) == 1
    return out


def shape_distance(r1, r2):
    return float(np.mean(np.abs(np.asarray(r1) - np.asarray(r2))))


def main():
    refs = reference_profiles()
    results = {}
    for name, (code, neigh, seed_len) in RULES.items():
        print(f"running {name} (code {code})", flush=True)
        results[name] = run_rule(name, code, neigh, seed_len)

    summary = {}
    for name, res in results.items():
        cp = res["checkpoints"]
        rho = {t: np.array(cp[t]["rho"]) for t in CHECKPOINTS}
        simple = {k: shape_distance(rho[1000], v) for k, v in refs.items()}
        best = min(simple, key=simple.get)
        summary[name] = {
            "population_500": cp[500]["population"],
            "population_1000": cp[1000]["population"],
            "mean_radius_500": cp[500]["mean_radius"],
            "mean_radius_1000": cp[1000]["mean_radius"],
            "radius_ratio_1000_over_500": cp[1000]["mean_radius"] / cp[500]["mean_radius"],
            "D_500_1000": shape_distance(rho[500], rho[1000]),
            "D_750_1000": shape_distance(rho[750], rho[1000]),
            "D_consecutive_checkpoints": [shape_distance(rho[a], rho[b]) for a, b in zip(CHECKPOINTS[:-1], CHECKPOINTS[1:])],
            "rho_std_1000": cp[1000]["rho_std"],
            "simple_shape_distances_1000": simple,
            "min_simple_shape_distance_1000": simple[best],
            "closest_simple_shape_1000": best,
            "solidity_1000": cp[1000]["population"] / cp[1000]["hull_area"] if cp[1000]["hull_area"] else None,
            "population_900_to_1000_constant": res["population_900_to_1000_constant"],
        }

    main_rule = summary["code174826_B3_row11"]
    controls = [summary["control_square_any8_row11"], summary["control_diamond_any4_row11"]]
    crit = {
        "a_growth_continues": bool(main_rule["radius_ratio_1000_over_500"] >= 1.5 and main_rule["population_1000"] > main_rule["population_500"]),
        "b_outline_changing": bool(main_rule["D_500_1000"] >= 0.05 and main_rule["D_750_1000"] >= 0.03 and all(c["D_500_1000"] <= 0.02 for c in controls)),
        "c_not_simple_form": bool(main_rule["min_simple_shape_distance_1000"] >= 0.05 and all(c["min_simple_shape_distance_1000"] <= 0.03 for c in controls)),
        "fail_growth_stopped": bool(main_rule["population_900_to_1000_constant"]),
        "fail_converged_simple": bool(main_rule["D_500_1000"] < 0.02 and main_rule["min_simple_shape_distance_1000"] < 0.03),
    }
    if crit["fail_growth_stopped"] or crit["fail_converged_simple"]:
        verdict = "refutes"
    elif crit["a_growth_continues"] and crit["b_outline_changing"] and crit["c_not_simple_form"]:
        verdict = "supports"
    else:
        verdict = "mixed"

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump({"summary": summary, "criteria": crit, "verdict": verdict,
                   "profiles_1000": {k: [round(x, 4) for x in results[k]["checkpoints"][1000]["rho"]] for k in results}}, f, indent=1)
    print(json.dumps({"summary": summary, "criteria": crit, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
