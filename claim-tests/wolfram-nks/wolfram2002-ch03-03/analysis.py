#!/usr/bin/env python3
"""Test of wolfram2002-ch03-03: census of random-looking and nested elementary CA
from a single black cell, with a compressibility criterion calibrated on
reference patterns before the rules are run.

Writes derived/census.csv and derived/summary.json; prints the measured block.
"""
import json
import lzma
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 4096
HALF = 64          # strip half-width
R0, R1 = 1024, 4096
PMAX = 64
MARGIN = 2 * HALF
SEED = 20260303


def rho(arr):
    a = np.ascontiguousarray(arr, dtype=np.uint8)
    return 8 * len(lzma.compress(a.tobytes(), preset=9)) / a.size


def run_rule(rule, T):
    # Width 2(T+MARGIN)+1: rules with f(000)=1 flip the background, so the zero
    # boundary injects defects that travel inward at one cell per step; the margin
    # keeps them out of the central strip (|x| <= HALF) for all T steps.  (Bug fix
    # after the first run, which used width 2T+1 and let edge defects reach the strip
    # in its last 64 rows.)
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    w = 2 * (T + MARGIN) + 1
    rows = np.zeros((T, w), dtype=np.uint8)
    row = np.zeros(w, dtype=np.uint8)
    row[T + MARGIN] = 1
    for t in range(T):
        rows[t] = row
        l = np.roll(row, 1)
        r = np.roll(row, -1)
        l[0] = 0
        r[-1] = 0
        row = table[4 * l + 2 * row + r]
    return rows


def strip(rows):
    c = rows.shape[1] // 2
    return rows[R0:R1, c - HALF:c + HALF]


def is_periodic(s, pmax=PMAX):
    n = s.shape[0]
    half = n // 2
    for p in range(1, pmax + 1):
        if np.array_equal(s[half:, :], s[half - p:n - p, :]):
            return True, p
    return False, 0


def extent(row):
    nz = np.nonzero(row)[0]
    return 0 if len(nz) == 0 else int(nz[-1] - nz[0] + 1)


def reflect(rule):
    out = 0
    for i in range(8):
        l, c, r = (i >> 2) & 1, (i >> 1) & 1, i & 1
        j = 4 * r + 2 * c + l
        out |= ((rule >> i) & 1) << j
    return out


def complement(rule):
    out = 0
    for i in range(8):
        out |= (1 - ((rule >> (7 - i)) & 1)) << i
    return out


def sym_class(rule):
    return min(rule, reflect(rule), complement(rule), reflect(complement(rule)))


# ----------------------------------------------------------------------------- calibration
def thue_morse(n):
    t = np.zeros(1, dtype=np.uint8)
    while len(t) < n:
        t = np.concatenate([t, 1 - t])
    return t[:n]


def period_doubling(n):
    s = np.array([0], dtype=np.uint8)
    while len(s) < n:
        s = np.concatenate([[0, 1] if x == 0 else [0, 0] for x in s]).astype(np.uint8)
    return s[:n]


def pascal_mod(m, T):
    """Rows of Pascal's triangle mod m laid out like a CA pattern (centre column T)."""
    w = 2 * T + 1
    rows = np.zeros((T, w), dtype=np.uint8)
    row = np.zeros(w, dtype=np.int64)
    row[T] = 1
    for t in range(T):
        rows[t] = (row % m != 0).astype(np.uint8)
        row = (np.roll(row, 1) + np.roll(row, -1)) % m
    return rows


def calibrate(rng):
    nr, nc = R1 - R0, 2 * HALF
    random_refs = {f"iid_{k}": rho(rng.integers(0, 2, (nr, nc)).astype(np.uint8)) for k in range(3)}
    nested_refs = {}
    nested_refs["sierpinski_mod2"] = rho(strip(pascal_mod(2, T)))
    nested_refs["pascal_mod3"] = rho(strip(pascal_mod(3, T)))
    tm = thue_morse(R1).astype(np.uint8)
    nested_refs["thue_morse_outer"] = rho((tm[R0:R1, None] ^ tm[None, :nc]))
    pd = period_doubling(R1).astype(np.uint8)
    nested_refs["period_doubling_outer"] = rho((pd[R0:R1, None] ^ pd[None, :nc]))
    periodic_refs = {}
    for pt, ps in ((1, 1), (2, 3), (7, 5), (64, 16), (13, 1), (1, 16)):
        tile = rng.integers(0, 2, (pt, ps)).astype(np.uint8)
        periodic_refs[f"period_t{pt}_s{ps}"] = rho(np.tile(tile, (nr // pt + 1, nc // ps + 1))[:nr, :nc])
    tau = math.sqrt(min(random_refs.values()) * max(nested_refs.values()))
    ok = max(nested_refs.values()) < min(random_refs.values())
    return {"random": random_refs, "nested": nested_refs, "periodic": periodic_refs, "tau": tau, "separated": ok}


def main():
    rng = np.random.default_rng(SEED)
    cal = calibrate(rng)
    print("calibration:", json.dumps({k: v for k, v in cal.items()}, indent=None))
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    if not cal["separated"]:
        print(json.dumps({"verdict": "inconclusive", "reason": "other"}))
        return
    tau = cal["tau"]
    rows_out = []
    for rule in range(256):
        rows = run_rule(rule, T)
        s = strip(rows)
        r = rho(s)
        per, p = is_periodic(s)
        e_full, e_half = extent(rows[T - 1]), extent(rows[T // 2 - 1])
        growing = (e_half > 0 and e_full >= 1.2 * e_half) or (e_full > 64 and not per)
        N_full = int(rows.sum())
        N_half = int(rows[: T // 2].sum())
        D = math.log2(N_full / N_half) if N_half > 0 and N_full > N_half else 0.0
        wexp = math.log2(e_full / e_half) if e_half > 0 and e_full > 0 else 0.0
        if r >= tau:
            cls = "random"
        elif (not per) and growing:
            cls = "nested"
        else:
            cls = "regular"
        rows_out.append({"rule": rule, "rho": r, "periodic": per, "period": p, "extent_T": e_full,
                         "extent_T/2": e_half, "growing": growing, "D": D, "width_exp": wexp, "class": cls,
                         "sym_class": sym_class(rule)})
    with open(os.path.join(HERE, "derived", "census.csv"), "w") as f:
        f.write("rule,rho,periodic,period,extent_T,extent_half,growing,D,width_exp,class,sym_class\n")
        for e in rows_out:
            f.write(f"{e['rule']},{e['rho']:.4f},{int(e['periodic'])},{e['period']},{e['extent_T']},"
                    f"{e['extent_T/2']},{int(e['growing'])},{e['D']:.3f},{e['width_exp']:.3f},{e['class']},{e['sym_class']}\n")

    rnd = [e for e in rows_out if e["class"] == "random"]
    nst = [e for e in rows_out if e["class"] == "nested"]
    rnd_classes = sorted({e["sym_class"] for e in rnd})
    nested_bins = sorted({(round(e["D"], 1), "w~1" if e["width_exp"] > 0.75 else "w~0.5") for e in nst})
    n_r, n_n = len(rnd), len(nst)
    if n_r <= 5 or n_r >= 16 or n_n <= 14 or n_n >= 36:
        verdict = "refutes"
    elif 8 <= n_r <= 12 and len(rnd_classes) == 3 and 20 <= n_n <= 28:
        verdict = "supports"
    else:
        verdict = "mixed"
    summary = {"calibration": cal, "n_random": n_r, "random_rules": [e["rule"] for e in rnd],
               "random_sym_classes": rnd_classes, "n_nested": n_n, "nested_rules": [e["rule"] for e in nst],
               "nested_sym_classes": sorted({e["sym_class"] for e in nst}),
               "nested_bins_D_width": [list(map(str, b)) for b in nested_bins],
               "nested_D": {e["rule"]: round(e["D"], 3) for e in nst},
               "nested_width_exp": {e["rule"]: round(e["width_exp"], 3) for e in nst},
               "rho_random_rules": {e["rule"]: round(e["rho"], 3) for e in rnd},
               "rho_sorted_top_20": sorted(((round(e["rho"], 3), e["rule"]) for e in rows_out), reverse=True)[:20],
               "verdict": verdict}
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    measured = {
        "value": {"n_random_looking": n_r, "n_random_symmetry_classes": len(rnd_classes), "n_nested": n_n,
                  "n_nested_form_bins": len(nested_bins)},
        "unit": "rule counts (of 256)",
        "n": 256,
        "uncertainty": "deterministic given the calibrated threshold tau = %.3f" % tau,
        "extra": {"tau": round(tau, 4), "calibration": {k: ({kk: round(vv, 4) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in cal.items()},
                  "random_rules": [e["rule"] for e in rnd], "random_sym_classes": rnd_classes,
                  "nested_rules": [e["rule"] for e in nst],
                  "nested_bins_D_width": [list(map(str, b)) for b in nested_bins],
                  "rho_sorted_top_20": summary["rho_sorted_top_20"]},
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
