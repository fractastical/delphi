#!/usr/bin/env python3
"""Test of wolfram2002-ch03-14: two-block cyclic tag systems with random-looking growth fluctuations.

Family: all cyclic tag systems with two blocks, each block a binary string of length 0..3
(15 choices per block, 225 systems), started from the single-element sequence {1}.
Update (NKS p. 95, note p. 895): remove the first element; if it was 1, append the current
block; blocks alternate on successive steps.

Only the leading elements matter, so the whole history is stored as one growing tape:
at step t the sequence is tape[t:], its length is len(tape) - t.

Run:  python3 analysis.py            (writes derived/systems.csv and prints the measured block)
"""
import csv
import itertools
import json
import lzma
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCREEN_STEPS = 100_000
TEST_STEPS = 1_000_000
MIN_LEN_SCREEN = 1000
R2_MIN = 0.999
LOCAL_RATE_TOL = 0.25
HURST_RANGE = (0.35, 0.65)
BITS_PER_SYMBOL_MIN = 0.25
N_WINDOWS = 10
TAUS = [2 ** k for k in range(0, 14)]


def blocks():
    out = []
    for length in range(0, 4):
        for bits in itertools.product((0, 1), repeat=length):
            out.append(bytes(bits))
    return out  # 15 blocks: '', 0, 1, 00, 01, 10, 11, 000, ..., 111


def run(rule, steps):
    """Return (lengths array of len steps+1, leading bits array of len steps, died_at or None)."""
    b0, b1 = rule
    tape = bytearray(b"\x01")
    lengths = np.empty(steps + 1, dtype=np.int64)
    lengths[0] = 1
    for t in range(steps):
        if t >= len(tape):
            lengths[t + 1:] = 0
            return lengths, np.frombuffer(bytes(tape), dtype=np.uint8), t
        if tape[t]:
            tape += b0 if (t % 2 == 0) else b1
        lengths[t + 1] = len(tape) - (t + 1)
    lead = np.frombuffer(bytes(tape[:steps]), dtype=np.uint8)
    return lengths, lead, None


def linear_fit(y):
    t = np.arange(len(y), dtype=np.float64)
    b, a = np.polyfit(t, y, 1)
    resid = y - (a + b * t)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return a, b, r2, resid


def local_rates(y, n_windows):
    n = len(y) - 1
    edges = np.linspace(0, n, n_windows + 1).astype(int)
    return [(y[edges[i + 1]] - y[edges[i]]) / max(1, edges[i + 1] - edges[i]) for i in range(n_windows)]


def hurst(resid, taus):
    xs, ys = [], []
    for tau in taus:
        if tau >= len(resid) // 4:
            break
        d = resid[tau:] - resid[:-tau]
        v = float(np.mean(d ** 2))
        if v <= 0:
            return 0.0
        xs.append(np.log(tau))
        ys.append(np.log(v))
    if len(xs) < 3:
        return float("nan")
    slope = np.polyfit(xs, ys, 1)[0]
    return float(slope / 2.0)


def bits_per_symbol(lead):
    packed = np.packbits(lead).tobytes()
    comp = lzma.compress(packed, preset=9 | lzma.PRESET_EXTREME)
    return 8.0 * len(comp) / len(lead)


def fmt(rule):
    return "{" + ",".join("{" + ",".join(str(x) for x in b) + "}" for b in rule) + "}"


def main():
    t0 = time.time()
    B = blocks()
    rules = [(x, y) for x in B for y in B]
    assert len(rules) == 225
    rows = []
    growing = []
    for rule in rules:
        lengths, lead, died = run(rule, SCREEN_STEPS)
        final = int(lengths[-1]) if died is None else 0
        is_growing = died is None and final >= MIN_LEN_SCREEN
        rows.append({"rule": fmt(rule), "screen_final_length": final, "died_at": died, "growing": is_growing})
        if is_growing:
            growing.append(rule)
    print(f"screen done: {len(growing)} growing of {len(rules)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    results = {}
    for rule in growing:
        lengths, lead, died = run(rule, TEST_STEPS)
        a, b, r2, resid = linear_fit(lengths.astype(np.float64))
        rates = local_rates(lengths, N_WINDOWS)
        steady = r2 >= R2_MIN and b > 0 and all(abs(r - b) <= LOCAL_RATE_TOL * b for r in rates)
        # zero-amplitude residuals (all-ones tapes) have no fluctuations to scale; treat H as 0
        H = hurst(resid, TAUS) if np.max(np.abs(resid)) >= 1.0 else 0.0
        bps = bits_per_symbol(lead)
        ones_in_blocks = sum(rule[0]) + sum(rule[1])
        res = {
            "rule": fmt(rule),
            "final_length": int(lengths[-1]),
            "slope": round(float(b), 5),
            "uncorrelated_drift": ones_in_blocks / 2 - 1,
            "r2": round(float(r2), 6),
            "local_rate_min": round(float(min(rates)), 4),
            "local_rate_max": round(float(max(rates)), 4),
            "steady": bool(steady),
            "hurst": round(H, 3),
            "hurst_ok": bool(HURST_RANGE[0] <= H <= HURST_RANGE[1]),
            "lead_ones_fraction": round(float(lead.mean()), 4),
            "bits_per_symbol": round(bps, 4),
            "incompressible": bool(bps >= BITS_PER_SYMBOL_MIN),
            "max_abs_resid": round(float(np.max(np.abs(resid))), 1),
        }
        res["passes"] = bool(res["steady"] and res["hurst_ok"] and res["incompressible"])
        results[fmt(rule)] = res
        print(f"{res['rule']:>22} L={res['final_length']:>8} b={res['slope']:.4f} R2={res['r2']:.5f} "
              f"H={res['hurst']:.3f} bps={res['bits_per_symbol']:.3f} steady={res['steady']} pass={res['passes']}",
              file=sys.stderr)

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    fields = ["rule", "screen_final_length", "died_at", "growing", "final_length", "slope", "uncorrelated_drift", "r2",
              "local_rate_min", "local_rate_max", "steady", "hurst", "hurst_ok", "lead_ones_fraction",
              "bits_per_symbol", "incompressible", "max_abs_resid", "passes"]
    with open(os.path.join(HERE, "derived", "systems.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            row = dict(row)
            row.update(results.get(row["rule"], {}))
            w.writerow({k: row.get(k, "") for k in fields})

    passing = [r for r in results.values() if r["passes"]]
    book = {name: results.get(key) for name, key in
            (("d", "{{1},{1,0,1}}"), ("e", "{{1,1,1},{0}}"), ("c_nested_control", "{{1,0},{1,1}}"))}
    # Calibration controls for criterion (iii), not part of the pre-registered decision:
    # an i.i.d. Bernoulli(3/4) sequence and a first-order Markov chain with no '00' and P(1)=3/4
    # (the local statistics Wolfram reports for example (d)), both of length TEST_STEPS.
    rng = np.random.default_rng(20261031)
    bern = (rng.random(TEST_STEPS) < 0.75).astype(np.uint8)
    markov = np.empty(TEST_STEPS, dtype=np.uint8)
    markov[0] = 1
    u = rng.random(TEST_STEPS)
    for i in range(1, TEST_STEPS):
        markov[i] = 1 if markov[i - 1] == 0 else (0 if u[i] < 1 / 3 else 1)
    controls = {
        "bernoulli_0.75_bits_per_symbol": round(bits_per_symbol(bern), 4),
        "markov_no00_p1_0.75_bits_per_symbol": round(bits_per_symbol(markov), 4),
        "markov_no00_entropy_rate_bits": round(0.75 * (-(1 / 3) * np.log2(1 / 3) - (2 / 3) * np.log2(2 / 3)), 4),
    }
    measured = {
        "value": len(passing),
        "unit": "systems passing all three pre-registered criteria",
        "n": len(rules),
        "uncertainty": None,
        "extra": {
            "growing_systems": len(growing),
            "steady_growth": sum(r["steady"] for r in results.values()),
            "hurst_in_range": sum(r["hurst_ok"] for r in results.values()),
            "incompressible": sum(r["incompressible"] for r in results.values()),
            "passing_rules": [r["rule"] for r in passing],
            "book_examples": book,
            "compression_controls": controls,
            "steady_and_hurst_only": [r["rule"] for r in results.values() if r["steady"] and r["hurst_ok"]],
            "test_steps": TEST_STEPS,
            "screen_steps": SCREEN_STEPS,
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
