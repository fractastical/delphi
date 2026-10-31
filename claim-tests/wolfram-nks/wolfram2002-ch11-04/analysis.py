#!/usr/bin/env python3
"""Test of wolfram2002-ch11-04: one fixed universal rule (the NKS 19-colour
universal cellular automaton) realises behaviour of widely different
complexity depending only on the encoded initial condition.

Reuses the rule list and encoding of the ch11-06 test (fetched live if
possible, else from derived/uca_rule.txt).  Complexity = lzma compressibility.
"""
import hashlib
import html
import json
import lzma
import math
import os
import random
import re
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "wolfram2002-ch11-06"))
import analysis as uca  # noqa: E402  (parse_rules, build_table, uca_step, encode, target_step, period)

NOTE_URL = uca.NOTE_URL
N = 128
S = 128
SEED = 20261104
K = 19


def load_rule_text():
    rule_path = os.path.join(HERE, "derived", "uca_rule.txt")
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    rec = None
    try:
        import requests
        t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        resp = requests.get(NOTE_URL, timeout=60)
        resp.raise_for_status()
        page = resp.content
        rec = {"download_url": NOTE_URL, "retrieved_at": t0, "byte_size": len(page),
               "sha256": hashlib.sha256(page).hexdigest()}
        text = page.decode("utf-8", "ignore").replace("&#62754;", "->")
        m = re.search(r'<span class="c2c-copyable c2c-block">(\{\{_, 3, 7, 18, _\}.*?)</span></p>', text, re.S)
        rule_text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
        with open(rule_path, "w") as f:
            f.write(rule_text + "\n")
    except Exception as e:
        print("fetch failed, using derived copy:", e, file=sys.stderr)
        if not os.path.exists(rule_path):
            src = os.path.join(HERE, "..", "wolfram2002-ch11-06", "derived", "uca_rule.txt")
            shutil.copy(src, rule_path)
        with open(rule_path) as f:
            rule_text = f.read().split("\n\n")[0].strip()
    return rule_text, rec


def rho(arr, alphabet):
    a = np.ascontiguousarray(arr, dtype=np.uint8)
    return 8 * len(lzma.compress(a.tobytes(), preset=9)) / (a.size * math.log2(alphabet))


def run_target(table, rtab):
    config = [0] * N
    config[N // 2] = 1
    row = uca.encode(config, 1, rtab)
    P = uca.period(1)
    raw_rows, dec_rows, ref_rows = [], [], []
    mism = 0
    for _ in range(S):
        for _ in range(P):
            row = uca.uca_step(row, table)
        config = uca.target_step(config, 1, rtab)
        ref = uca.encode(config, 1, rtab)
        mism += int((row != ref).sum())
        raw_rows.append(row.copy())
        dec_rows.append(np.array([1 - row[20 * i + 2] // 18 for i in range(N)], dtype=np.uint8))
        ref_rows.append(np.array(config, dtype=np.uint8))
    raw = np.array(raw_rows)
    dec = np.array(dec_rows)
    refa = np.array(ref_rows)
    return {"mismatches": mism, "decoded_equals_target": bool((dec == refa).all()),
            "rho_dec": rho(dec, 2), "rho_ref": rho(refa, 2), "rho_raw": rho(raw, K)}


def main():
    rule_text, rec = load_rule_text()
    table = uca.build_table(uca.parse_rules(rule_text))
    rng = random.Random(SEED)
    while True:
        rnd = rng.randrange(256)
        if rnd % 2 == 0:  # f(000) = 0
            break
    targets = [("rule_250", 250), ("rule_90", 90), ("rule_110", 110), ("rule_30", 30), (f"rule_{rnd}_random", rnd)]
    results = {}
    for name, rule in targets:
        rtab = [(rule >> i) & 1 for i in range(7, -1, -1)]
        results[name] = run_target(table, rtab)
        print(name, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in results[name].items()}))
    cond_i = all(r["rho_dec"] == r["rho_ref"] and r["mismatches"] == 0 for r in results.values())
    r250, r90, r30 = results["rule_250"]["rho_raw"], results["rule_90"]["rho_raw"], results["rule_30"]["rho_raw"]
    cond_ii = (r250 < r90 < r30) and (r30 >= 2 * r250)
    if not cond_i:
        verdict = "refutes"
    elif cond_ii:
        verdict = "supports"
    else:
        verdict = "mixed"
    summary = {"note_file": rec, "N": N, "S": S, "seed": SEED, "random_rule": rnd,
               "results": results, "condition_i_decoded_complexity_equal": cond_i,
               "condition_ii_raw_ordering": cond_ii, "raw_ratio_30_over_250": r30 / r250, "verdict": verdict}
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    measured = {"value": round(r30 / r250, 3),
                "unit": "ratio of raw universal-automaton compressibility rho_raw when emulating rule 30 to that when emulating rule 250 (same rule, different initial condition)",
                "n": 5,
                "uncertainty": "deterministic for the fixed initial conditions",
                "extra": {"per_target": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in results.items()},
                          "condition_i": cond_i, "condition_ii": cond_ii, "N": N, "S": S, "random_rule": rnd}}
    print(json.dumps({"note_file": rec, "measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
