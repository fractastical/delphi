#!/usr/bin/env python3
"""aristotle-ha05-23: domestic-dog gestation of 60 to 63 days.

The AnAge table and the Okkens abstract are opened only after result.json
was committed. Thresholds are the claim's 60 and 63 days.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test"
ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"
ABSTRACT_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pubmed&id=11787149&retmode=text&rettype=abstract"
)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(name: str, url: str) -> dict:
    DATA.mkdir(exist_ok=True)
    path = DATA / name
    retrieved = None
    if not path.exists() or path.stat().st_size == 0:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            path.write_bytes(resp.read())
        retrieved = now_utc()
    raw = path.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": retrieved
        or dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def blank(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null", "na", "<na>"}


def anage_dog() -> dict:
    raw = (DATA / "anage_dataset.zip").read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        member = next(n for n in zf.namelist() if n.lower().endswith((".txt", ".tsv", ".csv")))
        payload = zf.read(member)
    text = payload.decode("utf-8-sig", errors="replace")
    delim = "\t" if "\t" in text.splitlines()[0] else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    headers = list(rows[0].keys()) if rows else []
    genus_col = next(h for h in headers if h.lower() == "genus")
    species_col = next(h for h in headers if h.lower() == "species")
    gest_col = next(h for h in headers if "gestat" in h.lower())
    wanted = {("canis", "familiaris"), ("canis", "lupus familiaris")}
    found = []
    for row in rows:
        genus = (row.get(genus_col) or "").strip()
        epithet = (row.get(species_col) or "").strip()
        key = (genus.lower(), epithet.lower())
        if key not in wanted and not (
            genus.lower() == "canis" and "familiaris" in epithet.lower()
        ):
            continue
        gest = None
        raw_g = row.get(gest_col)
        if not blank(raw_g):
            try:
                gest = float(str(raw_g).strip())
            except ValueError:
                gest = None
        found.append({
            "binomial": f"{genus} {epithet}",
            "genus": genus,
            "species": epithet,
            "gestation_days": gest,
            "gestation_column": gest_col,
            "preferred": key == ("canis", "familiaris") or epithet.lower() == "familiaris",
        })
    chosen = None
    for row in found:
        if row["preferred"]:
            chosen = row
            break
    if chosen is None and found:
        for row in found:
            if row["species"].lower() in {"lupus familiaris", "familiaris"}:
                chosen = row
                break
    return {"member": member, "column": gest_col, "candidates": found, "chosen": chosen}


def parse_abstract(text: str) -> dict:
    range_match = re.search(
        r"between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)\s+days",
        text,
        re.I,
    )
    bitch_match = re.search(r"(\d+)\s+bitches", text, re.I)
    # A short pregnancy rescues the claim only when the abstract itself says
    # litters born before 60 days failed to survive.
    short_failed = bool(re.search(
        r"(?:before|under|less than|shorter than)\s+60\s+days[\s\S]{0,120}"
        r"(?:did not survive|failed to survive|do not survive|does not survive|"
        r"not survive|failed to live|did not live)",
        text,
        re.I,
    )) or bool(re.search(
        r"(?:did not survive|failed to survive|do not survive|not survive)"
        r"[\s\S]{0,120}(?:before|under|less than|shorter than)\s+60\s+days",
        text,
        re.I,
    ))
    # Word boundaries: "studied" contains the letters "died" and is not a survival statement.
    survival_mentioned = bool(re.search(
        r"\bsurviv\w*\b|\bneonat\w*\b|\bstillborn\b|\bdied\b|\bdeath\b|"
        r"\bnon-viable\b|\bnonviable\b",
        text,
        re.I,
    ))
    below_60 = bool(re.search(r"(?:less than|under|shorter than|before)\s+60\s+days", text, re.I))
    parsed_min = float(range_match.group(1)) if range_match else None
    parsed_max = float(range_match.group(2)) if range_match else None
    if parsed_min is not None and parsed_max is not None and parsed_min > parsed_max:
        parsed_min, parsed_max = parsed_max, parsed_min
    return {
        "range_span": range_match.group(0) if range_match else None,
        "min_days": parsed_min,
        "max_days": parsed_max,
        "n_bitches": int(bitch_match.group(1)) if bitch_match else None,
        "n_span": bitch_match.group(0) if bitch_match else None,
        "short_pregnancy_said_not_to_survive": short_failed,
        "survival_mentioned": survival_mentioned,
        "mentions_shorter_than_60": below_60 or (
            parsed_min is not None and parsed_min < 60
        ),
    }


def main() -> None:
    anage_file = fetch("anage_dataset.zip", ANAGE_URL)
    abstract_file = fetch("pmid-11787149.txt", ABSTRACT_URL)
    dog = anage_dog()
    abstract = (DATA / "pmid-11787149.txt").read_text(encoding="utf-8", errors="replace")
    parsed = parse_abstract(abstract)
    chosen = dog["chosen"]
    T = chosen["gestation_days"] if chosen else None
    sample_min = parsed["min_days"]
    sample_max = parsed["max_days"]
    n = parsed["n_bitches"]
    range_ok = (
        sample_min is not None
        and sample_max is not None
        and sample_min >= 60
        and sample_max <= 63
    )
    T_ok = T is not None and 60 <= T <= 63
    outside = (
        sample_min is not None
        and sample_max is not None
        and (sample_min < 60 or sample_max > 63)
    )
    refutes = (
        n is not None
        and n >= 20
        and sample_min is not None
        and sample_max is not None
        and (
            sample_max > 63
            or (sample_min < 60 and not parsed["short_pregnancy_said_not_to_survive"])
        )
    )
    if chosen is None and not abstract.strip():
        verdict, why = "inconclusive", "data-unavailable"
    elif refutes:
        verdict, why = "refutes", None
    elif T_ok and range_ok and not parsed["mentions_shorter_than_60"]:
        verdict, why = "supports", None
    elif (not refutes) and T_ok and outside:
        verdict, why = "mixed", None
    elif T is not None and sample_min is None:
        verdict, why = "inconclusive", "underpowered"
    elif chosen is None and sample_min is None:
        verdict, why = "inconclusive", "data-unavailable"
    else:
        verdict, why = "inconclusive", "underpowered"

    if verdict == "inconclusive":
        confidence = 0.4
    elif verdict == "refutes" and n is not None and n >= 50:
        confidence = 0.75
    elif verdict == "supports":
        confidence = 0.6
    else:
        confidence = 0.5

    survival_clause = (
        "stated non-survival"
        if parsed["short_pregnancy_said_not_to_survive"]
        else ("mentioned but not tied to a birth before 60 days" if parsed["survival_mentioned"] else "untested")
    )
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "anage": dog,
        "abstract_parse": parsed,
        "survival_clause": survival_clause,
        "abstract_chars": len(abstract),
    }, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if (chosen or abstract.strip()) else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if why:
        result["reason"] = why
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "anage-dataset-zip",
            "name": "AnAge species dataset",
            "landing_url": "https://genomics.senescence.info/species/index.html",
            "doi": None,
            "version": dog["member"],
            "license": "AnAge is free to use with citation; the download page does not name an SPDX licence",
            "files": [{"name": "dataset.zip", **anage_file}],
            "role": "species-typical gestation for the domestic dog",
        },
        {
            "id": "pubmed-11787149",
            "name": "Okkens et al. 2001, Influence of litter size and breed on the duration of gestation in dogs, J Reprod Fertil Suppl",
            "landing_url": "https://pubmed.ncbi.nlm.nih.gov/11787149/",
            "doi": None,
            "version": "PMID 11787149",
            "license": "PubMed abstract",
            "files": [{"name": "pmid-11787149.txt", **abstract_file}],
            "role": "mating-to-parturition range in the abstract",
        },
    ]
    result["method"] = (
        "Downloaded the AnAge zip and read the gestation column for Canis familiaris, "
        "falling back only to a Canis row whose species epithet contains familiaris. "
        "Downloaded the PubMed abstract of PMID 11787149 and parsed the first "
        "'between A and B days' span as the sample minimum and maximum, and the first "
        "count of bitches as n. A value above 63 is not rescued. A value below 60 "
        "is rescued only when the abstract says litters born before 60 days failed "
        "to survive. The two sources are not averaged."
    )
    result["measured"] = {
        "value": sample_min if sample_min is not None else T,
        "unit": "days, parsed sample minimum if the abstract range was found, otherwise the AnAge point",
        "n": n if n is not None else (1 if T is not None else 0),
        "uncertainty": None,
        "extra": {
            "anage_gestation_days": T,
            "anage_binomial": None if not chosen else chosen["binomial"],
            "sample_min_days": sample_min,
            "sample_max_days": sample_max,
            "n_bitches": n,
            "range_inside_60_to_63": range_ok,
            "anage_inside_60_to_63": T_ok,
            "short_pregnancy_said_not_to_survive": parsed["short_pregnancy_said_not_to_survive"],
            "survival_clause": survival_clause,
        },
    }
    result["results_summary"] = [
        (
            f"AnAge gestation for {chosen['binomial'] if chosen else 'the dog'}: {T} days. "
            f"Abstract range: {sample_min} to {sample_max} days"
            + (f", n={n} bitches." if n is not None else ".")
        ),
        f"Survival clause: {survival_clause}.",
        f"Parsed abstract span: {parsed['range_span']!r}.",
    ]
    note = (
        "After the run, the survival clause is "
        + survival_clause
        + ". An abstract is not a litter table, so pup survival was not recounted from primary records."
    )
    caveats = [c for c in result.get("caveats") or [] if not c.startswith("After the run,")]
    caveats.append(note)
    result["caveats"] = caveats
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": why,
        "T": T,
        "min": sample_min,
        "max": sample_max,
        "n": n,
        "survival": survival_clause,
        "confidence": confidence,
        "binomial": None if not chosen else chosen["binomial"],
    }, indent=2))


if __name__ == "__main__":
    main()
