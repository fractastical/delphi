#!/usr/bin/env python3
"""Honey-bee queens mother workers and new queens (aristotle-ga03-21).

Microsatellite genotypes from Withrow and Tarpy 2018, Figshare 6805307.
"""
import os
import sys

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import fetch, load_result, write_result

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULT = os.path.join(HERE, "result.json")
API = "https://api.figshare.com/v2/articles/6805307"
FILE_URL = "https://ndownloader.figshare.com/files/12376838"


def allele(value):
    if pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number == 0:
        return None
    return int(round(number))


def parse_colony(df):
    header = queen = None
    for i, row in df.iterrows():
        if header is None and isinstance(row[1], str):
            header = i
            continue
        if header is not None and queen is None and allele(row[1]) is not None:
            queen = i
            break
    loci = []
    col = 1
    while col < df.shape[1]:
        name = df.iloc[header, col]
        if isinstance(name, str):
            loci.append((name, col, col + 1))
        col += 2
    mother = {name: (allele(df.iloc[queen, a]), allele(df.iloc[queen, b])) for name, a, b in loci}
    section = None
    groups = {"queen_caste": [], "worker": []}
    for _, row in df.iterrows():
        label = row[0]
        if isinstance(label, str) and "split" in label.lower():
            section = "queen_caste"
            continue
        if isinstance(label, str) and label.lower().startswith("worker"):
            section = "worker"
            continue
        if section in groups and isinstance(label, str) and any(ch.isdigit() for ch in label):
            geno = {name: (allele(row[a]), allele(row[b])) for name, a, b in loci}
            groups[section].append(geno)
    return mother, groups


def compatible(mother, geno):
    scored = 0
    for locus, (qa, qb) in mother.items():
        maternal = [x for x in (qa, qb) if x is not None]
        offspring = [x for x in geno[locus] if x is not None]
        if not maternal or not offspring:
            continue
        scored += 1
        if not any(o in maternal for o in offspring):
            return False
    return scored >= 1


def main():
    os.makedirs(DATA, exist_ok=True)
    meta_api = fetch(API, os.path.join(DATA, "figshare-6805307.json"))
    meta_api["label"] = "Figshare article metadata"
    article = requests.get(API, timeout=60, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
    xlsx = fetch(FILE_URL, os.path.join(DATA, "pone.0199124.s001.xlsx"))
    xlsx["label"] = "Withrow and Tarpy 2018 sample genotypes"
    book = pd.ExcelFile(os.path.join(DATA, "pone.0199124.s001.xlsx"))
    colonies = []
    for sheet in book.sheet_names:
        if sheet == "Sheet1":
            continue
        mother, groups = parse_colony(pd.read_excel(book, sheet_name=sheet, header=None))
        n_q = len(groups["queen_caste"])
        n_w = len(groups["worker"])
        ok_q = sum(1 for g in groups["queen_caste"] if compatible(mother, g))
        ok_w = sum(1 for g in groups["worker"] if compatible(mother, g))
        qualifies = n_w >= 5 and n_q >= 3
        both = qualifies and (ok_w / n_w) >= 0.80 and (ok_q / n_q) >= 0.80
        colonies.append({
            "colony": sheet,
            "n_workers": n_w,
            "n_queen_caste": n_q,
            "workers_compatible": ok_w,
            "queen_caste_compatible": ok_q,
            "worker_fraction": round(ok_w / n_w, 4) if n_w else None,
            "queen_caste_fraction": round(ok_q / n_q, 4) if n_q else None,
            "qualifies": qualifies,
            "both_castes_at_least_80_percent": both,
            "n_loci": len(mother),
        })
    qualifying = [c for c in colonies if c["qualifies"]]
    n_pass = sum(1 for c in qualifying if c["both_castes_at_least_80_percent"])
    if not qualifying:
        verdict, reason = "inconclusive", "underpowered"
    elif n_pass > len(qualifying) / 2:
        verdict, reason = "supports", None
    elif n_pass == 0 and all(
        c["workers_compatible"] == 0 or c["queen_caste_compatible"] == 0 for c in qualifying
    ):
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    confidence = {"supports": 0.84, "refutes": 0.7, "mixed": 0.6, "inconclusive": 0.35}[verdict]
    payload = {
        "datasets": [{
            "id": "figshare-6805307-withrow-tarpy-2018-sample-genotypes",
            "name": article.get("title") or "Withrow and Tarpy 2018 honey-bee sample genotypes",
            "landing_url": "https://plos.figshare.com/articles/dataset/Cryptic_royal_subfamilies_in_honey_bee_i_Apis_mellifera_i_colonies/6805307",
            "doi": "10.1371/journal.pone.0199124",
            "version": "figshare 6805307",
            "license": (article.get("license") or {}).get("name"),
            "files": [meta_api, xlsx],
            "role": "observed queen genotypes and daughter-queen and worker microsatellites",
        }],
        "method": (
            "Each colony sheet states the queen's allele pair at each microsatellite locus, then "
            "lists daughter queens under 'Queen genotypes split A/B' and workers under 'Worker genotypes'. "
            "An offspring is compatible when every locus with a called allele shares at least one allele "
            "with that queen. A zero allele is treated as missing. A colony qualifies with at least 5 workers "
            "and 3 daughter queens, and passes when both castes are at least 80 percent compatible."
        ),
        "measured": {
            "value": n_pass,
            "unit": "qualifying colonies in which the queen is compatible with at least 80 percent of workers and of daughter queens",
            "n": len(qualifying),
            "uncertainty": None,
            "extra": {"colonies": colonies},
        },
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "headline": (
            f"In {n_pass} of {len(qualifying)} genotyped honey-bee colonies, the queen's alleles fit "
            f"at least 80 percent of both the workers and the daughter queens."
        ),
        "caveats": [
            "Daughter queens are the rows under 'Queen genotypes split', the new queens in this supplement, not the mother.",
            "Colony 5 is included and does not meet the 80 percent bar. The verdict uses the pre-registered majority rule.",
            "Compatibility is maternal allele sharing. It does not identify which drone fathered each bee.",
            "The Animal Diversity Web account was not needed because the genotype table contains both castes.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, n_pass, len(qualifying))


if __name__ == "__main__":
    main()
