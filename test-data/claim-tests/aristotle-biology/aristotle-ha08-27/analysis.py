#!/usr/bin/env python3
"""aristotle-ha08-27: named birds hide in winter rather than migrate.

GBIF occurrence counts by 5-degree latitude bin. Medians and the 6-of-8
rule are those fixed in result.json. Counts are cached in derived/ so a
second run reproduces the same medians without another download.
Set REFRESH_GBIF=1 to query again.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
COUNTS_PATH = DERIVED / "gbif_counts.json"
UA = "delphisci-claim-test/aristotle-biology"
API = "https://api.gbif.org/v1"

VERDICT_SPECIES = [
    ("swallow", "Hirundo rustica"),
    ("kite", "Milvus migrans"),
    ("stork", "Ciconia ciconia"),
    ("owzel", "Turdus merula"),
    ("turtle-dove", "Streptopelia turtur"),
    ("lark", "Alauda arvensis"),
    ("thrush", "Turdus philomelos"),
    ("starling", "Sturnus vulgaris"),
]
EXTRA_SPECIES = [
    ("owl", "Athene noctua"),
    ("cushat", "Columba palumbus"),
]
EDGES = list(range(-55, 75, 5))
BINS = [(EDGES[i], EDGES[i + 1]) for i in range(len(EDGES) - 1)]
SUMMER = (6, 7, 8)
WINTER = (12, 1, 2)


def get_json(url: str, attempts: int = 5) -> dict:
    last = None
    for i in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — retry transient HTTP errors
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GBIF request failed: {url} ({last})")


def load_cache() -> dict:
    if COUNTS_PATH.exists() and os.environ.get("REFRESH_GBIF") != "1":
        return json.loads(COUNTS_PATH.read_text())
    return {"retrieved_at": None, "matches": {}, "counts": {}}


def save_cache(cache: dict) -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    COUNTS_PATH.write_text(json.dumps(cache) + "\n")


def match_species(cache: dict, name: str) -> dict:
    if name in cache["matches"]:
        return cache["matches"][name]
    url = f"{API}/species/match?name={urllib.parse.quote(name)}&verbose=false"
    payload = get_json(url)
    key = payload.get("acceptedUsageKey") or payload.get("usageKey")
    info = {
        "name": name,
        "usageKey": payload.get("usageKey"),
        "acceptedUsageKey": payload.get("acceptedUsageKey"),
        "taxonKey": key,
        "rank": payload.get("rank"),
        "status": payload.get("status"),
        "scientificName": payload.get("scientificName") or payload.get("canonicalName"),
        "matchType": payload.get("matchType"),
    }
    cache["matches"][name] = info
    save_cache(cache)
    time.sleep(0.05)
    return info


def occurrence_count(cache: dict, taxon_key: int, months: tuple, lat_lo: float, lat_hi: float) -> int:
    q = [
        ("taxonKey", str(taxon_key)),
        ("hasCoordinate", "true"),
        ("hasGeospatialIssue", "false"),
        ("occurrenceStatus", "PRESENT"),
        ("year", "2000,2026"),
        ("decimalLatitude", f"{lat_lo},{lat_hi - 0.0001:.4f}"),
        ("limit", "0"),
        ("basisOfRecord", "HUMAN_OBSERVATION"),
        ("basisOfRecord", "OBSERVATION"),
    ]
    for month in months:
        q.append(("month", str(month)))
    url = f"{API}/occurrence/search?{urllib.parse.urlencode(q)}"
    if url in cache["counts"]:
        return int(cache["counts"][url])
    payload = get_json(url)
    count = int(payload.get("count", 0))
    cache["counts"][url] = count
    if cache["retrieved_at"] is None:
        cache["retrieved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_cache(cache)
    time.sleep(0.05)
    return count


def histogram(cache: dict, taxon_key: int, months: tuple) -> list[int]:
    return [occurrence_count(cache, taxon_key, months, lo, hi) for lo, hi in BINS]


def median_lat(counts: list[int]):
    total = sum(counts)
    if total <= 0:
        return None, 0
    half = total / 2.0
    cum = 0
    for (lo, hi), count in zip(BINS, counts):
        if cum + count >= half:
            frac = 0.5 if count == 0 else (half - cum) / count
            return lo + frac * (hi - lo), total
        cum += count
    return None, total


def classify(summer_median, winter_median, n_summer, n_winter):
    if summer_median is None or winter_median is None or n_summer < 200 or n_winter < 200:
        return "uncounted-sample"
    if summer_median < 25:
        return "uncounted-not-northern"
    shift = summer_median - winter_median
    if shift >= 10:
        return "migrates-south"
    if abs(shift) < 5:
        return "stays"
    return "intermediate"


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    species_rows = []
    for role, group in (("verdict", VERDICT_SPECIES), ("descriptive", EXTRA_SPECIES)):
        for label, name in group:
            info = match_species(cache, name)
            key = info.get("taxonKey")
            if not key or info.get("rank") not in (None, "SPECIES"):
                # rank None only if the match payload omitted it; still require a key.
                if not key or (info.get("rank") and info.get("rank") != "SPECIES"):
                    species_rows.append({
                        "label": label, "scientific": name, "role": role,
                        "match": info, "class": "uncounted-match",
                    })
                    continue
            summer_counts = histogram(cache, key, SUMMER)
            winter_counts = histogram(cache, key, WINTER)
            s_med, n_s = median_lat(summer_counts)
            w_med, n_w = median_lat(winter_counts)
            kind = classify(s_med, w_med, n_s, n_w)
            shift = None if s_med is None or w_med is None else s_med - w_med
            species_rows.append({
                "label": label,
                "scientific": name,
                "role": role,
                "taxonKey": key,
                "matchedName": info.get("scientificName"),
                "n_summer": n_s,
                "n_winter": n_w,
                "summer_median_lat": s_med,
                "winter_median_lat": w_med,
                "summer_minus_winter_deg": shift,
                "class": kind,
                "summer_hist": summer_counts,
                "winter_hist": winter_counts,
            })
            print(f"{name}: {kind} nS={n_s} nW={n_w} shift={shift}", flush=True)

    verdict_rows = [r for r in species_rows if r["role"] == "verdict"]
    counted = [r for r in verdict_rows if r["class"] in ("migrates-south", "stays", "intermediate")]
    n_migrate = sum(r["class"] == "migrates-south" for r in counted)
    n_stay = sum(r["class"] == "stays" for r in counted)
    if len(counted) < 4:
        verdict, reason = "inconclusive", "underpowered"
        conf = 0.35
    elif n_stay >= 6:
        verdict, reason, conf = "supports", None, 0.55
    elif n_migrate >= 6:
        verdict, reason, conf = "refutes", None, 0.75
    else:
        verdict, reason, conf = "mixed", None, 0.65

    raw = COUNTS_PATH.read_bytes() if COUNTS_PATH.exists() else b""
    file_meta = {
        "download_url": f"{API}/occurrence/search",
        "retrieved_at": cache.get("retrieved_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "name": "derived/gbif_counts.json",
    }
    measured = {
        "value": n_migrate,
        "unit": "of the eight named species, how many have a winter median latitude at least 10 degrees south of the summer median",
        "n": len(counted),
        "uncertainty": f"{n_stay} stay within 5 degrees; {len(verdict_rows) - len(counted)} of the eight did not meet the sample gate",
        "extra": {
            "n_stay": n_stay,
            "n_migrate_south": n_migrate,
            "n_counted": len(counted),
            "bins": BINS,
            "species": [
                {k: v for k, v in row.items() if k not in ("summer_hist", "winter_hist")}
                for row in species_rows
            ],
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "histograms": species_rows}, indent=2) + "\n")
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["method"] = (
        "Matched each pre-registered scientific name to a GBIF species key, then counted human observations "
        "with coordinates from 2000 through 2026 in 5-degree latitude bins for June–August and for December–February. "
        "The seasonal median is interpolated inside the bin where the cumulative count crosses half. "
        "A species counts when both seasons have at least 200 records and the summer median is at least 25 N. "
        "Six of eight staying supports the non-migration clause; six of eight shifting south by at least 10 degrees refutes it."
    )
    result["measured"] = measured
    bits = []
    for row in verdict_rows:
        shift = row.get("summer_minus_winter_deg")
        shift_s = "NA" if shift is None else f"{shift:.1f}"
        bits.append(f"{row['scientific']} {row['class']} (shift {shift_s} deg, nS={row.get('n_summer')}, nW={row.get('n_winter')})")
    result["results_summary"] = bits + [
        f"Counted {len(counted)} of 8. Stayed: {n_stay}. Migrated south: {n_migrate}. Verdict {verdict}.",
        "Torpor in holes was not measured. A small latitude shift does not show that the bird was hidden.",
    ]
    result["datasets"] = [{
        "id": "gbif-occurrence-api",
        "name": "GBIF occurrence search counts",
        "landing_url": "https://www.gbif.org/",
        "doi": None,
        "version": file_meta["retrieved_at"][:10],
        "license": "GBIF occurrence records, various; counts queried from the public API",
        "files": [file_meta],
        "role": "seasonal latitude histograms for the named bird species",
    }]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "n_stay": n_stay, "n_migrate": n_migrate, "n_counted": len(counted)}, indent=2))


if __name__ == "__main__":
    main()
