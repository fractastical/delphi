"""Test aristotle-ha07-21 on four open pediatric eruption cohorts.

Requires pdftotext for the Spanish PDF. Run: python3 analysis.py
"""

import json
import re
import statistics
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _fetch

HERE = Path(__file__).resolve().parent
SOURCES = {
    "romanian": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8947037/fullTextXML",
    "jecs": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10670756/fullTextXML",
    "indian": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5661043/fullTextXML",
    "spanish": "https://www.ejpd.eu/wp-content/uploads/pdf/EJPD_2015_4_8.pdf",
}


def local(tag):
    return tag.split("}")[-1]


def xml_meta(xml_bytes):
    root = ET.fromstring(xml_bytes)
    doi, license_text = None, None
    for element in root.iter():
        if local(element.tag) == "article-id" and element.attrib.get("pub-id-type") == "doi" and not doi:
            doi = (element.text or "").strip() or None
        if local(element.tag) == "license" and license_text is None:
            license_text = " ".join("".join(element.itertext()).split())[:300] or None
    return doi, license_text


def table_rows(xml_bytes):
    root = ET.fromstring(xml_bytes)
    tables = []
    for wrap in root.iter():
        if local(wrap.tag) != "table-wrap":
            continue
        caption = ""
        for element in wrap.iter():
            if local(element.tag) == "caption":
                caption = " ".join("".join(element.itertext()).split())
                break
        rows = []
        for tr in wrap.iter():
            if local(tr.tag) != "tr":
                continue
            cells = []
            for cell in list(tr):
                if local(cell.tag) in ("td", "th"):
                    cells.append(" ".join("".join(cell.itertext()).split()))
            if any(cells):
                rows.append(cells)
        tables.append((caption, rows))
    return tables


def mean_of(cell):
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:±|\+/-)", cell)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)", cell)
    return float(match.group(1)) if match else None


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(data)
        handle.flush()
        out = subprocess.run(["pdftotext", "-layout", handle.name, "-"], check=True, capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def classify(label):
    low = label.lower()
    if "molar" in low or re.search(r"\.[45]\b", label) or re.search(r"-[0-9]\.[45]", label):
        # FDI second digit 4 or 5, or the word molar
        if "molar" in low or re.search(r"(?:^|[^0-9])[5-8]\.[45]\b", label) or re.search(r"[5-8]\.[45]", label):
            return "molar"
    if "canine" in low or re.search(r"[5-8]\.3\b", label):
        return "canine"
    if "incisor" in low or re.search(r"[5-8]\.[12]\b", label):
        return "incisor"
    return "other"


def romanian(tables):
    pooled = None
    classes = []
    for caption, rows in tables:
        if "groups of two deciduous teeth" not in caption:
            continue
        for row in rows:
            if not row or not re.match(r"\d\.\d", row[0]):
                continue
            age = mean_of(row[2]) if len(row) > 2 else None
            if age is None:
                continue
            classes.append({"label": row[0], "age": age, "kind": classify(row[0])})
            if row[0].startswith("7.1"):
                pooled = age
    return pooled, classes


def jecs(tables):
    sexes = {}
    classes = []
    for caption, rows in tables:
        if "males and females in chronological ages" not in caption:
            continue
        sex = None
        for row in rows:
            head = row[0].lower() if row else ""
            if head in ("male", "female"):
                sex = head
                continue
            if "mandibular primary central incisor" in head or "maxillary primary central incisor" in head or "lateral incisor" in head:
                age = mean_of(row[2]) if len(row) > 2 else None
                if age is None or sex is None:
                    continue
                kind = "incisor"
                classes.append({"label": f"{sex} {row[0]}", "age": age, "kind": kind})
                if "mandibular primary central incisor" in head:
                    sexes[sex] = age
    if len(sexes) < 2:
        return None, classes
    return (sexes["male"] + sexes["female"]) / 2, classes


def indian(tables):
    classes = []
    pooled = None
    for caption, rows in tables:
        if "Eruption timing of deciduous" not in caption:
            continue
        index = 0
        while index < len(rows):
            label = rows[index][0].strip()
            if label and index + 1 < len(rows):
                months = re.findall(r"\((\d+(?:\.\d+)?)\s*months\)", " ".join(rows[index + 1]))
                if len(months) >= 3:
                    age = float(months[2])
                    kind = classify(label)
                    classes.append({"label": label, "age": age, "kind": kind})
                    if label.lower().startswith("mandibular central"):
                        pooled = age
            index += 1
    return pooled, classes


def spanish(text):
    classes = []
    pooled = None
    for kind, prefix in (("incisor", "Central Incisor"), ("incisor", "Lateral Incisor"), ("canine", "Canine"), ("molar", "1st Molar"), ("molar", "2nd Molar")):
        match = re.search(rf"{prefix}\s+((?:\d+(?:\.\d+)?\s+){{9}}\d+(?:\.\d+)?)", text)
        if not match:
            continue
        numbers = [float(item) for item in match.group(1).split()]
        mandible = (numbers[5] + numbers[7]) / 2
        maxilla = (numbers[0] + numbers[2]) / 2
        classes.append({"label": f"maxillary {prefix}", "age": maxilla, "kind": kind})
        classes.append({"label": f"mandibular {prefix}", "age": mandible, "kind": kind})
        if prefix == "Central Incisor":
            pooled = mandible
    return pooled, classes


def order_status(classes):
    if not classes:
        return "unscored"
    earliest = min(classes, key=lambda item: item["age"])
    molars = [item for item in classes if item["kind"] == "molar"]
    incisors = [item for item in classes if item["kind"] == "incisor"]
    if earliest["kind"] in ("molar", "canine"):
        return "refute"
    if not molars or not incisors:
        return "incisor_but_no_molar"
    if min(item["age"] for item in molars) > min(item["age"] for item in incisors):
        return "pass"
    return "refute"


def main():
    fetched = {key: _fetch.fetch(url) for key, url in SOURCES.items()}
    meta = {key: xml_meta(fetched[key]["data"]) for key in ("romanian", "jecs", "indian")}
    romanian_age, romanian_classes = romanian(table_rows(fetched["romanian"]["data"]))
    jecs_age, jecs_classes = jecs(table_rows(fetched["jecs"]["data"]))
    indian_age, indian_classes = indian(table_rows(fetched["indian"]["data"]))
    spanish_age, spanish_classes = spanish(pdf_text(fetched["spanish"]["data"]))
    studies = {
        "romanian": {"age": romanian_age, "order": order_status(romanian_classes), "classes": romanian_classes},
        "jecs": {"age": jecs_age, "order": order_status(jecs_classes), "classes": jecs_classes},
        "indian": {"age": indian_age, "order": order_status(indian_classes), "classes": indian_classes},
        "spanish": {"age": spanish_age, "order": order_status(spanish_classes), "classes": spanish_classes},
    }
    present = {key: item["age"] for key, item in studies.items() if item["age"] is not None}
    reason = None
    if len(present) < 3:
        verdict, reason, confidence, tee = "inconclusive", "underpowered", 0.4, None
    else:
        tee = sum(present.values()) / len(present)
        order_refute = any(item["order"] == "refute" for item in studies.values())
        order_pass = all(item["order"] == "pass" for item in studies.values())
        split = min(present.values()) < 8 and max(present.values()) >= 8
        if tee < 5 or tee >= 8 or order_refute:
            verdict, confidence = "refutes", 0.80 if tee >= 8 else 0.55
        elif 6 <= tee < 7 and order_pass and not split:
            verdict, confidence = "supports", 0.70
        elif (5 <= tee < 6) or (7 <= tee < 8) or (split and order_pass and not (tee < 5 or tee >= 8)):
            verdict, confidence = "mixed", 0.60
        else:
            verdict, confidence = "mixed", 0.55
    measured = {
        "value": None if tee is None else round(tee, 4),
        "unit": "months, unweighted mean of study-level mandibular central-incisor estimates",
        "n": len(present),
        "uncertainty": None if len(present) < 2 else round(max(present.values()) - min(present.values()), 4),
        "extra": {
            "study_estimates_months": present,
            "order": {key: item["order"] for key, item in studies.items()},
            "alternative_window_6_to_8_also_fails": None if tee is None else not (6 <= tee <= 8),
            "classes": {key: item["classes"] for key, item in studies.items()},
        },
    }
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    assert result["pass_criterion"].startswith("Pre-registered.")
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "Europe PMC full text for the Romanian, Japanese JECS and Indian cohorts, and the Spanish PDF, "
            "were downloaded. Mandibular central-incisor means were taken as pre-registered: the Romanian "
            "pooled pair, the unweighted mean of the JECS male and female means, the Indian common parenthetical "
            "age in months, and the unweighted mean of the Spanish left and right mandibular means. T is their "
            "unweighted mean. Order compares incisor and molar class means inside each cohort. The seventh month "
            "of life is ages 6 up to 7 months; T at or above 8 months refutes."
        ),
        "datasets": [
            {
                "id": "pmc8947037-romanian-primary-eruption",
                "name": "Ogodescu et al., eruption timing in Romanian children",
                "landing_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8947037/",
                "doi": meta["romanian"][0],
                "version": "PMC8947037",
                "license": meta["romanian"][1],
                "files": [{k: fetched["romanian"][k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
                "role": "mean eruption age by primary tooth",
            },
            {
                "id": "pmc10670756-jecs-parent-reported-eruption",
                "name": "Japan Environment and Children's Study, parent-reported primary eruption",
                "landing_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10670756/",
                "doi": meta["jecs"][0],
                "version": "PMC10670756",
                "license": meta["jecs"][1],
                "files": [{k: fetched["jecs"][k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
                "role": "sex-specific mean ages of the primary incisors",
            },
            {
                "id": "pmc5661043-indian-eruption-chronology",
                "name": "Indian cross-sectional eruption chronology",
                "landing_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5661043/",
                "doi": meta["indian"][0],
                "version": "PMC5661043",
                "license": meta["indian"][1],
                "files": [{k: fetched["indian"][k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
                "role": "common eruption age in months by tooth class",
            },
            {
                "id": "ejpd-2015-spanish-primary-eruption",
                "name": "Spanish primary-tooth eruption chronology",
                "landing_url": "https://www.ejpd.eu/wp-content/uploads/pdf/EJPD_2015_4_8.pdf",
                "doi": None,
                "version": "European Journal of Paediatric Dentistry 2015",
                "license": None,
                "files": [{k: fetched["spanish"][k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
                "role": "left and right mean eruption ages for the primary dentition",
            },
        ],
        "measured": measured,
        "caveats": [
            "The seventh month of life was fixed as ages 6 up to 7 months before these tables were parsed. A looser reading, ages 6 to 8 inclusive, is reported and does not decide the verdict.",
            "The Japanese table does not report molars, so eruption order can be scored only in the cohorts that list molars.",
            "The milk-temperature clause was pre-registered as untested. Study means also cannot show that some children erupt an upper tooth first.",
            "Parent-reported ages and clinic examinations are pooled with equal weight per cohort, not per child.",
            "Licence text is whatever the PMC XML license element contained. No licence line was extracted from the Spanish PDF.",
        ],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(verdict, confidence, present, {k: v["order"] for k, v in studies.items()})


if __name__ == "__main__":
    main()
