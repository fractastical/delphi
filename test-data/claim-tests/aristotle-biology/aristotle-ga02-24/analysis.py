#!/usr/bin/env python3
"""Test aristotle-ga02-24 against PanTHERIA age at eye opening."""

from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
DERIVED = ROOT / "derived"
URL = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
FIGSHARE_API = "https://api.figshare.com/v2/articles/3531875"
UA = "Mozilla/5.0 (compatible; delphi-claim-test/1.0; research)"
PINNIPEDS = {"Otariidae", "Phocidae", "Odobenidae"}
EXEMPLARS = {
    "lion": ["panthera leo"],
    "wolf": ["canis lupus"],
    "fox": ["vulpes vulpes"],
    "jackal": ["canis aureus"],
}
FROZEN = [
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "claim_id",
    "claim_iri",
    "project",
    "agent",
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def norm_col(name: str) -> str:
    return re.sub(r"\s+", "", str(name))


def find_col(columns, suffix: str):
    for column in columns:
        if norm_col(column).endswith(suffix):
            return column
    raise SystemExit(f"column not found: {suffix}")


def is_dog(binomial: str, species: str) -> bool:
    b = binomial.lower().strip()
    s = species.lower().strip()
    return b in {"canis familiaris", "canis lupus familiaris"} or s == "familiaris"


def download():
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    retrieved = now()
    errors = []
    try:
        r = sess.get(URL, timeout=120)
        r.raise_for_status()
        head = r.content[:20000]
        if head.lstrip().startswith(b"<!") or (b"MSW05_Order" not in head and b"MSW05_Binomial" not in head):
            raise requests.RequestException("response was not the PanTHERIA table")
        return r.content, r.url, retrieved, errors
    except requests.RequestException as exc:
        errors.append(str(exc))
    meta = sess.get(FIGSHARE_API, timeout=60)
    meta.raise_for_status()
    files = meta.json().get("files") or []
    chosen = None
    for item in files:
        name = item.get("name") or ""
        if "WR05" in name and name.endswith(".txt"):
            chosen = item
            break
    if chosen is None:
        for item in files:
            name = item.get("name") or ""
            if "WR05" in name or "PanTHERIA" in name:
                chosen = item
                break
    if chosen is None:
        raise SystemExit("PanTHERIA file not found at ESA or figshare: " + "; ".join(errors))
    download_url = chosen.get("download_url")
    r = sess.get(download_url, timeout=180)
    r.raise_for_status()
    content = r.content
    if chosen.get("name", "").endswith(".zip") or content[:2] == b"PK":
        import zipfile

        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = [n for n in zf.namelist() if "WR05" in n and n.endswith(".txt")]
            if not names:
                names = [n for n in zf.namelist() if n.endswith(".txt") and "PanTHERIA" in n]
            if not names:
                raise SystemExit("zip did not contain the WR05 table")
            content = zf.read(names[0])
    return content, download_url, retrieved, errors


def main():
    DERIVED.mkdir(exist_ok=True)
    try:
        content, download_url, retrieved, errors = download()
    except (requests.RequestException, SystemExit) as exc:
        data = json.loads(RESULT.read_text())
        snapshot = {k: data[k] for k in FROZEN}
        data.update(
            {
                "status": "complete",
                "data_kind": "none",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.35,
                "measured": {
                    "value": None,
                    "unit": "fraction of terrestrial carnivores with eyes opening after birth",
                    "n": 0,
                    "uncertainty": None,
                    "extra": {"error": str(exc), "rule_based_verdict": "inconclusive"},
                },
                "datasets": [],
                "method": "The PanTHERIA WR05 file was requested and could not be read.",
                "caveats": ["No eye-opening values were measured because the file was unavailable."],
            }
        )
        for key, value in snapshot.items():
            if data[key] != value:
                raise SystemExit(f"frozen field changed: {key}")
        RESULT.write_text(json.dumps(data, indent=2) + "\n")
        print(json.dumps(data["measured"]["extra"], indent=2))
        return

    digest = hashlib.sha256(content).hexdigest()
    frame = pd.read_csv(io.BytesIO(content), sep="\t", dtype=str)
    eye_col = find_col(frame.columns, "AgeatEyeOpening_d")
    order_col = find_col(frame.columns, "MSW05_Order")
    family_col = find_col(frame.columns, "MSW05_Family")
    binomial_col = find_col(frame.columns, "MSW05_Binomial")
    species_col = find_col(frame.columns, "MSW05_Species")

    def numeric(series):
        values = pd.to_numeric(series, errors="coerce")
        return values.mask(values == -999)

    carnivores = frame[frame[order_col].str.strip() == "Carnivora"].copy()
    terrestrial = carnivores[~carnivores[family_col].isin(PINNIPEDS)].copy()
    terrestrial["eye"] = numeric(terrestrial[eye_col])
    known = terrestrial[terrestrial["eye"].notna()].copy()
    known["after_birth"] = known["eye"] > 0
    n = int(len(known))
    n_after = int(known["after_birth"].sum()) if n else 0
    fraction = (n_after / n) if n else None

    exemplars = {}
    for key, names in EXEMPLARS.items():
        rows = known[known[binomial_col].str.lower().str.strip().isin(names)]
        if len(rows) == 0:
            exemplars[key] = None
        else:
            exemplars[key] = {
                "binomial": rows.iloc[0][binomial_col],
                "age_at_eye_opening_d": float(rows.iloc[0]["eye"]),
                "after_birth": bool(rows.iloc[0]["after_birth"]),
            }
    dog_rows = known[known.apply(lambda row: is_dog(str(row[binomial_col]), str(row[species_col])), axis=1)]
    if len(dog_rows) == 0:
        exemplars["dog"] = None
    else:
        exemplars["dog"] = {
            "binomial": dog_rows.iloc[0][binomial_col],
            "age_at_eye_opening_d": float(dog_rows.iloc[0]["eye"]),
            "after_birth": bool(dog_rows.iloc[0]["after_birth"]),
        }

    present = {k: v for k, v in exemplars.items() if v is not None}
    n_exemplars = len(present)
    n_exemplars_open_at_birth = sum(1 for v in present.values() if not v["after_birth"])

    ungulate_summary = {}
    for order in ("Artiodactyla", "Perissodactyla"):
        sub = frame[frame[order_col].str.strip() == order].copy()
        sub["eye"] = numeric(sub[eye_col])
        sub = sub[sub["eye"].notna()]
        ungulate_summary[order] = {
            "n": int(len(sub)),
            "n_after_birth": int((sub["eye"] > 0).sum()) if len(sub) else 0,
        }

    if fraction is None:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n < 15 or n_exemplars < 3:
        verdict, reason = "inconclusive", "underpowered"
    elif fraction < 0.70 or n_exemplars_open_at_birth >= 2:
        verdict, reason = "refutes", None
    elif fraction >= 0.90 and n_exemplars_open_at_birth == 0:
        verdict, reason = "supports", None
    else:
        verdict, reason = "mixed", None

    if verdict == "supports" and n >= 30:
        confidence = 0.78
    elif verdict == "supports":
        confidence = 0.7
    elif verdict == "refutes" and n >= 30:
        confidence = 0.8
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "mixed":
        confidence = 0.6
    else:
        confidence = 0.4

    rows_out = known[[binomial_col, family_col, "eye", "after_birth"]].sort_values(binomial_col)
    rows_out.to_csv(DERIVED / "carnivores.csv", index=False)
    exemplar_lines = []
    for key in ("dog", "lion", "wolf", "fox", "jackal"):
        value = exemplars.get(key)
        if value is None:
            exemplar_lines.append(f"{key},missing,,")
        else:
            exemplar_lines.append(
                f"{key},{value['binomial']},{value['age_at_eye_opening_d']},{value['after_birth']}"
            )
    (DERIVED / "exemplars.csv").write_text("exemplar,binomial,age_at_eye_opening_d,after_birth\n" + "\n".join(exemplar_lines) + "\n")

    measured = {
        "value": fraction,
        "unit": "fraction of terrestrial carnivores with age at eye opening greater than 0 days",
        "n": n,
        "uncertainty": None,
        "extra": {
            "n_after_birth": n_after,
            "n_open_at_birth": n - n_after,
            "open_at_birth_species": known.loc[~known["after_birth"], binomial_col].tolist(),
            "n_exemplars_with_data": n_exemplars,
            "n_exemplars_open_at_birth": n_exemplars_open_at_birth,
            "exemplars": exemplars,
            "ungulates_descriptive_only": ungulate_summary,
            "eye_column": eye_col,
            "download_errors": errors,
            "rule_based_verdict": verdict,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    data = json.loads(RESULT.read_text())
    snapshot = {k: data[k] for k in FROZEN}
    data.update(
        {
            "status": "complete",
            "data_kind": "biological",
            "verdict": verdict,
            "confidence": confidence,
            "measured": measured,
            "datasets": [
                {
                    "id": "pantheria-1-0-wr05-aug2008",
                    "name": "PanTHERIA 1.0 WR05",
                    "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
                    "doi": "10.1890/08-1494.1",
                    "version": "1.0 (WR05, August 2008)",
                    "license": "not stated on the Ecological Archives file",
                    "files": [
                        {
                            "download_url": download_url,
                            "retrieved_at": retrieved,
                            "byte_size": len(content),
                            "sha256": digest,
                        }
                    ],
                    "role": "age at eye opening for terrestrial carnivores",
                }
            ],
            "method": (
                f"Read PanTHERIA column {eye_col}. Kept MSW05 order Carnivora, dropped Otariidae, Phocidae and Odobenidae, "
                f"and treated -999 as missing. {n_after} of {n} species with a value open their eyes after day 0. "
                "The five named exemplars were scored with the same cut. Hoofed orders were counted only as a description."
            ),
            "caveats": [
                "PanTHERIA compiles published life-history reports. It is not a new measurement of eyelids on the day of birth.",
                "A value of 0 is read as eyes fully open at birth, from the variable definition that the age is when both eyes are fully open after birth.",
                "Species with a value of 0 days: " + ", ".join(known.loc[~known["after_birth"], binomial_col].tolist()) + ".",
                "The domestic dog is included only when a familiaris binomial is present. Canis lupus is the wolf, not a substitute for the dog.",
                "Pinnipeds were excluded before the fraction was computed. Artiodactyla and Perissodactyla do not affect the verdict.",
                "Many carnivores have no eye-opening value. The fraction is among species with a value, not among all carnivores.",
            ],
        }
    )
    if reason:
        data["reason"] = reason
    for key, value in snapshot.items():
        if data[key] != value:
            raise SystemExit(f"frozen field changed: {key}")
    RESULT.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "fraction": fraction, "n": n, "exemplars": exemplars}, indent=2))


if __name__ == "__main__":
    main()
