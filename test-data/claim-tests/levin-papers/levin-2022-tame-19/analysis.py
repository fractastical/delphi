#!/usr/bin/env python3
"""Test of levin-2022-tame-19: genes for morphogenesis and for learning and memory overlap
significantly and specifically.

Mouse genes with experimental GO biological-process annotations (MGI GAF), after removing
ion-channel, gap-junction and neurotransmission genes. Overlap of GO:0007611 learning or
memory with GO:0009653 anatomical structure morphogenesis (both with is_a/part_of
descendants): Fisher exact test, Mantel-Haenszel odds ratio stratified by annotation depth,
and percentile among size-matched control BP terms. Thresholds are in result.json.

Run: python3 analysis.py   (needs numpy; downloads data/ via fetch.py if missing)
"""
import gzip
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
LEARN, MORPH = "GO:0007611", "GO:0009653"
EXCLUDE_ROOTS = ["GO:0005216", "GO:0005243", "GO:0005921", "GO:0007268", "GO:0001505", "GO:0030594"]
EXPERIMENTAL = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP"}
SIZE_FACTOR = 1.5


def read_obo(path):
    parents, namespace, names, alt = defaultdict(set), {}, {}, {}
    term = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("["):
            term = {} if line == "[Term]" else None
            continue
        if term is None or ": " not in line:
            continue
        key, val = line.split(": ", 1)
        if key == "id":
            term["id"] = val
        elif key == "name":
            names[term["id"]] = val
        elif key == "namespace":
            namespace[term["id"]] = val
        elif key == "is_a":
            parents[term["id"]].add(val.split()[0])
        elif key == "relationship" and val.startswith("part_of "):
            parents[term["id"]].add(val.split()[1])
        elif key == "alt_id":
            alt[val] = term["id"]
        elif key == "is_obsolete" and val == "true":
            namespace.pop(term["id"], None)
    return parents, namespace, names, alt


def ancestors_fn(parents):
    memo = {}

    def anc(t):
        if t not in memo:
            out = {t}
            for p in parents.get(t, ()):
                out |= anc(p)
            memo[t] = out
        return memo[t]
    return anc


def read_gaf(path, alt):
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("!"):
                continue
            c = line.rstrip("\n").split("\t")
            if "NOT" in c[3].split("|"):
                continue
            rows.append((c[1], alt.get(c[4], c[4]), c[6], c[8]))
    return rows


def log_hyper_pmf(k, K, n, N):
    lc = lambda a, b: math.lgamma(a + 1) - math.lgamma(b + 1) - math.lgamma(a - b + 1)
    return lc(K, k) + lc(N - K, n - k) - lc(N, n)


def fisher_greater(a, b, c, d):
    """P(X >= a) for the 2x2 table [[a, b], [c, d]] under the hypergeometric null."""
    K, n, N = a + b, a + c, a + b + c + d
    terms = [log_hyper_pmf(k, K, n, N) for k in range(a, min(K, n) + 1)]
    m = max(terms)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in terms))


def odds_ratio(a, b, c, d):
    if 0 in (a, b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    return a * d / (b * c)


def table(x, y, universe):
    a = len(x & y)
    b = len(x - y)
    c = len(y - x)
    d = len(universe) - a - b - c
    return a, b, c, d


def main():
    if not all(os.path.exists(os.path.join(DATA, f)) for f in ("go-basic.obo", "mgi.gaf.gz")):
        import fetch
        fetch.main()
    parents, namespace, names, alt = read_obo(os.path.join(DATA, "go-basic.obo"))
    anc = ancestors_fn(parents)
    rows = read_gaf(os.path.join(DATA, "mgi.gaf.gz"), alt)

    exp_bp = defaultdict(set)
    any_terms = defaultdict(set)
    for gene, term, ev, aspect in rows:
        if term not in namespace:
            continue
        any_terms[gene].add(term)
        if aspect == "P" and ev in EXPERIMENTAL:
            exp_bp[gene].add(term)

    excluded = {g for g, ts in any_terms.items() if any(r in anc(t) for t in ts for r in EXCLUDE_ROOTS)}
    all_exp_genes = set(exp_bp)
    universe = all_exp_genes - excluded

    closure = {g: set().union(*(anc(t) for t in exp_bp[g])) for g in all_exp_genes}
    term_genes = defaultdict(set)
    for g in universe:
        for t in closure[g]:
            term_genes[t].add(g)

    L, M = term_genes[LEARN], term_genes[MORPH]
    a, b, c, d = table(L, M, universe)
    or_main = odds_ratio(a, b, c, d)
    p_main = fisher_greater(a, b, c, d)

    L_all = {g for g in all_exp_genes if LEARN in closure[g]}
    M_all = {g for g in all_exp_genes if MORPH in closure[g]}
    a0, b0, c0, d0 = table(L_all, M_all, all_exp_genes)

    genes = sorted(universe, key=lambda g: (len(exp_bp[g]), g))
    stratum = {g: (i * 10) // len(genes) for i, g in enumerate(genes)}
    num = den = 0.0
    strata = []
    for s in range(10):
        U = {g for g in genes if stratum[g] == s}
        sa, sb, sc, sd = table(L & U, M & U, U)
        n = len(U)
        num += sa * sd / n
        den += sb * sc / n
        depth = [len(exp_bp[g]) for g in U]
        strata.append({"stratum": s, "n": n, "bp_annotations_min_max": [min(depth), max(depth)],
                       "table_a_b_c_d": [sa, sb, sc, sd]})
    or_mh = num / den if den else None

    related = anc(LEARN) | anc(MORPH)
    lo, hi = len(L) / SIZE_FACTOR, len(L) * SIZE_FACTOR
    controls = []
    for t, gs in term_genes.items():
        if namespace.get(t) != "biological_process" or t in related:
            continue
        if LEARN in anc(t) or MORPH in anc(t):
            continue
        if not lo <= len(gs) <= hi:
            continue
        controls.append((t, len(gs), odds_ratio(*table(gs, M, universe))))
    ctrl_or = np.array([o for _, _, o in controls])
    pct = float((ctrl_or < or_main).mean() * 100) if len(ctrl_or) else None
    q50, q75 = (float(np.percentile(ctrl_or, 50)), float(np.percentile(ctrl_or, 75))) if len(ctrl_or) else (None, None)

    pass_a = or_main > 1.5 and p_main < 1e-3
    pass_b = or_mh is not None and or_mh > 1.5
    pass_c = q75 is not None and or_main > q75
    fail = or_main <= 1.2 or p_main >= 0.05 or (or_mh is not None and or_mh <= 1.2) or (q50 is not None and or_main <= q50)
    verdict = "supports" if (pass_a and pass_b and pass_c) else ("refutes" if fail else "mixed")

    top_controls = sorted(controls, key=lambda x: (-x[2], x[0]))[:15]
    out = {
        "value": round(or_main, 4),
        "unit": "odds ratio, learning-or-memory vs anatomical-structure-morphogenesis gene sets (mouse, experimental BP annotations, channel/synaptic genes excluded)",
        "n": len(universe),
        "uncertainty": f"one-sided Fisher exact p = {p_main:.3e}",
        "extra": {
            "genes_with_experimental_bp": len(all_exp_genes),
            "excluded_channel_gap_junction_neurotransmission_genes": len(all_exp_genes & excluded),
            "universe": len(universe),
            "learning_or_memory_genes": len(L),
            "morphogenesis_genes": len(M),
            "overlap": a,
            "table_a_b_c_d": [a, b, c, d],
            "expected_overlap": round(len(L) * len(M) / len(universe), 2),
            "fisher_p_one_sided": float(f"{p_main:.3e}"),
            "odds_ratio_before_exclusion": round(odds_ratio(a0, b0, c0, d0), 4),
            "overlap_before_exclusion": a0,
            "mantel_haenszel_odds_ratio_by_annotation_depth_decile": round(or_mh, 4) if or_mh else None,
            "strata": strata,
            "control_terms": len(controls),
            "control_size_range": [math.ceil(lo), math.floor(hi)],
            "control_odds_ratio_median": round(q50, 4) if q50 else None,
            "control_odds_ratio_p75": round(q75, 4) if q75 else None,
            "percentile_among_controls": round(pct, 2) if pct is not None else None,
            "top_control_terms_by_odds_ratio": [{"id": t, "name": names.get(t), "genes": n, "odds_ratio": round(o, 3)}
                                                for t, n, o in top_controls],
            "criteria": {"a_fisher_or_gt_1.5_p_lt_0.001": pass_a, "b_mh_or_gt_1.5": pass_b,
                         "c_above_control_p75": pass_c, "fail_condition_met": fail},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
