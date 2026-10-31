#!/usr/bin/env python3
"""Test of wolfram2002-ch12-17: for rules 60 and 188 the colour of a cell after t steps
can be found in about log2(t) steps from the base-2 digits of its position.

Operationalisation: the pattern A(t, x) is 2-automatic, i.e. a finite automaton reading
the binary digits of (t, x) outputs A(t, x). This is tested by
  (i)  2-kernel saturation: the number of distinct kernel elements
       A(2^k t + r, 2^k x + s) (compared on a 32 x 32 window) stops growing with k;
  (ii) constructing the automaton from the 2^11 x 2^11 pattern (states = distinct
       kernel elements on a 64 x 64 window, levels k <= 5; transition on digits (dt, dx)
       from (k, r, s) to (k+1, r + 2^k dt, s + 2^k dx)), checking it is consistent, and
       running it on all cells of the 2^12 x 2^12 pattern (12 digit pairs, least
       significant first), comparing with direct evolution;
  (iii) checking that stopping after bitlen(t) digit pairs gives the same output.
Controls: rules 30, 110 (mirrored), 90, 150 (right halves).

Run: python3 analysis.py   (needs numpy)
"""
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
K_TEST = 12
K_BUILD = 11
M_BUILD = 64   # window for automaton states
M_SAT = 32     # window for the saturation count
S = 1 << K_TEST


def evolve_right_growing(rule, size, mirror=False):
    """Pattern of a rule from a single black cell that grows only to the right.
    Returns A[t][x] for t, x in 0..size-1 (x = 0 is the seed cell)."""
    bits = np.array([(rule >> k) & 1 for k in range(8)], dtype=np.uint8)
    width = size + 2
    row = np.zeros(width, dtype=np.uint8)
    row[1] = 1  # index 0 is x = -1
    A = np.zeros((size, size), dtype=np.uint8)
    A[0] = row[1:size + 1]
    for t in range(1, size):
        l = np.concatenate(([0], row[:-1]))
        r = np.concatenate((row[1:], [0]))
        if mirror:
            row = bits[4 * r + 2 * row + l]
        else:
            row = bits[4 * l + 2 * row + r]
        assert row[0] == 0, "pattern spread to the left"
        A[t] = row[1:size + 1]
    return A


def evolve_two_sided_right_half(rule, size):
    bits = np.array([(rule >> k) & 1 for k in range(8)], dtype=np.uint8)
    width = 2 * size + 1
    row = np.zeros(width, dtype=np.uint8)
    row[size] = 1
    A = np.zeros((size, size), dtype=np.uint8)
    A[0] = row[size:2 * size]
    for t in range(1, size):
        l = np.concatenate(([0], row[:-1]))
        r = np.concatenate((row[1:], [0]))
        row = bits[4 * l + 2 * row + r]
        A[t] = row[size:2 * size]
    return A


def kernel_counts(A, M):
    """Cumulative number of distinct kernel elements (M x M window) by level."""
    K = int(np.log2(A.shape[0]))
    seen = set()
    cum = []
    per_level_new = []
    for k in range(0, K - int(np.log2(M)) + 1):
        step = 1 << k
        new = 0
        for r in range(step):
            for s in range(step):
                key = A[r::step, s::step][:M, :M].tobytes()
                if key not in seen:
                    seen.add(key)
                    new += 1
        per_level_new.append(new)
        cum.append(len(seen))
    return cum, per_level_new


def build_automaton(A, M):
    """States: distinct M x M kernel windows of pattern A (levels k with 2^k M <= size).
    Returns (table[state, dt, dx], output[state], info)."""
    K = int(np.log2(A.shape[0]))
    kmax = K - int(np.log2(M))
    ids = {}
    elems = {}  # (k, r, s) -> state id
    for k in range(0, kmax + 1):
        step = 1 << k
        for r in range(step):
            for s in range(step):
                key = A[r::step, s::step][:M, :M].tobytes()
                if key not in ids:
                    ids[key] = len(ids)
                elems[(k, r, s)] = ids[key]
    n = len(ids)
    table = -np.ones((n, 2, 2), dtype=np.int64)
    conflicts = 0
    for (k, r, s), st in elems.items():
        if k + 1 > kmax:
            continue
        for dt in (0, 1):
            for dx in (0, 1):
                tgt = elems[(k + 1, r + (dt << k), s + (dx << k))]
                if table[st, dt, dx] == -1:
                    table[st, dt, dx] = tgt
                elif table[st, dt, dx] != tgt:
                    conflicts += 1
    undefined = int((table == -1).sum())
    output = np.zeros(n, dtype=np.uint8)
    for key, st in ids.items():
        output[st] = np.frombuffer(key, dtype=np.uint8)[0]  # window entry (0, 0)
    first_level = {}
    for (k, r, s), st in sorted(elems.items()):
        first_level.setdefault(st, k)
    return table, output, {"states": n, "transition_conflicts": conflicts,
                           "undefined_transitions": undefined,
                           "states_first_seen_at_level": sorted(first_level.values())}


def run_automaton(table, output, size, stop_at_bitlen=False):
    t = np.repeat(np.arange(size, dtype=np.int64), size)
    x = np.tile(np.arange(size, dtype=np.int64), size)
    state = np.zeros(size * size, dtype=np.int64)
    nbits = int(np.log2(size))
    bitlen = np.zeros_like(t)
    tt = t.copy()
    while tt.any():
        bitlen += (tt > 0)
        tt >>= 1
    for j in range(nbits):
        dt = (t >> j) & 1
        dx = (x >> j) & 1
        new = table[state, dt, dx]
        if stop_at_bitlen:
            active = j < bitlen
            state = np.where(active, new, state)
        else:
            state = new
        if (state < 0).any():
            return None, int((state < 0).sum())
    return output[state].reshape(size, size), 0


def analyse(name, A):
    t0 = time.time()
    res = {"rule": name}
    cum, new = kernel_counts(A, M_SAT)
    res["kernel_cumulative_distinct_by_level_window32"] = cum
    res["kernel_new_elements_by_level_window32"] = new
    res["kernel_saturated_(count_k_le_5_equals_count_k_le_7)"] = bool(cum[5] == cum[7])
    Ab = A[:1 << K_BUILD, :1 << K_BUILD]
    table, output, info = build_automaton(Ab, M_BUILD)
    res["automaton"] = info
    if info["transition_conflicts"] == 0 and info["undefined_transitions"] == 0:
        pred, neg = run_automaton(table, output, S)
        mism = int((pred != A).sum())
        res["cells_tested"] = int(A.size)
        res["cells_outside_build_range"] = int(A.size - Ab.size)
        res["mismatching_cells_full_digits"] = mism
        res["mismatching_cells_outside_build_range"] = int((pred[1 << K_BUILD:] != A[1 << K_BUILD:]).sum()
                                                             + (pred[:1 << K_BUILD, 1 << K_BUILD:] != A[:1 << K_BUILD, 1 << K_BUILD:]).sum())
        pred2, _ = run_automaton(table, output, S, stop_at_bitlen=True)
        inside = np.tril(np.ones((S, S), dtype=bool))  # cells with x <= t (the pattern proper)
        res["cells_with_x_le_t"] = int(inside.sum())
        res["mismatching_cells_x_le_t_stop_after_bitlen_t_digits"] = int(((pred2 != A) & inside).sum())
        res["automaton_steps_for_t_4095"] = 12
        res["direct_evolution_steps_for_t_4095"] = 4095
    else:
        res["cells_tested"] = int(A.size)
        res["mismatching_cells_full_digits"] = None
    res["seconds"] = round(time.time() - t0, 1)
    return res


def main():
    out = {"K_test": K_TEST, "K_build": K_BUILD, "window_build": M_BUILD, "window_saturation": M_SAT, "rules": {}}
    patterns = {
        "60": evolve_right_growing(60, S),
        "188": evolve_right_growing(188, S),
        "30_right_half": evolve_two_sided_right_half(30, S),
        "110_mirrored": evolve_right_growing(110, S, mirror=True),
        "90_right_half": evolve_two_sided_right_half(90, S),
        "150_right_half": evolve_two_sided_right_half(150, S),
    }
    for name, A in patterns.items():
        r = analyse(name, A)
        out["rules"][name] = r
        print(json.dumps(r))
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
