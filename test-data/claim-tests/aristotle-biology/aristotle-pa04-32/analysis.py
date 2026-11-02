#!/usr/bin/env python3
"""FishBase operculum codes against aristotle-pa04-32.

Rules are those committed in result.json before any OperculumPresent value was read.
Requires python3 and duckdb.
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
BASE = "https://data.source.coop/cboettig/fishbase/fb/v24.07/parquet/"
FILES = {
    "morphdat.parquet": BASE + "morphdat.parquet",
    "species.parquet": BASE + "species.parquet",
    "families.parquet": BASE + "families.parquet",
}
UA = "delphisci-claim-test"


def fetch(url: str, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
    raw = dest.read_bytes()
    return {
        "name": dest.name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def proportion(present: int, n: int) -> float | None:
    if n == 0:
        return None
    return present / n


def group_stats(rows: list[dict], pred) -> dict:
    chosen = [row for row in rows if pred(row)]
    n = len(chosen)
    present = sum(1 for row in chosen if row["oper"] == 1)
    return {"n": n, "n_present": present, "proportion_present": proportion(present, n)}


def main() -> None:
    infos = [fetch(url, DATA / name) for name, url in FILES.items()]
    con = duckdb.connect()
    quality = con.execute(
        """
        SELECT
          count(*) AS n_rows,
          count(OperculumPresent) AS n_nonnull,
          count(*) FILTER (WHERE OperculumPresent IS NOT NULL AND OperculumPresent NOT IN (0, 1)) AS n_other
        FROM read_parquet(?)
        """,
        [str(DATA / "morphdat.parquet")],
    ).fetchone()
    n_rows, n_nonnull, n_other = quality
    value_counts = [
        {"value": None if value is None else int(value), "n": int(n)}
        for value, n in con.execute(
            "SELECT OperculumPresent, count(*) FROM read_parquet(?) GROUP BY 1 ORDER BY 2 DESC",
            [str(DATA / "morphdat.parquet")],
        ).fetchall()
    ]
    other_share = (n_other / n_nonnull) if n_nonnull else None

    species_rows = con.execute(
        """
        WITH raw AS (
          SELECT Speccode AS spec_code, OperculumPresent AS oper
          FROM read_parquet(?)
          WHERE OperculumPresent IS NOT NULL
        ),
        per_spec AS (
          SELECT spec_code,
                 max(CASE WHEN oper = 1 THEN 1 ELSE 0 END) AS oper
          FROM raw
          WHERE oper IN (0, 1)
          GROUP BY spec_code
        ),
        fam AS (
          SELECT SpecCode AS spec_code, FamCode AS fam_code, Genus AS genus, Species AS species
          FROM read_parquet(?)
        ),
        tax AS (
          SELECT FamCode AS fam_code, Class AS class_name, "Order" AS order_name, Family AS family,
                 Synonym AS synonym
          FROM read_parquet(?)
        )
        SELECT p.spec_code, p.oper, f.genus, f.species, t.class_name, t.order_name, t.family, t.synonym
        FROM per_spec p
        LEFT JOIN fam f ON p.spec_code = f.spec_code
        LEFT JOIN tax t ON f.fam_code = t.fam_code
        """,
        [str(DATA / "morphdat.parquet"), str(DATA / "species.parquet"), str(DATA / "families.parquet")],
    ).fetchall()

    by_spec: dict[int, dict] = {}
    class_conflict = 0
    unmatched = 0
    for spec, oper, genus, species, class_name, order_name, family, synonym in species_rows:
        if synonym == 1:
            continue
        slot = by_spec.setdefault(spec, {"rows": [], "oper": oper})
        slot["rows"].append({
            "genus": genus, "species": species, "class_name": class_name,
            "order_name": order_name, "family": family,
        })
    clean = []
    for spec, slot in by_spec.items():
        classes = {row["class_name"] for row in slot["rows"] if row["class_name"]}
        orders = {row["order_name"] for row in slot["rows"] if row["order_name"]}
        if not slot["rows"] or not classes:
            unmatched += 1
            continue
        if len(classes) > 1 or len(orders) > 1:
            class_conflict += 1
            continue
        sample = slot["rows"][0]
        clean.append({
            "spec_code": spec,
            "oper": int(slot["oper"]),
            "name": f"{sample['genus']} {sample['species']}".strip(),
            "class_name": sample["class_name"] or "",
            "order_name": sample["order_name"] or "",
            "family": sample["family"] or "",
        })

    def has(text: str, needle: str) -> bool:
        return needle in (text or "").lower()

    all_stats = group_stats(clean, lambda row: True)
    elas = group_stats(clean, lambda row: has(row["class_name"], "elasmobranch"))
    holo = group_stats(clean, lambda row: has(row["class_name"], "holocephal") or has(row["order_name"], "chimaer"))
    aci = group_stats(clean, lambda row: has(row["order_name"], "acipenser"))
    class_names = sorted({row["class_name"] for row in clean})
    by_class = []
    for name in class_names:
        stats = group_stats(clean, lambda row, name=name: row["class_name"] == name)
        stats["class_name"] = name
        by_class.append(stats)

    n_all, n_elas = all_stats["n"], elas["n"]
    p_all, p_elas = all_stats["proportion_present"], elas["proportion_present"]
    causal_hit = (
        (holo["n"] >= 5 and holo["proportion_present"] is not None and holo["proportion_present"] > 0.5)
        or (aci["n"] >= 5 and aci["proportion_present"] is not None and aci["proportion_present"] > 0.5)
    )
    elas_class_exists = any(has(name, "elasmobranch") for name in class_names) or n_elas > 0

    if n_nonnull == 0:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.85
    elif other_share is not None and other_share > 0.05:
        verdict, reason, confidence = "inconclusive", "other", 0.7
    elif not any(has(name, "elasmobranch") for name in class_names):
        verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.6
    elif n_all < 100 or n_elas < 20:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.65
    elif p_elas >= 0.5 or p_all <= 0.5:
        verdict, reason, confidence = "refutes", None, 0.75
    elif p_all > 0.5 and p_elas == 0 and causal_hit:
        verdict, reason, confidence = "mixed", None, 0.7
    elif p_all > 0.5 and 0 < p_elas < 0.5:
        verdict, reason, confidence = "mixed", None, 0.7
    elif p_all > 0.5 and p_elas == 0:
        verdict, reason = "supports", None
        confidence = 0.55 if (holo["n"] < 5 and aci["n"] < 5) else 0.7
    else:
        verdict, reason, confidence = "inconclusive", "other", 0.4

    examples = [row["name"] for row in clean if has(row["class_name"], "elasmobranch") and row["oper"] == 1][:12]
    measured = {
        "value": None if p_elas is None else round(p_elas, 6),
        "unit": "proportion of scored elasmobranch species with an operculum coded present",
        "n": n_elas,
        "uncertainty": "exact species counts after collapsing stocks",
        "extra": {
            "all_scored": all_stats,
            "elasmobranchii": elas,
            "holocephali_or_chimaera_order": holo,
            "acipenseriformes": aci,
            "by_class": by_class,
            "n_morphdat_rows": n_rows,
            "n_operculum_nonnull": n_nonnull,
            "n_operculum_outside_0_1": n_other,
            "share_outside_0_1": other_share,
            "operculum_value_counts": value_counts,
            "n_species_unmatched_to_family": unmatched,
            "n_species_with_conflicting_class_or_order": class_conflict,
            "elasmobranch_species_coded_present": examples,
            "class_names": class_names,
            "elasmobranch_class_string_present": elas_class_exists,
        },
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "fishbase-rfishbase-snapshot-v24.07-morphdat",
        "name": "FishBase morphology, species and family tables, rfishbase snapshot v24.07",
        "landing_url": "https://source.coop/cboettig/fishbase/fb/v24.07",
        "doi": None,
        "version": "fb/v24.07",
        "license": "CC BY-NC (FishBase, redistributed by the rfishbase snapshot)",
        "files": infos,
        "role": "operculum presence joined to class and order",
    }]
    doc["method"] = (
        "Downloaded morphdat, species and families from the FishBase v24.07 snapshot and hashed them. "
        "OperculumPresent values other than 0 or 1 were counted and, if rare, excluded. "
        "Each species was scored present if any stock was 1 and absent if every stock was 0. "
        "Synonym families (Synonym = 1) were dropped. Elasmobranchii, chimaeras and sturgeons were identified by the "
        "pre-registered substrings of Class and Order, and the pre-registered thresholds were applied."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["confidence"] = confidence
    doc["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    doc["results_summary"] = [
        f"OperculumPresent values in the file: {value_counts}. Codes other than 0 and 1 are {n_other} of {n_nonnull} non-null rows.",
        f"Scored species: {n_all}, proportion with an operculum {p_all}. Elasmobranchs: {n_elas}, proportion {p_elas}.",
        f"Holocephali or chimaera-order species: {holo}. Sturgeon-order species: {aci}.",
        f"Verdict {verdict}. The distributional contrast and the 'because cartilage' clause are separated in the pre-registered rule.",
    ]
    if reason:
        doc["reason"] = reason
    else:
        doc.pop("reason", None)
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "all": all_stats, "elas": elas, "holo": holo, "aci": aci}))


if __name__ == "__main__":
    main()
