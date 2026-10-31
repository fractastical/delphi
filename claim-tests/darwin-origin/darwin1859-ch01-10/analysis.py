#!/usr/bin/env python3
"""Test of darwin1859-ch01-10: "all our domestic breeds have descended from the
Columba livia with its geographical sub-species".

All GenBank mitochondrial records of Columba livia and of every other Columba species
are fetched. COI and CYTB regions are located in each record by best ungapped offset
against the C. livia reference mitogenome NC_013978. Domestic records (organism
'domestica', /breed qualifier, or a breed name in the record) are compared with
non-domestic C. livia and with the other Columba species by p-distance over shared
positions. The claim predicts every domestic sequence is nearest to C. livia.

Re-run:  python3 analysis.py   (downloads ~15 MB of GenBank flat files into ./data/)
"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
QUERIES = {
    "livia": '"Columba livia"[Organism] AND mitochondrion[filter]',
    "other_columba": '"Columba"[Organism] NOT "Columba livia"[Organism] AND mitochondrion[filter]',
}
REFERENCE = "NC_013978.1"
GENES = {"COI": ("COX1", "cytochrome c oxidase subunit I"), "CYTB": ("CYTB", "cytochrome b")}
MIN_OVERLAP_REF = 400     # bp of a record that must overlap the reference gene
MIN_SHARED = 300          # bp shared between two records for a distance
INTRASPECIFIC = 0.02
MIN_DOMESTIC, MIN_BREEDS = 10, 5
BREED_WORDS = r"\b(fantail|pouter|tumbler|homer|homing|racing|jacobin|carrier|runt|barb|frillback|king pigeon|modena|owl|trumpeter|cropper|swallow|nun|helmet|magpie|turbit|dragoon|archangel|lahore|scandaroon|roller|highflyer|tippler|shiqi|tarim|taihu|domestic|breed|fancy|utility|squab|meat pigeon|white king|silver king|mondain|texan|hubbell|damascene|ice pigeon|oriental frill|satinette|blondinette|budapest|komorner|polish|danzig|birmingham|rock dove \(domestic\))\b"
FILES = []


def ncbi(endpoint, params, label, tries=6):
    for attempt in range(tries):
        try:
            r = requests.get(EUTILS + endpoint, params=params, timeout=300)
            if r.status_code == 200 and r.content:
                FILES.append({"label": label, "download_url": r.url,
                              "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
                time.sleep(0.4)
                return r
        except requests.RequestException:
            pass
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"NCBI request failed: {endpoint}")


def esearch(term):
    r = ncbi("esearch.fcgi", {"db": "nuccore", "term": term, "retmode": "json", "retmax": 10000}, f"esearch:{term}")
    return sorted(int(i) for i in r.json()["esearchresult"]["idlist"])


def efetch_gb(ids, label):
    out = []
    for i in range(0, len(ids), 100):
        r = ncbi("efetch.fcgi", {"db": "nuccore", "id": ",".join(map(str, ids[i:i + 100])), "rettype": "gb", "retmode": "text"}, f"efetch:{label}:{i}")
        out.append(r.text)
    text = "\n".join(out)
    open(os.path.join(DATA, f"{label}.gb"), "w").write(text)
    return text


def parse_genbank(text):
    for rec in text.split("\n//\n"):
        if "LOCUS" not in rec:
            continue
        acc = re.search(r"^VERSION\s+(\S+)", rec, re.M)
        src_org = re.search(r'/organism="([^"]+)"', rec)
        breed = re.search(r'/breed="([^"]+)"', rec)
        definition = re.search(r"^DEFINITION\s+(.+?)(?=\n[A-Z])", rec, re.M | re.S)
        header = rec.split("\nORIGIN")[0]
        origin = rec.split("\nORIGIN")[1] if "\nORIGIN" in rec else ""
        seq = re.sub(r"[^acgt]", "n", re.sub(r"[^a-z]", "", origin.lower()))
        feats = []
        ftxt = header.split("\nFEATURES")[1] if "\nFEATURES" in header else ""
        for m in re.finditer(r"^\s{5}(CDS|gene)\s+(\S+)\n((?:\s{21}.*\n?)*)", ftxt, re.M):
            feats.append((m.group(1), m.group(2), m.group(3)))
        yield {"accession": acc.group(1) if acc else None, "organism": src_org.group(1) if src_org else None,
               "breed": breed.group(1) if breed else None, "definition": " ".join(definition.group(1).split()) if definition else "",
               "header": header, "features": feats, "seq": seq}


COMP = str.maketrans("acgtn", "tgcan")


def revcomp(s):
    return s.translate(COMP)[::-1]


def extract_gene(rec, gene):
    name, product = GENES[gene]
    for kind, loc, quals in rec["features"]:
        if kind != "CDS":
            continue
        if not (re.search(r'/gene="' + re.escape(name) + r'"', quals, re.I) or re.search(r'/product="' + re.escape(product) + r'"', quals, re.I)):
            continue
        m = re.fullmatch(r"(complement\()?<?(\d+)\.\.>?(\d+)\)?", loc)
        if not m:
            return None
        s = rec["seq"][int(m.group(2)) - 1:int(m.group(3))]
        return revcomp(s) if m.group(1) else s
    return None


def kmer_index(ref, k=11):
    idx = defaultdict(list)
    for i in range(len(ref) - k + 1):
        idx[ref[i:i + k]].append(i)
    return idx


def best_offset(seq, ref, idx, k=11):
    """Return (offset, matches, overlap) of the best ungapped placement of seq on ref."""
    votes = Counter()
    for i in range(0, len(seq) - k + 1, 3):
        for j in idx.get(seq[i:i + k], ()):
            votes[j - i] += 1
    best = (None, 0, 0)
    for off, _ in votes.most_common(5):
        lo, hi = max(0, off), min(len(ref), off + len(seq))
        if hi - lo < MIN_OVERLAP_REF:
            continue
        a = np.frombuffer(ref[lo:hi].encode(), dtype="S1")
        b = np.frombuffer(seq[lo - off:hi - off].encode(), dtype="S1")
        valid = (a != b"n") & (b != b"n")
        matches = int(((a == b) & valid).sum())
        if matches > best[1]:
            best = (off, matches, int(valid.sum()))
    return best


def place(seq, ref, idx):
    fwd = best_offset(seq, ref, idx)
    rev = best_offset(revcomp(seq), ref, idx)
    strand, (off, matches, overlap) = ("+", fwd) if fwd[1] >= rev[1] else ("-", rev)
    if off is None or overlap < MIN_OVERLAP_REF or matches / overlap < 0.8:
        return None
    s = seq if strand == "+" else revcomp(seq)
    row = ["n"] * len(ref)
    lo, hi = max(0, off), min(len(ref), off + len(s))
    row[lo:hi] = list(s[lo - off:hi - off])
    return "".join(row)


def species_of(org):
    parts = (org or "").split()
    return " ".join(parts[:2]) if len(parts) >= 2 else org


def main():
    ids = {k: esearch(q) for k, q in QUERIES.items()}
    print({k: len(v) for k, v in ids.items()}, file=sys.stderr)
    records = []
    for label, idlist in ids.items():
        for rec in parse_genbank(efetch_gb(idlist, label)):
            rec["set"] = label
            records.append(rec)
    by_acc = {r["accession"]: r for r in records}
    ref_rec = by_acc.get(REFERENCE)
    if ref_rec is None:
        ref_rec = next(parse_genbank(efetch_gb(esearch(f"{REFERENCE}[Accession]"), "reference")))
    refs = {g: extract_gene(ref_rec, g) for g in GENES}
    assert all(refs.values()), "reference genes not found"
    idxs = {g: kmer_index(refs[g]) for g in GENES}

    rows = {g: {} for g in GENES}
    meta = {}
    for rec in records:
        org = rec["organism"] or ""
        text = rec["header"]
        is_livia = org.lower().startswith("columba livia")
        domestic = is_livia and bool("domestica" in org.lower() or rec["breed"] or re.search(BREED_WORDS, text, re.I))
        breed_label = None
        if domestic:
            m_note = re.search(r'/note="breed:\s*([^"]+)"', text, re.I)
            m_def = re.search(r"\bbreed\s+(.+?)\s+(?:cytochrome|mitochondri|NADH|16S|12S|control|D-loop)", rec["definition"], re.I)
            m_iso = re.search(r'/isolate="([^"]+)"', text.replace("_", " "))
            if rec["breed"]:
                breed_label = rec["breed"].strip()
            elif m_note:
                breed_label = m_note.group(1).strip()
            elif m_def:
                breed_label = m_def.group(1).strip()
            elif m_iso and re.search(BREED_WORDS, m_iso.group(1), re.I):
                breed_label = re.sub(r"^[\d ]+", "", m_iso.group(1)).strip()
            else:
                kw = re.search(BREED_WORDS, text, re.I)
                breed_label = kw.group(1).lower() if kw else "domestica"
        GENERIC = {"domestic", "domestica", "breed", "fancy", "utility", "racing", "homing"}
        meta_named = breed_label not in GENERIC if breed_label else False
        meta[rec["accession"]] = {"organism": org, "species": species_of(org), "domestic": domestic, "breed": breed_label, "named_breed": meta_named, "definition": rec["definition"]}
        # a record is placed on each reference gene it covers (complete mitogenomes cover both)
        for g in GENES:
            seq = rec["seq"]
            if len(seq) > 3000:  # complete / large record: use the annotated gene if present, else skip
                gs = extract_gene(rec, g)
                if gs is None:
                    continue
                seq = gs
            row = place(seq, refs[g], idxs[g])
            if row is not None:
                rows[g][rec["accession"]] = row

    def pdist_matrix(accs, rowdict):
        arr = np.frombuffer("".join(rowdict[a] for a in accs).encode(), dtype="S1").reshape(len(accs), -1)
        valid = arr != b"n"
        n = len(accs)
        d = np.full((n, n), np.nan)
        shared = np.zeros((n, n), dtype=int)
        for i in range(n):
            both = valid[i] & valid
            sh = both.sum(1)
            diff = ((arr[i] != arr) & both).sum(1)
            shared[i] = sh
            with np.errstate(invalid="ignore", divide="ignore"):
                d[i] = np.where(sh >= MIN_SHARED, diff / np.maximum(sh, 1), np.nan)
        return d, shared

    per_domestic = {}
    gene_stats = {}
    for g in GENES:
        accs = sorted(rows[g])
        if not accs:
            continue
        d, shared = pdist_matrix(accs, rows[g])
        dom = [i for i, a in enumerate(accs) if meta[a]["domestic"]]
        livia_wild = [i for i, a in enumerate(accs) if meta[a]["species"] == "Columba livia" and not meta[a]["domestic"]]
        others = defaultdict(list)
        for i, a in enumerate(accs):
            # 'Columba sp.' records are unidentified pigeons, not an alternative wild species
            if meta[a]["species"] != "Columba livia" and not meta[a]["species"].endswith(" sp."):
                others[meta[a]["species"]].append(i)
        gene_stats[g] = {"n_records_placed": len(accs), "n_domestic": len(dom), "n_livia_non_domestic": len(livia_wild),
                         "n_other_species_records": {k: len(v) for k, v in sorted(others.items())}}
        for i in dom:
            dl = d[i, livia_wild]
            dl = dl[~np.isnan(dl)]
            if dl.size == 0:
                continue
            dother = {}
            for sp, idx in others.items():
                v = d[i, idx]
                v = v[~np.isnan(v)]
                if v.size:
                    dother[sp] = float(v.min())
            if not dother:
                continue
            nearest = min(dother, key=dother.get)
            per_domestic[(accs[i], g)] = {"accession": accs[i], "gene": g, "breed": meta[accs[i]]["breed"],
                                          "d_nearest_livia": float(dl.min()), "nearest_other_species": nearest,
                                          "d_nearest_other": dother[nearest],
                                          "nearest_is_other_species": bool(dother[nearest] < dl.min()),
                                          "outside_livia_within_other": bool(dl.min() >= INTRASPECIFIC and dother[nearest] < INTRASPECIFIC),
                                          "d_rupestris": dother.get("Columba rupestris")}

    results = list(per_domestic.values())
    dom_accs = {r["accession"] for r in results}
    breeds = {r["breed"] for r in results if r["breed"] and meta[r["accession"]]["named_breed"]}
    violations = [r for r in results if r["nearest_is_other_species"] or r["outside_livia_within_other"]]
    viol_accs = {r["accession"] for r in violations}
    viol_breeds = {r["breed"] for r in violations}
    max_d_livia = max([r["d_nearest_livia"] for r in results], default=None)

    if len(dom_accs) < MIN_DOMESTIC or len(breeds) < MIN_BREEDS:
        verdict = "inconclusive"
    elif len(viol_accs) == 0 and max_d_livia is not None and max_d_livia < INTRASPECIFIC:
        verdict = "supports"
    elif len(viol_accs) >= 2 and len(viol_breeds) >= 2:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": len(viol_accs),
        "unit": "domestic-labelled Columba livia records whose nearest non-domestic mitochondrial sequence (COI or CYTB) belongs to another Columba species",
        "n": len(dom_accs),
        "uncertainty": f"max p-distance from a domestic record to the nearest C. livia record {max_d_livia}; MIN_SHARED {MIN_SHARED} bp",
        "extra": {
            "n_domestic_records_compared": len(dom_accs),
            "n_domestic_record_gene_pairs": len(results),
            "named_breeds": sorted(breeds),
            "n_named_breeds": len(breeds),
            "n_domestic_records_without_breed_name": sum(1 for a in dom_accs if not meta[a]["named_breed"]),
            "max_d_domestic_to_nearest_livia": max_d_livia,
            "mean_d_domestic_to_nearest_livia": float(np.mean([r["d_nearest_livia"] for r in results])) if results else None,
            "min_d_domestic_to_other_species": min([r["d_nearest_other"] for r in results], default=None),
            "nearest_other_species_counts": dict(Counter(r["nearest_other_species"] for r in results)),
            "domestic_nearest_to_rupestris_than_livia": sum(1 for r in results if r["d_rupestris"] is not None and r["d_rupestris"] < r["d_nearest_livia"]),
            "min_d_domestic_to_rupestris": min([r["d_rupestris"] for r in results if r["d_rupestris"] is not None], default=None),
            "violations": violations,
            "gene_stats": gene_stats,
            "n_records_fetched": {k: len(v) for k, v in ids.items()},
            "verdict_by_rule": verdict,
        },
    }
    json.dump(results, open(os.path.join(DERIVED, "per_domestic_record.json"), "w"), indent=1)
    json.dump({a: m for a, m in meta.items() if a in set(rows["COI"]) | set(rows["CYTB"])}, open(os.path.join(DERIVED, "records_used.json"), "w"), indent=1)
    json.dump({"measured": measured, "files": FILES}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
