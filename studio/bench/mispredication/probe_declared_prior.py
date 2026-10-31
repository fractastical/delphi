"""Declared-prior probe of the mispredication claim. See PROBE_DECLARATION.md (committed before this script's output).
Usage: python3 -I probe_declared_prior.py [OUT_JSON]   (numpy only; ~20 s on one thread)"""
import json, sys
import numpy as np

SEED, N = 12345, 20000
GRID = [0.1, 0.5, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 4.0, 4.25, 5.0]
PRIORS = [30, 100, 1000]

def ensemble(rng, n, R):
    keep = []
    while sum(len(k) for k in keep) < n:
        m = 4 * n
        a, b, c, d = rng.uniform(-2, 2, (4, m)); Dv = np.exp(rng.uniform(0, np.log(R), m)); Du = np.ones(m)
        tr, det, s = a + d, a * d - b * c, Dv * a + Du * d
        ok = (tr < 0) & (det > 0) & (s > 0) & (s ** 2 > 4 * Du * Dv * det)
        keep.append(np.stack([a, b, c, d, Du, Dv], 1)[ok])
    return np.concatenate(keep)[:n]

def band(E):
    a, b, c, d, Du, Dv = E.T; det = a * d - b * c; s = Dv * a + Du * d; disc = np.sqrt(s ** 2 - 4 * Du * Dv * det)
    qm, qp = (s - disc) / (2 * Du * Dv), (s + disc) / (2 * Du * Dv)
    lam = 2 * np.pi / (det / (Du * Dv)) ** 0.25
    return np.sqrt(qm), np.sqrt(qp), lam

def mispredicted(E, x):
    km, kp, lam = band(E); L = x * lam
    lo, hi = L * km / np.pi, L * kp / np.pi
    n = np.floor(lo) + 1
    return ~((n < hi) & (n >= 1))

def direct_unstable(row, L, nmax=60):
    a, b, c, d, Du, Dv = row
    for n in range(1, nmax + 1):
        q = (n * np.pi / L) ** 2
        if np.linalg.eigvals(np.array([[a - Du * q, b], [c, d - Dv * q]])).real.max() > 0: return True
    return False

def main(out):
    rng = np.random.default_rng(SEED); res = {"seed": SEED, "n_per_prior": N, "grid": GRID, "priors": {}, "controls": {}}
    ens = {}
    for R in PRIORS:
        E = ensemble(rng, N, R); ens[R] = E; rows = {}
        for x in GRID:
            k = int(mispredicted(E, x).sum()); rows[str(x)] = {"mispredicted": k, "of": N, "pct": round(100 * k / N, 2)}
        res["priors"][f"Dv/Du log-uniform [1,{R}]"] = rows
    # control 1: half-integers exactly zero
    half = [x for x in GRID if (2 * x) == int(2 * x)]
    c1 = all(res["priors"][p][str(x)]["mispredicted"] == 0 for p in res["priors"] for x in half if x != 0.1)
    # control 2: x = 0.1 mostly mispredicted
    c2 = all(res["priors"][p]["0.1"]["pct"] > 90 for p in res["priors"])
    # control 3: band criterion == direct eigenvalues
    E = ens[100][:500]; mism = 0; checked = 0
    for x in (0.1, 0.7, 1.25, 1.75, 2.25, 3.4):
        km, kp, lam = band(E); band_mis = mispredicted(E, x)
        for i in range(len(E)):
            direct = not direct_unstable(E[i], x * lam[i]); checked += 1; mism += int(direct != band_mis[i])
    c3 = mism == 0
    res["controls"] = {"half_integer_exactly_zero": c1, "x0.1_over_90pct": c2, "band_equals_direct_eigenvalues": {"checked": checked, "disagreements": mism, "pass": c3}}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res["controls"])); [print(p, {x: v["pct"] for x, v in r.items()}) for p, r in res["priors"].items()]
    if not (c1 and c2 and c3): print("CONTROL FAILED"); sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "probe_declared_prior.json")
