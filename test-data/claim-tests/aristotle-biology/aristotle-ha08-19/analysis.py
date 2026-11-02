#!/usr/bin/env python3
"""Maximum recorded longevity of Camelus for aristotle-ha08-19.

Refute if the longest curated maximum is under 60 years. Mixed if it is
60 years or more, because a maximum cannot confirm an ordinary life of
about thirty years. Criteria were committed before this download.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/1.0"
ANAGE = ("https://genomics.senescence.info/species/dataset.zip", 169150, "e3ddb66e32e973a79932859ba53013e8f60d957c6ec01c6eb573e3ea3018d630")
PAN = ("https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt", 2359096, "36e64314cae0394a966a63b949504d1975ac5c5629e05e36c1b139b3348f044a")


def num(text):
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if not s or s.lower() in {"na", "nan", "null", "-"}:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if not math.isfinite(value) or value == -999:
        return None
    return value


def fetch(url, dest, size, sha):
    DATA.mkdir(parents=True, exist_ok=True)
    raw = dest.read_bytes() if dest.exists() else b""
    if hashlib.sha256(raw).hexdigest() != sha or len(raw) != size:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
    got = hashlib.sha256(raw).hexdigest()
    if got != sha or len(raw) != size:
        raise RuntimeError(f"checksum mismatch {dest.name}: {got} {len(raw)}")
    return {
        "name": dest.name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": got,
    }, raw


def anage_camels(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        text = zf.read("anage_data.txt").decode("utf-8")
    out = []
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        if row.get("Genus", "").strip().lower() != "camelus":
            continue
        years = num(row.get("Maximum longevity (yrs)"))
        if years is None or years <= 0:
            continue
        out.append({
            "source": "anage-build-15",
            "species": f"{row['Genus'].strip()} {row['Species'].strip()}",
            "maximum_longevity_years": years,
            "specimen_origin": row.get("Specimen origin", ""),
            "data_quality": row.get("Data quality", ""),
            "sample_size": row.get("Sample size", ""),
        })
    return out


def pantheria_camels(raw):
    text = raw.decode("utf-8", errors="replace")
    out = []
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        binomial = row.get("MSW05_Binomial", "").strip()
        if not binomial.lower().startswith("camelus "):
            continue
        months = num(row.get("17-1_MaxLongevity_m"))
        if months is None or months <= 0:
            continue
        out.append({
            "source": "pantheria-1-0-wr05-aug2008",
            "species": binomial,
            "maximum_longevity_years": months / 12.0,
            "maximum_longevity_months": months,
        })
    return out


def settle_caveats(existing, additions):
    stale = (
        "has not been downloaded",
        "have not been re-hashed",
        "No maturity value has been read",
        "No Camelus number has been read",
        "No age has been read",
        "No species habitat value has been read",
        "No body mass or litter size has been read",
        "No brain or body mass value has been read",
    )
    kept = []
    for item in list(existing) + list(additions):
        if any(mark in item for mark in stale):
            continue
        if item not in kept:
            kept.append(item)
    return kept


def main():
    anage_meta, anage_raw = fetch(ANAGE[0], DATA / "dataset.zip", ANAGE[1], ANAGE[2])
    pan_meta, pan_raw = fetch(PAN[0], DATA / "PanTHERIA_1-0_WR05_Aug2008.txt", PAN[1], PAN[2])
    records = anage_camels(anage_raw) + pantheria_camels(pan_raw)
    if not records:
        verdict, reason, M = "inconclusive", "data-unavailable", None
    else:
        reason = None
        M = max(r["maximum_longevity_years"] for r in records)
        if M < 60:
            verdict = "refutes"
        else:
            verdict = "mixed"
    if M is None:
        confidence = 0.4
    elif M < 40:
        confidence = 0.8
    elif M < 60:
        confidence = 0.65
    else:
        confidence = 0.55
    for rec in records:
        rec["in_20_to_45_years"] = 20 <= rec["maximum_longevity_years"] <= 45
    measured = {
        "value": M,
        "unit": "years, maximum of curated Camelus maximum longevities",
        "n": len(records),
        "uncertainty": None,
        "extra": {
            "records": records,
            "century_clause": None if M is None else ("supported" if M >= 90 else "intermediate" if M >= 60 else "refuted"),
            "about_thirty_measured": False,
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["datasets"] = [
        {
            "id": "anage-build-15",
            "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
            "landing_url": "https://genomics.senescence.info/species/",
            "doi": "10.1093/nar/gks1155",
            "version": "build 15",
            "license": "CC BY 3.0",
            "files": [anage_meta],
            "role": "maximum longevity of genus Camelus",
            "prior_record": "test-data/organisms/thompson-growth-form/ch08/datasets/anage-build-15.json",
        },
        {
            "id": "pantheria-1-0-wr05-aug2008",
            "name": "PanTHERIA 1.0 life-history table",
            "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
            "doi": "10.1890/08-1494.1",
            "version": "1.0 (WR05, Aug 2008)",
            "license": "Ecological Archives; reuse with citation",
            "files": [pan_meta],
            "role": "mammal maximum longevity in months for genus Camelus",
            "prior_record": "test-data/organisms/thompson-growth-form/ch04-05/datasets/pantheria-1-0-wr05-aug2008.json",
        },
    ]
    result["method"] = (
        "Downloaded AnAge build 15 and PanTHERIA, checked both SHA-256 checksums, and kept genus Camelus. "
        "AnAge maximum longevity is in years. PanTHERIA 17-1_MaxLongevity_m was divided by 12. "
        "M is the maximum across species and sources. Values of -999 and non-positive numbers were treated as missing."
    )
    result["measured"] = measured
    result["verdict"] = verdict
    result["data_kind"] = "none" if not records else "biological"
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    bits = ", ".join(f"{r['species']} {r['maximum_longevity_years']:.4g} y ({r['source']})" for r in records) or "no Camelus rows"
    result["results_summary"] = [
        f"Curated Camelus maxima: {bits}.",
        f"M = {M}. Century clause is {'unmeasured' if M is None else measured['extra']['century_clause']}. About thirty years is not measured by a maximum.",
    ]
    result["caveats"] = settle_caveats(result.get("caveats", []), [
        "A maximum near thirty years is compatible with the ordinary-lifespan clause and is still a refutation of the hundred-year clause under the pre-registered rule.",
    ])
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "measured": measured}, indent=2) + "\n")
    print(verdict, reason, "M", M, "n", len(records))


if __name__ == "__main__":
    main()
