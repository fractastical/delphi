#!/usr/bin/env python3
"""aristotle-pa04-15: is the neck of the wolf and of the lion a single bone?

Decision rule: the one committed in result.json before any cervical count was
read. Needs pypdf to read the lion article PDF (`pip install pypdf`). The other
two sources use only the standard library.

    python3 analysis.py
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/aristotle-pa04-15"
COMMIT = "a766ce94587640a2654e33bff14a7ddaf00aa732"
RAW = f"https://raw.githubusercontent.com/dbkk/vertebral_pattern/{COMMIT}"

GITHUB_FILES = {
    "vertebralData.csv": f"{RAW}/vertebral/fullFormulaTree/vertebralData.csv",
    "species.csv": f"{RAW}/vertebral/fullFormulaTree/species.csv",
    "constraintMaster.csv": f"{RAW}/vertebral/constraintMaster.csv",
}
WOLF_URL = "https://virtual.imnh.iri.isu.edu/Osteo/View/Grey_Wolf/614"
LION_DOI = "https://doi.org/10.22271/veterinary.2021.v6.i2a.328"
LION_PDF = "https://www.veterinarypaper.com/pdf/2021/vol6issue2/PartA/5-4-28-366.pdf"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.status, resp.read(), resp.geturl()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plain(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()


def file_record(url: str, raw: bytes, final: str, retrieved: str) -> dict:
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": sha256(raw),
    }


def binomial_of(name: str) -> str | None:
    tokens = name.replace("_", " ").split()
    if len(tokens) < 2:
        return None
    binomial = f"{tokens[0]} {tokens[1]}"
    if binomial in {"Canis lupus", "Panthera leo"} and len(tokens) == 2:
        return binomial
    return None


def as_count(value: str) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number != int(number):
        return None
    return int(number)


def vertebral_counts(raw: bytes) -> list[dict]:
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    found = []
    for row in rows:
        species = binomial_of((row.get("species") or "").strip())
        if not species:
            continue
        count = as_count(row.get("Cervical") or "")
        if count is None:
            continue
        found.append({"source": "vertebral-pattern-cerbus-2024", "species": species, "count": count, "detail": row.get("species")})
    return found


def other_species_summary(raw: bytes) -> dict:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    ge2 = 0
    eq1 = 0
    for row in rows:
        if binomial_of((row.get("species") or "").strip()):
            continue
        count = as_count(row.get("Cervical") or "")
        if count is None:
            continue
        if count >= 2:
            ge2 += 1
        elif count == 1:
            eq1 += 1
    return {"other_species_cervical_ge_2": ge2, "other_species_cervical_eq_1": eq1, "rows": len(rows)}


def wolf_labels(raw: bytes) -> dict:
    page = raw.decode("utf-8", errors="replace")
    text = plain(page)
    labels = []
    for match in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", page, re.S | re.I):
        label = plain(match.group(1))
        if re.search(r"cervical vertebra", label, re.I):
            labels.append(label)
    # Preserve order, drop duplicates.
    distinct = list(dict.fromkeys(labels))
    return {
        "contains_canis_lupus": "Canis lupus" in text,
        "labels": distinct,
        "count": len(distinct) if "Canis lupus" in text else None,
    }


def lion_pdf_count(raw: bytes) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    admissible = bool(re.search(r"panthera leo|\blion\b", text, re.I))
    match = re.search(r"cervical vertebrae?\b[^\d]{0,40}(\d+)", text, re.I)
    count = int(match.group(1)) if match and admissible else None
    snippet = None
    if match:
        start = max(0, match.start() - 40)
        snippet = re.sub(r"\s+", " ", text[start:match.end() + 40]).strip()
    return {"admissible": admissible, "count": count, "snippet": snippet, "pages": len(reader.pages)}


def consensus(counts: list[int]) -> str:
    if not counts:
        return "missing"
    if all(c > 1 for c in counts):
        return "many"
    if all(c == 1 for c in counts):
        return "one"
    return "conflict"


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = now_utc()
    files = {}
    observations = []

    github_raw = {}
    for name, url in GITHUB_FILES.items():
        status, raw, final = fetch(url)
        (DATA / name).write_bytes(raw)
        files[name] = file_record(url, raw, final, retrieved)
        files[name]["http_status"] = status
        github_raw[name] = raw

    table_counts = vertebral_counts(github_raw["vertebralData.csv"])
    observations.extend({"species": row["species"], "count": row["count"], "source": row["source"], "detail": "Cervical column"} for row in table_counts)
    others = other_species_summary(github_raw["vertebralData.csv"])
    species_list = github_raw["species.csv"].decode("utf-8", errors="replace")
    name_presence = {
        "Canis lupus in species.csv": bool(re.search(r"(?m)^Canis lupus$", species_list)),
        "Panthera leo in species.csv": bool(re.search(r"(?m)^Panthera leo$", species_list)),
        "constraintMaster exact-binomial rows": 0,
    }
    # constraintMaster rows are tree nodes with a species list, not one binomial per row.
    # The pre-registered rule accepts only a row whose scientific name is exactly the binomial.
    master = csv.DictReader(io.StringIO(github_raw["constraintMaster.csv"].decode("utf-8", errors="replace")))
    for row in master:
        for value in row.values():
            if value and binomial_of(value.strip()):
                name_presence["constraintMaster exact-binomial rows"] += 1

    status, wolf_raw, wolf_final = fetch(WOLF_URL)
    (DATA / "grey-wolf.html").write_bytes(wolf_raw)
    files["grey-wolf.html"] = file_record(WOLF_URL, wolf_raw, wolf_final, retrieved)
    files["grey-wolf.html"]["http_status"] = status
    wolf = wolf_labels(wolf_raw)
    if wolf["count"] is not None:
        observations.append({
            "species": "Canis lupus",
            "count": wolf["count"],
            "source": "imnh-grey-wolf-r884-cervicals",
            "detail": wolf["labels"],
        })

    status, lion_html, lion_final = fetch(LION_DOI)
    (DATA / "lion-landing.html").write_bytes(lion_html)
    files["lion-landing.html"] = file_record(LION_DOI, lion_html, lion_final, retrieved)
    files["lion-landing.html"]["http_status"] = status
    landing = lion_html.decode("utf-8", errors="replace")
    title_match = re.search(r"<title>(.*?)</title>", landing, re.S | re.I)
    title = plain(title_match.group(1)) if title_match else ""
    pdf_url = LION_PDF if LION_PDF in landing else None
    lion = {"admissible": False, "count": None, "snippet": None, "title": title, "pdf_url": pdf_url}
    deviations = [{
        "what": "The lion cervical count was read from the PDF linked on the DOI landing page, not from the HTML itself.",
        "why": "The DOI resolves to an HTML page whose title is the lion paper, but that HTML does not contain a cervical row. The PDF linked from the page is the article. pypdf extracts the text. The PDF is about 1.1 MB and is not committed.",
    }]
    if pdf_url and re.search(r"panthera leo|\blion\b", title, re.I):
        status, pdf, pdf_final = fetch(pdf_url)
        (DATA / "lion.pdf").write_bytes(pdf)
        files["lion.pdf"] = file_record(pdf_url, pdf, pdf_final, retrieved)
        files["lion.pdf"]["http_status"] = status
        lion.update(lion_pdf_count(pdf))
        if lion["count"] is not None:
            observations.append({
                "species": "Panthera leo",
                "count": lion["count"],
                "source": "onwuama-lion-axial-skeleton-2021",
                "detail": lion["snippet"],
            })

    by_species = {"Canis lupus": [], "Panthera leo": []}
    for obs in observations:
        by_species[obs["species"]].append(obs["count"])
    species_consensus = {name: consensus(counts) for name, counts in by_species.items()}
    many = [name for name, kind in species_consensus.items() if kind == "many"]
    conflict = [name for name, kind in species_consensus.items() if kind == "conflict"]
    missing = [name for name, kind in species_consensus.items() if kind == "missing"]
    if not observations:
        verdict, reason = "inconclusive", "data-unavailable"
    elif many:
        verdict, reason = "refutes", None
    elif conflict:
        verdict, reason = "mixed", None
    elif not missing and all(species_consensus[name] == "one" for name in by_species) and others["other_species_cervical_ge_2"] >= 1:
        verdict, reason = "supports", None
    elif missing:
        verdict, reason = "inconclusive", "underpowered"
    else:
        verdict, reason = "inconclusive", "underpowered"

    counts_used = [obs["count"] for obs in observations]
    if verdict == "refutes" and counts_used and min(counts_used) >= 2 and len(many) == 2:
        confidence = 0.8
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "mixed":
        confidence = 0.45
    elif verdict == "supports":
        confidence = 0.7
    else:
        confidence = 0.3

    measured = {
        "value": min(counts_used) if counts_used else None,
        "unit": "cervical elements; the smaller species count among the sources that entered the verdict",
        "n": len(observations),
        "uncertainty": "the wolf figure is a count of separately titled elements on one specimen page, not a stated total; the lion figures are published counts",
        "extra": {
            "species_consensus": species_consensus,
            "observations": observations,
            "wolf_page": wolf,
            "lion_paper": {k: v for k, v in lion.items() if k != "pages"} | {"pdf_pages": lion.get("pages")},
            "name_presence": name_presence,
            "other_species_in_vertebral_formula_table": others,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "deviations": deviations}, indent=2) + "\n")

    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if observations else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["measured"] = measured
    result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "vertebral-pattern-cerbus-2024",
            "name": "Vertebral formula tables (Cerbus, Hiratani and Kawaguchi), GitHub dbkk/vertebral_pattern",
            "landing_url": "https://github.com/dbkk/vertebral_pattern",
            "doi": "10.1073/pnas.2411421121",
            "version": COMMIT,
            "license": "Data deposited with the paper in the public GitHub repository; no separate license file was retrieved",
            "files": [
                {"name": name, **{k: v for k, v in files[name].items() if k != "http_status"}}
                for name in GITHUB_FILES
            ],
            "role": "species-level cervical counts; a row counts only when its species cell is exactly Canis lupus or Panthera leo",
        },
        {
            "id": "imnh-grey-wolf-r884-cervicals",
            "name": "Idaho Museum of Natural History virtual osteology, grey wolf",
            "landing_url": WOLF_URL,
            "doi": None,
            "version": "page retrieved " + retrieved,
            "license": "Idaho Museum of Natural History virtual specimen page; no Creative Commons mark was read off the page",
            "files": [{**{k: v for k, v in files["grey-wolf.html"].items() if k != "http_status"}}],
            "role": "separately titled cervical elements of one Canis lupus specimen",
        },
        {
            "id": "onwuama-lion-axial-skeleton-2021",
            "name": "Onwuama, Jaji, Salami and Kigir 2021, axial skeleton of the African lion",
            "landing_url": LION_DOI,
            "doi": "10.22271/veterinary.2021.v6.i2a.328",
            "version": "2021; 6(2): 09-14",
            "license": "Copyright 2021, the journal (VET), as printed on the PDF",
            "files": [
                {**{k: v for k, v in files["lion-landing.html"].items() if k != "http_status"}},
                *([{**{k: v for k, v in files["lion.pdf"].items() if k != "http_status"}}] if "lion.pdf" in files else []),
            ],
            "role": "published cervical-vertebra count for Panthera leo",
        },
    ]
    result["method"] = (
        "Downloaded the three pre-registered vertebral-pattern files at the pinned commit and kept a cervical count "
        "only from a row whose species cell is exactly Canis lupus or Panthera leo. constraintMaster.csv is a tree-node "
        "table and has no such row, so it contributes no count. Counted distinct 'Cervical Vertebra' headings on the "
        "Idaho grey-wolf page after checking that the page names Canis lupus. Read the lion count from the PDF linked "
        "on the DOI landing page, whose title names the lion, using the first 'Cervical vertebra' row integer."
    )
    lines = [f"{obs['species']}: {obs['count']} ({obs['source']})" for obs in observations]
    lines.append("Consensus: " + ", ".join(f"{name}={kind}" for name, kind in species_consensus.items()))
    result["results_summary"] = lines
    caveats = list(result.get("caveats") or [])
    for caveat in [
        "The wolf page titles four cervical elements (the first, the second, the third, and the last) and does not print a complete cervical formula. Four separately titled elements are already more than one bone.",
        "The vertebral-formula table has no Canis lupus row. The wolf count comes only from the museum specimen page.",
        "constraintMaster.csv was downloaded and hashed. Its rows are not one species each, so the pre-registered exact-name rule gives it no count.",
    ]:
        if caveat not in caveats:
            caveats.append(caveat)
    result["caveats"] = caveats
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "consensus": species_consensus, "observations": observations, "others": others}, indent=2))


if __name__ == "__main__":
    main()
