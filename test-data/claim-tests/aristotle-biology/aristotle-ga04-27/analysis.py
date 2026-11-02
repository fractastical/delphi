#!/usr/bin/env python3
"""Gestation of horses, humans and elephants against Aristotle's stated durations.

Windows were fixed in result.json before anage_data.txt was opened:
  Equus median in [334.8125, 395.6875] days (one solar year ± one Gregorian month)
  Homo sapiens in [236.2447, 295.3059] days (eight to ten synodic months)
  Loxodonta and Elephas median in [700.0625, 760.9375] days (two solar years ± one month)

Run: python3 analysis.py
"""

import csv
import hashlib
import io
import json
import statistics
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
URL = "https://genomics.senescence.info/species/dataset.zip"
UA = "delphisci-claim-test/1.0 (aristotle-ga04-27)"

YEAR = 365.25
GREGORIAN_MONTH = YEAR / 12
SYNODIC = 29.53059
WINDOWS = {
    "equus": (YEAR - GREGORIAN_MONTH, YEAR + GREGORIAN_MONTH),
    "human": (8 * SYNODIC, 10 * SYNODIC),
    "elephant": (2 * YEAR - GREGORIAN_MONTH, 2 * YEAR + GREGORIAN_MONTH),
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_zip():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "dataset.zip"
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
            final = resp.geturl()
    else:
        final = URL
    raw = dest.read_bytes()
    info = {
        "download_url": final,
        "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        text = zf.read(name)
    txt_path = DATA / "anage_data.txt"
    txt_path.write_bytes(text)
    info["inner_name"] = name
    info["inner_byte_size"] = len(text)
    info["inner_sha256"] = hashlib.sha256(text).hexdigest()
    return info, text


def parse_days(value):
    value = (value or "").strip()
    if value == "" or value.lower() in {"na", "nan", "-", "null"}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if number <= 0:
        return None
    return number


def group_of(genus, species):
    genus_l = genus.strip().lower()
    species_l = species.strip().lower()
    if genus_l == "equus":
        return "equus"
    if genus_l == "homo" and species_l == "sapiens":
        return "human"
    if genus_l in {"loxodonta", "elephas"}:
        return "elephant"
    return None


def median(values):
    return float(statistics.median(values))


def in_window(value, window):
    low, high = window
    return low <= value <= high


def main():
    info, text = fetch_zip()
    rows = list(csv.DictReader(io.StringIO(text.decode("utf-8-sig")), delimiter="\t"))
    if not rows:
        raise SystemExit("AnAge table has no rows")
    gestation_key = next(
        (key for key in rows[0] if "gestat" in key.lower()),
        None,
    )
    if gestation_key is None:
        raise SystemExit("No gestation column in " + ", ".join(rows[0]))
    genus_key = next(key for key in rows[0] if key.lower() == "genus")
    species_key = next(key for key in rows[0] if key.lower() == "species")
    common_key = next((key for key in rows[0] if key.lower().replace(" ", "") == "commonname"), None)

    picked = []
    for row in rows:
        group = group_of(row[genus_key], row[species_key])
        if group is None:
            continue
        days = parse_days(row.get(gestation_key))
        picked.append(
            {
                "group": group,
                "genus": row[genus_key],
                "species": row[species_key],
                "common_name": row.get(common_key) if common_key else None,
                "gestation_days": days,
                "column": gestation_key,
            }
        )

    clauses = {}
    for group, window in WINDOWS.items():
        values = [r["gestation_days"] for r in picked if r["group"] == group and r["gestation_days"] is not None]
        if not values:
            clauses[group] = {"status": "missing", "n": 0, "median_days": None, "window": list(window)}
            continue
        mid = median(values)
        clauses[group] = {
            "status": "pass" if in_window(mid, window) else "fail",
            "n": len(values),
            "median_days": mid,
            "min_days": min(values),
            "max_days": max(values),
            "window": [window[0], window[1]],
            "signed_error_days": mid - (sum(window) / 2),
        }

    statuses = [c["status"] for c in clauses.values()]
    if any(s == "missing" for s in statuses) and not any(s == "fail" for s in statuses):
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.45
    elif all(s == "pass" for s in statuses):
        verdict, reason, confidence = "supports", None, 0.8
    elif any(s == "pass" for s in statuses) and any(s == "fail" for s in statuses):
        verdict, reason, confidence = "mixed", None, 0.7
    elif any(s == "fail" for s in statuses) and not any(s == "pass" for s in statuses):
        verdict, reason, confidence = "refutes", None, 0.8
    else:
        verdict, reason, confidence = "inconclusive", "other", 0.4

    # The reported value is the elephant median when present, because that clause
    # is the one the year-scale wording puts farthest from a one-month tolerance,
    # but every clause is in extra and the verdict uses all three. Use a structured
    # value the reader can check: the three medians, with `value` the count of
    # clauses that pass.
    n_pass = sum(1 for s in statuses if s == "pass")
    measured = {
        "value": n_pass,
        "unit": "clauses passing (Equus year, human ten months, elephant two years)",
        "n": sum(c["n"] for c in clauses.values()),
        "uncertainty": None,
        "extra": {
            "column": gestation_key,
            "clauses": clauses,
            "species": picked,
            "windows_days": {k: list(v) for k, v in WINDOWS.items()},
        },
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(
        json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n",
        encoding="utf-8",
    )
    (DERIVED / "gestation-rows.json").write_text(json.dumps(picked, indent=2) + "\n", encoding="utf-8")

    result = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    result["status"] = "complete"
    result["data_kind"] = "biological" if any(c["n"] for c in clauses.values()) else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "anage-gestation",
            "name": "AnAge: The Animal Ageing and Longevity Database, species build",
            "landing_url": "https://genomics.senescence.info/species/index.html",
            "doi": None,
            "version": "dataset.zip retrieved " + info["retrieved_at"][:10],
            "license": "HAGR license, free to use with attribution",
            "files": [
                {
                    "name": "dataset.zip",
                    "download_url": info["download_url"],
                    "retrieved_at": info["retrieved_at"],
                    "byte_size": info["byte_size"],
                    "sha256": info["sha256"],
                },
                {
                    "name": info["inner_name"],
                    "download_url": info["download_url"],
                    "retrieved_at": info["retrieved_at"],
                    "byte_size": info["inner_byte_size"],
                    "sha256": info["inner_sha256"],
                },
            ],
            "role": "gestation length in days for Equus, Homo sapiens, Loxodonta and Elephas",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        f"Downloaded the AnAge species zip and read column '{gestation_key}'. "
        "Equus species, Homo sapiens, and Loxodonta plus Elephas were kept. "
        "The median of the positive numeric values in each group was compared with the "
        "interval committed in pass_criterion. A blank cell was treated as missing. "
        "The verdict follows the pre-registered conjunction: all three clauses must pass to support."
    )
    bits = []
    for name, clause in clauses.items():
        bits.append(f"{name}: {clause['status']}, median {clause['median_days']} days, n {clause['n']}")
    result["results_summary"] = bits + [
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + f", clauses passing {n_pass} of 3."
    ]
    equus = clauses["equus"]
    if equus.get("min_days") is not None and (
        equus["min_days"] < WINDOWS["equus"][0] or equus["max_days"] > WINDOWS["equus"][1]
    ):
        note = (
            f"The Equus clause is the median of {equus['n']} species "
            f"({equus['min_days']} to {equus['max_days']} days). "
            "Species at the ends of that range fall outside the one-year window. "
            "The pre-registered rule uses the median and was not changed."
        )
        result.setdefault("caveats", [])
        if note not in result["caveats"]:
            result["caveats"].append(note)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "reason": reason, "clauses": clauses}, indent=2))


if __name__ == "__main__":
    main()
