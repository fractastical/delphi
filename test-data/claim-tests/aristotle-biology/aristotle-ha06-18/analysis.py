#!/usr/bin/env python3
"""Cetacean reproductive mode from WoRMS Marine Species Traits.

Pre-registered before this run: supports only if at least 15 accepted extant
cetacean species are coded viviparous, none oviparous or ovoviviparous, and
both a dolphin family and a whale family are represented. Any oviparous species
refutes. Fewer than 15 coded species, with no taxon-wide viviparous attribute
on Cetacea, is inconclusive / underpowered. Mammal classification is not
treated as evidence of live birth.

Run: python3 analysis.py
"""

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-ha06-18)"
CETACEA = 2688
WHALE_FAMILIES = {
    "Balaenidae",
    "Balaenopteridae",
    "Eschrichtiidae",
    "Neobalaenidae",
    "Physeteridae",
    "Kogiidae",
    "Ziphiidae",
    "Monodontidae",
}
MODE_TYPE = "modes of reproduction"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_json(url, dest: Path, pause=0.2):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        raw = dest.read_bytes()
        retrieved = datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        final = url
    else:
        time.sleep(pause)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
                final = resp.geturl()
        except urllib.error.HTTPError as exc:
            # An empty attribute list is sometimes a 204 or an empty body.
            detail = exc.read()
            if exc.code in (204, 404) or not detail.strip():
                raw = b"[]"
                final = url
            else:
                raise
        dest.write_bytes(raw)
        retrieved = now()
    info = {
        "download_url": final,
        "requested_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "path": str(dest.relative_to(HERE)),
    }
    text = raw.decode("utf-8", errors="replace").strip()
    payload = json.loads(text) if text else []
    return info, payload


def classify(value):
    text = (value or "").strip().lower()
    if re.search(r"ovovivipar", text):
        return "ovoviviparous"
    if re.search(r"egg-?lay|ovipar", text) and not re.search(r"vivipar", text):
        return "oviparous"
    if re.search(r"vivipar|live-?bear|live birth", text):
        return "viviparous"
    if text:
        return "other"
    return None


def flatten_attributes(nodes, found):
    for node in nodes or []:
        mtype = (node.get("measurementType") or "").strip().lower()
        if mtype == MODE_TYPE:
            found.append(
                {
                    "value": node.get("measurementValue"),
                    "class": classify(node.get("measurementValue")),
                    "reference": node.get("reference"),
                    "qualitystatus": node.get("qualitystatus"),
                    "inherited_from": node.get("AphiaID_Inherited"),
                    "source_id": node.get("source_id"),
                }
            )
        flatten_attributes(node.get("children"), found)


def children(aphia_id):
    rows = []
    offset = 1
    while True:
        url = (
            "https://www.marinespecies.org/rest/AphiaChildrenByAphiaID/"
            f"{aphia_id}?marine_only=false&offset={offset}"
        )
        info, payload = fetch_json(url, DATA / "children" / f"{aphia_id}-offset-{offset}.json", pause=0.15)
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(payload)
        if len(payload) < 50:
            break
        offset += len(payload)
        if offset > 5000:
            break
    return rows


def accepted_species():
    species = []
    seen = set()
    stack = [CETACEA]
    while stack:
        aphia = stack.pop()
        if aphia in seen:
            continue
        seen.add(aphia)
        for child in children(aphia):
            status = (child.get("status") or "").lower()
            if status != "accepted":
                continue
            if child.get("isExtinct") == 1:
                continue
            cid = child.get("AphiaID")
            rank = child.get("rank")
            if rank == "Species":
                species.append(
                    {
                        "AphiaID": cid,
                        "scientificname": child.get("scientificname"),
                        "authority": child.get("authority"),
                        "family": child.get("family"),
                        "genus": child.get("genus"),
                        "isExtinct": child.get("isExtinct"),
                        "status": child.get("status"),
                        "url": child.get("url"),
                    }
                )
            elif cid and rank != "Species":
                stack.append(cid)
    species.sort(key=lambda s: (s["family"] or "", s["scientificname"] or ""))
    return species


def main():
    cetacea_info, cetacea_attrs = fetch_json(
        f"https://www.marinespecies.org/rest/AphiaAttributesByAphiaID/{CETACEA}",
        DATA / "attributes" / f"{CETACEA}.json",
        pause=0.0,
    )
    group_modes = []
    flatten_attributes(cetacea_attrs, group_modes)

    species = accepted_species()
    coded = []
    errors = []
    for sp in species:
        url = f"https://www.marinespecies.org/rest/AphiaAttributesByAphiaID/{sp['AphiaID']}"
        try:
            info, attrs = fetch_json(url, DATA / "attributes" / f"{sp['AphiaID']}.json")
        except Exception as exc:  # noqa: BLE001 — recorded, not hidden
            errors.append({"AphiaID": sp["AphiaID"], "name": sp["scientificname"], "error": str(exc)})
            continue
        modes = []
        flatten_attributes(attrs, modes)
        sp["modes"] = modes
        sp["attribute_byte_size"] = info["byte_size"]
        sp["attribute_sha256"] = info["sha256"]
        sp["attribute_retrieved_at"] = info["retrieved_at"]
        if modes:
            coded.append(sp)

    classes = []
    for sp in coded:
        for mode in sp["modes"]:
            classes.append(mode["class"])
    n_viv = sum(1 for sp in coded if sp["modes"] and all(m["class"] == "viviparous" for m in sp["modes"]))
    n_ovi = sum(1 for sp in coded if any(m["class"] == "oviparous" for m in sp["modes"]))
    n_ovo = sum(1 for sp in coded if any(m["class"] == "ovoviviparous" for m in sp["modes"]))
    n_other = sum(1 for sp in coded if any(m["class"] == "other" for m in sp["modes"]))
    families_coded = sorted({sp["family"] for sp in coded if sp.get("family")})
    has_dolphin = any(sp.get("family") == "Delphinidae" for sp in coded)
    has_whale = any(sp.get("family") in WHALE_FAMILIES for sp in coded)
    group_classes = [m["class"] for m in group_modes]
    group_viv = bool(group_modes) and all(c == "viviparous" for c in group_classes)
    group_ovi = any(c == "oviparous" for c in group_classes)

    if n_ovi or group_ovi:
        verdict, reason, confidence = "refutes", None, 0.85
    elif n_ovo or n_other:
        verdict, reason, confidence = "mixed", None, 0.6
    elif len(coded) >= 15 and n_viv == len(coded) and has_dolphin and has_whale and n_ovi == 0:
        verdict, reason, confidence = "supports", None, 0.85
    elif len(coded) < 15 and group_viv and n_ovi == 0:
        verdict, reason, confidence = "supports", None, 0.5
    elif errors and not species:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.4
    elif len(coded) < 15 and not group_viv:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.8
    else:
        # At least 15 viviparous records but missing dolphin or whale coverage.
        verdict, reason, confidence = "inconclusive", "underpowered", 0.55

    attr_paths = sorted((DATA / "attributes").glob("*.json")) if (DATA / "attributes").exists() else []
    attr_blob = b"".join(p.read_bytes() for p in attr_paths)
    child_paths = sorted((DATA / "children").glob("*.json")) if (DATA / "children").exists() else []
    child_blob = b"".join(p.read_bytes() for p in child_paths)

    measured = {
        "value": len(coded),
        "unit": "accepted extant cetacean species with a WoRMS mode of reproduction",
        "n": len(species),
        "uncertainty": None,
        "extra": {
            "accepted_extant_species": len(species),
            "species_with_mode": len(coded),
            "viviparous_species": n_viv,
            "oviparous_species": n_ovi,
            "ovoviviparous_species": n_ovo,
            "other_mode_species": n_other,
            "families_with_a_mode": families_coded,
            "delphinidae_coded": has_dolphin,
            "whale_family_coded": has_whale,
            "cetacea_group_modes": group_modes,
            "attribute_errors": errors,
            "coded_species": [
                {
                    "AphiaID": sp["AphiaID"],
                    "scientificname": sp["scientificname"],
                    "family": sp["family"],
                    "modes": sp["modes"],
                }
                for sp in coded
            ],
        },
    }
    summary_rows = [
        {
            "AphiaID": sp["AphiaID"],
            "scientificname": sp["scientificname"],
            "family": sp["family"],
            "genus": sp["genus"],
            "isExtinct": sp["isExtinct"],
            "mode_values": [m["value"] for m in sp.get("modes") or []],
            "mode_classes": [m["class"] for m in sp.get("modes") or []],
        }
        for sp in species
    ]
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "species-modes.json").write_text(json.dumps(summary_rows, indent=2) + "\n", encoding="utf-8")
    (DERIVED / "measured.json").write_text(
        json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    result["status"] = "complete"
    result["data_kind"] = "biological" if species else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "worms-cetacea-modes-of-reproduction",
            "name": "World Register of Marine Species, Cetacea checklist and Marine Species Traits attributes",
            "landing_url": "https://www.marinespecies.org/aphia.php?p=taxdetails&id=2688",
            "doi": None,
            "version": "live REST, retrieved " + now()[:10],
            "license": "CC BY 4.0",
            "files": [
                {
                    "name": "AphiaChildrenByAphiaID pages under Cetacea, concatenated in path order",
                    "download_url": "https://www.marinespecies.org/rest/AphiaChildrenByAphiaID/2688?marine_only=false&offset=1",
                    "retrieved_at": cetacea_info["retrieved_at"],
                    "byte_size": len(child_blob),
                    "sha256": hashlib.sha256(child_blob).hexdigest(),
                },
                {
                    "name": "AphiaAttributesByAphiaID for Cetacea and each accepted species, concatenated in AphiaID order",
                    "download_url": "https://www.marinespecies.org/rest/AphiaAttributesByAphiaID/2688",
                    "retrieved_at": cetacea_info["retrieved_at"],
                    "byte_size": len(attr_blob),
                    "sha256": hashlib.sha256(attr_blob).hexdigest(),
                },
            ],
            "role": "accepted cetacean species and the Modes of reproduction trait where WoRMS has recorded it",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Accepted children of Cetacea (AphiaID 2688) were walked through the WoRMS REST service. "
        "Unaccepted names and records with isExtinct = 1 were dropped. For Cetacea itself and for every "
        "accepted species reached, AphiaAttributesByAphiaID was read and measurement type "
        "'Modes of reproduction' was classified as viviparous, oviparous, ovoviviparous or other "
        "by the pre-registered string rules. Being a mammal was not counted as viviparity. "
        "The pass and fail thresholds in this file were then applied."
    )
    result["results_summary"] = [
        f"Accepted species reached: {len(species)}. Species with a mode of reproduction: {len(coded)}.",
        f"Among coded species, viviparous {n_viv}, oviparous {n_ovi}, ovoviviparous {n_ovo}, other {n_other}.",
        f"Cetacea group-level modes: {group_modes or 'none'}. Attribute errors: {len(errors)}.",
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + f" at confidence {confidence}.",
    ]
    note = (
        f"The checklist walk returned {len(species)} accepted species and {len(coded)} reproduction-mode "
        "records. An empty trait is a property of this source, not an inference that the species lays eggs or gives birth."
    )
    result.setdefault("caveats", [])
    if note not in result["caveats"]:
        result["caveats"].append(note)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "reason": reason, "n_species": len(species), "n_coded": len(coded), "confidence": confidence}, indent=2))


if __name__ == "__main__":
    main()
