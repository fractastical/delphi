#!/usr/bin/env python3
"""Test of wolfram2002-ch09-17: substitution systems whose blocks never overlap
themselves or each other give the same causal network for every order of replacements.

Family: all 1- and 2-rule systems over {A,B} with lhs of length 1..3 and |rhs| < |lhs|
(so every evolution terminates), all initial strings of length 1..5, all complete
evolutions. Each element carries an identity (creating event, position); an event is
identified by (rule, identities of consumed elements); the causal network has an edge
from the creator of each consumed element (node 'init' for initial elements) to the
event. Networks from different orders are compared exactly (identity-labelled) and up
to isomorphism (brute force over event permutations, <= 5 events).

Run: python3 analysis.py   (standard library only)
"""
import json
import os
import time
from itertools import combinations, permutations, product

HERE = os.path.dirname(os.path.abspath(__file__))
LETTERS = "AB"
MAX_INIT = 5


def all_words(min_len, max_len):
    return ["".join(p) for n in range(min_len, max_len + 1) for p in product(LETTERS, repeat=n)]


def overlaps(u, v):
    """True if a non-empty proper suffix of u equals a prefix of v."""
    return any(u[-i:] == v[:i] for i in range(1, min(len(u), len(v))))


def non_overlapping(lhss):
    for u in lhss:
        if overlaps(u, u):
            return False
    for u, v in combinations(lhss, 2):
        if overlaps(u, v) or overlaps(v, u) or u in v or v in u:
            return False
    return True


def complete_evolutions(cells, rules, events, edges, out):
    """Enumerate all complete evolutions; collect (events, edges) networks in `out`."""
    matches = []
    for ri, (lhs, rhs) in enumerate(rules):
        L = len(lhs)
        for pos in range(len(cells) - L + 1):
            if all(cells[pos + j][0] == lhs[j] for j in range(L)):
                matches.append((ri, pos))
    if not matches:
        out.add((frozenset(events), frozenset(edges)))
        return 1
    n = 0
    for ri, pos in matches:
        lhs, rhs = rules[ri]
        consumed = cells[pos:pos + len(lhs)]
        eid = (ri, tuple(c[1] for c in consumed))
        new_cells = [(ch, (eid, j)) for j, ch in enumerate(rhs)]
        new_edges = {(c[1][0] if c[1][0] != "init" else "init", eid) for c in consumed}
        n += complete_evolutions(cells[:pos] + new_cells + cells[pos + len(lhs):], rules,
                                 events | {eid}, edges | new_edges, out)
    return n


def canonical(network):
    """Canonical form of a causal network up to relabelling of events (rule labels kept)."""
    events, edges = network
    ev = sorted(events, key=repr)
    n = len(ev)
    best = None
    for perm in permutations(range(n)):
        pos = {e: perm[i] for i, e in enumerate(ev)}
        labels = tuple(sorted((pos[e], e[0]) for e in ev))
        es = tuple(sorted((-1 if a == "init" else pos[a], pos[b]) for a, b in edges))
        enc = (labels, es)
        if best is None or enc < best:
            best = enc
    return best


def run_family(max_lhs, max_init, only_nonoverlapping=False):
    t0 = time.time()
    blocks = all_words(1, max_lhs)
    rulesets = []
    for lhs in blocks:
        if only_nonoverlapping and not non_overlapping([lhs]):
            continue
        for rhs in all_words(0, len(lhs) - 1):
            rulesets.append(((lhs, rhs),))
    for l1, l2 in combinations(blocks, 2):
        if only_nonoverlapping and not non_overlapping([l1, l2]):
            continue
        for r1 in all_words(0, len(l1) - 1):
            for r2 in all_words(0, len(l2) - 1):
                rulesets.append(((l1, r1), (l2, r2)))
    inits = all_words(1, max_init)

    stats = {"non_overlapping": {"rulesets": 0, "pairs": 0, "pairs_with_multiple_evolutions": 0,
                                 "pairs_identical_networks": 0, "pairs_one_iso_class": 0,
                                 "pairs_multiple_iso_classes": 0, "pairs_multiple_final_strings": 0,
                                 "complete_evolutions": 0, "violation_examples": []},
             "overlapping": {"rulesets": 0, "pairs": 0, "pairs_with_multiple_evolutions": 0,
                             "pairs_identical_networks": 0, "pairs_one_iso_class": 0,
                             "pairs_multiple_iso_classes": 0, "pairs_multiple_final_strings": 0,
                             "complete_evolutions": 0, "rulesets_with_order_dependence": 0}}
    nonov_rulesets = []
    for rules in rulesets:
        lhss = [l for l, _ in rules]
        key = "non_overlapping" if non_overlapping(lhss) else "overlapping"
        st = stats[key]
        st["rulesets"] += 1
        if key == "non_overlapping":
            nonov_rulesets.append(rules)
        order_dependent = False
        for init in inits:
            cells = [(ch, ("init", i)) for i, ch in enumerate(init)]
            nets = set()
            finals = set()

            def run(cells, events, edges):
                return complete_evolutions(cells, rules, events, edges, nets)

            n_ev = run(cells, frozenset(), frozenset())
            # final strings: recompute cheaply by replaying? Instead derive from networks is not
            # possible; so track them with a second light enumeration.
            def finals_enum(cs):
                ms = [(ri, p) for ri, (l, r) in enumerate(rules) for p in range(len(cs) - len(l) + 1)
                      if cs[p:p + len(l)] == l]
                if not ms:
                    finals.add(cs)
                    return
                for ri, p in ms:
                    l, r = rules[ri]
                    finals_enum(cs[:p] + r + cs[p + len(l):])
            finals_enum(init)
            st["pairs"] += 1
            st["complete_evolutions"] += n_ev
            if n_ev < 2:
                continue
            st["pairs_with_multiple_evolutions"] += 1
            if len(finals) > 1:
                st["pairs_multiple_final_strings"] += 1
            if len(nets) == 1:
                st["pairs_identical_networks"] += 1
                st["pairs_one_iso_class"] += 1
            else:
                classes = {canonical(nw) for nw in nets}
                if len(classes) == 1:
                    st["pairs_one_iso_class"] += 1
                else:
                    st["pairs_multiple_iso_classes"] += 1
                    order_dependent = True
                    if key == "non_overlapping" and len(st["violation_examples"]) < 5:
                        st["violation_examples"].append({"rules": rules, "init": init, "classes": len(classes)})
        if key == "overlapping" and order_dependent:
            st["rulesets_with_order_dependence"] += 1

    no = stats["non_overlapping"]
    ov = stats["overlapping"]
    out = {
        "max_lhs_length": max_lhs, "max_init_length": max_init, "only_nonoverlapping": only_nonoverlapping,
        "rulesets_total": len(rulesets), "initial_strings": len(inits),
        "non_overlapping": no, "overlapping": ov,
        "non_overlapping_rulesets_list": [[list(r) for r in rs] for rs in nonov_rulesets],
        "fraction_non_overlapping_multi_evolution_pairs_with_one_iso_class":
            no["pairs_one_iso_class"] / no["pairs_with_multiple_evolutions"] if no["pairs_with_multiple_evolutions"] else None,
        "fraction_overlapping_rulesets_with_order_dependence": ov["rulesets_with_order_dependence"] / ov["rulesets"] if ov["rulesets"] else None,
        "seconds": round(time.time() - t0, 1),
    }
    return out


def main():
    primary = run_family(3, MAX_INIT)
    print(json.dumps({k: v for k, v in primary.items() if k != "non_overlapping_rulesets_list"}, indent=1))
    # Supplementary (not pre-registered): longer blocks, so that non-overlapping PAIRS of
    # multi-letter blocks occur; only non-overlapping rule sets, initial strings up to 6.
    supp = run_family(4, 6, only_nonoverlapping=True)
    supp.pop("overlapping", None)
    print(json.dumps({k: v for k, v in supp.items() if k != "non_overlapping_rulesets_list"}, indent=1))
    out = {"primary_preregistered_family": primary, "supplementary_nonoverlapping_lhs_le_4_init_le_6": supp}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
