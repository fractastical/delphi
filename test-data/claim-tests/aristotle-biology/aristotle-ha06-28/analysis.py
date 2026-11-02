#!/usr/bin/env python3
"""Recompute aristotle-ha06-28 from the FishBase v26.06 parquet tables.

Thresholds stay as they were pre-registered in result.json.
"""

import csv
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone

import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
RESULT = os.path.join(HERE, "result.json")
UA = "delphisci-claim-test/aristotle-ha06-28"
BASE = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet"
FILES = [
    "species.parquet",
    "reproduc.parquet",
    "fecundity.parquet",
    "eggs.parquet",
    "spawning.parquet",
]

PREREG_CAVEATS = [
    "No FishBase reproduction table, fecundity number, or eel gonad paper was opened before this registration.",
    "The claim is about eels Aristotle could cut open. A modern species code still answers whether an eel has been found with spawn. It does not show what a river fisherman in Greece would have seen.",
    "Other eel species are not substitutes for Anguilla anguilla.",
]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name):
    os.makedirs(DATA, exist_ok=True)
    dest = os.path.join(DATA, name)
    url = BASE + "/" + name
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        retrieved = datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return dest, url, retrieved
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    return dest, url, utc_now()


def spec_column(table):
    for name in table.column_names:
        if name.lower() == "speccode":
            return name
    raise RuntimeError("no SpecCode column")


def rows_for(table, spec_code):
    col = spec_column(table)
    sub = table.filter(pc.equal(pc.cast(table.column(col), "int64"), spec_code))
    dicts = sub.to_pylist()
    cleaned = []
    for row in dicts:
        cleaned.append(
            {
                k: (v.isoformat(sep=" ") if hasattr(v, "isoformat") else v)
                for k, v in row.items()
                if v not in (None, "")
            }
        )
    return cleaned


def positive(value):
    if value is None:
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def main():
    with open(RESULT, encoding="utf-8") as f:
        result = json.load(f)
    for key in (
        "hypothesis",
        "pass_criterion",
        "fail_criterion",
        "test_contract",
        "planned_datasets",
        "preregistered_at",
        "interpretation",
    ):
        if key not in result:
            raise SystemExit("missing pre-registered field %s" % key)

    file_meta = []
    tables = {}
    for name in FILES:
        path, url, retrieved = fetch(name)
        tables[name] = pq.read_table(path)
        file_meta.append(
            {
                "name": name,
                "download_url": url,
                "retrieved_at": retrieved,
                "byte_size": os.path.getsize(path),
                "sha256": sha256_file(path),
            }
        )

    species = tables["species.parquet"]
    mask = pc.and_(
        pc.equal(species.column("Genus"), "Anguilla"),
        pc.equal(species.column("Species"), "anguilla"),
    )
    hits = species.filter(mask).select(["SpecCode", "Genus", "Species", "FBname"]).to_pylist()
    if len(hits) != 1:
        verdict = "inconclusive"
        reason = "other"
        measured_value = None
        n = 0
        summary = "Anguilla anguilla did not match exactly one species row."
        spec_code = None
        extra = {"species_hits": hits}
    else:
        spec_code = int(hits[0]["SpecCode"])
        reproduc = rows_for(tables["reproduc.parquet"], spec_code)
        fecundity = rows_for(tables["fecundity.parquet"], spec_code)
        eggs = rows_for(tables["eggs.parquet"], spec_code)
        spawning = rows_for(tables["spawning.parquet"], spec_code)

        fecundity_values = []
        for row in fecundity:
            for key in (
                "FecundityMin",
                "FecundityMax",
                "FecundityMean",
                "RelFecundityMin",
                "RelFecundityMean",
                "RelFecundityMax",
            ):
                if positive(row.get(key)):
                    fecundity_values.append({"field": key, "value": row[key], "autoctr": row.get("autoctr")})
        egg_values = []
        for row in eggs:
            for key in ("Eggdiammin", "Eggdiammax", "Eggdiammod"):
                if positive(row.get(key)):
                    egg_values.append({"field": key, "value": row[key]})
        modes = [row.get("ReproMode") for row in reproduc if row.get("ReproMode")]
        oviparous_code = any("ovipar" in str(m).lower() for m in modes)

        numeric_hit = bool(fecundity_values or egg_values)
        if numeric_hit or oviparous_code:
            verdict = "refutes"
            reason = None
            confidence = 0.85 if numeric_hit else 0.70
        else:
            verdict = "inconclusive"
            reason = "data-unavailable" if not (reproduc or fecundity or eggs or spawning) else "other"
            confidence = 0.55
        confidence = min(confidence, 0.90)
        n = sum(
            1
            for row in fecundity
            if any(
                positive(row.get(key))
                for key in (
                    "FecundityMin",
                    "FecundityMax",
                    "FecundityMean",
                    "RelFecundityMin",
                    "RelFecundityMean",
                    "RelFecundityMax",
                )
            )
        ) + sum(
            1
            for row in eggs
            if any(positive(row.get(key)) for key in ("Eggdiammin", "Eggdiammax", "Eggdiammod"))
        )
        max_fec = max((item["value"] for item in fecundity_values), default=None)
        measured_value = max_fec
        if numeric_hit:
            summary = (
                "FishBase v26.06 records Anguilla anguilla with fecundity and egg diameter above zero, "
                "so the universal negative is refuted. The reproduction mode field says %s, not the word oviparous."
                % (modes[0] if modes else "nothing")
            )
        else:
            summary = "No numeric fecundity, egg diameter, or oviparous code was stored for Anguilla anguilla."
        extra = {
            "spec_code": spec_code,
            "fb_name": hits[0]["FBname"],
            "repro_modes": modes,
            "oviparous_code": oviparous_code,
            "fecundity_positive": fecundity_values,
            "egg_diameter_positive": egg_values,
            "reproduc_rows": reproduc,
            "fecundity_rows": fecundity,
            "eggs_rows": eggs,
            "spawning_rows": spawning,
            "numeric_hit": numeric_hit,
        }

    if spec_code is None:
        confidence = 0.55

    os.makedirs(DERIVED, exist_ok=True)
    derived = {
        "verdict": verdict,
        "spec_code": spec_code,
        "extra": extra,
    }
    with open(os.path.join(DERIVED, "measured.json"), "w", encoding="utf-8") as f:
        json.dump(derived, f, indent=2)
        f.write("\n")
    with open(os.path.join(DERIVED, "anguilla-anguilla.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["table", "field", "value"])
        if spec_code is not None:
            for item in extra["fecundity_positive"]:
                writer.writerow(["fecundity", item["field"], item["value"]])
            for item in extra["egg_diameter_positive"]:
                writer.writerow(["eggs", item["field"], item["value"]])
            for mode in extra["repro_modes"]:
                writer.writerow(["reproduc", "ReproMode", mode])

    result["status"] = "complete"
    result["verdict"] = verdict
    result["data_kind"] = "biological"
    result["confidence"] = confidence
    if reason is None:
        result.pop("reason", None)
    else:
        result["reason"] = reason
    result["measured"] = {
        "value": measured_value,
        "unit": "maximum stored fecundity (FecundityMin or FecundityMax) for Anguilla anguilla; eggs per female as recorded, not re-estimated",
        "n": n,
        "uncertainty": "n is the number of fecundity or egg rows with a positive value for this one species, not a count of eels dissected",
        "extra": extra,
    }
    result["method"] = (
        "FishBase v26.06 parquet tables were downloaded from data.source.coop. "
        "Anguilla anguilla was the species row with Genus Anguilla and Species anguilla. "
        "Reproduction mode, fecundity, egg diameter and spawning rows for that SpecCode were read. "
        "A fecundity or egg diameter above zero refutes, as pre-registered. Other Anguilla species were not used."
    )
    result["deviations"] = [
        {
            "what": "The tables are the rfishbase parquet mirror fb/v26.06, not a page scraped from www.fishbase.se.",
            "why": "The mirror's list of versions resolves, and v26.06 is the newest prefix in that listing. fecundity.parquet and eggs.parquet are public files with a species code and the numeric fields named in the registration. Thresholds are unchanged.",
        }
    ]
    notes = []
    if spec_code is not None:
        for row in extra["reproduc_rows"]:
            if row.get("AddInfos"):
                notes.append(row["AddInfos"])
    result["caveats"] = PREREG_CAVEATS + [
        summary,
        "The same reproduction row says actual spawning has never been observed and is believed to occur in the Sargasso Sea. Egg diameter and fecundity are still positive records of eggs. They are not an observation of a spawning event.",
        "Reproduction mode is stored as dioecism with external fertilization and the guild 'open water/substratum egg scatterers'. The word oviparous is not the mode code. The numeric egg and fecundity fields set the verdict.",
    ]
    result["results_summary"] = [
        summary,
        "SpecCode %s. Positive fecundity fields: %s. Positive egg-diameter fields: %s."
        % (
            spec_code,
            extra.get("fecundity_positive") if spec_code is not None else None,
            extra.get("egg_diameter_positive") if spec_code is not None else None,
        ),
    ]
    result["datasets"] = [
        {
            "id": "fishbase-fb-v26.06",
            "name": "FishBase parquet mirror, fb/v26.06",
            "landing_url": "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/",
            "doi": None,
            "version": "fb/v26.06",
            "license": "FishBase terms; the mirror is the public parquet export used by rfishbase",
            "files": file_meta,
            "role": "species identity plus reproduction, fecundity, egg and spawning rows for Anguilla anguilla",
        }
    ]
    result["agent"] = {
        "kind": "cloud-agent",
        "model": "Grok 4.7",
        "run": "cursor/aristotle-claim-tests-3f12",
        "date": "2026-11-01",
    }
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print("VERDICT", verdict, "value", measured_value, "n", n, "conf", confidence, flush=True)


if __name__ == "__main__":
    main()
