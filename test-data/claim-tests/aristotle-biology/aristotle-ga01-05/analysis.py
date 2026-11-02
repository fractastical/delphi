#!/usr/bin/env python3
"""Count FishBase reproductive modes that the manual ties to testes.

The mode column is identified by the pre-registered vocabulary, not by name.
"""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/reproduc.parquet"
UA = "delphisci-claim-test/aristotle-ga01-05"

# FishBase REPRODUCTION manual vocabulary. Matching is case- and space-insensitive.
TESTICULAR = {
    "dioecism",
    "protandry",
    "protogyny",
    "true hermaphroditism",
}
PARTHENOGENESIS = {"parthenogenesis"}
VOCAB = TESTICULAR | PARTHENOGENESIS


def norm(value):
    if value is None:
        return None
    text = " ".join(str(value).strip().lower().split())
    return text or None


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "reproduc.parquet"
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=120).read()
    dest.write_bytes(raw)
    return raw, dest


def main():
    raw, dest = fetch()
    table = pq.read_table(dest)
    columns = table.column_names
    scored = []
    for name in columns:
        values = table.column(name).to_pylist()
        hits = 0
        for value in values:
            if norm(value) in VOCAB:
                hits += 1
        scored.append((hits, name))
    scored.sort(reverse=True)
    mode_name = scored[0][1] if scored and scored[0][0] > 0 else None
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if "SpecCode" not in columns or mode_name is None:
        reason = "other" if mode_name and "SpecCode" not in columns else "data-unavailable"
        if "SpecCode" not in columns and mode_name:
            reason = "other"
        if mode_name is None:
            reason = "data-unavailable"
        result = json.loads((HERE / "result.json").read_text())
        result.update({
            "status": "complete",
            "verdict": "inconclusive",
            "reason": reason,
            "confidence": 0.35,
            "data_kind": "none",
            "method": "Downloaded reproduc.parquet and looked for a column whose values use the FishBase mode vocabulary and for SpecCode. One of those was missing, so no count was turned into a biological verdict.",
            "measured": {
                "value": None,
                "unit": "testicular species",
                "n": 0,
                "uncertainty": None,
                "extra": {"columns": columns, "vocab_hits": scored[:8]},
            },
            "datasets": [dataset_record(raw, now)],
            "results_summary": [f"mode column={mode_name}", f"has SpecCode={'SpecCode' in columns}"],
        })
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        (DERIVED / "columns.json").write_text(json.dumps({"columns": columns, "vocab_hits": scored}, indent=2) + "\n")
        print("inconclusive", reason)
        return

    spec = table.column("SpecCode").to_pylist()
    modes = [norm(v) for v in table.column(mode_name).to_pylist()]
    by_species = {}
    for spec_code, mode in zip(spec, modes):
        if spec_code is None or mode not in VOCAB:
            continue
        by_species.setdefault(spec_code, set()).add(mode)
    recognized = len(by_species)
    testicular_species = {k for k, modeset in by_species.items() if modeset & TESTICULAR}
    testicular_n = len(testicular_species)
    only_parth = recognized - testicular_n
    mode_counts = {}
    for modeset in by_species.values():
        for mode in modeset:
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

    if recognized < 100:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.5
    elif testicular_n >= 100:
        verdict, reason, confidence = "refutes", None, 0.8
    elif testicular_n == 0:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.45
    else:
        verdict, reason, confidence = "mixed", None, 0.55

    summary = {
        "mode_column": mode_name,
        "recognized_species": recognized,
        "testicular_species": testicular_n,
        "parthenogenesis_only_species": only_parth,
        "species_with_mode": mode_counts,
        "n_rows": table.num_rows,
    }
    (DERIVED / "mode_counts.json").write_text(json.dumps(summary, indent=2) + "\n")
    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "method": "Downloaded the FishBase v26.06 reproduc table, selected the column whose values match the manual's reproductive-mode vocabulary, and counted distinct SpecCode values. Dioecism, protandry, protogyny and true hermaphroditism were coded as testicular, following the manual's definition that dioecism is males developing testes. Parthenogenesis was not. Snakes are not in this table. A testicular count of at least 100 refutes the joint claim.",
        "measured": {
            "value": testicular_n,
            "unit": "FishBase species with a reproductive mode the manual ties to testicular tissue",
            "n": recognized,
            "uncertainty": "compiled modes, not a new dissection; one row-group per stock collapsed to SpecCode",
            "extra": summary,
        },
        "datasets": [dataset_record(raw, now)],
        "results_summary": [
            f"Mode column {mode_name}. Recognized species {recognized}. Testicular species {testicular_n}.",
            "Mode occupancy (a species can carry more than one mode across stocks): " + json.dumps(mode_counts),
            "Serpents were not in FishBase. The joint claim is refuted by the fish count alone when that count is at least 100.",
        ],
    })
    if reason:
        result["reason"] = reason
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, testicular_n, "of", recognized)


def dataset_record(raw, now):
    return {
        "id": "fishbase-fb-v26.06-reproduc",
        "name": "FishBase reproduction table, snapshot fb/v26.06",
        "landing_url": "https://source.coop/cboettig/fishbase",
        "doi": None,
        "version": "fb/v26.06",
        "license": "CC-BY-NC, FishBase.org team, via the rfishbase parquet snapshot",
        "files": [{
            "download_url": URL,
            "retrieved_at": now,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }],
        "role": "reproductive mode of fishes; dioecism is defined by the FishBase manual as males developing testes",
    }


if __name__ == "__main__":
    main()
