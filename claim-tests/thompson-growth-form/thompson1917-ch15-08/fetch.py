#!/usr/bin/env python3
"""Fetch Schistosoma cox1 sequences from NCBI GenBank (E-utilities, no key needed) and write
derived/schistosoma_cox1.fasta plus derived/accessions.csv.

Sampling is fixed: for each nominal species the esearch result (sorted by accession) is
subsampled with random.Random(20261031) to at most N_PER_SPECIES records. Records whose title
contains 'hybrid', cDNA/mRNA/EST records and whole genomes are excluded by the query (length 400-2000 bp). The retrieval time, the esearch counts and the
SHA-256 of the FASTA actually fetched are printed and recorded in result.json; because GenBank
grows, a later run may draw a different sample, which is why the FASTA is committed.
"""
import csv
import hashlib
import os
import random
import re
import sys
import time
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
N_PER_SPECIES = {"Schistosoma mansoni": 40, "Schistosoma haematobium": 40, "Schistosoma bovis": 20,
                 "Schistosoma rodhaini": 10, "Schistosoma japonicum": 10, "Schistosoma curassoni": 10,
                 "Schistosoma guineensis": 6, "Schistosoma intercalatum": 4, "Schistosoma mattheei": 7}
GENE = ('(cox1[Gene] OR COI[Gene] OR COX1[Gene] OR "cytochrome c oxidase subunit I"[Title] '
        'OR "cytochrome oxidase subunit 1"[Title] OR "cytochrome c oxidase subunit 1"[Title])')


def esearch(term):
    r = requests.get(f"{EUTILS}/esearch.fcgi", params={"db": "nuccore", "term": term, "retmax": 5000,
                                                        "tool": "delphi-claim-tests"},
                     timeout=60)
    r.raise_for_status()
    ids = re.findall(r"<Id>(\d+)</Id>", r.text)
    count = int(re.search(r"<Count>(\d+)</Count>", r.text).group(1))
    return count, sorted(ids, key=int)


def efetch_fasta(ids):
    out = []
    for i in range(0, len(ids), 50):
        r = requests.get(f"{EUTILS}/efetch.fcgi", params={"db": "nuccore", "id": ",".join(ids[i:i + 50]),
                                                           "rettype": "fasta", "retmode": "text",
                                                           "tool": "delphi-claim-tests"},
                         timeout=120)
        r.raise_for_status()
        out.append(r.text)
        time.sleep(0.4)
    return "".join(out)


def main():
    os.makedirs(DERIVED, exist_ok=True)
    rng = random.Random(20261031)
    records = []
    fasta = []
    print("retrieved_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    for sp, n in N_PER_SPECIES.items():
        term = (f'"{sp}"[Organism] AND {GENE} AND 400:2000[SLEN] NOT hybrid[Title] '
                'NOT cDNA[Title] NOT mRNA[Title] NOT EST[Keyword] NOT genome[Title]')
        count, ids = esearch(term)
        chosen = sorted(rng.sample(ids, min(n, len(ids))), key=int)
        print(f"{sp}: {count} records matched, {len(chosen)} sampled")
        txt = efetch_fasta(chosen)
        for block in txt.strip().split("\n>"):
            block = block.lstrip(">")
            header, _, seq = block.partition("\n")
            acc = header.split()[0]
            seq = seq.replace("\n", "").upper()
            records.append({"species": sp, "accession": acc, "title": header[len(acc):].strip(), "length": len(seq)})
            fasta.append(f">{acc} [{sp}] {header[len(acc):].strip()}\n{seq}\n")
        time.sleep(0.5)
    fpath = os.path.join(DERIVED, "schistosoma_cox1.fasta")
    with open(fpath, "w") as f:
        f.write("".join(fasta))
    with open(os.path.join(DERIVED, "accessions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["species", "accession", "length", "title"])
        w.writeheader()
        w.writerows(records)
    h = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
    print(f"wrote {fpath}: {len(records)} sequences, {os.path.getsize(fpath)} bytes, sha256={h}")


if __name__ == "__main__":
    main()
