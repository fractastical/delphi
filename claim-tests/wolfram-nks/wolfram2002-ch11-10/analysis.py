#!/usr/bin/env python3
"""Test of wolfram2002-ch11-10 (Turing-machine family): a uniform construction
turning any 1-D cellular automaton (k colours, radius r) into a Turing machine
that emulates it exactly, checked against direct evolution.

Tape: E x_0 ... x_{W-1} E, where E = k is an end marker.  One CA step is one
round trip of the head.  During the rightward sweep the state carries the last
2r *old* cell values; after reading old x_i it steps back r cells, writes the
new value of cell i-r, returns to i and moves on.  At the right marker the
remaining r cells are finished with virtual zero reads, then the head returns
to the left marker.  Cells outside [0, W) are fixed at 0 in both systems.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261110
W = 48
STEPS = 40
N_IC = 2


def ca_step(x, k, r, table):
    n = len(x)
    pad = [0] * r + list(x) + [0] * r
    out = []
    for i in range(n):
        idx = 0
        for j in range(2 * r + 1):
            idx = idx * k + pad[i + j]
        out.append(table[idx])
    return out


def build_tm(k, r, table):
    """Return (transitions, start_state).  transitions[(state, sym)] = (state', sym', move)."""
    E = k
    tr = {}
    buffers = [()]
    for _ in range(2 * r):
        buffers = [b + (c,) for b in buffers for c in range(k)]

    def f(window):
        idx = 0
        for c in window:
            idx = idx * k + c
        return table[idx]

    def add(state, sym, nstate, nsym, move):
        key = (state, sym)
        assert key not in tr, key
        tr[key] = (nstate, nsym, move)

    # ('scan', B, j): head on cell i about to read old x_i; B = last 2r old values
    # (zeros for cells left of 0); j = number of cells read so far, capped at r.
    for B in buffers:
        for j in range(r + 1):
            for s in range(k):
                nB = B[1:] + (s,)
                if j < r:
                    # cell i-r does not exist yet: just absorb the value
                    add(('scan', B, j), s, ('scan', nB, j + 1), s, +1)
                else:
                    v = f(B + (s,))
                    add(('scan', B, j), s, ('back', nB, v, r - 1), s, -1)
            # right end marker: finish the last r cells with virtual zero reads
            # e = how many virtual zeros already consumed
            add(('scan', B, j), E, ('end', B, 0, j), E, 0)
    # ('back', nB, v, m): moving left; m more moves needed before writing
    for B in buffers:
        for v in range(k):
            for m in range(r):
                for s in range(k):
                    if m == 0:
                        add(('back', B, v, m), s, ('fwd', B, r), v, +1)
                    else:
                        add(('back', B, v, m), s, ('back', B, v, m - 1), s, -1)
    # ('fwd', B, m): moving right after writing; m moves to get back onto cell i,
    # then one more onto cell i+1 which is read in 'scan' with j = r
    for B in buffers:
        for m in range(1, r + 1):
            for s in list(range(k)) + [E]:
                if m == 1:
                    add(('fwd', B, m), s, ('scan', B, r), s, +1)
                else:
                    add(('fwd', B, m), s, ('fwd', B, m - 1), s, +1)
    # ('end', B, e, j): head on right marker E; e virtual zeros consumed so far;
    # j = cells read so far (capped at r; if j < r the row is shorter than r,
    # which we exclude by requiring W >= r, but handle for completeness).
    for B in buffers:
        for j in range(r + 1):
            for e in range(r):
                if j < r:
                    add(('end', B, e, j), E, ('ret',), E, -1)
                    continue
                v = f(B + (0,))
                nB = B[1:] + (0,)
                # cell to write is at marker position - r + e
                add(('end', B, e, j), E, ('eback', nB, v, e, r - e - 1), E, -1)
    # ('eback', nB, v, e, m): moving left m more cells, then write v, then
    # return to the marker ('efwd') with e+1 virtual zeros consumed
    for B in buffers:
        for v in range(k):
            for e in range(r):
                for m in range(r - e):
                    for s in range(k):
                        if m == 0:
                            add(('eback', B, v, e, m), s, ('efwd', B, e + 1), v, +1)
                        else:
                            add(('eback', B, v, e, m), s, ('eback', B, v, e, m - 1), s, -1)
    # ('efwd', B, e): moving right until the marker
    for B in buffers:
        for e in range(1, r + 1):
            for s in range(k):
                add(('efwd', B, e), s, ('efwd', B, e), s, +1)
            if e < r:
                add(('efwd', B, e), E, ('end', B, e, r), E, 0)
            else:
                add(('efwd', B, e), E, ('ret',), E, -1)
    # ('ret',): move left to the left marker, then start a new sweep
    for s in range(k):
        add(('ret',), s, ('ret',), s, -1)
    add(('ret',), E, ('scan', (0,) * (2 * r), 0), E, +1)
    start = ('scan', (0,) * (2 * r), 0)
    return tr, start


def run_tm(tr, start, k, r, x0, steps):
    """Run the TM; yield the tape contents after each round trip."""
    E = k
    tape = [E] + list(x0) + [E]
    pos = 1
    state = start
    n_steps = 0
    visited = set()
    for _ in range(steps):
        # one round trip ends when the head leaves the left marker rightwards
        while True:
            key = (state, tape[pos])
            visited.add(key)
            nstate, nsym, move = tr[key]
            tape[pos] = nsym
            pos += move
            state = nstate
            n_steps += 1
            if key[0] == ('ret',) and key[1] == E:
                break
        yield list(tape[1:-1]), n_steps, visited


def test_rule(k, r, table, rng, steps=STEPS, n_ic=N_IC, W=W):
    tr, start = build_tm(k, r, table)
    mism = 0
    cells = 0
    tm_steps = 0
    visited = set()
    for _ in range(n_ic):
        x = [rng.randrange(k) for _ in range(W)]
        ref = list(x)
        for tape, n_steps, vis in run_tm(tr, start, k, r, x, steps):
            ref = ca_step(ref, k, r, table)
            mism += sum(1 for a, b in zip(tape, ref) if a != b)
            cells += W
            tm_steps = n_steps
            visited = vis
    return mism, cells, tm_steps * n_ic, len(tr), len({s for s, _ in tr}), len(visited)


def main():
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    rng = random.Random(SEED)
    groups = []
    # (a) all elementary rules
    g = {"group": "eca_all", "k": 2, "r": 1, "rules": [], "mismatches": 0, "cells": 0}
    for rule in range(256):
        table = [(rule >> i) & 1 for i in range(8)]  # index 4l+2c+r = Wolfram bit
        m, c, ts, ntr, nst, nvis = test_rule(2, 1, table, rng)
        g["mismatches"] += m
        g["cells"] += c
        g["rules"].append(rule)
        if rule == 110:
            rule110 = {"states": nst, "transitions": ntr, "transitions_used": nvis,
                       "tm_steps_per_ca_step": ts // (2 * STEPS)}
    groups.append(g)

    def random_group(name, k, r, n):
        g = {"group": name, "k": k, "r": r, "n_rules": n, "mismatches": 0, "cells": 0}
        for _ in range(n):
            table = [rng.randrange(k) for _ in range(k ** (2 * r + 1))]
            m, c, ts, ntr, nst, nvis = test_rule(k, r, table, rng)
            g["mismatches"] += m
            g["cells"] += c
            g["tm_states"] = nst
            g["tm_transitions"] = ntr
        return g

    groups.append(random_group("k3_r1_random", 3, 1, 100))
    groups.append(random_group("k2_r2_random", 2, 2, 50))
    groups.append(random_group("k4_r1_random", 4, 1, 20))
    groups.append(random_group("k3_r2_random", 3, 2, 10))
    total_mism = sum(g["mismatches"] for g in groups)
    total_cells = sum(g["cells"] for g in groups)
    n_rules = 256 + 100 + 50 + 20 + 10
    verdict = "supports" if total_mism == 0 else "refutes"
    summary = {"groups": [{k: v for k, v in g.items() if k != "rules"} for g in groups],
               "total_mismatches": total_mism, "total_cells_compared": total_cells,
               "n_rules": n_rules, "rule110_tm": rule110, "verdict": verdict}
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    measured = {
        "value": total_mism,
        "unit": "mismatching cells between Turing-machine tape and direct cellular-automaton evolution, summed over all runs",
        "n": total_cells,
        "uncertainty": "exact (deterministic comparison)",
        "extra": {"n_rules": n_rules, "W": W, "steps": STEPS, "initial_conditions_per_rule": N_IC,
                  "seed": SEED, "groups": summary["groups"], "rule110_tm": rule110},
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
