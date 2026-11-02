#!/usr/bin/env python3
"""Reproductive mode of cartilaginous fishes (aristotle-ga03-01).

Pre-registered in result.json before these tables were opened. FishBase v25.04
RepGuild2 is the primary coding; Sharkipedia trait "Reproductive mode" is the
second. Thresholds: pass if the oviparous fraction is <= 0.05 with n large
enough; refute if that fraction is >= 0.20; mixed in between.

Run from this directory: python3 analysis.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0 (aristotle-ga03-01)"}
FB = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
SHARK_URL = (
    "https://zenodo.org/api/records/6656525/files/"
    "Sharkipedia-Traits-v1.0-22-01-25.csv/content"
)
SHARK_MD5 = "113d0bc4d1441df9a0969c33663847fa"
SHARK_SIZE = 812477
CHOND = ("elasmobranchii", "holocephali", "chondrichthyes")
LIVE_SUB = (
    "vivipar",
    "placental",
    "lecithotroph",
    "histotroph",
    "oophag",
    "adelphophag",
    "matrotroph",
    "trophonem",
    "aplacental",
    "yolk-sac",
    "yolk sac",
)


def now_iso(path: Path) -> str:
    stamp = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        with requests.get(url, headers=UA, timeout=300, stream=True) as response:
            response.raise_for_status()
            partial = dest.with_suffix(dest.suffix + ".part")
            with partial.open("wb") as handle:
                for chunk in response.iter_content(1 << 16):
                    if chunk:
                        handle.write(chunk)
            partial.replace(dest)
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": now_iso(dest),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
    }


def find_col(columns, pattern: str, forbid: str | None = None):
    hits = []
    for name in columns:
        low = str(name).lower()
        if re.search(pattern, low) and not (forbid and re.search(forbid, low)):
            hits.append(name)
    return hits[0] if hits else None


def guild_class(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "unknown"
    text = str(value).strip().lower()
    if not text or text in {"nan", "none", "null"}:
        return "unknown"
    live = "internal live" in text
    oviparous = any(
        token in text
        for token in ("egg scatter", "brood hid", "clutch tend", "nester", "external brood")
    )
    if live and oviparous:
        return "ambiguous"
    if live:
        return "live"
    if oviparous:
        return "oviparous"
    return "unknown"


def shark_class(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "unknown"
    text = str(value).strip().lower()
    if not text:
        return "unknown"
    oviparous = "ovipar" in text
    live = any(token in text for token in LIVE_SUB)
    if oviparous and live:
        return "ambiguous"
    if oviparous:
        return "oviparous"
    if live:
        return "live"
    return "unknown"


def collapse(series: pd.Series) -> str:
    labels = {guild_class(value) if False else value for value in series}
    labels.discard("unknown")
    labels.discard("ambiguous")
    if not labels:
        if (series == "ambiguous").any():
            return "ambiguous"
        return "unknown"
    if len(labels) > 1:
        return "conflict"
    return next(iter(labels))


def fraction_call(p_ovi: float, n: int, minimum: int) -> str:
    if n < minimum:
        return "underpowered"
    if p_ovi <= 0.05:
        return "supports"
    if p_ovi >= 0.20:
        return "refutes"
    return "mixed"


def summarise(labels: pd.Series) -> dict:
    known = labels[labels.isin(["live", "oviparous"])]
    n_live = int((known == "live").sum())
    n_ovi = int((known == "oviparous").sum())
    n = n_live + n_ovi
    p_ovi = (n_ovi / n) if n else None
    return {
        "n_species_coded": n,
        "n_live": n_live,
        "n_oviparous": n_ovi,
        "p_oviparous": None if p_ovi is None else round(p_ovi, 4),
        "n_unknown": int((labels == "unknown").sum()),
        "n_ambiguous": int((labels == "ambiguous").sum()),
        "n_conflict": int((labels == "conflict").sum()),
    }


def chondrichthyan_mask(frame: pd.DataFrame) -> pd.Series:
    """Match the class tokens only in taxonomy columns, not in free-text remarks."""
    mask = pd.Series(False, index=frame.index)
    tax_cols = [
        name for name in frame.columns
        if re.search(r"class|order|family|phylum|taxo|division", str(name), re.I)
        and not re.search(r"speccode|famcode|author|ref", str(name), re.I)
    ]
    columns = tax_cols or list(frame.columns)
    for name in columns:
        series = frame[name]
        if series.dtype != object and not pd.api.types.is_string_dtype(series):
            continue
        low = series.astype(str).str.lower()
        mask = mask | low.apply(lambda text: any(token in text for token in CHOND))
    return mask


def shell_failure(eggs: pd.DataFrame | None, reproduc: pd.DataFrame, live_codes) -> dict:
    frames = [("reproduc", reproduc)]
    if eggs is not None:
        frames.append(("eggs", eggs))
    shell_cols = []
    for label, frame in frames:
        for name in frame.columns:
            if re.search(r"shell|egg.?case|colour|color", str(name), re.I):
                shell_cols.append({"table": label, "column": str(name)})
    if not shell_cols:
        return {"tested": False, "failed": False, "columns": []}
    hard = re.compile(r"horn|keratin|hard", re.I)
    n_hard = 0
    for label, frame in frames:
        spec = find_col(frame.columns, r"speccode")
        if spec is None:
            continue
        sub = frame[frame[spec].isin(live_codes)]
        for column in [item["column"] for item in shell_cols if item["table"] == label]:
            n_hard += int(sub[column].astype(str).str.contains(hard, na=False).sum())
    return {
        "tested": True,
        "failed": n_hard >= 10,
        "n_hard_mentions_on_live_bearers": n_hard,
        "columns": shell_cols,
    }


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    deviations = []
    files = {
        "reproduc.parquet": fetch(FB + "reproduc.parquet", DATA / "reproduc.parquet"),
        "species.parquet": fetch(FB + "species.parquet", DATA / "species.parquet"),
        "families.parquet": fetch(FB + "families.parquet", DATA / "families.parquet"),
        "eggs.parquet": fetch(FB + "eggs.parquet", DATA / "eggs.parquet"),
        "Sharkipedia-Traits-v1.0-22-01-25.csv": fetch(
            SHARK_URL, DATA / "Sharkipedia-Traits-v1.0-22-01-25.csv"
        ),
    }
    shark_meta = files["Sharkipedia-Traits-v1.0-22-01-25.csv"]
    if shark_meta["md5"] != SHARK_MD5 or shark_meta["byte_size"] != SHARK_SIZE:
        deviations.append(
            "Sharkipedia file md5 or size does not match the Zenodo record metadata "
            f"registered before download (expected md5 {SHARK_MD5}, size {SHARK_SIZE}; "
            f"got md5 {shark_meta['md5']}, size {shark_meta['byte_size']})."
        )

    reproduc = pd.read_parquet(DATA / "reproduc.parquet")
    species = pd.read_parquet(DATA / "species.parquet")
    families = pd.read_parquet(DATA / "families.parquet")
    eggs = pd.read_parquet(DATA / "eggs.parquet")

    spec_s = find_col(species.columns, r"speccode")
    genus = find_col(species.columns, r"^genus$") or find_col(species.columns, r"genus")
    epithet = find_col(species.columns, r"^species$") or find_col(species.columns, r"species", r"speccode|speciesref")
    fam_s = find_col(species.columns, r"famcode")
    fam_f = find_col(families.columns, r"famcode")
    if not all([spec_s, genus, epithet, fam_s, fam_f]):
        deviations.append(
            "Species or families columns were not the documented SpecCode/Genus/Species/FamCode names; "
            f"species columns include {list(species.columns)[:40]}."
        )
    tax = species.merge(families, left_on=fam_s, right_on=fam_f, how="left", suffixes=("", "_fam"))
    mask = chondrichthyan_mask(tax)
    chond = tax.loc[mask, [spec_s, genus, epithet]].drop_duplicates()
    elasm_mask = pd.Series(False, index=tax.index)
    for name in tax.columns:
        if tax[name].dtype != object and not pd.api.types.is_string_dtype(tax[name]):
            continue
        elasm_mask = elasm_mask | tax[name].astype(str).str.lower().str.contains("elasmobranchii", na=False)
    elasm_codes = set(tax.loc[elasm_mask, spec_s])

    guild_col = find_col(reproduc.columns, r"guild2|repguild2")
    spec_r = find_col(reproduc.columns, r"speccode")
    if guild_col is None or spec_r is None:
        deviations.append(
            "reproduc.parquet has no RepGuild2 or SpecCode column; "
            f"columns are {list(reproduc.columns)}."
        )
        fish_summary = {"n_species_coded": 0, "p_oviparous": None}
        fish_call = "underpowered"
        live_codes = set()
        by_species = pd.Series(dtype=object)
    else:
        sub = reproduc[reproduc[spec_r].isin(set(chond[spec_s]))].copy()
        sub["label"] = sub[guild_col].map(guild_class)
        by_species = sub.groupby(spec_r)["label"].agg(
            lambda values: collapse(pd.Series(list(values)))
        )
        # species with no reproduc row stay unknown and out of n
        fish_summary = summarise(by_species)
        fish_summary["n_chondrichthyan_species_in_taxonomy"] = int(chond[spec_s].nunique())
        fish_summary["guild_column"] = str(guild_col)
        p = fish_summary["p_oviparous"]
        fish_call = fraction_call(0 if p is None else p, fish_summary["n_species_coded"], 50)
        live_codes = set(by_species[by_species == "live"].index)
        elasm_labels = by_species[by_species.index.isin(elasm_codes)]
        fish_summary["elasmobranchii_only"] = summarise(elasm_labels)
        ep = fish_summary["elasmobranchii_only"]["p_oviparous"]
        fish_summary["elasmobranchii_call"] = fraction_call(
            0 if ep is None else ep,
            fish_summary["elasmobranchii_only"]["n_species_coded"],
            50,
        )
        if {fish_call, fish_summary["elasmobranchii_call"]} == {"supports", "refutes"}:
            fish_call = "mixed"
            deviations.append(
                "All-chondrichthyan and elasmobranch-only fractions fell on opposite sides of the pass and fail thresholds, so FishBase is mixed."
            )

    shell = shell_failure(eggs, reproduc, live_codes)

    traits = pd.read_csv(DATA / "Sharkipedia-Traits-v1.0-22-01-25.csv", low_memory=False)
    trait_col = find_col(traits.columns, r"trait_name")
    value_col = find_col(traits.columns, r"^value$") or find_col(traits.columns, r"value", r"value_type")
    name_col = find_col(traits.columns, r"species_name")
    shark_summary = {"n_species_coded": 0, "p_oviparous": None}
    shark_call = "underpowered"
    if not all([trait_col, value_col, name_col]):
        deviations.append(f"Sharkipedia columns were not trait_name/value/species_name: {list(traits.columns)}")
    else:
        mode = traits[traits[trait_col].astype(str).str.strip().str.lower() == "reproductive mode"].copy()
        mode["label"] = mode[value_col].map(shark_class)
        by_name = mode.groupby(name_col)["label"].agg(lambda values: collapse(pd.Series(list(values))))
        shark_summary = summarise(by_name)
        shark_summary["n_trait_rows"] = int(len(mode))
        sp = shark_summary["p_oviparous"]
        shark_call = fraction_call(0 if sp is None else sp, shark_summary["n_species_coded"], 40)

    if fish_call != "underpowered" and shark_call != "underpowered":
        if {fish_call, shark_call} == {"supports", "refutes"}:
            mode_call = "mixed"
        elif fish_call == shark_call:
            mode_call = fish_call
        elif "refutes" in (fish_call, shark_call) and "mixed" in (fish_call, shark_call):
            mode_call = "mixed"
        elif fish_call == "supports" and shark_call == "mixed":
            mode_call = "mixed"
        elif shark_call == "supports" and fish_call == "mixed":
            mode_call = "mixed"
        else:
            mode_call = fish_call
        deciding = "both"
    elif fish_call != "underpowered":
        mode_call = fish_call
        deciding = "fishbase"
    elif shark_call != "underpowered":
        mode_call = shark_call
        deciding = "sharkipedia"
    else:
        mode_call = "underpowered"
        deciding = "none"

    if mode_call == "underpowered":
        verdict, reason = "inconclusive", "underpowered"
    elif mode_call == "refutes":
        verdict, reason = "refutes", None
    elif shell["tested"] and shell["failed"] and mode_call == "supports":
        verdict, reason = "mixed", None
    else:
        verdict, reason = mode_call, None

    if verdict == "supports":
        confidence = 0.75 if not shell["tested"] else 0.8
    elif verdict == "refutes":
        confidence = 0.75 if deciding == "both" else 0.6
    elif verdict == "mixed":
        confidence = 0.55
    else:
        confidence = 0.4

    measured = {
        "value": None if fish_summary.get("p_oviparous") is None else fish_summary["p_oviparous"],
        "unit": "oviparous fraction among chondrichthyan species with a FishBase guild class",
        "n": fish_summary.get("n_species_coded", 0),
        "uncertainty": None,
        "extra": {
            "fishbase": fish_summary,
            "fishbase_call": fish_call,
            "sharkipedia": shark_summary,
            "sharkipedia_call": shark_call,
            "deciding_source": deciding,
            "shell": shell,
        },
    }
    # If FishBase is underpowered and Sharkipedia decides, the headline value is Sharkipedia's.
    if deciding == "sharkipedia":
        measured["value"] = shark_summary.get("p_oviparous")
        measured["n"] = shark_summary.get("n_species_coded", 0)
        measured["unit"] = "oviparous fraction among Sharkipedia species with a reproductive-mode class"

    summary = [
        f"FishBase call {fish_call}: n={fish_summary.get('n_species_coded')}, "
        f"live={fish_summary.get('n_live')}, oviparous={fish_summary.get('n_oviparous')}, "
        f"p_oviparous={fish_summary.get('p_oviparous')}.",
        f"Sharkipedia call {shark_call}: n={shark_summary.get('n_species_coded')}, "
        f"p_oviparous={shark_summary.get('p_oviparous')}.",
        f"Deciding source: {deciding}. Shell clause tested={shell['tested']} failed={shell['failed']}.",
        f"Verdict {verdict}.",
    ]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "summary": summary, "deviations": deviations}, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["method"] = (
        "Downloaded the FishBase v25.04 reproduc, species, families and eggs parquet files and the "
        "Sharkipedia traits CSV, checked the Zenodo md5, joined cartilaginous fishes on the class names "
        "fixed at registration, mapped RepGuild2 and the Reproductive mode trait with the registered "
        "substrings, and applied the 0.05 / 0.20 rules. The shell-colour clause ran only if a matching column existed."
    )
    result["measured"] = measured
    result["results_summary"] = summary
    if deviations:
        result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "fishbase-v25.04-reproduc-parquet",
            "name": "FishBase v25.04 reproduc, species, families and eggs tables (rfishbase parquet snapshot)",
            "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
            "doi": None,
            "version": "v25.04",
            "license": "CC BY-NC 4.0",
            "files": [
                {"name": name, **meta}
                for name, meta in files.items()
                if name.endswith(".parquet")
            ],
            "role": "Balon reproductive guild and taxonomy for cartilaginous fishes",
        },
        {
            "id": "sharkipedia-traits-v1.0-zenodo-6656525",
            "name": "Sharkipedia traits v1.0",
            "landing_url": "https://zenodo.org/records/6656525",
            "doi": "10.5281/zenodo.6656525",
            "version": "1.0",
            "license": "CC BY 4.0",
            "files": [{"name": "Sharkipedia-Traits-v1.0-22-01-25.csv", **files["Sharkipedia-Traits-v1.0-22-01-25.csv"]}],
            "role": "species-level reproductive mode for sharks and rays",
        },
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "reason": reason, "measured": measured}, indent=2))


if __name__ == "__main__":
    main()
