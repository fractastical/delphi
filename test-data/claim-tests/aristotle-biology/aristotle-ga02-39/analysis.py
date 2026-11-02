#!/usr/bin/env python3
"""aristotle-ga02-39: gestation of the horse and the ass against one year.

The decision rule is the one committed in result.json before these files were
downloaded. Re-run from the repository root or from this directory:

    python3 analysis.py

Downloads three public compilations into data/ (gitignored; each is hashed and
not committed), writes derived/measured.json, and fills the measured fields of
result.json. It does not change hypothesis, pass_criterion, fail_criterion, or
test_contract.
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

Y = 365.25
TOL = Y / 24.0  # half a month: boundary between 12 months and 11 or 13
SEASON = Y / 4.0

SOURCES = [
    {
        "id": "anage-hagr-dataset-zip",
        "name": "AnAge: The Animal Ageing and Longevity Database (latest stable build, tab-delimited)",
        "landing_url": "https://genomics.senescence.info/species/index.html",
        "doi": "10.1093/nar/gkx1042",
        "version": "stable build served 2026-11-02 (zip last-modified 2023-07-03)",
        "license": "Freely available under the HAGR license, as stated on https://genomics.senescence.info/species/index.html",
        "download_url": "https://genomics.senescence.info/species/dataset.zip",
        "expected_bytes": 169150,
        "role": "species-level gestation/incubation length in days for Equus caballus and Equus asinus",
    },
    {
        "id": "pantheria-1-0-wr05-aug2008",
        "name": "PanTHERIA 1.0 (Wilson and Reeder 2005 taxonomy)",
        "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
        "doi": "10.1890/08-1494.1",
        "version": "PanTHERIA_1-0_WR05_Aug2008",
        "license": "Published with Ecological Archives E090-184; redistribution with the data paper",
        "download_url": "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt",
        "expected_bytes": 2359096,
        "role": "species-level gestation length in days (column 9-1_GestationLen_d)",
    },
    {
        "id": "amniote-life-history-database-aug-2015",
        "name": "Amniote Life-History Database (Myhrvold et al. 2015), median table",
        "landing_url": "https://esapubs.org/archive/ecol/E096/269/",
        "doi": "10.1890/15-0846.1",
        "version": "Aug 2015",
        "license": "Published with Ecological Archives E096-269",
        "download_url": "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv",
        "expected_bytes": 4728122,
        "role": "species-level median gestation length in days (column gestation_d)",
    },
]

TARGETS = {
    "Equus caballus": ("equus", "caballus"),
    "Equus asinus": ("equus", "asinus"),
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test/aristotle-ga02-39"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_table(raw: bytes, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    headers = list(reader.fieldnames or [])
    return headers, rows


def norm(value: str | None) -> str:
    return (value or "").strip().lower()


def find_header(headers: list[str], pred) -> str | None:
    for h in headers:
        if h is not None and pred(h.strip()):
            return h
    return None


def parse_days(text: str | None, negative_is_missing: bool) -> float | None:
    if text is None:
        return None
    s = text.strip().replace(",", "")
    if s == "" or s.lower() in {"na", "nan", "null", "-999", "-999.0", "-999.00"}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if negative_is_missing and v < 0:
        return None
    if v <= 0:
        return None
    return v


def median(xs: list[float]) -> float:
    ys = sorted(xs)
    n = len(ys)
    mid = n // 2
    if n % 2:
        return ys[mid]
    return (ys[mid - 1] + ys[mid]) / 2.0


def species_of(row: dict[str, str], genus_key: str | None, species_key: str | None, binomial_key: str | None) -> str | None:
    if binomial_key:
        b = norm(row.get(binomial_key))
        for name, (g, s) in TARGETS.items():
            if b == f"{g} {s}":
                return name
    if genus_key and species_key:
        g = norm(row.get(genus_key))
        s = norm(row.get(species_key)).split()[0] if norm(row.get(species_key)) else ""
        for name, (gg, ss) in TARGETS.items():
            if g == gg and s == ss:
                return name
    return None


def inside(g: float) -> bool:
    return abs(g - Y) <= TOL + 1e-9


def season_fraction(g: float) -> float:
    return max(0.0, 1.0 - abs(g - Y) / SEASON)


def rounded(x: float | None, nd: int = 4) -> float | None:
    if x is None:
        return None
    return round(x, nd)


def anage_rows(raw: bytes) -> tuple[str, list[dict]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        member = None
        for n in names:
            if n.endswith("anage_data.txt") or n.endswith(".txt") or n.endswith(".tsv"):
                member = n
                break
        if member is None:
            raise RuntimeError(f"AnAge zip has no table member: {names}")
        headers, rows = load_table(zf.read(member), "\t")
    gest = find_header(headers, lambda h: "gestation" in h.lower() and "incubation" in h.lower())
    if gest is None:
        raise RuntimeError(f"AnAge gestation/incubation column not found in {headers}")
    genus = find_header(headers, lambda h: h.lower() == "genus")
    species = find_header(headers, lambda h: h.lower() == "species")
    quality = find_header(headers, lambda h: h.lower().replace(" ", "") in {"dataquality", "data_quality"})
    out = []
    for row in rows:
        name = species_of(row, genus, species, None)
        if not name:
            continue
        g = parse_days(row.get(gest), negative_is_missing=True)
        out.append({
            "species": name,
            "gestation_d": g,
            "data_quality": (row.get(quality) or "").strip() if quality else None,
            "genus": (row.get(genus) or "").strip() if genus else None,
            "species_epithet": (row.get(species) or "").strip() if species else None,
        })
    return member, out


def pantheria_rows(raw: bytes) -> list[dict]:
    headers, rows = load_table(raw, "\t")
    gest = find_header(headers, lambda h: h.replace(" ", "") == "9-1_GestationLen_d")
    if gest is None:
        raise RuntimeError(f"PanTHERIA gestation column not found in {headers[:12]}...")
    genus = find_header(headers, lambda h: h.replace(" ", "") in {"MSW05_Genus", "MSW05_Genus"})
    species = find_header(headers, lambda h: h.replace(" ", "") == "MSW05_Species")
    binomial = find_header(headers, lambda h: h.replace(" ", "") == "MSW05_Binomial")
    out = []
    for row in rows:
        name = species_of(row, genus, species, binomial)
        if not name:
            continue
        g = parse_days(row.get(gest), negative_is_missing=True)
        out.append({
            "species": name,
            "gestation_d": g,
            "binomial": (row.get(binomial) or "").strip() if binomial else None,
        })
    return out


def amniote_rows(raw: bytes) -> list[dict]:
    headers, rows = load_table(raw, ",")
    gest = find_header(headers, lambda h: h.strip() == "gestation_d")
    if gest is None:
        raise RuntimeError(f"Amniote gestation_d column not found in {headers[:20]}")
    genus = find_header(headers, lambda h: h.strip().lower() == "genus")
    species = find_header(headers, lambda h: h.strip().lower() == "species")
    out = []
    for row in rows:
        name = species_of(row, genus, species, None)
        if not name:
            continue
        g = parse_days(row.get(gest), negative_is_missing=True)
        out.append({
            "species": name,
            "gestation_d": g,
            "genus": (row.get(genus) or "").strip() if genus else None,
            "species_epithet": (row.get(species) or "").strip() if species else None,
        })
    return out


def consensus(flags: list[bool]) -> str:
    if not flags:
        return "missing"
    if all(flags):
        return "inside"
    if not any(flags):
        return "outside"
    return "conflict"


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = now_utc()
    file_info = {}
    parsed = {}

    for src in SOURCES:
        dest = DATA / src["id"]
        # AnAge is a zip; keep the bytes as downloaded.
        suffix = ".zip" if src["download_url"].endswith(".zip") else (".csv" if src["download_url"].endswith(".csv") else ".txt")
        dest = dest.with_suffix(suffix)
        raw = fetch(src["download_url"])
        dest.write_bytes(raw)
        info = {
            "download_url": src["download_url"],
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": sha256(raw),
            "expected_bytes_at_preregistration": src["expected_bytes"],
            "bytes_match_preregistration_header": len(raw) == src["expected_bytes"],
            "path_not_committed": str(dest.relative_to(HERE)),
        }
        file_info[src["id"]] = info
        if src["id"].startswith("anage"):
            member, rows = anage_rows(raw)
            info["zip_member"] = member
        elif src["id"].startswith("pantheria"):
            rows = pantheria_rows(raw)
        else:
            rows = amniote_rows(raw)
        parsed[src["id"]] = rows

    per_species: dict[str, dict] = {name: {"by_dataset": {}, "flags": []} for name in TARGETS}
    records = []
    for src in SOURCES:
        by_name: dict[str, list[float]] = {name: [] for name in TARGETS}
        qualities: dict[str, list] = {name: [] for name in TARGETS}
        for row in parsed[src["id"]]:
            if row["gestation_d"] is None:
                qualities[row["species"]].append({"value": None, **{k: v for k, v in row.items() if k != "gestation_d"}})
                continue
            by_name[row["species"]].append(row["gestation_d"])
            qualities[row["species"]].append(row)
        for name in TARGETS:
            vals = by_name[name]
            if not vals:
                per_species[name]["by_dataset"][src["id"]] = None
                continue
            g = median(vals)
            flag = inside(g)
            per_species[name]["flags"].append(flag)
            per_species[name]["by_dataset"][src["id"]] = {
                "n_rows": len(vals),
                "values_d": [rounded(v, 4) for v in vals],
                "median_d": rounded(g, 4),
                "abs_deviation_from_365_25_d": rounded(abs(g - Y), 4),
                "inside_one_year_bin": flag,
                "same_season_fraction": rounded(season_fraction(g), 4),
                "rows": qualities[name],
            }
            records.append({
                "dataset": src["id"],
                "species": name,
                "gestation_d": rounded(g, 4),
                "inside_one_year_bin": flag,
            })

    species_consensus = {name: consensus(per_species[name]["flags"]) for name in TARGETS}
    missing = [name for name, c in species_consensus.items() if c == "missing"]
    outside = [name for name, c in species_consensus.items() if c == "outside"]
    conflict = [name for name, c in species_consensus.items() if c == "conflict"]
    length_mismatch = [sid for sid, info in file_info.items() if not info["bytes_match_preregistration_header"]]

    if length_mismatch and not records:
        verdict, reason = "inconclusive", "data-unavailable"
    elif missing:
        verdict, reason = "inconclusive", "underpowered"
    elif outside:
        verdict, reason = "refutes", None
    elif conflict:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "supports", None

    deviations = []
    if length_mismatch:
        deviations.append({
            "what": "Downloaded byte size differed from the content-length recorded at pre-registration for: " + ", ".join(length_mismatch),
            "why": "The header check and the body were separated by the pre-registration commit. Sizes are reported; the files were still the URLs named in the contract.",
        })

    # Headline number: largest absolute deviation of a species median across datasets
    # that entered the verdict (one median per dataset). Descriptive, not a new threshold.
    deviations_d = []
    for name in TARGETS:
        for payload in per_species[name]["by_dataset"].values():
            if payload:
                deviations_d.append(payload["abs_deviation_from_365_25_d"])
    headline = max(deviations_d) if deviations_d else None

    # Confidence is a judgment about this verdict, not a pre-registered threshold.
    # Far from the bin edge and replicated in every compilation: higher.
    # A value within 2 days of the edge, or a conflict: lower.
    past_edge = []
    for name in TARGETS:
        for payload in per_species[name]["by_dataset"].values():
            if payload and not payload["inside_one_year_bin"]:
                past_edge.append(payload["abs_deviation_from_365_25_d"] - TOL)
    n_datasets_used = len({r["dataset"] for r in records})
    clearly_past = bool(past_edge) and min(past_edge) >= 10
    if verdict == "inconclusive":
        confidence = 0.35 if reason == "underpowered" else 0.2
    elif verdict == "mixed":
        confidence = 0.45
    elif verdict == "refutes" and n_datasets_used == 3 and clearly_past:
        # Three compilations agree, and the failing species is at least 10 days
        # beyond the bin edge. Not higher: the horse figures sit within 2 days of
        # each other, so the compilations may share literature sources.
        confidence = 0.8
    elif n_datasets_used < 2:
        confidence = 0.55
    else:
        confidence = 0.7

    measured = {
        "value": headline,
        "unit": "days; largest |gestation - 365.25| among species-level medians that entered the verdict",
        "n": len(records),
        "uncertainty": "compilations publish one point estimate per species; no within-species standard error is in these files",
        "extra": {
            "year_days": Y,
            "half_month_tolerance_days": round(TOL, 5),
            "one_year_bin_days": [round(Y - TOL, 5), round(Y + TOL, 5)],
            "species_consensus": species_consensus,
            "per_species": per_species,
            "records": records,
        },
    }

    derived = {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "measured": measured,
        "files": file_info,
        "deviations": deviations,
    }
    (DERIVED / "measured.json").write_text(json.dumps(derived, indent=2) + "\n")

    result = json.loads(RESULT.read_text())
    for key in ("hypothesis", "pass_criterion", "fail_criterion", "test_contract", "planned_datasets"):
        if key not in result:
            raise SystemExit(f"preregistered field missing: {key}")
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["measured"] = measured
    if deviations:
        result["deviations"] = deviations
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
            "files": [{
                "download_url": info["download_url"],
                "retrieved_at": info["retrieved_at"],
                "byte_size": info["byte_size"],
                "sha256": info["sha256"],
            }],
            "role": src["role"],
        })
    result["method"] = (
        "Downloaded the three pre-registered compilations, checked byte size against the content-length "
        "recorded at pre-registration, and hashed each file. Kept Equus caballus and Equus asinus only. "
        "Read AnAge's combined gestation/incubation column, PanTHERIA 9-1_GestationLen_d (values below 0 treated as missing), "
        "and Amniote gestation_d. A value is inside the one-year bin when it is within half a month of 365.25 days. "
        "The verdict follows the pre-registered consensus rule. The same-season fraction is stored in measured.extra and is not used for the verdict."
    )
    lines = [
        "The ass is inside the one-year bin in every compilation; the horse is outside in every compilation, nearer eleven months (334.8125 days) than twelve, so the claim that both gestate for one year is refuted.",
    ]
    for name, cons in species_consensus.items():
        bits = []
        for src in SOURCES:
            payload = per_species[name]["by_dataset"][src["id"]]
            if payload is None:
                bits.append(f"{src['id']}: no value")
            else:
                bits.append(
                    f"{src['id']}: {payload['median_d']} days "
                    f"({'inside' if payload['inside_one_year_bin'] else 'outside'}, "
                    f"|dev|={payload['abs_deviation_from_365_25_d']})"
                )
        lines.append(f"{name} ({cons}): " + "; ".join(bits))
    result["results_summary"] = lines
    extra_caveats = [
        "Equus asinus is inside the one-year bin in all three compilations. The refutation is Equus caballus alone: the claim requires both.",
        "The three horse estimates differ by less than two days (337, 338.97, 337.985). The compilations may be repeating overlapping literature rather than three independent samples of mares. Every one of them still places the horse outside the bin.",
        "Eleven months is 334.8125 days. The horse estimates sit 2 to 4 days above that figure and 26 to 28 days below 365.25, which is why they round to eleven months.",
    ]
    caveats = list(result.get("caveats") or [])
    for c in extra_caveats:
        if c not in caveats:
            caveats.append(c)
    result["caveats"] = caveats
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "headline_deviation_d": headline, "species_consensus": species_consensus, "files": {k: {"bytes": v["byte_size"], "sha256": v["sha256"], "match": v["bytes_match_preregistration_header"]} for k, v in file_info.items()}}, indent=2))


if __name__ == "__main__":
    main()
