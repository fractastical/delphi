#!/usr/bin/env python3
"""wolfram2002-ch11-28: all 4096 two-state two-colour Turing machines are too simple for universality.

Compiles tm22.c (gcc) and classifies every machine from 3076 exhaustive short initial conditions
(all tapes of length 1..7, every head position, both states) and 100 random tapes of length 16-32
(numpy seed = machine number) into
  A eventually periodic (exact), B escaping (exact; two tests),
  C regular linear growth, D nested counter growth, E counter certificate (post-hoc heuristics),
  U unclassified within 10000 steps.
Also compares early-stopping with full 10000-step runs on two blocks of 64 machines, and counts
symmetry-distinct machines.  Prints JSON to stdout and writes derived/per_machine.tsv.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NRAND = 100
N_EXHAUSTIVE = sum(2 ** n * n * 2 for n in range(1, 8))  # 3076
COLS = ["machine", "nA", "nB", "nC", "nD", "nE", "nU", "max_period", "max_transient", "max_span"]


def entries(m):
    out = []
    for i in range(4):
        e = (m >> (3 * (3 - i))) & 7
        out.append((e & 1, 1 if (e >> 1) & 1 else -1, e >> 2))  # (colour, move, state) for case i = 2*s + c
    return out


def number(ents):
    m = 0
    for i, (c, mv, s) in enumerate(ents):
        e = c | ((1 if mv == 1 else 0) << 1) | (s << 2)
        m |= e << (3 * (3 - i))
    return m


def orbit(m):
    """Images of machine m under state relabelling, colour swap and left-right reflection."""
    ents = entries(m)
    out = set()
    for swap_state in (0, 1):
        for swap_col in (0, 1):
            for refl in (0, 1):
                new = [None] * 4
                for s in range(2):
                    for c in range(2):
                        col, mv, ns = ents[2 * s + c]
                        s2, c2 = s ^ swap_state, c ^ swap_col
                        new[2 * s2 + c2] = (col ^ swap_col, -mv if refl else mv, ns ^ swap_state)
                out.add(number(new))
    return out


def symmetry_classes():
    rep = {}
    for m in range(4096):
        if m in rep:
            continue
        for x in orbit(m):
            rep[x] = m
    return rep


def parse(text):
    return [list(map(int, line.split())) for line in text.strip().splitlines()]


def main():
    rng_file = "/tmp/tm22_random.txt"
    with open(rng_file, "w") as f:
        for m in range(4096):
            rng = np.random.default_rng(m)
            for _ in range(NRAND):
                n = int(rng.integers(16, 33))
                f.write("".join(map(str, rng.integers(0, 2, n).tolist())) + "\n")
    exe = "/tmp/tm22_bin"
    subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(HERE, "tm22.c")], check=True)
    t0 = time.time()
    rows = parse(subprocess.run([exe, rng_file], capture_output=True, text=True, check=True).stdout)
    t_main = time.time() - t0
    arr = np.array(rows)
    assert arr.shape == (4096, 10)
    per_ic = N_EXHAUSTIVE + NRAND
    assert (arr[:, 1:7].sum(axis=1) == per_ic).all()
    tot = {k: int(arr[:, i].sum()) for i, k in enumerate(COLS[1:7], start=1)}
    runs = 4096 * per_ic
    rep = symmetry_classes()
    n_classes = len(set(rep.values()))

    def machines_with(col):
        i = COLS.index(col)
        return [int(r[0]) for r in rows if r[i] > 0]

    non_ab = sorted(set(machines_with("nC") + machines_with("nD") + machines_with("nE") + machines_with("nU")))
    classes_non_ab = sorted({rep[m] for m in non_ab})
    classes_DEU = sorted({rep[m] for m in set(machines_with("nD") + machines_with("nE") + machines_with("nU"))})

    # validation: early stopping vs full 10000-step runs on two blocks of 64 machines
    t1 = time.time()
    validation = []
    for m0 in (256, 2048):
        full = parse(subprocess.run([exe, rng_file, str(m0), str(m0 + 64), "full"], capture_output=True, text=True, check=True).stdout)
        early = [r for r in rows if m0 <= r[0] < m0 + 64]
        diffs = [(e[0], e[1:7], f[1:7]) for e, f in zip(early, full) if e[1:7] != f[1:7]]
        validation.append({"machines": f"{m0}-{m0 + 63}", "runs_per_machine": per_ic,
                           "class_counts_identical_for_all_64_machines": not diffs, "differences": diffs[:5]})
    t_val = time.time() - t1

    maxT_row = rows[int(np.argmax(arr[:, 8]))]
    out = {
        "n_machines": 4096,
        "initial_conditions_per_machine": per_ic,
        "initial_conditions_note": "3076 exhaustive: all tapes of length 1..7 x head position x 2 states; plus 100 random tapes of length 16..32 (numpy default_rng(machine), head at cell 0, state 0)",
        "runs": runs,
        "step_limit": 10000,
        "counts": {"A_periodic_exact": tot["nA"], "B_escaping_exact": tot["nB"], "C_linear_growth": tot["nC"],
                   "D_nested_counter_growth": tot["nD"], "E_counter_certificate": tot["nE"], "U_unclassified": tot["nU"]},
        "fraction_A_or_B": (tot["nA"] + tot["nB"]) / runs,
        "fraction_A_to_E": (runs - tot["nU"]) / runs,
        "max_period_modulo_translation": int(arr[:, 7].max()),
        "max_transient_before_A_or_B": int(arr[:, 8].max()),
        "machine_with_max_transient": {"machine": int(maxT_row[0]), "entries_(colour,move,state)_for_cases_(s0c0,s0c1,s1c0,s1c1)": entries(int(maxT_row[0]))},
        "max_nonzero_span_reached_before_classification": int(arr[:, 9].max()),
        "machines_by_max_period": {str(p): int(np.sum(arr[:, 7] == p)) for p in sorted(set(arr[:, 7].tolist()))},
        "machines_with_any_non_AB_run": len(non_ab),
        "machines_with_C_runs": len(machines_with("nC")),
        "machines_with_D_runs": len(machines_with("nD")),
        "machines_with_E_runs": len(machines_with("nE")),
        "machines_with_U_runs": machines_with("nU"),
        "unclassified_runs_detail": [{"machine": int(r[0]), "nU": int(r[6]), "nD": int(r[4]), "nE": int(r[5])} for r in rows if r[6] > 0],
        "symmetry_distinct_machines": n_classes,
        "symmetry_classes_with_non_AB_runs": len(classes_non_ab),
        "symmetry_classes_with_D_E_or_U_runs": len(classes_DEU),
        "representatives_of_classes_with_D_E_or_U_runs": {str(c): entries(c) for c in classes_DEU},
        "validation_early_stop_vs_full_run": validation,
        "seconds_main": round(t_main, 1), "seconds_validation": round(t_val, 1),
    }
    out["preregistered_criterion"] = "100% of runs A or B within 10000 steps and max period <= 1000"
    out["preregistered_verdict"] = "supports" if tot["nA"] + tot["nB"] == runs and out["max_period_modulo_translation"] <= 1000 else "mixed"
    out["posthoc_criterion"] = "every run A-E (periodic, escaping, regular linear growth, nested counter growth or counter certificate), no run of any machine shows anything else"
    out["posthoc_verdict"] = "supports" if tot["nU"] == 0 else ("supports_with_residual" if tot["nU"] <= 10 else "mixed")
    json.dump(out, sys.stdout, indent=1)
    print()
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "per_machine.tsv"), "w") as f:
        f.write("\t".join(COLS) + "\tsymmetry_class_representative\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + f"\t{rep[r[0]]}\n")
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
