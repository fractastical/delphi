#!/usr/bin/env python3
"""Test of wolfram2002-ch11-09: subword complexity of all small neighbour-independent
substitution systems versus rule 30, plus the neighbour-dependent emulation of rules 90/30.

Everything is generated here; no download. Writes derived/measurements.json.
"""
import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
L = 131072
NMAX = 14
NESTED_BOUND = (NMAX + 1) ** 2  # 225
COMPLEX_BOUND = 2000
ROW_STEP = 20000
COLUMN_STEPS = 65536
ND_STEPS = 1000


# ------------------------------------------------------------ complexity p(n)
def factor_counts(word, nmax=NMAX, base=4):
    """Number of distinct factors of length n = 1..nmax of a uint8 word (symbols < base).
    Exact: windows ending in the first nmax-1 positions are added separately."""
    w = np.asarray(word, dtype=np.int64)
    n_pos = len(w) - nmax + 1
    if n_pos <= 0:
        return [len(set(bytes(w[i:i + n].astype(np.uint8)) for i in range(len(w) - n + 1))) for n in range(1, nmax + 1)]
    bits = 2  # base 4 -> 2 bits per symbol
    code = np.zeros(n_pos, dtype=np.int64)
    for k in range(nmax):
        code = (code << bits) | w[k:k + n_pos]
    code.sort()
    out = []
    for n in range(1, nmax + 1):
        shifted = code >> (bits * (nmax - n))  # last n symbols of each window, still sorted
        distinct = int(np.count_nonzero(np.diff(shifted))) + 1
        # factors of length n starting before position nmax-n are not suffixes of any window
        extra = set()
        for s in range(0, nmax - n):
            c = 0
            for k in range(n):
                c = (c << bits) | int(w[s + k])
            i = np.searchsorted(shifted, c)
            if i >= len(shifted) or shifted[i] != c:
                extra.add(c)
        out.append(distinct + len(extra))
    return out


# ----------------------------------------------------- substitution systems
def blocks(colors, maxlen):
    return [b for n in range(1, maxlen + 1) for b in itertools.product(range(colors), repeat=n)]


def run_substitution(rule, colors, start=1, length=L, max_steps=60):
    """rule: tuple of blocks, rule[c] is the replacement of colour c. Returns the first row
    of length >= `length` truncated, or the row at max_steps if it never grows that far."""
    tables = [np.array(b, dtype=np.uint8) for b in rule]
    row = np.array([start], dtype=np.uint8)
    for step in range(1, max_steps + 1):
        row = np.concatenate([tables[c] for c in row]) if len(row) < 4096 else _fast_sub(row, tables)
        if len(row) >= length:
            return row[:length], step, True
    return row, max_steps, False


def _fast_sub(row, tables):
    lens = np.array([len(t) for t in tables])
    out_len = int(lens[row].sum())
    out = np.empty(out_len, dtype=np.uint8)
    pos = np.concatenate([[0], np.cumsum(lens[row])[:-1]])
    for c, t in enumerate(tables):
        idx = np.flatnonzero(row == c)
        for k, v in enumerate(t):
            out[pos[idx] + k] = v
    return out


# -------------------------------------------------------------- rule 30 etc.
def eca_step_int(x, rule):
    """One step of an elementary CA on a Python-int bitset (bit i = cell i), white boundary."""
    left, right = x << 1, x >> 1
    new = 0
    for pat in range(8):
        if (rule >> pat) & 1:
            l, c, r = (pat >> 2) & 1, (pat >> 1) & 1, pat & 1
            term = ~0
            term &= left if l else ~left
            term &= x if c else ~x
            term &= right if r else ~right
            new |= term
    return new


def rule30_step(x):
    return (x << 1) ^ (x | (x >> 1))


def int_to_bits(x, lo, hi):
    """Bits lo..hi-1 of x as a uint8 array (bit lo first)."""
    s = bin(x)[2:][::-1]
    s = s + "0" * max(0, hi - len(s))
    return np.frombuffer(s[lo:hi].encode(), dtype=np.uint8) - ord("0")


def rule30_row_and_column(row_step, col_steps):
    origin = max(row_step, col_steps) + 2
    x = 1 << origin
    col = np.zeros(col_steps, dtype=np.uint8)
    row = None
    for t in range(1, max(row_step, col_steps) + 1):
        if t <= col_steps:
            col[t - 1] = (x >> origin) & 1
        x = rule30_step(x) & ~(-1 << (2 * origin + 1))
        if t == row_step:
            row = int_to_bits(x, origin - row_step, origin + row_step + 1)
    return row, col


def neighbour_dependent_emulation(rule, steps):
    """Neighbour-dependent substitution system: each cell is replaced by exactly one cell,
    table(left, self, right). Compared with the direct CA evolution. Returns True if all rows agree."""
    width = 2 * steps + 3
    row = np.zeros(width, dtype=np.uint8)
    row[width // 2] = 1
    x = 1 << (width // 2)
    table = np.array([(rule >> p) & 1 for p in range(8)], dtype=np.uint8)
    for t in range(steps):
        l = np.concatenate([[0], row[:-1]])
        r = np.concatenate([row[1:], [0]])
        row = table[(l << 2) | (row << 1) | r]  # the substitution: one new cell per cell
        x = eca_step_int(x, rule) & ((1 << width) - 1)
        if not np.array_equal(row, int_to_bits(x, 0, width)):
            return False, t + 1
    return True, steps


def main():
    results = {"families": {}}
    all_rules = []
    for colors, maxlen in ((2, 3), (3, 2)):
        bl = blocks(colors, maxlen)
        fam = []
        for rule in itertools.product(bl, repeat=colors):
            word, step, grew = run_substitution(rule, colors)
            p = factor_counts(word)
            rec = {"rule": ["".join(map(str, b)) for b in rule], "len": int(len(word)), "steps": step, "reached_L": grew, "p": p}
            rec["class"] = "repetitive" if p[NMAX - 1] == p[NMAX - 2] else ("nested" if p[NMAX - 1] <= NESTED_BOUND else ("complex" if p[NMAX - 1] >= COMPLEX_BOUND else "intermediate"))
            fam.append(rec)
        all_rules.extend(fam)
        counts = {k: sum(r["class"] == k for r in fam) for k in ("repetitive", "nested", "intermediate", "complex")}
        top = sorted(fam, key=lambda r: -r["p"][NMAX - 1])[:5]
        results["families"][f"{colors}colours_blocks1to{maxlen}"] = {
            "n_rules": len(fam), "classes": counts, "max_p14": max(r["p"][NMAX - 1] for r in fam),
            "n_reached_L": sum(r["reached_L"] for r in fam),
            "top5_by_p14": [{"rule": r["rule"], "p": r["p"], "len": r["len"]} for r in top],
        }
        print(colors, maxlen, counts, "max p14", results["families"][f"{colors}colours_blocks1to{maxlen}"]["max_p14"], flush=True)

    row, col = rule30_row_and_column(ROW_STEP, COLUMN_STEPS)
    p_row, p_col = factor_counts(row), factor_counts(col)
    results["rule30"] = {"row_step": ROW_STEP, "row_len": int(len(row)), "p_row": p_row, "column_len": int(len(col)), "p_column": p_col,
                         "column_first_64_bits": "".join(map(str, col[:64].tolist()))}
    print("rule30 row p:", p_row, "\ncolumn p:", p_col, flush=True)

    # does any substitution word contain a large share of rule 30's length-14 factors?
    def codes14(w):
        w = np.asarray(w, dtype=np.int64)
        c = np.zeros(len(w) - NMAX + 1, dtype=np.int64)
        for k in range(NMAX):
            c = (c << 2) | w[k:k + len(c)]
        return np.unique(c)
    r30 = codes14(col)
    max_share, max_rule = 0.0, None
    for colors, maxlen in ((2, 3), (3, 2)):
        for rule in itertools.product(blocks(colors, maxlen), repeat=colors):
            word, _, _ = run_substitution(rule, colors)
            if len(word) < NMAX or word.max() > 1:
                continue
            share = float(np.isin(r30, codes14(word)).mean())
            if share > max_share:
                max_share, max_rule = share, ["".join(map(str, b)) for b in rule]
    results["max_share_of_rule30_column_14factors_in_any_binary_substitution_word"] = {"share": max_share, "rule": max_rule}

    nd = {}
    for rule in (90, 30):
        ok, t = neighbour_dependent_emulation(rule, ND_STEPS)
        nd[f"rule{rule}"] = {"exact_match_all_steps": ok, "steps_checked": t}
    results["neighbour_dependent"] = nd

    n_complex = sum(r["class"] == "complex" for r in all_rules)
    n_inter = sum(r["class"] == "intermediate" for r in all_rules)
    crit = {
        "a_all_independent_rules_within_nested_bound": n_complex == 0 and n_inter == 0,
        "b_rule30_sequences_complex": p_row[NMAX - 1] >= COMPLEX_BOUND and p_col[NMAX - 1] >= COMPLEX_BOUND,
        "c_neighbour_dependent_reproduces_90_and_30": all(v["exact_match_all_steps"] for v in nd.values()),
        "n_independent_rules": len(all_rules), "n_complex": n_complex, "n_intermediate": n_inter,
    }
    if n_complex > 0 or not crit["c_neighbour_dependent_reproduces_90_and_30"]:
        verdict = "refutes"
    elif crit["a_all_independent_rules_within_nested_bound"] and crit["b_rule30_sequences_complex"]:
        verdict = "supports"
    else:
        verdict = "mixed"
    results["criteria"] = crit
    results["verdict"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(results, f, indent=1)
    with open(os.path.join(HERE, "derived", "all_rules_p14.json"), "w") as f:
        json.dump([{"rule": r["rule"], "p13": r["p"][NMAX - 2], "p14": r["p"][NMAX - 1], "class": r["class"], "len": r["len"]} for r in all_rules], f)
    print(json.dumps({k: v for k, v in results.items() if k != "families"}, indent=1))
    print(json.dumps(results["families"], indent=1))


if __name__ == "__main__":
    sys.exit(main())
