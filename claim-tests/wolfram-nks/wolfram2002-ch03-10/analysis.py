#!/usr/bin/env python3
"""Test of wolfram2002-ch03-10: neighbour-independent (context-free) substitution
systems only produce nested patterns, operationalised as sub-exponential subword
complexity; neighbour-dependent systems can exceed the bound.

Run: python3 analysis.py   (needs numpy, requests)
"""
import csv
import datetime
import hashlib
import itertools
import json
import os

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = 1 << 15
MAX_ANALYSED = 1 << 17
MAX_STEPS = 40000
CONTROL_MAX_STEPS = 2000
BOUNDED_WINDOW = 60
N_MAX = 20
P20_LIMIT = 10_000
RATIO_LIMIT = 8.0
CONTROL_P20 = 20_000
OEIS = {
    "A010060": "https://oeis.org/A010060/b010060.txt",
    "A003849": "https://oeis.org/A003849/b003849.txt",
}


def fetch_bfile(url):
    t = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    raw = r.content
    vals = []
    for line in raw.decode().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        vals.append(int(line.split()[1]))
    return vals, {"download_url": url, "retrieved_at": t, "byte_size": len(raw),
                  "sha256": hashlib.sha256(raw).hexdigest()}


def all_strings(k, max_len, min_len=0):
    out = []
    for L in range(min_len, max_len + 1):
        for tup in itertools.product(range(k), repeat=L):
            out.append("".join(str(c) for c in tup))
    return out


def run_system(step, start, max_steps=MAX_STEPS):
    """Iterate a string map until TARGET symbols; returns (status, string, steps).
    status in {'growing', 'died', 'bounded', 'slow'}."""
    s = start
    hist = []
    for t in range(1, max_steps + 1):
        s = step(s)
        n = len(s)
        if n == 0:
            return "died", s, t
        if n >= TARGET:
            return "growing", s, t
        hist.append(n)
        if len(hist) >= 2 * BOUNDED_WINDOW and \
                max(hist[-BOUNDED_WINDOW:]) <= max(hist[-2 * BOUNDED_WINDOW:-BOUNDED_WINDOW]):
            return "bounded", s, t
    return "slow", s, max_steps


def subword_complexity(s, k, n_max):
    a = np.frombuffer(s[:MAX_ANALYSED].encode(), dtype=np.uint8).astype(np.int64) - ord("0")
    p = []
    code = np.zeros(len(a), dtype=np.int64)
    for n in range(1, n_max + 1):
        code = code[:len(a) - n + 1] * k + a[n - 1:]
        p.append(int(len(np.unique(code))))
    return p


def context_free_step(rhs):
    """Parallel replacement of every symbol by rhs[symbol] (str.replace via private
    placeholder characters is several times faster than str.translate here)."""
    tmp = {"0": "\x01", "1": "\x02", "2": "\x03"}
    items = [(c, tmp[c], rhs[c]) for c in sorted(rhs)]

    def step(s):
        for c, t, _ in items:
            s = s.replace(c, t)
        for _, t, r in items:
            s = s.replace(t, r)
        return s
    return step


def neighbour_step(rhs):
    """rhs[(c, r)] for c, r in {0, 1}; the last element is paired with colour 0."""
    table = {ord("0") + 2 * c + r: rhs[(c, r)] for c in range(2) for r in range(2)}

    def step(s):
        a = np.frombuffer(s.encode(), dtype=np.uint8) - ord("0")
        right = np.append(a[1:], 0)
        codes = (2 * a + right + ord("0")).astype(np.uint8).tobytes().decode()
        return codes.translate(table)
    return step


def context3_step(rhs):
    """rhs[4*left + 2*element + right]; boundary neighbours are colour 0."""
    table = {ord("0") + i: rhs[i] for i in range(8)}

    def step(s):
        a = np.frombuffer(s.encode(), dtype=np.uint8) - ord("0")
        left = np.insert(a[:-1], 0, 0)
        right = np.append(a[1:], 0)
        codes = (4 * left + 2 * a + right + ord("0")).astype(np.uint8).tobytes().decode()
        return codes.translate(table)
    return step


def main():
    res = {}
    rows = []

    def analyse_family(name, k, rhs_choices, start_symbols, make_step, describe):
        counts = {"systems": 0, "runs": 0, "growing": 0, "died": 0, "bounded": 0, "slow": 0}
        worst = {"p20": 0, "ratio": 0.0}
        violators = []
        for combo in itertools.product(rhs_choices, repeat=len(start_symbols) if name != "control" else 4):
            counts["systems"] += 1
            step = make_step(combo)
            for start in start_symbols:
                counts["runs"] += 1
                status, s, t = run_system(step, start, CONTROL_MAX_STEPS if name == "control" else MAX_STEPS)
                counts[status] += 1
                if status == "slow" and len(s) >= TARGET // 2:
                    # growth slower than one symbol per step: analysed at the length reached
                    p = subword_complexity(s, k, N_MAX)
                    rows.append({"family": name, "rule": describe(combo), "start": start, "steps": t,
                                 "status": "slow", "length": len(s), "p10": p[9], "p20": p[19],
                                 "ratio_p20_p10": round(p[19] / p[9], 3)})
                if status != "growing":
                    continue
                p = subword_complexity(s, k, N_MAX)
                ratio = p[19] / p[9]
                worst["p20"] = max(worst["p20"], p[19])
                worst["ratio"] = max(worst["ratio"], ratio)
                rows.append({"family": name, "rule": describe(combo), "start": start, "steps": t,
                             "status": status, "length": len(s), "p10": p[9], "p20": p[19],
                             "ratio_p20_p10": round(ratio, 3)})
                if name != "control" and (p[19] > P20_LIMIT or ratio > RATIO_LIMIT):
                    violators.append(describe(combo))
                if name == "control" and p[19] > CONTROL_P20 and ratio > RATIO_LIMIT:
                    violators.append(describe(combo))
        return counts, worst, violators

    # (a) 2 colours, replacement strings of length 0..3
    choices2 = all_strings(2, 3)
    c2, w2, v2 = analyse_family(
        "k2_len0to3", 2, choices2, ["0", "1"],
        lambda combo: context_free_step({"0": combo[0], "1": combo[1]}),
        lambda combo: "0->%s,1->%s" % combo)
    res["k2_len0to3"] = {"counts": c2, "worst": w2, "violating_rules": v2}
    print(res["k2_len0to3"], flush=True)

    # (b) 3 colours, replacement strings of length 0..2
    choices3 = all_strings(3, 2)
    c3, w3, v3 = analyse_family(
        "k3_len0to2", 3, choices3, ["0", "1", "2"],
        lambda combo: context_free_step({"0": combo[0], "1": combo[1], "2": combo[2]}),
        lambda combo: "0->%s,1->%s,2->%s" % combo)
    res["k3_len0to2"] = {"counts": c3, "worst": w3, "violating_rules": v3}
    print(res["k3_len0to2"], flush=True)

    # control: neighbour-dependent, 2 colours, (element, right neighbour) -> string of length 1..2
    choices_ctrl = all_strings(2, 2, min_len=1)
    pairs = [(0, 0), (0, 1), (1, 0), (1, 1)]
    cc, wc, vc = analyse_family(
        "control", 2, choices_ctrl, ["0", "1"],
        lambda combo: neighbour_step({pairs[i]: combo[i] for i in range(4)}),
        lambda combo: "00->%s,01->%s,10->%s,11->%s" % combo)
    ctrl_rows = [r for r in rows if r["family"] == "control"]
    n_exceed = sum(1 for r in ctrl_rows if r["p20"] > CONTROL_P20 and r["ratio_p20_p10"] > RATIO_LIMIT)
    res["control"] = {"counts": cc, "worst": wc, "runs_exceeding_both_thresholds": n_exceed,
                      "systems_exceeding_both_thresholds": len(set(vc)),
                      "example_rules": sorted(set(vc))[:5]}
    print(res["control"], flush=True)

    # exploratory (not pre-registered): 1500 random neighbour-dependent systems whose
    # replacement depends on (left neighbour, element, right neighbour), strings of
    # length 1..2, boundary neighbours taken as colour 0
    rng = np.random.default_rng(20261031)
    ext_best = {"p20": 0, "ratio": 0.0, "rule": None}
    ext_exceed = 0
    ext_growing = 0
    for _ in range(1500):
        rhs = [choices_ctrl[i] for i in rng.integers(0, len(choices_ctrl), 8)]
        step = context3_step(rhs)
        for start in ("0", "1"):
            status, s, t = run_system(step, start, CONTROL_MAX_STEPS)
            if status != "growing":
                continue
            ext_growing += 1
            p = subword_complexity(s, 2, N_MAX)
            ratio = p[19] / p[9]
            if p[19] > ext_best["p20"]:
                ext_best = {"p20": p[19], "ratio": round(ratio, 3), "rule": ",".join(
                    "%d%d%d->%s" % (i >> 2, (i >> 1) & 1, i & 1, rhs[i]) for i in range(8)), "start": start,
                    "length": len(s)}
            if p[19] > CONTROL_P20 and ratio > RATIO_LIMIT:
                ext_exceed += 1
    res["exploratory_control_context3_sampled"] = {"systems_sampled": 1500, "growing_runs": ext_growing,
                                                   "best": ext_best, "runs_exceeding_both_thresholds": ext_exceed}
    print(res["exploratory_control_context3_sampled"], flush=True)

    # OEIS checks
    datasets = {}
    tm_vals, datasets["A010060"] = fetch_bfile(OEIS["A010060"])
    s = "0"
    while len(s) < len(tm_vals):
        s = s.translate({ord("0"): "01", ord("1"): "10"})
    res["thue_morse_vs_A010060"] = {"terms": len(tm_vals),
                                    "mismatches": sum(1 for i, v in enumerate(tm_vals) if int(s[i]) != v)}
    fib_vals, datasets["A003849"] = fetch_bfile(OEIS["A003849"])
    s = "0"
    while len(s) < len(fib_vals):
        s = s.translate({ord("0"): "01", ord("1"): "0"})
    res["fibonacci_vs_A003849"] = {"terms": len(fib_vals),
                                   "mismatches": sum(1 for i, v in enumerate(fib_vals) if int(s[i]) != v)}
    print(res["thue_morse_vs_A010060"], res["fibonacci_vs_A003849"])

    # random reference for p(20) at the analysed length
    rng = np.random.default_rng(20261031)
    rs = "".join(map(str, rng.integers(0, 2, TARGET)))
    pr = subword_complexity(rs, 2, N_MAX)
    res["random_binary_reference_len_2^15"] = {"p10": pr[9], "p20": pr[19], "ratio": round(pr[19] / pr[9], 3)}

    res["datasets"] = datasets
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    # per-system summary of the neighbour-independent families (keeps the table < 200 KB)
    summary = {}
    for r in rows:
        if r["family"] == "control":
            continue
        key = (r["family"], r["rule"])
        cur = summary.setdefault(key, {"family": r["family"], "rule": r["rule"], "growing_starts": "",
                                       "max_length": 0, "max_p10": 0, "max_p20": 0, "max_ratio": 0.0})
        cur["growing_starts"] += r["start"] if r["status"] == "growing" else r["start"].lower() + "s"
        cur["max_length"] = max(cur["max_length"], r["length"])
        cur["max_p10"] = max(cur["max_p10"], r["p10"])
        cur["max_p20"] = max(cur["max_p20"], r["p20"])
        cur["max_ratio"] = max(cur["max_ratio"], r["ratio_p20_p10"])
    with open(os.path.join(HERE, "derived", "neighbour_independent_systems.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["family", "rule", "growing_starts", "max_length", "max_p10",
                                           "max_p20", "max_ratio"])
        wr.writeheader()
        wr.writerows(summary.values())
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
