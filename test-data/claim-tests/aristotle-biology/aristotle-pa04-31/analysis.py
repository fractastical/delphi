#!/usr/bin/env python3
"""aristotle-pa04-31: paired fins of fishes that are not broad and flat.

Follows result.json, which was committed before PectoralAttributes,
PelvicsAttributes, VPosition, and AddChars were tabulated.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from collections import Counter
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
}
UA = "delphisci-claim-test"
INCLUDED = {
    "actinopterygii",
    "actinopteri",
    "teleostei",
    "chondrostei",
    "holostei",
    "cladistii",
    "elasmobranchii",
    "holocephali",
    "sarcopterygii",
    "coelacanthi",
    "dipneusti",
}
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
ABSENT = re.compile(r"\b(absent|suppressed|none)\b", re.I)
EXTRA = re.compile(
    r"three pairs|third pair|two pairs of pectoral|additional pair of pectoral|"
    r"extra pectoral fin|three pectoral",
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
    return [{c: cols[c][i] for c in columns} for i in range(table.num_rows)]


def is_absent(value) -> bool:
    return (not blank(value)) and ABSENT.search(str(value)) is not None


def is_present_text(value) -> bool:
    return (not blank(value)) and not is_absent(value)


REJECT_WINDOW = re.compile(
    r"barbel|filament|tubercle|hook|gill|nostril|\bbands?\b|lobe|foramina|"
    r"\brays?\b|escal|plaque|tooth|cirrus|fin lengths?|pectoral-fin length",
    re.I,
)


def real_extra(text: str) -> list[str]:
    """Keep AddChars hits that name an extra pectoral or pelvic fin.

    The literal patterns also match 'three pairs of barbels' and 'three pectoral
    rays'. Those windows are not an extra paired fin. This filter is the deviation
    recorded in result.json.
    """
    found = []
    for match in EXTRA.finditer(text or ""):
        window = text[max(0, match.start() - 70): match.end() + 70]
        if REJECT_WINDOW.search(window):
            continue
        if re.search(r"pectoral|pelvic", window, re.I):
            found.append(re.sub(r"\s+", " ", window))
    return found


def contains_flat(*values) -> bool:
    for value in values:
        if not blank(value) and "flat" in str(value).lower():
            return True
    return False


def main() -> None:
    files = fetch()
    species = load_columns(
        "species.parquet", ["SpecCode", "Genus", "Species", "FamCode", "BodyShapeI"]
    )
    families = load_columns(
        "families.parquet", ["FamCode", "Family", "Order", "Ordnum", "Class"]
    )
    orders = load_columns("orders.parquet", ["Ordnum", "Order", "CommonName", "Class"])
    morph_cols = [
        "Speccode",
        "PectoralAttributes",
        "PelvicsAttributes",
        "VPosition",
        "BodyShapeI",
        "BodyShapeII",
        "AddChars",
        "Dfinno",
    ]
    morph = load_columns("morphdat.parquet", morph_cols)

    fam_by = {as_int(r["FamCode"]): r for r in families if as_int(r["FamCode"]) is not None}
    ord_by = {as_int(r["Ordnum"]): r for r in orders if as_int(r["Ordnum"]) is not None}
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
        genus = (row.get("Genus") or "").strip()
        epithet = (row.get("Species") or "").strip()
        batoid = bool(BATOID_ORDER.search(order_name) or BATOID_COMMON.search(common or ""))
        spec_by[key] = {
            "binomial": f"{genus} {epithet}".strip(),
            "genus": genus,
            "family": (fam or {}).get("Family") or "",
            "order": order_name,
            "order_common": common,
            "class": class_name,
            "species_body": row.get("BodyShapeI") or "",
            "batoid": batoid,
            "included": class_name.lower() in INCLUDED,
        }

    grouped: dict[int, list] = {}
    for row in morph:
        key = as_int(row["Speccode"])
        if key is not None:
            grouped.setdefault(key, []).append(row)

    extra_hits = []
    scored_rows = []
    n_included = 0
    n_raw_extra = 0
    for key, info in spec_by.items():
        if not info["included"]:
            continue
        n_included += 1
        rows = grouped.get(key, [])
        add_text = " ".join("" if blank(r.get("AddChars")) else str(r.get("AddChars")) for r in rows)
        if EXTRA.search(add_text):
            n_raw_extra += 1
        real_windows = real_extra(add_text)
        if real_windows:
            extra_hits.append({**info, "addchars": real_windows[0][:240]})
        flat = info["batoid"] or contains_flat(
            info["species_body"],
            *[r.get("BodyShapeI") for r in rows],
            *[r.get("BodyShapeII") for r in rows],
        )
        has_pect_field = any(not blank(r.get("PectoralAttributes")) for r in rows)
        has_pelv_field = any(
            (not blank(r.get("PelvicsAttributes"))) or (not blank(r.get("VPosition"))) for r in rows
        )
        if not (has_pect_field and has_pelv_field):
            continue
        pect_absent = any(is_absent(r.get("PectoralAttributes")) for r in rows)
        pect_present = any(is_present_text(r.get("PectoralAttributes")) for r in rows)
        pelv_absent = any(
            is_absent(r.get("PelvicsAttributes")) or is_absent(r.get("VPosition")) for r in rows
        )
        pelv_present = any(
            (
                is_present_text(r.get("PelvicsAttributes"))
                or (blank(r.get("PelvicsAttributes")) and is_present_text(r.get("VPosition")))
            )
            and not is_absent(r.get("VPosition"))
            for r in rows
        )
        has_four = pect_present and not pect_absent and pelv_present and not pelv_absent
        if not pect_present and not pect_absent:
            reason = "pectoral-unscored"
        elif not pelv_present and not pelv_absent:
            reason = "pelvic-unscored"
        elif has_four:
            reason = "four"
        elif pect_absent and not pect_present:
            reason = "pectoral-absent"
        elif pelv_absent and not pelv_present:
            reason = "pelvic-absent"
        else:
            reason = "conflict"
        dorsal_vals = [r.get("Dfinno") for r in rows if not blank(r.get("Dfinno"))]
        scored_rows.append(
            {
                **info,
                "flat": flat,
                "has_four": has_four,
                "reason": reason,
                "dorsal_n": dorsal_vals[:1],
            }
        )

    nonflat = [r for r in scored_rows if not r["flat"]]
    n_s = len(nonflat)
    n_four = sum(1 for r in nonflat if r["has_four"])
    p = (n_four / n_s) if n_s else None
    n_extra = len({r["binomial"] for r in extra_hits})
    reason_counts = Counter(r["reason"] for r in nonflat)
    class_counts = Counter(r["class"] for r in nonflat)
    flat_scored = sum(1 for r in scored_rows if r["flat"])

    # Descriptive only: dorsal-fin count among non-flat species that have four paired fins.
    dorsal_ge1 = 0
    dorsal_known = 0
    for r in nonflat:
        if not r["has_four"] or not r["dorsal_n"]:
            continue
        try:
            dnum = float(r["dorsal_n"][0])
        except (TypeError, ValueError):
            continue
        dorsal_known += 1
        if dnum >= 1:
            dorsal_ge1 += 1

    columns_blank = all(
        blank(row.get("PectoralAttributes")) and blank(row.get("PelvicsAttributes"))
        for row in morph
    )
    if columns_blank:
        verdict, why = "inconclusive", "data-unavailable"
    elif n_extra >= 5:
        verdict, why = "refutes", None
    elif n_s < 200:
        verdict, why = "inconclusive", "underpowered"
    elif p is not None and p < 0.50:
        verdict, why = "refutes", None
    elif p is not None and p >= 0.95 and n_extra == 0:
        verdict, why = "supports", None
    else:
        verdict, why = "mixed", None

    if verdict == "inconclusive":
        confidence = 0.35 if why == "data-unavailable" else 0.45
    else:
        confidence = 0.6
        if n_s >= 1000:
            confidence += 0.1
        if p is not None and (p >= 0.99 or p <= 0.2):
            confidence += 0.05
        if p is not None and min(abs(p - 0.95), abs(p - 0.50)) < 0.02:
            confidence -= 0.1
        n_real_absence = reason_counts.get("pelvic-absent", 0) + reason_counts.get("pectoral-absent", 0)
        if n_real_absence >= 50:
            confidence = min(confidence, 0.55)
        confidence = round(min(0.85, max(0.3, confidence)), 2)

    failure_examples = [
        {"binomial": r["binomial"], "class": r["class"], "order": r["order"], "reason": r["reason"]}
        for r in nonflat
        if not r["has_four"]
    ][:40]

    measured_extra = {
        "n_included_species": n_included,
        "n_scored_any_shape": len(scored_rows),
        "n_scored_flat_excluded_from_proportion": flat_scored,
        "n_four": n_four,
        "n_extra_pair_text": n_extra,
        "reason_counts_nonflat": dict(reason_counts),
        "class_counts_nonflat_scored": dict(class_counts),
        "extra_pair_species": [
            {"binomial": r["binomial"], "class": r["class"], "order": r["order"]}
            for r in extra_hits
        ],
        "failure_examples": failure_examples,
        "descriptive_dorsal_fin_among_four_paired": {
            "n_with_numeric_dorsal_count": dorsal_known,
            "n_dorsal_count_at_least_1": dorsal_ge1,
            "note": "Not used for the verdict. A dorsal fin plus four paired fins is more than four fins on the unpaired-fin reading.",
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(
        json.dumps({"value": None if p is None else round(p, 4), "n": n_s, "extra": measured_extra}, indent=2)
        + "\n"
    )

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if why:
        result["reason"] = why
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "fishbase-v25.04-parquet-mirror",
            "name": "FishBase v25.04 morphdat, species, families, and orders",
            "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
            "doi": None,
            "version": "v25.04",
            "license": "CC BY-NC 4.0",
            "files": [{"name": name, **meta} for name, meta in files.items()],
            "role": "pectoral and pelvic fin attributes, body shape, and the order used to mark rays and skates",
        }
    ]
    result["method"] = (
        "Downloaded the FishBase v25.04 tables and joined morphdat to species, families, "
        "and orders. A blank pelvic position is not an absence code; the words absent, "
        "suppressed, and none are. A species has four paired fins only when the pectoral "
        "text is present without an absence row and the pelvic text is present without an "
        "absence row. Broad-and-flat species (body-shape text containing 'flat', or a batoid "
        "order) are removed from the proportion and kept in the extra-pair search. "
        "Dorsal-fin counts are descriptive and are not in the verdict."
    )
    result["measured"] = {
        "value": None if p is None else round(p, 4),
        "unit": "proportion of scored non-flat fishes with both pectoral and pelvic pairs and no absence row",
        "n": n_s,
        "uncertainty": None,
        "extra": {
            "n_four": n_four,
            "n_extra_pair_text": n_extra,
            "n_included_species": n_included,
            "reason_counts_nonflat": dict(reason_counts),
            "descriptive_dorsal_among_four_paired_n": dorsal_known,
            "descriptive_dorsal_count_at_least_1": dorsal_ge1,
        },
    }
    summary = [
        (
            f"Scored non-flat fishes: {n_four} of {n_s} have both pairs"
            + (f" ({p:.3f}). " if p is not None else ". ")
            + f"Pelvic pair coded absent in {reason_counts.get('pelvic-absent', 0)}, "
            + f"pectoral pair coded absent in {reason_counts.get('pectoral-absent', 0)}."
        ),
        "Reasons among scored non-flat species: "
        + ", ".join(f"{k} {v}" for k, v in sorted(reason_counts.items())),
        f"AddChars matches for an extra paired fin: {n_extra}.",
        f"Included species in the named classes: {n_included}. "
        f"Scored but broad-and-flat, removed from the proportion: {flat_scored}.",
    ]
    if dorsal_known:
        summary.append(
            f"Descriptive only: of {dorsal_known} non-flat species with four paired fins and a numeric dorsal-fin count, "
            f"{dorsal_ge1} have at least one dorsal fin."
        )
    caveats = list(result.get("caveats") or [])
    post = (
        f"After the deviations, {n_four} of {n_s} scored non-flat species have both pairs "
        f"({None if p is None else round(p, 4)}). "
        f"{reason_counts.get('pelvic-absent', 0)} are coded with the pelvic pair absent and "
        f"{reason_counts.get('pectoral-absent', 0)} with the pectoral pair absent, so the "
        "universal wording is not literally true of every scored fish. The verdict uses the "
        "pre-registered 0.95 tolerance. Separately, nearly every species with a dorsal-fin "
        "count has at least one dorsal fin, which would put the total above four if median "
        "fins were counted. That reading is not the verdict."
    )
    caveats = [c for c in caveats if not c.startswith("After the deviations,")]
    caveats.append(post)
    result["caveats"] = caveats
    result["deviations"] = [
        {
            "what": "Pelvic fins with a recorded position and a blank attribute now count as present.",
            "why": (
                "The pre-registered present-rule required a non-absent PelvicsAttributes value. "
                "249 scored species have PelvicsAttributes blank and VPosition equal to abdominal, "
                "thoracic, or jugular, which is a position of a fin rather than a missing fin. "
                "A blank attribute plus one of those positions now counts as a pelvic pair, "
                "unless an absence code is also present. Absence codes are unchanged."
            ),
        },
        {
            "what": "AddChars pattern hits are kept only when the window names a pectoral or pelvic fin and is not a count of rays, barbels, or filaments.",
            "why": (
                f"The literal patterns matched {n_raw_extra} species. The matched windows were "
                "three pairs of barbels, filaments, or tubercles, a count of pectoral rays, "
                "or, in one case, 'three pectoral-fin lengths' used as a distance. "
                "None of those is a second paired fin. Those windows no longer add to n_extra. "
                f"After the filter, n_extra is {n_extra}."
            ),
        },
    ]
    result["results_summary"] = summary
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": why, "n": n_s, "p": p, "n_extra": n_extra, "reasons": dict(reason_counts), "confidence": confidence}, indent=2))


if __name__ == "__main__":
    main()
