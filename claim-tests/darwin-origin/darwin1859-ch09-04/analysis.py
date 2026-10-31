#!/usr/bin/env python3
"""Test darwin1859-ch09-04: wholly soft-bodied organisms are not preserved; fossil record biased to hard parts.

Data: Paleobiology Database occs/list record counts (body fossils) per phylum; GBIF backbone accepted
species counts per phylum (total minus flagged extinct = living).
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PBDB = "https://paleobiodb.org/data1.2"
GBIF = "https://api.gbif.org/v1"
BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
SOFT = ["Ctenophora", "Platyhelminthes", "Nemertea", "Chaetognatha", "Priapulida", "Onychophora", "Nematoda",
        "Nematomorpha", "Xenacoelomorpha", "Gastrotricha", "Placozoa", "Rotifera", "Tardigrada"]
MINERALISED = ["Mollusca", "Brachiopoda", "Echinodermata", "Bryozoa", "Porifera", "Cnidaria"]
FILES = []


def get_cached(url, cache_name, role, ok_statuses=(200,)):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=300)
                if r.status_code in ok_statuses:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** attempt)
        if r.status_code not in ok_statuses:
            r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    FILES.append({"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
                  "sha256": hashlib.sha256(content).hexdigest(), "role": role})
    return json.loads(content.decode("utf-8"))


def pbdb_taxon_id(phylum):
    """Resolve the phylum-level taxon id. Names such as Tardigrada (also a sloth clade) and Ctenophora
    (also a crane-fly genus) are homonyms in PBDB, so the lookup keeps only accepted high-rank records."""
    d = get_cached(f"{PBDB}/taxa/list.json?match_name={phylum}&show=parent", f"pbdb_taxa_{phylum}.json",
                   f"PBDB taxon lookup, {phylum}", ok_statuses=(200, 404))
    recs = [r for r in d.get("records", []) if r.get("rnk") in (20, 25) and r.get("acc", r.get("oid")) == r.get("oid")]
    if not recs:
        return None, None
    return recs[0]["oid"], recs[0].get("prl")


def pbdb_count(phylum):
    tid, parent = pbdb_taxon_id(phylum)
    if tid is None:
        return 0, "taxon not in PBDB", None
    d = get_cached(f"{PBDB}/occs/list.json?base_id={tid}&pres=regular&limit=1&rowcount",
                   f"pbdb_count_{phylum}.json", f"PBDB body-fossil occurrence count, {phylum}", ok_statuses=(200, 404))
    if "records_found" not in d:
        return 0, d.get("errors") or d.get("warnings"), tid
    return int(d["records_found"]), d.get("warnings"), tid


def pbdb_examples(phylum, n=5):
    tid, _ = pbdb_taxon_id(phylum)
    d = get_cached(f"{PBDB}/occs/list.json?base_id={tid}&pres=regular&limit={n}&show=coll,loc",
                   f"pbdb_examples_{phylum}.json", f"example occurrences, {phylum}", ok_statuses=(200, 404))
    out = []
    for r in d.get("records", []):
        out.append({"phylum": phylum, "occurrence": r.get("oid"), "taxon": r.get("tna") or r.get("idn"),
                    "interval": r.get("oei"), "early_ma": r.get("eag"), "late_ma": r.get("lag"),
                    "collection": r.get("cnm"), "country": r.get("cc2"), "reference": r.get("rid")})
    return out


def gbif_counts(phylum):
    m = get_cached(f"{GBIF}/species/match?name={phylum}&rank=PHYLUM&kingdom=Animalia&strict=true",
                   f"gbif_match_{phylum}.json", f"GBIF backbone match, {phylum}")
    key = m.get("usageKey") if m.get("matchType") == "EXACT" and m.get("rank") == "PHYLUM" else None
    if key is None:
        return None, None, None
    base = f"{GBIF}/species/search?highertaxonKey={key}&rank=SPECIES&status=ACCEPTED&datasetKey={BACKBONE}&limit=0"
    total = get_cached(base, f"gbif_total_{phylum}.json", f"accepted species, {phylum}")["count"]
    extinct = get_cached(base + "&isExtinct=true", f"gbif_extinct_{phylum}.json", f"accepted species flagged extinct, {phylum}")["count"]
    return key, int(total), int(extinct)


def main():
    write_result = "--write-result" in sys.argv
    rows, examples = [], []
    for grp, phyla in (("soft", SOFT), ("mineralised", MINERALISED)):
        for ph in phyla:
            n_occ, warn, tid = pbdb_count(ph)
            key, total, extinct = gbif_counts(ph)
            living = None if total is None else total - extinct
            rows.append({"group": grp, "phylum": ph, "pbdb_taxon_id": tid, "pbdb_body_fossil_occurrences": n_occ, "pbdb_note": json.dumps(warn) if warn else None,
                         "gbif_phylum_key": key, "gbif_accepted_species": total, "gbif_accepted_species_flagged_extinct": extinct,
                         "living_species_est": living,
                         "occurrences_per_living_species": None if not living else n_occ / living})
            if grp == "soft" and n_occ > 0:
                examples += pbdb_examples(ph)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "phyla.csv"), index=False)
    pd.DataFrame(examples).to_csv(os.path.join(DERIVED, "soft_bodied_examples.csv"), index=False)

    soft = df[df.group == "soft"]
    mine = df[df.group == "mineralised"]
    soft_occ = int(soft.pbdb_body_fossil_occurrences.sum())
    soft_phyla_with_fossils = soft[soft.pbdb_body_fossil_occurrences > 0].phylum.tolist()
    clause1 = "refuted" if (soft_occ >= 10 and len(soft_phyla_with_fossils) >= 3) else ("supported" if soft_occ == 0 else "indeterminate")
    med_soft = float(soft.occurrences_per_living_species.dropna().median())
    med_mine = float(mine.occurrences_per_living_species.dropna().median())
    ratio = med_mine / med_soft if med_soft > 0 else float("inf")
    clause2 = "supported" if ratio >= 100 else ("refuted" if ratio < 10 else "indeterminate")
    if clause2 == "refuted":
        verdict = "refutes"
    elif clause1 == "supported" and clause2 == "supported":
        verdict = "supports"
    elif clause1 == "refuted" and clause2 == "supported":
        verdict = "mixed"
    else:
        verdict = "mixed"

    measured = {
        "value": soft_occ,
        "unit": "PBDB body-fossil occurrences in the 13 wholly soft-bodied phyla",
        "n": int(len(df)),
        "uncertainty": f"ratio of median occurrences-per-living-species, mineralised/soft = {ratio:.1f}",
        "extra": {
            "soft_phyla_with_fossil_occurrences": soft_phyla_with_fossils,
            "soft_occurrences_by_phylum": dict(zip(soft.phylum, soft.pbdb_body_fossil_occurrences.astype(int))),
            "mineralised_occurrences_by_phylum": dict(zip(mine.phylum, mine.pbdb_body_fossil_occurrences.astype(int))),
            "living_species_by_phylum": {r.phylum: (None if pd.isna(r.living_species_est) else int(r.living_species_est)) for r in df.itertuples()},
            "median_occurrences_per_living_species_soft": med_soft,
            "median_occurrences_per_living_species_mineralised": med_mine,
            "ratio_mineralised_over_soft": ratio,
            "total_soft_living_species": int(soft.living_species_est.sum()), "total_mineralised_living_species": int(mine.living_species_est.sum()),
            "pooled_occurrences_per_living_species_soft": soft_occ / int(soft.living_species_est.sum()),
            "pooled_occurrences_per_living_species_mineralised": int(mine.pbdb_body_fossil_occurrences.sum()) / int(mine.living_species_est.sum()),
            "clause1_absolute_non_preservation": clause1, "clause2_bias": clause2,
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, default=float)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2, default=float))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = json.loads(json.dumps(measured, default=float))
        for ds in res["datasets"]:
            host = "paleobiodb.org" if ds["id"].startswith("pbdb") else "gbif.org"
            fl = [f for f in FILES if host in f["download_url"]]
            ds["files"] = [{
                "download_url": fl[0]["download_url"].split("?")[0] + "?... (one call per phylum; full list with per-call SHA-256 in derived/files.json)",
                "retrieved_at": min(f["retrieved_at"] for f in fl), "byte_size": sum(f["byte_size"] for f in fl),
                "sha256": hashlib.sha256("".join(f["sha256"] for f in fl).encode()).hexdigest(),
                "note": f"{len(fl)} API responses; sha256 is the SHA-256 of the concatenated per-response SHA-256 hex digests"}]
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
