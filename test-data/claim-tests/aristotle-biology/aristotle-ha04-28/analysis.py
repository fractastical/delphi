#!/usr/bin/env python3
"""Sex and offspring of the European eel (aristotle-ha04-28).

Blank FishBase fields are missing data, not evidence that the eel has no sex
and no eggs. One positive record of separate sexes, eggs, fecundity or larvae
for Anguilla anguilla refutes the claim.

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
UA = {"User-Agent": "delphisci-claim-test/1.0 (aristotle-ha04-28)"}
FB = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
TABLES = (
    "species.parquet",
    "reproduc.parquet",
    "eggs.parquet",
    "larvae.parquet",
    "larvaepresence.parquet",
    "fecundity.parquet",
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
    }


def find_col(columns, pattern: str, forbid: str | None = None):
    for name in columns:
        low = str(name).lower()
        if re.search(pattern, low) and not (forbid and re.search(forbid, low)):
            return name
    return None


def blank(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "null", "na"}


def obis_larvae() -> dict:
    """Complete count only. A partial page is not evidence."""
    out = {"used": False, "reason": None}
    facet_urls = [
        "https://api.obis.org/v3/occurrence/facet?scientificname=Anguilla%20anguilla&facet=lifeStage",
        "https://api.obis.org/v3/facet?scientificname=Anguilla%20anguilla&facet=lifeStage",
    ]
    for url in facet_urls:
        try:
            response = requests.get(url, headers=UA, timeout=60)
        except requests.RequestException as exc:
            out["reason"] = f"{type(exc).__name__}: {exc}"
            continue
        out["facet_status"] = response.status_code
        out["facet_url"] = url
        if response.status_code != 200:
            continue
        try:
            payload = response.json()
        except ValueError:
            out["reason"] = "facet response was not JSON"
            continue
        out["facet"] = payload if isinstance(payload, dict) else {"raw_type": type(payload).__name__}
        # Accept only an explicit total of larval records if the payload exposes one.
        text = json.dumps(payload).lower()
        if "larva" in text and any(key in text for key in ("count", "total", "value")):
            out["used"] = False
            out["reason"] = (
                "A facet payload mentioned larvae but no pre-registered parser was fixed "
                "for an unknown JSON shape, so the count is not used."
            )
            out["payload_excerpt"] = text[:500]
            return out
        # A 200 that is not a larval total is not a count. Try the next URL.
    # Total occurrences, unfiltered by life stage, is not an offspring record.
    try:
        response = requests.get(
            "https://api.obis.org/v3/occurrence?scientificname=Anguilla%20anguilla&size=0",
            headers=UA,
            timeout=60,
        )
        out["total_status"] = response.status_code
        if response.status_code == 200:
            payload = response.json()
            total = payload.get("total") if isinstance(payload, dict) else None
            out["anguilla_anguilla_occurrence_total_unfiltered"] = total
            out["reason"] = (
                "OBIS returned an unfiltered occurrence total. lifeStage is not a documented "
                "query filter and no facet total was usable, so OBIS does not enter the verdict."
            )
    except requests.RequestException as exc:
        out["reason"] = f"OBIS request failed: {type(exc).__name__}: {exc}"
    return out


def positive_number(series: pd.Series) -> int:
    numeric = pd.to_numeric(series, errors="coerce")
    return int((numeric > 0).sum())


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    deviations = []
    files = {}
    frames = {}
    for name in TABLES:
        files[name] = fetch(FB + name, DATA / name)
        frames[name] = pd.read_parquet(DATA / name)

    species = frames["species.parquet"]
    spec_col = find_col(species.columns, r"speccode")
    genus_col = find_col(species.columns, r"^genus$") or find_col(species.columns, r"genus")
    epithet_col = find_col(species.columns, r"^species$") or find_col(species.columns, r"species", r"speccode|speciesref")
    anguilla = species[
        species[genus_col].astype(str).str.lower().eq("anguilla")
        & ~species[epithet_col].astype(str).str.lower().isin(["sp", "spp", "nan", ""])
    ][[spec_col, genus_col, epithet_col]].drop_duplicates()
    target = anguilla[anguilla[epithet_col].astype(str).str.lower().eq("anguilla")]
    if target.empty:
        record = {
            "species_found": False,
            "sex_positive": False,
            "offspring_positive": False,
            "explicit_negative": False,
        }
    else:
        code = target.iloc[0][spec_col]
        record = species_record(frames, code, deviations)
        record["species_found"] = True
        record["spec_code"] = int(code) if not isinstance(code, str) else code

    genus_rows = []
    for _, row in anguilla.iterrows():
        item = species_record(frames, row[spec_col], [])
        item["binomial"] = f"{row[genus_col]} {row[epithet_col]}"
        genus_rows.append(item)

    obis = obis_larvae()
    if not obis.get("used"):
        deviations.append(
            "OBIS is not used. A facet URL can return HTTP 200 JSON that is not a larval total; "
            "the first run left reason null in that case. The script now records why no explicit "
            "larval count was accepted. An unfiltered occurrence total is still not offspring. "
            "FishBase sex and offspring counts are unchanged."
        )
    sex_positive = bool(record.get("sex_positive"))
    offspring_positive = bool(record.get("offspring_positive"))
    if record.get("species_found") and (sex_positive or offspring_positive):
        verdict, reason = "refutes", None
        if sex_positive and offspring_positive:
            confidence = 0.85
        else:
            confidence = 0.7
    elif record.get("explicit_negative"):
        verdict, reason = "supports", None
        confidence = 0.4
    else:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.35

    measured = {
        "value": int(sex_positive) + int(offspring_positive),
        "unit": "positive arms (sex, offspring) for Anguilla anguilla",
        "n": 1 if record.get("species_found") else 0,
        "uncertainty": None,
        "extra": {
            "anguilla_anguilla": record,
            "anguilla_genus": genus_rows,
            "obis": {key: value for key, value in obis.items() if key != "facet"},
        },
    }
    summary = [
        f"Anguilla anguilla found={record.get('species_found')}; sex_positive={sex_positive}; offspring_positive={offspring_positive}.",
        f"Mode={record.get('mode')!r}; eggs={record.get('n_egg_rows')}; larvae={record.get('n_larva_rows')}; "
        f"larvaepresence={record.get('larvae_present')!r}; positive_fecundity_rows={record.get('n_positive_fecundity')}.",
        f"Other Anguilla species in the species table: {len(genus_rows)}.",
        f"OBIS used={obis.get('used')}. {obis.get('reason')}",
        f"Verdict {verdict}.",
    ]
    (DERIVED / "measured.json").write_text(
        json.dumps({"measured": measured, "summary": summary, "deviations": deviations}, indent=2) + "\n"
    )
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if record.get("species_found") else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["method"] = (
        "Joined Anguilla anguilla to its FishBase SpecCode and counted reproduc Mode, eggs rows, "
        "larvae rows, larvaepresence and positive fecundity. Any of the manual's sex-system codes, or any "
        "offspring row, refutes the claim. OBIS was queried for a complete larval count and used only if "
        "that count was explicit; an unfiltered occurrence total was stored and not treated as offspring."
    )
    result["measured"] = measured
    result["results_summary"] = summary
    if deviations:
        result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "fishbase-v25.04-reproduc-eggs-larvae-fecundity",
            "name": "FishBase v25.04 species, reproduc, eggs, larvae, larvaepresence and fecundity",
            "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
            "doi": None,
            "version": "v25.04",
            "license": "CC BY-NC 4.0",
            "files": [{"name": name, **meta} for name, meta in files.items()],
            "role": "sex system, eggs, larvae and fecundity of Anguilla",
        },
        {
            "id": "obis-anguilla-anguilla-lifestage",
            "name": "OBIS occurrence API for Anguilla anguilla",
            "landing_url": "https://obis.org/",
            "doi": None,
            "version": "api-v3",
            "license": "occurrence records retain their source licences; the API is public",
            "files": [],
            "role": "attempted complete larval count; not used unless a filtered total was returned",
            "note": obis.get("reason"),
        },
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "summary": summary}, indent=2))


def species_record(frames: dict, code, deviations: list) -> dict:
    reproduc = frames["reproduc.parquet"]
    spec_r = find_col(reproduc.columns, r"speccode")
    mode_col = find_col(reproduc.columns, r"^mode$") or find_col(reproduc.columns, r"repromode|reproductionmode|^mode")
    rows = reproduc[reproduc[spec_r] == code]
    modes = []
    if mode_col:
        modes = [str(value).strip() for value in rows[mode_col] if not blank(value)]
    else:
        deviations.append(f"reproduc columns had no Mode field: {list(reproduc.columns)}")
    mode_text = " | ".join(modes)
    sex_system = re.compile(r"dioec|protandr|protogyn|hermaphrod|parthenogen", re.I)
    sex_positive = any(sex_system.search(mode) for mode in modes) or any(
        re.search(r"\bmales?\b", mode, re.I) and re.search(r"\bfemales?\b", mode, re.I) for mode in modes
    )

    def n_rows(table: str) -> int:
        frame = frames[table]
        column = find_col(frame.columns, r"speccode")
        if column is None:
            return 0
        return int((frame[column] == code).sum())

    n_eggs = n_rows("eggs.parquet")
    n_larvae = n_rows("larvae.parquet")
    presence = frames["larvaepresence.parquet"]
    presence_col_spec = find_col(presence.columns, r"speccode")
    presence_rows = presence[presence[presence_col_spec] == code] if presence_col_spec else presence.iloc[0:0]
    larvae_present = False
    presence_values = []
    for name in presence_rows.columns:
        if re.search(r"present|larva", str(name), re.I):
            for value in presence_rows[name]:
                if blank(value):
                    continue
                presence_values.append(f"{name}={value}")
                if re.search(r"\b(1|yes|present|true)\b", str(value), re.I):
                    larvae_present = True
    # Any non-blank larvaepresence row that is not an explicit negative counts as presence
    # only when the cell says present. An explicit "no" is an explicit negative.
    explicit_larvae_absent = False
    if presence_values and not larvae_present:
        explicit_larvae_absent = all(re.search(r"\b(0|no|absent|false)\b", item, re.I) for item in presence_values)

    fecundity = frames["fecundity.parquet"]
    fec_spec = find_col(fecundity.columns, r"speccode")
    fec_rows = fecundity[fecundity[fec_spec] == code] if fec_spec else fecundity.iloc[0:0]
    n_positive = 0
    sexes = set()
    sex_col = find_col(fecundity.columns, r"^sex$") or find_col(fecundity.columns, r"sex", r"species")
    for name in fecundity.columns:
        if re.search(r"fecund", str(name), re.I):
            n_positive += positive_number(fec_rows[name]) if len(fec_rows) else 0
    if sex_col and len(fec_rows):
        for value in fec_rows[sex_col]:
            if blank(value):
                continue
            text = str(value).strip().lower()
            if text in {"m", "male", "males"}:
                sexes.add("male")
            elif text in {"f", "female", "females"}:
                sexes.add("female")
    if {"male", "female"} <= sexes:
        sex_positive = True

    offspring_positive = n_eggs > 0 or n_larvae > 0 or larvae_present or n_positive > 0
    denies_sex = any(re.search(r"no sex|sexless|neither male", mode, re.I) for mode in modes)
    explicit_negative = (
        denies_sex
        and not sex_positive
        and n_eggs == 0
        and n_larvae == 0
        and n_positive == 0
        and not larvae_present
    )
    return {
        "mode": mode_text or None,
        "sex_positive": sex_positive,
        "n_egg_rows": n_eggs,
        "n_larva_rows": n_larvae,
        "larvae_present": larvae_present,
        "larvaepresence_values": presence_values,
        "n_positive_fecundity": n_positive,
        "fecundity_sexes": sorted(sexes),
        "offspring_positive": offspring_positive,
        "explicit_negative": explicit_negative,
    }


if __name__ == "__main__":
    main()
