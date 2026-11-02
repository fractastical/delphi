#!/usr/bin/env python3
"""Insect developmental mode for fleas, flies and blister beetles.

Uses the pre-registered Zenodo archive and, only if Coleoptera is coded
holometabolous while Meloidae is absent, the GBIF backbone placement of Meloidae.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
ZIP_URL = "https://zenodo.org/api/records/13319669/files/insectdevelopment.zip/content"
GBIF_URL = "https://api.gbif.org/v1/species/match?name=Meloidae&verbose=true"
UA = "delphisci-claim-test"
GROUPS = {
    "flies": ("Diptera",),
    "fleas": ("Siphonaptera",),
    "cantharides": ("Meloidae",),
}


def get(url, accept=None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mode_label(value):
    text = (value or "").strip()
    if "/" in text:
        text = text.rstrip("/").split("/")[-1]
    return text.lower()


def is_holometabolous(label):
    return label in {"holometabolous", "complete metamorphosis", "completemetamorphosis"} or "holometabol" in label


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    retrieved = now()
    raw = get(ZIP_URL)
    (DATA / "insectdevelopment.zip").write_bytes(raw)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    measurements = zf.read("measurementsorfacts.txt").decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(measurements), delimiter="\t"))
    by_taxon = {}
    for row in rows:
        if "DevelopmentalMode" not in (row.get("measurementType") or ""):
            continue
        taxon = (row.get("occurrenceID") or "").strip()
        label = mode_label(row.get("measurementValue") or "")
        if taxon:
            by_taxon.setdefault(taxon, set()).add(label)
    present_names = set(by_taxon)
    group_status = {}
    for group, names in GROUPS.items():
        hits = {name: sorted(by_taxon[name]) for name in names if name in by_taxon}
        group_status[group] = hits
    coleoptera = sorted(by_taxon.get("Coleoptera", []))
    gbif = None
    meloidae_via_coleoptera = False
    if "Meloidae" not in by_taxon and coleoptera and any(is_holometabolous(m) for m in coleoptera):
        gbif_raw = get(GBIF_URL, accept="application/json")
        gbif = json.loads(gbif_raw)
        order = gbif.get("order")
        rank = gbif.get("rank")
        meloidae_via_coleoptera = order == "Coleoptera" and rank == "FAMILY"
        if meloidae_via_coleoptera:
            group_status["cantharides"] = {"Meloidae": ["holometabolous via Coleoptera + GBIF placement"]}

    def coded_holo(group):
        hits = group_status[group]
        if not hits:
            return None
        labels = [lab for labs in hits.values() for lab in labs]
        return any(is_holometabolous(lab) or "via Coleoptera" in lab for lab in labels)

    flags = {g: coded_holo(g) for g in GROUPS}
    named = [g for g, v in flags.items() if v is not None]
    holo = [g for g, v in flags.items() if v is True]
    if not any(name in present_names for name in ("Diptera", "Siphonaptera", "Coleoptera", "Meloidae")):
        verdict, reason, confidence = "inconclusive", "underpowered", 0.4
    elif flags["flies"] and flags["fleas"] and flags["cantharides"]:
        verdict, reason, confidence = "refutes", None, 0.7
    elif all(v is False for v in flags.values()):
        verdict, reason, confidence = "supports", None, 0.55
    elif holo and len(holo) < 3:
        verdict, reason, confidence = "mixed", None, 0.45
    elif not named:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.4
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.4
    if not by_taxon:
        verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.3
    measured = {
        "value": len(holo),
        "unit": "named groups coded holometabolous (flies, fleas, cantharides)",
        "n": len(by_taxon),
        "uncertainty": None,
        "extra": {
            "developmental_modes_by_taxon": {k: sorted(v) for k, v in sorted(by_taxon.items())},
            "group_status": group_status,
            "coleoptera_modes": coleoptera,
            "meloidae_placed_in_coleoptera_by_gbif": meloidae_via_coleoptera,
            "gbif_match": None if gbif is None else {
                "scientificName": gbif.get("scientificName"),
                "rank": gbif.get("rank"),
                "order": gbif.get("order"),
                "confidence": gbif.get("confidence"),
                "usageKey": gbif.get("usageKey"),
            },
            "taxa_in_archive": sorted(by_taxon),
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    files = [{
        "name": "insectdevelopment.zip",
        "download_url": ZIP_URL,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }]
    datasets = [{
        "id": "eol-insect-development-zenodo-13319669",
        "name": "Insect Development",
        "landing_url": "https://zenodo.org/records/13319669",
        "doi": "10.5281/zenodo.13319669",
        "version": "13319669",
        "license": "CC0-1.0",
        "files": files,
        "role": "EOL developmental-mode codings for insect higher taxa",
    }]
    if gbif is not None:
        datasets.append({
            "id": "gbif-backbone-meloidae-placement",
            "name": "GBIF backbone species match for Meloidae",
            "landing_url": "https://www.gbif.org/species/search?q=Meloidae",
            "doi": None,
            "version": "GBIF backbone match API",
            "license": "GBIF data are available under the terms of the records returned by the API",
            "files": [{
                "name": "species-match-Meloidae.json",
                "download_url": GBIF_URL,
                "retrieved_at": retrieved,
                "byte_size": None,
                "sha256": None,
            }],
            "role": "placement of family Meloidae, used only if Coleoptera carries the mode",
        })
    result["datasets"] = datasets
    result["method"] = (
        "Opened the Zenodo Darwin Core archive and read measurementType DevelopmentalMode. "
        "A taxon is holometabolous when the value URI ends in holometabolous or the label is complete metamorphosis. "
        "Flies, fleas and cantharides are looked up as Diptera, Siphonaptera and Meloidae. "
        "The GBIF backbone is queried only when Meloidae is absent and Coleoptera is coded holometabolous. "
        "The verdict follows the pre-registered rule: all three holometabolous refutes the claim, all three "
        "present and non-holometabolous supports it, a split is mixed, and absence of the named taxa is inconclusive."
    )
    result["measured"] = measured
    result["results_summary"] = [
        "Taxa with a developmental mode in the archive: " + ", ".join(sorted(by_taxon)) + ".",
        "Diptera, Siphonaptera, Coleoptera and Meloidae are not rows in the archive."
        if not any(n in by_taxon for n in ("Diptera", "Siphonaptera", "Coleoptera", "Meloidae"))
        else f"Group hits: {group_status}.",
        (
            "Endopterygota is coded " + ", ".join(sorted(by_taxon["Endopterygota"]))
            + ". It was not substituted for Diptera, Siphonaptera or Meloidae, because the pre-registered groups are those three taxa and Coleoptera only as a placement bridge."
            if "Endopterygota" in by_taxon
            else "Endopterygota is not a row in the archive."
        ),
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + ".",
    ]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.joinpath("measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "taxa": sorted(by_taxon)}, indent=2))


if __name__ == "__main__":
    main()
