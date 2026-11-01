#!/usr/bin/env python3
"""Test of levin-2025-wisdom-08: numerous channelopathies produce patterning defects.

Human disease genes from HPO genes_to_phenotype. Ion-channel genes: GO:0005216 ion channel
activity or descendant (human GOA, any evidence, NOT lines dropped). Patterning: HPO face/limb
malformation branches (below). Nervous system: HP:0000707. Count channel genes with both, and a
Mantel-Haenszel odds ratio (patterning, channel vs non-channel) over deciles of each gene's number
of distinct phenotypic-abnormality terms, with a one-sided CMH test. Thresholds are in result.json.

Needs: numpy, scipy, requests (fetch.py). Run: python3 analysis.py   (downloads data/ if missing)
"""
import gzip
import json
import math
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ION_CHANNEL = "GO:0005216"
PATTERNING = {
    "HP:0001999": "Abnormal facial shape",
    "HP:0000202": "Orofacial cleft",
    "HP:0001159": "Syndactyly",
    "HP:0010442": "Polydactyly",
    "HP:0009815": "Aplasia/hypoplasia of the extremities",
}
NERVOUS = "HP:0000707"
PHENOTYPIC_ABNORMALITY = "HP:0000118"


def read_obo(path):
    parents, alt, names, obsolete = defaultdict(set), {}, {}, set()
    term = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("["):
            term = "" if line == "[Term]" else None
            continue
        if term is None or ": " not in line:
            continue
        key, val = line.split(": ", 1)
        if key == "id":
            term = val
        elif key == "name":
            names[term] = val
        elif key == "is_a":
            parents[term].add(val.split()[0])
        elif key == "relationship" and val.startswith("part_of "):
            parents[term].add(val.split()[1])
        elif key == "alt_id":
            alt[val] = term
        elif key == "is_obsolete" and val == "true":
            obsolete.add(term)
    return parents, alt, names, obsolete


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


def cmh(tables):
    """Mantel-Haenszel OR and one-sided (greater) CMH z test, no continuity correction."""
    num = den = s_a = s_e = s_v = 0.0
    for a, b, c, d in tables:
        n = a + b + c + d
        if n < 2:
            continue
        num += a * d / n
        den += b * c / n
        r1, c1 = a + b, a + c
        s_a += a
        s_e += r1 * c1 / n
        s_v += r1 * (n - r1) * c1 * (n - c1) / (n * n * (n - 1))
    z = (s_a - s_e) / math.sqrt(s_v) if s_v > 0 else float("nan")
    return (num / den if den else float("inf")), z, float(stats.norm.sf(z)), float(stats.norm.cdf(z))


def main():
    need = ("genes_to_phenotype.txt", "hp.obo", "go-basic.obo", "goa_human.gaf.gz")
    if not all(os.path.exists(os.path.join(DATA, f)) for f in need):
        import fetch
        fetch.main()

    hpar, halt, hnames, hobs = read_obo(os.path.join(DATA, "hp.obo"))
    hanc = ancestors_fn(hpar)
    gpar, galt, _, gobs = read_obo(os.path.join(DATA, "go-basic.obo"))
    ganc = ancestors_fn(gpar)

    channels = set()
    with gzip.open(os.path.join(DATA, "goa_human.gaf.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("!"):
                continue
            c = line.rstrip("\n").split("\t")
            if "NOT" in c[3].split("|") or c[8] != "F":
                continue
            t = galt.get(c[4], c[4])
            if t not in gobs and ION_CHANNEL in ganc(t):
                channels.add(c[2])

    gene_terms = defaultdict(set)
    with open(os.path.join(DATA, "genes_to_phenotype.txt"), encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            t = halt.get(c[2], c[2])
            if t in hobs or PHENOTYPIC_ABNORMALITY not in hanc(t):
                continue
            gene_terms[c[1]].add(t)

    genes = sorted(gene_terms)
    closure = {g: set().union(*(hanc(t) for t in gene_terms[g])) for g in genes}
    patt = {g for g in genes if closure[g] & PATTERNING.keys()}
    nerv = {g for g in genes if NERVOUS in closure[g]}
    chan = {g for g in genes if g in channels}
    both = sorted(chan & patt & nerv)
    by_branch = {f"{k} {v}": sorted(g for g in chan if k in closure[g]) for k, v in PATTERNING.items()}

    a = len(chan & patt)
    b = len(chan - patt)
    c = len(patt - chan)
    d = len(genes) - a - b - c
    crude_or = (a * d) / (b * c)
    fisher_or, fisher_p_two = stats.fisher_exact([[a, b], [c, d]])

    ordered = sorted(genes, key=lambda g: (len(gene_terms[g]), g))
    strata, tables = [], []
    for s in range(10):
        U = ordered[s * len(ordered) // 10:(s + 1) * len(ordered) // 10]
        U = set(U)
        sa = len(U & chan & patt)
        sb = len(U & chan) - sa
        sc = len(U & patt) - sa
        sd = len(U) - sa - sb - sc
        tables.append((sa, sb, sc, sd))
        depth = [len(gene_terms[g]) for g in U]
        strata.append({"stratum": s, "n": len(U), "terms_min_max": [min(depth), max(depth)], "table_a_b_c_d": [sa, sb, sc, sd]})
    mh_or, z, p_greater, p_less = cmh(tables)

    a2 = len(chan & patt & nerv)
    frac_chan_patt = a / len(chan)
    frac_non_patt = c / (len(genes) - len(chan))
    chan_nerv = chan & nerv
    frac_chan_nerv_patt = len(chan_nerv & patt) / len(chan_nerv) if chan_nerv else None
    non_nerv = nerv - chan
    frac_non_nerv_patt = len(non_nerv & patt) / len(non_nerv)

    pass_a = len(both) >= 20
    pass_b = mh_or > 1.2 and p_greater < 0.05
    depleted = mh_or < 0.8 and p_less < 0.05
    if pass_a and pass_b:
        verdict = "supports"
    elif len(both) < 10 or (depleted and len(both) < 20):
        verdict = "refutes"
    else:
        verdict = "mixed"

    out = {
        "value": len(both),
        "unit": "ion-channel disease genes with both a face/limb patterning phenotype and a nervous-system phenotype in HPO",
        "n": len(chan),
        "uncertainty": f"depth-stratified Mantel-Haenszel OR = {mh_or:.3f}, one-sided CMH p(enrichment) = {p_greater:.3g}",
        "extra": {
            "hpo_genes": len(genes),
            "go_ion_channel_genes_any_evidence": len(channels),
            "ion_channel_hpo_genes": len(chan),
            "ion_channel_genes_with_patterning": a,
            "ion_channel_genes_with_patterning_and_nervous": a2,
            "genes_with_both": both,
            "ion_channel_genes_by_patterning_branch": by_branch,
            "fraction_patterning_channel": round(frac_chan_patt, 4),
            "fraction_patterning_non_channel": round(frac_non_patt, 4),
            "fraction_patterning_among_nervous_channel_genes": round(frac_chan_nerv_patt, 4) if frac_chan_nerv_patt is not None else None,
            "fraction_patterning_among_nervous_non_channel_genes": round(frac_non_nerv_patt, 4),
            "crude_table_a_b_c_d": [a, b, c, d],
            "crude_odds_ratio": round(crude_or, 4),
            "fisher_two_sided_p": float(f"{fisher_p_two:.3g}"),
            "mantel_haenszel_odds_ratio": round(mh_or, 4),
            "cmh_z": round(z, 3),
            "cmh_p_one_sided_enrichment": float(f"{p_greater:.3g}"),
            "cmh_p_one_sided_depletion": float(f"{p_less:.3g}"),
            "strata": strata,
            "median_terms_channel_vs_non_channel": [float(np.median([len(gene_terms[g]) for g in chan])),
                                                   float(np.median([len(gene_terms[g]) for g in genes if g not in chan]))],
            "criteria": {"a_ge_20_genes": pass_a, "b_mh_or_gt_1.2_p_lt_0.05": bool(pass_b), "depleted_mh_or_lt_0.8_p_lt_0.05": bool(depleted)},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
