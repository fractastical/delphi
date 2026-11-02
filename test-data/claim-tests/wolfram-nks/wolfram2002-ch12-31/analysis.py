#!/usr/bin/env python3
"""Length-bounded multiway systems: completeness, consistency, and the
decision procedure of NKS p. 783 (wolfram2002-ch12-31).

Negation is colour swap. The universe is every string of length 1..6.
Writes derived/measured.json.
"""
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LMAX = 6


def complement(s):
    return "".join("1" if c == "0" else "0" for c in s)


def all_rules():
    sides_lhs = ["".join(p) for n in (1, 2) for p in itertools.product("01", repeat=n)]
    sides_rhs = [""] + ["".join(p) for n in (1, 2) for p in itertools.product("01", repeat=n)]
    return [(a, b) for a in sides_lhs for b in sides_rhs]


def successors(s, rules):
    out = []
    for lhs, rhs in rules:
        start = 0
        while True:
            i = s.find(lhs, start)
            if i < 0:
                break
            t = s[:i] + rhs + s[i + len(lhs) :]
            if 1 <= len(t) <= LMAX:
                out.append(t)
            start = i + 1
    return out


def closure_stack(rules):
    seen = {"1"}
    stack = ["1"]
    while stack:
        s = stack.pop()
        for t in successors(s, rules):
            if t not in seen:
                seen.add(t)
                stack.append(t)
    return seen


def closure_bfs(rules):
    seen = {"1"}
    order = ["1"]
    q = ["1"]
    while q:
        s = q.pop(0)
        for t in successors(s, rules):
            if t not in seen:
                seen.add(t)
                order.append(t)
                q.append(t)
    return seen, order


def classify(reachable):
    incomplete = False
    inconsistent = False
    for n in range(1, LMAX + 1):
        for bits in itertools.product("01", repeat=n):
            s = "".join(bits)
            neg = complement(s)
            has = s in reachable
            hasn = neg in reachable
            if has and hasn:
                inconsistent = True
            if not has and not hasn:
                incomplete = True
            if incomplete and inconsistent:
                return False, True
    return (not incomplete), inconsistent


def procedure_errors(reachable, order):
    """Errors of the book's procedure on a set that is supposed to be complete and consistent."""
    pos = {s: i for i, s in enumerate(order)}
    errors = 0
    decided = 0
    for n in range(1, LMAX + 1):
        for bits in itertools.product("01", repeat=n):
            s = "".join(bits)
            neg = complement(s)
            is_ = pos.get(s)
            ineg = pos.get(neg)
            if is_ is None and ineg is None:
                errors += 1
                continue
            if is_ is not None and ineg is not None:
                errors += 1
                continue
            decided += 1
            answer_reached = is_ is not None
            if answer_reached != (s in reachable):
                errors += 1
    return errors, decided


def main():
    rules = all_rules()
    assert len(rules) == 42, len(rules)
    systems = [(r,) for r in rules]
    systems += list(itertools.combinations(rules, 2))
    assert len(systems) == 42 + 42 * 41 // 2

    n_cc = n_inc = n_incons = n_both = 0
    proc_errors = 0
    oracle_disagreements = 0
    cc_strings_checked = 0
    reachable_sizes = []

    for system in systems:
        stack_set = closure_stack(system)
        bfs_set, order = closure_bfs(system)
        if stack_set != bfs_set:
            oracle_disagreements += 1
            continue
        complete, inconsistent = classify(bfs_set)
        incomplete = not complete
        if incomplete and inconsistent:
            n_both += 1
        if incomplete:
            n_inc += 1
        if inconsistent:
            n_incons += 1
        if complete and not inconsistent:
            n_cc += 1
            err, decided = procedure_errors(bfs_set, order)
            proc_errors += err
            cc_strings_checked += decided
        reachable_sizes.append(len(bfs_set))

    def run_anchor(system):
        bfs_set, order = closure_bfs(system)
        stack_set = closure_stack(system)
        assert stack_set == bfs_set
        complete, inconsistent = classify(bfs_set)
        return {
            "rules": [list(r) for r in system],
            "reachable": len(bfs_set),
            "complete": complete,
            "consistent": not inconsistent,
        }

    anchors = {
        "generate_strings_starting_with_black": run_anchor((("1", "10"), ("1", "11"))),
        "identity": run_anchor((("1", "1"),)),
        "flip_axiom": run_anchor((("1", "0"),)),
    }

    measured = {
        "n_rules": len(rules),
        "n_systems": len(systems),
        "universe_strings": sum(2**n for n in range(1, LMAX + 1)),
        "length_max": LMAX,
        "oracle_disagreements": oracle_disagreements,
        "n_complete_and_consistent": n_cc,
        "n_incomplete": n_inc,
        "n_inconsistent": n_incons,
        "n_incomplete_and_inconsistent": n_both,
        "procedure_errors_on_complete_consistent": proc_errors,
        "strings_checked_on_complete_consistent": cc_strings_checked,
        "reachable_size_min": min(reachable_sizes) if reachable_sizes else None,
        "reachable_size_max": max(reachable_sizes) if reachable_sizes else None,
        "anchors": anchors,
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    path = os.path.join(HERE, "derived", "measured.json")
    with open(path, "w") as f:
        json.dump(measured, f, indent=2)
        f.write("\n")
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
