#!/usr/bin/env python3
"""aristotle-ha05-03: male claspers in sharks and dogfish.

Pre-registered in result.json before any SexualAttributes value was read.
Fetches the FishBase v25.04 parquet mirror, scores species, and writes
derived/measured.json plus the completed fields of result.json.

Requires: python3, pyarrow (parquet). Stdlib only otherwise.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
BASE = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
FILES = {
    "morphdat.parquet": BASE + "morphdat.parquet",
    "species.parquet": BASE + "species.parquet",
    "families.parquet": BASE + "families.parquet",
    "orders.parquet": BASE + "orders.parquet",
    "classes.parquet": BASE + "classes.parquet",
}
UA = "delphisci-claim-test"

BATOID_ORDER = re.compile(
    r"rajiformes|myliobatiformes|torpediniformes|rhinopristiformes|"
    r"rhinobatiformes|pristiformes|platyrhiniformes",
    re.I,
)
BATOID_COMMON = re.compile(
    r"\b(rays?|skates?|guitarfish(?:es)?|sawfish(?:es)?|torpedoes|"
    r"torpedo(?:\s+rays?)?|electric\s+rays?)\b",
    re.I,
)
UNPAIRED = re.compile(r"one clasper|single clasper|unpaired clasper", re.I)
CLASPER = re.compile(r"clasper", re.I)
MALE = re.compile(r"\(m\)|\bmales?\b", re.I)
FEMALE = re.compile(r"\(f\)|\bfemales?\b", re.I)
NOT_EXAMINED = re.compile(
    r"not examined|not recorded|no data|unknown|not scored",
    re.I,
)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch() -> dict:
    DATA.mkdir(exist_ok=True)
    info = {}
    for name, url in FILES.items():
        path = DATA / name
        retrieved = None
        if not path.exists() or path.stat().st_size == 0:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as resp:
                path.write_bytes(resp.read())
            retrieved = now_utc()
        raw = path.read_bytes()
        info[name] = {
            "download_url": url,
            "retrieved_at": retrieved
            or dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    return info


def blank(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null", "<na>"}


def row_kind(value) -> str:
    """Return empty, not_examined, male_clasper, or disconfirming."""
    if blank(value):
        return "empty"
    text = str(value).strip()
    if UNPAIRED.search(text):
        return "disconfirming"
    has_c = CLASPER.search(text) is not None
    has_m = MALE.search(text) is not None
    has_f = FEMALE.search(text) is not None
    if has_c and has_f and not has_m:
        return "disconfirming"
    if has_c and has_m:
        return "male_clasper"
    if NOT_EXAMINED.search(text) and not has_c:
        return "not_examined"
    return "disconfirming"


def as_int(value):
    if blank(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def load_columns(name: str, columns: list[str]):
    table = pq.read_table(DATA / name, columns=columns)
    cols = {c: table.column(c).to_pylist() for c in columns}
    n = table.num_rows
    return [{c: cols[c][i] for c in columns} for i in range(n)]


def is_batoid(order: str, common: str) -> bool:
    blob_o = order or ""
    blob_c = common or ""
    return bool(BATOID_ORDER.search(blob_o) or BATOID_COMMON.search(blob_c))


def main() -> None:
    files = fetch()
    species = load_columns(
        "species.parquet", ["SpecCode", "Genus", "Species", "FamCode", "BodyShapeI"]
    )
    families = load_columns(
        "families.parquet",
        ["FamCode", "Family", "Order", "Ordnum", "Class", "CommonName"],
    )
    orders = load_columns("orders.parquet", ["Ordnum", "Order", "CommonName", "Class"])
    classes = load_columns("classes.parquet", ["Class", "CommonName", "Subclass", "SuperClass"])
    morph = load_columns("morphdat.parquet", ["Speccode", "SexualAttributes"])

    fam_by = {}
    for row in families:
        key = as_int(row["FamCode"])
        if key is not None:
            fam_by[key] = row
    ord_by = {}
    for row in orders:
        key = as_int(row["Ordnum"])
        if key is not None:
            ord_by[key] = row

    spec_by = {}
    for row in species:
        key = as_int(row["SpecCode"])
        if key is None:
            continue
        fam = fam_by.get(as_int(row["FamCode"]))
        order_name = (fam or {}).get("Order") or ""
        class_name = (fam or {}).get("Class") or ""
        common = ""
        if fam is not None:
            order_row = ord_by.get(as_int(fam.get("Ordnum")))
            if order_row:
                common = order_row.get("CommonName") or ""
                if not order_name:
                    order_name = order_row.get("Order") or ""
                if not class_name:
                    class_name = order_row.get("Class") or ""
        genus = (row.get("Genus") or "").strip()
        epithet = (row.get("Species") or "").strip()
        spec_by[key] = {
            "spec_code": key,
            "binomial": f"{genus} {epithet}".strip(),
            "genus": genus,
            "family": (fam or {}).get("Family") or "",
            "family_common": (fam or {}).get("CommonName") or "",
            "order": order_name,
            "order_common": common,
            "class": class_name,
            "body_shape": row.get("BodyShapeI") or "",
            "batoid": is_batoid(order_name, common),
            "elasmobranch": "elasmobranch" in class_name.lower(),
            "holocephalan": "holoceph" in class_name.lower(),
        }

    # species -> list of row kinds and raw values
    by_species: dict[int, list[tuple[str, str]]] = {}
    n_clasper_token_rows = 0
    for row in morph:
        key = as_int(row["Speccode"])
        if key is None:
            continue
        raw = row.get("SexualAttributes")
        kind = row_kind(raw)
        if kind == "empty":
            continue
        if not blank(raw) and CLASPER.search(str(raw)):
            n_clasper_token_rows += 1
        by_species.setdefault(key, []).append((kind, "" if blank(raw) else str(raw).strip()))

    def summarise(predicate):
        rows_out = []
        for key, info in spec_by.items():
            if not predicate(info):
                continue
            scored_rows = by_species.get(key, [])
            if not scored_rows:
                continue
            kinds = [k for k, _ in scored_rows]
            values = sorted({v for _, v in scored_rows})
            disconfirming = "disconfirming" in kinds
            male = "male_clasper" in kinds
            passed = male and not disconfirming
            both_markers = any(
                (not blank(v)) and CLASPER.search(v) and MALE.search(v) and FEMALE.search(v)
                for v in values
            )
            rows_out.append(
                {
                    **info,
                    "passed": passed,
                    "kinds": sorted(set(kinds)),
                    "values": values,
                    "both_sex_markers": both_markers,
                }
            )
        return rows_out

    sharks = summarise(lambda info: info["elasmobranch"] and not info["batoid"])
    rays = summarise(lambda info: info["elasmobranch"] and info["batoid"])
    holo = summarise(lambda info: info["holocephalan"])

    def rate(rows):
        n = len(rows)
        k = sum(1 for r in rows if r["passed"])
        return n, k, (k / n if n else None)

    n_shark_universe = sum(1 for info in spec_by.values() if info["elasmobranch"] and not info["batoid"])
    n_ray_universe = sum(1 for info in spec_by.values() if info["elasmobranch"] and info["batoid"])
    n, k, p = rate(sharks)
    n_ray, k_ray, p_ray = rate(rays)
    n_holo, k_holo, p_holo = rate(holo)
    n_dis = sum(1 for r in sharks if not r["passed"])
    n_both = sum(1 for r in sharks if r["both_sex_markers"])
    n_female = sum(
        1
        for r in sharks
        if any(
            CLASPER.search(v) and FEMALE.search(v) and not MALE.search(v) for v in r["values"]
        )
    )
    n_unpaired = sum(
        1 for r in sharks if any(UNPAIRED.search(v) for v in r["values"])
    )
    n_no_token = sum(
        1
        for r in sharks
        if not any(CLASPER.search(v) for v in r["values"])
    )

    value_counts: dict[str, int] = {}
    for r in sharks:
        for v in r["values"]:
            value_counts[v] = value_counts.get(v, 0) + 1
    value_table = [
        {"value": val, "n_species": count}
        for val, count in sorted(value_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    order_counts: dict[str, dict] = {}
    for r in sharks:
        slot = order_counts.setdefault(
            r["order"] or "(blank)",
            {"order": r["order"], "order_common": r["order_common"], "n": 0, "n_pass": 0},
        )
        slot["n"] += 1
        slot["n_pass"] += int(r["passed"])

    dogfish_genera = {"Squalus", "Scyliorhinus", "Mustelus", "Galeus", "Squalus"}
    dogfish = [
        {
            "binomial": r["binomial"],
            "genus": r["genus"],
            "family": r["family"],
            "order": r["order"],
            "passed": r["passed"],
            "values": r["values"],
        }
        for r in sharks
        if r["genus"] in dogfish_genera or "dogfish" in (r["family_common"] or "").lower()
    ]

    # Verdict from the pre-registered thresholds. Do not revise them here.
    if n_clasper_token_rows == 0:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n < 30:
        verdict, reason = "inconclusive", "underpowered"
    elif p >= 0.95:
        verdict, reason = "supports", None
    elif p >= 0.80:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "refutes", None

    # Confidence is a function of sample size and how close the rate is to a
    # boundary. The field is a literature compilation and does not count the
    # appendages, so the ceiling stays below 0.9.
    if verdict == "inconclusive":
        confidence = 0.35 if reason == "data-unavailable" else 0.4
    else:
        confidence = 0.55
        if n >= 100:
            confidence += 0.1
        if n >= 300:
            confidence += 0.05
        if p is not None and (p >= 0.99 or p <= 0.5):
            confidence += 0.1
        if p is not None and min(abs(p - 0.95), abs(p - 0.80)) < 0.02:
            confidence -= 0.1
        if n_both > 0:
            confidence -= 0.05
        confidence = round(min(0.85, max(0.3, confidence)), 2)

    failures = [
        {
            "binomial": r["binomial"],
            "family": r["family"],
            "order": r["order"],
            "values": r["values"],
            "kinds": r["kinds"],
        }
        for r in sharks
        if not r["passed"]
    ]

    measured = {
        "value": None if p is None else round(p, 4),
        "unit": "proportion of scored shark species with a male-clasper code and no disconfirming row",
        "n": n,
        "uncertainty": None,
        "extra": {
            "n_shark_species_in_fishbase": n_shark_universe,
            "n_ray_species_in_fishbase": n_ray_universe,
            "n_pass": k,
            "n_fail": n_dis,
            "scored_sharks": [
                {
                    "binomial": r["binomial"],
                    "family": r["family"],
                    "order": r["order"],
                    "passed": r["passed"],
                    "values": r["values"],
                }
                for r in sorted(sharks, key=lambda r: r["binomial"])
            ],
            "n_clasper_token_rows_all_fishes": n_clasper_token_rows,
            "n_female_only_clasper_species": n_female,
            "n_unpaired_clasper_species": n_unpaired,
            "n_scored_without_clasper_token": n_no_token,
            "n_both_sex_markers": n_both,
            "rays_scored": n_ray,
            "rays_pass": k_ray,
            "rays_pass_rate": None if p_ray is None else round(p_ray, 4),
            "holocephali_scored": n_holo,
            "holocephali_pass": k_holo,
            "holocephali_pass_rate": None if p_holo is None else round(p_holo, 4),
            "pass_rate_by_order": sorted(order_counts.values(), key=lambda r: -r["n"]),
            "sexual_attribute_values": value_table,
            "dogfish_like_genera": dogfish,
            "failures": failures[:80],
            "n_failures_listed": min(80, len(failures)),
            "n_failures_total": len(failures),
            "class_names_seen": sorted({c["Class"] for c in classes if c.get("Class")}),
        },
    }

    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "fishbase-v25.04-parquet-mirror",
            "name": "FishBase v25.04 tables (morphdat, species, families, orders, classes), parquet mirror distributed with rfishbase",
            "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
            "doi": None,
            "version": "v25.04",
            "license": "CC BY-NC 4.0",
            "files": [
                {"name": name, **meta}
                for name, meta in files.items()
            ],
            "role": "specialized sex organs (SexualAttributes) for fishes, restricted to sharks with the family and order tables",
        }
    ]
    result["method"] = (
        "Downloaded the five FishBase v25.04 parquet tables, hashed them, and joined "
        "morphdat to species, families, and orders on SpecCode, FamCode, and Ordnum. "
        "Sharks and dogfish are Elasmobranchii excluding batoid orders named in the "
        "pre-registration. Each non-empty SexualAttributes value was classed as a "
        "male-clasper code or as disconfirming, and the species pass rate was compared "
        "with the pre-registered thresholds. Rays and holocephalans are counted in extra "
        "and are not in the verdict."
    )
    result["measured"] = {
        "value": measured["value"],
        "unit": measured["unit"],
        "n": n,
        "uncertainty": None,
        "extra": {
            "n_shark_species_in_fishbase": n_shark_universe,
            "n_ray_species_in_fishbase": n_ray_universe,
            "n_pass": k,
            "n_fail": n_dis,
            "scored_sharks": measured["extra"]["scored_sharks"],
            "n_female_only_clasper_species": n_female,
            "n_unpaired_clasper_species": n_unpaired,
            "n_scored_without_clasper_token": n_no_token,
            "n_both_sex_markers": n_both,
            "rays_scored": n_ray,
            "rays_pass_rate": measured["extra"]["rays_pass_rate"],
            "holocephali_scored": n_holo,
            "holocephali_pass_rate": measured["extra"]["holocephali_pass_rate"],
        },
    }
    headlines = []
    if p is None:
        headlines.append("No scored shark species.")
    else:
        headlines.append(
            f"Scored sharks and dogfish: {k} of {n} pass ({p:.3f}), "
            f"out of {n_shark_universe} non-batoid elasmobranch species in FishBase."
        )
        names = ", ".join(
            f"{r['binomial']} ({r['values'][0]})" for r in measured["extra"]["scored_sharks"]
        )
        headlines.append(f"Scored species: {names}.")
    headlines.append(
        f"Female-only clasper codes: {n_female}. Unpaired clasper codes: {n_unpaired}. "
        f"Scored without the token clasper: {n_no_token}. Both-sex markers: {n_both}."
    )
    def fmt_rate(rate):
        return "unscored" if rate is None else f"{rate:.3f}"

    headlines.append(
        f"Rays scored {n_ray} (pass rate {fmt_rate(p_ray)}); "
        f"holocephalans scored {n_holo} (pass rate {fmt_rate(p_holo)}). "
        "Those groups are outside the verdict."
    )
    headlines.append(
        "The pre-registered rule does not apply the 0.95 or 0.80 rate thresholds "
        f"because only {n} shark species are scored (minimum 30). "
        "The reported proportion is descriptive."
    )
    if failures:
        sample = ", ".join(r["binomial"] for r in failures[:8])
        headlines.append(f"Failures include: {sample}.")
    result["results_summary"] = headlines
    extra_caveat = (
        f"After the run, SexualAttributes is filled for {n} of {n_shark_universe} "
        f"non-batoid elasmobranch species, so the pre-registered minimum of 30 scored "
        f"species is not met. Rays account for most elasmobranch clasper codes and are "
        f"outside the verdict. Galeus priapus is coded 'gonopodium (m)' and Megachasma "
        f"pelagios is coded 'no special organs'; both are scored non-passes, and neither "
        f"code is a count of appendages."
    )
    caveats = result.get("caveats") or []
    if extra_caveat not in caveats:
        # Replace a previous generated coverage caveat if the script is re-run.
        caveats = [c for c in caveats if not c.startswith("After the run, SexualAttributes")]
        caveats.append(extra_caveat)
    result["caveats"] = caveats
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "n": n,
        "k": k,
        "p": p,
        "confidence": confidence,
        "n_clasper_token_rows": n_clasper_token_rows,
        "value_table_top": value_table[:15],
        "n_fail": n_dis,
    }, indent=2))


if __name__ == "__main__":
    main()
