#!/usr/bin/env python3
"""aristotle-ha06-14: elasmobranch viviparity versus actinopterygian oviparity.

Rules are those in result.json. Run: python3 analysis.py
Needs pandas and pyarrow.
"""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
DATA = HERE / "data"
BASE = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/"
FILES = {
    "species.parquet": ["SpecCode", "Genus", "Species", "FamCode"],
    "families.parquet": ["FamCode", "Class", "Order", "Family"],
    "reproduc.parquet": ["SpecCode", "RepGuild1", "RepGuild2", "ReproMode"],
}


def fetch(name):
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    url = BASE + name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
        path.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    raw = path.read_bytes()
    return path, {
        "name": name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def row_kind(guild1, guild2):
    g1 = "" if pd.isna(guild1) else str(guild1).casefold()
    g2 = "" if pd.isna(guild2) else str(guild2).casefold()
    if not g1 and not g2:
        return "empty"
    internal = ("internal" in g2 and "bear" in g2) or ("vivip" in g2)
    if internal:
        return "viviparous"
    return "oviparous"


def main():
    result = json.loads(RESULT.read_text())
    DERIVED.mkdir(parents=True, exist_ok=True)
    file_infos = []
    frames = {}
    for name, cols in FILES.items():
        path, info = fetch(name)
        file_infos.append(info)
        frames[name] = pd.read_parquet(path, columns=cols)

    repro = frames["reproduc.parquet"].copy()
    guild2 = repro["RepGuild2"].dropna().astype(str)
    vocab_hit = guild2.str.contains("bear|vivip|ovipar", case=False, regex=True).any()
    nonempty_g2 = int(guild2.shape[0])
    if nonempty_g2 > 100 and not bool(vocab_hit):
        top = guild2.str.casefold().value_counts().head(15)
        measured = {
            "value": None,
            "unit": "proportion",
            "n": nonempty_g2,
            "extra": {"top_repguild2": top.to_dict()},
        }
        result.update({
            "status": "complete",
            "verdict": "inconclusive",
            "reason": "not-operationalizable",
            "confidence": 0.35,
            "data_kind": "none",
            "measured": measured,
            "method": "Loaded FishBase reproduc. RepGuild2 did not contain bearer, viviparous or oviparous strings, so the pre-registered map was not applied.",
        })
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
        print("inconclusive vocabulary")
        return

    repro["kind"] = [row_kind(a, b) for a, b in zip(repro["RepGuild1"], repro["RepGuild2"])]
    species = frames["species.parquet"].copy()
    families = frames["families.parquet"][["FamCode", "Class", "Order", "Family"]].drop_duplicates("FamCode")
    species = species.merge(families, on="FamCode", how="left")
    species["binomial"] = (species["Genus"].fillna("").astype(str).str.strip() + " " + species["Species"].fillna("").astype(str).str.strip()).str.strip()
    species["class_key"] = species["Class"].fillna("").astype(str).str.strip().str.casefold()
    species["genus_key"] = species["Genus"].fillna("").astype(str).str.strip().str.casefold()

    kinds = repro.groupby("SpecCode")["kind"].apply(lambda s: set(x for x in s if x != "empty"))
    species = species.merge(kinds.rename("kinds"), left_on="SpecCode", right_index=True, how="left")

    def mode_of(kinds_set):
        if not isinstance(kinds_set, set) or not kinds_set:
            return "unknown"
        viv = "viviparous" in kinds_set
        ovi = "oviparous" in kinds_set
        if viv and ovi:
            return "mixed"
        if viv:
            return "viviparous"
        if ovi:
            return "oviparous"
        return "unknown"

    species["mode"] = species["kinds"].map(mode_of)

    def proportion(class_key, positive):
        sub = species[(species["class_key"] == class_key) & (species["mode"] != "unknown")]
        n = int(sub.shape[0])
        if positive == "viviparous":
            k = int((sub["mode"] == "viviparous").sum())
        else:
            k = int((sub["mode"] == "oviparous").sum())
        return n, k, (k / n if n else None)

    n_el, k_el, p_el = proportion("elasmobranchii", "viviparous")
    n_act, k_act, p_act = proportion("actinopterygii", "oviparous")
    holo = species[(species["class_key"] == "holocephali") & (species["mode"] != "unknown")]
    lophius = species[(species["genus_key"] == "lophius") & (species["mode"] != "unknown")]
    lophius_modes = sorted(lophius["mode"].unique().tolist())
    lophius_all_ovi = (len(lophius) >= 1) and set(lophius_modes) == {"oviparous"}

    def counts(class_key):
        sub = species[species["class_key"] == class_key]
        return {m: int((sub["mode"] == m).sum()) for m in ["viviparous", "oviparous", "mixed", "unknown"]}

    measured = {
        "value": None if p_el is None else round(p_el, 4),
        "unit": "proportion of coded elasmobranch species that are internal live-bearers",
        "n": n_el,
        "extra": {
            "elasmobranch_viviparous": k_el,
            "elasmobranch_proportion_viviparous": None if p_el is None else round(p_el, 4),
            "elasmobranch_mode_counts": counts("elasmobranchii"),
            "actinopterygii_n": n_act,
            "actinopterygii_oviparous": k_act,
            "actinopterygii_proportion_oviparous": None if p_act is None else round(p_act, 4),
            "actinopterygii_mode_counts": counts("actinopterygii"),
            "holocephali_mode_counts": {m: int((holo["mode"] == m).sum()) for m in ["viviparous", "oviparous", "mixed"]} if len(holo) else {},
            "lophius_n_with_mode": int(len(lophius)),
            "lophius_modes": lophius_modes,
            "lophius_all_oviparous": bool(lophius_all_ovi),
            "classes_seen": sorted(c for c in species["class_key"].unique() if c),
        },
    }
    if n_el < 30:
        verdict, reason, conf = "inconclusive", "underpowered", 0.35
    elif (p_el is not None and p_el < 0.70) or (n_act >= 200 and p_act is not None and p_act < 0.80):
        verdict, reason, conf = "refutes", None, 0.85
    elif (
        n_el >= 50 and n_act >= 500 and p_el is not None and p_act is not None
        and p_el >= 0.90 and p_act >= 0.95 and lophius_all_ovi
    ):
        verdict, reason, conf = "supports", None, 0.75
    else:
        verdict, reason, conf = "mixed", None, 0.65

    result["status"] = "complete"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = conf
    result["data_kind"] = "none" if reason in {"data-unavailable"} else "biological"
    result["measured"] = measured
    result["method"] = (
        "Joined FishBase v26.06 species to families for class and to reproduc for RepGuild1 and RepGuild2. "
        "Internal live-bearing is a guild string with internal and bear, or vivip. Other non-empty guilds are oviparous. "
        "Species proportions were compared with the pre-registered thresholds. Holocephali were not in the elasmobranch denominator."
    )
    result["datasets"] = [{
        "id": "fishbase-v26.06-species-families-reproduc",
        "name": "FishBase snapshot v26.06 (species, families, reproduc), via the rfishbase parquet mirror",
        "landing_url": "https://www.fishbase.se/",
        "doi": None,
        "version": "v26.06",
        "license": "CC BY-NC",
        "files": file_infos,
        "role": "class membership and reproductive guild for elasmobranchs, actinopterygians and Lophius",
    }]
    result["results_summary"] = [
        f"Elasmobranchs with a mode: {k_el}/{n_el} internal live-bearing (proportion {measured['extra']['elasmobranch_proportion_viviparous']}).",
        f"Actinopterygians with a mode: {k_act}/{n_act} oviparous (proportion {measured['extra']['actinopterygii_proportion_oviparous']}).",
        f"Lophius species with a mode: {int(len(lophius))}, modes {lophius_modes}.",
    ]
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, measured["extra"]["elasmobranch_proportion_viviparous"], measured["extra"]["actinopterygii_proportion_oviparous"])


if __name__ == "__main__":
    main()
