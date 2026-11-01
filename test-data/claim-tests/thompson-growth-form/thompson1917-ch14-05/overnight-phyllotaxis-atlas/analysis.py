#!/usr/bin/env python3
"""Monte Carlo basin-volume atlas for the Douady-Couder disc rule.

Approach phyllotaxis-attractor-classification--grok-4-7--3. The rule, sweep,
classification and thresholds are the ones pre-registered in result.json.

Usage: python3 analysis.py [--n-g 200] [--seeds 500] [--jobs 8] [--cache DIR]
Per-G terminal divergences are cached (default: $TMPDIR/phyllo-atlas-cache) so an
interrupted run resumes; the cache is not part of the repo.
"""
import argparse
import csv
import json
import math
import os
import sys
import tempfile
import time
from multiprocessing import Pool

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")

N_TOTAL = 300
N_INIT = 3
N_TAIL = 50
GRID = 720
REF_GRID = 3600
N_CAND = 3
CUTOFF = 10.0  # primordia with r - 1 > CUTOFF are dropped from the sum
TOL = 1e-3
G_MIN, G_MAX, N_G_FULL = 0.02, 1.0, 200
SEED_SIM = 20261101
SEED_BOOT = 20261102
N_BOOT = 1000
GS_TOL = 1e-10
INVPHI = (math.sqrt(5) - 1) / 2

PHI = (1 + math.sqrt(5)) / 2
GOLDEN = 2 * math.pi / (1 + PHI)  # 137.5078 deg
LUCAS = 2 * math.pi / (2 + PHI)  # 99.5016 deg
LISTED = {
    "golden": ("const", [GOLDEN]),
    "lucas": ("const", [LUCAS]),
    "bijugate-golden": ("p2", [math.pi, GOLDEN / 2]),
    "bijugate-lucas": ("p2", [math.pi, LUCAS / 2]),
}
FIB = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
LUC = [1, 3, 4, 7, 11, 18, 29, 47, 76]
FIB_PAIRS = {(FIB[i], FIB[i + 1]) for i in range(len(FIB) - 1)}
LUC_PAIRS = {(LUC[i], LUC[i + 1]) for i in range(len(LUC) - 1)}


def g_values(n_g):
    full = np.geomspace(G_MIN, G_MAX, N_G_FULL)
    if n_g >= N_G_FULL:
        return full
    idx = np.unique(np.round(np.linspace(0, N_G_FULL - 1, n_g)).astype(int))
    return full[idx]


def initial_angles(n_seeds):
    rng = np.random.default_rng(SEED_SIM)
    return rng.uniform(0, 2 * np.pi, size=(n_seeds, N_INIT))


def kmax(G):
    return int(math.floor(math.log(1 + CUTOFF) / G))


def wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


# ---------------- vectorized implementation ----------------

def energy_points(x, th, r):
    """x (S,P) angles, th (S,K) primordium angles, r (K,) radii -> (S,P) energy."""
    d2 = (1.0 + r * r)[None, None, :] - 2.0 * r[None, None, :] * np.cos(x[:, :, None] - th[:, None, :])
    return np.sum(d2 ** -1.5, axis=2)


def place_vectorized(th, r, grid, cg, sg):
    S = th.shape[0]
    ct, st = np.cos(th).astype(np.float32), np.sin(th).astype(np.float32)
    rr = r.astype(np.float32)
    a = (1.0 + rr * rr)[None, :, None]
    cosdiff = ct[:, :, None] * cg[None, None, :] + st[:, :, None] * sg[None, None, :]
    d2 = a - 2.0 * rr[None, :, None] * cosdiff
    E = np.sum(d2 ** np.float32(-1.5), axis=1)  # (S, M)
    M = E.shape[1]
    left, right = np.roll(E, 1, axis=1), np.roll(E, -1, axis=1)
    is_min = (E <= left) & (E <= right)
    Em = np.where(is_min, E, np.inf)
    order = np.argsort(Em, axis=1)[:, :N_CAND]
    valid = np.isfinite(np.take_along_axis(Em, order, axis=1))
    order = np.where(valid, order, order[:, :1])
    step = 2 * np.pi / M
    lo = grid[order] - step
    hi = grid[order] + step
    c = hi - INVPHI * (hi - lo)
    d = lo + INVPHI * (hi - lo)
    fc, fd = energy_points(c, th, r), energy_points(d, th, r)
    while np.max(hi - lo) > GS_TOL:
        left_better = fc < fd
        hi = np.where(left_better, d, hi)
        lo = np.where(left_better, lo, c)
        nc = hi - INVPHI * (hi - lo)
        nd = lo + INVPHI * (hi - lo)
        # golden-section reuses one point; recompute both for simplicity of masking
        c, d = nc, nd
        fc, fd = energy_points(c, th, r), energy_points(d, th, r)
    xm = 0.5 * (lo + hi)
    fm = energy_points(xm, th, r)
    best = np.argmin(fm, axis=1)
    return np.mod(xm[np.arange(S), best], 2 * np.pi)


def simulate_vectorized(G, init, chunk=100):
    S = init.shape[0]
    M = GRID
    grid = np.arange(M) * (2 * np.pi / M)
    cg, sg = np.cos(grid).astype(np.float32), np.sin(grid).astype(np.float32)
    theta = np.zeros((S, N_TOTAL))
    theta[:, :N_INIT] = init
    km = kmax(G)
    for k in range(N_INIT, N_TOTAL):
        j0 = max(0, k - km)
        ages = k - np.arange(j0, k)
        r = np.exp(G * ages)
        for s0 in range(0, S, chunk):
            sl = slice(s0, s0 + chunk)
            theta[sl, k] = place_vectorized(theta[sl, j0:k], r, grid, cg, sg)
    div = wrap(np.diff(theta, axis=1))
    return div[:, -N_TAIL:], km


# ---------------- independent scalar reference ----------------

def simulate_reference(G, init):
    th = list(init)
    km = kmax(G)
    grid = [2 * math.pi * i / REF_GRID for i in range(REF_GRID)]

    def energy(x, prim):
        e = 0.0
        for t, rad in prim:
            e += (1.0 + rad * rad - 2.0 * rad * math.cos(x - t)) ** -1.5
        return e

    for k in range(N_INIT, N_TOTAL):
        prim = [(th[j], math.exp(G * (k - j))) for j in range(max(0, k - km), k)]
        E = [energy(x, prim) for x in grid]
        mins = [i for i in range(REF_GRID) if E[i] <= E[i - 1] and E[i] <= E[(i + 1) % REF_GRID]]
        mins.sort(key=lambda i: E[i])
        best_x, best_e = None, math.inf
        for i in mins[:N_CAND]:
            a, b = grid[i] - 2 * math.pi / REF_GRID, grid[i] + 2 * math.pi / REF_GRID
            while b - a > GS_TOL:
                c, d = b - INVPHI * (b - a), a + INVPHI * (b - a)
                if energy(c, prim) < energy(d, prim):
                    b = d
                else:
                    a = c
            x = 0.5 * (a + b)
            e = energy(x, prim)
            if e < best_e:
                best_x, best_e = x, e
        th.append(best_x % (2 * math.pi))
    div = [math.remainder(th[i + 1] - th[i], 2 * math.pi) for i in range(N_TOTAL - 1)]
    return div[-N_TAIL:]


# ---------------- classification ----------------

def periodic_signature(f, p):
    meds = [float(np.median(f[i::p])) for i in range(p)]
    ok = all(np.max(np.abs(f[i::p] - meds[i])) <= TOL for i in range(p))
    return ok, meds


def signature(f):
    """f: folded |divergence| over the tail. Returns (kind, values) with smallest period."""
    for p, kind in ((1, "const"), (2, "p2"), (3, "p3"), (4, "p4")):
        ok, meds = periodic_signature(f, p)
        if ok:
            return kind, meds
    return "nonperiodic", []


def matches_listed(f, kind_vals):
    kind, vals = kind_vals
    if kind == "const":
        return bool(np.all(np.abs(f - vals[0]) <= TOL))
    for phase in (0, 1):
        pat = np.array([vals[(i + phase) % 2] for i in range(len(f))])
        if np.all(np.abs(f - pat) <= TOL):
            return True
    return False


def parastichy_pair(d, G, mmax=300):
    if abs(abs(d) - math.pi) <= TOL:
        return (1, 2)
    m = np.arange(1, mmax + 1)
    ang = wrap(m * d)
    ln = np.hypot(ang, m * G)
    m1 = int(np.argmin(ln))
    s1 = np.sign(ang[m1])
    opp = np.where(np.sign(ang) == -s1)[0]
    m2 = int(opp[np.argmin(ln[opp])])
    return tuple(sorted((int(m[m1]), int(m[m2]))))


def branch_of(kind, vals, G):
    if kind == "const":
        pair = parastichy_pair(vals[0], G)
        if pair in FIB_PAIRS:
            return "fibonacci", pair
        if pair in LUC_PAIRS:
            return "lucas", pair
        return "other", pair
    if kind == "p2" and any(abs(v - math.pi) <= 0.05 for v in vals):
        return "bijugate", None
    return "other", None


def classify_G(G, tail):
    """tail (S, N_TAIL) signed divergences -> per-seed labels and class table."""
    S = tail.shape[0]
    folded = np.abs(tail)
    labels = [None] * S
    unclassified = []
    for s in range(S):
        f = folded[s]
        for name, kv in LISTED.items():
            if matches_listed(f, kv):
                labels[s] = name
                break
        else:
            unclassified.append((s, *signature(f)))
    # single-linkage merge of unclassified signatures at TOL on sorted medians
    groups = []  # each: dict(kind, members, vals list)
    for s, kind, vals in unclassified:
        key = sorted(vals)
        placed = None
        for g in groups:
            if g["kind"] != kind:
                continue
            if kind == "nonperiodic" or any(
                max(abs(a - b) for a, b in zip(key, other)) <= TOL for other in g["keys"]
            ):
                placed = g
                break
        if placed is None:
            placed = {"kind": kind, "members": [], "keys": []}
            groups.append(placed)
        placed["members"].append(s)
        placed["keys"].append(key)
    classes = {}
    for name in LISTED:
        idx = [s for s in range(S) if labels[s] == name]
        if idx:
            kind, vals = LISTED[name]
            classes[name] = {"listed": True, "kind": kind, "values": vals, "members": idx}
    for g in groups:
        vals = list(np.median(np.array(g["keys"]), axis=0)) if g["kind"] != "nonperiodic" else []
        deg = "/".join(f"{math.degrees(v):.3f}" for v in vals) if vals else "-"
        name = f"unclassified:{g['kind']}:{deg}"
        while name in classes:
            name += "'"
        for s in g["members"]:
            labels[s] = name
        classes[name] = {"listed": False, "kind": g["kind"], "values": vals, "members": g["members"]}
    for name, c in classes.items():
        if c["listed"]:
            c["branch"] = {"golden": "fibonacci", "lucas": "lucas"}.get(name, "bijugate")
            c["pair"] = parastichy_pair(c["values"][0], G) if c["kind"] == "const" else None
        else:
            c["branch"], c["pair"] = branch_of(c["kind"], c["values"], G)
    return labels, classes


def bootstrap(labels, names, rng):
    S = len(labels)
    lab_idx = np.array([names.index(l) for l in labels])
    draws = rng.integers(0, S, size=(N_BOOT, S))
    counts = np.stack([(lab_idx[draws] == i).sum(axis=1) for i in range(len(names))], axis=1) / S
    return np.percentile(counts, 2.5, axis=0), np.percentile(counts, 97.5, axis=0)


def spearman(x, y):
    def rank(a):
        a = np.asarray(a, float)
        order = np.argsort(a, kind="mergesort")
        r = np.empty(len(a))
        r[order] = np.arange(len(a))
        for v in np.unique(a):
            m = a == v
            r[m] = r[m].mean()
        return r
    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


# ---------------- driver ----------------

def run_one(args):
    G, init, cache = args
    path = os.path.join(cache, f"G_{G:.8f}_S{init.shape[0]}.npy")
    if os.path.exists(path):
        return G, np.load(path), None
    t0 = time.time()
    tail, _ = simulate_vectorized(G, init)
    np.save(path, tail)
    return G, tail, time.time() - t0


def run_ref(args):
    G, s, init_row = args
    return G, s, simulate_reference(G, init_row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-g", type=int, default=N_G_FULL)
    ap.add_argument("--seeds", type=int, default=500)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "phyllo-atlas-cache"))
    ap.add_argument("--skip-crosscheck", action="store_true")
    ap.add_argument("--time-only", type=float, default=None, help="time one G and exit")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    init_all = initial_angles(500)
    init = init_all[: a.seeds]
    if a.time_only is not None:
        t0 = time.time()
        simulate_vectorized(a.time_only, init)
        print(f"G={a.time_only} seeds={a.seeds}: {time.time() - t0:.1f}s")
        return
    Gs = g_values(a.n_g)
    t_start = time.time()
    tails = {}
    with Pool(a.jobs) as pool:
        for G, tail, dt in pool.imap_unordered(run_one, [(G, init, a.cache) for G in Gs[::-1]]):
            tails[G] = tail
            print(f"G={G:.5f} done ({'cached' if dt is None else f'{dt:.0f}s'}) {len(tails)}/{len(Gs)}",
                  flush=True)
    sim_wall = time.time() - t_start

    cross = []
    if not a.skip_crosscheck:
        cg_idx = np.unique(np.round(np.linspace(0, len(Gs) - 1, 5)).astype(int))
        jobs = [(Gs[i], s, init[s]) for i in cg_idx for s in range(min(4, a.seeds))]
        with Pool(a.jobs) as pool:
            for G, s, ref_tail in pool.imap_unordered(run_ref, jobs):
                diff = float(np.max(np.abs(np.abs(np.array(ref_tail)) - np.abs(tails[G][s]))))
                cross.append({"G": float(G), "seed": s, "max_abs_diff_rad": diff})
        cross.sort(key=lambda c: (c["G"], c["seed"]))

    rng = np.random.default_rng(SEED_BOOT)
    rows = []
    per_G = []
    for G in sorted(tails):
        labels, classes = classify_G(G, tails[G])
        names = sorted(classes, key=lambda n: -len(classes[n]["members"]))
        lo, hi = bootstrap(labels, names, rng)
        S = len(labels)
        for i, n in enumerate(names):
            c = classes[n]
            rows.append({
                "G": f"{G:.6f}", "class": n, "listed": c["listed"], "kind": c["kind"],
                "values_deg": "/".join(f"{math.degrees(v):.4f}" for v in c["values"]),
                "branch": c["branch"], "parastichy_pair": "" if c["pair"] is None else f"{c['pair'][0]}:{c['pair'][1]}",
                "n": len(c["members"]), "fraction": round(len(c["members"]) / S, 4),
                "ci95_lo": round(float(lo[i]), 4), "ci95_hi": round(float(hi[i]), 4),
            })
        modal = classes[names[0]]
        unl = [(n, len(classes[n]["members"]) / S) for n in names if not classes[n]["listed"]]
        per_G.append({
            "G": float(G), "modal_class": names[0], "modal_pair": modal["pair"],
            "modal_kind": modal["kind"], "modal_fraction": len(modal["members"]) / S,
            "listed_fraction": sum(len(c["members"]) for c in classes.values() if c["listed"]) / S,
            "max_unclassified_fraction": max([f for _, f in unl], default=0.0),
            "max_offbranch_fraction": max([len(c["members"]) / S for c in classes.values()
                                           if c["branch"] == "other"], default=0.0),
            "nonperiodic_fraction": sum(len(c["members"]) for c in classes.values()
                                        if c["kind"] == "nonperiodic") / S,
        })

    with open(os.path.join(DERIVED, "basin-volumes.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    list_fail_G = [p for p in per_G if p["max_unclassified_fraction"] > 0.01]
    branch_fail_G = [p for p in per_G if p["max_offbranch_fraction"] > 0.01]
    const_modal = [p for p in per_G if p["modal_pair"] is not None and p["modal_kind"] == "const"]
    pairs = sorted({tuple(p["modal_pair"]) for p in const_modal})
    rho = spearman([p["G"] for p in const_modal], [sum(p["modal_pair"]) for p in const_modal]) \
        if const_modal else float("nan")
    if len(pairs) >= 3 and rho <= -0.9:
        claim_verdict = "supports"
    elif len(pairs) == 1:
        claim_verdict = "refutes"
    else:
        claim_verdict = "mixed"
    max_cross = max([c["max_abs_diff_rad"] for c in cross], default=None)
    summary = {
        "grid_run": {"n_G": len(Gs), "G_min": float(Gs.min()), "G_max": float(Gs.max()),
                     "seeds_per_G": a.seeds, "primordia": N_TOTAL, "tail": N_TAIL,
                     "grid_angles": GRID, "cutoff_r_minus_1": CUTOFF,
                     "kept_primordia_at_G_min": kmax(float(Gs.min())),
                     "simulation_wall_s": round(sim_wall, 1)},
        "list_test": {"G_values_failing": len(list_fail_G),
                      "outcome": "falsified" if list_fail_G else "not falsified",
                      "max_unclassified_fraction": max(p["max_unclassified_fraction"] for p in per_G),
                      "total_listed_fraction_mean": float(np.mean([p["listed_fraction"] for p in per_G])),
                      "G_with_listed_fraction_above_0.99": [p["G"] for p in per_G if p["listed_fraction"] > 0.99]},
        "branch_test": {"G_values_failing": len(branch_fail_G),
                        "outcome": "falsified" if branch_fail_G else "not falsified",
                        "failing_G": [p["G"] for p in branch_fail_G],
                        "max_offbranch_fraction": max(p["max_offbranch_fraction"] for p in per_G)},
        "claim_test": {"distinct_modal_pairs": [list(p) for p in pairs], "spearman_G_vs_m_plus_n": rho,
                       "n_G_const_modal": len(const_modal), "verdict": claim_verdict},
        "crosscheck": {"cases": cross, "max_abs_diff_rad": max_cross,
                       "bug_signature": None if max_cross is None else bool(max_cross > TOL)},
        "per_G": per_G,
    }
    with open(os.path.join(DERIVED, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else o)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_G"}, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
