#!/usr/bin/env python3
"""Measure paternal alleles on chromosome 22 of the 1000 Genomes CEU trio.

Implements the thresholds in result.json. Those thresholds are not changed here.
The VCF is downloaded to the system temp directory and is not written into the repo.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
VCF_URL = (
    "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/pilot_data/paper_data_sets/"
    "a_map_of_human_variation/trio/snps/CEU.trio.2010_09.genotypes.vcf.gz"
)
README_URL = (
    "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/pilot_data/paper_data_sets/"
    "a_map_of_human_variation/trio/snps/README.2010_10.trio_snps"
)
CACHE = Path("/tmp/delphi-claim-tests/1000genomes-ceu-trio")
UA = {"User-Agent": "Mozilla/5.0 DelphiClaimTest/1.0 (aristotle-ga01-31)"}
CHILD, FATHER, MOTHER = "NA12878", "NA12891", "NA12892"
BASES = set("ACGT")


def fetch(url: str, name: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    hasher = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=300) as response, path.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            hasher.update(chunk)
            size += len(chunk)
    return {
        "download_url": url,
        "retrieved_at": retrieved_at,
        "byte_size": size,
        "sha256": hasher.hexdigest(),
        "path": str(path),
    }


def alleles(gt: str, allele_list: list[str]) -> set[str] | None:
    gt = gt.split(":", 1)[0]
    if gt in {".", "./.", ".|."} or "." in gt:
        return None
    parts = gt.replace("|", "/").split("/")
    if len(parts) != 2:
        return None
    out = set()
    for part in parts:
        if not part.isdigit():
            return None
        index = int(part)
        if index >= len(allele_list):
            return None
        out.add(allele_list[index])
    return out


def snp_alleles(ref: str, alt: str) -> list[str] | None:
    alts = alt.split(",")
    if len(ref) != 1 or ref.upper() not in BASES:
        return None
    cleaned = [ref.upper()]
    for item in alts:
        if len(item) != 1 or item.upper() not in BASES:
            return None
        cleaned.append(item.upper())
    return cleaned


def main() -> None:
    vcf = fetch(VCF_URL, "CEU.trio.2010_09.genotypes.vcf.gz")
    readme = fetch(README_URL, "README.2010_10.trio_snps")

    child_i = father_i = mother_i = None
    n_chr22_rows = 0
    n_snps_all_called = 0
    n_mother_hom = 0
    n_concordant = 0
    n_informative = 0
    n_transmitted = 0
    n_informative_father_het = 0
    n_transmitted_father_het = 0
    n_informative_father_hom = 0
    n_transmitted_father_hom = 0

    with gzip.open(vcf["path"], "rt") as handle:
        for line in handle:
            if line.startswith("#CHROM"):
                header = line.rstrip("\n").split("\t")
                samples = header[9:]
                try:
                    child_i = samples.index(CHILD)
                    father_i = samples.index(FATHER)
                    mother_i = samples.index(MOTHER)
                except ValueError:
                    child_i = None
                continue
            if line.startswith("#"):
                continue
            if child_i is None:
                break
            if not (line.startswith("22\t") or line.startswith("chr22\t")):
                continue
            n_chr22_rows += 1
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            if fields[6] not in {"PASS", "."}:
                continue
            allele_list = snp_alleles(fields[3], fields[4])
            if allele_list is None:
                continue
            child = alleles(fields[9 + child_i], allele_list)
            father = alleles(fields[9 + father_i], allele_list)
            mother = alleles(fields[9 + mother_i], allele_list)
            if child is None or father is None or mother is None:
                continue
            n_snps_all_called += 1
            if len(mother) != 1:
                continue
            n_mother_hom += 1
            maternal = next(iter(mother))
            if maternal in child:
                n_concordant += 1
            paternal_only = father - mother
            if not paternal_only:
                continue
            n_informative += 1
            transmitted = bool(child & paternal_only)
            if transmitted:
                n_transmitted += 1
            if len(father) == 2:
                n_informative_father_het += 1
                if transmitted:
                    n_transmitted_father_het += 1
            else:
                # Father homozygous for an allele the mother lacks. Kept separate
                # because a Mendelian filter would drop the non-transmitted cases.
                n_informative_father_hom += 1
                if transmitted:
                    n_transmitted_father_hom += 1

    if child_i is None:
        verdict, reason = "inconclusive", "data-unavailable"
        p = None
        concordance = None
    elif n_informative < 100:
        verdict, reason = "inconclusive", "underpowered"
        p = (n_transmitted / n_informative) if n_informative else None
        concordance = (n_concordant / n_mother_hom) if n_mother_hom else None
    else:
        p = n_transmitted / n_informative
        concordance = (n_concordant / n_mother_hom) if n_mother_hom else 0.0
        if concordance < 0.95:
            verdict, reason = "inconclusive", "other"
        elif p <= 0.01:
            verdict, reason = "supports", None
        elif p >= 0.40:
            verdict, reason = "refutes", None
        else:
            verdict, reason = "mixed", None

    p_het = (
        n_transmitted_father_het / n_informative_father_het
        if n_informative_father_het
        else None
    )
    measured = {
        "value": None if p is None else round(p, 6),
        "unit": "fraction of informative chromosome-22 sites where the child carries a father-only allele",
        "n": n_informative,
        "uncertainty": None,
        "extra": {
            "n_chr22_rows": n_chr22_rows,
            "n_snps_all_called": n_snps_all_called,
            "n_mother_homozygous": n_mother_hom,
            "n_maternal_concordant": n_concordant,
            "maternal_concordance": None if n_mother_hom == 0 else round(n_concordant / n_mother_hom, 6),
            "n_informative": n_informative,
            "n_transmitted": n_transmitted,
            "p_paternal": None if p is None else round(p, 6),
            "n_informative_father_heterozygous": n_informative_father_het,
            "n_transmitted_father_heterozygous": n_transmitted_father_het,
            "p_father_heterozygous": None if p_het is None else round(p_het, 6),
            "n_informative_father_homozygous_other": n_informative_father_hom,
            "n_transmitted_father_homozygous_other": n_transmitted_father_hom,
            "p_father_homozygous_other": (
                None
                if n_informative_father_hom == 0
                else round(n_transmitted_father_hom / n_informative_father_hom, 6)
            ),
            "child": CHILD,
            "father": FATHER,
            "mother": MOTHER,
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    payload = {
        "files": {"vcf": vcf, "readme": readme},
        "measured": measured,
        "verdict": verdict,
        "reason": reason,
    }
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    # Drop local paths before writing the repo file.
    public = json.loads(json.dumps(payload))
    for item in public["files"].values():
        item.pop("path", None)
    (derived / "measured.json").write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps(public, indent=2))


if __name__ == "__main__":
    main()
