#!/usr/bin/env python3
"""wolfram2002-ch11-08: cellular automata cannot emulate substitution systems step for step.

  A  light-cone bound: pattern width grows by at most 2r per step (all quiescent ECAs; random radius-2 rules)
  B  substitution systems: exact lengths versus growth-matrix prediction; Perron roots
  C  minimal CA steps needed per substitution step under a >= 1 cell per element encoding
  D  Turing machines are emulated one step per step by a radius-1 CA with k(s+1) colours
Deterministic; prints JSON to stdout.
"""
import itertools
import json
import sys
from math import ceil

import numpy as np

ECA_STEPS, ECA_SEEDS, SEED_LEN = 300, 10, 20
R2_RULES, R2_STEPS, R2_SEEDS = 50, 200, 5
SUB_STEPS = 12
TM_N, TM_STEPS, TM_TAPE = 20, 200, 40


# ---------------------------------------------------------------- A
def width(x):
    nz = np.flatnonzero(x)
    return 0 if nz.size == 0 else int(nz[-1] - nz[0] + 1)


def run_width_growth(table, r, steps, seeds):
    k = 2 * r + 1
    worst = 0
    violations = 0
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        W = SEED_LEN + 2 * 2 * r * steps + 4
        x = np.zeros(W, np.uint8)
        lo = W // 2 - SEED_LEN // 2
        x[lo:lo + SEED_LEN] = rng.integers(0, 2, SEED_LEN)
        w_prev = width(x)
        for _ in range(steps):
            idx = np.zeros(W - 2 * r, np.int64)
            for j in range(k):
                idx = (idx << 1) | x[j:W - 2 * r + j].astype(np.int64)
            y = np.zeros(W, np.uint8)
            y[r:W - r] = table[idx]
            x = y
            w = width(x)
            if w_prev > 0:
                worst = max(worst, w - w_prev)
                if w - w_prev > 2 * r:
                    violations += 1
            w_prev = w
    return worst, violations


def part_a():
    eca = {}
    worst_all = 0
    viol_all = 0
    for rule in range(0, 256, 2):  # bit 0 (neighbourhood 000) is 0
        table = np.array([(rule >> i) & 1 for i in range(8)], np.uint8)
        worst, viol = run_width_growth(table, 1, ECA_STEPS, ECA_SEEDS)
        worst_all = max(worst_all, worst)
        viol_all += viol
        eca[rule] = worst
    r2_worst = 0
    r2_viol = 0
    for s in range(R2_RULES):
        rng = np.random.default_rng(s)
        table = rng.integers(0, 2, 32).astype(np.uint8)
        table[0] = 0
        worst, viol = run_width_growth(table, 2, R2_STEPS, R2_SEEDS)
        r2_worst = max(r2_worst, worst)
        r2_viol += viol
    return {"eca_rules_tested": len(eca), "eca_max_width_increase_per_step": worst_all, "eca_violations_of_2r": viol_all,
            "eca_rules_reaching_increase_2": sorted(r for r, w in eca.items() if w == 2),
            "radius2_rules_tested": R2_RULES, "radius2_max_width_increase_per_step": r2_worst, "radius2_violations_of_2r": r2_viol,
            "bound_holds": viol_all == 0 and r2_viol == 0}


# ---------------------------------------------------------------- B, C
def blocks():
    out = [""]
    for n in (1, 2, 3):
        out += ["".join(p) for p in itertools.product("01", repeat=n)]
    return out


def substitute(s, rule):
    return "".join(rule[ch] for ch in s)


def perron(rule):
    M = np.array([[rule["0"].count("0"), rule["0"].count("1")],
                  [rule["1"].count("0"), rule["1"].count("1")]], float)  # row = colour, col = produced colour
    ev = np.linalg.eigvals(M)
    return M, float(max(abs(ev)))


def part_bc():
    systems = []
    n_exp = n_exact = 0
    c_ok = 0
    c_fail = []
    for b0 in blocks():
        for b1 in blocks():
            rule = {"0": b0, "1": b1}
            M, lam = perron(rule)
            s = "1"
            lengths = [1]
            counts = np.array([0.0, 1.0])
            exact = True
            for t in range(SUB_STEPS):
                s = substitute(s, rule)
                counts = counts @ M
                lengths.append(len(s))
                exact &= (len(s) == int(round(counts.sum())))
                if len(s) > 2_000_000:
                    break
            n_exact += int(exact)
            rec = {"rule": rule, "lambda": round(lam, 4), "lengths": lengths, "exact_match_matrix": exact}
            if lam > 1 + 1e-9:
                n_exp += 1
                L = lengths
                total_ca_steps = ceil((L[SUB_STEPS] - L[0]) / 2)
                c4 = ceil((L[4] - L[3]) / 2)
                c12 = ceil((L[12] - L[11]) / 2)
                rec.update({"ca_steps_needed_for_12_sub_steps_r1": total_ca_steps, "c_4": c4, "c_12": c12})
                ok = total_ca_steps > 12 and c12 >= 4 * max(c4, 1)
                c_ok += int(ok)
                if not ok:
                    c_fail.append(rec)
            systems.append(rec)
    # Post-hoc (not pre-registered, see result.json caveats): classify growth by the actual
    # lengths from the seed instead of the matrix root, and use two-step windows so that
    # systems growing only every second step are measured fairly.
    grown = [r for r in systems if r["lengths"][SUB_STEPS] >= 2 * r["lengths"][SUB_STEPS // 2] and r["lengths"][SUB_STEPS] > 1]
    ph_ok = 0
    ph_fail = []
    for r in grown:
        L = r["lengths"]
        total = ceil((L[12] - L[0]) / 2)
        early = ceil((L[4] - L[2]) / 2)
        late = ceil((L[12] - L[10]) / 2)
        ok = total > 12 and late >= 4 * max(early, 1)
        ph_ok += int(ok)
        if not ok:
            ph_fail.append(r)
    not_grown_lambda_gt1 = [r["rule"] for r in systems if r["lambda"] > 1 + 1e-9 and r not in grown]
    posthoc = {"n_systems_growing_from_seed": len(grown), "passing": ph_ok, "failures": ph_fail,
               "lambda_gt_1_but_not_growing_from_seed": not_grown_lambda_gt1,
               "min_total_ca_steps_for_12_sub_steps": min(ceil((r["lengths"][12] - 1) / 2) for r in grown)}
    return {"n_systems": len(systems), "posthoc_C": posthoc, "n_lengths_exactly_matching_matrix": n_exact, "n_lambda_gt_1": n_exp,
            "fraction_lambda_gt_1": n_exp / len(systems), "min_lambda_gt_1": min(r["lambda"] for r in systems if r["lambda"] > 1 + 1e-9),
            "C_systems_passing": c_ok, "C_failures": c_fail,
            "examples": [r for r in systems if r["rule"] in ({"0": "1", "1": "10"}, {"0": "11", "1": "0"}, {"0": "0", "1": "10"}, {"0": "00", "1": "11"})],
            "systems": systems}


# ---------------------------------------------------------------- D
def part_d():
    machines = []
    all_ok = True
    for seed in range(TM_N):
        rng = np.random.default_rng(seed)
        m = int(rng.integers(2, 5))
        delta = {(k, z): (int(rng.integers(0, 2)), int(rng.choice([-1, 1])), int(rng.integers(0, m)))
                 for k in range(m) for z in range(2)}
        colours = [(c, h) for c in (0, 1) for h in range(-1, m)]  # h = -1: no head
        code = {cl: i for i, cl in enumerate(colours)}

        def local(l, c, r):
            (lc, lh), (cc, ch), (rc, rh) = l, c, r
            if ch >= 0:
                w, mv, s2 = delta[(ch, cc)]
                return (w, -1)
            if lh >= 0 and delta[(lh, lc)][1] == 1:
                return (cc, delta[(lh, lc)][2])
            if rh >= 0 and delta[(rh, rc)][1] == -1:
                return (cc, delta[(rh, rc)][2])
            return (cc, -1)

        n = len(colours)
        table = np.zeros((n, n, n), np.int64)
        for a in colours:
            for b in colours:
                for c in colours:
                    table[code[a], code[b], code[c]] = code[local(a, b, c)]
        W = TM_TAPE + 2 * TM_STEPS + 4
        tape = np.zeros(W, np.int64)
        lo = W // 2 - TM_TAPE // 2
        tape[lo:lo + TM_TAPE] = rng.integers(0, 2, TM_TAPE)
        pos, state = W // 2, 0
        ca = np.array([code[(int(c), -1)] for c in tape])
        ca[pos] = code[(int(tape[pos]), state)]
        ok_steps = 0
        for _ in range(TM_STEPS):
            w, mv, s2 = delta[(state, int(tape[pos]))]
            tape[pos] = w
            pos += mv
            state = s2
            ca = np.concatenate(([ca[0]], table[ca[:-2], ca[1:-1], ca[2:]], [ca[-1]]))
            expect = np.array([code[(int(c), -1)] for c in tape])
            expect[pos] = code[(int(tape[pos]), state)]
            if np.array_equal(ca, expect):
                ok_steps += 1
            else:
                break
        all_ok &= ok_steps == TM_STEPS
        machines.append({"seed": seed, "states": m, "ca_colours": n, "steps_exact": ok_steps})
    return {"n_machines": TM_N, "steps_per_machine": TM_STEPS, "all_exact": all_ok, "machines": machines}


def main():
    out = {"A_light_cone": part_a(), "BC_substitution": part_bc(), "D_turing_step_for_step": part_d()}
    a = out["A_light_cone"]["bound_holds"]
    bc = out["BC_substitution"]
    b = bc["fraction_lambda_gt_1"] >= 0.5 and bc["n_lengths_exactly_matching_matrix"] == bc["n_systems"]
    c = bc["C_systems_passing"] == bc["n_lambda_gt_1"] and bc["n_lambda_gt_1"] > 0
    d = out["D_turing_step_for_step"]["all_exact"]
    any_c_refute = any(f["ca_steps_needed_for_12_sub_steps_r1"] <= 12 for f in bc["C_failures"])
    if a and b and c and d:
        verdict = "supports"
    elif (not a) or any_c_refute or (not d):
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["criteria"] = {"A": a, "B": b, "C": c, "D": d}
    out["preregistered_verdict"] = verdict
    ph = bc["posthoc_C"]
    c2 = ph["passing"] == ph["n_systems_growing_from_seed"] and ph["n_systems_growing_from_seed"] > 0
    out["criteria"]["C_posthoc"] = c2
    out["verdict_with_posthoc_C"] = "supports" if (a and b and c2 and d) else ("refutes" if (not a or not d) else "mixed")
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
