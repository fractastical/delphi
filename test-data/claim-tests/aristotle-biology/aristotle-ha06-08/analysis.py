#!/usr/bin/env python3
"""Female age at maturity in birds for aristotle-ha06-08.

Pass if the share with female maturity under 365 days is < 0.10; refute if
that share is >= 0.25; mixed in between. Minimum n = 80. Criteria were
committed before this download.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import zipfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://genomics.senescence.info/species/dataset.zip"
SHA = "e3ddb66e32e973a79932859ba53013e8f60d957c6ec01c6eb573e3ea3018d630"
SIZE = 169150
UA = "delphisci-claim-test/1.0"


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


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "dataset.zip"
    raw = dest.read_bytes() if dest.exists() else b""
    if hashlib.sha256(raw).hexdigest() != SHA or len(raw) != SIZE:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
    if hashlib.sha256(raw).hexdigest() != SHA or len(raw) != SIZE:
        raise RuntimeError("AnAge zip checksum mismatch")
    return {
        "name": "dataset.zip",
        "download_url": URL,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def load_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        text = zf.read(name).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def is_bird(label):
    return label.strip().lower() in {"aves", "birds", "bird"}


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
    meta, raw = fetch()
    rows = load_rows(raw)
    birds = []
    male_vals = []
    earliest = []
    for row in rows:
        if not is_bird(row.get("Class", "")):
            continue
        female = num(row.get("Female maturity (days)"))
        male = num(row.get("Male maturity (days)"))
        if female is not None and female > 0:
            birds.append(female)
        if male is not None and male > 0:
            male_vals.append(male)
        pool = [v for v in (female, male) if v is not None and v > 0]
        if pool:
            earliest.append(min(pool))
    n = len(birds)
    p = (sum(v < 365 for v in birds) / n) if n else None
    n_exactly_365 = sum(v == 365 for v in birds)
    n_at_or_under_365 = sum(v <= 365 for v in birds)
    if n < 80 or p is None:
        verdict, reason = "inconclusive", "underpowered" if n else "data-unavailable"
    elif p < 0.10:
        verdict, reason = "supports", None
    elif p >= 0.25:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    if verdict == "refutes" and p is not None and p >= 0.40:
        confidence = 0.85
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "supports":
        confidence = 0.7
    elif verdict == "mixed":
        # Judgment only. The locked cut stays strictly under 365 days.
        # A large pile coded at exactly 365 days means a one-day reading of
        # "within the first year" would change the verdict, so confidence stays low.
        confidence = 0.5
    else:
        confidence = 0.45
    male_p = (sum(v < 365 for v in male_vals) / len(male_vals)) if male_vals else None
    early_p = (sum(v < 365 for v in earliest) / len(earliest)) if earliest else None
    median = sorted(birds)[n // 2] if n else None
    measured = {
        "value": p,
        "unit": "share of bird species with female maturity under 365 days",
        "n": n,
        "uncertainty": None,
        "extra": {
            "n_under_365": None if p is None else sum(v < 365 for v in birds),
            "n_exactly_365": n_exactly_365,
            "n_at_or_under_365": n_at_or_under_365,
            "share_at_or_under_365_not_used_for_verdict": (n_at_or_under_365 / n) if n else None,
            "median_female_maturity_days": median,
            "male_share_under_365": male_p,
            "n_male": len(male_vals),
            "earliest_sex_share_under_365": early_p,
            "n_earliest": len(earliest),
            "secondary_not_used_for_verdict": True,
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["datasets"] = [{
        "id": "anage-build-15",
        "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
        "landing_url": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gks1155",
        "version": "build 15",
        "license": "CC BY 3.0",
        "files": [meta],
        "role": "female age at maturity for birds",
        "prior_record": "test-data/organisms/thompson-growth-form/ch08/datasets/anage-build-15.json",
    }]
    result["method"] = (
        "Downloaded the AnAge build 15 zip, checked SHA-256 and byte size, and read anage_data.txt. "
        "Among rows with Class Aves and Female maturity (days) > 0, p is the share under 365 days. "
        "Male maturity and the earliest of the two sexes are reported and do not set the verdict."
    )
    result["measured"] = measured
    result["verdict"] = verdict
    result["data_kind"] = "biological" if n else "none"
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["results_summary"] = [
        f"AnAge birds with female maturity: n={n}. Share under 365 days: {None if p is None else round(p, 4)}.",
        f"Median female maturity {median} days. Male share under 365 days {None if male_p is None else round(male_p, 4)} (n={len(male_vals)}), not used for the verdict.",
        f"{n_exactly_365} of {n} species are coded at exactly 365.0 days. The share at or under 365 days is {n_at_or_under_365}/{n} and is not used for the verdict.",
    ]
    result["caveats"] = settle_caveats(result.get("caveats", []), [
        "AnAge female maturity mixes wild and captive records and is age at sexual maturity, not the age of the first wild clutch.",
        (
            f"{n_exactly_365} of {n} species are coded at exactly 365.0 days. "
            "The pre-registered cut is strictly under 365 days, so those species are not counted as breeding in the first year. "
            f"The share at or under 365 days is {n_at_or_under_365}/{n} and is not used for the verdict."
        ),
    ])
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "measured": measured}, indent=2) + "\n")
    print(verdict, reason, "p", p, "n", n)


if __name__ == "__main__":
    main()
