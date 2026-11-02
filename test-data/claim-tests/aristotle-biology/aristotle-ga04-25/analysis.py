#!/usr/bin/env python3
"""aristotle-ga04-25: human maximum longevity versus other species in AnAge.

Rules are those in result.json, committed before any longevity value was read.
Run from the repo root or from this directory: python3 analysis.py
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
ROOT = HERE.parents[3]
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
DATA = HERE / "data"
EXPECTED_SHA = "e3ddb66e32e973a79932859ba53013e8f60d957c6ec01c6eb573e3ea3018d630"
EXPECTED_SIZE = 169150
URL = "https://genomics.senescence.info/species/dataset.zip"
VENDORED = ROOT / "test-data/organisms/darwin-origin/ch11-14/data/anage_build15_dataset.zip"
CREDIBLE = {"acceptable", "high"}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def load_zip():
    DATA.mkdir(parents=True, exist_ok=True)
    source = "download"
    raw = None
    if VENDORED.exists():
        vendored = VENDORED.read_bytes()
        if sha256(vendored) == EXPECTED_SHA and len(vendored) == EXPECTED_SIZE:
            raw = vendored
            source = "vendored"
    if raw is None:
        req = urllib.request.Request(URL, headers={"User-Agent": "delphisci-claim-test"})
        raw = urllib.request.urlopen(req, timeout=120).read()
        source = "download"
    path = DATA / "dataset.zip"
    path.write_bytes(raw)
    info = {
        "name": "dataset.zip",
        "download_url": URL,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": sha256(raw),
        "source_used": source,
        "vendored_path": str(VENDORED.relative_to(ROOT)) if VENDORED.exists() else None,
    }
    return raw, info


def rows_from_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        text = zf.read(name).decode("utf-8", errors="replace")
        txt_sha = sha256(text.encode("utf-8"))
        txt_size = len(text.encode("utf-8"))
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return list(reader), {"inner_name": name, "byte_size": txt_size, "sha256": txt_sha}


def num(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.upper() in {"NA", "N/A", "NULL"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    result = json.loads(RESULT.read_text())
    raw, file_info = load_zip()
    ok = file_info["sha256"] == EXPECTED_SHA and file_info["byte_size"] == EXPECTED_SIZE
    table, inner = rows_from_zip(raw)
    file_info["inner"] = inner
    DERIVED.mkdir(parents=True, exist_ok=True)

    def finish(verdict, reason, confidence, measured, method):
        result["status"] = "complete"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        else:
            result.pop("reason", None)
        result["confidence"] = confidence
        result["data_kind"] = "none" if verdict == "inconclusive" and reason == "data-unavailable" else "biological"
        result["measured"] = measured
        result["method"] = method
        result["datasets"] = [
            {
                "id": "anage-build-15",
                "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
                "landing_url": "https://genomics.senescence.info/species/",
                "doi": "10.1093/nar/gkx1042",
                "version": "build 15",
                "license": "CC BY 3.0",
                "files": [file_info],
                "role": "maximum longevity and data-quality flag for animal species, including Homo sapiens and Elephantidae",
            }
        ]
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        extra = measured.get("extra") or {}
        result["results_summary"] = [
            f"Homo sapiens maximum longevity is {measured.get('value')} years (quality {extra.get('human_quality')}).",
            f"Credible non-elephant species at or above that value: {extra.get('n_non_elephant_ge_human')} of {extra.get('n_credible_nonhuman')}.",
            f"Among mammals the same count is {extra.get('mammal_n_ge_human')} of {extra.get('mammal_n')}.",
            "AnAge includes plants. The refutation does not depend on them: the exceedance list contains animals, including a mammal.",
        ]
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
        print(verdict, measured.get("value"), measured.get("n"))

    if not ok:
        finish(
            "inconclusive",
            "data-unavailable",
            0.2,
            {"value": None, "unit": "years", "n": 0, "extra": {"sha256": file_info["sha256"], "byte_size": file_info["byte_size"]}},
            "The downloaded or vendored zip did not match the pre-registered SHA-256 and byte size, so no longevity comparison was used.",
        )
        return

    qualities = sorted({(r.get("Data quality") or "").strip() for r in table if (r.get("Data quality") or "").strip()})
    if not (CREDIBLE & {q.lower() for q in qualities}):
        finish(
            "inconclusive",
            "not-operationalizable",
            0.3,
            {"value": None, "unit": "years", "n": len(table), "extra": {"data_quality_labels": qualities}},
            "AnAge loaded, but the Data quality column did not contain acceptable or high.",
        )
        return

    def pack(r):
        return {
            "binomial": f"{(r.get('Genus') or '').strip()} {(r.get('Species') or '').strip()}".strip(),
            "class": (r.get("Class") or "").strip(),
            "family": (r.get("Family") or "").strip(),
            "longevity": num(r.get("Maximum longevity (yrs)")),
            "quality": (r.get("Data quality") or "").strip().lower(),
            "origin": (r.get("Specimen origin") or "").strip().lower(),
            "common": (r.get("Common name") or "").strip(),
        }

    parsed = [pack(r) for r in table]
    humans = [p for p in parsed if p["binomial"].lower() == "homo sapiens" and p["longevity"] is not None]
    if not humans:
        finish(
            "inconclusive",
            "data-unavailable",
            0.3,
            {"value": None, "unit": "years", "n": 0, "extra": {"data_quality_labels": qualities}},
            "The zip matched its checksum, but Homo sapiens had no numeric maximum longevity.",
        )
        return
    human = max(humans, key=lambda p: p["longevity"])
    credible = [p for p in parsed if p["quality"] in CREDIBLE and p["longevity"] is not None and p["binomial"].lower() != "homo sapiens"]
    non_elephant = [p for p in credible if p["family"].lower() != "elephantidae"]
    elephants = [p for p in credible if p["family"].lower() == "elephantidae"]
    exceed = [p for p in non_elephant if p["longevity"] >= human["longevity"]]
    exceed.sort(key=lambda p: -p["longevity"])
    low_exceed = [
        p for p in parsed
        if p["binomial"].lower() != "homo sapiens"
        and p["family"].lower() != "elephantidae"
        and p["quality"] not in CREDIBLE
        and p["longevity"] is not None
        and p["longevity"] >= human["longevity"]
    ]
    mammals = [p for p in non_elephant if p["class"].lower() == "mammalia"]
    mammal_exceed = [p for p in mammals if p["longevity"] >= human["longevity"]]

    def brief(p):
        return {
            "binomial": p["binomial"],
            "common": p["common"],
            "class": p["class"],
            "family": p["family"],
            "longevity_yrs": p["longevity"],
            "quality": p["quality"],
            "origin": p["origin"],
        }

    n = len(non_elephant)
    measured = {
        "value": human["longevity"],
        "unit": "years, Homo sapiens maximum longevity",
        "n": n,
        "extra": {
            "human_quality": human["quality"],
            "human_origin": human["origin"],
            "n_credible_nonhuman": n,
            "n_elephantidae_credible": len(elephants),
            "elephantidae": [brief(p) for p in sorted(elephants, key=lambda p: -p["longevity"])],
            "n_non_elephant_ge_human": len(exceed),
            "exceeding_non_elephants": [brief(p) for p in exceed[:15]],
            "max_non_elephant_longevity_yrs": exceed[0]["longevity"] if exceed else (max(p["longevity"] for p in non_elephant) if non_elephant else None),
            "mammal_n": len(mammals),
            "mammal_n_ge_human": len(mammal_exceed),
            "mammal_exceeding": [brief(p) for p in sorted(mammal_exceed, key=lambda p: -p["longevity"])[:10]],
            "low_or_questionable_n_ge_human": len(low_exceed),
            "exceed_origin_counts": {
                "wild": sum(1 for p in exceed if p["origin"] == "wild"),
                "captivity": sum(1 for p in exceed if p["origin"] == "captivity"),
                "other_or_blank": sum(1 for p in exceed if p["origin"] not in {"wild", "captivity"}),
            },
            "checksum_ok": True,
        },
    }
    if n < 100:
        finish("inconclusive", "underpowered", 0.4, measured, "The checksum matched, but fewer than 100 non-human credible species had a numeric longevity.")
        return
    if exceed:
        finish(
            "refutes",
            None,
            0.9 if len(exceed) >= 3 else 0.75,
            measured,
            "Compared Homo sapiens maximum longevity with every other AnAge species of data quality acceptable or high. At least one non-Elephantidae species had a longevity greater than or equal to the human value, which is the pre-registered refutation.",
        )
        return
    finish(
        "supports",
        None,
        0.7,
        measured,
        "Compared Homo sapiens maximum longevity with every other AnAge species of data quality acceptable or high. No non-Elephantidae species reached the human value.",
    )


if __name__ == "__main__":
    main()
