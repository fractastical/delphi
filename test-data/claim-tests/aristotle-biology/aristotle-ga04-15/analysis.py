#!/usr/bin/env python3
"""aristotle-ga04-15: large animals bear few young, small animals many.

Pre-registered in result.json before either data file was opened.
Walking: terrestrial mammals (reptiles combined when n >= 40).
Flying: birds. Swimming: FishBase absolute fecundity vs body weight.
Spearman rho, two-sided. No outlier removal.
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
import pyarrow.parquet as pq
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"

AMNIOTE_URL = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
AMNIOTE_MD5 = "10e7c14395d95ed7f53258f96fadb4f7"
FEC_URL = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/fecundity.parquet"
SPP_URL = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/species.parquet"

EXCLUDE_ORDERS = {"Chiroptera", "Cetacea", "Sirenia"}
AQUATIC_FAMILIES = {
    "Balaenidae", "Balaenopteridae", "Delphinidae", "Phocoenidae", "Monodontidae",
    "Iniidae", "Platanistidae", "Ziphiidae", "Eschrichtiidae", "Physeteridae",
    "Kogiidae", "Lipotidae", "Pontoporiidae", "Neobalaenidae", "Cetotheriidae",
    "Trichechidae", "Dugongidae",
}
UA = "delphisci-claim-test/aristotle-biology"
MIN_N = 40


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as resp:
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


def find_col(columns, *options):
    lower = {c.lower(): c for c in columns}
    for opt in options:
        if opt.lower() in lower:
            return lower[opt.lower()]
    return None


def spearman(mass, young):
    if len(mass) < 3:
        return {"n": int(len(mass)), "rho": None, "p": None, "class": "underpowered"}
    res = stats.spearmanr(mass, young)
    rho = float(res.statistic)
    p = float(res.pvalue)
    n = int(len(mass))
    if n < MIN_N or rho is None or math.isnan(rho):
        label = "underpowered"
    elif rho < -0.20 and p < 0.01:
        label = "pass"
    elif rho >= 0:
        label = "fail"
    else:
        label = "weak"
    return {
        "n": n,
        "rho": rho,
        "p": p,
        "class": label,
        "mass_min_g": float(np.min(mass)),
        "mass_max_g": float(np.max(mass)),
        "young_min": float(np.min(young)),
        "young_max": float(np.max(young)),
    }


def combine_walking(mammal, reptile):
    if reptile["class"] == "underpowered":
        return mammal["class"]
    if mammal["class"] == "underpowered":
        return reptile["class"]
    if mammal["class"] == "pass" and reptile["class"] == "pass":
        return "pass"
    if mammal["class"] == "fail" and reptile["class"] == "fail":
        return "fail"
    return "weak"


def overall(walking, flying, swimming):
    statuses = {"walking": walking, "flying": flying, "swimming": swimming}
    measured = [s for s in statuses.values() if s != "underpowered"]
    if len(measured) < 2:
        return "inconclusive", "underpowered"
    if all(s == "pass" for s in statuses.values()):
        return "supports", None
    if sum(s == "fail" for s in statuses.values()) >= 2:
        return "refutes", None
    return "mixed", None


def confidence(verdict, blocks):
    if verdict == "inconclusive":
        return 0.35
    base = {"supports": 0.7, "refutes": 0.7, "mixed": 0.6}[verdict]
    for block in blocks:
        rho = block.get("rho")
        if rho is None or block.get("class") == "underpowered":
            continue
        if abs(rho - (-0.20)) < 0.05 or abs(rho) < 0.05:
            base -= 0.1
            break
    return round(max(0.3, base), 2)


def amniote_block(df, mask):
    sub = df.loc[mask, ["adult_body_mass_g", "litter_or_clutch_size_n"]].dropna()
    sub = sub[(sub["adult_body_mass_g"] > 0) & (sub["litter_or_clutch_size_n"] > 0)]
    return spearman(sub["adult_body_mass_g"].to_numpy(), sub["litter_or_clutch_size_n"].to_numpy())


def fish_from_paired(fec: pd.DataFrame):
    spec = find_col(fec.columns, "SpecCode", "speccode")
    fmin = find_col(fec.columns, "FecundityMin", "fecunditymin")
    fmax = find_col(fec.columns, "FecundityMax", "fecunditymax")
    body = find_col(fec.columns, "BodyWeight", "bodyweight")
    if spec is None or fmin is None or body is None:
        return None, {"spec": spec, "fmin": fmin, "fmax": fmax, "body": body, "reason": "missing-column"}
    work = fec[[spec, fmin, body] + ([fmax] if fmax else [])].copy()
    work[fmin] = pd.to_numeric(work[fmin], errors="coerce")
    work[body] = pd.to_numeric(work[body], errors="coerce")
    if fmax:
        work[fmax] = pd.to_numeric(work[fmax], errors="coerce")
        both = work[fmin].gt(0) & work[fmax].gt(0)
        work["fecundity"] = np.where(both, (work[fmin] + work[fmax]) / 2.0, work[fmin])
    else:
        work["fecundity"] = work[fmin]
    work = work[(work["fecundity"] > 0) & (work[body] > 0)]
    if work.empty:
        return spearman(np.array([]), np.array([])), {"rows": 0, "body_column": body}
    grouped = work.groupby(spec).agg(fecundity=("fecundity", "median"), mass=(body, "median"))
    block = spearman(grouped["mass"].to_numpy(), grouped["fecundity"].to_numpy())
    block["aggregation"] = "median of absolute fecundity and BodyWeight on the same fecundity record"
    block["rows"] = int(len(work))
    block["body_column"] = body
    return block, {"rows": int(len(work)), "species": int(len(grouped)), "body_column": body}


def fish_fallback(fec: pd.DataFrame, species: pd.DataFrame):
    spec_f = find_col(fec.columns, "SpecCode", "speccode")
    fmin = find_col(fec.columns, "FecundityMin", "fecunditymin")
    fmax = find_col(fec.columns, "FecundityMax", "fecunditymax")
    spec_s = find_col(species.columns, "SpecCode", "speccode")
    weight = find_col(species.columns, "Weight", "weight")
    if not all([spec_f, fmin, spec_s, weight]):
        return {
            "n": 0, "rho": None, "p": None, "class": "underpowered",
            "note": "fallback columns missing",
            "columns_species": list(species.columns),
            "columns_fecundity": list(fec.columns),
        }
    work = fec[[spec_f, fmin] + ([fmax] if fmax else [])].copy()
    work[fmin] = pd.to_numeric(work[fmin], errors="coerce")
    if fmax:
        work[fmax] = pd.to_numeric(work[fmax], errors="coerce")
        both = work[fmin].gt(0) & work[fmax].gt(0)
        work["fecundity"] = np.where(both, (work[fmin] + work[fmax]) / 2.0, work[fmin])
    else:
        work["fecundity"] = work[fmin]
    work = work[work["fecundity"] > 0]
    med = work.groupby(spec_f)["fecundity"].median()
    spp = species[[spec_s, weight]].copy()
    spp[weight] = pd.to_numeric(spp[weight], errors="coerce")
    spp = spp[spp[weight] > 0].drop_duplicates(spec_s)
    joined = med.to_frame("fecundity").join(spp.set_index(spec_s), how="inner")
    block = spearman(joined[weight].to_numpy(), joined["fecundity"].to_numpy())
    block["aggregation"] = "species-median absolute fecundity joined to species.Weight"
    block["weight_column"] = weight
    return block


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    am_meta = fetch(AMNIOTE_URL, DATA / "Amniote_Database_Aug_2015.csv")
    fec_meta = fetch(FEC_URL, DATA / "fecundity.parquet")
    spp_meta = fetch(SPP_URL, DATA / "species.parquet")
    am_meta["md5_matches_archive_page"] = am_meta["md5"] == AMNIOTE_MD5

    am = pd.read_csv(DATA / "Amniote_Database_Aug_2015.csv", low_memory=False, na_values=["-999"])
    terrestrial = (am["class"] == "Mammalia") & (~am["order"].isin(EXCLUDE_ORDERS)) & (~am["family"].isin(AQUATIC_FAMILIES))
    bats = (am["class"] == "Mammalia") & (am["order"] == "Chiroptera")
    reptiles = am["class"] == "Reptilia"
    birds = am["class"] == "Aves"
    mammal = amniote_block(am, terrestrial)
    reptile = amniote_block(am, reptiles)
    bat = amniote_block(am, bats)
    flying = amniote_block(am, birds)
    walking_label = combine_walking(mammal, reptile)

    fec = pq.read_table(DATA / "fecundity.parquet").to_pandas()
    species = pq.read_table(DATA / "species.parquet").to_pandas()
    paired, paired_note = fish_from_paired(fec)
    used_fallback = paired is None or paired.get("n", 0) < MIN_N
    fallback = fish_fallback(fec, species) if used_fallback else None
    swimming_block = fallback if used_fallback else paired
    if swimming_block is None:
        swimming_block = {"n": 0, "rho": None, "p": None, "class": "underpowered"}

    verdict, reason = overall(walking_label, flying["class"], swimming_block["class"])
    blocks_for_conf = [mammal, flying, swimming_block]
    conf = confidence(verdict, blocks_for_conf)

    headline_rho = mammal.get("rho")
    measured = {
        "value": headline_rho,
        "unit": "Spearman rho, terrestrial-mammal litter size vs adult body mass (full verdict uses all three groups)",
        "n": mammal.get("n"),
        "uncertainty": None if mammal.get("p") is None else f"two-sided p = {mammal['p']:.3e}",
        "extra": {
            "walking_terrestrial_mammals": mammal,
            "walking_reptiles": reptile,
            "walking_combined": walking_label,
            "flying_birds": flying,
            "swimming": swimming_block,
            "swimming_used_fallback": used_fallback,
            "swimming_paired": paired,
            "bats_descriptive": bat,
            "fish_columns": [str(c) for c in fec.columns],
        },
    }
    summary = [
        f"Terrestrial mammals: n={mammal['n']}, rho={mammal['rho']}, p={mammal['p']}, {mammal['class']}.",
        f"Reptiles: n={reptile['n']}, rho={reptile['rho']}, p={reptile['p']}, {reptile['class']}. Walking combined: {walking_label}.",
        f"Birds: n={flying['n']}, rho={flying['rho']}, p={flying['p']}, {flying['class']}.",
        f"Fishes ({'fallback species.Weight' if used_fallback else 'paired BodyWeight'}): n={swimming_block.get('n')}, rho={swimming_block.get('rho')}, p={swimming_block.get('p')}, {swimming_block.get('class')}.",
        f"Bats, not in the walking set: n={bat['n']}, rho={bat['rho']}, {bat['class']}.",
        f"Verdict {verdict}.",
    ]
    method = (
        "Spearman correlations of offspring number against adult body mass. "
        "Mammals, birds and reptiles come from the Amniote Life-History Database, with -999 read as missing. "
        "Terrestrial mammals exclude bats, the orders Cetacea and Sirenia, and the named whale and sirenian families. "
        "Fishes use FishBase v25.04 absolute fecundity (midpoint of min and max when both are positive, otherwise the minimum). "
        + (
            "Fewer than 40 species had a body weight on the fecundity record, so the pre-registered fallback joined median fecundity to species.Weight."
            if used_fallback
            else "Body weight was taken from the same fecundity record and averaged as a species median."
        )
    )
    derived = {
        "amniote_rows": int(len(am)),
        "fecundity_rows": int(len(fec)),
        "species_rows": int(len(species)),
        "paired_note": paired_note,
        "groups": measured["extra"],
        "verdict": verdict,
        "reason": reason,
    }
    (DERIVED / "measured.json").write_text(json.dumps(clean(derived), indent=2) + "\n")

    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["method"] = method
    result["measured"] = clean(measured)
    result["results_summary"] = summary
    result["datasets"] = [
        {
            "id": "amniote-life-history-database-2015",
            "name": "Amniote Life-History Database (Myhrvold et al. 2015)",
            "landing_url": "https://esapubs.org/archive/ecol/E096/269/",
            "doi": "10.1890/15-0846.1",
            "version": "Aug 2015",
            "license": "CC0",
            "files": [{k: am_meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
            "role": "adult body mass and litter or clutch size for mammals, birds and reptiles",
        },
        {
            "id": "fishbase-v25.04-fecundity",
            "name": "FishBase v25.04 fecundity and species tables (rfishbase parquet mirror)",
            "landing_url": "https://www.fishbase.se/",
            "doi": None,
            "version": "04/2025",
            "license": "CC BY-NC 4.0",
            "files": [
                {**{k: fec_meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}, "name": "fecundity.parquet"},
                {**{k: spp_meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}, "name": "species.parquet"},
            ],
            "role": "absolute fecundity and body weight of fishes",
        },
    ]
    devs = list(result.get("deviations") or [])
    if am_meta["md5"] != AMNIOTE_MD5:
        devs.append("Amniote file md5 did not match the Ecological Archives page; counts were still computed from the downloaded bytes and the mismatch is recorded on the file object.")
    if used_fallback and paired is not None and paired.get("n", 0) < MIN_N:
        devs.append("Paired fecundity-record body weights covered fewer than 40 species, so the pre-registered species.Weight fallback was used for the swimming verdict.")
    if devs:
        result["deviations"] = devs
    RESULT.write_text(json.dumps(clean(result), indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": conf, "mammal": mammal, "reptile": reptile, "flying": flying, "swimming": {k: swimming_block.get(k) for k in ("n", "rho", "p", "class")}}, indent=2))


if __name__ == "__main__":
    main()
