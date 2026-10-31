#!/usr/bin/env python3
"""Test of wolfram2002-ch06-20: additive elementary rules, self-emulation, nesting.

Wolfram rule numbering: new cell = bit (4*l + 2*c + r) of the rule number.
Writes derived/self_emulation.json and prints the measured block.
"""
import itertools
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TRIVIAL = {0, 204, 170, 240}


def f_of(rule):
    return lambda l, c, r: (rule >> (4 * l + 2 * c + r)) & 1


def is_additive(rule):
    f = f_of(rule)
    nb = list(itertools.product((0, 1), repeat=3))
    for x in nb:
        for y in nb:
            z = tuple(a ^ b for a, b in zip(x, y))
            if f(*z) != f(*x) ^ f(*y):
                return False
    return True


def step_row(rule, row):
    """One step on a finite row with zero boundary (row is a list of 0/1)."""
    f = f_of(rule)
    n = len(row)
    return [f(row[i - 1] if i > 0 else 0, row[i], row[i + 1] if i < n - 1 else 0)
            for i in range(n)]


def self_emulations(rule, b, t):
    """All block pairs (B0, B1) with which `rule` emulates itself (b cells, t steps)."""
    f = f_of(rule)
    k = math.ceil(t / b)
    nblocks = 2 * k + 1
    found = []
    blocks = list(itertools.product((0, 1), repeat=b))
    for B0 in blocks:
        for B1 in blocks:
            if B0 == B1:
                continue
            B = (B0, B1)
            ok = True
            for bits in itertools.product((0, 1), repeat=nblocks):
                row = [x for bit in bits for x in B[bit]]
                # k blocks (>= t cells) on each side cover the centre block's light
                # cone, so the zero boundary of the window cannot affect the result.
                for _ in range(t):
                    row = step_row(rule, row)
                centre = tuple(row[k * b:(k + 1) * b])
                target = B[f(bits[k - 1], bits[k], bits[k + 1])]
                if centre != target:
                    ok = False
                    break
            if ok:
                found.append((B0, B1))
    return found


def single_cell_pattern(rule, T):
    """Pattern p[t][x] for x in -T..T from a single black cell."""
    width = 2 * T + 1
    f = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    rows = np.zeros((T, width), dtype=np.uint8)
    rows[0, T] = 1
    for s in range(1, T):
        prev = rows[s - 1]
        l = np.roll(prev, 1)
        r = np.roll(prev, -1)
        l[0] = 0
        r[-1] = 0
        rows[s] = f[4 * l + 2 * prev + r]
    return rows


def is_nested(rule, T=256):
    p = single_cell_pattern(rule, 2 * T)
    c = 2 * T  # column index of x = 0
    for t in range(T):
        for i in range(-t, t + 1):
            if p[2 * t, c + 2 * i] != p[t, c + i]:
                return False
    return True


def sublattice_60_vs_90(T=256):
    p60 = single_cell_pattern(60, T)
    p90 = single_cell_pattern(90, T)
    c = T
    for t in range(T):
        for j in range(0, t + 1):
            if p90[t, c + 2 * j - t] != p60[t, c + j]:
                return False
    return True


def reflect(rule):
    out = 0
    for l, c, r in itertools.product((0, 1), repeat=3):
        bit = (rule >> (4 * l + 2 * c + r)) & 1
        out |= bit << (4 * r + 2 * c + l)
    return out


def main():
    additive = [r for r in range(256) if is_additive(r)]
    out = {"additive_rules": additive}

    # Clause A
    A_selfemu = {r: len(self_emulations(r, 2, 2)) for r in additive}
    nontrivial_additive = [r for r in additive if r not in TRIVIAL]
    A_nested = {r: is_nested(r) for r in nontrivial_additive}
    clause_A = all(v > 0 for v in A_selfemu.values()) and all(A_nested.values())
    out["A_self_emulation_b2_t2_count"] = A_selfemu
    out["A_nested"] = A_nested

    # Clause B: classes of non-trivial additive rules under reflection and the
    # 60/90 sublattice relation (only applied if verified).
    sub_ok = sublattice_60_vs_90()
    parent = {r: r for r in nontrivial_additive}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for r in nontrivial_additive:
        if reflect(r) in parent:
            union(r, reflect(r))
    if sub_ok and 60 in parent and 90 in parent:
        union(60, 90)
    classes = {}
    for r in nontrivial_additive:
        classes.setdefault(find(r), []).append(r)
    classes = sorted(classes.values())
    clause_B = (len(classes) == 2 and any(90 in c for c in classes)
                and any(150 in c for c in classes))
    out["B_sublattice_60_90_verified"] = sub_ok
    out["B_classes"] = classes

    # Clause C: exhaustive self-emulation search for all rules.
    table = {}
    for r in range(256):
        table[r] = {}
        for b in (2, 3, 4):
            for t in (1, 2, 3, 4):
                found = self_emulations(r, b, t)
                if found:
                    table[r][f"b{b}_t{t}"] = ["".join(map(str, B0)) + "/" + "".join(map(str, B1))
                                             for B0, B1 in found]
    self_emulating = sorted(r for r in range(256) if table[r])
    non_additive_self = [r for r in self_emulating if r not in additive]
    frac = len(non_additive_self) / (256 - len(additive))
    rule184_b3 = any(k.startswith("b3_") for k in table[184])
    clause_C = rule184_b3 and frac <= 0.25
    out["C_self_emulating_rules"] = self_emulating
    out["C_rule184"] = table[184]
    out["C_fraction_non_additive_self_emulating"] = frac
    out["self_emulation_table"] = {str(r): v for r, v in table.items() if v}
    # Also the Wolfram-style matched case b = t only.
    matched = sorted(r for r in range(256)
                     if any(k in table[r] for k in ("b2_t2", "b3_t3", "b4_t4")))
    out["C_self_emulating_rules_b_equals_t"] = matched

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "self_emulation.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    if not (clause_A and clause_B):
        verdict = "refutes"
    elif clause_C:
        verdict = "supports"
    else:
        verdict = "mixed"
    measured = {
        "value": {"additive_rules": additive,
                  "non_trivial_additive_classes": classes,
                  "fraction_non_additive_self_emulating": round(frac, 4),
                  "n_self_emulating_rules_total": len(self_emulating)},
        "unit": "rule numbers; fraction of the 248 non-additive rules",
        "n": 256,
        "uncertainty": "exhaustive finite check; none within the searched b <= 4, t <= 4",
        "extra": {
            "clause_A": clause_A, "clause_B": clause_B, "clause_C": clause_C,
            "A_self_emulation_b2_t2_count": A_selfemu,
            "A_nested": {str(k): v for k, v in A_nested.items()},
            "B_sublattice_60_90_verified": sub_ok,
            "rule184_self_emulations": table[184],
            "self_emulating_rules": self_emulating,
            "self_emulating_rules_b_equals_t": matched,
            "n_self_emulating_b_equals_t": len(matched),
        },
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
