#!/usr/bin/env python3
"""Pleiotropy-matched overlap of morphogenesis (GO:0009653) and learning-or-memory (GO:0007611)
human genes, overall and within ion-channel (GO:0005216) and gap-junction (GO:0005921) genes.

Primary run excludes IEA; a labelled secondary run includes it. The null shuffles
learning-or-memory labels within strata of annotation count x INDRA CoGEx statement degree
(10,000 permutations, seed 20261101). Writes derived/measured.json and the `measured` block of
result.json (pre-registered fields are left untouched).

Usage: python3 fetch.py && python3 analysis.py
"""
import csv
import gzip
import json
import math
import os
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MORPH, LEARN, ION, GAPJ = "GO:0009653", "GO:0007611", "GO:0005216", "GO:0005921"
N_PERM, SEED, OR_THRESHOLD, P_THRESHOLD, MIN_SET = 10_000, 20261101, 2.0, 0.01, 5


def load_obo(path):
    parents, obsolete, cur = defaultdict(set), set(), None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("["):
                cur = None
                continue
            if line.startswith("id: GO:"):
                cur = line[4:]
            elif cur is None:
                continue
            elif line.startswith("is_a: "):
                parents[cur].add(line[6:16])
            elif line.startswith("relationship: part_of "):
                parents[cur].add(line[22:32])
            elif line == "is_obsolete: true":
                obsolete.add(cur)
    return parents, obsolete


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


def load_hgnc():
    genes, uniprot_to_hgnc = [], {}
    with open(os.path.join(DATA, "hgnc_protein_coding.tsv")) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["status"] != "Approved":
                continue
            hid = row["hgnc_id"].replace("HGNC:", "hgnc:")
            genes.append(hid)
            for acc in filter(None, row["uniprot_ids"].split("|")):
                uniprot_to_hgnc.setdefault(acc.strip(), set()).add(hid)
    return genes, uniprot_to_hgnc


def load_gaf(uniprot_to_hgnc, obsolete, known_terms):
    rows, stats = [], defaultdict(int)
    with gzip.open(os.path.join(DATA, "goa_human.gaf.gz"), "rt") as f:
        for line in f:
            if line.startswith("!"):
                continue
            c = line.rstrip("\n").split("\t")
            stats["lines"] += 1
            if "NOT" in c[3].split("|"):
                stats["not_qualified"] += 1
                continue
            if c[4] in obsolete or c[4] not in known_terms:
                stats["obsolete_or_unknown_term"] += 1
                continue
            hids = uniprot_to_hgnc.get(c[1]) if c[0] == "UniProtKB" else None
            if not hids:
                stats["unmapped_to_hgnc_protein_coding"] += 1
                continue
            for h in hids:
                rows.append((h, c[4], c[6]))
    return rows, dict(stats)


def odds_ratio(a, m, l, n):
    b, c, d = m - a, l - a, n - m - l + a
    if min(a, b, c, d) == 0:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    return (a * d) / (b * c), math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)


def strata(df, q):
    ann = pd.qcut(df["ann"].rank(method="average"), q, labels=False, duplicates="drop")
    deg = pd.qcut(df["deg"].rank(method="average"), q, labels=False, duplicates="drop")
    return (ann * q + deg).to_numpy()


def endpoint(df, q, rng, label):
    n, m, l = len(df), int(df["M"].sum()), int(df["L"].sum())
    a = int((df["M"] & df["L"]).sum())
    out = {"endpoint": label, "n": n, "morphogenesis_genes": m, "learning_or_memory_genes": l, "overlap": a}
    if m < MIN_SET or l < MIN_SET:
        out.update(underpowered=True, passes=False)
        return out
    obs_or, se = odds_ratio(a, m, l, n)
    s = strata(df, q)
    mflag, lflag = df["M"].to_numpy(), df["L"].to_numpy()
    null_overlap = np.zeros(N_PERM, dtype=np.int64)
    for st in np.unique(s):
        idx = np.where(s == st)[0]
        ls = int(lflag[idx].sum())
        if ls == 0:
            continue
        ms = mflag[idx].astype(np.int64)
        for start in range(0, N_PERM, 1000):
            k = min(1000, N_PERM - start)
            pick = rng.random((k, len(idx))).argsort(axis=1)[:, :ls]
            null_overlap[start:start + k] += ms[pick].sum(axis=1)
    null_or = np.array([odds_ratio(int(x), m, l, n)[0] for x in null_overlap])
    p = (1 + int((null_or >= obs_or - 1e-12).sum())) / (1 + N_PERM)
    out.update(
        underpowered=False,
        odds_ratio=round(obs_or, 4),
        ci95=[round(math.exp(math.log(obs_or) - 1.96 * se), 4), round(math.exp(math.log(obs_or) + 1.96 * se), 4)],
        expected_overlap_independence=round(m * l / n, 2),
        fisher_one_sided_p=float(f"{fisher_exact([[a, m - a], [l - a, n - m - l + a]], alternative='greater')[1]:.3e}"),
        strata=int(len(np.unique(s))),
        null_overlap_mean=round(float(null_overlap.mean()), 2),
        null_or_median=round(float(np.median(null_or)), 4),
        null_or_p99=round(float(np.percentile(null_or, 99)), 4),
        or_over_null_median=round(obs_or / float(np.median(null_or)), 4),
        permutation_p=float(f"{p:.4g}"),
        passes=bool(obs_or > OR_THRESHOLD and p < P_THRESHOLD),
    )
    return out


def run(gene_terms_all, genes, anc, deg, exclude_iea, rng):
    direct = defaultdict(set)
    for h, t, ev in gene_terms_all:
        if exclude_iea and ev == "IEA":
            continue
        direct[h].add(t)
    recs = []
    for h in genes:
        prop = set()
        for t in direct.get(h, ()):
            prop |= anc(t)
        recs.append((h, len(direct.get(h, ())), deg.get(h, 0), MORPH in prop, LEARN in prop, ION in prop, GAPJ in prop))
    df = pd.DataFrame(recs, columns=["gene", "ann", "deg", "M", "L", "ION", "GJ"])
    res = {
        "genes_with_any_annotation": int((df["ann"] > 0).sum()),
        "E1_all_protein_coding": endpoint(df, 5, rng, "E1 all human protein-coding genes"),
        "E2_ion_channel_GO_0005216": endpoint(df[df["ION"]].reset_index(drop=True), 3, rng, "E2 ion-channel subset"),
        "E3_gap_junction_GO_0005921": endpoint(df[df["GJ"]].reset_index(drop=True), 3, rng, "E3 gap-junction subset"),
    }
    e1, e2, e3 = (res[k] for k in ("E1_all_protein_coding", "E2_ion_channel_GO_0005216", "E3_gap_junction_GO_0005921"))
    res["verdict_by_preregistered_rule"] = (
        "refutes" if not e1["passes"] else "supports" if (e2["passes"] and e3["passes"]) else "mixed")
    return res


def main():
    parents, obsolete = load_obo(os.path.join(DATA, "go-basic.obo"))
    known = set(parents) | {t for ps in parents.values() for t in ps}
    with open(os.path.join(DATA, "go-basic.obo")) as f:
        known |= {line[4:14] for line in f if line.startswith("id: GO:")}
    anc = ancestors_fn(parents)
    genes, u2h = load_hgnc()
    rows, gaf_stats = load_gaf(u2h, obsolete, known)
    deg_df = pd.read_csv(os.path.join(DATA, "indra_degree.tsv"), sep="\t", dtype={"indra_statements": "Int64"})
    missing = int(deg_df["indra_statements"].isna().sum())
    deg = {r.hgnc_id: (0 if pd.isna(r.indra_statements) else int(r.indra_statements)) for r in deg_df.itertuples()}
    rng = np.random.default_rng(SEED)
    measured = {
        "universe_hgnc_protein_coding": len(genes),
        "gaf": gaf_stats,
        "indra": {"genes_queried": len(deg_df), "genes_absent_from_cogex_set_to_0": missing,
                  "median_statements": float(np.median(list(deg.values())))},
        "primary_iea_excluded": run(rows, genes, anc, deg, True, rng),
        "secondary_iea_included_LABELLED": run(rows, genes, anc, deg, False, rng),
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(measured, f, indent=1)
    e1 = measured["primary_iea_excluded"]["E1_all_protein_coding"]
    result_path = os.path.join(HERE, "result.json")
    result = json.load(open(result_path))
    result["measured"] = {
        "value": e1["odds_ratio"],
        "unit": "odds ratio, GO:0009653 x GO:0007611 human protein-coding genes, IEA excluded",
        "n": e1["n"],
        "uncertainty": f"95% CI {e1['ci95'][0]}-{e1['ci95'][1]}; matched-permutation p = {e1['permutation_p']}",
        "extra": measured,
    }
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(measured, indent=1))


if __name__ == "__main__":
    main()
