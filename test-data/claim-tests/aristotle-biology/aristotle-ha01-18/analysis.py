#!/usr/bin/env python3
"""Test aristotle-ha01-18 against published alligator feeding kinematics."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
DERIVED = ROOT / "derived"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
UA = "delphi-claim-test/aristotle-ha01-18 (research)"
FROZEN = [
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "claim_id",
    "claim_iri",
    "project",
    "agent",
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local(tag: str) -> str:
    return tag.split("}")[-1]


def text_of(node) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def finish(payload):
    data = json.loads(RESULT.read_text())
    snapshot = {k: data[k] for k in FROZEN}
    data.update(payload)
    for key, value in snapshot.items():
        if data[key] != value:
            raise SystemExit(f"frozen field changed: {key}")
    RESULT.write_text(json.dumps(data, indent=2) + "\n")


def table_matrix(table):
    caption = ""
    matrix = []
    for node in table.iter():
        if local(node.tag) == "caption" and not caption:
            caption = text_of(node)
        if local(node.tag) == "tr":
            cells = []
            for cell in list(node):
                if local(cell.tag) in {"td", "th"}:
                    cells.append(text_of(cell))
            if any(cells):
                matrix.append(cells)
    return caption, matrix


def kind_of_raw_angle(label: str):
    """Return lower_jaw or cranial only for an untransformed angular excursion."""
    low = label.lower()
    if re.search(r"(?i)\blog\b|velocity|speed|slope|scaling", low):
        return None
    if "lower jaw" in low and "displac" in low:
        return "lower_jaw"
    if "cranial" in low and "rotat" in low and "lower jaw" not in low:
        return "cranial"
    return None


def is_logged_degree_angle(label: str) -> bool:
    low = label.lower()
    if not re.search(r"\blog\b", low):
        return False
    if re.search(r"velocity|speed", low):
        return False
    degree = bool(re.search(r"degree|°", low))
    jaw = "lower jaw" in low and "displac" in low
    cranial = "cranial" in low and "rotat" in low and "lower jaw" not in low
    return degree and (jaw or cranial)


def mean_pm(cell: str):
    """A reported mean is a number written with a ± uncertainty, not a unit exponent or a slope."""
    cleaned = cell.replace("−", "-").replace("–", "-")
    if re.search(r"(?i)slope|\blog\b", cleaned):
        return None
    if re.search(r"(?i)(?:s-1|/s|·s)", cleaned) and "±" not in cleaned and "+/-" not in cleaned:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:±|\+/-)", cleaned)
    if not match:
        return None
    return float(match.group(1))


def extract_measurements(root):
    """Raw degree means only. Log averages, slopes and velocities are recorded as ignored labels."""
    used = []
    ignored_log_labels = []
    for table in root.iter():
        if local(table.tag) not in {"table-wrap", "table"}:
            continue
        caption, matrix = table_matrix(table)
        if not matrix:
            continue
        header_index = None
        for i, row in enumerate(matrix[:4]):
            joined = " ".join(row).lower()
            if re.search(r"average|mean", joined) and "slope" in joined:
                header_index = i
                break
            if re.search(r"\baverage\b|\bmean\b", joined):
                header_index = i
                break
        headers = matrix[header_index] if header_index is not None else []
        mean_cols = [
            i
            for i, header in enumerate(headers)
            if re.search(r"(?i)average|\bmean\b", header) and not re.search(r"(?i)slope", header)
        ]
        pending = ""
        start = header_index + 1 if header_index is not None else 0
        for row in matrix[start:]:
            label = (row[0] if row else "").strip()
            rest = " ".join(row[1:]).strip()
            if pending:
                label = f"{pending} {label}".strip()
                pending = ""
            if label and not rest and re.search(r"(?i)lower jaw|cranial", label):
                pending = label
                continue
            blob = f"{label} {rest}"
            if is_logged_degree_angle(blob):
                ignored_log_labels.append(re.sub(r"\s+", " ", label)[:160])
                continue
            kind = kind_of_raw_angle(label)
            if not kind or not re.search(r"(?i)degree|°", blob):
                continue
            values = []
            for idx in mean_cols:
                if idx < len(row):
                    value = mean_pm(row[idx])
                    if value is not None:
                        values.append(value)
            if not values:
                continue
            used.append(
                {
                    "kind": kind,
                    "group": label[:120],
                    "mean_degrees": values[0],
                    "source": label[:160],
                    "caption": caption[:180],
                }
            )
    return used, ignored_log_labels


def extract_prose(root):
    """A prose mean counts only when it is written in degrees, not as a log, slope or velocity."""
    found = []
    for node in root.iter():
        if local(node.tag) not in {"p"}:
            continue
        sentence_blob = text_of(node)
        for kind, pattern in (
            ("lower_jaw", r"lower jaw displacement"),
            ("cranial", r"cranial rotation"),
        ):
            for match in re.finditer(pattern, sentence_blob, flags=re.I):
                window = sentence_blob[max(0, match.start() - 40) : match.end() + 140]
                if re.search(r"(?i)\blog\b|slope|scaling|velocity| per ", window):
                    continue
                if not re.search(r"(?i)\b(mean|average)\b", window):
                    continue
                num = re.search(r"(\d+(?:\.\d+)?)\s*(?:°|degrees)\b", window, flags=re.I)
                if num:
                    found.append(
                        {
                            "kind": kind,
                            "group": "prose",
                            "mean_degrees": float(num.group(1)),
                            "source": window[:160],
                            "caption": "",
                        }
                    )
    return found


def individual_count(root) -> int | None:
    text = text_of(root)
    match = re.search(r"(\d+)\s+individuals were randomly sampled", text, flags=re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"randomly sampled[^.]{0,80}?(\d+)\s+individuals", text, flags=re.I)
    if match:
        return int(match.group(1))
    return None


def main():
    DERIVED.mkdir(exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    retrieved = now()
    content = None
    url = None
    for pmc_id in ("4280508", "PMC4280508"):
        r = sess.get(EFETCH, params={"db": "pmc", "id": pmc_id, "retmode": "xml"}, timeout=90)
        if r.ok and b"article" in r.content[:2000].lower() or (r.ok and b"<" in r.content[:20]):
            if r.ok and (b"Alligator" in r.content or b"alligator" in r.content):
                content = r.content
                url = r.url
                break
    if content is None:
        finish(
            {
                "status": "complete",
                "data_kind": "none",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.35,
                "measured": {"value": None, "unit": "degrees of lower-jaw displacement", "n": 0, "uncertainty": None, "extra": {}},
                "datasets": [],
                "method": "PMC efetch did not return the alligator feeding paper.",
                "caveats": ["No kinematic numbers were measured."],
            }
        )
        return

    root = ET.fromstring(content)
    doi = None
    title = ""
    license_text = ""
    for node in root.iter():
        if local(node.tag) == "article-title" and not title:
            title = text_of(node)
        if local(node.tag) == "article-id" and node.attrib.get("pub-id-type") == "doi":
            doi = (node.text or "").strip()
        if local(node.tag) == "license-p" and not license_text:
            license_text = text_of(node)[:240]

    measurements, ignored_log_labels = extract_measurements(root)
    ignored_log_labels = list(dict.fromkeys(ignored_log_labels))
    if not measurements:
        measurements = extract_prose(root)
    # De-duplicate identical kind/group/value pairs.
    unique = []
    seen = set()
    for item in measurements:
        key = (item["kind"], item["group"], item["mean_degrees"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    lower = [item["mean_degrees"] for item in unique if item["kind"] == "lower_jaw"]
    cranial = [item["mean_degrees"] for item in unique if item["kind"] == "cranial"]
    n_individuals = individual_count(root)

    lines = ["kind,group,mean_degrees,source"]
    for item in unique:
        source = item["source"].replace('"', "'")
        group = item["group"].replace('"', "'")
        lines.append(f"{item['kind']},\"{group}\",{item['mean_degrees']},\"{source}\"")
    (DERIVED / "kinematics.csv").write_text("\n".join(lines) + "\n")

    # Precedence from the frozen fail rule: unavailable, not-operationalizable, or underpowered
    # before a directional verdict. Log-only publication is not-operationalizable, not a lack of data.
    if not lower and not cranial and ignored_log_labels:
        verdict, reason = "inconclusive", "not-operationalizable"
    elif not lower and not cranial:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n_individuals is not None and n_individuals < 5:
        verdict, reason = "inconclusive", "underpowered"
    elif any(value > 10 for value in lower):
        verdict, reason = "refutes", None
    elif lower and cranial and all(value <= 5 for value in lower) and all(value >= 10 for value in cranial):
        verdict, reason = "supports", None
    elif lower or cranial:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "not-operationalizable"

    if verdict == "refutes" and n_individuals and n_individuals >= 20:
        confidence = 0.76
    elif verdict == "refutes":
        confidence = 0.68
    elif verdict == "supports":
        confidence = 0.6
    elif verdict == "mixed":
        confidence = 0.55
    else:
        confidence = 0.35

    max_lower = max(lower) if lower else None
    measured = {
        "value": max_lower,
        "unit": "degrees, largest reported mean lower-jaw displacement",
        "n": n_individuals if n_individuals is not None else len(lower),
        "uncertainty": None,
        "extra": {
            "lower_jaw_means_degrees": lower,
            "cranial_rotation_means_degrees": cranial,
            "n_individuals": n_individuals,
            "n_lower_jaw_means": len(lower),
            "n_cranial_means": len(cranial),
            "ignored_log_degree_labels": ignored_log_labels,
            "rule_based_verdict": verdict,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    digest = hashlib.sha256(content).hexdigest()
    finish(
        {
            "status": "complete",
            "data_kind": "biological" if (lower or cranial) else "none",
            "verdict": verdict,
            "confidence": confidence,
            **({"reason": reason} if reason else {}),
            "measured": measured,
            "datasets": [
                {
                    "id": "pmc4280508-alligator-feeding-kinematics",
                    "name": title or "Alligator mississippiensis feeding kinematics",
                    "landing_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4280508/",
                    "doi": doi,
                    "version": None,
                    "license": license_text or None,
                    "files": [
                        {
                            "download_url": url,
                            "retrieved_at": retrieved,
                            "byte_size": len(content),
                            "sha256": digest,
                            "note": "PMC JATS XML via efetch",
                        }
                    ],
                    "role": "lower-jaw displacement and cranial rotation during feeding",
                }
            ],
            "method": (
                "Downloaded the JATS XML of PMC4280508. A degree mean was kept only when the variable name is "
                "lower-jaw displacement or cranial rotation, the cell is an average written with a ± uncertainty, "
                "and the name is not a log, a slope, or a velocity. "
                f"Found {len(lower)} raw lower-jaw means and {len(cranial)} raw cranial-rotation means. "
                f"Ignored {len(ignored_log_labels)} log-transformed degree rows. "
                "The individual count is the number in the sentence that says individuals were randomly sampled."
            ),
            "caveats": [
                "The animals are American alligators, not the Nile crocodile named in the claim. The measurement is a proxy for the crocodilian jaw joint.",
                "Cranial rotation is rotation of the head relative to the body. It is not a joint inside the upper jaw.",
                "Log-transformed averages and slopes were not converted back into degrees and were not compared with the 5-degree and 10-degree cuts.",
                "A unit such as degree s−1 is a velocity. The exponent was not read as an angle.",
                "Published group means are used. The raw trial table is not in the XML if the authors did not include it.",
            ],
        }
    )
    print(json.dumps({"verdict": verdict, "lower": lower, "cranial": cranial, "n": n_individuals, "doi": doi}, indent=2))


if __name__ == "__main__":
    main()
