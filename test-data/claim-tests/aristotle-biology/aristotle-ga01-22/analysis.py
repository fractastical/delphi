#!/usr/bin/env python3
"""aristotle-ga01-22: adult mass versus litter or clutch size in mammals and birds.

Thresholds are those committed in result.json. Run: python3 analysis.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import requests
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
ZIP_URL = "https://genomics.senescence.info/species/dataset.zip"
UA = "delphisci-claim-test/aristotle-ga01-22"


def fetch_zip():
    DATA.mkdir(exist_ok=True)
    path = DATA / "dataset.zip"
    if not path.exists():
        r = requests.get(ZIP_URL, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
        retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return path.read_bytes(), retrieved


def num(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def score_class(rows, class_name):
    weights, litters = [], []
    for row in rows:
        if (row.get("Class") or "").strip().casefold() != class_name:
            continue
        w = num(row.get("Adult weight (g)"))
        lit = num(row.get("Litter/Clutch size"))
        if w is None or lit is None or w <= 0 or lit <= 0:
            continue
        weights.append(w)
        litters.append(lit)
    w = np.asarray(weights, dtype=float)
    lit = np.asarray(litters, dtype=float)
    n = int(w.size)
    out = {"class": class_name, "n": n}
    if n < 3:
        out["scorable"] = False
        out["reason"] = "too few rows"
        return out
    rho, p = stats.spearmanr(w, lit)
    med_w = float(np.median(w))
    low = lit[w <= med_w]
    high = lit[w > med_w]
    out.update({
        "spearman_rho": float(rho) if np.isfinite(rho) else None,
        "spearman_p": float(p) if np.isfinite(p) else None,
        "median_adult_weight_g": med_w,
        "n_lighter_or_equal": int(low.size),
        "n_heavier": int(high.size),
        "median_litter_lighter": float(np.median(low)) if low.size else None,
        "median_litter_heavier": float(np.median(high)) if high.size else None,
        "min_adult_weight_g": float(w.min()),
        "max_adult_weight_g": float(w.max()),
    })
    finite = out["spearman_rho"] is not None and out["spearman_p"] is not None
    halves = low.size >= 10 and high.size >= 10
    out["scorable"] = bool(n >= 40 and halves and finite)
    if not out["scorable"]:
        return out
    heavier_fewer = out["median_litter_heavier"] < out["median_litter_lighter"]
    heavier_not_fewer = out["median_litter_heavier"] >= out["median_litter_lighter"]
    out["passes"] = bool(out["spearman_rho"] <= -0.20 and out["spearman_p"] < 0.05 and heavier_fewer)
    out["fails"] = bool(out["spearman_rho"] >= 0 and heavier_not_fewer)
    return out


def confidence(verdict, mammals, birds):
    if verdict == "inconclusive":
        return 0.40
    if verdict == "mixed":
        return 0.58
    if verdict == "refutes":
        return 0.74
    rhos = [mammals.get("spearman_rho"), birds.get("spearman_rho")]
    if all(r is not None and r <= -0.35 for r in rhos):
        return 0.82
    return 0.70


def main():
    raw, retrieved = fetch_zip()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        text = zf.read(name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows = list(reader)
    result = json.loads((HERE / "result.json").read_text())
    result["datasets"] = [{
        "id": "anage-build-15",
        "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
        "landing_url": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gks1155",
        "version": "build 15",
        "license": "CC BY 3.0 (Human Ageing Genomic Resources terms)",
        "files": [{
            "name": "dataset.zip",
            "download_url": ZIP_URL,
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }],
        "role": "adult body mass and litter or clutch size of mammals and birds",
    }]
    needed = ["Class", "Adult weight (g)", "Litter/Clutch size"]
    missing = [c for c in needed if c not in reader.fieldnames]
    if missing:
        result.update(status="complete", verdict="inconclusive", reason="data-unavailable",
                      data_kind="none", confidence=0.40)
        result["measured"] = {"value": None, "unit": "Spearman rho", "n": 0, "uncertainty": None,
                              "extra": {"missing_columns": missing}}
        result["method"] = "The AnAge zip did not contain the expected mass and litter columns."
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return

    mammals = score_class(rows, "mammalia")
    birds = score_class(rows, "aves")
    # Descriptive all-row correlation, not used for the verdict.
    weights, litters = [], []
    for row in rows:
        w = num(row.get("Adult weight (g)"))
        lit = num(row.get("Litter/Clutch size"))
        if w is None or lit is None or w <= 0 or lit <= 0:
            continue
        weights.append(w)
        litters.append(lit)
    if len(weights) >= 3:
        all_rho, all_p = stats.spearmanr(weights, litters)
        all_stats = {"n": len(weights), "spearman_rho": float(all_rho), "spearman_p": float(all_p)}
    else:
        all_stats = {"n": len(weights)}

    if not mammals["scorable"] or not birds["scorable"]:
        verdict, reason = "inconclusive", "underpowered"
    elif mammals["passes"] and birds["passes"]:
        verdict, reason = "supports", None
    elif mammals["fails"] and birds["fails"]:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None

    # The reported value is the mammal correlation; both classes are in extra and both set the verdict.
    result.update(status="complete", verdict=verdict, data_kind="biological",
                  confidence=confidence(verdict, mammals, birds))
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["measured"] = {
        "value": mammals.get("spearman_rho"),
        "unit": "Spearman rho of adult weight vs litter size within Mammalia",
        "n": mammals.get("n"),
        "uncertainty": None,
        "extra": {"mammalia": mammals, "aves": birds, "all_classes_descriptive": all_stats},
    }
    result["method"] = (
        "Downloaded the AnAge build zip and, within Mammalia and within Aves, computed the Spearman "
        "correlation of adult weight with litter or clutch size and compared median brood size below "
        "and above the median adult weight. Both classes had to meet the pre-registered pass rule to "
        "support, or the fail rule to refute. The all-class correlation is descriptive only."
    )
    result["results_summary"] = [
        f"Mammalia n={mammals.get('n')} rho={mammals.get('spearman_rho')} p={mammals.get('spearman_p')} "
        f"lighter median litter={mammals.get('median_litter_lighter')} heavier={mammals.get('median_litter_heavier')}.",
        f"Aves n={birds.get('n')} rho={birds.get('spearman_rho')} p={birds.get('spearman_p')} "
        f"lighter median clutch={birds.get('median_litter_lighter')} heavier={birds.get('median_litter_heavier')}.",
        f"Verdict {verdict}.",
    ]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(result["measured"], indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, mammals.get("spearman_rho"), birds.get("spearman_rho"))


if __name__ == "__main__":
    main()
