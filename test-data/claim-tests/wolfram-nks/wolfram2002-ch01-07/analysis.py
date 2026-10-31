#!/usr/bin/env python3
"""wolfram2002-ch01-07: a one-sentence rule (ECA rule 110) is universal.

Executes the parts of Cook's (2004) proof that are fully specified constructions:
  A  the one-sentence statement of rule 110 reproduces Wolfram's rule table
  B  2-symbol Turing machine -> 2-deletion tag system (Cook 2004 section 2.1, pp. 4-7)
  C  2-tag system -> cyclic tag system (Cook 2004 section 2.2, pp. 7-8)
  D  the glider velocities of Cook 2004 figure 5 occur in rule 110 from random initial
     conditions (measured in ../wolfram2002-ch02-09/derived/measured.json)
Deterministic; prints JSON to stdout.
"""
import hashlib
import json
import os
import sys
from collections import deque
from fractions import Fraction

import numpy as np

SENTENCE = ("A cell becomes black if it or its right-hand neighbour is black, "
            "unless it and both of its neighbours are black")
N_TM = 30
TM_STEPS = 40
TM_INIT_BITS = 8
TAG_STEP_CAP = 100000
TAPE_CAP = 1 << 16          # abort a machine once 2(TL+TR) would exceed this (unary tape length)
N_RANDOM_TAG = 30
TAG_STEPS_C = 200
COOK_FIG5 = {"A": Fraction(2, 3), "B": Fraction(-1, 2), "C": Fraction(0), "D": Fraction(1, 5),
             "E": Fraction(-4, 15), "Ebar": Fraction(-8, 30), "F": Fraction(-4, 36), "G": Fraction(-14, 42)}
CH0209 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wolfram2002-ch02-09", "derived", "measured.json")


# ---------------------------------------------------------------- A: one sentence
def sentence_rule(l, c, r):
    return int((c or r) and not (l and c and r))


def part_a():
    table = {}
    ok = True
    for code in range(8):
        l, c, r = (code >> 2) & 1, (code >> 1) & 1, code & 1
        wolfram = (110 >> code) & 1
        table["%d%d%d" % (l, c, r)] = {"rule110": wolfram, "sentence": sentence_rule(l, c, r)}
        ok &= wolfram == sentence_rule(l, c, r)
    return {"sentence": SENTENCE, "words": len(SENTENCE.split()), "table": table, "sentence_equals_rule110": ok}


# ---------------------------------------------------------------- B: TM -> tag system
def random_tm(rng, m):
    """delta[(k, z)] = (write, move, new_state); move +1 = right, -1 = left; no halting."""
    return {(k, z): (int(rng.integers(0, 2)), int(rng.choice([-1, 1])), int(rng.integers(0, m)))
            for k in range(m) for z in range(2)}


def tm_step(delta, conf):
    k, h, tl, tr = conf
    w, mv, k2 = delta[(k, h)]
    if mv == 1:
        return (k2, tr & 1, 2 * tl + w, tr >> 1)
    return (k2, tl & 1, tl >> 1, 2 * tr + w)


def cook_tag_rules(delta, m):
    """Cook 2004 pp. 5-6.  Symbols are tuples (letter, state, suffix), suffix in {None, 0, 1, '*'}."""
    rules = {}
    for k in range(m):
        for z in (0, 1):
            w, mv, k2 = delta[(k, z)]
            a = (mv == -1 and w == 1)
            b = (z == 0)
            c = (mv == 1 and w == 1)
            d = (mv == 1)
            e = (mv == -1)
            rules[("H", k, z)] = ([("R", k2, "*")] * 2 if a else []) + ([("H", k2, None)] if b else []) \
                + [("H", k2, None)] + ([("L", k2, None)] * 2 if c else [])
            rules[("L", k, z)] = [("L", k2, None)] + ([("L", k2, None)] * 3 if d else [])
            rules[("R", k, z)] = [("R", k2, None)] + ([("R", k2, None)] * 3 if e else [])
        rules[("R", k, "*")] = [("R", k, None)] * 2
        rules[("H", k, None)] = [("H", k, 1), ("H", k, 0)]
        rules[("L", k, None)] = [("L", k, 1), ("L", k, 0)]
        rules[("R", k, None)] = [("R", k, 1), ("R", k, 0)]
    return rules


def encode_conf(conf):
    k, h, tl, tr = conf
    head = [("H", k, 1), ("H", k, 0)] if h == 1 else [("H", k, 0)]
    return head + [("L", k, 1), ("L", k, 0)] * tl + [("R", k, 1), ("R", k, 0)] * tr


def tag_step(tape, rules, deletions=2):
    """Read the first symbol, append its appendant, delete `deletions` symbols."""
    tape.extend(rules[tape[0]])
    for _ in range(deletions):
        tape.popleft()


def part_b():
    checks = 0
    successes = 0
    machines = []
    for seed in range(N_TM):
        rng = np.random.default_rng(seed)
        m = int(rng.integers(2, 5))
        delta = random_tm(rng, m)
        rules = cook_tag_rules(delta, m)
        conf = (0, int(rng.integers(0, 2)), int(rng.integers(0, 1 << TM_INIT_BITS)), int(rng.integers(0, 1 << TM_INIT_BITS)))
        tape = deque(encode_conf(conf))
        rec = {"seed": seed, "states": m, "tag_symbols": 10 * m, "steps_checked": 0, "steps_ok": 0,
               "max_tape": len(tape), "stopped": "completed %d steps" % TM_STEPS}
        for step in range(TM_STEPS):
            conf = tm_step(delta, conf)
            target = encode_conf(conf)
            if len(target) > TAPE_CAP:
                rec["stopped"] = "unary tape would exceed %d symbols at TM step %d" % (TAPE_CAP, step + 1)
                break
            found = False
            for _ in range(TAG_STEP_CAP):
                tag_step(tape, rules)
                rec["max_tape"] = max(rec["max_tape"], len(tape))
                if len(tape) == len(target) and list(tape) == target:
                    found = True
                    break
            checks += 1
            rec["steps_checked"] += 1
            if found:
                successes += 1
                rec["steps_ok"] += 1
            else:
                rec["stopped"] = "tag system failed to reach TM configuration at step %d" % (step + 1)
                break
        machines.append(rec)
    return {"n_machines": N_TM, "checks": checks, "successes": successes, "all_ok": checks == successes,
            "machines": machines}


# ---------------------------------------------------------------- C: tag -> cyclic tag
def encode_symbol(i, k):
    return "N" * i + "Y" + "N" * (k - 1 - i)


def cts_from_tag(appendants, k):
    """Cook 2004 p. 8: k encoded appendants (in symbol order) followed by k empty appendants."""
    return ["".join(encode_symbol(s, k) for s in appendants[i]) for i in range(k)] + [""] * k


def cts_run(tape, productions, nsteps, start):
    i = start
    for _ in range(nsteps):
        if not tape:
            break
        ch = tape.popleft()
        if ch == "Y":
            tape.extend(productions[i % len(productions)])
        i += 1
    return i


def check_tag_vs_cts(appendants, k, tape0, nsteps):
    tag = deque(tape0)
    cts = deque("".join(encode_symbol(s, k) for s in tape0))
    prods = cts_from_tag(appendants, k)
    rules = {s: appendants[s] for s in range(k)}
    checks = ok = 0
    pos = 0
    for _ in range(nsteps):
        if len(tag) < 2:
            break
        tag_step(tag, rules)
        pos = cts_run(cts, prods, 2 * k, pos)
        checks += 1
        ok += int("".join(cts) == "".join(encode_symbol(s, k) for s in tag))
    return checks, ok, len(tag)


def part_c():
    total = okc = 0
    cases = []
    for seed in range(N_TM):
        rng = np.random.default_rng(seed)
        m = int(rng.integers(2, 5))
        delta = random_tm(rng, m)
        rules = cook_tag_rules(delta, m)
        conf = (0, int(rng.integers(0, 2)), int(rng.integers(0, 1 << TM_INIT_BITS)), int(rng.integers(0, 1 << TM_INIT_BITS)))
        symbols = sorted(rules.keys(), key=str)
        index = {s: i for i, s in enumerate(symbols)}
        appendants = [[index[x] for x in rules[s]] for s in symbols]
        tape0 = [index[x] for x in encode_conf(conf)]
        c, o, final_len = check_tag_vs_cts(appendants, len(symbols), tape0, TAG_STEPS_C)
        total += c
        okc += o
        cases.append({"source": "TM seed %d" % seed, "k": len(symbols), "checks": c, "ok": o, "final_tag_length": final_len})
    for seed in range(1000, 1000 + N_RANDOM_TAG):
        rng = np.random.default_rng(seed)
        k = int(rng.integers(2, 7))
        appendants = [[int(x) for x in rng.integers(0, k, int(rng.integers(0, 5)))] for _ in range(k)]
        tape0 = [int(x) for x in rng.integers(0, k, int(rng.integers(2, 7)))]
        c, o, final_len = check_tag_vs_cts(appendants, k, tape0, TAG_STEPS_C)
        total += c
        okc += o
        cases.append({"source": "random 2-tag seed %d" % seed, "k": k, "checks": c, "ok": o, "final_tag_length": final_len})
    return {"n_tag_systems": len(cases), "checks": total, "successes": okc, "all_ok": total == okc, "cases": cases}


# ---------------------------------------------------------------- D: glider inventory
def part_d():
    with open(CH0209, "rb") as f:
        raw = f.read()
    m = json.loads(raw)
    observed = {Fraction(s["velocity"]) for s in m["structures_by_velocity"]}
    found = {name: (v in observed) for name, v in COOK_FIG5.items()}
    return {"source_file": os.path.relpath(CH0209, os.getcwd()), "sha256": hashlib.sha256(raw).hexdigest(),
            "observed_velocities": sorted(str(v) for v in observed),
            "cook_fig5_velocities": {n: str(v) for n, v in COOK_FIG5.items()},
            "found": found, "n_distinct_fig5_velocities": len(set(COOK_FIG5.values())),
            "n_found": len({COOK_FIG5[n] for n, f in found.items() if f}),
            "all_found": all(found.values())}


def main():
    out = {"A_one_sentence": part_a(), "B_tm_to_tag": part_b(), "C_tag_to_cts": part_c(), "D_gliders": part_d()}
    a = out["A_one_sentence"]["sentence_equals_rule110"] and out["A_one_sentence"]["words"] <= 30
    b = out["B_tm_to_tag"]["all_ok"]
    c = out["C_tag_to_cts"]["all_ok"]
    d = out["D_gliders"]["all_found"]
    fb = 1 - out["B_tm_to_tag"]["successes"] / max(1, out["B_tm_to_tag"]["checks"])
    fc = 1 - out["C_tag_to_cts"]["successes"] / max(1, out["C_tag_to_cts"]["checks"])
    if a and b and c and d:
        verdict = "supports"
    elif (not a) or fb > 0.05 or fc > 0.05 or out["D_gliders"]["n_found"] < 5:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["criteria"] = {"A": a, "B": b, "C": c, "D": d}
    out["verdict"] = verdict
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
