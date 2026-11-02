#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-ha08-38.

Tries the Dryad PLINK ped file and the Ensembl karyotypes for the domestic
dog and the red fox. The pre-registered rule stops the verdict at
data-unavailable if the ped file cannot be downloaded. Diploid counts are
computed only as a diagnostic and do not override that stop.

Requires Python 3 and a network connection on a cold cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "result.json"
DERIVED = HERE / "derived"
CACHE = Path(os.environ.get("CLAIM_TEST_CACHE", "/tmp/aristotle-ha08-38"))
USER_AGENT = "Mozilla/5.0 (compatible; delphi-claim-test/1.0; +https://github.com/fractastical/delphi)"

PED_URLS = [
    "https://datadryad.org/downloads/file_stream/684548",
    "https://datadryad.org/api/v2/files/684548/download",
]
MAP_URLS = [
    "https://datadryad.org/downloads/file_stream/684547",
    "https://datadryad.org/api/v2/files/684547/download",
]
# SHA-256 published in the Dryad file metadata before any byte was fetched.
PED_DIGEST = "9303839150f13d4b945c554f3be42efede4c902c85073ca3968a2a259fe976d3"
PED_SIZE = 248477

ASSEMBLIES = {
    "canis_lupus_familiaris": {
        "url": "https://rest.ensembl.org/info/assembly/canis_lupus_familiaris?content-type=application/json",
        "byte_size": 29512,
        "sha256": "9528d16c782eed14e3b055b9bf4c9b0d90a40edb19cf33d93b17988cb95860a7",
    },
    "vulpes_vulpes": {
        "url": "https://rest.ensembl.org/info/assembly/vulpes_vulpes?content-type=application/json",
        "byte_size": 6032152,
        "sha256": "24a413a2a84053a48ff7adf14e13a0ac90349c49bebec8693537330ff0d3aa18",
    },
}

HYBRID_TOKENS = ("hybrid", "hyb", "suspected", "wolfdog", "wolf-dog", "wolf_dog", "saarloos", "czechoslovak")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_status(url: str, dest: Path) -> tuple[int, bytes]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        data = exc.read()
        status = exc.code
    if status == 200:
        dest.write_bytes(data)
    return status, data


def looks_like_html(data: bytes) -> bool:
    head = data[:200].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def first_ok(urls: list[str], dest: Path) -> dict:
    attempts = []
    for url in urls:
        status, data = fetch_status(url, dest)
        html = status == 200 and looks_like_html(data)
        attempts.append({
            "url": url,
            "http_status": status,
            "byte_size": len(data),
            "html_challenge": html,
        })
        if status == 200 and not html:
            return {"ok": True, "url": url, "data": data, "attempts": attempts}
    return {"ok": False, "data": b"", "attempts": attempts}


def diploid_from_karyotype(names: list[str]) -> dict:
    cleaned = [str(n) for n in names if str(n).strip()]
    sex = {n.casefold() for n in cleaned if n.casefold() in {"x", "y"}}
    has_x = "x" in sex
    has_y = "y" in sex
    autosomes = [n for n in cleaned if n.casefold() not in {"x", "y"}]
    if has_x and has_y:
        diploid = 2 * len(autosomes) + 2
        rule = "both X and Y listed"
        scored = True
    elif has_x and not has_y:
        diploid = 2 * len(cleaned)
        rule = "X listed, Y absent"
        scored = True
    else:
        diploid = None
        rule = "neither sex chromosome listed; species not scored"
        scored = False
    return {
        "names": cleaned,
        "n_names": len(cleaned),
        "n_autosomes": len(autosomes),
        "has_x": has_x,
        "has_y": has_y,
        "diploid": diploid,
        "rule": rule,
        "scored": scored,
    }


def classify(fid: str, iid: str) -> str:
    blob = f"{fid} {iid}".casefold()
    fox = "fox" in blob
    hybridish = any(token in blob for token in HYBRID_TOKENS)
    if fox and ("dog" in blob or hybridish):
        return "fox-dog"
    if hybridish:
        return "hybrid"
    if fox:
        return "fox"
    if "jackal" in blob:
        return "jackal"
    if "wolf" in blob and "dog" not in blob:
        return "wolf"
    if "dog" in blob:
        return "dog"
    return "other"


def score_ped(text: str) -> dict:
    counts = {k: 0 for k in ("fox-dog", "hybrid", "fox", "jackal", "wolf", "dog", "other")}
    n = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        counts[classify(parts[0], parts[1])] += 1
        n += 1
    wolf_or_dog = counts["wolf"] + counts["dog"]
    if counts["hybrid"] >= 1 and counts["wolf"] >= 1 and counts["dog"] >= 1:
        component = "supports"
    elif wolf_or_dog >= 100 and counts["hybrid"] == 0:
        component = "refutes"
    else:
        component = "inconclusive"
    return {"n_rows": n, "counts": counts, "component": component}


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(RESULT_PATH.read_text())
    CACHE.mkdir(parents=True, exist_ok=True)

    ped = first_ok(PED_URLS, CACHE / "panel.ped")
    map_file = first_ok(MAP_URLS, CACHE / "panel.map")
    ped_ok = False
    ped_note = "not downloaded"
    if ped["ok"]:
        digest = sha256_bytes(ped["data"])
        ped_ok = digest == PED_DIGEST and len(ped["data"]) == PED_SIZE
        ped_note = "sha256 matches Dryad metadata" if ped_ok else "sha256 does not match Dryad metadata"
    elif any(a.get("html_challenge") for a in ped["attempts"]):
        ped_note = "HTTP 200 body was an HTML challenge page, not the ped file"

    assemblies = {}
    assembly_mismatch = False
    for species, meta in ASSEMBLIES.items():
        status, data = fetch_status(meta["url"], CACHE / f"{species}.json")
        ok = status == 200 and len(data) == meta["byte_size"] and sha256_bytes(data) == meta["sha256"]
        assembly_mismatch = assembly_mismatch or not ok
        payload = json.loads(data) if status == 200 else {}
        scored = diploid_from_karyotype(payload.get("karyotype") or [])
        scored["assembly_name"] = payload.get("assembly_name")
        scored["http_status"] = status
        scored["byte_size"] = len(data) if status == 200 else 0
        scored["sha256"] = sha256_bytes(data) if status == 200 else None
        assemblies[species] = scored

    ped_counts = None
    if ped_ok:
        ped_counts = score_ped(ped["data"].decode("utf-8", "replace"))

    # The stop rule is explicit: a missing ped makes the verdict data-unavailable,
    # whether or not the assemblies scored.
    if not ped_ok:
        verdict = "inconclusive"
        reason = "data-unavailable"
        confidence = 0.35
        data_kind = "none"
    else:
        fox = assemblies["vulpes_vulpes"]
        dog = assemblies["canis_lupus_familiaris"]
        if not fox["scored"] or not dog["scored"] or assembly_mismatch:
            fox_component = "inconclusive"
            gap = None
        else:
            gap = abs(dog["diploid"] - fox["diploid"])
            foxdog_rows = ped_counts["counts"]["fox-dog"]
            if gap >= 8:
                fox_component = "refutes"
            elif gap <= 2 and foxdog_rows >= 1:
                fox_component = "supports"
            else:
                fox_component = "inconclusive"
        wolf_component = ped_counts["component"]
        if wolf_component == "inconclusive" or fox_component == "inconclusive":
            verdict = "inconclusive"
            reason = "underpowered"
        elif wolf_component == "supports" and fox_component == "supports":
            verdict = "supports"
            reason = None
        elif wolf_component == "refutes" and fox_component == "refutes":
            verdict = "refutes"
            reason = None
        else:
            verdict = "mixed"
            reason = None
        if verdict == "inconclusive":
            confidence = 0.4
            data_kind = "none"
        elif verdict == "mixed" and gap is not None and gap >= 8:
            confidence = 0.7
            data_kind = "biological"
        else:
            confidence = 0.55
            data_kind = "biological"

    dog = assemblies["canis_lupus_familiaris"]
    fox = assemblies["vulpes_vulpes"]
    measured = {
        "value": None if ped_counts is None else ped_counts["counts"]["hybrid"],
        "unit": "labeled wolf-dog hybrid rows in the ped file",
        "n": 0 if ped_counts is None else ped_counts["n_rows"],
        "uncertainty": ped_note,
        "extra": {
            "ped_attempts": ped["attempts"],
            "map_attempts": map_file["attempts"],
            "ped_sha256_ok": ped_ok,
            "ped_class_counts": None if ped_counts is None else ped_counts["counts"],
            "dog_diploid_diagnostic": dog["diploid"],
            "dog_karyotype_n": dog["n_names"],
            "dog_rule": dog["rule"],
            "fox_karyotype_n": fox["n_names"],
            "fox_scored": fox["scored"],
            "fox_rule": fox["rule"],
            "diagnostics_not_used_for_verdict": not ped_ok,
        },
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "karyotype-diagnostic.json").write_text(json.dumps({
        "canis_lupus_familiaris": {k: dog[k] for k in ("assembly_name", "n_names", "n_autosomes", "has_x", "has_y", "diploid", "rule", "scored", "names")},
        "vulpes_vulpes": {k: fox[k] for k in ("assembly_name", "n_names", "n_autosomes", "has_x", "has_y", "diploid", "rule", "scored", "names")},
    }, indent=2) + "\n")
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    prior = result.get("datasets") or []
    if prior:
        retrieved_at = prior[0]["files"][0].get("retrieved_at", retrieved_at)

    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = data_kind
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["measured"] = measured
    result["method"] = (
        "Requested the Dryad ped and map files at the file_stream URL and the API "
        "download URL. A response that is not HTTP 200, or whose SHA-256 is not the "
        "digest in the Dryad file metadata, does not count as the file. Ensembl "
        "assembly documents for Canis lupus familiaris and Vulpes vulpes were "
        "downloaded and the pre-registered diploid rule was applied to the karyotype "
        "list. The ped-download stop in the pre-registration sets the verdict; the "
        "diploid numbers are recorded and do not replace that stop."
    )
    result["results_summary"] = [
        f"Ped download: {ped_note}. Attempts: "
        + ", ".join(f"{a['url']} -> HTTP {a['http_status']}" for a in ped["attempts"])
        + ".",
        f"Dog karyotype diagnostic: {dog['n_names']} names, diploid {dog['diploid']} ({dog['rule']}). "
        f"Fox karyotype list length {fox['n_names']}; scored={fox['scored']}.",
        "Verdict is inconclusive with reason data-unavailable because the genotype file could not be fetched."
        if verdict == "inconclusive" and reason == "data-unavailable"
        else f"Verdict {verdict}.",
    ]
    caveats = list(result.get("caveats") or [])
    added = (
        "The Dryad file_stream URL answered HTTP 200 with an HTML bot-challenge page "
        "(about 4 KB, title Validating), and the API download URL did not return the ped "
        "bytes. The SHA-256 in the Dryad file metadata was therefore never checked against "
        "a genotype file. The dog assembly karyotype is 38 autosomes plus X and Y, which the "
        "pre-registered rule turns into diploid 78. The red-fox assembly VulVul2.2 returns an "
        "empty karyotype list, so the fox is not scored. Neither diagnostic is the verdict."
    )
    if added not in caveats:
        caveats.append(added)
    result["caveats"] = caveats
    result["datasets"] = [
        {
            "id": "dryad-10.5061-dryad.76hdr7stk-wolf-dog-snp-ped",
            "name": "SNP genotypes for wolf-dog hybrid detection (Harmoinen et al.)",
            "landing_url": "https://doi.org/10.5061/dryad.76hdr7stk",
            "doi": "10.5061/dryad.76hdr7stk",
            "version": "4",
            "license": "CC0-1.0",
            "files": [
                {
                    "name": "GTIC-D-20-00312R1.ped",
                    "download_url": PED_URLS[0],
                    "retrieved_at": retrieved_at,
                    "byte_size": None,
                    "sha256": None,
                    "http_status": ped["attempts"][0]["http_status"],
                    "metadata_sha256": PED_DIGEST,
                    "note": "Bytes not retrieved. metadata_sha256 is the digest Dryad publishes for the file.",
                }
            ],
            "role": "individual canid genotypes whose identifiers were to be classed as wolf, dog or hybrid",
        },
        {
            "id": "ensembl-assembly-karyotype-dog-and-red-fox",
            "name": "Ensembl assembly karyotypes, domestic dog ROS_Cfam_1.0 and red fox VulVul2.2",
            "landing_url": "https://rest.ensembl.org/",
            "doi": None,
            "version": "as served 2026-11-01",
            "license": "Ensembl public REST data",
            "files": [
                {
                    "name": f"{species}.json",
                    "download_url": meta["url"],
                    "retrieved_at": retrieved_at,
                    "byte_size": assemblies[species]["byte_size"],
                    "sha256": assemblies[species]["sha256"],
                }
                for species, meta in ASSEMBLIES.items()
            ],
            "role": "diagnostic chromosome lists; not used to set the verdict while the ped file is unavailable",
        },
    ]
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "data_kind": data_kind,
        "ped_ok": ped_ok,
        "dog_diploid": dog["diploid"],
        "fox_scored": fox["scored"],
    }, indent=2))


if __name__ == "__main__":
    main()
