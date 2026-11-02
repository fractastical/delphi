#!/usr/bin/env python3
"""aristotle-ha09-38: ruminants lack upper front teeth.

Rules fixed in result.json before HerbiTraits_1.2.csv and file19.txt were opened.
Dependencies: pandas.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test"}

HERBI_URL = (
    "https://raw.githubusercontent.com/MegaPast2Future/HerbiTraits/master/"
    "Data/HerbiTraits_1.2/HerbiTraits_1.2/HerbiTraits_1.2.csv"
)
DENTAL_URL = "https://people.sc.fsu.edu/~jburkardt/datasets/hartigan/file19.txt"

# Fixed before either table was opened. Do not add keys.
GENUS_MAP = {
    "cow": "Bos",
    "ox": "Bos",
    "cattle": "Bos",
    "bull": "Bos",
    "sheep": "Ovis",
    "ewe": "Ovis",
    "ram": "Ovis",
    "goat": "Capra",
    "deer": "Cervus",
    "elk": "Cervus",
    "moose": "Alces",
    "caribou": "Rangifer",
    "reindeer": "Rangifer",
    "camel": "Camelus",
    "llama": "Lama",
    "alpaca": "Lama",
    "giraffe": "Giraffa",
    "pig": "Sus",
    "hog": "Sus",
    "boar": "Sus",
    "horse": "Equus",
    "mare": "Equus",
    "stallion": "Equus",
    "hippopotamus": "Hippopotamus",
    "hippo": "Hippopotamus",
}
EXAMPLE_GENERA = ("Bos", "Ovis", "Capra")
FROZEN = (
    "claim_id",
    "claim_iri",
    "project",
    "created",
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "agent",
)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(exist_ok=True)
    retrieved = None
    if not dest.exists() or dest.stat().st_size < 100:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
        retrieved = now_utc()
    raw = dest.read_bytes()
    mtime = dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc)
    return {
        "download_url": url,
        "retrieved_at": retrieved or mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": sha256(raw),
    }


def normalize(value: object) -> str:
    text = str(value).lower().strip()
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_extant(status: object) -> bool:
    return re.search(r"\bExtant\b", str(status)) is not None


def parse_dentition(path: Path) -> tuple[pd.DataFrame, bool]:
    """Return rows and whether the file itself names column I as top incisors."""
    text = path.read_text(encoding="utf-8", errors="replace")
    header_ok = bool(
        re.search(r"top incisors", text, flags=re.IGNORECASE)
        and re.search(r'"Name"\s+"I"\s+"i"\s+"C"\s+"c"\s+"P"\s+"p"\s+"M"\s+"m"', text)
    )
    rows = []
    for line in text.splitlines():
        match = re.match(
            r'^"([^"]+)"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',
            line.strip(),
        )
        if not match:
            continue
        name = match.group(1)
        if name == "Name":
            continue
        rows.append(
            {
                "dental_name": name,
                "top_incisors": int(match.group(2)),
                "lower_incisors": int(match.group(3)),
            }
        )
    return pd.DataFrame(rows), header_ok and not pd.DataFrame(rows).empty


def assign_genera(dental: pd.DataFrame, traits: pd.DataFrame) -> dict:
    """Map each dental name onto at most one genus. Conflicting counts drop the genus."""
    traits = traits.copy()
    traits["genus"] = traits["Binomial"].astype(str).str.split().str[0]
    traits["common_norm"] = traits["Common.Name"].map(
        lambda value: normalize(value) if pd.notna(value) else ""
    )
    used = []
    skipped = []
    genus_counts: dict[str, set[int]] = {}
    genus_sources: dict[str, list[str]] = {}

    for row in dental.itertuples(index=False):
        key = normalize(row.dental_name)
        if key in GENUS_MAP:
            genus = GENUS_MAP[key]
            route = "fixed-map"
        else:
            hits = traits[traits["common_norm"] == key]
            genera = sorted({g for g in hits["genus"].dropna().unique() if g})
            if len(genera) != 1:
                skipped.append(
                    {
                        "dental_name": row.dental_name,
                        "why": "no common-name match" if not genera else "more than one genus",
                        "genera": genera,
                    }
                )
                continue
            genus = genera[0]
            route = "exact-common-name"
        genus_counts.setdefault(genus, set()).add(int(row.top_incisors))
        genus_sources.setdefault(genus, []).append(
            f"{row.dental_name} (I={int(row.top_incisors)}, {route})"
        )
        used.append(
            {
                "dental_name": row.dental_name,
                "genus": genus,
                "top_incisors": int(row.top_incisors),
                "route": route,
            }
        )

    assigned = {}
    conflicts = []
    for genus, counts in genus_counts.items():
        if len(counts) != 1:
            conflicts.append({"genus": genus, "counts": sorted(counts)})
            continue
        assigned[genus] = {
            "top_incisors": next(iter(counts)),
            "sources": genus_sources[genus],
        }
    return {"assigned": assigned, "used": used, "skipped": skipped, "conflicts": conflicts}


def score(traits: pd.DataFrame, assignment: dict) -> dict:
    frame = traits.copy()
    frame["genus"] = frame["Binomial"].astype(str).str.split().str[0]
    frame["extant"] = frame["Species.Status"].map(is_extant)
    frame["ruminant"] = frame["Fermentation.Type"].eq("Foregut Ruminant")
    assigned = assignment["assigned"]
    frame["top_incisors"] = frame["genus"].map(
        lambda genus: assigned.get(genus, {}).get("top_incisors")
    )
    frame["joined"] = frame["top_incisors"].notna()

    extant = frame[frame["extant"]].copy()
    group = extant[extant["ruminant"] & extant["joined"]].drop_duplicates("Binomial")
    n = int(group.shape[0])
    n_zero = int((group["top_incisors"] == 0).sum()) if n else 0
    fraction = None if n == 0 else n_zero / n

    example = {}
    example_fail = False
    example_pass_flags = []
    for genus in EXAMPLE_GENERA:
        sub = extant[extant["genus"] == genus]
        joined = sub[sub["joined"]]
        bad = joined[(~joined["ruminant"]) | (joined["top_incisors"] > 0)]
        good = joined[joined["ruminant"] & (joined["top_incisors"] == 0)]
        failed = int(bad.drop_duplicates("Binomial").shape[0]) > 0
        passed = int(good.drop_duplicates("Binomial").shape[0]) > 0
        example_fail = example_fail or failed
        example_pass_flags.append(passed)
        example[genus] = {
            "n_extant": int(sub.drop_duplicates("Binomial").shape[0]),
            "n_extant_foregut_ruminant": int(
                sub[sub["ruminant"]].drop_duplicates("Binomial").shape[0]
            ),
            "n_joined_extant": int(joined.drop_duplicates("Binomial").shape[0]),
            "top_incisors": assigned.get(genus, {}).get("top_incisors"),
            "clause": "fail" if failed else ("pass" if passed else "missing"),
        }
    example_pass = all(example_pass_flags) and not example_fail
    example_status = "fail" if example_fail else ("pass" if example_pass else "missing")

    if n >= 8 and fraction is not None and fraction < 0.50:
        group_status = "fail"
    elif n >= 8 and fraction is not None and fraction >= 0.80:
        group_status = "pass"
    elif n >= 8 and fraction is not None and 0.50 <= fraction < 0.80:
        group_status = "intermediate"
    else:
        group_status = "underpowered"

    if example_status == "fail" or group_status == "fail":
        verdict, reason = "refutes", None
    elif example_status == "pass" and group_status == "pass":
        verdict, reason = "supports", None
    elif example_status == "missing" and group_status == "pass":
        verdict, reason = "mixed", None
    elif group_status == "intermediate" and example_status != "fail":
        verdict, reason = "mixed", None
    elif group_status == "underpowered" and example_status != "fail":
        verdict, reason = "inconclusive", "underpowered"
    else:
        verdict, reason = "inconclusive", "other"

    confidence = {
        "supports": 0.66,
        "refutes": 0.7,
        "mixed": 0.5,
        "inconclusive": 0.48 if reason == "underpowered" else 0.35,
    }[verdict]

    rows = group.sort_values(["genus", "Binomial"])
    return {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "n": n,
        "n_zero": n_zero,
        "fraction": fraction,
        "example_status": example_status,
        "group_status": group_status,
        "example": example,
        "joined_rows": rows,
    }


def main() -> None:
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    frozen = {key: result[key] for key in FROZEN}
    analysis_caveats = [
        "The Hartigan file's labels that hit the fixed map are elk, deer, moose and reindeer. Cattle, sheep and goat are not labels in that file, so Bos, Ovis and Capra receive no top-incisor count. The map was not extended to fill that gap.",
        "One count is copied to every extant species of the matched genus. Cervus receives the elk and deer formulae, which agree at 0 upper incisors.",
    ]
    original_caveats = [c for c in result.get("caveats", []) if c not in analysis_caveats]

    herbi_meta = fetch(HERBI_URL, DATA / "HerbiTraits_1.2.csv")
    dental_meta = fetch(DENTAL_URL, DATA / "file19.txt")
    traits = pd.read_csv(DATA / "HerbiTraits_1.2.csv")
    dental, column_ok = parse_dentition(DATA / "file19.txt")

    if not column_ok:
        result.update(
            {
                "status": "complete",
                "data_kind": "biological",
                "verdict": "inconclusive",
                "reason": "other",
                "confidence": 0.35,
                "method": "Both files downloaded. The Hartigan file does not identify a top-incisor column, so no species was scored.",
                "measured": {
                    "value": None,
                    "unit": "fraction of joined extant foregut ruminants with top-incisor count 0",
                    "n": 0,
                    "uncertainty": None,
                    "extra": {"dental_rows": int(dental.shape[0]), "column_identified": False},
                },
            }
        )
    else:
        assignment = assign_genera(dental, traits)
        scored = score(traits, assignment)
        fraction = scored["fraction"]
        value = None if fraction is None else round(fraction, 4)
        extra = {
            "n_top_incisors_zero": scored["n_zero"],
            "fraction_top_incisors_zero": value,
            "example_status": scored["example_status"],
            "group_status": scored["group_status"],
            "example_genera": scored["example"],
            "genera_assigned": {
                genus: {
                    "top_incisors": info["top_incisors"],
                    "sources": info["sources"],
                }
                for genus, info in sorted(assignment["assigned"].items())
            },
            "dental_names_used": assignment["used"],
            "dental_names_not_used": assignment["skipped"],
            "genus_count_conflicts": assignment["conflicts"],
            "dental_rows": int(dental.shape[0]),
            "column_identified": True,
        }
        joined = scored["joined_rows"][
            ["Binomial", "Common.Name", "genus", "Species.Status", "Fermentation.Type", "top_incisors"]
        ].rename(columns={"genus": "Genus", "top_incisors": "TopIncisors"})
        joined["TopIncisors"] = joined["TopIncisors"].astype(int)
        DERIVED.mkdir(exist_ok=True)
        joined.to_csv(DERIVED / "joined.csv", index=False)
        measured = {
            "value": value,
            "unit": "fraction of joined extant foregut ruminants with top-incisor count 0",
            "n": scored["n"],
            "uncertainty": None,
            "extra": extra,
        }
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        n = scored["n"]
        n_zero = scored["n_zero"]
        summary = (
            f"Group {scored['group_status']}: {n_zero} of {n} joined extant foregut ruminants "
            f"have a top-incisor count of 0 (fraction {value}). "
            f"Example clause {scored['example_status']}: "
            + ", ".join(
                f"{genus} {scored['example'][genus]['clause']}" for genus in EXAMPLE_GENERA
            )
            + "."
        )
        result.update(
            {
                "status": "complete",
                "data_kind": "biological",
                "verdict": scored["verdict"],
                "confidence": scored["confidence"],
                "measured": measured,
                "method": (
                    "Downloaded HerbiTraits 1.2 and the Hartigan dentition file. "
                    "A ruminant is an extant species whose Fermentation.Type is exactly Foregut Ruminant. "
                    "Column I is the top-incisor count, as the file header states. "
                    "Each dental common name is attached to one genus by the fixed map, or, if it is not in the map, "
                    "by an exact match to one HerbiTraits common name after case-folding. "
                    "Every extant species of that genus receives that count. "
                    "The example clause and the 80 percent group clause are then applied as pre-registered. "
                    "Species with no count are excluded from the fraction."
                ),
                "results_summary": [summary],
                "deviations": [
                    {
                        "field": "normalized strings",
                        "change": "Case-folding, hyphen and underscore to space, other punctuation removed, whitespace collapsed.",
                        "why": "The pre-registered rule says normalized strings must be equal and does not name the function. This does not add map keys and does not change the 80 percent, 50 percent, or n>=8 thresholds.",
                    }
                ],
            }
        )
        if scored["reason"]:
            result["reason"] = scored["reason"]
        else:
            result.pop("reason", None)
        result["caveats"] = original_caveats + analysis_caveats

    herbi_meta_out = {"name": "HerbiTraits_1.2.csv", **herbi_meta}
    dental_meta_out = {"name": "file19.txt", **dental_meta}
    result["datasets"] = [
        {
            "id": "herbitraits-1.2-lundgren-2021",
            "name": "HerbiTraits 1.2, functional traits of late Quaternary large-bodied herbivores",
            "landing_url": "https://github.com/MegaPast2Future/HerbiTraits",
            "doi": "10.1038/s41597-020-00788-5",
            "version": "1.2",
            "license": "CC BY 4.0",
            "files": [herbi_meta_out],
            "role": "fermentation class, independent of the dental formulae; Foregut Ruminant is the ruminant class",
        },
        {
            "id": "hartigan-mammal-dentition-file19",
            "name": "Dentition of mammals, Hartigan Clustering Algorithms page 170, Burkardt file19",
            "landing_url": DENTAL_URL,
            "doi": None,
            "version": "burkardt transcription, Last-Modified 2011-10-16",
            "license": None,
            "files": [dental_meta_out],
            "role": "upper-incisor counts; column I is named as top incisors in the file header",
        },
    ]
    for key, value in frozen.items():
        result[key] = value
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": result.get("verdict"),
        "reason": result.get("reason"),
        "confidence": result.get("confidence"),
        "measured_value": result.get("measured", {}).get("value"),
        "n": result.get("measured", {}).get("n"),
        "summary": result.get("results_summary"),
    }, indent=2))


if __name__ == "__main__":
    main()
