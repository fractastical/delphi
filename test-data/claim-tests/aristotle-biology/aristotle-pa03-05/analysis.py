#!/usr/bin/env python3
"""aristotle-pa03-05: crooked-talon birds eat no vegetable food.

EltonTraits 1.0 bird diets. Verdict uses families and certainty codes
fixed in result.json. Hooked beaks are not scored.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://esapubs.org/archive/ecol/E095/178/BirdFuncDat.txt"
MD5_EXPECTED = "d6197b2cd90ca3ece0a7393abbf8b7fc"
UA = "delphisci-claim-test/aristotle-biology"
FAMILIES = {
    "Accipitridae", "Pandionidae", "Sagittariidae", "Cathartidae",
    "Falconidae", "Strigidae", "Tytonidae",
}
PLANT_COLS = ["Diet-Fruit", "Diet-Nect", "Diet-Seed", "Diet-PlantO"]


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
    }


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        obj = float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def read_table(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "latin1"):
        try:
            return pd.read_csv(path, sep="\t", encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise RuntimeError("could not decode BirdFuncDat.txt")


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    meta = fetch(URL, DATA / "BirdFuncDat.txt")
    df = read_table(DATA / "BirdFuncDat.txt")
    missing = [c for c in PLANT_COLS + ["BLFamilyLatin", "Diet-Certainty", "Scientific"] if c not in df.columns]
    result = json.loads(RESULT.read_text())
    if missing:
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["data_kind"] = "none"
        result["confidence"] = 0.3
        result["method"] = "The EltonTraits bird file was downloaded but did not contain the pre-registered columns."
        result["measured"] = {"value": None, "unit": "raptor species with plant diet", "n": 0, "extra": {"missing_columns": missing, "columns": list(df.columns)}}
        result["datasets"] = [{
            "id": "eltontraits-1.0-birdfuncdat",
            "name": "EltonTraits 1.0 bird foraging attributes",
            "landing_url": "https://esapubs.org/archive/ecol/E095/178/",
            "doi": "10.1890/13-1917.1",
            "version": "August 2013",
            "license": "public Ecological Archives release",
            "files": [{k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
            "role": "percent diet of the world's birds",
        }]
        RESULT.write_text(json.dumps(clean(result), indent=2) + "\n")
        print("missing columns", missing)
        return

    work = df.copy()
    for col in PLANT_COLS:
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    work["plant"] = work[PLANT_COLS].sum(axis=1)
    work["certainty"] = work["Diet-Certainty"].astype(str).str.strip().str.upper()
    raptors = work[work["BLFamilyLatin"].isin(FAMILIES)].copy()
    ab = raptors[raptors["certainty"].isin(["A", "B"])]
    any_plant = ab[ab["plant"] > 0]
    ge10 = ab[ab["plant"] >= 10]
    majority = ab[(ab["certainty"] == "A") & (ab["plant"] >= 50)]
    n_ab = int(len(ab))
    n_ge10 = int(len(ge10))
    n_majority = int(len(majority))
    n_any = int(len(any_plant))

    if n_ab < 50:
        verdict, reason = "inconclusive", "underpowered"
    elif n_ge10 >= 3 or n_majority >= 1:
        verdict, reason = "refutes", None
    elif n_any == 0:
        verdict, reason = "supports", None
    else:
        verdict, reason = "mixed", None

    if verdict == "inconclusive":
        conf = 0.35
    elif verdict == "mixed":
        conf = 0.6
    elif verdict == "refutes" and n_ge10 >= 5:
        conf = 0.8
    elif verdict == "supports":
        conf = 0.55
    else:
        conf = 0.7

    def rows(frame):
        keep = [c for c in ["Scientific", "BLFamilyLatin", "IOCOrder", "certainty", "plant", *PLANT_COLS, "Diet-5Cat"] if c in frame.columns or c == "certainty"]
        out = frame.rename(columns={"certainty": "Diet-Certainty"})
        cols = [c for c in ["Scientific", "BLFamilyLatin", "IOCOrder", "Diet-Certainty", "plant", *PLANT_COLS, "Diet-5Cat"] if c in out.columns]
        return out[cols].sort_values("plant", ascending=False).to_dict(orient="records")

    imputed = raptors[raptors["certainty"].isin(["D1", "D2", "C"])]
    measured = {
        "value": n_ge10,
        "unit": "raptor species with Diet-Certainty A or B and plant diet >= 10 percent",
        "n": n_ab,
        "uncertainty": None,
        "extra": {
            "n_raptor_rows": int(len(raptors)),
            "n_certainty_AB": n_ab,
            "n_plant_gt_0": n_any,
            "n_plant_ge_10": n_ge10,
            "n_certainty_A_plant_ge_50": n_majority,
            "species_plant_ge_10": rows(ge10),
            "species_majority_plant_certainty_A": rows(majority),
            "imputed_or_C_with_plant_gt_0_descriptive": int((imputed["plant"] > 0).sum()),
            "family_counts_AB": {str(k): int(v) for k, v in ab["BLFamilyLatin"].value_counts().items()},
            "md5_matches_archive_page": meta["md5"] == MD5_EXPECTED,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(clean(measured), indent=2) + "\n")
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["method"] = (
        "Downloaded EltonTraits BirdFuncDat.txt, kept the seven raptor families, and summed fruit, nectar, seed and other plant percentages. "
        "The verdict uses only Diet-Certainty A and B. Genus-imputed scores are counted in the descriptive total and not in the verdict."
    )
    result["measured"] = clean(measured)
    names = ", ".join(ge10["Scientific"].astype(str).head(12).tolist()) if n_ge10 else "none"
    result["results_summary"] = [
        f"Raptor rows {len(raptors)}; certainty A or B: {n_ab}.",
        f"Of those, plant diet > 0: {n_any}; plant diet >= 10: {n_ge10}; certainty A and plant >= 50: {n_majority}.",
        f"Species at or above 10 percent plant (first names): {names}.",
        f"Verdict {verdict}. The hooked-beak clause was not scored.",
    ]
    result["datasets"] = [{
        "id": "eltontraits-1.0-birdfuncdat",
        "name": "EltonTraits 1.0 bird foraging attributes (Wilman et al. 2014)",
        "landing_url": "https://esapubs.org/archive/ecol/E095/178/",
        "doi": "10.1890/13-1917.1",
        "version": "August 2013",
        "license": "public Ecological Archives release",
        "files": [{k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
        "role": "percent of diet from fruit, nectar, seeds and other plant material for birds of prey",
    }]
    if meta["md5"] != MD5_EXPECTED:
        result["deviations"] = list(result.get("deviations") or []) + [
            "BirdFuncDat.txt md5 did not match the Ecological Archives page. The verdict uses the downloaded bytes; the mismatch is recorded."
        ]
    RESULT.write_text(json.dumps(clean(result), indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "n_ab": n_ab, "n_ge10": n_ge10, "n_majority": n_majority}, indent=2))


if __name__ == "__main__":
    main()
