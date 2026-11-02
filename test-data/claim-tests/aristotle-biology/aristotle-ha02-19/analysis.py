#!/usr/bin/env python3
"""aristotle-ha02-19: scaly fishes oviparous, cartilaginous fishes viviparous, Lophius the exception.

Re-run: python3 analysis.py
Downloads FishBase v25.04 species, families, and reproduc parquet into ./data (gitignored).
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
BASE = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
FILES = {
    "species": BASE + "species.parquet",
    "families": BASE + "families.parquet",
    "reproduc": BASE + "reproduc.parquet",
}
VIV = ("internal live bear", "internal bearer", "live bearer")
OVI = ("egg scatter", "brood hider", "clutch tender", "nester", "external brood")
UA = {"User-Agent": "delphi-claim-tests/1.0 (aristotle-ha02-19)"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(name, url):
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / f"{name}.parquet"
    meta_path = dest.with_suffix(".parquet.meta.json")
    if dest.exists() and dest.stat().st_size > 0 and meta_path.exists():
        return json.loads(meta_path.read_text())
    r = requests.get(url, timeout=180, headers=UA)
    r.raise_for_status()
    meta = {
        "download_url": r.url,
        "requested_url": url,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
    }
    dest.write_bytes(r.content)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def col(df, options):
    lower = {c.lower(): c for c in df.columns}
    for o in options:
        if o.lower() in lower:
            return lower[o.lower()]
    return None


def guild_of(val):
    if not isinstance(val, str) or not val.strip():
        return None
    s = val.lower()
    if any(t in s for t in VIV):
        return "viviparous"
    if any(t in s for t in OVI):
        return "oviparous"
    return "other"


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    metas = {name: fetch(name, url) for name, url in FILES.items()}
    species = pd.read_parquet(DATA / "species.parquet")
    families = pd.read_parquet(DATA / "families.parquet")
    reproduc = pd.read_parquet(DATA / "reproduc.parquet")
    deviations = []

    spec_code = col(species, ["SpecCode"])
    genus = col(species, ["Genus"])
    epithet = col(species, ["Species"])
    fam_code_sp = col(species, ["FamCode"])
    fam_code_fam = col(families, ["FamCode"])
    class_col = col(families, ["Class", "classname", "ClassName"])
    if class_col is None:
        class_col = col(species, ["Class", "classname", "ClassName"])
        fam_code_fam = None
    rep_code = col(reproduc, ["SpecCode"])
    guild2 = col(reproduc, ["RepGuild2", "RepGuild", "ReproductiveGuild2"])
    if guild2 is None:
        # Pre-registered fallback: the column whose values use Balon's guild phrases.
        sample_cols = []
        for c in reproduc.columns:
            vals = reproduc[c].dropna().astype(str).str.lower()
            if vals.empty:
                continue
            hit = vals.str.contains("internal live bear|egg scatter|brood hider|nester|external brood", regex=True).any()
            if hit:
                sample_cols.append(c)
        if len(sample_cols) == 1:
            guild2 = sample_cols[0]
            deviations.append(
                f"RepGuild2 was not a column name. Used {guild2}, the only column containing Balon's guild phrases. Thresholds unchanged."
            )
        else:
            guild2 = None
            deviations.append(
                "No RepGuild2 column and no single Balon-guild column. Reproductive mode could not be coded."
            )

    if not all([spec_code, genus, epithet, rep_code]) or guild2 is None or (class_col is None):
        result = json.loads((HERE / "result.json").read_text())
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["confidence"] = 0.60
        result["data_kind"] = "none"
        result["deviations"] = deviations + [
            f"columns species={list(species.columns)[:40]} families={list(families.columns)[:40]} reproduc={list(reproduc.columns)[:40]}"
        ]
        result["measured"] = {
            "value": None,
            "unit": "coded species",
            "n": 0,
            "uncertainty": "required columns were absent",
            "extra": {"species_columns": list(map(str, species.columns)), "reproduc_columns": list(map(str, reproduc.columns))},
        }
        result["method"] = "Opened the FishBase v25.04 parquet files and could not find the class crosswalk or the reproductive-guild column required by the pre-registration."
        result["datasets"] = dataset_block(metas)
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"verdict": "inconclusive", "deviations": result["deviations"]}, indent=2))
        return

    if fam_code_fam and fam_code_sp and class_col in families.columns:
        cross = families[[fam_code_fam, class_col]].drop_duplicates()
        cross = cross.rename(columns={fam_code_fam: "FamCode", class_col: "Class"})
        sp = species.rename(columns={spec_code: "SpecCode", genus: "Genus", epithet: "Species", fam_code_sp: "FamCode"})
        sp = sp.merge(cross, on="FamCode", how="left")
    else:
        sp = species.rename(columns={spec_code: "SpecCode", genus: "Genus", epithet: "Species", class_col: "Class"})
        deviations.append("Class was taken from the species table rather than families. Thresholds unchanged.")

    rep = reproduc.rename(columns={rep_code: "SpecCode", guild2: "RepGuild2"})
    rep["mode_row"] = rep["RepGuild2"].map(guild_of)
    # any viviparous row wins; else any oviparous row
    def agg(s):
        vals = set(s.dropna())
        if "viviparous" in vals:
            return "viviparous"
        if "oviparous" in vals:
            return "oviparous"
        return None
    modes = rep.groupby("SpecCode")["mode_row"].apply(agg).rename("mode")
    sp = sp.merge(modes, left_on="SpecCode", right_index=True, how="left")
    sp["ClassStr"] = sp["Class"].astype(str)
    low = sp["ClassStr"].str.lower()
    ray_labels = ("teleostei", "chondrostei", "holostei", "cladistii")
    class_counts = {str(k): int(v) for k, v in sp["ClassStr"].value_counts(dropna=False).items()}
    if not low.str.contains("actinopteryg", na=False).any():
        deviations.append(
            "FishBase v25.04 Class has no value containing Actinopterygii. "
            "The ray-finned labels Teleostei, Chondrostei, Holostei, and Cladistii were used as that pre-registered clause. "
            "Elasmobranchii and Holocephali remain the cartilaginous clause. "
            "A pass still requires zero counterexamples, a clause still fails at five or more, and the minima stay 100 and 30."
        )
        sp["bony"] = low.isin(ray_labels)
    else:
        sp["bony"] = low.str.contains("actinopteryg", na=False)
    sp["cart"] = low.str.contains("elasmobranch|holocephal|chondrichth", na=False, regex=True)
    coded = sp[sp["mode"].isin(["viviparous", "oviparous"])].copy()

    bony = coded[coded["bony"]]
    cart = coded[coded["cart"]]
    bony_viv = bony[bony["mode"] == "viviparous"]
    cart_ovi = cart[cart["mode"] == "oviparous"]
    lophius = coded[coded["Genus"].astype(str).str.lower() == "lophius"]
    lophius_viv = lophius[lophius["mode"] == "viviparous"]

    def clause(n_scored, n_bad, minimum):
        if n_scored < minimum and n_bad < 5:
            return "underpowered"
        if n_bad >= 5:
            return "fail"
        if n_bad == 0 and n_scored >= minimum:
            return "pass"
        return "band"  # 1 to 4

    bony_clause = clause(len(bony), len(bony_viv), 100)
    cart_clause = clause(len(cart), len(cart_ovi), 30)
    if len(lophius) == 0:
        exception = "unscored"
    elif len(lophius_viv):
        exception = "fail"
    else:
        exception = "pass"

    if bony_clause == "underpowered" or cart_clause == "underpowered":
        if bony_clause == "fail" and cart_clause == "fail":
            verdict, confidence, reason = "refutes", 0.80, None
        elif bony_clause == "fail" or cart_clause == "fail":
            verdict, confidence, reason = "mixed", 0.55, None
        else:
            verdict, confidence, reason = "inconclusive", 0.60, "underpowered"
    elif bony_clause == "pass" and cart_clause == "pass" and exception == "pass":
        verdict, confidence, reason = "supports", 0.75, None
    elif bony_clause == "fail" and cart_clause == "fail":
        verdict, confidence, reason = "refutes", 0.80, None
    else:
        verdict, confidence, reason = "mixed", 0.55, None

    def names(df, limit=40):
        out = (df["Genus"].astype(str) + " " + df["Species"].astype(str)).drop_duplicates().sort_values()
        return out.head(limit).tolist()

    counter = pd.concat([
        bony_viv.assign(why="actinopterygian internal live bearer"),
        cart_ovi.assign(why="chondrichthyan egg-layer"),
    ], ignore_index=True)
    keep = [c for c in ("Genus", "Species", "ClassStr", "mode", "why") if c in counter.columns]
    if len(counter):
        counter[keep].drop_duplicates().sort_values(["why", "Genus", "Species"]).to_csv(DERIVED / "counterexamples.csv", index=False)
    else:
        (DERIVED / "counterexamples.csv").write_text("Genus,Species,ClassStr,mode,why\n")

    measured = {
        "value": int(len(bony_viv)),
        "unit": "Actinopterygii species coded as internal live bearers",
        "n": int(len(bony)),
        "uncertainty": "FishBase RepGuild2 codes; a species with any internal-live-bearer row is viviparous",
        "extra": {
            "bony_scored": int(len(bony)),
            "bony_viviparous": int(len(bony_viv)),
            "bony_clause": bony_clause,
            "cartilaginous_scored": int(len(cart)),
            "cartilaginous_egglaying": int(len(cart_ovi)),
            "cartilaginous_clause": cart_clause,
            "lophius_scored": int(len(lophius)),
            "lophius_viviparous": int(len(lophius_viv)),
            "lophius_exception": exception,
            "lophius_species": names(lophius, 20),
            "bony_viviparous_examples": names(bony_viv, 30),
            "cartilaginous_egglaying_examples": names(cart_ovi, 30),
            "guild_column": guild2,
            "class_column": class_col,
            "class_counts_species": class_counts,
            "lophius_classes": sorted({str(x) for x in lophius["ClassStr"].dropna().unique()}),
        },
    }
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological"
    result.pop("reason", None)
    if reason:
        result["reason"] = reason
    if deviations:
        result["deviations"] = deviations
    result["datasets"] = dataset_block(metas)
    result["method"] = (
        "Downloaded FishBase v25.04 species, families, and reproduc. Joined class through FamCode. "
        "Coded RepGuild2 as internal live bearer or as an egg-laying guild (egg scatterers, brood hiders, "
        "clutch tenders, nesters, external brooders). RepGuild1 alone was not used. A species with any "
        "live-bearer row is viviparous. Ray-finned fishes are Actinopterygii when that class string is present, "
        "and otherwise the FishBase labels Teleostei, Chondrostei, Holostei, and Cladistii. Elasmobranchii plus "
        "Holocephali are the cartilaginous clause. Lophius is the fishing-frog. Thresholds are those in the pre-registration."
    )
    result["measured"] = measured
    if verdict == "refutes":
        headline = (
            f"FishBase codes {len(bony_viv)} live-bearing ray-finned species of {len(bony)} scored, "
            f"and {len(cart_ovi)} egg-laying cartilaginous species of {len(cart)} scored, so neither universal holds."
        )
    elif verdict == "supports":
        headline = "Every coded ray-finned fish is an egg-layer, every coded cartilaginous fish is a live-bearer, and Lophius is not a live-bearer."
    elif verdict == "mixed":
        headline = (
            f"The ray-finned clause is {bony_clause} ({len(bony_viv)} live-bearers of {len(bony)}) and "
            f"the cartilaginous clause is {cart_clause} ({len(cart_ovi)} egg-layers of {len(cart)}); "
            f"the Lophius exception is {exception}."
        )
    else:
        headline = "Too few species have a coded reproductive guild to apply the pre-registered thresholds."
    result["results_summary"] = [headline]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "extra": {k: measured["extra"][k] for k in measured["extra"] if k not in ("bony_viviparous_examples", "cartilaginous_egglaying_examples")}}, indent=2))


def dataset_block(metas):
    return [
        {
            "id": "fishbase-v25.04-" + name,
            "name": f"FishBase {name} table, rfishbase snapshot v25.04",
            "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
            "doi": None,
            "version": "v25.04",
            "license": "CC BY-NC 3.0 (FishBase)",
            "files": [{k: metas[name][k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
            "role": {"species": "scientific name and family code", "families": "class of each family", "reproduc": "Balon reproductive guild"}[name],
        }
        for name in ("species", "families", "reproduc")
    ]


if __name__ == "__main__":
    main()
