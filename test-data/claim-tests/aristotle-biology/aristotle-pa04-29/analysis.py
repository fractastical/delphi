#!/usr/bin/env python3
"""aristotle-pa04-29: toe count and toe arrangement in Carril et al. 2024.

The decision rule is the one committed in result.json before this matrix was
opened. This script downloads the supplementary files, checks their checksums,
maps character 16, and writes measured, the verdict and derived/species-scores.csv.

Run from anywhere: python3 analysis.py
Requires pandas and xlrd (the supplements are Excel 97 .xls). pdftotext, if
present, is used only to confirm the codebook still lists the pre-registered labels.
"""

import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"

FILES = {
    "41467_2024_54297_MOESM3_ESM.xls": {
        "url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-54297-9/MediaObjects/41467_2024_54297_MOESM3_ESM.xls",
        "role": "Supplementary Data 1, species list with order",
        "sha256": "9971f7e84135d926b10ff82eca8560a4077a5d210e6dbb41fc82ded38e286d50",
        "byte_size": 72704,
    },
    "41467_2024_54297_MOESM5_ESM.pdf": {
        "url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-54297-9/MediaObjects/41467_2024_54297_MOESM5_ESM.pdf",
        "role": "Supplementary Data 3, character codebook including foot type",
        "sha256": "393092fff0e23ec20bc2cbd7e92321d546e977b60df4bbfb7b5bcecaa48b1aa1",
        "byte_size": 109898,
    },
    "41467_2024_54297_MOESM6_ESM.xls": {
        "url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-54297-9/MediaObjects/41467_2024_54297_MOESM6_ESM.xls",
        "role": "Supplementary Data 4, character matrix; foot type is Ch16",
        "sha256": "8e48979953ee03570bf7e1db8b90b1512f601888a2ebb29be9e48e804a338ae5",
        "byte_size": 148992,
    },
}

# Fixed before the matrix was opened. See result.json interpretation.
CODE_MAP = {
    0: {"label": "anisodactyl", "toes": 4, "arrangement": True, "web": False},
    1: {"label": "didactyl", "toes": 2, "arrangement": False, "web": False},
    2: {"label": "tridactyl", "toes": 3, "arrangement": False, "web": False},
    3: {"label": "semizygodactyl", "toes": 4, "arrangement": False, "web": False},
    4: {"label": "zygodactyl", "toes": 4, "arrangement": False, "web": False},
    5: {"label": "pamprodactyl", "toes": 4, "arrangement": False, "web": False},
    6: {"label": "syndactyl", "toes": 4, "arrangement": True, "web": False},
    7: {"label": "lobate", "toes": 4, "arrangement": True, "web": False},
    8: {"label": "semipalmate", "toes": 4, "arrangement": True, "web": True},
    9: {"label": "palmate", "toes": 4, "arrangement": True, "web": True},
    10: {"label": "totipalmate", "toes": 4, "arrangement": False, "web": True},
    11: {"label": "multidactyl", "toes": 4, "arrangement": False, "web": False},
}
LABEL_MAP = {v["label"]: v for v in CODE_MAP.values()}
LABEL_MAP["heterodactyl"] = {"label": "heterodactyl", "toes": 4, "arrangement": False, "web": False}
# Ectropodactyl is intentionally absent: toe count was not to be guessed, so it stays unmapped.

CODEBOOK_LABELS = [
    "anisodactyl", "didactyl", "tridactyl", "semizygodactyl", "zygodactyl",
    "pamprodactyl", "syndactyl", "lobate", "semipalmate", "palmate",
    "totipalmate", "multidactyl",
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    info = {}
    checksums_ok = True
    for name, meta in FILES.items():
        path = DATA / name
        downloaded_now = False
        if not path.exists():
            req = urllib.request.Request(meta["url"], headers={"User-Agent": "delphisci-claim-test/1.0"})
            path.write_bytes(urllib.request.urlopen(req, timeout=90).read())
            downloaded_now = True
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        retrieved = utc_now() if downloaded_now else dt.datetime.fromtimestamp(
            path.stat().st_mtime, dt.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        match = digest == meta["sha256"] and len(raw) == meta["byte_size"]
        checksums_ok = checksums_ok and match
        info[name] = {
            "name": name,
            "download_url": meta["url"],
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": digest,
            "matches_registered_sha256": digest == meta["sha256"],
            "matches_registered_size": len(raw) == meta["byte_size"],
            "role_note": meta["role"],
        }
    return info, checksums_ok


def find_header(df, required):
    for i in range(min(20, len(df))):
        vals = ["" if pd.isna(x) else str(x).strip() for x in df.iloc[i].tolist()]
        if all(any(v.lower() == r.lower() for v in vals) for r in required):
            return i, vals
    return None, None


def col_index(header, name):
    for i, v in enumerate(header):
        if v.lower() == name.lower():
            return i
    return None


def read_table(path, required):
    df = pd.read_excel(path, sheet_name=0, header=None, engine="xlrd")
    idx, header = find_header(df, required)
    if idx is None:
        return None
    body = df.iloc[idx + 1 :].copy()
    body.columns = [header[i] if i < len(header) else f"col{i}" for i in range(body.shape[1])]
    return body


def parse_code(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text.isdigit():
            return CODE_MAP.get(int(text))
        return LABEL_MAP.get(text)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return CODE_MAP.get(number)


def codebook_labels_present():
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    pdf = DATA / "41467_2024_54297_MOESM5_ESM.pdf"
    text = subprocess.check_output([exe, "-layout", str(pdf), "-"], text=True, errors="replace")
    return {label: (label in text.lower()) for label in CODEBOOK_LABELS}


def clean_name(name):
    # Supplementary Data 1 marks some binomials with a trailing " (*)". The matrix does not.
    text = " ".join(str(name).split())
    return re.sub(r"\s*\(\*\)\s*$", "", text).strip()


def genus_of(name):
    parts = clean_name(name).split()
    return parts[0] if parts else ""


def decide(rows):
    in_scope = [r for r in rows if not r["excluded_struthio"]]
    mapped = [r for r in in_scope if r["mapped"]]
    unmapped = [r for r in in_scope if not r["mapped"]]
    denom = len(in_scope)
    unmapped_fraction = (len(unmapped) / denom) if denom else None
    count_fail = [r for r in mapped if r["toes"] != 4]
    arrangement_fail = [r for r in mapped if r["toes"] == 4 and r["arrangement"] is False]
    orders = sorted({r["order"] for r in mapped if r["order"]})
    n_web = sum(1 for r in mapped if r["web"])
    n_nonweb = sum(1 for r in mapped if not r["web"])
    breadth = (
        len(mapped) >= 30
        and len(orders) >= 10
        and n_web >= 1
        and n_nonweb >= 1
        and unmapped_fraction is not None
        and unmapped_fraction <= 0.10
    )
    c = len(count_fail)
    a = len(arrangement_fail)
    genera = sorted({genus_of(r["species"]) for r in count_fail})
    if c >= 1:
        verdict, reason = "refutes", None
        confidence = 0.9 if c >= 2 and len(genera) >= 2 else 0.7
    elif a >= 1:
        verdict, reason = "mixed", None
        if a >= 2 and breadth:
            confidence = 0.8
        elif a >= 2:
            confidence = 0.65
        else:
            confidence = 0.55
    elif breadth:
        verdict, reason, confidence = "supports", None, 0.45
    elif unmapped_fraction is not None and unmapped_fraction > 0.10:
        verdict, reason, confidence = "inconclusive", "other", 0.5
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.5
    return {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "C": c,
        "A": a,
        "n_mapped": len(mapped),
        "n_in_scope": denom,
        "n_unmapped": len(unmapped),
        "unmapped_fraction": unmapped_fraction,
        "n_orders": len(orders),
        "orders": orders,
        "n_web": n_web,
        "n_nonweb": n_nonweb,
        "breadth": breadth,
        "count_fail_genera": genera,
        "count_fail": count_fail,
        "arrangement_fail": arrangement_fail,
        "n_struthio": sum(1 for r in rows if r["excluded_struthio"]),
        "leave_one_count_genus_out": [
            {
                "left_out_genus": g,
                "C": sum(1 for r in count_fail if genus_of(r["species"]) != g),
            }
            for g in genera
        ],
    }


def main():
    file_info, checksums_ok = fetch()
    labels = codebook_labels_present()
    if not checksums_ok:
        outcome = {
            "verdict": "inconclusive",
            "reason": "data-unavailable",
            "confidence": 0.8,
            "note": "A downloaded file did not match the checksum recorded from the first retrieval.",
        }
        write_result(file_info, labels, [], outcome, checksums_ok)
        return

    species = read_table(DATA / "41467_2024_54297_MOESM3_ESM.xls", ["Species", "Order"])
    matrix = read_table(DATA / "41467_2024_54297_MOESM6_ESM.xls", ["Species", "Ch16"])
    if species is None or matrix is None:
        outcome = {
            "verdict": "inconclusive",
            "reason": "data-unavailable",
            "confidence": 0.8,
            "note": "Species, Order or Ch16 header was not found.",
        }
        write_result(file_info, labels, [], outcome, checksums_ok)
        return

    order_by_name = {}
    for _, row in species.iterrows():
        name = row["Species"]
        if pd.isna(name):
            continue
        key = clean_name(name)
        order = row["Order"]
        order_by_name[key] = "" if pd.isna(order) else str(order).strip()

    rows = []
    for _, row in matrix.iterrows():
        name = row["Species"]
        if pd.isna(name):
            continue
        species_name = clean_name(name)
        if not species_name or species_name.lower() == "species":
            continue
        mapped = parse_code(row["Ch16"])
        genus = genus_of(species_name)
        record = {
            "species": species_name,
            "genus": genus,
            "order": order_by_name.get(species_name, ""),
            "order_joined": species_name in order_by_name,
            "ch16": None if pd.isna(row["Ch16"]) else int(row["Ch16"]) if not isinstance(row["Ch16"], str) else row["Ch16"],
            "excluded_struthio": genus.lower() == "struthio",
            "mapped": mapped is not None,
            "label": None if mapped is None else mapped["label"],
            "toes": None if mapped is None else mapped["toes"],
            "arrangement": None if mapped is None else mapped["arrangement"],
            "web": None if mapped is None else mapped["web"],
        }
        rows.append(record)

    if not rows:
        outcome = {
            "verdict": "inconclusive",
            "reason": "data-unavailable",
            "confidence": 0.8,
            "note": "No species rows were read from the character matrix.",
        }
        write_result(file_info, labels, rows, outcome, checksums_ok)
        return

    stats = decide(rows)
    write_result(file_info, labels, rows, stats, checksums_ok)
    print(json.dumps({k: stats[k] for k in ("verdict", "confidence", "reason", "C", "A", "n_mapped", "n_orders", "n_web", "n_nonweb", "breadth", "count_fail_genera")}, indent=2))


def write_result(file_info, labels, rows, stats, checksums_ok):
    DERIVED.mkdir(parents=True, exist_ok=True)
    result = json.loads(RESULT.read_text())
    # Outcome fields only. Pre-registered criterion text is left as it was committed.
    dataset_files = []
    for name in FILES:
        item = dict(file_info[name])
        item.pop("role_note", None)
        dataset_files.append(item)
    result["status"] = "complete"
    result["data_kind"] = "biological" if checksums_ok and rows else "none"
    result["datasets"] = [
        {
            "id": "carril-2024-natcomms-avian-foot-supplementary-data-1-and-4",
            "name": "Evolution of avian foot morphology through anatomical network analysis, supplementary data",
            "landing_url": "https://www.nature.com/articles/s41467-024-54297-9",
            "doi": "10.1038/s41467-024-54297-9",
            "version": "Nature Communications 15:9888 (2024)",
            "license": "CC BY-NC-ND 4.0",
            "files": dataset_files,
            "role": "foot-type code (character 16) for  the study's bird species, with taxonomic order from the species list",
        }
    ]
    # fix accidental double space if I typed one
    result["datasets"][0]["role"] = (
        "Foot-type code (character 16) for the study's bird species, with taxonomic order from the species list. "
        "The codebook file is the source of the code labels. Original spreadsheets are re-fetched and are not committed."
    )

    by_label = {}
    for r in rows:
        if r["excluded_struthio"]:
            continue
        key = r["label"] or "unmapped"
        by_label[key] = by_label.get(key, 0) + 1

    if stats.get("verdict") == "inconclusive" and not rows:
        measured = {
            "value": None,
            "unit": "in-scope species failing a clause",
            "n": 0,
            "uncertainty": None,
            "extra": {"note": stats.get("note"), "checksums_ok": checksums_ok},
        }
        summary = [stats.get("note") or "The supplementary files could not be used."]
        method = "The script attempted to fetch Carril et al. 2024 Supplementary Data 1, 3 and 4 and stopped because the files or the required columns were not usable."
    else:
        failing = stats["C"] + stats["A"]
        measured = {
            "value": failing,
            "unit": "in-scope species that fail the four-toe clause or, among four-toed species, the fixed three-forward one-back clause",
            "n": stats["n_mapped"],
            "uncertainty": None,
            "extra": {
                "C_toe_count_not_4": stats["C"],
                "A_four_toed_arrangement_not_3_plus_1": stats["A"],
                "n_in_scope_rows": stats["n_in_scope"],
                "n_struthio_excluded": stats["n_struthio"],
                "n_unmapped_in_scope": stats["n_unmapped"],
                "unmapped_fraction": stats["unmapped_fraction"],
                "n_orders": stats["n_orders"],
                "orders": stats["orders"],
                "n_web_footed": stats["n_web"],
                "n_not_web_footed": stats["n_nonweb"],
                "breadth_thresholds_met": stats["breadth"],
                "toe_count_failure_genera": stats["count_fail_genera"],
                "leave_one_count_genus_out_descriptive": stats.get("leave_one_count_genus_out"),
                "toe_count_failures": [
                    {"species": r["species"], "order": r["order"], "foot_type": r["label"], "toes": r["toes"]}
                    for r in stats["count_fail"]
                ],
                "arrangement_failures": [
                    {"species": r["species"], "order": r["order"], "foot_type": r["label"], "toes": r["toes"]}
                    for r in stats["arrangement_fail"]
                ],
                "in_scope_counts_by_foot_type": by_label,
                "quote_four_toe_clause": "fails" if stats["C"] >= 1 else "no counterexample in the mapped sample",
                "claim_arrangement_clause": "fails" if (stats["C"] + stats["A"]) >= 1 else "no counterexample in the mapped sample",
                "codebook_labels_found": labels,
                "species_missing_an_order_join": [r["species"] for r in rows if not r["excluded_struthio"] and not r["order_joined"]],
                "checksums_ok": checksums_ok,
            },
        }
        summary = [
            f"In-scope mapped species: {stats['n_mapped']} (Struthio excluded: {stats['n_struthio']}), in {stats['n_orders']} orders, web-footed {stats['n_web']}, not web-footed {stats['n_nonweb']}.",
            f"Toe-count failures (C): {stats['C']}. Arrangement failures among four-toed species (A): {stats['A']}.",
            "Species with a toe count other than 4: "
            + (", ".join(f"{r['species']} ({r['label']})" for r in stats["count_fail"]) or "none")
            + ".",
            "Four-toed species whose arrangement is not three forward and one back: "
            + (", ".join(f"{r['species']} ({r['label']})" for r in stats["arrangement_fail"]) or "none")
            + ".",
        ]
        if stats["C"] >= 2:
            summary.append(
                "Descriptive only, not used for the verdict: dropping either toe-count genus on its own leaves C at "
                + ", ".join(f"{s['C']} without {s['left_out_genus']}" for s in stats["leave_one_count_genus_out"])
                + "."
            )
        method = (
            "Fetched Carril et al. 2024 Supplementary Data 1 (species and order), Supplementary Data 3 (codebook) and Supplementary Data 4 (character matrix), "
            "and checked byte size and SHA-256. Read Ch16 for each species, mapped the codes with the pre-registered table, dropped genus Struthio, "
            "and counted toe-count failures separately from arrangement failures among the remaining four-toed species. "
            "Orders were taken from the Order column of Supplementary Data 1 after stripping a trailing ' (*)' marker from binomials in that list, so the GBIF fallback was not used. "
            "The verdict is the pre-registered rule applied to those two counts."
        )

    result["measured"] = measured
    result["verdict"] = stats["verdict"]
    result["confidence"] = stats["confidence"]
    if stats.get("reason"):
        result["reason"] = stats["reason"]
    elif "reason" in result:
        del result["reason"]
    result["method"] = method
    result["results_summary"] = summary

    scores_path = DERIVED / "species-scores.csv"
    with scores_path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["species", "genus", "order", "ch16", "foot_type", "toes", "arrangement_3_forward_1_back", "web_footed", "in_scope", "fails_toe_count", "fails_arrangement_only"],
        )
        writer.writeheader()
        for r in rows:
            in_scope = not r["excluded_struthio"]
            fails_count = bool(in_scope and r["mapped"] and r["toes"] != 4)
            fails_arr = bool(in_scope and r["mapped"] and r["toes"] == 4 and r["arrangement"] is False)
            writer.writerow({
                "species": r["species"],
                "genus": r["genus"],
                "order": r["order"],
                "ch16": r["ch16"],
                "foot_type": r["label"] or "",
                "toes": "" if r["toes"] is None else r["toes"],
                "arrangement_3_forward_1_back": "" if r["arrangement"] is None else str(r["arrangement"]).lower(),
                "web_footed": "" if r["web"] is None else str(r["web"]).lower(),
                "in_scope": str(in_scope).lower(),
                "fails_toe_count": str(fails_count).lower(),
                "fails_arrangement_only": str(fails_arr).lower(),
            })
    measured_path = DERIVED / "measured.json"
    measured_path.write_text(json.dumps({"verdict": result["verdict"], "confidence": result["confidence"], "reason": result.get("reason"), "measured": measured}, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
