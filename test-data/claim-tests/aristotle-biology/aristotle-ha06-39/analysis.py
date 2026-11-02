#!/usr/bin/env python3
"""Bear-cub relative size. Thresholds are the pre-registered ones in result.json."""
import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
EXCLUDED_ORDERS = {
    "didelphimorphia",
    "paucituberculata",
    "microbiotheria",
    "notoryctemorphia",
    "dasyuromorphia",
    "peramelemorphia",
    "diprotodontia",
    "monotremata",
    "marsupialia",
}
PAN_URL = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return {
        "download_url": url,
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def fnum(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "" or text.lower() in {"na", "nan", "-"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number <= -900:
        return None
    return number


def norm_header(header):
    return re.sub(r"\s+", "", header)


def qualifying(rows):
    kept = []
    for row in rows:
        neo = row["neonate"]
        adult = row["adult"]
        if neo is None or adult is None:
            continue
        if neo <= 0 or adult <= 0 or neo >= adult:
            continue
        row = dict(row)
        row["ratio"] = neo / adult
        kept.append(row)
    return kept


def find_species(rows, genus, species):
    genus = genus.lower()
    species = species.lower()
    for row in rows:
        if row["genus"].lower() == genus and row["species"].lower() == species:
            return row
    return None


def superlative(rows, bear):
    """Return status for the unique-minimum rule."""
    others = [row for row in rows if row["binomial"].lower() != bear["binomial"].lower()]
    smaller = [row for row in others if row["ratio"] < bear["ratio"]]
    tied = [row for row in others if row["ratio"] == bear["ratio"]]
    smaller.sort(key=lambda row: row["ratio"])
    if smaller:
        return "refutes", smaller, tied
    if tied:
        return "mixed", smaller, tied
    return "supports", smaller, tied


def placental(rows):
    return [row for row in rows if row["order"].lower() not in EXCLUDED_ORDERS]


def bracket(bear, mouse, weasel):
    if bear is None or mouse is None or weasel is None:
        return "untested"
    if mouse["adult"] is None or weasel["adult"] is None or bear["neonate"] is None:
        return "untested"
    if bear["neonate"] > mouse["adult"] and bear["neonate"] < weasel["adult"]:
        return "supports"
    return "refutes"


def combine(pan_status, anage_status, bracket_status, eye):
    """eye is 'supports', 'refutes', or 'untested'."""
    if pan_status == "inconclusive":
        return "inconclusive", None
    if anage_status == "mixed" or (
        anage_status in {"supports", "refutes"} and anage_status != pan_status
    ):
        return "mixed", None
    if pan_status == "refutes":
        return "refutes", None
    if pan_status == "mixed":
        return "mixed", None
    # superlative supports
    if bracket_status == "refutes" or eye == "refutes":
        return "mixed", None
    return "supports", None


def confidence_for(verdict, n_smaller, anage_status, bracket_status):
    if verdict == "inconclusive":
        return 0.8
    if verdict == "mixed":
        return 0.6
    if verdict == "refutes":
        return 0.85 if n_smaller >= 5 else 0.7
    if anage_status == "supports" and bracket_status == "supports":
        return 0.7
    return 0.55


def load_pantheria(path):
    # The metadata header contains spaces after some underscores.
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    headers = [norm_header(h) for h in lines[0].split("\t")]

    def col(*parts, exclude=()):
        for i, header in enumerate(headers):
            if all(part in header for part in parts) and not any(bad in header for bad in exclude):
                return i
        raise KeyError(parts)

    i_order = col("Order")
    i_genus = col("Genus")
    i_species = col("Species")
    i_binomial = col("Binomial")
    i_adult = col("AdultBodyMass_g", exclude=("EXT", "Basal", "Weaning", "Neonate"))
    i_neo = col("NeonateBodyMass_g", exclude=("EXT", "Weaning"))
    i_eye = col("AgeatEyeOpening")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split("\t")
        genus = cells[i_genus].strip()
        species = cells[i_species].strip()
        rows.append(
            {
                "order": cells[i_order].strip(),
                "genus": genus,
                "species": species,
                "binomial": cells[i_binomial].strip() or f"{genus} {species}",
                "neonate": fnum(cells[i_neo]),
                "adult": fnum(cells[i_adult]),
                "eye": fnum(cells[i_eye]),
            }
        )
    return rows


def load_anage(path):
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if not names:
            raise RuntimeError(f"no text file in AnAge zip: {archive.namelist()}")
        text = archive.read(names[0]).decode("utf-8", errors="replace")
        inner_name = names[0]
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    headers = reader.fieldnames or []

    def find(*needles):
        for header in headers:
            lowered = header.lower()
            if all(needle in lowered for needle in needles):
                return header
        return None

    c_class = find("class")
    c_order = find("order")
    c_genus = find("genus")
    c_species = find("species")
    c_birth = find("birth", "weight")
    c_adult = find("adult", "weight")
    if not all([c_class, c_genus, c_species, c_birth, c_adult]):
        raise RuntimeError(f"AnAge columns missing: {headers}")
    rows = []
    for record in reader:
        if (record.get(c_class) or "").strip().lower() != "mammalia":
            continue
        genus = (record.get(c_genus) or "").strip()
        species = (record.get(c_species) or "").strip()
        rows.append(
            {
                "order": (record.get(c_order) or "").strip() if c_order else "",
                "genus": genus,
                "species": species,
                "binomial": f"{genus} {species}",
                "neonate": fnum(record.get(c_birth)),
                "adult": fnum(record.get(c_adult)),
                "eye": None,
            }
        )
    return rows, inner_name, headers


def rank_payload(rows, bear):
    ordered = sorted(rows, key=lambda row: row["ratio"])
    bear_rank = 1 + sum(1 for row in ordered if row["ratio"] < bear["ratio"])
    smallest = [
        {
            "binomial": row["binomial"],
            "order": row["order"],
            "ratio": round(row["ratio"], 6),
            "neonate_g": row["neonate"],
            "adult_g": row["adult"],
        }
        for row in ordered[:12]
    ]
    return bear_rank, len(rows), smallest


def dataset_status(rows, label):
    kept = qualifying(rows)
    bear = find_species(kept, "Ursus", "arctos")
    if bear is None or len(kept) < 30:
        return {
            "label": label,
            "status": "inconclusive",
            "n": len(kept),
            "bear": None,
            "n_smaller": 0,
            "smaller": [],
            "tied": [],
            "smallest": [],
            "placental": None,
        }
    status, smaller, tied = superlative(kept, bear)
    rank, n, smallest = rank_payload(kept, bear)
    plac = qualifying(placental(rows))
    plac_bear = find_species(plac, "Ursus", "arctos")
    plac_info = None
    if plac_bear is not None and len(plac) >= 30:
        plac_status, plac_smaller, _tied = superlative(plac, plac_bear)
        plac_info = {
            "status": plac_status,
            "n": len(plac),
            "n_smaller": len(plac_smaller),
            "smallest": [
                {"binomial": row["binomial"], "ratio": round(row["ratio"], 6)}
                for row in sorted(plac, key=lambda row: row["ratio"])[:8]
            ],
        }
    return {
        "label": label,
        "status": status,
        "n": n,
        "rank": rank,
        "bear": {
            "binomial": bear["binomial"],
            "ratio": bear["ratio"],
            "neonate_g": bear["neonate"],
            "adult_g": bear["adult"],
            "eye": bear.get("eye"),
        },
        "n_smaller": len(smaller),
        "smaller": [
            {"binomial": row["binomial"], "order": row["order"], "ratio": round(row["ratio"], 6)}
            for row in smaller[:15]
        ],
        "tied": [row["binomial"] for row in tied[:10]],
        "smallest": smallest,
        "placental": plac_info,
    }


def eye_status(bear_row_unfiltered):
    if bear_row_unfiltered is None or bear_row_unfiltered.get("eye") is None:
        return "untested", None
    eye = bear_row_unfiltered["eye"]
    if eye > 0:
        return "supports", eye
    if eye == 0:
        return "refutes", eye
    return "untested", eye


def self_test():
    def row(binomial, order, neo, adult):
        genus, species = binomial.split()
        return {
            "order": order,
            "genus": genus,
            "species": species,
            "binomial": binomial,
            "neonate": neo,
            "adult": adult,
            "eye": None,
            "ratio": neo / adult,
        }

    bear = row("Ursus arctos", "Carnivora", 40, 100000)
    mouse = row("Mus musculus", "Rodentia", 1, 20)
    weasel = row("Mustela nivalis", "Carnivora", 2, 80)
    kangaroo = row("Macropus rufus", "Diprotodontia", 1, 30000)
    wolf = row("Canis lupus", "Carnivora", 500, 40000)
    assert superlative([bear, mouse, wolf], bear)[0] == "supports"
    assert superlative([bear, kangaroo], bear)[0] == "refutes"
    tied = row("Canis lupus", "Carnivora", 40, 100000)
    assert superlative([bear, tied], bear)[0] == "mixed"
    assert bracket(bear, mouse, weasel) == "supports"
    huge_mouse = dict(mouse, adult=500)
    assert bracket(bear, huge_mouse, weasel) == "refutes"
    assert combine("supports", "supports", "supports", "supports")[0] == "supports"
    assert combine("refutes", "supports", "supports", "supports")[0] == "mixed"
    assert combine("refutes", "refutes", "supports", "supports")[0] == "refutes"
    assert combine("supports", "supports", "refutes", "supports")[0] == "mixed"
    assert combine("supports", None, "supports", "untested")[0] == "supports"
    assert combine("inconclusive", None, "untested", "untested")[0] == "inconclusive"
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    pan_meta = fetch(PAN_URL, CACHE / "PanTHERIA_1-0_WR05_Aug2008.txt")
    anage_meta = fetch(ANAGE_URL, CACHE / "anage.zip")
    pan_rows = load_pantheria(CACHE / "PanTHERIA_1-0_WR05_Aug2008.txt")
    anage_rows, anage_inner, _headers = load_anage(CACHE / "anage.zip")
    pan = dataset_status(pan_rows, "pantheria")
    anage = dataset_status(anage_rows, "anage")
    anage_for_rule = anage["status"] if anage["status"] in {"supports", "refutes", "mixed"} else None
    if anage["n"] < 30 or anage["bear"] is None:
        anage_for_rule = None
    pan_bear_raw = find_species(pan_rows, "Ursus", "arctos")
    eye_flag, eye_value = eye_status(pan_bear_raw)
    # Bracket uses PanTHERIA adult masses, falling back to AnAge adults.
    pan_kept = qualifying(pan_rows)
    an_kept = qualifying(anage_rows)
    bear = find_species(pan_kept, "Ursus", "arctos") or find_species(an_kept, "Ursus", "arctos")
    mouse = find_species(pan_kept, "Mus", "musculus") or find_species(an_kept, "Mus", "musculus")
    # Adult mass for the bracket is the adult of that species, even if neonate failed the filter.
    def adult_of(rows, genus, species):
        found = find_species(rows, genus, species)
        if found and found.get("adult"):
            return found
        return None

    mouse_adult = adult_of(pan_rows, "Mus", "musculus") or adult_of(anage_rows, "Mus", "musculus")
    weasel_adult = adult_of(pan_rows, "Mustela", "nivalis") or adult_of(anage_rows, "Mustela", "nivalis")
    weasel_name = "Mustela nivalis"
    if weasel_adult is None or weasel_adult.get("adult") is None:
        weasel_adult = adult_of(pan_rows, "Mustela", "erminea") or adult_of(anage_rows, "Mustela", "erminea")
        weasel_name = "Mustela erminea"
    bracket_status = bracket(bear, mouse_adult, weasel_adult)
    if pan["status"] == "inconclusive":
        verdict = "inconclusive"
        reason = "underpowered" if pan["n"] and pan["n"] < 30 else "data-unavailable"
    else:
        verdict, _ = combine(pan["status"], anage_for_rule, bracket_status, eye_flag)
        reason = None
    measured = {
        "value": None if not pan.get("bear") else round(pan["bear"]["ratio"], 6),
        "unit": "neonate mass / adult mass, Ursus arctos, PanTHERIA",
        "n": pan["n"],
        "uncertainty": "ratio of published point masses; adult mass is not sex-specific",
        "extra": {
            "pantheria": pan,
            "anage": anage,
            "anage_used_in_verdict": anage_for_rule is not None,
            "bracket": bracket_status,
            "weasel_species": weasel_name,
            "mouse_adult_g": None if not mouse_adult else mouse_adult.get("adult"),
            "weasel_adult_g": None if not weasel_adult else weasel_adult.get("adult"),
            "eye_opening_days": eye_value,
            "eye_clause": eye_flag,
            "anage_inner_file": anage_inner,
        },
    }
    reason_text = {
        "supports": "Ursus arctos has the unique minimum neonate/adult ratio in PanTHERIA, and the scored side clauses do not contradict it.",
        "refutes": "At least one other mammal in PanTHERIA has a strictly smaller neonate/adult ratio than Ursus arctos.",
        "mixed": "The superlative, the mouse/weasel bracket, eye opening, or the AnAge replication do not agree.",
        "inconclusive": "Ursus arctos or the species sample is missing from PanTHERIA.",
    }[verdict]
    result["status"] = "complete"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = confidence_for(verdict, pan["n_smaller"], anage_for_rule, bracket_status)
    result["data_kind"] = "none" if verdict == "inconclusive" and reason == "data-unavailable" else "biological"
    result["method"] = (
        "Downloaded PanTHERIA WR05 and the AnAge zip, dropped non-positive masses and neonate masses at least as large as adult mass, "
        "and ranked neonate/adult ratios. The verdict follows the pre-registered rule: a strictly smaller non-bear refutes, a tie or a "
        "failed size bracket or eyes open at birth or a disagreeing AnAge replication is mixed, and a unique minimum with the side clauses "
        "holding or untested supports. The placental subset is stored and does not vote."
    )
    result["datasets"] = [
        {
            "id": "pantheria-wr05-2008",
            "name": "PanTHERIA 1.0 WR05 species-level mammal life-history table",
            "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
            "doi": "10.1890/08-1494.1",
            "version": "1.0_WR05_Aug2008",
            "license": "No copyright restriction stated in the Ecological Archives metadata; citation requested",
            "files": [{**pan_meta, "name": "PanTHERIA_1-0_WR05_Aug2008.txt"}],
            "role": "neonate mass, adult mass and age at eye opening",
        },
        {
            "id": "anage-hagr",
            "name": "AnAge build, birth weight and adult weight",
            "landing_url": "https://genomics.senescence.info/species/index.html",
            "doi": None,
            "version": anage_inner,
            "license": "CC BY 3.0",
            "files": [{**anage_meta, "name": "dataset.zip"}],
            "role": "replication of neonate/adult ratios, and adult masses for mouse and weasel if PanTHERIA lacks them",
        },
    ]
    result["measured"] = measured
    result["results_summary"] = [reason_text]
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, measured["value"], "n", pan["n"], "smaller", pan["n_smaller"])


if __name__ == "__main__":
    main()
