#!/usr/bin/env python3
"""Test of wolfram2002-ch03-13: one-deletion tag systems are slow substitution systems
(repetitive or nested); two-deletion tag systems can be very complicated.

Tag system convention (NKS p. 93-94, note p. 894): state is a sequence over {0,1}; at each
step the first n elements are removed and the block rule[removed n-tuple] is appended; if
fewer than n elements remain the sequence becomes empty.  Blocks have length 0..3, so there
are 15 blocks, 15^2 = 225 one-deletion rules and 15^4 = 50625 two-deletion rules.

Part 1: exact equivalence of |s| one-deletion steps with one substitution step.
Part 2: long-run behaviour of all one-deletion rules (finite state space or linear factor
        complexity).
Part 3: census of two-deletion rules from the pair 11 and the complexity test on survivors.
"""
import itertools
import json
import lzma
import random
import sys
from collections import deque

BLOCKS = [tuple(b) for L in range(4) for b in itertools.product((0, 1), repeat=L)]  # 15 blocks
P2_PASSES = 400
P2_MIN_LEN = 2000
P2_MAX_LEN = 200000
P3_PRESCAN_STEPS = 2000
P3_FULL_STEPS = 50000
P3_SKIP = 10000
P3_MAX_LEN = 100000
P3_MAX_CANDIDATES = 400


def tag_run(n, rule, init, steps, record_len=False, detect_recurrence=True):
    """Run a tag system.  Returns (final deque, status, lengths or None).
    status: 'empty', 'recurrent', 'toolong' or 'running'."""
    q = deque(init)
    lengths = [] if record_len else None
    seen = set() if detect_recurrence else None
    for _ in range(steps):
        if len(q) < n:
            q.clear()
            return q, "empty", lengths
        if detect_recurrence:
            key = bytes(q)
            if key in seen:
                return q, "recurrent", lengths
            seen.add(key)
        removed = tuple(q.popleft() for _ in range(n))
        q.extend(rule[removed])
        if record_len:
            lengths.append(len(q))
        if len(q) > P3_MAX_LEN:
            return q, "toolong", lengths
    return q, "running", lengths


def substitute(seq, rule1):
    out = []
    for a in seq:
        out.extend(rule1[(a,)])
    return out


def factor_complexity(seq, L):
    b = bytes(seq)
    return len({b[i:i + L] for i in range(len(b) - L + 1)})


def part1():
    inits = [list(s) for L in range(1, 6) for s in itertools.product((0, 1), repeat=L)]
    total = ok = 0
    for b0 in BLOCKS:
        for b1 in BLOCKS:
            rule = {(0,): b0, (1,): b1}
            for s in inits:
                seq = list(s)
                for _ in range(4):
                    if len(seq) == 0:
                        break
                    q = deque(seq)
                    for _ in range(len(seq)):
                        a = q.popleft()
                        q.extend(rule[(a,)])
                    sub = substitute(seq, rule)
                    total += 1
                    ok += (list(q) == sub)
                    seq = sub
    return {"n_rules": len(BLOCKS) ** 2, "n_initial_sequences": len(inits), "n_pass_checks": total,
            "n_pass_checks_identical": ok, "all_identical": ok == total}


def part2():
    results = {"finite_state": 0, "nested_linear": 0, "complex": 0, "undetermined": 0}
    max_p10 = 0
    worst = None
    details = []
    for b0 in BLOCKS:
        for b1 in BLOCKS:
            rule = {(0,): b0, (1,): b1}
            for init in ([1], [1, 1], [1, 0]):
                seq = list(init)
                seen = set()
                status = None
                for _ in range(P2_PASSES):
                    key = bytes(seq)
                    if len(seq) == 0 or key in seen:
                        status = "finite_state"
                        break
                    seen.add(key)
                    seq = substitute(seq, rule)
                    if len(seq) >= P2_MIN_LEN:
                        p10 = factor_complexity(seq, 10)
                        if p10 > max_p10:
                            max_p10 = p10
                            worst = {"rule": {"0": "".join(map(str, b0)), "1": "".join(map(str, b1))},
                                     "init": "".join(map(str, init)), "length": len(seq), "p10": p10}
                        status = "nested_linear" if p10 <= 60 else "complex"
                        details.append(p10)
                        break
                    if len(seq) > P2_MAX_LEN:
                        status = "undetermined"
                        break
                if status is None:
                    status = "undetermined"
                results[status] += 1
    return {"classification_counts": results, "max_p10_over_growing_cases": max_p10,
            "case_with_max_p10": worst, "n_growing_cases": len(details),
            "p10_histogram": {str(k): details.count(k) for k in sorted(set(details))}}


def lzma_size(vals):
    return len(lzma.compress(bytes(vals), preset=9 | lzma.PRESET_EXTREME))


def complexity_test(lengths):
    diffs = [lengths[i + 1] - lengths[i] + 2 for i in range(P3_SKIP, len(lengths) - 1)]  # values 0..3
    real = lzma_size(diffs)
    rng = random.Random(12345)
    shuf = []
    for _ in range(5):
        d = list(diffs)
        rng.shuffle(d)
        shuf.append(lzma_size(d))
    shuf.sort()
    return real, shuf[2], real / shuf[2]


def part3():
    keys = [(0, 0), (0, 1), (1, 0), (1, 1)]
    census = {"empty": 0, "recurrent": 0, "toolong": 0, "running": 0}
    candidates = []
    rules_all = itertools.product(range(len(BLOCKS)), repeat=4)
    for idx in rules_all:
        rule = {k: BLOCKS[i] for k, i in zip(keys, idx)}
        q, status, _ = tag_run(2, rule, [1, 1], P3_PRESCAN_STEPS)
        census[status] += 1
        if status == "running":
            candidates.append((idx, len(q)))
    # prefer bounded-looking survivors (smaller final length) for the full test
    candidates.sort(key=lambda c: c[1])
    tested = []
    n_pass = 0
    for idx, _ in candidates[:P3_MAX_CANDIDATES]:
        rule = {k: BLOCKS[i] for k, i in zip(keys, idx)}
        q, status, lengths = tag_run(2, rule, [1, 1], P3_FULL_STEPS, record_len=True)
        rec = {"rule": {"".join(map(str, k)): "".join(map(str, rule[k])) for k in keys}, "status_at_50000": status}
        if status == "running":
            real, shuf, ratio = complexity_test(lengths)
            rec.update({"final_length": len(q), "max_length": max(lengths), "lzma_bytes": real,
                        "lzma_bytes_shuffled_median": shuf, "ratio": round(ratio, 4), "passes": ratio >= 0.6})
            n_pass += ratio >= 0.6
        tested.append(rec)
    # NKS p. 94 case (a): {2, {{0,0}->{1,1}, {1,0}->{}, {0,1}->{1,0}, {1,1}->{0,0,0}}}
    nks_a = {(0, 0): (1, 1), (1, 0): (), (0, 1): (1, 0), (1, 1): (0, 0, 0)}
    q, status, lengths = tag_run(2, nks_a, [1, 1], P3_FULL_STEPS, record_len=True)
    nks = {"status_at_50000": status}
    if status == "running":
        real, shuf, ratio = complexity_test(lengths)
        nks.update({"final_length": len(q), "max_length": max(lengths), "lzma_bytes": real,
                    "lzma_bytes_shuffled_median": shuf, "ratio": round(ratio, 4), "passes": ratio >= 0.6})
    passing = [t for t in tested if t.get("passes")]
    return {"n_rules": len(BLOCKS) ** 4, "census_after_%d_steps" % P3_PRESCAN_STEPS: census,
            "n_candidates_fully_tested": len(tested), "n_passing_complexity_test": n_pass,
            "examples_passing": passing[:5], "nks_p94_case_a": nks,
            "ratio_distribution_of_running": sorted(round(t["ratio"], 3) for t in tested if "ratio" in t)}


def main():
    p1 = part1()
    p2 = part2()
    p3 = part3()
    pass1 = p1["all_identical"]
    pass2 = p2["classification_counts"]["complex"] == 0
    pass3 = p3["n_passing_complexity_test"] >= 1
    if pass1 and pass2 and pass3:
        verdict = "supports"
    elif (not pass1) or p2["max_p10_over_growing_cases"] > 200 or not pass3:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out = {"part1_equivalence": p1, "part2_one_deletion_behaviour": p2, "part3_two_deletion": p3,
           "pass_1": pass1, "pass_2": pass2, "pass_3": pass3, "verdict": verdict,
           "parameters": {"blocks": ["".join(map(str, b)) for b in BLOCKS], "part2_passes": P2_PASSES,
                          "part2_min_len": P2_MIN_LEN, "part3_prescan_steps": P3_PRESCAN_STEPS,
                          "part3_full_steps": P3_FULL_STEPS, "part3_skip": P3_SKIP,
                          "part3_max_candidates": P3_MAX_CANDIDATES}}
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
