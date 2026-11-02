#!/usr/bin/env python3
"""aristotle-ha06-19: dolphins and porpoises have milk and suckle their young.

The decision rule is the one committed in result.json. Re-fetches the three
trait compilations. Only genus Delphinus and genus Phocoena are scored.

    python3 analysis.py
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/aristotle-ha06-19"
GENERA = ("Delphinus", "Phocoena")

SOURCES = [
    {
        "id": "anage-hagr-dataset-zip",
        "name": "AnAge: The Animal Ageing and Longevity Database (latest stable build)",
        "landing_url": "https://genomics.senescence.info/species/index.html",
        "doi": "10.1093/nar/gkx1042",
        "version": "stable build",
        "license": "Freely available under the HAGR license, as stated on https://genomics.senescence.info/species/index.html",
        "download_url": "https://genomics.senescence.info/species/dataset.zip",
        "role": "weaning age in days for Delphinus and Phocoena",
    },
    {
        "id": "pantheria-1-0-wr05-aug2008",
        "name": "PanTHERIA 1.0 (Wilson and Reeder 2005 taxonomy)",
        "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
        "doi": "10.1890/08-1494.1",
        "version": "PanTHERIA_1-0_WR05_Aug2008",
        "license": "Published with Ecological Archives E090-184",
        "download_url": "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt",
        "role": "weaning age (25-1_WeaningAge_d) and teat number (24-1_TeatNumber)",
    },
    {
        "id": "amniote-life-history-database-aug-2015",
        "name": "Amniote Life-History Database (Myhrvold et al. 2015), median table",
        "landing_url": "https://esapubs.org/archive/ecol/E096/269/",
        "doi": "10.1890/15-0846.1",
        "version": "Aug 2015",
        "license": "Published with Ecological Archives E096-269",
        "download_url": "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv",
        "role": "weaning age in days (weaning_d); this table has no teat column",
    },
]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows_from_text(text: str, delimiter: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def header(headers: list[str], pred) -> str | None:
    for name in headers:
        if name and pred(name.strip()):
            return name
    return None


def number(text: str | None) -> float | None:
    if text is None:
        return None
    s = text.strip().replace(",", "")
    if s == "" or s.lower() in {"na", "nan", "null", "-999", "-999.0"}:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def genus_species(row: dict[str, str], genus_key: str | None, species_key: str | None, binomial_key: str | None) -> tuple[str, str] | None:
    if binomial_key:
        parts = (row.get(binomial_key) or "").strip().split()
        if len(parts) >= 2 and parts[0] in GENERA:
            return parts[0], parts[1]
    if genus_key and species_key:
        genus = (row.get(genus_key) or "").strip()
        epithet = (row.get(species_key) or "").strip().split()[:1]
        if genus in GENERA and epithet:
            return genus, epithet[0]
    return None


def collect(rows: list[dict[str, str]], genus_key, species_key, binomial_key, fields: dict[str, str]) -> list[dict]:
    out = []
    for row in rows:
        named = genus_species(row, genus_key, species_key, binomial_key)
        if not named:
            continue
        genus, epithet = named
        record = {"genus": genus, "species": f"{genus} {epithet}"}
        for label, column in fields.items():
            record[label] = number(row.get(column))
        out.append(record)
    return out


def load_anage(raw: bytes) -> tuple[str, list[dict]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        member = next(n for n in zf.namelist() if n.endswith("anage_data.txt") or n.endswith(".txt"))
        rows = rows_from_text(zf.read(member).decode("utf-8-sig"), "\t")
    headers = list(rows[0].keys()) if rows else []
    weaning = header(headers, lambda h: "weaning" in h.lower() and "day" in h.lower() and "weight" not in h.lower())
    if weaning is None:
        raise RuntimeError(f"AnAge weaning column missing: {headers}")
    genus = header(headers, lambda h: h.lower() == "genus")
    species = header(headers, lambda h: h.lower() == "species")
    return member, collect(rows, genus, species, None, {"weaning_d": weaning})


def load_pantheria(raw: bytes) -> list[dict]:
    rows = rows_from_text(raw.decode("utf-8-sig"), "\t")
    headers = list(rows[0].keys()) if rows else []
    weaning = header(headers, lambda h: h.replace(" ", "") == "25-1_WeaningAge_d")
    teats = header(headers, lambda h: h.replace(" ", "") == "24-1_TeatNumber")
    if weaning is None or teats is None:
        raise RuntimeError("PanTHERIA weaning or teat column missing")
    genus = header(headers, lambda h: h.replace(" ", "") == "MSW05_Genus")
    species = header(headers, lambda h: h.replace(" ", "") == "MSW05_Species")
    binomial = header(headers, lambda h: h.replace(" ", "") == "MSW05_Binomial")
    return collect(rows, genus, species, binomial, {"weaning_d": weaning, "teat_number": teats})


def load_amniote(raw: bytes) -> list[dict]:
    rows = rows_from_text(raw.decode("utf-8-sig"), ",")
    headers = list(rows[0].keys()) if rows else []
    weaning = header(headers, lambda h: h.strip() == "weaning_d")
    if weaning is None:
        raise RuntimeError("Amniote weaning_d column missing")
    genus = header(headers, lambda h: h.strip().lower() == "genus")
    species = header(headers, lambda h: h.strip().lower() == "species")
    return collect(rows, genus, species, None, {"weaning_d": weaning})


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = now_utc()
    parsed = {}
    file_info = {}
    for src in SOURCES:
        raw = fetch(src["download_url"])
        suffix = ".zip" if src["download_url"].endswith(".zip") else ".csv" if src["download_url"].endswith(".csv") else ".txt"
        path = DATA / f"{src['id']}{suffix}"
        path.write_bytes(raw)
        info = {
            "download_url": src["download_url"],
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": sha256(raw),
        }
        if src["id"].startswith("anage"):
            member, rows = load_anage(raw)
            info["zip_member"] = member
        elif src["id"].startswith("pantheria"):
            rows = load_pantheria(raw)
        else:
            rows = load_amniote(raw)
        file_info[src["id"]] = info
        parsed[src["id"]] = rows

    per_genus = {genus: {"weaning": [], "teats": [], "zeros": []} for genus in GENERA}
    for src in SOURCES:
        for row in parsed[src["id"]]:
            for label, key in (("weaning", "weaning_d"), ("teats", "teat_number")):
                if key not in row or row[key] is None:
                    continue
                entry = {"dataset": src["id"], "species": row["species"], "value": row[key]}
                if row[key] == 0:
                    per_genus[row["genus"]]["zeros"].append({**entry, "quantity": label})
                else:
                    per_genus[row["genus"]][label].append(entry)

    def ok(genus: str) -> bool:
        g = per_genus[genus]
        return bool(g["weaning"]) and bool(g["teats"]) and not g["zeros"]

    zeros = [genus for genus, g in per_genus.items() if g["zeros"]]
    if not any(parsed.values()) and not file_info:
        verdict, reason = "inconclusive", "data-unavailable"
    elif zeros:
        verdict, reason = "refutes", None
    elif all(ok(genus) for genus in GENERA):
        verdict, reason = "supports", None
    elif any(ok(genus) for genus in GENERA):
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "underpowered"

    n_values = sum(len(g["weaning"]) + len(g["teats"]) + len(g["zeros"]) for g in per_genus.values())
    weaning_values = [entry["value"] for g in per_genus.values() for entry in g["weaning"]]
    weaning_datasets = {e["dataset"] for g in per_genus.values() for e in g["weaning"]}
    both_genera_weaned = all(per_genus[g]["weaning"] for g in GENERA)
    no_teats = all(not per_genus[g]["teats"] for g in GENERA)
    if verdict == "supports" and len(weaning_datasets) >= 2:
        confidence = 0.75
    elif verdict == "supports":
        confidence = 0.6
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "mixed":
        confidence = 0.5
    elif verdict == "inconclusive" and both_genera_weaned and no_teats and not zeros:
        # The gap is the missing teat column, not a thin weaning sample.
        confidence = 0.7
    else:
        confidence = 0.4

    measured = {
        "value": min(weaning_values) if weaning_values else None,
        "unit": "days; shortest positive weaning age recorded for Delphinus or Phocoena",
        "n": n_values,
        "uncertainty": "species-level published figures; no count of nursing bouts",
        "extra": {"per_genus": per_genus},
    }
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n")

    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if n_values or any(parsed[s["id"]] for s in SOURCES) else "none"
    # data were the trait tables even if the genera are absent: biological compilations were read.
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["measured"] = measured
    result["datasets"] = []
    for src in SOURCES:
        info = file_info[src["id"]]
        result["datasets"].append({
            "id": src["id"],
            "name": src["name"],
            "landing_url": src["landing_url"],
            "doi": src["doi"],
            "version": src["version"],
            "license": src["license"],
            "files": [{k: v for k, v in info.items() if k != "zip_member"} | ({"zip_member": info["zip_member"]} if "zip_member" in info else {})],
            "role": src["role"],
        })
    result["method"] = (
        "Re-fetched the three pre-registered compilations and kept rows in genus Delphinus or Phocoena. "
        "Read AnAge's weaning-in-days column, PanTHERIA weaning age and teat number, and Amniote weaning_d. "
        "Values below zero are the PanTHERIA missing code and are ignored. A genus passes only when it has a "
        "positive weaning age, a teat number of at least one, and no recorded zero."
    )
    lines = []
    if both_genera_weaned and no_teats and not zeros:
        lines.append(
            "Both genera have positive weaning ages in every compilation that records them, so a suckling period is in the data. "
            "No compilation records a teat number for either genus (PanTHERIA stores the missing code), so the milk clause is unmeasured and the verdict stays inconclusive."
        )
    for genus in GENERA:
        g = per_genus[genus]
        lines.append(
            f"{genus}: weaning records={len(g['weaning'])}, teat records={len(g['teats'])}, zeros={len(g['zeros'])}"
        )
    result["results_summary"] = lines
    caveats = list(result.get("caveats") or [])
    for caveat in [
        "Teat number is present in PanTHERIA only. AnAge and the Amniote table can corroborate weaning and cannot corroborate teats.",
    ]:
        if caveat not in caveats:
            caveats.append(caveat)
    result["caveats"] = caveats
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "per_genus": per_genus}, indent=2))


if __name__ == "__main__":
    main()
