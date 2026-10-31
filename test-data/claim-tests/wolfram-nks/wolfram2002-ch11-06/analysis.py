#!/usr/bin/env python3
"""Test of wolfram2002-ch11-06: Wolfram's 19-colour range-2 universal cellular
automaton, with the rule list and block encoding published in the NKS online
notes (Chapter 11, Section 4, 'Universal cellular automaton'), run from encoded
initial conditions and compared block-for-block with the target automaton.

The note is fetched live (byte size and SHA-256 recorded); the extracted rule
text is kept in derived/uca_rule.txt so the test also runs offline.
"""
import hashlib
import html
import json
import os
import random
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NOTE_URL = "https://www.wolframscience.com/nks/notes-11-4--universal-cellular-automaton/"
K = 19
SEED = 20261106


def fetch_note():
    """Return (rule_text, encoding_text, file_record) from the live note, or from derived/."""
    rule_path = os.path.join(HERE, "derived", "uca_rule.txt")
    rec = None
    page = None
    try:
        import requests
        t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        resp = requests.get(NOTE_URL, timeout=60)
        resp.raise_for_status()
        page = resp.content
        rec = {"download_url": NOTE_URL, "retrieved_at": t0, "byte_size": len(page),
               "sha256": hashlib.sha256(page).hexdigest()}
        os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
        with open(os.path.join(HERE, "data", "note.html"), "wb") as f:
            f.write(page)
    except Exception as e:  # offline fallback
        print("fetch failed:", e, file=sys.stderr)
    if page is not None:
        text = page.decode("utf-8", "ignore")
        text = text.replace("&#62754;", "->")
        m = re.search(r'<span class="c2c-copyable c2c-block">(\{\{_, 3, 7, 18, _\}.*?)</span></p>', text, re.S)
        rule_text = html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        rule_text = re.sub(r"\s+", " ", rule_text).strip()
        m2 = re.search(r'data-c2c-inline="(Flatten\[\{Transpose.*?)"', text, re.S)
        enc_text = html.unescape(m2.group(1))
        os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
        with open(rule_path, "w") as f:
            f.write(rule_text + "\n\n" + enc_text + "\n")
    else:
        with open(rule_path) as f:
            rule_text, enc_text = f.read().strip().split("\n\n")
    return rule_text, enc_text, rec


def parse_rules(rule_text):
    """Parse '{{p1,..,p5} -> out, ...}' into a list of (5 sets-or-None, var position, output fn)."""
    body = rule_text.strip()
    assert body.startswith("{{") and body.endswith("}")
    body = body[1:-1]
    parts = re.findall(r"\{([^{}]*)\}\s*->\s*([^,{}]+)", body)
    rules = []
    for pat, out in parts:
        items = [s.strip() for s in pat.split(",")]
        assert len(items) == 5, items
        sets, var = [], None
        for pos, it in enumerate(items):
            if it == "_":
                sets.append(None)
            elif re.fullmatch(r"[a-z]_", it):
                sets.append(None)
                var = pos
            elif ":" in it:
                name, alts = it.split(":")
                var = pos
                alts = alts.strip().strip("()")
                sets.append({int(a) for a in alts.split("|")})
            else:
                sets.append({int(a) for a in it.split("|")})
        out = out.strip()
        if re.fullmatch(r"\d+", out):
            c = int(out)
            fn = (lambda x, c=c: np.full_like(x, c))
        elif out == "x":
            fn = (lambda x: x)
        elif out == "x - 1":
            fn = (lambda x: x - 1)
        elif out == "x + 1":
            fn = (lambda x: x + 1)
        elif out == "8 - x":
            fn = (lambda x: 8 - x)
        else:
            raise ValueError(out)
        if out != "x" and "x" in out:
            assert var is not None
        rules.append((sets, var, fn, pat, out))
    return rules


def build_table(rules):
    """Full 19^5 lookup table; first matching rule wins (apply in reverse order, overwrite)."""
    n = K ** 5
    idx = np.arange(n, dtype=np.int64)
    cols = [(idx // K ** (4 - p)) % K for p in range(5)]  # position 0 = leftmost
    table = np.zeros(n, dtype=np.int64)
    covered = np.zeros(n, dtype=bool)
    for sets, var, fn, pat, out in reversed(rules):
        mask = np.ones(n, dtype=bool)
        for p in range(5):
            if sets[p] is not None:
                mask &= np.isin(cols[p], list(sets[p]))
        x = cols[var] if var is not None else cols[2]
        table[mask] = fn(x)[mask]
        covered |= mask
    assert covered.all()
    assert table.min() >= 0 and table.max() < K
    return table.astype(np.uint8)


def uca_step(row, table):
    code = np.zeros(row.shape, dtype=np.int64)
    for p, shift in enumerate((2, 1, 0, -1, -2)):
        code = code * K + np.roll(row, shift).astype(np.int64)
    return table[code]


def encode_block(a, r, rtab):
    m = 2 ** (2 * r + 1)
    first = [4, 18 * (1 - a), 6] + [9] * (m - 3)
    second = [10 - 3 * t for t in rtab]
    out = []
    for f, s in zip(first, second):
        out += [f, s]
    out += [9, 1] * r + [9, 13]
    return out


def encode(config, r, rtab):
    return np.array(sum((encode_block(a, r, rtab) for a in config), []), dtype=np.uint8)


def target_step(config, r, rtab):
    n = len(config)
    m = 2 ** (2 * r + 1)
    out = []
    for i in range(n):
        v = 0
        for d in range(-r, r + 1):
            v = 2 * v + config[(i + d) % n]
        out.append(rtab[m - 1 - v])
    return out


def period(r):
    return (3 * r + 2) * 2 ** (2 * r + 1) + 3 * r * r + 7 * r + 3


def run_check(table, r, rtab, config, steps):
    P = period(r)
    row = encode(config, r, rtab)
    mism = 0
    cells = 0
    for _ in range(steps):
        for _ in range(P):
            row = uca_step(row, table)
        config = target_step(config, r, rtab)
        ref = encode(config, r, rtab)
        mism += int((row != ref).sum())
        cells += ref.size
    return mism, cells


def main():
    rule_text, enc_text, rec = fetch_note()
    rules = parse_rules(rule_text)
    table = build_table(rules)
    print("parsed rules:", len(rules), "; period r=1:", period(1), "r=2:", period(2))
    rng = random.Random(SEED)
    groups = []
    # (a) all elementary rules
    g = {"group": "eca_all", "r": 1, "n_rules": 256, "N_cells": 16, "steps": 8,
         "initial_conditions": 2, "mismatches": 0, "cells": 0}
    for rule in range(256):
        rtab = [(rule >> i) & 1 for i in range(7, -1, -1)]  # all-ones neighbourhood first
        for _ in range(2):
            config = [rng.randrange(2) for _ in range(16)]
            m, c = run_check(table, 1, rtab, config, 8)
            g["mismatches"] += m
            g["cells"] += c
    groups.append(g)
    # (b) random range-2 rules
    g = {"group": "r2_random", "r": 2, "n_rules": 30, "N_cells": 10, "steps": 4,
         "initial_conditions": 1, "mismatches": 0, "cells": 0}
    for _ in range(30):
        rtab = [rng.randrange(2) for _ in range(32)]
        config = [rng.randrange(2) for _ in range(10)]
        m, c = run_check(table, 2, rtab, config, 4)
        g["mismatches"] += m
        g["cells"] += c
    groups.append(g)
    total_m = sum(g["mismatches"] for g in groups)
    total_c = sum(g["cells"] for g in groups)
    verdict = "supports" if total_m == 0 else "refutes"
    summary = {"note_file": rec, "n_rules_parsed": len(rules), "rules": [(p, o) for _, _, _, p, o in rules],
               "block_width": {"r1": len(encode_block(0, 1, [0] * 8)), "r2": len(encode_block(0, 2, [0] * 32))},
               "period": {"r1": period(1), "r2": period(2)}, "groups": groups,
               "total_mismatches": total_m, "total_cells": total_c, "verdict": verdict}
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    measured = {"value": total_m,
                "unit": "mismatching universal-automaton cells between the evolved array and the encoding of the directly computed target configuration, summed over all checkpoints",
                "n": total_c, "uncertainty": "exact (deterministic comparison)",
                "extra": {"n_rules_parsed": len(rules), "block_width": summary["block_width"],
                          "period": summary["period"], "groups": groups, "seed": SEED}}
    print(json.dumps({"note_file": rec, "measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
