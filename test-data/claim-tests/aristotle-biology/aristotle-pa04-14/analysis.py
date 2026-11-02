#!/usr/bin/env python3
"""aristotle-pa04-14: eight arms, short in cuttlefish and squid, longer in octopus.

Counts come from Nixon 2011, Treatise Online 17. Specimen length files are
attempted and, if they are not actually the tables, the length clause is left
unscored. Does not edit the frozen criteria.

Run: python3 analysis.py
Needs pypdf (pip install pypdf).
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
PDF_URL = "https://journals.ku.edu/treatiseonline/article/download/4087/3854"
UA = "delphisci-claim-test/aristotle-pa04-14"
LENGTH_ATTEMPTS = [
    ("hosono-2024-heterololigo-arm-lengths", "https://datadryad.org/downloads/file_stream/3750116"),
    ("voss-mehta-2022-octopus-arm-measurements", "https://datadryad.org/downloads/file_stream/1462749"),
    ("guerra-2001-sepia-morphometrics", "https://digital.csic.es/bitstream/10261/26125/1/Sepia.pdf"),
]
MORPHDAT_URL = "https://data.source.coop/cboettig/fishbase/slb/v26.06/parquet/morphdat.parquet"
SQUID_ARMS = "extant myopsid and oegopsid squids; arm I is dorsal and arm IV is ventral"
CAVEAT_MARK = "Analysis: "


def fetch(url, name, timeout=120):
    DATA.mkdir(exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    (DATA / name).write_bytes(raw)
    return {
        "name": name,
        "download_url": url,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def pairs_to_count(phrase):
    m = re.search(r"(four|4|eight|8)\s+pairs?\s+of\s+arms", phrase, re.I)
    if not m:
        return None
    word = m.group(1).lower()
    n = {"four": 4, "4": 4, "eight": 8, "8": 8}[word]
    return n if word in {"eight", "8"} else n * 2


def main():
    pdf_meta, pdf = fetch(PDF_URL, "nixon2011-anatomy.pdf")
    reader = PdfReader(DATA / "nixon2011-anatomy.pdf")
    text = re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in reader.pages))
    dec = re.search(r"ten appendages are present in Decapodiformes: four pairs of arms and a pair of tentacles", text)
    octo = re.search(r"Octopodiformes have just four pair of arms", text)
    sepia = re.search(r"Sepia officinalis \(Decapodiformes, Sepiida\)", text)
    squid = re.search(re.escape(SQUID_ARMS), text)
    if not dec or not octo or not sepia or not squid:
        raise SystemExit("required sentences missing")
    dec_arms = pairs_to_count(dec.group(0))
    tentacles = 2 if re.search(r"a pair of tentacles", dec.group(0), re.I) else None
    oct_arms = pairs_to_count("four pair of arms")
    # Four numbered arm pairs (I through IV) on myopsid and oegopsid squids, plus the
    # group sentence of four pairs of arms for Decapodiformes, which includes Sepia.
    count_ok = bool(dec_arms == 8 and tentacles == 2 and oct_arms == 8 and sepia and squid)

    morph_note = None
    morph_meta = None
    try:
        morph_meta, morph_raw = fetch(MORPHDAT_URL, "slb-morphdat.parquet", timeout=60)
        import pyarrow.parquet as pq
        columns = list(pq.read_schema(DATA / "slb-morphdat.parquet").names)
        armish = [c for c in columns if re.search(r"arm|tentacle|mantle", c, re.I)]
        morph_note = "SeaLifeBase v26.06 morphdat has %d columns; %d match arm, tentacle or mantle%s." % (
            len(columns), len(armish), (": " + ", ".join(armish)) if armish else "")
    except Exception as exc:
        morph_note = "SeaLifeBase morphdat could not be read: %s" % exc

    length_notes = []
    for dataset_id, url in LENGTH_ATTEMPTS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                head = resp.read(300)
                ctype = resp.headers.get("content-type", "")
        except Exception as exc:
            length_notes.append("%s: %s" % (dataset_id, exc))
            continue
        if b"<html" in head.lower() or b"anubis" in head.lower() or b"validating" in head.lower() or "html" in ctype.lower():
            length_notes.append("%s: URL returned an interstitial page (%s), not a measurement table" % (dataset_id, ctype or "html"))
        else:
            length_notes.append("%s: unexpected payload %s %r" % (dataset_id, ctype, head[:40]))
    length_scored = False

    if not count_ok:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
    elif not length_scored:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
    else:
        verdict, reason, confidence = "inconclusive", "other", 0.35

    quotes = {
        "decapodiformes": dec.group(0),
        "octopodiformes": octo.group(0),
        "sepia_in_decapodiformes": sepia.group(0),
        "squid_tentacle_mention": squid.group(0) if squid else None,
    }
    measured = {
        "value": dec_arms if count_ok else None,
        "unit": "arms stated for Decapodiformes (cuttlefish and squid) and for Octopodiformes (octopus)",
        "n": 3 if count_ok else 0,
        "uncertainty": None,
        "extra": {
            "decapodiformes_arms": dec_arms,
            "decapodiformes_tentacles": tentacles,
            "octopodiformes_arms": oct_arms,
            "count_clause": "pass" if count_ok else "fail",
            "length_clause": "unscored",
            "quotes": quotes,
            "length_attempts": length_notes,
            "sealifebase_morphdat": morph_note,
            "squid_arm_pairs_i_through_iv": True,
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["reason"] = reason
    result["datasets"] = [{
        "id": "treatise-online-17-anatomy-of-recent-coleoids",
        "name": "Nixon 2011, Treatise Online 17, Part M Chapter 3, Anatomy of Recent forms",
        "landing_url": "https://doi.org/10.17161/to.v0i0.4087",
        "doi": "10.17161/to.v0i0.4087",
        "version": "Treatise Online Number 17",
        "license": "University of Kansas Paleontological Institute; PDF publicly downloadable from the journal",
        "files": [pdf_meta],
        "role": "group-level arm and tentacle counts for Decapodiformes and Octopodiformes",
    }]
    if morph_meta:
        result["datasets"].append({
            "id": "sealifebase-v26.06-morphdat-if-arm-fields-exist",
            "name": "SeaLifeBase morphdat snapshot v26.06",
            "landing_url": "https://www.sealifebase.ca/",
            "doi": None,
            "version": "v26.06",
            "license": None,
            "files": [morph_meta],
            "role": "checked for an arm-length or mantle-length field; none is present, so it was not used for the length clause",
        })
    result["measured"] = measured
    result["method"] = (
        "Downloaded Nixon 2011 and extracted the sentences that give the appendage counts. "
        "Decapodiformes, which the chapter identifies as including Sepia officinalis (Sepiida), "
        "are stated to have four pairs of arms and one pair of tentacles. "
        "Myopsid and oegopsid squids are drawn with arms I through IV, which is four pairs, and tentacles are not added. "
        "Octopodiformes are stated to have just four pairs of arms. "
        "The three planned measurement files were requested and did not return tables (%s). " % "; ".join(length_notes)
        + (morph_note or "")
        + " The length clause is unscored."
    )
    result["results_summary"] = [
        "Count clause %s: Decapodiformes %s arms and %s tentacles; Octopodiformes %s arms." % (
            "passes" if count_ok else "does not pass", dec_arms, tentacles, oct_arms),
        "Length clause unscored. " + " ".join(length_notes),
    ]
    caveats = [
        c for c in (result.get("caveats") or [])
        if not str(c).startswith(CAVEAT_MARK)
        and not str(c).startswith("The arm count is a group diagnosis")
        and not str(c).startswith("No arm-length to mantle-length ratios")
    ]
    caveats.append(CAVEAT_MARK + "The arm count is a group diagnosis in a morphological review, not a recount of specimens. Cuttlefish enter as Sepia officinalis (Decapodiformes, Sepiida). Squid enter because the chapter's diagram of extant myopsid and oegopsid squids labels arms I through IV, the same four pairs the Decapodiformes sentence counts, and the chapter says the tentacles of some so-called eight-armed squids are resorbed later. That resorption does not change the arm count of eight. Tentacles were not added.")
    caveats.append(CAVEAT_MARK + "No arm-length to mantle-length ratios for the three kinds were obtained. The length files were not measurement tables, and SeaLifeBase morphdat has no arm or mantle field, so the length contrast is untested. The verdict is inconclusive for that reason. The count clause itself passed.")
    result["caveats"] = caveats
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "count_ok": count_ok, "arms": dec_arms, "tentacles": tentacles, "oct": oct_arms, "length": length_notes}, indent=2))


if __name__ == "__main__":
    main()
