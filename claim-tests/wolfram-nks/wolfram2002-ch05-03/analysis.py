#!/usr/bin/env python3
"""Test of wolfram2002-ch05-03: does 2D outer totalistic code 746 grow a near-circle?

Wolfram's outer totalistic code for 8 (Moore) neighbours: the new colour of a cell
with colour c and s black neighbours is bit (2*s + c) of the code.  Code 746 =
0b1011101010: white -> black iff s == 3; black stays black iff s <= 4.

Initial condition: a row of 7 black cells (NKS p. 178).  Writes derived/profiles.json
and prints the measured block for result.json.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_746 = 746
# Control: any black neighbour -> black, black stays black (grows a square).
CODE_SQUARE = sum(1 << (2 * s + c) for s in range(9) for c in (0, 1) if s >= 1 or c == 1)


def step(grid, table):
    s = np.zeros_like(grid, dtype=np.int8)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            s += np.roll(np.roll(grid, dx, axis=0), dy, axis=1)
    return table[2 * s.astype(np.int16) + grid.astype(np.int16)]


def run(code, T, size):
    table = np.array([(code >> k) & 1 for k in range(18)], dtype=np.int8)
    grid = np.zeros((size, size), dtype=np.int8)
    c = size // 2
    grid[c, c - 3:c + 4] = 1
    for _ in range(T):
        grid = step(grid, table)
    assert grid[0, :].sum() == 0 and grid[-1, :].sum() == 0
    assert grid[:, 0].sum() == 0 and grid[:, -1].sum() == 0
    return grid


def profile(grid):
    ys, xs = np.nonzero(grid)
    cy, cx = ys.mean(), xs.mean()
    dy, dx = ys - cy, xs - cx
    r = np.hypot(dx, dy)
    theta = np.degrees(np.arctan2(dy, dx)) % 360.0
    bins = np.floor(theta).astype(int)
    prof = np.zeros(360)
    np.maximum.at(prof, bins, r)
    cv = float(prof.std() / prof.mean())
    axis_bins = [b % 360 for a in (0, 90, 180, 270) for b in range(a - 5, a + 6)]
    diag_bins = [b % 360 for a in (45, 135, 225, 315) for b in range(a - 5, a + 6)]
    A = float(prof[axis_bins].mean() / prof[diag_bins].mean())
    return {"n_black": int(len(xs)), "mean_r": float(prof.mean()), "cv": cv, "anisotropy_A": A,
            "profile": [round(float(v), 2) for v in prof]}


def main():
    out = {}
    for name, code in (("code746", CODE_746), ("control_square", CODE_SQUARE)):
        for T in (400, 1200):
            size = 1100 if T == 1200 else 500
            if name == "control_square":
                size = 2 * T + 20
            g = run(code, T, size)
            p = profile(g)
            p["T"] = T
            p["mean_r_over_T"] = p["mean_r"] / T
            out[f"{name}_T{T}"] = p
            print(name, T, {k: round(v, 4) for k, v in p.items() if k not in ("profile",)})

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "profiles.json"), "w") as f:
        json.dump(out, f)

    c400, c1200 = out["code746_T400"], out["code746_T1200"]
    ctrl = out["control_square_T1200"]
    method_ok = ctrl["anisotropy_A"] < 0.8 and ctrl["cv"] > 0.06
    sup = (c1200["cv"] <= 0.03 and abs(c1200["anisotropy_A"] - 1) <= 0.03
           and c400["cv"] <= 0.05 and abs(c400["anisotropy_A"] - 1) <= 0.05)
    ref = c1200["cv"] >= 0.06 or abs(c1200["anisotropy_A"] - 1) >= 0.06
    if not method_ok:
        verdict = "inconclusive"
    elif sup:
        verdict = "supports"
    elif ref:
        verdict = "refutes"
    else:
        verdict = "mixed"
    measured = {
        "value": {"cv_T1200": round(c1200["cv"], 4), "A_T1200": round(c1200["anisotropy_A"], 4),
                  "cv_T400": round(c400["cv"], 4), "A_T400": round(c400["anisotropy_A"], 4)},
        "unit": "CV = std/mean of the 360-bin outer radial profile; A = axis/diagonal mean radius",
        "n": {"black_cells_T400": c400["n_black"], "black_cells_T1200": c1200["n_black"]},
        "uncertainty": "deterministic; one-cell lattice discreteness ~ 0.5/mean_r",
        "extra": {
            "mean_r_over_T": {"T400": round(c400["mean_r_over_T"], 4),
                              "T1200": round(c1200["mean_r_over_T"], 4)},
            "control_square_T1200": {"cv": round(ctrl["cv"], 4), "A": round(ctrl["anisotropy_A"], 4)},
            "method_validation_passed": method_ok,
        },
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
