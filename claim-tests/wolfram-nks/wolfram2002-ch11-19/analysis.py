#!/usr/bin/env python3
"""Test of wolfram2002-ch11-19: class 1/2 elementary CA transmit perturbations only over bounded distances.

Run: python3 analysis.py   (writes derived/rules.csv, derived/wikipedia.json, prints measured block)
"""
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N = 800
T_SETTLE = 1000
P_MAX = 64
T_DAMAGE = 400
FLIP = 400
TRIALS = 10
SETTLE_MIN = 9
W_BOUNDED = 20
W_SPREAD = 100
SEED = 20261033
WIKI_URL = "https://en.wikipedia.org/wiki/Elementary_cellular_automaton"
WIKI_CLASSES = {1: [0, 32, 160, 232], 2: [4, 108, 218, 250], 3: [22, 30, 126, 150, 182], 4: [110, 54]}


def rule_table(rule):
    return np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)


def step(x, table):
    idx = (np.roll(x, 1) << 2) | (x << 1) | np.roll(x, -1)
    return table[idx]


def run_rule(rule, rng):
    table = rule_table(rule)
    out = []
    for _ in range(TRIALS):
        x = rng.integers(0, 2, N, dtype=np.uint8)
        for _ in range(T_SETTLE):
            x = step(x, table)
        c = x
        period = 0
        y = c
        for p in range(1, P_MAX + 1):
            y = step(y, table)
            if np.array_equal(y, c):
                period = p
                break
        if period == 0:
            out.append({"settled": False, "period": 0, "width": None})
            continue
        a = c.copy()
        b = c.copy()
        b[FLIP] ^= 1
        width_half = None
        for t in range(1, T_DAMAGE + 1):
            a = step(a, table)
            b = step(b, table)
            if t == T_DAMAGE // 2:
                diff = np.flatnonzero(a != b)
                width_half = int(diff[-1] - diff[0] + 1) if diff.size else 0
        diff = np.flatnonzero(a != b)
        width = int(diff[-1] - diff[0] + 1) if diff.size else 0
        # width at T/2 is recorded post hoc (not part of the decision) to tell static damage from slow growth
        out.append({"settled": True, "period": period, "width": width, "width_half": width_half})
    return out


def fetch_wikipedia():
    try:
        import requests
        r = requests.get(WIKI_URL, headers={"User-Agent": "delphi-claim-tests/0.1 (research)"}, timeout=60)
        r.raise_for_status()
        data = r.content
        text = r.text
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    found = {}
    for cls, rules in WIKI_CLASSES.items():
        found[cls] = [r_ for r_ in rules if re.search(rf"[Rr]ule[ _]{r_}\b", text)]
    return {"ok": True, "download_url": WIKI_URL, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "rules_mentioned": found}


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    rows = []
    for rule in range(256):
        trials = run_rule(rule, rng)
        settled = [t for t in trials if t["settled"]]
        widths = [t["width"] for t in settled]
        op_class12 = len(settled) >= SETTLE_MIN
        if settled:
            if max(widths) <= W_BOUNDED:
                behaviour = "bounded"
            elif float(np.median(widths)) >= W_SPREAD:
                behaviour = "spreading"
            else:
                behaviour = "intermediate"
        else:
            behaviour = "n/a"
        rows.append({
            "rule": rule, "n_settled": len(settled), "operational_class12": op_class12,
            "periods": " ".join(str(t["period"]) for t in trials),
            "max_width": max(widths) if widths else None,
            "median_width": float(np.median(widths)) if widths else None,
            "behaviour": behaviour,
            "widths_t200_t400": " ".join(f"{t['width_half']}:{t['width']}" for t in settled),
            "growing_t200_to_t400": sum(t["width"] > t["width_half"] for t in settled),
        })
        if rule % 32 == 31:
            print(f"rule {rule} done ({time.time()-t0:.0f}s)", file=sys.stderr)

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "rules.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    wiki = fetch_wikipedia()
    with open(os.path.join(HERE, "derived", "wikipedia.json"), "w") as f:
        json.dump(wiki, f, indent=2)

    c12 = [r for r in rows if r["operational_class12"]]
    other = [r for r in rows if not r["operational_class12"]]
    bounded = [r for r in c12 if r["behaviour"] == "bounded"]
    spreading = [r for r in c12 if r["behaviour"] == "spreading"]
    inter = [r for r in c12 if r["behaviour"] == "intermediate"]
    by_rule = {r["rule"]: r for r in rows}
    validation = {
        f"class{cls}": {str(r_): {"operational_class12": by_rule[r_]["operational_class12"], "n_settled": by_rule[r_]["n_settled"],
                                  "behaviour": by_rule[r_]["behaviour"], "max_width": by_rule[r_]["max_width"]} for r_ in rules}
        for cls, rules in WIKI_CLASSES.items()
    }
    val_ok = all(by_rule[r_]["operational_class12"] for r_ in WIKI_CLASSES[1] + WIKI_CLASSES[2]) and \
        not any(by_rule[r_]["operational_class12"] for r_ in WIKI_CLASSES[3] + WIKI_CLASSES[4])
    # Non-settled rules: for their (few) settled trials, how often is the damage spreading? Also report
    # the fraction of non-class-1/2 rules with any settled trial.
    other_with_settled = [r for r in other if r["n_settled"] > 0]
    measured = {
        "value": round(len(bounded) / len(c12), 4) if c12 else None,
        "unit": "fraction of operational class 1/2 rules whose settled-state perturbation stays bounded (width <= 20 after 400 steps)",
        "n": len(c12),
        "uncertainty": None,
        "extra": {
            "class12_rules_n": len(c12),
            "class12_bounded_n": len(bounded),
            "class12_spreading": [(r["rule"], r["median_width"]) for r in spreading],
            "class12_intermediate": [(r["rule"], r["max_width"], r["median_width"], r["widths_t200_t400"]) for r in inter],
            "class12_trials_growing_between_t200_and_t400": sum(r["growing_t200_to_t400"] for r in c12),
            "class12_max_width_distribution": sorted(set(r["max_width"] for r in c12)),
            "non_class12_rules": [r["rule"] for r in other],
            "non_class12_with_some_settled_trials": [(r["rule"], r["n_settled"], r["behaviour"]) for r in other_with_settled],
            "validation_wikipedia_examples": validation,
            "validation_ok": val_ok,
            "wikipedia_fetch": {k: v for k, v in wiki.items() if k != "rules_mentioned"},
            "wikipedia_rules_mentioned": wiki.get("rules_mentioned"),
            "params": {"N": N, "T_settle": T_SETTLE, "P_max": P_MAX, "T_damage": T_DAMAGE, "flip_index": FLIP,
                       "trials": TRIALS, "settle_min": SETTLE_MIN, "w_bounded": W_BOUNDED, "w_spread": W_SPREAD, "seed": SEED},
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    print(json.dumps(measured, indent=2, default=str))


if __name__ == "__main__":
    main()
