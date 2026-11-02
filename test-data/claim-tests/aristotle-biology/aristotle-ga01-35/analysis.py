#!/usr/bin/env python3
"""FishBase reproductive mode against aristotle-ga01-35.

The pass and fail rules are the ones committed in result.json before any
ReproMode value was read. Requires python3 and duckdb.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
REPRO_URL = "https://data.source.coop/cboettig/fishbase/fb/v24.07/parquet/reproduc.parquet"
SPECIES_URL = "https://data.source.coop/cboettig/fishbase/fb/v24.07/parquet/species.parquet"
UA = "delphisci-claim-test"


def fetch(url: str, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def classify(mode: str) -> str:
    m = mode.strip().lower()
    if any(tok in m for tok in ("hermaphrod", "protandr", "protogyn")):
        return "hermaphrodite"
    if "dioec" in m:
        return "dioecism"
    if "parthen" in m:
        return "parthenogenesis"
    return "other"


def main() -> None:
    repro = fetch(REPRO_URL, DATA / "reproduc.parquet")
    species = fetch(SPECIES_URL, DATA / "species.parquet")
    con = duckdb.connect()
    mode_rows = con.execute(
        """
        SELECT SpecCode, ReproMode
        FROM read_parquet(?)
        WHERE ReproMode IS NOT NULL AND length(trim(ReproMode)) > 0
        """,
        [str(DATA / "reproduc.parquet")],
    ).fetchall()
    names = {
        spec: f"{genus} {sp}".strip()
        for spec, genus, sp in con.execute(
            "SELECT SpecCode, Genus, Species FROM read_parquet(?)",
            [str(DATA / "species.parquet")],
        ).fetchall()
    }
    by_spec: dict[int, set[str]] = {}
    raw_modes: dict[str, set[int]] = {}
    classes: dict[int, set[str]] = {}
    for spec, mode in mode_rows:
        text = str(mode).strip()
        by_spec.setdefault(spec, set()).add(text)
        raw_modes.setdefault(text, set()).add(spec)
        classes.setdefault(spec, set()).add(classify(text))

    def has(label: str) -> list[int]:
        return sorted(spec for spec, labs in classes.items() if label in labs)

    herm = has("hermaphrodite")
    dioec = has("dioecism")
    parth = has("parthenogenesis")
    other = has("other")
    both = sorted(set(herm) & set(dioec))
    n_mode = len(by_spec)
    n_herm = len(herm)
    n_dioec = len(dioec)

    if n_mode == 0:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.9
    elif n_herm >= 1:
        verdict, reason = "refutes", None
        confidence = 0.85 if n_herm >= 10 else 0.6
    elif n_mode < 100:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.7
    elif n_dioec >= 50:
        verdict, reason, confidence = "supports", None, 0.35
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.5

    def examples(specs: list[int], limit: int = 12) -> list[dict]:
        rows = []
        for spec in specs:
            rows.append({
                "spec_code": spec,
                "name": names.get(spec),
                "modes": sorted(by_spec[spec]),
            })
        rows.sort(key=lambda r: (r["name"] or "", r["spec_code"]))
        return rows[:limit]

    measured = {
        "value": n_herm,
        "unit": "fish species with a hermaphrodite reproduction mode",
        "n": n_mode,
        "uncertainty": "exact count of distinct SpecCode values",
        "extra": {
            "n_dioecism": n_dioec,
            "n_parthenogenesis": len(parth),
            "n_other_mode": len(other),
            "n_coded_both_hermaphrodite_and_dioecism": len(both),
            "mode_strings": [
                {"mode": mode, "n_species": len(specs)}
                for mode, specs in sorted(raw_modes.items(), key=lambda kv: -len(kv[1]))
            ],
            "hermaphrodite_examples": examples(herm),
            "parthenogenesis_examples": examples(parth),
        },
    }
    summary = [
        f"Coded species: {n_mode}. Hermaphrodite (protandry, protogyny or true hermaphroditism): {n_herm}. Dioecism: {n_dioec}. Parthenogenesis, not used for the verdict: {len(parth)}. Other filled modes: {len(other)}.",
        f"Species carrying both a hermaphrodite code and a dioecism code: {len(both)}. Those count as hermaphrodite, as pre-registered.",
        f"Verdict {verdict}: the universal is refuted by any hermaphrodite fish, and fishes move about.",
    ]
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "fishbase-rfishbase-snapshot-v24.07-reproduc",
        "name": "FishBase reproduction and species tables, rfishbase snapshot v24.07",
        "landing_url": "https://source.coop/cboettig/fishbase/fb/v24.07",
        "doi": None,
        "version": "fb/v24.07",
        "license": "CC BY-NC (FishBase, redistributed by the rfishbase snapshot)",
        "files": [
            {"name": "reproduc.parquet", **repro},
            {"name": "species.parquet", **species},
        ],
        "role": "species-level reproductive mode; species table supplies scientific names for the examples",
    }]
    doc["method"] = (
        "Downloaded the v24.07 reproduc and species parquet files, hashed them, and grouped non-empty "
        "ReproMode values by SpecCode. A species is hermaphrodite if any mode string contains hermaphrod, "
        "protandr or protogyn, dioecious if any contains dioec, and parthenogenetic if any contains parthen. "
        "The pre-registered rule was applied to those counts. Parthenogenesis is reported and does not decide the verdict."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["confidence"] = confidence
    doc["data_kind"] = "biological"
    doc["results_summary"] = summary
    if reason:
        doc["reason"] = reason
    else:
        doc.pop("reason", None)
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n_mode": n_mode, "n_herm": n_herm, "n_dioec": n_dioec}, indent=2))


if __name__ == "__main__":
    main()
