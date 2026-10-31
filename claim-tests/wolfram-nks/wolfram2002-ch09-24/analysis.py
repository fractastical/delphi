#!/usr/bin/env python3
"""wolfram2002-ch09-24: curvature correction to shell counts in networks approximating space.

Random geometric graphs on constant-curvature spaces with identical density and connection
radius; shell counts S(r) at hop distance r from many sources; comparison with the continuum
geodesic-sphere expansion  S_curved/S_flat = 1 - R s^2/(6d) + O(s^4).
Deterministic (seeded).  Prints JSON to stdout.
"""
import json
import sys

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import shortest_path
from scipy.spatial import cKDTree

DENSITY = {2: 3183.0, 3: 7600.0}
EPS = {2: 0.045, 3: 0.086}
SEEDS = [0, 1, 2]
N_SOURCES = 500
S_MIN, S_MAX = 0.25, 0.7
HYP_RMAX, HYP_SRC = 2.2, 1.0   # pre-registered 1.8 / 0.2 gave ~400 overlapping sources, see result.json caveats


# ---------------------------------------------------------------- geometries
def torus_points(rng, d, n):
    L = (n / DENSITY[d]) ** (1.0 / d)
    return rng.random((n, d)) * L, L


def sphere_points(rng, d, n, rho):
    v = rng.normal(size=(n, d + 1))
    return rho * v / np.linalg.norm(v, axis=1, keepdims=True)


def hyperbolic_points(rng, n):
    """Uniform w.r.t. hyperbolic area (curvature -1) in the disk of hyperbolic radius HYP_RMAX; Poincare coordinates."""
    u = rng.random(n)
    rh = np.arccosh(1 + u * (np.cosh(HYP_RMAX) - 1))
    th = rng.random(n) * 2 * np.pi
    re = np.tanh(rh / 2)
    return np.stack([re * np.cos(th), re * np.sin(th)], axis=1), rh


def hyp_dist(p, q):
    num = 2 * np.sum((p - q) ** 2, axis=1)
    den = (1 - np.sum(p ** 2, axis=1)) * (1 - np.sum(q ** 2, axis=1))
    return np.arccosh(1 + num / den)


def build_graph(kind, d, rng):
    eps = EPS[d]
    if kind == "torus":
        n = int(round(DENSITY[d] * {2: 4 * np.pi, 3: 2 * np.pi ** 2}[d]))
        pts, L = torus_points(rng, d, n)
        tree = cKDTree(pts, boxsize=L)
        pairs = tree.query_pairs(eps, output_type="ndarray")
        meta = {"L": L, "pts": pts}
    elif kind.startswith("sphere"):
        rho = float(kind.split(":")[1])
        area = {2: 4 * np.pi * rho ** 2, 3: 2 * np.pi ** 2 * rho ** 3}[d]
        n = int(round(DENSITY[d] * area))
        pts = sphere_points(rng, d, n, rho)
        chord = 2 * rho * np.sin(eps / (2 * rho))
        tree = cKDTree(pts)
        pairs = tree.query_pairs(chord, output_type="ndarray")
        meta = {"rho": rho}
    elif kind == "hyperbolic":
        area = 2 * np.pi * (np.cosh(HYP_RMAX) - 1)
        n = int(round(DENSITY[2] * area))
        pts, rh = hyperbolic_points(rng, n)
        tree = cKDTree(pts)
        radii = eps * (1 - np.sum(pts ** 2, axis=1))  # safe Euclidean over-estimate of a hyperbolic eps-ball
        nbrs = tree.query_ball_point(pts, radii)
        ii = np.concatenate([np.full(len(nb), i) for i, nb in enumerate(nbrs)])
        jj = np.concatenate([np.array(nb, dtype=np.int64) for nb in nbrs])
        mask = ii < jj
        ii, jj = ii[mask], jj[mask]
        keep = hyp_dist(pts[ii], pts[jj]) <= eps
        pairs = np.stack([ii[keep], jj[keep]], axis=1)
        meta = {"rh": rh}
    else:
        raise ValueError(kind)
    n = len(pts)
    A = coo_matrix((np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    A = (A + A.T).tocsr()
    return A, n, meta


def shells(A, sources, rmax):
    counts = np.zeros(rmax + 1)
    nsrc = 0
    dist_all = []
    for b in range(0, len(sources), 100):
        D = shortest_path(A, method="D", unweighted=True, indices=sources[b:b + 100])
        dist_all.append(D)
        for row in D:
            fin = row[np.isfinite(row)].astype(int)
            counts += np.bincount(fin, minlength=rmax + 1)[:rmax + 1]
            nsrc += 1
    return counts / nsrc, np.vstack(dist_all)


def torus_geodesic_radius(D, pts, sources, L, rmax):
    """mean Euclidean (periodic) distance of hop-r nodes from their source, for r = 0..rmax."""
    tot = np.zeros(rmax + 1)
    cnt = np.zeros(rmax + 1)
    for k, s in enumerate(sources):
        row = D[k]
        ok = np.isfinite(row) & (row <= rmax)
        idx = np.flatnonzero(ok)
        dv = np.abs(pts[idx] - pts[s])
        dv = np.minimum(dv, L - dv)
        e = np.sqrt((dv ** 2).sum(axis=1))
        h = row[idx].astype(int)
        tot += np.bincount(h, weights=e, minlength=rmax + 1)[:rmax + 1]
        cnt += np.bincount(h, minlength=rmax + 1)[:rmax + 1]
    return tot / np.maximum(cnt, 1)


GEOMETRIES = [
    ("torus2", "torus", 2, 0.0), ("sphere1", "sphere:1.0", 2, 2.0), ("sphere1.5", "sphere:1.5", 2, 8.0 / 9.0),
    ("hyperbolic", "hyperbolic", 2, -2.0), ("torus3", "torus", 3, 0.0), ("sphere3d", "sphere:1.0", 3, 6.0),
]


def main():
    rmax = {2: 24, 3: 16}
    results = {}
    s_of_r = {}
    for name, kind, d, R in GEOMETRIES:
        per_seed = []
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            A, n, meta = build_graph(kind, d, rng)
            deg = np.asarray(A.sum(axis=1)).ravel()
            if kind == "hyperbolic":
                cand = np.flatnonzero(meta["rh"] <= HYP_SRC)
                sources = rng.choice(cand, size=min(N_SOURCES, cand.size), replace=False)
            else:
                sources = rng.choice(n, size=N_SOURCES, replace=False)
            S, D = shells(A, sources, rmax[d])
            rec = {"seed": seed, "n": int(n), "mean_degree": float(deg.mean()), "S": S.tolist()}
            if kind == "torus":
                rec["s_of_r"] = torus_geodesic_radius(D, meta["pts"], sources, meta["L"], rmax[d]).tolist()
            per_seed.append(rec)
            print(name, seed, n, round(float(deg.mean()), 2), file=sys.stderr)
        results[name] = {"kind": kind, "d": d, "R": R, "per_seed": per_seed,
                         "S_mean": np.mean([p["S"] for p in per_seed], axis=0).tolist(),
                         "S_sd": np.std([p["S"] for p in per_seed], axis=0).tolist()}
        if kind == "torus":
            s_of_r[d] = np.mean([p["s_of_r"] for p in per_seed], axis=0)
            results[name]["s_of_r"] = s_of_r[d].tolist()

    out = {"parameters": {"density": DENSITY, "epsilon": EPS, "seeds": SEEDS, "sources_per_graph": N_SOURCES,
                          "fit_range_geodesic": [S_MIN, S_MAX], "hyperbolic_rmax": HYP_RMAX, "hyperbolic_source_radius": HYP_SRC},
           "geometries": results, "tests": {}}
    all_sign = all_exp = all_coef = True
    refute = False
    ks = {}
    for name, kind, d, R in GEOMETRIES:
        if R == 0:
            continue
        flat = results["torus%d" % d]["S_mean"]
        S = np.array(results[name]["S_mean"])
        s = s_of_r[d]
        r = np.arange(len(S))
        fit = np.flatnonzero((s >= S_MIN) & (s <= S_MAX) & (r >= 1))
        Sf = np.array(flat)
        Q = S[fit] / Sf[fit] - 1
        diff = S[fit] - Sf[fit]
        sign_ok = bool(np.all(Q < 0) if R > 0 else np.all(Q > 0))
        slope = float(np.polyfit(np.log(r[fit]), np.log(np.abs(diff)), 1)[0]) if np.all(diff != 0) else float("nan")
        exp_ok = bool(abs(slope - (d + 1)) <= 0.6)
        k = float(np.sum(Q * s[fit] ** 2) / np.sum(s[fit] ** 4))
        pred = -R / (6 * d)
        ratio = k / pred
        coef_ok = bool(0.7 <= ratio <= 1.3)
        ks[name] = k
        all_sign &= sign_ok
        all_exp &= exp_ok
        all_coef &= coef_ok
        refute |= (not sign_ok) or not (d <= slope <= d + 2) or not (0.4 <= ratio <= 2.5)
        out["tests"][name] = {"d": d, "R": R, "fit_hops": r[fit].tolist(), "s_of_r_fit": s[fit].round(4).tolist(),
                              "S_curved": S[fit].round(2).tolist(), "S_flat": Sf[fit].round(2).tolist(),
                              "Q": Q.round(5).tolist(), "predicted_Q": (pred * s[fit] ** 2).round(5).tolist(),
                              "sign_ok": sign_ok, "exponent_slope": round(slope, 3), "exponent_ok": exp_ok,
                              "k_fit": k, "k_predicted": pred, "k_ratio": round(ratio, 4), "coefficient_ok": coef_ok}
    sphere_ratio = ks["sphere1"] / ks["sphere1.5"]
    ratio_ok = bool(abs(sphere_ratio / 2.25 - 1) <= 0.3)
    all_coef &= ratio_ok
    out["tests"]["sphere_k_ratio"] = {"k_sphere1_over_k_sphere1.5": round(sphere_ratio, 4), "expected": 2.25, "ok": ratio_ok}
    out["criteria"] = {"a_sign": all_sign, "b_exponent": all_exp, "c_coefficient": all_coef}
    out["verdict"] = "supports" if (all_sign and all_exp and all_coef) else ("refutes" if refute else "mixed")
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
