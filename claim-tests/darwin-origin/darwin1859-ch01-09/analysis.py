#!/usr/bin/env python3
"""Test of darwin1859-ch01-09: "our domestic dogs have descended from several wild
species".

Complete mitochondrial genomes are fetched from GenBank (NCBI E-utilities) for a
systematic sample of domestic dogs, all wild grey wolves, and all records of the
other wild canid species Darwin could have counted as ancestors. CYTB and COX1
coding sequences are extracted from the GenBank feature table and compared by
ungapped p-distance. For each dog the nearest non-dog sequence is found; the claim
predicts that some dogs are nearest to a non-wolf species.

Re-run:  python3 analysis.py   (downloads ~30 MB of GenBank flat files into ./data/)
"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
MITO = 'mitochondrion[filter] AND "complete genome"[Title]'
QUERIES = {
    "dog": f'"Canis lupus familiaris"[Organism] AND {MITO}',
    "wolf": f'"Canis lupus"[Organism] NOT "Canis lupus familiaris"[Organism] AND {MITO}',
    "Canis latrans": f'"Canis latrans"[Organism] AND {MITO}',
    "Canis aureus": f'"Canis aureus"[Organism] AND {MITO}',
    "Canis lupaster": f'"Canis lupaster"[Organism] AND {MITO}',
    "Canis simensis": f'"Canis simensis"[Organism] AND {MITO}',
    "Cuon alpinus": f'"Cuon alpinus"[Organism] AND {MITO}',
    "Lycaon pictus": f'"Lycaon pictus"[Organism] AND {MITO}',
}
DOG_SAMPLE_STEP = 3  # pre-registered: every third dog record by ascending UID
GENES = {"CYTB": ("CYTB", "cytochrome b"), "COX1": ("COX1", "cytochrome c oxidase subunit I")}
MIN_DOGS, MIN_WOLVES = 100, 20
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
    raise RuntimeError(f"NCBI request failed: {endpoint} {params}")


def esearch(term):
    r = ncbi("esearch.fcgi", {"db": "nuccore", "term": term, "retmode": "json", "retmax": 5000}, f"esearch:{term}")
    ids = sorted(int(i) for i in r.json()["esearchresult"]["idlist"])
    return ids


def efetch_gb(ids, label):
    out = []
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        r = ncbi("efetch.fcgi", {"db": "nuccore", "id": ",".join(map(str, chunk)), "rettype": "gb", "retmode": "text"}, f"efetch:{label}:{i}")
        out.append(r.text)
    text = "\n".join(out)
    open(os.path.join(DATA, f"{label}.gb"), "w").write(text)
    return text


def parse_genbank(text):
    """Yield dicts with accession, organism, features (list of (location, qualifiers)), sequence."""
    for rec in text.split("\n//\n"):
        if "LOCUS" not in rec:
            continue
        acc = re.search(r"^VERSION\s+(\S+)", rec, re.M)
        org = re.search(r"^\s+ORGANISM\s+(.+)$", rec, re.M)
        src_org = re.search(r'/organism="([^"]+)"', rec)
        breed = re.search(r'/breed="([^"]+)"', rec)
        origin = rec.split("\nORIGIN")[1] if "\nORIGIN" in rec else ""
        # keep every base position; IUPAC ambiguity codes become 'n' (dropping them would shift coordinates)
        seq = re.sub(r"[^acgt]", "n", re.sub(r"[^a-z]", "", origin.lower()))
        feats = []
        ftxt = rec.split("\nFEATURES")[1].split("\nORIGIN")[0] if "\nFEATURES" in rec else ""
        for m in re.finditer(r"^\s{5}(CDS|gene)\s+(\S+)\n((?:\s{21}.*\n?)*)", ftxt, re.M):
            feats.append((m.group(1), m.group(2), m.group(3)))
        yield {"accession": acc.group(1) if acc else None,
               "organism": (src_org.group(1) if src_org else (org.group(1).strip() if org else None)),
               "breed": breed.group(1) if breed else None,
               "features": feats, "seq": seq}


COMP = str.maketrans("acgtn", "tgcan")


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
        if m.group(1):
            s = s.translate(COMP)[::-1]
        return s
    return None


def main():
    ids = {k: esearch(q) for k, q in QUERIES.items()}
    dog_ids_all = ids["dog"]
    ids["dog"] = dog_ids_all[::DOG_SAMPLE_STEP]
    print({k: len(v) for k, v in ids.items()}, file=sys.stderr)

    records = []
    for label, idlist in ids.items():
        if not idlist:
            continue
        text = efetch_gb(idlist, label.replace(" ", "_"))
        for rec in parse_genbank(text):
            rec["query"] = label
            records.append(rec)

    # classify each record by its own organism string
    def group(rec):
        o = (rec["organism"] or "").lower()
        if rec["query"] == "dog" or "familiaris" in o:
            return "dog"
        if "dingo" in o:
            return "dingo"
        if rec["query"] == "wolf" or o.startswith("canis lupus"):
            return "wolf"
        return rec["query"]
    for rec in records:
        rec["group"] = group(rec)

    seqs = {}
    for rec in records:
        parts = {g: extract_gene(rec, g) for g in GENES}
        if any(v is None for v in parts.values()):
            continue
        seqs[rec["accession"]] = {"group": rec["group"], "organism": rec["organism"], "breed": rec["breed"], **parts}

    # keep only the modal length per gene so that ungapped comparison is valid
    usable = {}
    modal = {g: Counter(len(s[g]) for s in seqs.values()).most_common(1)[0][0] for g in GENES}
    for acc, s in seqs.items():
        if all(len(s[g]) == modal[g] for g in GENES):
            usable[acc] = s
    accs = sorted(usable)
    groups = {a: usable[a]["group"] for a in accs}
    counts = Counter(groups.values())
    print("usable:", dict(counts), "modal lengths:", modal, file=sys.stderr)

    concat = ["".join(usable[a][g] for g in GENES) for a in accs]
    L = len(concat[0])
    arr = np.frombuffer("".join(concat).encode(), dtype="S1").reshape(len(accs), L)
    valid = np.isin(arr, [b"a", b"c", b"g", b"t"])
    n = len(accs)
    dist = np.zeros((n, n))
    for i in range(n):
        both = valid[i] & valid
        diff = (arr[i] != arr) & both
        dist[i] = diff.sum(1) / np.maximum(both.sum(1), 1)

    dogs = [i for i, a in enumerate(accs) if groups[a] == "dog"]
    wolves = [i for i, a in enumerate(accs) if groups[a] == "wolf"]
    others = {g: [i for i, a in enumerate(accs) if groups[a] == g] for g in counts if g not in ("dog", "wolf", "dingo")}

    if len(dogs) < MIN_DOGS or len(wolves) < MIN_WOLVES:
        measured = {"value": None, "unit": "dogs nearest to a non-wolf species", "n": len(dogs),
                    "uncertainty": "underpowered", "extra": {"n_dogs": len(dogs), "n_wolves": len(wolves), "verdict_by_rule": "inconclusive"}}
    else:
        per_dog = []
        for i in dogs:
            d_wolf = dist[i, wolves].min()
            d_other = {g: float(dist[i, idx].min()) for g, idx in others.items() if idx}
            nearest_other = min(d_other, key=d_other.get)
            per_dog.append({"accession": accs[i], "breed": usable[accs[i]]["breed"], "d_wolf": float(d_wolf),
                            "d_nearest_other_species": d_other[nearest_other], "nearest_other_species": nearest_other,
                            "non_wolf_nearest": bool(d_other[nearest_other] < d_wolf)})
        non_wolf = [p for p in per_dog if p["non_wolf_nearest"]]
        frac = len(non_wolf) / len(per_dog)
        if len(non_wolf) == 0:
            verdict = "refutes"
        elif len(non_wolf) >= 3 and frac >= 0.02:
            verdict = "supports"
        else:
            verdict = "mixed"
        dw = np.array([p["d_wolf"] for p in per_dog])
        do = np.array([p["d_nearest_other_species"] for p in per_dog])
        species_means = {g: float(dist[np.ix_(dogs, idx)].mean()) for g, idx in others.items() if idx}
        measured = {
            "value": len(non_wolf),
            "unit": "sampled dog mitogenomes whose nearest non-dog sequence belongs to a species other than Canis lupus",
            "n": len(per_dog),
            "uncertainty": f"fraction {frac:.4f}; p-distances over {L} bp of CYTB+COX1",
            "extra": {
                "n_dogs_sampled": len(per_dog), "n_wild_wolves": len(wolves),
                "n_other_species_sequences": {g: len(idx) for g, idx in others.items()},
                "n_dingo_excluded": counts.get("dingo", 0),
                "n_dog_records_total_in_genbank": len(dog_ids_all),
                "n_breeds_labelled": len({p["breed"] for p in per_dog if p["breed"]}),
                "alignment_length_bp": L, "modal_gene_lengths": modal,
                "dog_to_nearest_wolf_pdist": {"mean": float(dw.mean()), "median": float(np.median(dw)), "max": float(dw.max())},
                "dog_to_nearest_other_species_pdist": {"mean": float(do.mean()), "min": float(do.min())},
                "mean_dog_to_species_pdist": species_means,
                "min_wolf_to_other_species_pdist": float(min(dist[np.ix_(wolves, idx)].min() for idx in others.values() if idx)),
                "non_wolf_nearest_dogs": non_wolf,
                "verdict_by_rule": verdict,
            },
        }
        json.dump(per_dog, open(os.path.join(DERIVED, "per_dog.json"), "w"), indent=1)

    json.dump({a: {k: v for k, v in usable[a].items() if k not in GENES} for a in accs}, open(os.path.join(DERIVED, "sequences_used.json"), "w"), indent=1)
    json.dump({"measured": measured, "files": FILES}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
