#!/usr/bin/env python3
"""Test of wolfram2002-ch12-41: finite models (operator forms) of the simplest single-equation axiom systems.

Terms: int = variable index, tuple (l, r) = l o r.  Operator tables for k elements are all k^(k^2)
arrays T[x, y]; Wolfram's rule number has digit f(x, y) at position k*x + y (least significant = f(0,0)).

Run: python3 analysis.py [--k4]   (writes derived/axioms.csv.gz and derived/supplementary.json, prints measured block;
     about 2 minutes; --k4 adds the capped 4-element search S2, about 25 minutes)
"""
import csv
import gzip
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N_MAX = 4
KS = (2, 3)
MANY_MIN = 3
PASS_MANY, PASS_SINGLE = 0.80, 0.05
FAIL_MANY, FAIL_SINGLE = 0.50, 0.20
VALIDATION_N_MAX = 6


# ----------------------------------------------------------------------------- enumeration
def shapes(n_ops):
    """Binary trees with n_ops internal nodes; leaves are placeholders None."""
    if n_ops == 0:
        yield None
        return
    for i in range(n_ops):
        for l in shapes(i):
            for r in shapes(n_ops - 1 - i):
                yield (l, r)


def n_leaves(shape):
    return 1 if shape is None else n_leaves(shape[0]) + n_leaves(shape[1])


def rgs(m):
    """Restricted growth strings of length m (canonical variable labellings)."""
    def rec(prefix, mx):
        if len(prefix) == m:
            yield tuple(prefix)
            return
        for v in range(mx + 2):
            yield from rec(prefix + [v], max(mx, v))
    yield from rec([0], 0)


def fill(shape, labels):
    it = iter(labels)

    def rec(s):
        if s is None:
            return next(it)
        return (rec(s[0]), rec(s[1]))
    return rec(shape)


def leaves(term, out):
    if isinstance(term, tuple):
        leaves(term[0], out)
        leaves(term[1], out)
    else:
        out.append(term)
    return out


def relabel(term, mapping):
    if isinstance(term, tuple):
        return (relabel(term[0], mapping), relabel(term[1], mapping))
    return mapping[term]


def canon_eq(lhs, rhs):
    order = {}
    for v in leaves(lhs, []) + leaves(rhs, []):
        if v not in order:
            order[v] = len(order)
    return (relabel(lhs, order), relabel(rhs, order))


def term_str(term, names="abcdefgh"):
    if isinstance(term, tuple):
        return "(" + term_str(term[0], names) + "∘" + term_str(term[1], names) + ")"
    return names[term]


def enumerate_family(n_max):
    seen = set()
    out = []
    for n in range(1, n_max + 1):
        for i in range(0, n + 1):
            for ls in shapes(i):
                for rs in shapes(n - i):
                    m = n_leaves(ls) + n_leaves(rs)
                    ml = n_leaves(ls)
                    for lab in rgs(m):
                        lhs = fill(ls, lab[:ml])
                        rhs = fill(rs, lab[ml:])
                        if lhs == rhs:
                            continue
                        key = min(canon_eq(lhs, rhs), canon_eq(rhs, lhs), key=repr)
                        if key in seen:
                            continue
                        seen.add(key)
                        out.append((n, key[0], key[1]))
    return out


# ----------------------------------------------------------------------------- model finding
def all_tables(k):
    M = k ** (k * k)
    nums = np.arange(M)
    T = np.empty((M, k, k), dtype=np.int8)
    for x in range(k):
        for y in range(k):
            T[:, x, y] = (nums // (k ** (k * x + y))) % k
    return T


def evaluate(term, T, idx, assign):
    """Value of term for each table in T (rows idx) under assignment (array over variables)."""
    if isinstance(term, tuple):
        l = evaluate(term[0], T, idx, assign)
        r = evaluate(term[1], T, idx, assign)
        return T[idx, l, r]
    return np.full(len(idx), assign[term], dtype=np.int8)


def models(lhs, rhs, k, T):
    nvars = max(leaves(lhs, []) + leaves(rhs, [])) + 1
    idx = np.arange(T.shape[0])
    for assign in itertools.product(range(k), repeat=nvars):
        ok = evaluate(lhs, T, idx, assign) == evaluate(rhs, T, idx, assign)
        idx = idx[ok]
        if idx.size == 0:
            break
    return idx


def canonical_numbers(idx, k, T):
    """Distinct models up to relabelling of the k elements; returns set of canonical rule numbers."""
    perms = list(itertools.permutations(range(k)))
    weights = np.array([k ** (k * x + y) for x in range(k) for y in range(k)])
    out = set()
    for i in idx:
        t = T[i]
        best = None
        for p in perms:
            pa = np.array(p)
            inv = np.argsort(pa)
            # T'[p(x), p(y)] = p(T[x, y])  ->  T'[u, v] = p(T[inv u, inv v])
            tp = pa[t[np.ix_(inv, inv)]]
            num = int(np.dot(tp.reshape(-1), weights))
            if best is None or num < best:
                best = num
        out.add(best)
    return out


# ----------------------------------------------------------------------------- k = 4 capped search (supplementary)
def count_classes_capped(lhs, rhs, k, cap, node_budget=30_000):
    """Backtracking over the k*k table cells; stops after `cap` non-isomorphic models are found.
    Partial tables use -1 for unassigned cells; all ground instances are evaluated at once with numpy.
    Returns (classes_found, exhausted, nodes).  exhausted=True means the search completed."""
    nvars = max(leaves(lhs, []) + leaves(rhs, [])) + 1
    inst = np.array(list(itertools.product(range(k), repeat=nvars)), dtype=np.int64)  # (I, nvars)
    table = -np.ones((k, k), dtype=np.int64)
    perms = [np.array(p) for p in itertools.permutations(range(k))]
    weights = np.array([k ** (k * x + y) for x in range(k) for y in range(k)])
    found = set()
    nodes = 0

    def ev(term):
        if isinstance(term, tuple):
            l = ev(term[0])
            r = ev(term[1])
            ok = (l >= 0) & (r >= 0)
            out = -np.ones(len(inst), dtype=np.int64)
            out[ok] = table[l[ok], r[ok]]
            return out
        return inst[:, term]

    def consistent():
        a, b = ev(lhs), ev(rhs)
        return not np.any((a >= 0) & (b >= 0) & (a != b))

    cells = [(x, y) for x in range(k) for y in range(k)]

    def canon():
        best = None
        for pa in perms:
            inv = np.argsort(pa)
            num = int(np.dot(pa[table[np.ix_(inv, inv)]].reshape(-1), weights))
            if best is None or num < best:
                best = num
        return best

    def dfs(i):
        nonlocal nodes
        if len(found) >= cap or nodes > node_budget:
            return
        if i == len(cells):
            found.add(canon())
            return
        x, y = cells[i]
        for v in range(k):
            nodes += 1
            table[x, y] = v
            if consistent():
                dfs(i + 1)
            table[x, y] = -1
            if len(found) >= cap or nodes > node_budget:
                return

    dfs(0)
    exhausted = nodes <= node_budget and len(found) < cap
    return len(found), exhausted, nodes


def wolfram_family(n_max):
    """lhs == a with lhs over the alphabet {a, b} (all labellings), as in the figure on p. 804."""
    out = []
    for n in range(0, n_max + 1):
        for s in shapes(n):
            m = n_leaves(s)
            for lab in itertools.product((0, 1), repeat=m):
                lhs = fill(s, lab)
                if lhs == 0:
                    continue
                out.append((n, lhs, 0))
    return out


def main():
    t0 = time.time()
    family = enumerate_family(N_MAX)
    print(f"family: {len(family)} axiom systems with 1..{N_MAX} operators ({time.time()-t0:.0f}s)", file=sys.stderr)
    tables = {k: all_tables(k) for k in KS}
    rows = []
    for n, lhs, rhs in family:
        row = {"n_ops": n, "axiom": term_str(lhs) + " == " + term_str(rhs)}
        for k in KS:
            idx = models(lhs, rhs, k, tables[k])
            canon = canonical_numbers(idx, k, tables[k])
            row[f"models_k{k}"] = int(idx.size)
            row[f"classes_k{k}"] = len(canon)
            if k == 2:
                row["k2_model_set"] = " ".join(str(int(i)) for i in idx)
        m2, m3 = row["classes_k2"], row["classes_k3"]
        row["many_forms"] = m3 >= MANY_MIN
        row["single_form"] = (m2 <= 1 and m3 <= 1 and m2 + m3 >= 1)
        row["no_nontrivial_form"] = (m2 == 0 and m3 == 0)
        rows.append(row)
    print(f"k=2,3 model enumeration done ({time.time()-t0:.0f}s)", file=sys.stderr)

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with gzip.open(os.path.join(HERE, "derived", "axioms.csv.gz"), "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[c for c in rows[0].keys() if c != "k2_model_set"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    N = len(rows)
    many = sum(r["many_forms"] for r in rows)
    single = sum(r["single_form"] for r in rows)
    none = sum(r["no_nontrivial_form"] for r in rows)
    n4 = [r for r in rows if r["n_ops"] == 4]
    nand_nor = [r["axiom"] for r in rows if r["k2_model_set"] == "1 7"]
    xor_xnor = [r["axiom"] for r in rows if r["k2_model_set"] == "6 9"]

    # validation: lhs == a family, k = 2 only, up to 6 operators
    T2 = tables[2]
    val = {"count": 0, "only_6_9": 0, "only_1_7": 0, "k2_model_sets_size_le_2": {}}
    for n in range(0, VALIDATION_N_MAX + 1):
        for ls in shapes(n):
            m = n_leaves(ls)
            for lab in rgs(m):
                lhs = fill(ls, lab)
                idx = models(lhs, 0, 2, T2)
                val["count"] += 1
                key = tuple(int(i) for i in idx)
                if key == (6, 9):
                    val["only_6_9"] += 1
                if key == (1, 7):
                    val["only_1_7"] += 1
                if len(key) <= 2:
                    val["k2_model_sets_size_le_2"][str(key)] = val["k2_model_sets_size_le_2"].get(str(key), 0) + 1
    print(f"validation family: {val['count']} systems ({time.time()-t0:.0f}s)", file=sys.stderr)

    # Supplementary (post-hoc, not part of the pre-registered decision):
    # (S1) Wolfram's own family from the figure on p. 804: lhs == a, lhs over {a, b}, up to 3 operators,
    #      with k = 2, 3 exact class counts and a capped k = 4 search (stop at 3 non-isomorphic models).
    # (S2) Capped k = 4 search for the main family's systems that are not already 'many forms' at k = 3.
    supp = {"S1": [], "S2": {}}
    for n, lhs, rhs in wolfram_family(3):
        idx2 = models(lhs, rhs, 2, tables[2])
        idx3 = models(lhs, rhs, 3, tables[3])
        c2 = len(canonical_numbers(idx2, 2, tables[2]))
        c3 = len(canonical_numbers(idx3, 3, tables[3]))
        c4, done4, nodes = count_classes_capped(lhs, rhs, 4, cap=3)
        supp["S1"].append({"axiom": term_str(lhs) + " == a", "n_ops": n, "models_k2": int(idx2.size), "models_k3": int(idx3.size),
                           "classes_k2": c2, "classes_k3": c3, "classes_k4_capped3": c4, "k4_search_complete": done4})
    s1 = supp["S1"]
    s1_many = sum(1 for r in s1 if max(r["classes_k2"], r["classes_k3"], r["classes_k4_capped3"]) >= 3)
    s1_single = sum(1 for r in s1 if r["k4_search_complete"] and r["classes_k2"] <= 1 and r["classes_k3"] <= 1 and r["classes_k4_capped3"] <= 1 and (r["classes_k2"] + r["classes_k3"] + r["classes_k4_capped3"]) >= 1)
    s1_none = sum(1 for r in s1 if r["k4_search_complete"] and r["classes_k2"] + r["classes_k3"] + r["classes_k4_capped3"] == 0)
    supp["S1_summary"] = {"n": len(s1), "many_forms_any_k_le_4": s1_many, "single_form_k_le_4": s1_single, "no_nontrivial_form_k_le_4": s1_none,
                          "k4_incomplete": sum(1 for r in s1 if not r["k4_search_complete"])}
    print(f"S1 done ({time.time()-t0:.0f}s): {supp['S1_summary']}", file=sys.stderr)

    # S2 takes about 25 minutes and is only run with --k4; the default run reproduces `measured` in a few minutes.
    run_k4 = "--k4" in sys.argv
    k4_many = k4_single = k4_none = k4_incomplete = 0
    for (n, lhs, rhs), r in zip(family, rows):
        if r["many_forms"] or not run_k4:
            r["classes_k4_capped3"] = ""
            continue
        c4, done4, nodes = count_classes_capped(lhs, rhs, 4, cap=3)
        r["classes_k4_capped3"] = c4 if done4 or c4 >= 3 else f">={c4}?"
        if c4 >= 3:
            k4_many += 1
        elif not done4:
            k4_incomplete += 1
        elif r["classes_k2"] <= 1 and r["classes_k3"] <= 1 and c4 <= 1 and r["classes_k2"] + r["classes_k3"] + c4 >= 1:
            k4_single += 1
        elif r["classes_k2"] + r["classes_k3"] + c4 == 0:
            k4_none += 1
    supp["S2"] = None if not run_k4 else {"main_family_n": N, "many_forms_k_le_3": many, "additional_many_forms_at_k4": k4_many,
                  "many_forms_k_le_4_fraction": round((many + k4_many) / N, 4),
                  "single_form_k_le_4": k4_single, "single_form_k_le_4_fraction": round(k4_single / N, 4),
                  "no_nontrivial_form_k_le_4": k4_none, "k4_search_incomplete": k4_incomplete,
                  "excluding_degenerate": {"n": N - k4_none, "many_forms_fraction": round((many + k4_many) / max(1, N - k4_none), 4),
                                           "single_form_fraction": round(k4_single / max(1, N - k4_none), 4)}}
    print(f"S2 done ({time.time()-t0:.0f}s): {supp['S2']}", file=sys.stderr)
    with gzip.open(os.path.join(HERE, "derived", "axioms.csv.gz"), "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[c for c in rows[0].keys() if c != "k2_model_set"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(HERE, "derived", "supplementary.json"), "w") as f:
        json.dump(supp, f, indent=1, ensure_ascii=False)

    measured = {
        "value": round(many / N, 4),
        "unit": "fraction of axiom systems with >= 3 non-isomorphic 3-element models ('many forms')",
        "n": N,
        "uncertainty": None,
        "extra": {
            "single_form_fraction": round(single / N, 4),
            "single_form_count": single,
            "no_nontrivial_form_fraction": round(none / N, 4),
            "no_nontrivial_form_count": none,
            "many_forms_count": many,
            "n4_only": {"n": len(n4), "many_forms_fraction": round(sum(r["many_forms"] for r in n4) / len(n4), 4),
                        "single_form_fraction": round(sum(r["single_form"] for r in n4) / len(n4), 4)},
            "single_form_axioms": [(r["axiom"], r["classes_k2"], r["classes_k3"]) for r in rows if r["single_form"]][:40],
            "k2_models_exactly_nand_nor": nand_nor[:20],
            "k2_models_exactly_xor_xnor": xor_xnor[:20],
            "median_classes_k3": float(np.median([r["classes_k3"] for r in rows])),
            "validation_lhs_eq_a_k2": val,
            "supplementary_S1_wolfram_family_summary": supp["S1_summary"],
            "supplementary_S2_k4": supp["S2"],
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
