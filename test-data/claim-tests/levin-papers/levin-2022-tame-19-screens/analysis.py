#!/usr/bin/env python3
"""Test of levin-2022-tame-19, second half: memory genes appear in genetic studies of cancer,
regeneration and embryogenesis.

Mouse learning-or-memory genes (GO:0007611, experimental evidence, as in the first-half test in
../levin-2022-tame-19) against MGI mutant phenotypes (MGI_GenePheno.rpt) for neoplasm,
regeneration and embryo development / embryonic lethality. Mantel-Haenszel odds ratios
stratified by phenotyping depth; thresholds are in result.json.

Run: python3 analysis.py   (needs numpy; downloads data/ via fetch.py if missing)
"""
import importlib.util
import json
import math
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
_spec = importlib.util.spec_from_file_location(
    "first_half", os.path.join(HERE, "..", "levin-2022-tame-19", "analysis.py"))
first_half = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(first_half)
EXCLUDE_ROOTS, EXPERIMENTAL, LEARN = first_half.EXCLUDE_ROOTS, first_half.EXPERIMENTAL, first_half.LEARN
ancestors_fn, fisher_greater, odds_ratio = first_half.ancestors_fn, first_half.fisher_greater, first_half.odds_ratio
read_gaf, read_obo, table = first_half.read_gaf, first_half.read_obo, first_half.table

MP_LEARN = "MP:0002063"
OUTCOMES = {
    "cancer": ["MP:0002006"],
    "embryogenesis": ["MP:0001672", "MP:0008762"],
}


def read_mp(path):
    parents, names, obsolete = defaultdict(set), {}, set()
    term = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("["):
            term = None if line != "[Term]" else ""
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
        elif key == "is_obsolete" and val == "true":
            obsolete.add(term)
    for t in obsolete:
        names.pop(t, None)
    return parents, names


def read_genepheno(path):
    pheno = defaultdict(set)
    for line in open(path, encoding="utf-8"):
        c = line.rstrip("\n").split("\t")
        if len(c) < 7 or not c[4].startswith("MP:"):
            continue
        for gene in c[6].split("|"):
            if gene.startswith("MGI:"):
                pheno[gene].add(c[4])
    return pheno


def deciles(genes, depth):
    order = sorted(genes, key=lambda g: (depth[g], g))
    return {g: (i * 10) // len(order) for i, g in enumerate(order)}


def mantel_haenszel(x, y, universe, stratum):
    num = den = sa = se = sv = 0.0
    for s in range(10):
        U = {g for g in universe if stratum[g] == s}
        n = len(U)
        if n < 2:
            continue
        a, b, c, d = table(x & U, y & U, U)
        num += a * d / n
        den += b * c / n
        n1, m1 = a + b, a + c
        sa += a
        se += n1 * m1 / n
        sv += n1 * (n - n1) * m1 * (n - m1) / (n * n * (n - 1))
    z = (sa - se - 0.5) / math.sqrt(sv) if sv else 0.0
    return (num / den if den else None), 0.5 * math.erfc(z / math.sqrt(2)), int(sa), round(se, 2)


def main():
    if not all(os.path.exists(os.path.join(DATA, f)) for f in ("go-basic.obo", "mgi.gaf.gz", "mp.obo", "MGI_GenePheno.rpt")):
        import fetch
        fetch.main()

    go_parents, go_ns, _, go_alt = read_obo(os.path.join(DATA, "go-basic.obo"))
    go_anc = ancestors_fn(go_parents)
    exp_bp, any_terms = defaultdict(set), defaultdict(set)
    for gene, term, ev, aspect in read_gaf(os.path.join(DATA, "mgi.gaf.gz"), go_alt):
        if term not in go_ns:
            continue
        any_terms[gene].add(term)
        if aspect == "P" and ev in EXPERIMENTAL:
            exp_bp[gene].add(term)

    mp_parents, mp_names = read_mp(os.path.join(DATA, "mp.obo"))
    mp_anc = ancestors_fn(mp_parents)
    pheno = read_genepheno(os.path.join(DATA, "MGI_GenePheno.rpt"))
    pheno = {g: {t for t in ts if t in mp_names} for g, ts in pheno.items()}
    pheno = {g: ts for g, ts in pheno.items() if ts}

    regen_roots = sorted(t for t, n in mp_names.items() if "regenerat" in n.lower())
    outcomes = dict(OUTCOMES, regeneration=regen_roots)

    universe = set(pheno) & set(exp_bp)
    go_closure = {g: set().union(*(go_anc(t) for t in exp_bp[g])) for g in universe}
    mp_closure = {g: set().union(*(mp_anc(t) for t in pheno[g])) for g in universe}
    excluded = {g for g in universe if any(r in go_anc(t) for t in any_terms[g] for r in EXCLUDE_ROOTS)}

    memory_go = {g for g in universe if LEARN in go_closure[g]}
    memory_mp = {g for g in universe if MP_LEARN in mp_closure[g]}
    outcome_sets = {k: {g for g in universe if mp_closure[g] & set(roots)} for k, roots in outcomes.items()}

    mp_depth = {g: len(pheno[g]) for g in universe}
    go_depth = {g: len(exp_bp[g]) for g in universe}

    def analyse(memory, U, depth):
        strat = deciles(U, depth)
        res = {}
        for k, Y in outcome_sets.items():
            m, y = memory & U, Y & U
            a, b, c, d = table(m, y, U)
            mh, p, obs, exp = mantel_haenszel(m, y, U, strat)
            res[k] = {"memory_genes": len(m), "outcome_genes": len(y), "overlap": a,
                      "odds_ratio": round(odds_ratio(a, b, c, d), 4),
                      "fisher_p_one_sided": float(f"{fisher_greater(a, b, c, d):.3e}"),
                      "mh_odds_ratio": round(mh, 4) if mh else None,
                      "cmh_p_one_sided": float(f"{p:.3e}"),
                      "cmh_observed_expected": [obs, exp]}
        return res

    primary = analyse(memory_go, universe, mp_depth)
    passed = {k: v["mh_odds_ratio"] is not None and v["mh_odds_ratio"] > 1.5 and v["cmh_p_one_sided"] < 1e-3
              for k, v in primary.items()}
    failed = {k: v["mh_odds_ratio"] is None or v["mh_odds_ratio"] <= 1.2 or v["cmh_p_one_sided"] >= 0.05
              for k, v in primary.items()}
    if all(passed.values()):
        verdict = "supports"
    elif sum(failed.values()) >= 2:
        verdict = "refutes"
    else:
        verdict = "mixed"

    out = {
        "value": primary["embryogenesis"]["mh_odds_ratio"],
        "unit": "Mantel-Haenszel odds ratio (phenotyping-depth deciles), GO learning-or-memory genes vs MP embryogenesis phenotype genes; cancer and regeneration in extra",
        "n": len(universe),
        "uncertainty": f"one-sided CMH p = {primary['embryogenesis']['cmh_p_one_sided']:.3e}",
        "extra": {
            "universe_genes_with_mp_and_experimental_bp": len(universe),
            "regeneration_mp_roots": [{"id": t, "name": mp_names[t]} for t in regen_roots],
            "primary_go_memory_mp_depth": primary,
            "secondary_go_memory_mp_depth_channel_synaptic_excluded": analyse(memory_go, universe - excluded, mp_depth),
            "secondary_go_memory_go_depth": analyse(memory_go, universe, go_depth),
            "secondary_mp_memory_mp_depth": analyse(memory_mp, universe, mp_depth),
            "criteria": {"passed": passed, "failed": failed},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
