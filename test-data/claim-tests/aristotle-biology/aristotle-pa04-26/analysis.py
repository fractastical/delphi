#!/usr/bin/env python3
"""aristotle-pa04-26: milk and mammae only in internally viviparous animals.

A positive weaning age or weaning weight in a bird, reptile or monotreme
refutes the universal. Blank cells do not support it.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
MD5_EXPECTED = "10e7c14395d95ed7f53258f96fadb4f7"
UA = "delphisci-claim-test/aristotle-biology"


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


def positive(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").gt(0)


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    meta = fetch(URL, DATA / "Amniote_Database_Aug_2015.csv")
    df = pd.read_csv(DATA / "Amniote_Database_Aug_2015.csv", low_memory=False, na_values=["-999"])
    weaning = positive(df["weaning_d"]) | positive(df["weaning_weight_g"])
    egg = positive(df["egg_mass_g"]) | positive(df["incubation_d"]) if "egg_mass_g" in df.columns else positive(df.get("incubation_d", 0))
    oviparous = df["class"].isin(["Aves", "Reptilia"]) | (df["order"] == "Monotremata")
    hits = df.loc[oviparous & weaning, ["class", "order", "family", "genus", "species", "weaning_d", "weaning_weight_g", "egg_mass_g", "incubation_d"]].copy()
    monos = df.loc[df["order"] == "Monotremata", ["class", "order", "family", "genus", "species", "weaning_d", "weaning_weight_g", "egg_mass_g", "incubation_d"]].copy()
    other_mammals = (df["class"] == "Mammalia") & (df["order"] != "Monotremata")
    n_other = int(other_mammals.sum())
    n_other_wean = int((other_mammals & positive(df["weaning_d"])).sum())
    n_hits = int(len(hits))
    n_mono = int(len(monos))

    if n_hits >= 1:
        verdict, reason, conf = "refutes", None, 0.8
    elif n_mono == 0:
        verdict, reason, conf = "inconclusive", "underpowered", 0.35
    else:
        verdict, reason, conf = "inconclusive", "other", 0.4

    measured = {
        "value": n_hits,
        "unit": "bird, reptile or monotreme species with weaning_d > 0 or weaning_weight_g > 0",
        "n": int(oviparous.sum()),
        "uncertainty": None,
        "extra": {
            "n_monotremata": n_mono,
            "monotremata": monos.to_dict(orient="records"),
            "counterexamples": hits.to_dict(orient="records"),
            "other_mammals": n_other,
            "other_mammals_with_weaning_d": n_other_wean,
            "fraction_other_mammals_with_weaning_d": (n_other_wean / n_other) if n_other else None,
            "oviparous_with_egg_mass_or_incubation": int((oviparous & egg).sum()),
            "md5_matches_archive_page": meta["md5"] == MD5_EXPECTED,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(clean(measured), indent=2) + "\n")
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if n_hits or n_mono or n_other else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["method"] = (
        "Read the Amniote Life-History Database with -999 as missing. "
        "Counted species in Aves, Reptilia or order Monotremata with a positive weaning age or weaning weight. "
        "One such species refutes the universal. None leaves the claim inconclusive, because a blank cell is not evidence that milk is absent."
    )
    result["measured"] = clean(measured)
    result["results_summary"] = [
        f"Oviparous rows (birds, reptiles, monotremes): {int(oviparous.sum())}. Counterexamples with weaning: {n_hits}.",
        f"Monotremata rows: {n_mono}. Other mammals with weaning_d > 0: {n_other_wean} of {n_other}.",
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + ".",
    ]
    result["datasets"] = [{
        "id": "amniote-life-history-database-2015",
        "name": "Amniote Life-History Database (Myhrvold et al. 2015)",
        "landing_url": "https://esapubs.org/archive/ecol/E096/269/",
        "doi": "10.1890/15-0846.1",
        "version": "Aug 2015",
        "license": "CC0",
        "files": [{k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
        "role": "weaning age and weaning weight by class and order",
    }]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n_hits": n_hits, "n_mono": n_mono}, indent=2))


if __name__ == "__main__":
    main()
