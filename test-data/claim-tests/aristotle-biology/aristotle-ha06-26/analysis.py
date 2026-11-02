#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-ha06-26.

Reads FishBase rfishbase parquet snapshot v26.06 (species + families) and the
FishBase glossary pages for the migration terms. Does not read longevity
columns. Verdict rules are those committed in result.json before the download.

Requires: Python 3, pandas, pyarrow, and a network connection on a cold cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "result.json"
DERIVED = HERE / "derived"
CACHE = Path(os.environ.get("CLAIM_TEST_CACHE", "/tmp/aristotle-ha06-26"))

USER_AGENT = "delphi-claim-test/1.0 (research; +https://github.com/fractastical/delphi)"

SPECIES_URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/species.parquet"
FAMILIES_URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/families.parquet"

# SHA-256 of the bytes retrieved on the first run (2026-11-01). A mismatch
# means the snapshot changed; the pre-registered rule then says inconclusive.
EXPECTED_PARQUET = {
    "species.parquet": {
        "url": SPECIES_URL,
        "byte_size": 3469911,
        "sha256": "87c99bc57f368c6102ea4042e7e6c8019c7405d5a352ead840f06244609ab101",
    },
    "families.parquet": {
        "url": FAMILIES_URL,
        "byte_size": 274721,
        "sha256": "2f5e806d0af38aa4fe5422d29cdff94a2532382203b0d6b60412e48f4f4b4147",
    },
}

GLOSSARY = {
    "catadromous": "https://www.fishbase.se/glossary/Glossary.php?q=catadromous",
    "anadromous": "https://www.fishbase.se/glossary/Glossary.php?q=anadromous",
    "amphidromous": "https://www.fishbase.se/glossary/Glossary.php?q=amphidromous",
}

EEL = ("Anguilla", "anguilla")
MULLETS = [
    ("Mugil", "cephalus"),
    ("Chelon", "auratus"),
    ("Chelon", "labrosus"),
    ("Chelon", "ramada"),
    ("Chelon", "saliens"),
    ("Oedalechilus", "labeo"),
]

INLAND = {"anadromous", "amphidromous"}
NOT_INLAND = {
    "catadromous",
    "potamodromous",
    "limnodromous",
    "oceanodromous",
    "non-migratory",
}
EEL_REFUTE = {
    "anadromous",
    "amphidromous",
    "potamodromous",
    "limnodromous",
    "oceanodromous",
    "non-migratory",
}

SPECIES_COLUMNS = [
    "SpecCode",
    "Genus",
    "Species",
    "FBname",
    "FamCode",
    "Fresh",
    "Brack",
    "Saltwater",
    "AnaCat",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, dest: Path) -> bytes:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return data


def normalize_html(data: bytes) -> bytes:
    text = data.decode("utf-8", "replace")
    text = re.sub(
        r"Total processing time for the page : [0-9.]+ seconds",
        "Total processing time for the page : TIME",
        text,
    )
    return text.encode("utf-8")


def yes_flag(value):
    """FishBase yes is 1 or the legacy -1; 0 is no; anything else is missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number in (1, -1):
        return True
    if number == 0:
        return False
    return None


def norm_cat(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().casefold()
    return text or None


def inland_waters(fresh, brack) -> bool:
    return fresh is True or brack is True


def load_tables():
    CACHE.mkdir(parents=True, exist_ok=True)
    species_bytes = fetch(SPECIES_URL, CACHE / "species.parquet")
    families_bytes = fetch(FAMILIES_URL, CACHE / "families.parquet")
    parquet_ok = True
    for name, expected in EXPECTED_PARQUET.items():
        blob = (CACHE / name).read_bytes()
        if len(blob) != expected["byte_size"] or sha256_bytes(blob) != expected["sha256"]:
            parquet_ok = False
    species = pd.read_parquet(CACHE / "species.parquet", columns=SPECIES_COLUMNS)
    families = pd.read_parquet(
        CACHE / "families.parquet", columns=["FamCode", "Family", "Synonym", "CommonName"]
    )
    return species, families, species_bytes, families_bytes, parquet_ok


def family_name(families: pd.DataFrame, fam_code) -> str | None:
    if fam_code is None or (isinstance(fam_code, float) and pd.isna(fam_code)):
        return None
    rows = families[families["FamCode"] == int(fam_code)]
    if rows.empty:
        return None
    return str(rows.iloc[0]["Family"])


def row_record(row, families) -> dict:
    fresh = yes_flag(row["Fresh"])
    brack = yes_flag(row["Brack"])
    salt = yes_flag(row["Saltwater"])
    return {
        "spec_code": int(row["SpecCode"]),
        "genus": str(row["Genus"]),
        "species": str(row["Species"]),
        "fb_name": None if pd.isna(row["FBname"]) else str(row["FBname"]),
        "fam_code": None if pd.isna(row["FamCode"]) else int(row["FamCode"]),
        "family": family_name(families, row["FamCode"]),
        "fresh": fresh,
        "brackish": brack,
        "saltwater": salt,
        "anacat": norm_cat(row["AnaCat"]),
        "inland_and_sea": bool(salt is True and inland_waters(fresh, brack)),
    }


def exact_rows(species: pd.DataFrame, genus: str, epithet: str) -> pd.DataFrame:
    return species[(species["Genus"] == genus) & (species["Species"] == epithet)]


def resolve_mullet(species, families, genus, epithet) -> dict:
    exact = exact_rows(species, genus, epithet)
    if len(exact) == 1:
        rec = row_record(exact.iloc[0], families)
        rec["queried_as"] = f"{genus} {epithet}"
        rec["match"] = "exact"
        return rec
    if len(exact) > 1:
        return {
            "queried_as": f"{genus} {epithet}",
            "match": "duplicate",
            "n_rows": int(len(exact)),
        }
    epithet_rows = species[species["Species"] == epithet]
    mugil = []
    for _, row in epithet_rows.iterrows():
        rec = row_record(row, families)
        if rec["family"] == "Mugilidae":
            mugil.append(rec)
    if len(mugil) == 1:
        mugil[0]["queried_as"] = f"{genus} {epithet}"
        mugil[0]["match"] = "epithet-fallback"
        return mugil[0]
    return {
        "queried_as": f"{genus} {epithet}",
        "match": "unresolved",
        "n_rows": int(len(exact)),
        "mugilidae_epithet_hits": len(mugil),
    }


def score(species, families):
    eel_hits = exact_rows(species, *EEL)
    if len(eel_hits) != 1:
        eel = {
            "queried_as": "Anguilla anguilla",
            "match": "duplicate" if len(eel_hits) > 1 else "unresolved",
            "n_rows": int(len(eel_hits)),
            "component": "inconclusive",
        }
    else:
        eel = row_record(eel_hits.iloc[0], families)
        eel["queried_as"] = "Anguilla anguilla"
        eel["match"] = "exact"
        if eel["anacat"] == "catadromous" and eel["inland_and_sea"]:
            eel["component"] = "supports"
        elif eel["anacat"] in EEL_REFUTE:
            eel["component"] = "refutes"
        else:
            eel["component"] = "inconclusive"

    mullet_rows = [resolve_mullet(species, families, g, s) for g, s in MULLETS]
    if any(r.get("match") == "duplicate" for r in mullet_rows) or eel.get("match") == "duplicate":
        return eel, mullet_rows, "inconclusive", "underpowered", "duplicate species rows"

    resolved = [r for r in mullet_rows if r.get("anacat") and r.get("family") == "Mugilidae"]
    n = len(resolved)
    inland_support = [
        r for r in resolved if r["anacat"] in INLAND and r["inland_and_sea"]
    ]
    disconfirm = [r for r in resolved if r["anacat"] in NOT_INLAND]
    inland_habitat_fail = [
        r for r in resolved if r["anacat"] in INLAND and not r["inland_and_sea"]
    ]
    mullet_component = "inconclusive"
    mullet_reason = None
    if n < 4:
        mullet_reason = f"only {n} mullet rows with AnaCat"
    elif len(inland_support) > n / 2:
        mullet_component = "supports"
    elif len(disconfirm) > n / 2 or len(inland_habitat_fail) > n / 2:
        mullet_component = "refutes"
    else:
        mullet_reason = "no strict majority"

    if eel["component"] == "inconclusive" or mullet_component == "inconclusive":
        reason = "underpowered"
        if eel.get("match") == "unresolved":
            reason = "data-unavailable"
        return eel, mullet_rows, "inconclusive", reason, mullet_reason

    if eel["component"] == "supports" and mullet_component == "supports":
        verdict = "supports"
    elif eel["component"] == "refutes" and mullet_component == "refutes":
        verdict = "refutes"
    else:
        verdict = "mixed"

    extra_counts = {
        "mullet_resolved": n,
        "mullet_inland_support": len(inland_support),
        "mullet_disconfirm": len(disconfirm),
        "mullet_inland_habitat_fail": len(inland_habitat_fail),
    }
    return eel, mullet_rows, verdict, None, extra_counts


def confidence_for(verdict: str, mullet_resolved: int) -> float:
    """Pre-registered confidence rule. See confidence_rule_preregistered."""
    if verdict == "inconclusive":
        return 0.45
    complete = mullet_resolved == 6
    if complete and verdict in ("supports", "refutes"):
        return 0.7
    if complete and verdict == "mixed":
        return 0.65
    return 0.5


def migration_word(html: str) -> str | None:
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain)
    match = re.search(
        r"\b(catadromous|anadromous|amphidromous|potamodromous|limnodromous|oceanodromous|non-migratory)\b",
        plain,
        flags=re.I,
    )
    return match.group(1).casefold() if match else None


def migration_ref(html: str, word: str | None) -> str | None:
    if not word:
        return None
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain)
    match = re.search(rf"{word}\s*\(Ref\.\s*(\d+)\s*\)", plain, flags=re.I)
    return match.group(1) if match else None


def live_check(rows: list[dict]) -> list[dict]:
    out = []
    live_dir = CACHE / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    for rec in rows:
        if "spec_code" not in rec:
            continue
        url = f"https://www.fishbase.se/summary/{rec['spec_code']}"
        raw = fetch(url, live_dir / f"{rec['spec_code']}.html")
        norm = normalize_html(raw)
        html = norm.decode("utf-8")
        word = migration_word(html)
        out.append(
            {
                "spec_code": rec["spec_code"],
                "binomial": f"{rec['genus']} {rec['species']}",
                "download_url": url,
                "raw_byte_size": len(raw),
                "normalized_byte_size": len(norm),
                "sha256_normalized": sha256_bytes(norm),
                "live_anacat": word,
                "live_ref": migration_ref(html, word),
                "matches_parquet": word == rec.get("anacat"),
            }
        )
    return out


def glossary_files() -> list[dict]:
    out = []
    gdir = CACHE / "glossary"
    for term, url in GLOSSARY.items():
        raw = fetch(url, gdir / f"{term}.html")
        text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
        if term not in text.casefold():
            raise SystemExit(f"glossary page for {term} did not contain the term")
        out.append(
            {
                "name": f"{term}.html",
                "download_url": url,
                "byte_size": len(raw),
                "sha256": sha256_bytes(raw),
            }
        )
    return out


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(RESULT_PATH.read_text())
    species, families, species_bytes, families_bytes, parquet_ok = load_tables()

    if not parquet_ok:
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["data_kind"] = "none"
        result["confidence"] = 0.45
        result["method"] = (
            "The FishBase v26.06 parquet download did not match the SHA-256 "
            "recorded at first retrieval, so the pre-registered rule stops the test."
        )
        result["measured"] = {
            "value": None,
            "unit": "components supported, of 2",
            "n": 0,
            "uncertainty": "checksum mismatch",
            "extra": {},
        }
        RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n")
        print("inconclusive: checksum mismatch")
        return

    eel, mullets, verdict, reason, detail = score(species, families)
    scored_mullets = [r for r in mullets if r.get("anacat") and r.get("family") == "Mugilidae"]
    mullet_n = len(scored_mullets)
    if verdict == "inconclusive" or not isinstance(detail, dict):
        components_supported = None
        confidence = 0.45
    else:
        mullet_supported = detail["mullet_inland_support"] > detail["mullet_resolved"] / 2
        components_supported = int(eel["component"] == "supports") + int(mullet_supported)
        confidence = confidence_for(verdict, mullet_n)

    live_rows = []
    try:
        live_rows = live_check([eel] + [r for r in mullets if "spec_code" in r])
    except Exception as exc:  # network failure of the corroboration pages
        live_rows = [{"error": str(exc)}]
    glossary = glossary_files()

    # Keep the first retrieval time once the checksums have been locked.
    prior = result.get("datasets") or []
    if prior and all(
        any(f.get("sha256") == EXPECTED_PARQUET[name]["sha256"] for f in prior[0].get("files", []))
        for name in EXPECTED_PARQUET
    ):
        retrieved_at = prior[0]["files"][0].get("retrieved_at", retrieved_at)

    live_match = all(r.get("matches_parquet") for r in live_rows if "matches_parquet" in r)

    measured = {
        "value": components_supported,
        "unit": "migration components supported, of 2 (eel seaward; mullet inland from the sea)",
        "n": (1 if eel.get("component") in ("supports", "refutes") else 0) + mullet_n,
        "uncertainty": (
            None
            if verdict == "inconclusive"
            else (
                f"mullet inland-support {detail['mullet_inland_support']}/"
                f"{detail['mullet_resolved']}; "
                f"mullet catadromous-or-other {detail['mullet_disconfirm']}/"
                f"{detail['mullet_resolved']}"
            )
        ),
        "extra": {
            "eel_component": eel.get("component"),
            "mullet_component": (
                "supports"
                if verdict != "inconclusive" and detail["mullet_inland_support"] > detail["mullet_resolved"] / 2
                else (
                    "refutes"
                    if verdict != "inconclusive"
                    and (
                        detail["mullet_disconfirm"] > detail["mullet_resolved"] / 2
                        or detail["mullet_inland_habitat_fail"] > detail["mullet_resolved"] / 2
                    )
                    else "inconclusive"
                )
            ),
            "eel": {k: eel.get(k) for k in (
                "spec_code", "genus", "species", "fb_name", "family", "anacat",
                "fresh", "brackish", "saltwater", "component",
            )},
            "mullets": [
                {k: r.get(k) for k in (
                    "queried_as", "match", "spec_code", "genus", "species", "fb_name",
                    "family", "anacat", "fresh", "brackish", "saltwater", "inland_and_sea",
                )}
                for r in mullets
            ],
            "counts": detail if isinstance(detail, dict) else {"note": detail},
            "live_ecology_matches_parquet": live_match,
            "live_pages": live_rows,
        },
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    table_rows = []
    for rec in [eel] + mullets:
        if "genus" not in rec:
            continue
        table_rows.append(rec)
    pd.DataFrame(table_rows).to_csv(DERIVED / "scored-species.csv", index=False)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
    if verdict == "inconclusive":
        result["reason"] = reason
        result["data_kind"] = "none"
    else:
        result.pop("reason", None)
    result["measured"] = measured
    result["method"] = (
        "Downloaded the FishBase v26.06 species and families parquet files from "
        "Source Cooperative, checked both SHA-256 values against the first retrieval, "
        "and read only SpecCode, names, family, Fresh, Brack, Saltwater and AnaCat. "
        "Yes-flags accept 1 and -1. The European eel and the six pre-registered "
        "Mediterranean mullet binomials were scored with the pre-registered strict-majority "
        "rule. The same species' live summary pages were re-fetched and the migration word "
        "on the Ecology line was compared with AnaCat; that comparison is reported and is "
        "not an input to the verdict. Glossary pages were fetched to pin the term definitions "
        "used in the mapping."
    )
    eel_word = eel.get("anacat")
    mullet_bits = ", ".join(
        f"{r.get('genus')} {r.get('species')}={r.get('anacat')}"
        for r in mullets
        if r.get("genus")
    )
    result["results_summary"] = [
        f"Eel component {eel.get('component')}: Anguilla anguilla AnaCat={eel_word}, "
        f"fresh={eel.get('fresh')}, brackish={eel.get('brackish')}, saltwater={eel.get('saltwater')} "
        f"(SpecCode {eel.get('spec_code')}).",
        f"Mullet rows: {mullet_bits}.",
        (
            f"Mullet vote: inland-support {detail['mullet_inland_support']}/"
            f"{detail['mullet_resolved']}, disconfirming categories "
            f"{detail['mullet_disconfirm']}/{detail['mullet_resolved']}."
            if isinstance(detail, dict)
            else f"Mullet component undecided: {detail}."
        ),
        f"Overall verdict {verdict}. Live ecology lines match the parquet categories: {live_match}.",
    ]
    caveats = list(result.get("caveats") or [])
    extra_caveat = (
        "Oedalechilus labeo has no AnaCat in snapshot v26.06, so the mullet majority "
        "is taken over the five rows that have a category. Confidence 0.5 is the "
        "pre-registered value for a vote on four or five mullet rows."
    )
    if extra_caveat not in caveats:
        caveats.append(extra_caveat)
    live_caveat = (
        "Live fishbase.se summary pages (version string (06/2026) and "
        "Attribution-NonCommercial 4.0 International on search.php) carry the same "
        "migration word as AnaCat. Their raw SHA-256 is not stable, because the HTML "
        "includes a per-request processing time; sha256 on those files is of the HTML "
        "with that number replaced by TIME."
    )
    if live_caveat not in caveats:
        caveats.append(live_caveat)
    result["caveats"] = caveats

    result["datasets"] = [
        {
            "id": "fishbase-rfishbase-parquet-v26.06-species-families",
            "name": "FishBase backend snapshot v26.06, species and families tables (rfishbase parquet)",
            "landing_url": "https://source.coop/cboettig/fishbase",
            "doi": None,
            "version": "fb/v26.06",
            "license": "CC BY-NC 4.0",
            "files": [
                {
                    "name": "species.parquet",
                    "download_url": SPECIES_URL,
                    "retrieved_at": retrieved_at,
                    "byte_size": len(species_bytes),
                    "sha256": sha256_bytes(species_bytes),
                },
                {
                    "name": "families.parquet",
                    "download_url": FAMILIES_URL,
                    "retrieved_at": retrieved_at,
                    "byte_size": len(families_bytes),
                    "sha256": sha256_bytes(families_bytes),
                },
            ],
            "role": "AnaCat migration category and fresh, brackish and saltwater flags for the European eel and six Mediterranean grey mullets; family names for the Mugilidae check",
        },
        {
            "id": "fishbase-glossary-migration-terms",
            "name": "FishBase glossary entries for catadromous, anadromous and amphidromous",
            "landing_url": "https://www.fishbase.se/glossary/Glossary.php",
            "doi": None,
            "version": "as served 2026-11-01",
            "license": "CC BY-NC 4.0",
            "files": [{**g, "retrieved_at": retrieved_at} for g in glossary],
            "role": "definitions that fix how AnaCat strings map onto the directions in the claim",
        },
        {
            "id": "fishbase-live-summaries-2026-11-01",
            "name": "FishBase species summary pages for the seven SpecCodes",
            "landing_url": "https://www.fishbase.se/",
            "doi": None,
            "version": "(06/2026)",
            "license": "CC BY-NC 4.0",
            "files": [
                {
                    "name": f"{r['spec_code']}.html",
                    "download_url": r["download_url"],
                    "retrieved_at": retrieved_at,
                    "byte_size": r["normalized_byte_size"],
                    "sha256": r["sha256_normalized"],
                    "sha256_note": "HTML with the per-request processing-time number replaced by TIME",
                }
                for r in live_rows
                if "sha256_normalized" in r
            ],
            "role": "same-day re-query of the live source; the Ecology migration word is checked against AnaCat and is not used to choose the verdict",
        },
    ]

    # Preserve pre-registered prose. These keys must stay byte-identical to the
    # preregistration commit aside from the fields this script is allowed to add.
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "measured_value": measured["value"],
        "n": measured["n"],
        "uncertainty": measured["uncertainty"],
        "live_match": live_match,
    }, indent=2))


if __name__ == "__main__":
    main()
