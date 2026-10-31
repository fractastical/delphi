#!/usr/bin/env python3
"""Test of wolfram2002-ch06-12: finite deterministic discrete systems must repeat,
with eventual period at most the number N of possible states.

Three families of finite deterministic systems are enumerated exhaustively (every
system, every initial state):
  (a) all 256 elementary cellular automata on cyclic rings of n = 1..12 cells (N = 2^n);
  (b) all 4096 two-state two-colour Turing machines on cyclic tapes of n = 1..5 cells
      (N = 2 * n * 2^n);
  (c) the maps x -> m x mod n for n = 2..200, m = 0..n-1 (N = n).
For each system the full transition map f on its N states is built, and for every
state the transient length and eventual period are computed from the functional graph.
The claim predicts period <= N and transient + period <= N for every orbit.

Run: python3 analysis.py            (writes derived/measured.json)
Requires numpy only.
"""
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

ECA_RING_SIZES = range(1, 13)
TM_TAPE_SIZES = range(1, 6)
MOD_MAX_N = 200


def orbit_stats(f):
    """For a map f: {0..N-1} -> {0..N-1} given as an int array, return
    (transient, period) arrays giving, for every state, the number of steps before
    the orbit enters its cycle and the length of that cycle."""
    f = np.asarray(f, dtype=np.int64)
    N = len(f)
    indeg = np.bincount(f, minlength=N)
    on_cycle = np.ones(N, dtype=bool)
    stack = list(np.nonzero(indeg == 0)[0])
    while stack:
        v = stack.pop()
        on_cycle[v] = False
        w = f[v]
        indeg[w] -= 1
        if indeg[w] == 0:
            stack.append(w)
    period = np.zeros(N, dtype=np.int64)
    seen = np.zeros(N, dtype=bool)
    for v in np.nonzero(on_cycle)[0]:
        if seen[v]:
            continue
        cyc = [v]
        seen[v] = True
        w = f[v]
        while w != v:
            cyc.append(w)
            seen[w] = True
            w = f[w]
        period[cyc] = len(cyc)
    transient = np.full(N, -1, dtype=np.int64)
    transient[on_cycle] = 0
    pending = ~on_cycle
    steps = 0
    while pending.any():
        steps += 1
        ready = pending & (transient[f] >= 0)
        transient[ready] = transient[f[ready]] + 1
        period[ready] = period[f[ready]]
        pending &= ~ready
        if steps > N:
            raise RuntimeError("transient relaxation did not converge")
    return transient, period


def eca_map(rule, n):
    """Transition map of ECA `rule` on a cyclic ring of n cells; states are the
    integers 0..2^n-1 whose bit i is the colour of cell i."""
    N = 1 << n
    states = np.arange(N, dtype=np.int64)
    bits = (states[:, None] >> np.arange(n)) & 1  # shape (N, n)
    left = np.roll(bits, 1, axis=1)
    right = np.roll(bits, -1, axis=1)
    idx = 4 * left + 2 * bits + right
    rule_bits = (rule >> np.arange(8)) & 1
    new_bits = rule_bits[idx]
    return (new_bits << np.arange(n)).sum(axis=1)


def tm_map(machine, n):
    """Transition map of a 2-state 2-colour Turing machine on a cyclic tape of n cells.
    Global state index = (head_state * n + head_pos) * 2^n + tape, tape bit i = cell i.
    Case order: (s0,c0), (s0,c1), (s1,c0), (s1,c1); each case a base-8 digit
    4*newcolour + 2*(move==+1) + newstate, least significant digit = case (s0,c0)."""
    cases = [(machine >> (3 * k)) & 7 for k in range(4)]
    T = 1 << n
    N = 2 * n * T
    idx = np.arange(N, dtype=np.int64)
    tape = idx % T
    hp = (idx // T) % n
    hs = idx // (T * n)
    colour = (tape >> hp) & 1
    case = np.array(cases, dtype=np.int64)[2 * hs + colour]
    new_colour = case >> 2
    move = np.where((case >> 1) & 1, 1, -1)
    new_state = case & 1
    new_tape = (tape & ~(1 << hp)) | (new_colour << hp)
    new_hp = (hp + move) % n
    return (new_state * n + new_hp) * T + new_tape


def mod_map(m, n):
    return (m * np.arange(n, dtype=np.int64)) % n


def check_family(name, systems):
    """systems: iterable of (label, f). Returns summary dict."""
    t0 = time.time()
    n_systems = 0
    n_orbits = 0
    violations = []
    max_ratio = 0.0
    max_ratio_sys = None
    max_tp_ratio = 0.0
    max_tp_sys = None
    max_period_abs = 0
    for label, f in systems:
        N = len(f)
        tr, per = orbit_stats(f)
        n_systems += 1
        n_orbits += N
        bad = np.nonzero((per > N) | (tr + per > N))[0]
        for s in bad[:10]:
            violations.append({"system": label, "state": int(s), "N": N,
                               "transient": int(tr[s]), "period": int(per[s])})
        pmax = int(per.max())
        if pmax / N > max_ratio:
            max_ratio, max_ratio_sys = pmax / N, {"system": label, "N": N, "max_period": pmax}
        tpmax = int((tr + per).max())
        if tpmax / N > max_tp_ratio:
            max_tp_ratio, max_tp_sys = tpmax / N, {"system": label, "N": N, "max_transient_plus_period": tpmax}
        max_period_abs = max(max_period_abs, pmax)
    return {
        "family": name,
        "systems": n_systems,
        "orbits_checked": n_orbits,
        "violations": len(violations),
        "violation_examples": violations[:10],
        "max_period_over_N": round(max_ratio, 6),
        "max_period_over_N_at": max_ratio_sys,
        "max_transient_plus_period_over_N": round(max_tp_ratio, 6),
        "max_transient_plus_period_over_N_at": max_tp_sys,
        "max_period_absolute": max_period_abs,
        "seconds": round(time.time() - t0, 1),
    }


def main():
    results = []
    results.append(check_family(
        "eca-cyclic-rings-n1-12",
        ((f"ECA rule {r}, ring n={n}", eca_map(r, n)) for n in ECA_RING_SIZES for r in range(256))))
    print(json.dumps(results[-1], indent=1))
    results.append(check_family(
        "tm-2state-2color-cyclic-tape-n1-5",
        ((f"TM machine {m}, tape n={n}", tm_map(m, n)) for n in TM_TAPE_SIZES for m in range(4096))))
    print(json.dumps(results[-1], indent=1))
    results.append(check_family(
        "modular-multiplication-maps-n2-200",
        ((f"x -> {m} x mod {n}", mod_map(m, n)) for n in range(2, MOD_MAX_N + 1) for m in range(n))))
    print(json.dumps(results[-1], indent=1))

    total_orbits = sum(r["orbits_checked"] for r in results)
    total_systems = sum(r["systems"] for r in results)
    total_viol = sum(r["violations"] for r in results)
    summary = {
        "systems_checked": total_systems,
        "orbits_checked": total_orbits,
        "violations_period_gt_N_or_transient_plus_period_gt_N": total_viol,
        "fraction_of_orbits_with_period_le_N": 1.0 - total_viol / total_orbits,
        "max_period_over_N_any_family": max(r["max_period_over_N"] for r in results),
        "families": results,
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "families"}, indent=1))


if __name__ == "__main__":
    main()
