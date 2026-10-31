#!/usr/bin/env python3
"""Test of wolfram2002-ch11-25: single-step block emulation among elementary CA.

Scheme (reconstructed from NKS pp. 703-705): periodic initial condition with
period w+1 = one input cell followed by a fixed background block B of width w.
Run rule f for t steps (w+1 <= t <= 2w+2); read the output at offset d (0..w) to
the right of the input position of cell i.  If the output depends only on
(x[i-1], x[i], x[i+1]) the induced truth table is an elementary rule g emulated
by f for one step at width w.

Writes derived/emulation_counts.json and prints the measured block.
"""
import itertools
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WMAX = 6
NIN = 5  # inputs x[i-2..i+2] present in the window


def step_all(rows, table):
    l = np.roll(rows, 1, axis=1)
    r = np.roll(rows, -1, axis=1)
    return table[4 * l + 2 * rows + r]


def emulated_rules(f, w):
    """Set of rule numbers g emulated by f for one step with background width w."""
    table = np.array([(f >> i) & 1 for i in range(8)], dtype=np.uint8)
    period = w + 1
    inputs = np.array(list(itertools.product((0, 1), repeat=NIN)), dtype=np.uint8)  # 32 x 5
    # weights for the inner triple (x[i-1], x[i], x[i+1]) -> index 4l+2c+r
    inner_idx = 4 * inputs[:, 1] + 2 * inputs[:, 2] + inputs[:, 3]
    outer_idx = 2 * inputs[:, 0] + inputs[:, 4]
    found = set()
    tmax = 2 * w + 2
    pad_periods = (tmax + 2) // period + 2
    total_periods = NIN + 2 * pad_periods
    width = total_periods * period
    centre_period = pad_periods + NIN // 2  # period index holding x[i]
    for Bbits in itertools.product((0, 1), repeat=w):
        B = np.array(Bbits, dtype=np.uint8)
        base = np.zeros(width, dtype=np.uint8)
        for p in range(total_periods):
            base[p * period + 1:(p + 1) * period] = B
        rows = np.tile(base, (32, 1))
        for k in range(NIN):
            rows[:, (pad_periods + k) * period] = inputs[:, k]
        # Rows beyond the light cone of the window edges: the window is periodic
        # with the right structure (np.roll wraps), so no edge effects as long as the
        # wrapped neighbours are background, which they are by construction, and the
        # padding exceeds tmax.
        cur = rows
        for t in range(1, tmax + 1):
            cur = step_all(cur, table)
            if t < period:
                continue
            for d in range(0, w + 1):
                out = cur[:, centre_period * period + d]
                # dependence only on inner triple?
                ok = True
                g = 0
                for idx in range(8):
                    vals = out[inner_idx == idx]
                    if vals.min() != vals.max():
                        ok = False
                        break
                    g |= int(vals[0]) << idx
                if ok:
                    found.add(g)
    return found


def main():
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    counts = {}
    sets = {}
    for f in range(256):
        cum = set()
        per_width = []
        for w in range(1, WMAX + 1):
            cum |= emulated_rules(f, w)
            per_width.append(len(cum))
        counts[f] = per_width
        sets[f] = sorted(cum)
    with open(os.path.join(HERE, "derived", "emulation_counts.json"), "w") as fh:
        json.dump({"cumulative_count_by_width_1_to_6": {str(k): v for k, v in counts.items()},
                   "emulated_rules_at_width_6": {str(k): v for k, v in sets.items()}}, fh)

    complex_rules = {22, 30, 110}
    simple_rules = {90, 184}
    E = {f: counts[f][-1] for f in range(256)}
    sup = all(E[f] == 256 for f in complex_rules) and all(E[f] <= 32 for f in simple_rules)
    ref = any(E[f] >= 128 for f in simple_rules) or min(E[f] for f in complex_rules) < max(E[f] for f in simple_rules)
    if sup:
        verdict = "supports"
    elif ref:
        verdict = "refutes"
    else:
        verdict = "inconclusive"
    allE = np.array([E[f] for f in range(256)])

    # POST-HOC extension (not pre-registered, not decisive): the counts at W = 6
    # were still rising, so the same search is continued to width 12 for the
    # focal rules to see whether the complex rules reach 256 under this scheme.
    ext = {}
    for f in sorted(complex_rules | simple_rules | {45}):
        cum = set(sets[f])
        per_width = list(counts[f])
        for w in range(WMAX + 1, 13):
            cum |= emulated_rules(f, w)
            per_width.append(len(cum))
        ext[str(f)] = per_width
    with open(os.path.join(HERE, "derived", "post_hoc_width12.json"), "w") as fh:
        json.dump(ext, fh)

    measured = {
        "value": {str(f): E[f] for f in sorted(complex_rules | simple_rules | {41, 45, 54})},
        "unit": "number of the 256 elementary rules emulated for one step with background width <= 6",
        "n": {"underlying_rules": 256, "widths": WMAX},
        "uncertainty": "exhaustive within the scheme and searched range; none",
        "extra": {
            "cumulative_by_width": {str(f): counts[f] for f in sorted(complex_rules | simple_rules | {41, 45, 54})},
            "all_256_underlying_rules_count_distribution": {
                "min": int(allE.min()), "median": float(np.median(allE)), "max": int(allE.max()),
                "n_reaching_256": int(np.count_nonzero(allE == 256)),
                "rules_reaching_256": [int(f) for f in np.nonzero(allE == 256)[0]],
                "n_at_most_32": int(np.count_nonzero(allE <= 32)),
            },
            "post_hoc_cumulative_by_width_1_to_12": ext,
        },
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
