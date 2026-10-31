#!/usr/bin/env python3
"""Test of wolfram2002-ch09-15: ball-volume growth N(r) of graphs.

Generates every graph itself (no download): hypercubic lattices Z^1..Z^4, the
infinite 3-regular tree, a random 4-regular configuration-model graph and the
Cayley graph of the discrete Heisenberg group.  Measures N(r) = number of nodes
within graph distance r of the origin by breadth-first search and estimates the
growth exponent as the OLS slope of log N(r) vs log r over r in [R/2, R].

Writes derived/ball_sizes.json and prints the measured block for result.json.
"""
import json
import math
import os
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031


def bfs_ball_sizes(neighbors, origin, R, max_nodes=None):
    """N(r) for r = 0..R using an implicit neighbour function."""
    dist = {origin: 0}
    q = deque([origin])
    counts = [0] * (R + 1)
    counts[0] = 1
    while q:
        v = q.popleft()
        d = dist[v]
        if d == R:
            continue
        for w in neighbors(v):
            if w not in dist:
                dist[w] = d + 1
                counts[d + 1] += 1
                q.append(w)
                if max_nodes and len(dist) > max_nodes:
                    raise RuntimeError("ball too large")
    return list(np.cumsum(counts))


def lattice_neighbors(d):
    def nb(v):
        for i in range(d):
            for s in (-1, 1):
                w = list(v)
                w[i] += s
                yield tuple(w)
    return nb


def tree_neighbors(v):
    # Infinite 3-regular tree: node = tuple path from the root; root has 3 children,
    # every other node has 2 children and one parent.
    if v == ():
        for c in range(3):
            yield (c,)
    else:
        yield v[:-1]
        for c in range(2):
            yield v + (c,)


def heisenberg_neighbors(v):
    # Discrete Heisenberg group H(Z): (x,y,z)*(x',y',z') = (x+x', y+y', z+z'+x*y').
    x, y, z = v
    gens = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]
    for a, b, c in gens:
        yield (x + a, y + b, z + c + x * b)


def random_regular_graph(n, k, rng):
    """Configuration-model k-regular multigraph on n nodes (self-loops/multi-edges
    are kept; they only lower growth slightly)."""
    stubs = np.repeat(np.arange(n), k)
    rng.shuffle(stubs)
    a = stubs[0::2]
    b = stubs[1::2]
    order = np.argsort(np.concatenate([a, b]), kind="stable")
    src = np.concatenate([a, b])[order]
    dst = np.concatenate([b, a])[order]
    indptr = np.searchsorted(src, np.arange(n + 1))
    return indptr, dst


def ball_sizes_csr(indptr, dst, origin, R):
    n = len(indptr) - 1
    dist = np.full(n, -1, dtype=np.int64)
    dist[origin] = 0
    frontier = np.array([origin])
    counts = [1]
    for r in range(1, R + 1):
        cand = np.concatenate([dst[indptr[v]:indptr[v + 1]] for v in frontier])
        cand = np.unique(cand)
        cand = cand[dist[cand] < 0]
        dist[cand] = r
        counts.append(len(cand))
        frontier = cand
        if len(frontier) == 0:
            break
    return list(np.cumsum(counts))


def slope_loglog(N, r_lo, r_hi):
    r = np.arange(r_lo, r_hi + 1, dtype=float)
    y = np.log(np.array(N[r_lo:r_hi + 1], dtype=float))
    x = np.log(r)
    A = np.vstack([x, np.ones_like(x)]).T
    coef, res, _, _ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coef
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    return float(coef[0]), float(r2)


def r2_linear_in_r(N, r_lo, r_hi):
    r = np.arange(r_lo, r_hi + 1, dtype=float)
    y = np.log(np.array(N[r_lo:r_hi + 1], dtype=float))
    A = np.vstack([r, np.ones_like(r)]).T
    coef, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coef
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    return float(coef[0]), float(r2)


def main():
    rng = np.random.default_rng(SEED)
    out = {}

    for d, R in ((1, 32), (2, 32), (3, 32), (4, 20)):
        N = bfs_ball_sizes(lattice_neighbors(d), tuple([0] * d), R)
        s, r2 = slope_loglog(N, R // 2, R)
        out[f"Z^{d}"] = {"R": R, "N": [int(v) for v in N], "slope_loglog": s, "r2_loglog": r2,
                         "expected_d": d}

    R = 13
    N = bfs_ball_sizes(tree_neighbors, (), R)
    s, r2 = slope_loglog(N, R // 2, R)
    k, r2lin = r2_linear_in_r(N, R // 2, R)
    out["tree_3_regular"] = {"R": R, "N": [int(v) for v in N], "slope_loglog": s, "r2_loglog": r2,
                             "slope_linear_in_r": k, "r2_linear_in_r": r2lin}

    n = 300000
    indptr, dst = random_regular_graph(n, 4, rng)
    Nfull = ball_sizes_csr(indptr, dst, 0, 40)
    R = max(r for r, v in enumerate(Nfull) if v <= n // 10)
    N = Nfull[:R + 1]
    s, r2 = slope_loglog(N, R // 2, R)
    k, r2lin = r2_linear_in_r(N, R // 2, R)
    out["random_4_regular_n300000"] = {"R": R, "n": n, "N": [int(v) for v in N], "slope_loglog": s,
                                       "r2_loglog": r2, "slope_linear_in_r": k,
                                       "r2_linear_in_r": r2lin}

    R = 24
    N = bfs_ball_sizes(heisenberg_neighbors, (0, 0, 0), R)
    s, r2 = slope_loglog(N, R // 2, R)
    out["heisenberg_cayley"] = {"R": R, "N": [int(v) for v in N], "slope_loglog": s,
                                "r2_loglog": r2, "known_growth_degree": 4}

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "ball_sizes.json"), "w") as f:
        json.dump(out, f, indent=1)

    # Pre-registered decision logic.
    lattice_ok = all(abs(out[f"Z^{d}"]["slope_loglog"] - d) <= 0.15 for d in (1, 2, 3, 4))
    lattice_bad = any(abs(out[f"Z^{d}"]["slope_loglog"] - d) > 0.5 for d in (1, 2, 3, 4))
    exp_ok = all(out[g]["slope_loglog"] > 5 and out[g]["r2_linear_in_r"] > out[g]["r2_loglog"]
                 for g in ("tree_3_regular", "random_4_regular_n300000"))
    exp_bad = any(out[g]["slope_loglog"] < 3 or out[g]["r2_linear_in_r"] < out[g]["r2_loglog"]
                  for g in ("tree_3_regular", "random_4_regular_n300000"))
    primary = lattice_ok and exp_ok
    heis = out["heisenberg_cayley"]["slope_loglog"]
    heis_poly4 = 3.5 <= heis <= 4.5
    if lattice_bad or exp_bad:
        verdict = "refutes"
    elif primary and heis_poly4:
        verdict = "mixed"
    elif primary:
        verdict = "supports"
    else:
        verdict = "inconclusive"

    # POST-HOC (not pre-registered; added after seeing that the Z^4 slope at R = 20
    # missed the 0.15 tolerance): exact ball sizes of Z^d from the closed form
    # N_d(r) = sum_k 2^k C(d,k) C(r,k), cross-checked against the BFS counts, and the
    # same slope estimator at R = 200 to show the finite-R bias of the estimator.
    def exact_ball(d, r):
        return sum((2 ** k) * math.comb(d, k) * math.comb(r, k) for k in range(d + 1))

    post_hoc = {}
    for d in (1, 2, 3, 4):
        R = out[f"Z^{d}"]["R"]
        assert all(exact_ball(d, r) == out[f"Z^{d}"]["N"][r] for r in range(R + 1))
        Nbig = [exact_ball(d, r) for r in range(201)]
        s200, _ = slope_loglog(Nbig, 100, 200)
        post_hoc[f"Z^{d}_slope_R200"] = round(s200, 4)
    out["post_hoc_exact_lattice_slopes"] = post_hoc
    with open(os.path.join(HERE, "derived", "ball_sizes.json"), "w") as f:
        json.dump(out, f, indent=1)
    del out["post_hoc_exact_lattice_slopes"]

    measured = {
        "value": {g: round(out[g]["slope_loglog"], 3) for g in out},
        "unit": "log-log slope of N(r) over r in [R/2, R] (growth exponent estimate)",
        "n": {g: out[g]["N"][-1] for g in out},
        "uncertainty": "exact counts; slope is an OLS fit, R^2 reported per graph",
        "extra": {
            "r2_loglog": {g: round(out[g]["r2_loglog"], 4) for g in out},
            "r2_linear_in_r": {g: round(out[g]["r2_linear_in_r"], 4) for g in out
                               if "r2_linear_in_r" in out[g]},
            "primary_pass": primary,
            "heisenberg_slope_in_[3.5,4.5]": heis_poly4,
            "post_hoc_exact_lattice_slopes_R200": post_hoc,
        },
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
