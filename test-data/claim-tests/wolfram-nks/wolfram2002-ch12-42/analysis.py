#!/usr/bin/env python3
"""Test of wolfram2002-ch12-42: finite-model screening of short Nand axiom systems.

Enumerates all Nand expression trees with up to 6 Nands over {a,b,c}, screens the axiom
systems {X = a} and {X = a, a.b = b.a} against all binary operations on 2 and 3 elements
and (by backtracking) on 4 elements. Writes derived/measurements.json.
"""
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TIME_BUDGET_4VAL = 20 * 60


# ------------------------------------------------------------------- trees
def shapes(k):
    """All full binary trees with k internal nodes as post-order programs.
    A program is a list of nodes: ('L', leaf_index) or ('N', left_node, right_node)."""
    if k == 0:
        return [[("L", 0)]]
    out = []
    for kl in range(k):
        for left in shapes(kl):
            for right in shapes(k - 1 - kl):
                nl = len(left)
                leaves_left = sum(1 for n in left if n[0] == "L")
                shifted = [("L", n[1] + leaves_left) if n[0] == "L" else ("N", n[1] + nl, n[2] + nl) for n in right]
                out.append(left + shifted + [("N", nl - 1, nl + len(shifted) - 1)])
    return out


def tree_str(prog, labels, names="abc"):
    vals = []
    for n in prog:
        if n[0] == "L":
            vals.append(names[labels[n[1]]])
        else:
            vals.append(f"({vals[n[1]]}.{vals[n[2]]})")
    return vals[-1]


# ------------------------------------------------------- vectorised screens
def all_ops(d):
    """All d^(d*d) binary operations on range(d), shape [n_ops, d, d]."""
    n = d ** (d * d)
    idx = np.arange(n, dtype=np.int64)
    cells = []
    for c in range(d * d):
        cells.append((idx // d ** c) % d)
    return np.stack(cells, axis=1).reshape(n, d, d)


def evaluate(prog, labels, ops, assigns, d):
    """Values of the tree for every (label row, op, assignment).
    labels: [n_lab, n_leaves]; ops: [n_ops, d, d]; assigns: [n_as, 3]. Returns [n_lab, n_ops, n_as]."""
    n_lab, n_ops, n_as = labels.shape[0], ops.shape[0], assigns.shape[0]
    flat = ops.reshape(n_ops, d * d)
    vals = []
    for n in prog:
        if n[0] == "L":
            v = assigns[:, labels[:, n[1]]].T  # [n_lab, n_as]
            vals.append(np.broadcast_to(v[:, None, :], (n_lab, n_ops, n_as)))
        else:
            x, y = vals[n[1]], vals[n[2]]
            vals.append(np.take_along_axis(flat[None, :, :], (x * d + y).reshape(n_lab, n_ops, n_as), axis=2))
    return vals[-1]


def boolean_nand_tables(d):
    """Operation tables on range(d) isomorphic to the Nand of a Boolean algebra with d elements
    (d = 2: Nand and Nor; d = 4: 12 tables). Returns a set of flattened tuples."""
    if d == 2:
        return {(1, 1, 1, 0), (1, 0, 0, 0)}
    if d == 4:
        base = np.array([[(~(x & y)) & 3 for y in range(4)] for x in range(4)])
        out = set()
        for perm in itertools.permutations(range(4)):
            p = np.array(perm)
            t = np.empty((4, 4), dtype=int)
            for x in range(4):
                for y in range(4):
                    t[p[x], p[y]] = p[base[x, y]]
            out.add(tuple(t.flatten()))
        return out
    raise ValueError


def screen_family(k, n_vars, with_commutativity, label_ops2, label_ops3, assigns2, assigns3):
    """Screen all systems {X = a} (optionally plus a.b = b.a) with k Nands over n_vars variables
    on domains 2 and 3. Returns list of survivors (prog, labels) passing both, plus counts."""
    progs = shapes(k)
    n_leaves = k + 1
    ops2 = label_ops2
    ops3 = label_ops3
    if with_commutativity:
        ops2 = ops2[np.all(ops2 == ops2.transpose(0, 2, 1), axis=(1, 2))]
        ops3 = ops3[np.all(ops3 == ops3.transpose(0, 2, 1), axis=(1, 2))]
    nand2 = boolean_nand_tables(2)
    flat2 = ops2.reshape(len(ops2), 4)
    target_mask2 = np.array([tuple(r) in nand2 for r in flat2])
    labels_all = np.array(list(itertools.product(range(n_vars), repeat=n_leaves)), dtype=np.int64)
    n_total = len(progs) * len(labels_all)
    surv2, surv3 = [], []
    t0 = time.time()
    for prog in progs:
        vals = evaluate(prog, labels_all, ops2, assigns2, 2)  # [n_lab, n_ops, 8]
        target = assigns2[:, 0][None, None, :]
        sat = np.all(vals == target, axis=2)  # [n_lab, n_ops]
        ok2 = np.all(sat == target_mask2[None, :], axis=1)
        for li in np.flatnonzero(ok2):
            surv2.append((prog, labels_all[li]))
    # 3-valued screen on 2-valued survivors, batched by shape
    by_prog = {}
    for prog, lab in surv2:
        by_prog.setdefault(id(prog), (prog, []))[1].append(lab)
    for _, (prog, labs) in by_prog.items():
        labs = np.array(labs)
        chunk = max(1, 40_000_000 // (len(ops3) * 27))
        for s in range(0, len(labs), chunk):
            vals = evaluate(prog, labs[s:s + chunk], ops3, assigns3, 3)
            sat = np.all(vals == assigns3[:, 0][None, None, :], axis=2)
            ok3 = ~np.any(sat, axis=1)
            for li in np.flatnonzero(ok3):
                surv3.append((prog, labs[s + li]))
    return {"n_systems": n_total, "n_pass_2": len(surv2), "n_pass_3": len(surv3), "seconds": time.time() - t0}, surv3


# ----------------------------------------------------- 4-valued backtracking
def models_4(prog, labels, commutative=False, max_models=50):
    """All operation tables on {0,1,2,3} satisfying X = a (and optionally commutativity),
    by backtracking with most-constrained-cell branching."""
    d = 4
    assigns = np.array(list(itertools.product(range(d), repeat=3)), dtype=np.int64)
    target = assigns[:, 0]
    leaf_vals = [assigns[:, labels[n[1]]] if n[0] == "L" else None for n in prog]
    table = np.full(d * d, -1, dtype=np.int64)
    models = []

    def propagate():
        """Returns (conflict, needed_cell_counts)."""
        vals = []
        need = np.zeros(d * d, dtype=np.int64)
        for i, n in enumerate(prog):
            if n[0] == "L":
                vals.append(leaf_vals[i])
            else:
                x, y = vals[n[1]], vals[n[2]]
                known = (x >= 0) & (y >= 0)
                cell = np.where(known, x * d + y, 0)
                v = np.where(known, table[cell], -1)
                # cells that are known but unassigned block this node
                blocked = known & (v < 0)
                if blocked.any():
                    np.add.at(need, cell[blocked], 1)
                vals.append(v)
        root = vals[-1]
        conflict = bool(np.any((root >= 0) & (root != target)))
        return conflict, need, bool(np.all(root >= 0))

    def rec():
        if len(models) >= max_models:
            return
        conflict, need, complete = propagate()
        if conflict:
            return
        if complete and np.all(table >= 0):
            models.append(tuple(table.tolist()))
            return
        if need.max() > 0:
            cell = int(np.argmax(need))
        else:
            cell = int(np.flatnonzero(table < 0)[0])
        x, y = divmod(cell, d)
        for v in range(d):
            table[cell] = v
            if commutative:
                other = y * d + x
                prev = table[other]
                table[other] = v
                rec()
                table[other] = prev
            else:
                rec()
            table[cell] = -1

    rec()
    return models


def main():
    assigns2 = np.array(list(itertools.product(range(2), repeat=3)), dtype=np.int64)
    assigns3 = np.array(list(itertools.product(range(3), repeat=3)), dtype=np.int64)
    ops2, ops3 = all_ops(2), all_ops(3)
    nand4 = boolean_nand_tables(4)
    results = {"families": {}}

    # (I) single axioms {X = a}
    survivors_I = {}
    for k in range(1, 7):
        stats, surv = screen_family(k, 3, False, ops2, ops3, assigns2, assigns3)
        results["families"][f"I_k{k}_3vars"] = stats
        survivors_I[k] = surv
        print(f"I k={k}: {stats}", flush=True)
    stats2v, surv2v = screen_family(6, 2, False, ops2, ops3, assigns2, assigns3)
    results["families"]["I_k6_2vars"] = stats2v
    print(f"I k=6 2 vars: {stats2v}", flush=True)

    # (II) {X = a, a.b = b.a}, k = 4
    statsII, survII = screen_family(4, 3, True, ops2, ops3, assigns2, assigns3)
    results["families"]["II_k4_3vars_commutative"] = statsII
    print(f"II k=4: {statsII}", flush=True)

    # published axiom ((a.b).c).(a.((a.c).a)) = c  -> rename c->a, a->b, b->c to the form X = a
    # ((b.c).a).(b.((b.a).b)) = a
    def find_axiom(target_str):
        for prog, lab in survivors_I[6]:
            if tree_str(prog, lab) == target_str:
                return prog, lab
        return None

    pub_str = "(((b.c).a).(b.((b.a).b)))"
    pub = find_axiom(pub_str)
    results["published_axiom"] = {"form_X_eq_a": pub_str + " = a", "original": "((a.b).c).(a.((a.c).a)) = c", "passes_2_and_3_valued_screen": pub is not None}
    if pub is None:
        # evaluate directly to report its small models
        for prog in shapes(6):
            for lab in itertools.product(range(3), repeat=7):
                if tree_str(prog, np.array(lab)) == pub_str:
                    pub = (prog, np.array(lab))
    t0 = time.time()
    m4 = models_4(*pub)
    results["published_axiom"]["models_4_count"] = len(m4)
    results["published_axiom"]["models_4_exactly_boolean_nand"] = set(m4) == nand4
    results["published_axiom"]["seconds_4valued"] = time.time() - t0
    print("published axiom:", results["published_axiom"], flush=True)

    # 4-valued screen for family II survivors
    t0 = time.time()
    II_pass4 = []
    for prog, lab in survII:
        m = models_4(prog, lab, commutative=True)
        if set(m) == nand4:
            II_pass4.append(tree_str(prog, lab) + " = a")
    results["families"]["II_k4_3vars_commutative"]["n_pass_4"] = len(II_pass4)
    results["families"]["II_k4_3vars_commutative"]["pass_4_examples"] = II_pass4[:8]
    results["families"]["II_k4_3vars_commutative"]["seconds_4valued"] = time.time() - t0
    print("II pass 4:", len(II_pass4), II_pass4[:4], flush=True)

    # supplementary (not part of the pre-registered criteria): 4-valued screen of the shorter
    # single axioms that survived the 3-valued screen
    for k in (4, 5):
        p4 = []
        for prog, lab in survivors_I[k]:
            if set(models_4(prog, lab)) == nand4:
                p4.append(tree_str(prog, lab) + " = a")
        results["families"][f"I_k{k}_3vars"]["n_pass_4"] = len(p4)
        results["families"][f"I_k{k}_3vars"]["pass_3_examples"] = [tree_str(p, l) + " = a" for p, l in survivors_I[k][:4]]
        print(f"I k={k}: pass 4 = {len(p4)}", flush=True)
    # position of the first family-II survivor inside family II alone (the book's own listing)
    fam_II_smaller = sum(len(shapes(k)) * 3 ** (k + 1) for k in range(1, 4))

    # 4-valued screen for family I k=6 survivors (time-budgeted)
    t0 = time.time()
    I6_pass4, done = [], 0
    for prog, lab in survivors_I[6]:
        if time.time() - t0 > TIME_BUDGET_4VAL:
            break
        m = models_4(prog, lab)
        done += 1
        if set(m) == nand4:
            I6_pass4.append(tree_str(prog, lab) + " = a")
    results["families"]["I_k6_3vars"]["n_pass_4"] = len(I6_pass4) if done == len(survivors_I[6]) else None
    results["families"]["I_k6_3vars"]["n_4valued_checked"] = done
    results["families"]["I_k6_3vars"]["pass_4_examples"] = I6_pass4[:10]
    results["families"]["I_k6_3vars"]["seconds_4valued"] = time.time() - t0
    print("I6 pass 4:", len(I6_pass4), "checked", done, "of", len(survivors_I[6]), flush=True)

    # rank of the first screen-passing system in the book's ordering (fewer Nands first)
    # systems with total Nands <= 6: family I with k<=6 and family II with k<=4 (k+2 <= 6)
    fam_II_smaller = sum(len(shapes(k)) * 3 ** (k + 1) for k in range(1, 4))
    n_systems_total_nands_le6 = sum(results["families"][f"I_k{k}_3vars"]["n_systems"] for k in range(1, 7)) + fam_II_smaller + statsII["n_systems"]
    n_systems_fewer_than_6_total = sum(results["families"][f"I_k{k}_3vars"]["n_systems"] for k in range(1, 6)) + fam_II_smaller
    results["enumeration"] = {
        "n_systems_with_fewer_than_6_total_nands_I_and_II": n_systems_fewer_than_6_total,
        "n_systems_with_at_most_6_total_nands_I_and_II": n_systems_total_nands_le6,
        "n_family_II_systems_at_6_total_nands": statsII["n_systems"],
        "first_pass4_system_within_first_n_of_family_II_at_6": None,
    }
    if II_pass4:
        # position among the 3402 in enumeration order (shape order then labels)
        pos = None
        i = 0
        for prog in shapes(4):
            for lab in itertools.product(range(3), repeat=5):
                i += 1
                if tree_str(prog, np.array(lab)) + " = a" == II_pass4[0]:
                    pos = i
                    break
            if pos:
                break
        results["enumeration"]["first_pass4_system_within_first_n_of_family_II_at_6"] = pos
        results["enumeration"]["rank_upper_bound_of_first_pass4_system"] = n_systems_fewer_than_6_total + pos
        results["enumeration"]["rank_within_family_II_alone"] = fam_II_smaller + pos
        results["enumeration"]["n_family_II_systems_with_at_most_6_total_nands"] = fam_II_smaller + statsII["n_systems"]

    crit = {
        "a_published_axiom_works_to_4": bool(results["published_axiom"]["passes_2_and_3_valued_screen"] and results["published_axiom"]["models_4_exactly_boolean_nand"]),
        "b_no_shorter_single_axiom_passes_3": all(results["families"][f"I_k{k}_3vars"]["n_pass_3"] == 0 for k in range(1, 6)),
        "c_family_II_has_pass4_within_10000": bool(II_pass4) and results["enumeration"].get("rank_upper_bound_of_first_pass4_system", 10 ** 9) < 10000,
        "cross_checks": {
            "book_0_of_16896": results["families"]["I_k6_2vars"]["n_pass_3"] == 0 and results["families"]["I_k6_2vars"]["n_systems"] == 16896,
            "book_296_of_288684_pass3": [results["families"]["I_k6_3vars"]["n_pass_3"], results["families"]["I_k6_3vars"]["n_systems"]],
            "book_100_pass4": results["families"]["I_k6_3vars"]["n_pass_4"],
            "book_32_of_3402": [len(II_pass4), statsII["n_systems"]],
        },
    }
    if not crit["a_published_axiom_works_to_4"] or not II_pass4:
        verdict = "refutes"
    elif crit["a_published_axiom_works_to_4"] and crit["b_no_shorter_single_axiom_passes_3"] and crit["c_family_II_has_pass4_within_10000"]:
        verdict = "supports"
    else:
        verdict = "mixed"
    results["criteria"] = crit
    results["verdict"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(results, f, indent=1, default=str)
    print(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
