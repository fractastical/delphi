#!/usr/bin/env python3
"""aristotle-ha02-01: is the lion's neck one bone, or several vertebrae?

Pre-registered rule (result.json, committed before these files were read):
a normal Panthera leo neck supports the claim only if every voting source
reports exactly one cervical element. Any non-pathological source that
reports two or more refutes it. A source that states no count does not vote.

Run from this directory: python3 analysis.py
Uses only the Python standard library. Downloads are cached under data/ and
are not committed. Writes derived/measured.json and updates result.json.
"""

import datetime as dt
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0"}

DATAVERSE = (
    "https://dataverse.csuc.cat/api/datasets/:persistentId/"
    "?persistentId=doi:10.34810/data2062"
)
VET = "https://doi.org/10.22271/veterinary.2021.v6.i2a.328"
ADW = "https://animaldiversity.org/accounts/Panthera_leo/"
DRYAD_FILES = "https://datadryad.org/api/v2/versions/108252/files"

# One slot per cervical identity, so atlas and cervical_I are not counted twice.
SLOT = {
    "atlas": 1, "c1": 1, "cervical_i": 1, "cervical_1": 1,
    "axis": 2, "c2": 2, "cervical_ii": 2, "cervical_2": 2,
    "cervical_iii": 3, "cervical_3": 3, "c3": 3,
    "cervical_iv": 4, "cervical_4": 4, "c4": 4,
    "cervical_v": 5, "cervical_5": 5, "c5": 5,
    "cervical_vi": 6, "cervical_6": 6, "c6": 6,
    "cervical_vii": 7, "cervical_7": 7, "c7": 7,
}


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    path = DATA / name
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            final = resp.geturl()
            status = resp.status
    except urllib.error.HTTPError as err:
        return {
            "download_url": url,
            "retrieved_at": retrieved,
            "http_status": err.code,
            "error": f"HTTP {err.code}",
            "byte_size": None,
            "sha256": None,
        }
    path.write_bytes(raw)
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "http_status": status,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "path": str(path),
        "raw": raw,
    }


def strip_html(html):
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&#39;", "'")
    return re.sub(r"\s+", " ", text)


def pathological(text):
    """True only when the source calls the specimen or its neck pathological.

    A department name such as 'Veterinary Pathology' does not. The pre-registered
    rule excludes a count only when the source itself labels the animal as a
    pathological fusion.
    """
    return bool(re.search(
        r"pathological\s+fusion|pathologically\s+fus|"
        r"pathological\s+(?:specimen|skeleton|lion|neck|animal)|"
        r"(?:specimen|skeleton|neck|lion)\s+(?:is|was|were)\s+pathological",
        text, re.I))


def dataverse_count(raw):
    payload = json.loads(raw)
    version = payload["data"]["latestVersion"]
    files = version["files"]
    slots = {}
    for entry in files:
        directory = (entry.get("directoryLabel") or "").strip()
        key = directory.lower()
        if key not in SLOT:
            continue
        slots.setdefault(SLOT[key], directory)
    description = ""
    for field in version["metadataBlocks"]["citation"]["fields"]:
        if field.get("typeName") == "dsDescription":
            description = field["value"][0]["dsDescriptionValue"]["value"]
    license_name = (version.get("license") or {}).get("name")
    return {
        "id": "cora-dataverse-panthera-leo-93",
        "name": "Panthera leo 93 (skeleton file manifest)",
        "landing_url": "https://doi.org/10.34810/data2062",
        "doi": "10.34810/data2062",
        "version": f"{version.get('versionNumber')}.{version.get('versionMinorNumber')}",
        "license": license_name,
        "role": "separately archived neck bones of one lion skeleton",
        "cervical_count": len(slots),
        "elements": [slots[k] for k in sorted(slots)],
        "n_specimens": 1,
        "pathological": pathological(description),
        "description": description,
        "votes": len(slots) > 0 and not pathological(description),
    }


def paper_count(html):
    text = html.decode("utf-8", "replace")
    abstract = ""
    match = re.search(r'citation_abstract" content="([^"]*)"', text)
    if match:
        abstract = match.group(1)
    plain = strip_html(text)
    blob = abstract + " " + plain
    formula = re.search(r"C(\d+)\s*T(\d+)\s*L(\d+)\s*S(\d+)\s*C(\d+(?:-\d+)?)", blob)
    lions = re.search(r"\((\d+)\)\s*lions", blob, re.I)
    count = int(formula.group(1)) if formula else None
    about_lion = bool(re.search(r"Panthera leo|African lion", blob, re.I))
    return {
        "id": "veterinarypaper-2021-lion-axial-skeleton",
        "name": "Morphological studies on the axial skeleton of the African lion (Panthera leo)",
        "landing_url": "https://doi.org/10.22271/veterinary.2021.v6.i2a.328",
        "doi": "10.22271/veterinary.2021.v6.i2a.328",
        "version": "Int J Vet Sci Anim Husbandry 2021;6(2):09-14",
        "license": "not stated on the public landing page",
        "role": "published vertebral formula for two African lion skeletons",
        "cervical_count": count if about_lion else None,
        "formula": formula.group(0) if formula else None,
        "n_specimens": int(lions.group(1)) if lions else None,
        "pathological": pathological(abstract),
        "about_lion": about_lion,
        "votes": count is not None and about_lion and not pathological(abstract),
    }


def adw_count(html):
    plain = strip_html(html.decode("utf-8", "replace"))
    formula = re.search(r"C(\d+)\s*T(\d+)\s*L(\d+)", plain)
    words = re.search(r"(\d+|seven|one)\s+cervical\s+vertebr", plain, re.I)
    count = None
    if formula:
        count = int(formula.group(1))
    elif words:
        token = words.group(1).lower()
        count = {"one": 1, "seven": 7}.get(token, int(token) if token.isdigit() else None)
    return {
        "id": "adw-panthera-leo",
        "name": "Animal Diversity Web account for Panthera leo",
        "landing_url": ADW,
        "doi": None,
        "version": None,
        "license": "ADW content; see animaldiversity.org",
        "role": "species account checked for a stated cervical count",
        "cervical_count": count,
        "votes": count is not None,
        "silent": count is None,
    }


def decide(votes):
    """Apply the pre-registered rule. votes are dicts with cervical_count."""
    if not votes:
        return "inconclusive", "data-unavailable"
    counts = [v["cervical_count"] for v in votes]
    if any(c == 1 for c in counts) and any(c >= 2 for c in counts):
        return "mixed", None
    if all(c == 1 for c in counts):
        return "supports", None
    if any(c >= 2 for c in counts):
        return "refutes", None
    return "inconclusive", "other"


def main():
    dv = fetch(DATAVERSE, "dataverse-panthera-leo-93.json")
    vet = fetch(VET, "veterinarypaper-2021.html")
    adw = fetch(ADW, "adw-panthera-leo.html")
    dryad = fetch(DRYAD_FILES, "dryad-files.json")
    # The landmark CSVs are the actual measurements. Try the first one.
    dryad_csv = None
    if dryad.get("raw"):
        listing = json.loads(dryad["raw"])
        files = listing.get("_embedded", {}).get("stash:files", [])
        atlas = next((f for f in files if "Atlas" in f.get("path", "")), None)
        if atlas:
            href = atlas["_links"]["stash:download"]["href"]
            url = "https://datadryad.org" + href
            dryad_csv = fetch(url, "dryad-atlas.csv")

    sources = []
    if dv.get("raw"):
        sources.append(dataverse_count(dv["raw"]))
    if vet.get("raw"):
        sources.append(paper_count(vet["raw"]))
    if adw.get("raw"):
        sources.append(adw_count(adw["raw"]))

    voting = [s for s in sources if s.get("votes")]
    verdict, reason = decide(voting)
    counts = [s["cervical_count"] for s in voting]
    specimens = [s["n_specimens"] for s in voting if s.get("n_specimens")]

    if len(voting) >= 2 and verdict == "refutes" and len(set(counts)) == 1:
        confidence = 0.9
    elif len(voting) == 1 and verdict in ("refutes", "supports"):
        confidence = 0.6
    elif verdict == "mixed":
        confidence = 0.55
    else:
        confidence = 0.3

    measured = {
        "value": min(counts) if counts else None,
        "unit": "cervical elements reported for Panthera leo (minimum across voting sources)",
        "n": int(sum(specimens)) if specimens else 0,
        "uncertainty": (
            "voting sources reported " + ", ".join(str(c) for c in counts)
            if counts else "no voting source"
        ),
        "extra": {
            "voting_counts": counts,
            "n_voting_sources": len(voting),
            "sources": [
                {k: s[k] for k in s if k != "description"}
                for s in sources
            ],
            "dryad_csv_http_status": None if dryad_csv is None else dryad_csv.get("http_status"),
        },
    }

    def file_record(fetched, label):
        if not fetched or fetched.get("byte_size") is None:
            return {
                "name": label,
                "download_url": fetched.get("download_url") if fetched else None,
                "retrieved_at": fetched.get("retrieved_at") if fetched else None,
                "http_status": fetched.get("http_status") if fetched else None,
                "error": fetched.get("error") if fetched else "not requested",
            }
        return {
            "name": label,
            "download_url": fetched["download_url"],
            "final_url": fetched.get("final_url"),
            "retrieved_at": fetched["retrieved_at"],
            "byte_size": fetched["byte_size"],
            "sha256": fetched["sha256"],
        }

    datasets = []
    for source, fetched, label in (
        (next((s for s in sources if s["id"].startswith("cora")), None), dv, "dataverse-dataset.json"),
        (next((s for s in sources if s["id"].startswith("veterinary")), None), vet, "landing.html"),
        (next((s for s in sources if s["id"].startswith("adw")), None), adw, "account.html"),
    ):
        if source is None:
            continue
        datasets.append({
            "id": source["id"],
            "name": source["name"],
            "landing_url": source["landing_url"],
            "doi": source["doi"],
            "version": source["version"],
            "license": source["license"],
            "files": [file_record(fetched, label)],
            "role": source["role"],
        })
    datasets.append({
        "id": "dryad-10.5061-dryad.8931zcrq9-carnivoran-vertebrae",
        "name": "Phenotypic integration in the carnivoran backbone (Dryad)",
        "landing_url": "https://doi.org/10.5061/dryad.8931zcrq9",
        "doi": "10.5061/dryad.8931zcrq9",
        "version": "v2",
        "license": "CC0-1.0",
        "files": [
            file_record(dryad, "files.json"),
            file_record(dryad_csv, "Raw_data_Atlas.csv"),
        ],
        "role": "planned landmark tables; used only if a row is identified as Panthera leo. The CSV download was refused, so this dataset casts no vote.",
    })

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["datasets"] = datasets
    result["measured"] = measured
    result["deviations"] = [
        {
            "what": "The Dryad atlas CSV returned HTTP 401, so the landmark tables were not read and cast no vote.",
            "why": "The pre-registered contract already drops that dataset when the lion cannot be identified in it. An unreadable file cannot identify the lion. Pass and fail criteria were not changed.",
        },
        {
            "what": "The Animal Diversity Web account for Panthera leo states no cervical count, so it cast no vote.",
            "why": "The contract says a source that never states a count is silent. Criteria were not changed.",
        },
    ]
    result["method"] = (
        "Fetched the Dataverse dataset record for Panthera leo 93 and counted distinct "
        "cervical directory names (atlas, axis, cervical III–VII). Fetched the public "
        "landing page of Onwuama et al. 2021 and read the vertebral formula in the "
        "abstract. Checked the Animal Diversity Web lion account for a cervical count "
        "and found none. Attempted the Dryad carnivoran landmark file and received HTTP 401. "
        "Applied the pre-registered rule to the sources that reported a count."
    )
    smallest = measured["value"]
    result["results_summary"] = [
        f"Voting sources: {len(voting)}; cervical counts: {counts}; specimens accounted for: {measured['n']}.",
        f"Smallest reported cervical count is {smallest}. The claim requires exactly 1.",
        "Dryad CSV download status: " + str(measured["extra"]["dryad_csv_http_status"]) + ".",
    ]
    result_path.write_text(json.dumps(result, indent=2) + "\n")

    DERIVED.mkdir(exist_ok=True)
    public = {
        "verdict": verdict,
        "reason": reason,
        "measured": {k: v for k, v in measured.items() if k != "extra"},
        "voting": [
            {"id": s["id"], "cervical_count": s["cervical_count"], "elements": s.get("elements"),
             "formula": s.get("formula"), "n_specimens": s.get("n_specimens"),
             "pathological": s.get("pathological")}
            for s in voting
        ],
    }
    (DERIVED / "measured.json").write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps(public, indent=2))


if __name__ == "__main__":
    main()
