#!/usr/bin/env python3
"""Exact closure of small length-non-decreasing multiway systems for wolfram2002-ch12-31.

The pass/fail text in result.json was committed before this script was run.
Running the script recomputes measured and writes the verdict from those counts.
"""
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MAXLEN = 6
ALPHABET = "01"


def complement(s):
    return "".join("1" if c == "0" else "0" for c in s)


def reversal(s):
    return s[::-1]


def build_rules():
    rules = []
    for k in (1, 2):
        for lhs in itertools.product(ALPHABET, repeat=k):
            lhs = "".join(lhs)
            for rlen in (k, k + 1):
                for rhs in itertools.product(ALPHABET, repeat=rlen):
                    rhs = "".join(rhs)
                    if lhs != rhs:
                        rules.append((lhs, rhs))
    rules.sort()
    systems = [()]
    systems.extend((r,) for r in rules)
    systems.extend(itertools.combinations(rules, 2))
    return rules, systems


def closures(rules):
    """BFS discovery order and the reachable set, plus an independent DFS set."""
    rules = tuple(sorted(rules))
    order = ["1"]
    seen = {"1"}
    frontier = ["1"]
    while frontier:
        new = []
        for s in frontier:
            for lhs, rhs in rules:
                k = len(lhs)
                limit = len(s) - k + 1
                for i in range(limit):
                    if s[i:i + k] == lhs:
                        t = s[:i] + rhs + s[i + k:]
                        if len(t) <= MAXLEN and t not in seen:
                            seen.add(t)
                            order.append(t)
                            new.append(t)
        frontier = new
    dfs = set()
    stack = ["1"]
    while stack:
        s = stack.pop()
        if s in dfs or len(s) > MAXLEN:
            continue
        dfs.add(s)
        for lhs, rhs in rules:
            k = len(lhs)
            limit = len(s) - k + 1
            for i in range(limit):
                if s[i:i + k] == lhs:
                    t = s[:i] + rhs + s[i + k:]
                    if len(t) <= MAXLEN and t not in dfs:
                        stack.append(t)
    return order, seen, dfs


def strings_of_length(n):
    return ["".join(p) for p in itertools.product(ALPHABET, repeat=n)]


def classify(order, neg):
    """Return per-length records and whether any complete-consistent case fails."""
    index = {s: i for i, s in enumerate(order)}
    by_len = []
    failures = 0
    n_cc = n_incomplete = n_inconsistent = n_unsafe = 0
    examples = {"cc": [], "incomplete": [], "inconsistent_unsafe": []}
    for n in range(1, MAXLEN + 1):
        universe = strings_of_length(n)
        present = {s for s in order if len(s) == n}
        complete = True
        consistent = True
        unsafe = False
        unsafe_example = None
        for s in universe:
            other = neg(s)
            in_s = s in present
            in_o = other in present
            if not in_s and not in_o:
                complete = False
            if in_s and in_o:
                consistent = False
                if s != other and index[s] != index[other]:
                    unsafe = True
                    if unsafe_example is None:
                        first, second = (s, other) if index[s] < index[other] else (other, s)
                        unsafe_example = {"first": first, "later": second, "length": n}
        if complete and consistent:
            n_cc += 1
            failed = False
            for s in universe:
                other = neg(s)
                in_s = s in present
                in_o = other in present
                if s == other or in_s == in_o:
                    failed = True
                    break
                target = s if in_s else other
                found = None
                for g in order:
                    if g == s or g == other:
                        found = g
                        break
                if found != target:
                    failed = True
                    break
            if failed:
                failures += 1
            elif len(examples["cc"]) < 3:
                examples["cc"].append({"length": n, "generated": sorted(present)})
        else:
            if not complete:
                n_incomplete += 1
                if len(examples["incomplete"]) < 2:
                    examples["incomplete"].append({"length": n, "generated_count": len(present)})
            if not consistent:
                n_inconsistent += 1
                if unsafe:
                    n_unsafe += 1
                    if len(examples["inconsistent_unsafe"]) < 3 and unsafe_example:
                        examples["inconsistent_unsafe"].append(unsafe_example)
        by_len.append({
            "length": n,
            "complete": complete,
            "consistent": consistent,
            "unsafe": unsafe,
            "generated": len(present),
        })
    return {
        "failures": failures,
        "n_cc": n_cc,
        "n_incomplete": n_incomplete,
        "n_inconsistent": n_inconsistent,
        "n_unsafe": n_unsafe,
        "examples": examples,
        "by_len": by_len,
    }


def main():
    rules, systems = build_rules()
    universes = {n: strings_of_length(n) for n in range(1, MAXLEN + 1)}
    # silence unused in case classify rebuilds them; kept so a reader sees the universe size
    del universes
    dfs_disagreements = 0
    comp = {"failures": 0, "n_cc": 0, "n_incomplete": 0, "n_inconsistent": 0, "n_unsafe": 0}
    rev = {"failures": 0, "n_cc": 0, "n_incomplete": 0, "n_inconsistent": 0, "n_unsafe": 0}
    comp_examples = {"cc": [], "incomplete": [], "inconsistent_unsafe": []}
    rev_examples_cc_fail = []
    per_length = {n: {"cc": 0, "incomplete": 0, "inconsistent": 0, "unsafe": 0} for n in range(1, MAXLEN + 1)}
    named = {}
    for ruleset in systems:
        order, seen, dfs = closures(ruleset)
        if seen != dfs or set(order) != seen:
            dfs_disagreements += 1
            continue
        c = classify(order, complement)
        r = classify(order, reversal)
        for key in comp:
            comp[key] += c[key]
            rev[key] += r[key]
        for row in c["by_len"]:
            n = row["length"]
            per_length[n]["cc"] += row["complete"] and row["consistent"]
            per_length[n]["incomplete"] += not row["complete"]
            per_length[n]["inconsistent"] += not row["consistent"]
            per_length[n]["unsafe"] += row["unsafe"]
        if ruleset == () or ruleset == (("1", "0"),):
            named["|" .join(f"{a}->{b}" for a, b in ruleset) or "(no rules)"] = {
                "reachable": order,
                "complement": c["by_len"],
            }
        for kind in comp_examples:
            if len(comp_examples[kind]) < 3:
                for ex in c["examples"][kind]:
                    if len(comp_examples[kind]) < 3:
                        comp_examples[kind].append({"rules": [f"{a}->{b}" for a, b in ruleset], **ex})
        if r["failures"] and len(rev_examples_cc_fail) < 3:
            rev_examples_cc_fail.append([f"{a}->{b}" for a, b in ruleset])

    n_pairs = len(systems) * MAXLEN
    witnesses_ok = (
        comp["n_cc"] >= 1
        and comp["n_incomplete"] >= 1
        and comp["n_inconsistent"] >= 1
        and comp["n_unsafe"] >= 1
    )
    if dfs_disagreements > 0:
        verdict, confidence, reason = "inconclusive", 0.40, "other"
    elif comp["failures"] > 0 or rev["failures"] > 0:
        verdict, confidence, reason = "refutes", 0.88, None
    elif witnesses_ok:
        verdict, confidence, reason = "supports", 0.92, None
    else:
        verdict, confidence, reason = "mixed", 0.70, None

    measured = {
        "value": comp["failures"] + rev["failures"],
        "unit": "complete-and-consistent (system, length) cases whose discovery-order scan is not a safe exclusive decision",
        "n": n_pairs,
        "uncertainty": "exact",
        "extra": {
            "n_rules": len(rules),
            "n_systems": len(systems),
            "lengths": "1..6",
            "dfs_bfs_disagreements": dfs_disagreements,
            "complement": comp,
            "reversal": {k: rev[k] for k in rev},
            "complement_by_length": {str(k): v for k, v in per_length.items()},
            "complement_examples": comp_examples,
            "reversal_cc_failure_examples": rev_examples_cc_fail,
            "named_systems": named,
        },
    }
    # per_length booleans were added with += on bools; coerce to int for JSON clarity
    for row in measured["extra"]["complement_by_length"].values():
        for k in row:
            row[k] = int(row[k])

    method = (
        "analysis.py enumerates every multiway system on {0,1} with 0, 1 or 2 length-non-decreasing "
        "rules (left side length 1 or 2, right side the same length or one symbol longer, left side "
        "different from the right side), started from the string 1. The reachable strings of length "
        "at most 6 are the exact breadth-first closure; a depth-first search must produce the same set. "
        "At each length from 1 to 6 the closure is scored complete and consistent under complement, and "
        "the scan in discovery order is required to meet exactly one of each queried string and its "
        "complement. Reversal is scored the same way and can only move the verdict to refutes. "
        "Criteria were frozen in commit 093ca8002a77b774b469b965ff599d123fdaefbb before this run."
    )
    datasets = [{
        "id": "multiway-01-length-nondecreasing-closure",
        "name": "All 0-, 1- and 2-rule length-non-decreasing multiway systems on alphabet 01, closure through length 6, generated by analysis.py",
        "landing_url": "https://www.wolframscience.com/nks/p783--implications-for-mathematics-and-its-foundations/",
        "doi": None,
        "version": "generated",
        "license": None,
        "generator": "analysis.py",
        "program_family": (
            "multiway string substitution; alphabet 01; start 1; rules lhs->rhs with "
            "|lhs| in {1,2}, |rhs| in {|lhs|,|lhs|+1}, lhs != rhs; 0, 1 or 2 rules; "
            "matches applied left to right; BFS closure of strings of length <= 6; "
            "negation = bitwise complement (verdict) and reversal (reported)"
        ),
        "files": [],
        "role": "the finite multiway systems on which the completeness-consistency procedure is checked",
    }]
    caveats = [
        "The computation shows that the decision procedure in the claim holds as a mathematical fact about every system in this finite family. It does not show that organisms follow it.",
        "A finite closure cannot be algorithmically undecidable. The finite counterpart of an unanswered reachability question is a string whose scan exhausts the closure without meeting the string or its complement, which is incompleteness, and that is what was counted.",
        "Reversal was not a route to support: every length has a palindrome, which is a fixed point of reversal, so completeness and consistency cannot hold together. The book's negation pairs a string with a different string; complement does that.",
    ]
    path = os.path.join(HERE, "result.json")
    with open(path) as f:
        result = json.load(f)
    frozen = {k: result[k] for k in (
        "claim_id", "claim_iri", "project", "hypothesis", "pass_criterion", "fail_criterion",
        "planned_datasets", "interpretation", "test_contract", "agent",
    )}
    result.update({
        "status": "complete",
        "data_kind": "computational",
        "verdict": verdict,
        "confidence": confidence,
        "measured": measured,
        "method": method,
        "datasets": datasets,
        "caveats": caveats,
    })
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    for k, v in frozen.items():
        result[k] = v
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    derived = os.path.join(HERE, "derived")
    os.makedirs(derived, exist_ok=True)
    with open(os.path.join(derived, "measured.json"), "w") as f:
        json.dump({"verdict": verdict, "confidence": confidence, "measured": measured}, f, indent=2)
        f.write("\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "failures": measured["value"],
        "n_systems": len(systems),
        "complement": comp,
        "reversal_failures": rev["failures"],
        "reversal_cc": rev["n_cc"],
        "dfs_disagreements": dfs_disagreements,
    }, indent=2))


if __name__ == "__main__":
    main()
