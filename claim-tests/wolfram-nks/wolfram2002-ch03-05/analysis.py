#!/usr/bin/env python3
"""Test of wolfram2002-ch03-05: fraction of the 2187 three-colour totalistic CA
that are 'ultimately regular' from a single gray cell.

Regular := late-time central strip is time-periodic (p <= 256) or compresses
below a threshold tau calibrated on classical nested patterns (upper class) and
elementary class-3/class-4 rules (lower class).  Writes derived/census.csv and
derived/summary.json; prints the measured block.
"""
import json
import lzma
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 3000
HALF = 64
MARGIN = 2 * HALF
R0, R1 = 1500, 3000
P0 = 2250
PMAX = 256


def rho(arr, alphabet):
    a = np.ascontiguousarray(arr, dtype=np.uint8)
    return 8 * len(lzma.compress(a.tobytes(), preset=9)) / (a.size * math.log2(alphabet))


def run_tot3(code, T):
    table = np.array([(code // 3 ** k) % 3 for k in range(7)], dtype=np.uint8)
    w = 2 * (T + MARGIN) + 1
    rows = np.zeros((T, w), dtype=np.uint8)
    row = np.zeros(w, dtype=np.uint8)
    row[T + MARGIN] = 1
    for t in range(T):
        rows[t] = row
        s = np.roll(row, 1).astype(np.int16) + row + np.roll(row, -1)
        s[0] = row[0] + row[1]
        s[-1] = row[-1] + row[-2]
        row = table[s]
    return rows


def run_eca(rule, T):
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


def is_periodic(rows):
    c = rows.shape[1] // 2
    s = rows[P0:R1, c - HALF:c + HALF]
    n = s.shape[0]
    for p in range(1, PMAX + 1):
        if np.array_equal(s[p:], s[:n - p]):
            return True, p
    return False, 0


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
    w = 2 * T + 1
    rows = np.zeros((T, w), dtype=np.uint8)
    row = np.zeros(w, dtype=np.int64)
    row[T] = 1
    for t in range(T):
        rows[t] = (row % m).astype(np.uint8)
        row = (np.roll(row, 1) + np.roll(row, -1)) % m
    return rows


def calibrate():
    nr, nc = R1 - R0, 2 * HALF
    nested = {
        "pascal_mod3": rho(strip(pascal_mod(3, T)), 3),
        "pascal_mod2": rho(strip(pascal_mod(2, T)), 2),
    }
    tm = thue_morse(R1)
    nested["thue_morse_outer"] = rho(tm[R0:R1, None] ^ tm[None, :nc], 2)
    pd = period_doubling(R1)
    nested["period_doubling_outer"] = rho(pd[R0:R1, None] ^ pd[None, :nc], 2)
    irregular = {}
    for r in (110, 124, 137, 193, 30, 45):
        irregular[f"eca_{r}"] = rho(strip(run_eca(r, T)), 2)
    tau = math.sqrt(max(nested.values()) * min(irregular.values()))
    ok = max(nested.values()) < min(irregular.values())
    return {"nested": nested, "irregular": irregular, "tau": tau, "separated": ok}


def main():
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    cal = calibrate()
    print("calibration:", json.dumps(cal))
    if not cal["separated"]:
        print(json.dumps({"verdict": "inconclusive", "reason": "other"}))
        return
    tau = cal["tau"]
    rand_min = min(v for k, v in cal["irregular"].items() if k in ("eca_30", "eca_45"))
    out = []
    for code in range(2187):
        rows = run_tot3(code, T)
        per, p = is_periodic(rows)
        r = rho(strip(rows), 3)
        regular = per or r < tau
        out.append((code, per, p, r, regular))
    with open(os.path.join(HERE, "derived", "census.csv"), "w") as f:
        f.write("code,periodic,period,rho,regular\n")
        for code, per, p, r, reg in out:
            f.write(f"{code},{int(per)},{p},{r:.4f},{int(reg)}\n")
    n_reg = sum(1 for o in out if o[4])
    frac = n_reg / 2187
    irregular = [o for o in out if not o[4]]
    n_random_like = sum(1 for o in irregular if o[3] >= rand_min)
    if 0.80 <= frac <= 0.90:
        verdict = "supports"
    elif frac < 0.70 or frac > 0.95:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {"calibration": cal, "n_regular": n_reg, "fraction_regular": frac,
               "n_periodic": sum(1 for o in out if o[1]),
               "n_compressible_nonperiodic": sum(1 for o in out if o[4] and not o[1]),
               "n_irregular": len(irregular), "n_irregular_random_like": n_random_like,
               "irregular_codes": [o[0] for o in irregular],
               "irregular_rho": {o[0]: round(o[3], 3) for o in irregular}, "verdict": verdict}
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    measured = {
        "value": round(frac, 4),
        "unit": "fraction of the 2187 codes classified regular (late-time strip periodic with p <= 256, or rho < tau)",
        "n": 2187,
        "uncertainty": "deterministic given tau = %.3f; a few long-transient codes may be misclassified at T = 3000" % tau,
        "extra": {"tau": round(tau, 4), "calibration": {k: ({kk: round(vv, 4) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in cal.items()},
                  "n_regular": n_reg, "n_periodic": summary["n_periodic"],
                  "n_compressible_nonperiodic": summary["n_compressible_nonperiodic"],
                  "n_irregular": len(irregular), "n_irregular_random_like": n_random_like,
                  "irregular_codes_first_60": [o[0] for o in irregular][:60]},
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
