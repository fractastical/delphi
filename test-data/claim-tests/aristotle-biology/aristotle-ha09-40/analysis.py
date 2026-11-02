#!/usr/bin/env python3
"""GBIF identity and European month overlap for the two bird pairs in HA IX.50.

Decision rule: result.json pass_criterion, committed before any species query.
"""
import datetime as dt
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
PAIRS = [
    ("redbreast_redstart", "Erithacus rubecula", "Phoenicurus phoenicurus"),
    ("blackcap_beccafico", "Sylvia atricapilla", "Sylvia borin"),
]
LOCKED = {
    "hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract",
    "claim_id", "claim_iri", "project", "preregistered_at", "interpretation",
}


def get_json(url):
    DATA.mkdir(parents=True, exist_ok=True)
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (i + 1))
    else:
        raise last
    name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".json"
    path = DATA / name
    path.write_bytes(raw)
    info = {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "name": name,
    }
    return json.loads(raw.decode("utf-8")), info


def write_result(fields):
    doc = json.loads(RESULT.read_text())
    for key in fields:
        if key in LOCKED:
            raise SystemExit("refusing to edit locked field " + key)
    doc.update(fields)
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")


def month_counts(payload):
    facets = payload.get("facets") or []
    for facet in facets:
        field = str(facet.get("field") or facet.get("name") or "").lower()
        if field == "month":
            counts = {}
            for item in facet.get("counts") or []:
                try:
                    month = int(item.get("name"))
                    counts[month] = int(item.get("count"))
                except (TypeError, ValueError):
                    continue
            return counts
    return None


def match_one(name):
    url = "https://api.gbif.org/v1/species/match?" + urllib.parse.urlencode({"name": name, "verbose": "true"})
    payload, info = get_json(url)
    status = str(payload.get("matchType") or "")
    rank = str(payload.get("rank") or "")
    accepted = payload.get("acceptedUsageKey") or payload.get("usageKey")
    ok = status.upper() != "NONE" and rank.upper() == "SPECIES" and accepted is not None
    return {
        "query": name,
        "ok": ok,
        "matchType": payload.get("matchType"),
        "rank": payload.get("rank"),
        "status": payload.get("status"),
        "scientificName": payload.get("scientificName"),
        "acceptedScientificName": payload.get("acceptedScientificName") or payload.get("species"),
        "usageKey": payload.get("usageKey"),
        "acceptedUsageKey": accepted,
        "synonym": payload.get("synonym"),
        "file": info,
    }


def occurrences(key):
    query = urllib.parse.urlencode({
        "taxonKey": key,
        "continent": "EUROPE",
        "occurrenceStatus": "PRESENT",
        "facet": "month",
        "limit": 0,
        "facetLimit": 12,
    })
    url = "https://api.gbif.org/v1/occurrence/search?" + query
    payload, info = get_json(url)
    months = month_counts(payload)
    return {
        "taxonKey": key,
        "count": payload.get("count"),
        "months": months,
        "file": info,
    }


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    files = []
    pair_rows = []
    try:
        for pair_id, left, right in PAIRS:
            a = match_one(left)
            b = match_one(right)
            files.extend([a["file"], b["file"]])
            if not a["ok"] or not b["ok"]:
                pair_rows.append({"pair": pair_id, "left": a, "right": b, "error": "match-failed"})
                continue
            occ_a = occurrences(a["acceptedUsageKey"])
            occ_b = occurrences(b["acceptedUsageKey"])
            files.extend([occ_a["file"], occ_b["file"]])
            pair_rows.append({"pair": pair_id, "left": a, "right": b, "occ_left": occ_a, "occ_right": occ_b})
    except Exception as exc:  # noqa: BLE001
        measured = {"value": None, "unit": "shared European months (minimum across pairs)", "n": 0, "uncertainty": None, "extra": {"error": str(exc)}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete",
            "verdict": "inconclusive",
            "reason": "data-unavailable",
            "confidence": 0.3,
            "data_kind": "none",
            "measured": measured,
            "method": "A GBIF request failed before both pairs could be matched.",
            "results_summary": [f"Request failed: {exc}"],
            "datasets": [],
        })
        print("inconclusive", exc)
        return

    if any(row.get("error") for row in pair_rows) or any(
        row.get("occ_left", {}).get("months") is None or row.get("occ_right", {}).get("months") is None
        for row in pair_rows
    ):
        reason = "data-unavailable"
        measured = {"value": None, "unit": "shared European months (minimum across pairs)", "n": 0, "uncertainty": None, "extra": {"pairs": pair_rows}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": reason, "confidence": 0.35,
            "data_kind": "none", "measured": measured,
            "method": "GBIF species match or the month facet was missing for at least one name, so the continent was not changed.",
            "results_summary": ["At least one name failed to match or returned no month facet."],
            "datasets": dataset_block(files),
        })
        print("inconclusive match")
        return

    summaries = []
    underpowered = False
    for row in pair_rows:
        same = row["left"]["acceptedUsageKey"] == row["right"]["acceptedUsageKey"]
        months_a = {m: c for m, c in row["occ_left"]["months"].items() if c >= 20 and 1 <= m <= 12}
        months_b = {m: c for m, c in row["occ_right"]["months"].items() if c >= 20 and 1 <= m <= 12}
        shared = sorted(set(months_a) & set(months_b))
        count_a = int(row["occ_left"]["count"] or 0)
        count_b = int(row["occ_right"]["count"] or 0)
        if count_a < 100 or count_b < 100:
            underpowered = True
        row["same_species"] = same
        row["shared_months"] = shared
        row["n_shared_months"] = len(shared)
        row["europe_count_left"] = count_a
        row["europe_count_right"] = count_b
        summaries.append(
            f"{row['pair']}: same_species={same}, shared months with >=20 records={shared}, Europe counts {count_a} and {count_b}."
        )

    if underpowered:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.4
    elif all(row["same_species"] for row in pair_rows):
        verdict, reason, confidence = "supports", None, 0.40
    elif all((not row["same_species"]) and row["n_shared_months"] >= 3 for row in pair_rows):
        verdict, reason, confidence = "refutes", None, 0.85
    else:
        verdict, reason, confidence = "mixed", None, 0.50

    min_shared = min(row["n_shared_months"] for row in pair_rows)
    n_occ = sum(row["europe_count_left"] + row["europe_count_right"] for row in pair_rows)
    # Strip file blobs from the public extra by keeping the scientific result.
    public_pairs = []
    for row in pair_rows:
        public_pairs.append({
            "pair": row["pair"],
            "left": {k: row["left"][k] for k in ("query", "scientificName", "acceptedScientificName", "usageKey", "acceptedUsageKey", "rank", "status", "matchType", "synonym")},
            "right": {k: row["right"][k] for k in ("query", "scientificName", "acceptedScientificName", "usageKey", "acceptedUsageKey", "rank", "status", "matchType", "synonym")},
            "same_species": row["same_species"],
            "europe_count_left": row["europe_count_left"],
            "europe_count_right": row["europe_count_right"],
            "months_left": row["occ_left"]["months"],
            "months_right": row["occ_right"]["months"],
            "shared_months_count_at_least_20": row["shared_months"],
        })
    measured = {
        "value": min_shared,
        "unit": "calendar months in which both members of a pair have at least 20 European occurrences (minimum across the two pairs)",
        "n": n_occ,
        "uncertainty": None,
        "extra": {"pairs": public_pairs},
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    fields = {
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "measured": measured,
        "datasets": dataset_block(files),
        "method": "Matched each of the four scope names on the GBIF backbone, then counted European present occurrences by month. Applied the pre-registered identity and three-month overlap rule to both pairs. The continent and the names were not changed.",
        "results_summary": summaries + [f"Minimum shared-month count across pairs: {min_shared}."],
    }
    if reason:
        fields["reason"] = reason
        if reason == "data-unavailable":
            fields["data_kind"] = "none"
    write_result(fields)
    print(verdict, min_shared)


def dataset_block(files):
    return [
        {
            "id": "gbif-species-match",
            "name": "GBIF backbone species match",
            "landing_url": "https://www.gbif.org/species/search",
            "doi": None,
            "version": "GBIF backbone at retrieval",
            "license": "GBIF API. Taxon records are from the GBIF backbone.",
            "files": [f for f in files if "species/match" in f["download_url"]],
            "role": "accepted species keys for the four names in the claim scope",
        },
        {
            "id": "gbif-occurrence-month-facet-europe",
            "name": "GBIF occurrence search, Europe, month facet",
            "landing_url": "https://www.gbif.org/occurrence/search",
            "doi": None,
            "version": "GBIF occurrence index at retrieval",
            "license": "GBIF API. Only monthly counts were used; individual occurrences were not downloaded.",
            "files": [f for f in files if "occurrence/search" in f["download_url"]],
            "role": "European monthly occurrence counts for each accepted species",
        },
    ]


if __name__ == "__main__":
    main()
