#!/usr/bin/env python3
"""Maximum longevity of humans, elephants, and other animals in AnAge.

The decision rule is the pass_criterion committed in result.json before this
file was run. This script does not edit that criterion.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://genomics.senescence.info/species/dataset.zip"
LOCKED = {
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "claim_id",
    "claim_iri",
    "project",
    "preregistered_at",
    "interpretation",
}


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        last = None
        for i in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    dest.write_bytes(resp.read())
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 * (i + 1))
        else:
            raise last
    raw = dest.read_bytes()
    retrieved = dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def norm(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def pick(fieldnames, pred):
    for name in fieldnames:
        if pred(norm(name)):
            return name
    return None


def longevity(text):
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def write_result(fields):
    doc = json.loads(RESULT.read_text())
    for key in fields:
        if key in LOCKED:
            raise SystemExit("refusing to edit locked field " + key)
    doc.update(fields)
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")


def finish(verdict, reason, confidence, measured, datasets, method, summary, extra_caveat=None):
    doc = json.loads(RESULT.read_text())
    caveats = list(doc.get("caveats") or [])
    if extra_caveat:
        caveats.append(extra_caveat)
    fields = {
        "status": "complete",
        "datasets": datasets,
        "method": method,
        "measured": measured,
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none",
        "results_summary": summary,
        "caveats": caveats,
    }
    if verdict == "inconclusive":
        fields["reason"] = reason
        if reason == "data-unavailable":
            fields["data_kind"] = "none"
    write_result(fields)


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    info, raw = fetch(URL, DATA / "dataset.zip")
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        finish(
            "inconclusive",
            "data-unavailable",
            0.2,
            {"value": None, "unit": "species", "n": 0, "uncertainty": None, "extra": {"error": "bad zip"}},
            [{"id": "anage-build-dataset-zip", "name": "AnAge dataset.zip", "landing_url": "https://genomics.senescence.info/species/index.html", "doi": None, "version": None, "license": "HAGR licence; freely available, see https://genomics.senescence.info/legal.html", "files": [info], "role": "maximum longevity records"}],
            "The downloaded file was not a zip archive, so no longevity was read.",
            ["Download did not yield a zip archive."],
        )
        return
    text_name = next((n for n in zf.namelist() if n.lower().endswith(".txt")), None)
    if text_name is None:
        finish("inconclusive", "data-unavailable", 0.2, {"value": None, "unit": "species", "n": 0, "uncertainty": None, "extra": {"zip_entries": zf.namelist()}}, [], "No text table was inside the AnAge zip.", ["No text table inside the zip."])
        return
    table = zf.read(text_name).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(table), delimiter="\t"))
    if not rows:
        finish("inconclusive", "data-unavailable", 0.2, {"value": None, "unit": "species", "n": 0, "uncertainty": None, "extra": {}}, [], "The AnAge table had no rows.", ["Empty table."])
        return
    fields = rows[0].keys()
    c_king = pick(fields, lambda n: n == "kingdom")
    c_genus = pick(fields, lambda n: n == "genus")
    c_species = pick(fields, lambda n: n == "species")
    c_common = pick(fields, lambda n: "commonname" in n)
    c_long = pick(fields, lambda n: "maximum" in n and "longevity" in n)
    c_qual = pick(fields, lambda n: n == "dataquality")
    c_origin = pick(fields, lambda n: "specimenorigin" in n)
    if not all([c_genus, c_species, c_long, c_qual]):
        finish(
            "inconclusive",
            "other",
            0.3,
            {"value": None, "unit": "species", "n": 0, "uncertainty": None, "extra": {"columns": list(fields)}},
            [],
            "The AnAge header did not contain the pre-registered columns.",
            ["Required columns were absent: " + ", ".join(fields)],
        )
        return
    qualities = sorted({(r.get(c_qual) or "").strip().lower() for r in rows if (r.get(c_qual) or "").strip()})
    if "high" not in qualities or "acceptable" not in qualities:
        measured = {"value": None, "unit": "non-elephant species at or above the human record", "n": 0, "uncertainty": None, "extra": {"quality_tokens": qualities}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        finish("inconclusive", "other", 0.4, measured, [], "Data quality tokens were not the pre-registered pair high and acceptable, so no species was relabelled.", ["Quality tokens: " + ", ".join(qualities)])
        return

    admissible = []
    for row in rows:
        if c_king and (row.get(c_king) or "").strip().lower() != "animalia":
            continue
        years = longevity(row.get(c_long))
        quality = (row.get(c_qual) or "").strip().lower()
        if years is None or quality not in {"high", "acceptable"}:
            continue
        genus = (row.get(c_genus) or "").strip()
        species = (row.get(c_species) or "").strip()
        admissible.append({
            "genus": genus,
            "species": species,
            "binomial": (genus + " " + species).strip(),
            "common_name": (row.get(c_common) or "").strip() if c_common else "",
            "years": years,
            "quality": quality,
            "origin": (row.get(c_origin) or "").strip() if c_origin else "",
        })
    humans = [r for r in admissible if r["genus"].lower() == "homo" and r["species"].lower() == "sapiens"]
    elephants = [r for r in admissible if r["genus"].lower() in {"elephas", "loxodonta"}]
    if len(admissible) < 100 or not humans:
        reason = "underpowered" if humans else "data-unavailable"
        if len(admissible) < 100 and humans:
            reason = "underpowered"
        measured = {"value": None, "unit": "non-elephant species at or above the human record", "n": len(admissible), "uncertainty": None, "extra": {"n_admissible": len(admissible), "n_human_rows": len(humans)}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        finish( "inconclusive", reason, 0.35, measured, [], "The admissible set was below the pre-registered minimum or Homo sapiens was absent.", [f"Admissible rows: {len(admissible)}; human rows: {len(humans)}."])
        return
    human_years = max(r["years"] for r in humans)
    exceeders = [
        r for r in admissible
        if not (r["genus"].lower() == "homo" and r["species"].lower() == "sapiens")
        and r["genus"].lower() not in {"elephas", "loxodonta"}
        and r["years"] >= human_years
    ]
    exceeders.sort(key=lambda r: (-r["years"], r["binomial"]))
    elephant_max = max((r["years"] for r in elephants), default=None)
    n_exceed = len(exceeders)
    if n_exceed >= 1:
        verdict, confidence = "refutes", (0.85 if n_exceed >= 3 else 0.60)
    elif elephant_max is not None and elephant_max >= human_years:
        verdict, confidence = "supports", 0.70
    else:
        verdict, confidence = "mixed", 0.55
    measured = {
        "value": n_exceed,
        "unit": "non-elephant species with credible maximum longevity >= Homo sapiens",
        "n": len(admissible),
        "uncertainty": None,
        "extra": {
            "human_maximum_longevity_years": human_years,
            "n_human_rows": len(humans),
            "elephant_maximum_longevity_years": elephant_max,
            "elephant_rows": [{"binomial": r["binomial"], "years": r["years"], "quality": r["quality"], "origin": r["origin"]} for r in elephants],
            "n_exceed": n_exceed,
            "exceeding_species": [
                {"binomial": r["binomial"], "common_name": r["common_name"], "years": r["years"], "quality": r["quality"], "origin": r["origin"]}
                for r in exceeders[:15]
            ],
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    datasets = [{
        "id": "anage-build-dataset-zip",
        "name": "AnAge: The Animal Ageing and Longevity Database (latest stable build, dataset.zip)",
        "landing_url": "https://genomics.senescence.info/species/index.html",
        "doi": None,
        "version": "stable build served on the HAGR download page at retrieval",
        "license": "HAGR licence; the download page states the file is freely available. See https://genomics.senescence.info/legal.html",
        "files": [{**info, "name": "dataset.zip", "inner_file": text_name}],
        "role": "maximum longevity, data quality, and taxonomy for humans, elephants, and other animals",
    }]
    method = (
        "Downloaded the AnAge zip, opened the tab-separated table inside it, and kept Animalia rows "
        "with data quality high or acceptable and a positive maximum longevity. Compared the maximum "
        "Homo sapiens value with every other admissible species, leaving out Elephas and Loxodonta, "
        "and applied the pre-registered rule."
    )
    elephant_bit = "no admissible elephant row" if elephant_max is None else f"elephant maximum {elephant_max} years"
    summary = [
        f"Admissible rows: {len(admissible)}. Human maximum: {human_years} years. {elephant_bit}.",
        f"Non-elephant species at or above the human record: {n_exceed}.",
        "Verdict follows the pre-registered comparison and does not use assessor scores.",
    ]
    finish(verdict, None, confidence, measured, datasets, method, summary)
    print(verdict, n_exceed, human_years, elephant_max)


if __name__ == "__main__":
    main()
