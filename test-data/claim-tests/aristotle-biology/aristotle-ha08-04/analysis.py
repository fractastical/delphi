#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-ha08-04.

Thresholds are the ones in result.json. This script does not edit
pass_criterion, fail_criterion, hypothesis, planned_datasets,
test_contract, or interpretation.

Downloads stay in /tmp and are not written into the repository.
Requires python3 packages: requests, pandas, openpyxl.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "result.json"
DERIVED = ROOT / "derived"
CACHE = Path("/tmp/delphi-claim-tests/aristotle-ha08-04")

UA = {"User-Agent": "delphi-claim-test/aristotle-ha08-04 (scientific reproducibility; python-requests)"}

AMPHIBIO_URL = "https://ndownloader.figshare.com/files/8828578"
AMPHIBIO_MD5 = "3d2c8f3371516209f190fc842f26e32b"
REPT_URL = "https://ndownloader.figshare.com/files/45408133"
REPT_MD5 = "a00be695740e752db2654537bbb0814c"
PHYL_COMMIT = "f4ec385d302cacafe3a591f12f02df2585706119"
PHYL_BLOB = "69431490dddb3f9f54fa6e64603858b591162f7b"
PHYL_URL = (
    "https://raw.githubusercontent.com/MegaPast2Future/PHYLACINE_1.2/"
    f"{PHYL_COMMIT}/Data/Traits/Trait_data.csv"
)

MARINE_GENERA = {
    "chelonia",
    "caretta",
    "eretmochelys",
    "lepidochelys",
    "natator",
    "dermochelys",
}
WATER_HABITAT_RE = re.compile(
    r"ocean|marine|wetland|swamp|mangrove|river|lake|fresh\s*water|"
    r"aquatic|marsh|stream|estuar|pond|bog|riparian|coast",
    re.I,
)
# Aquatic and marine were added after the first run. See deviations in result.json.
MICRO_WATER_RE = re.compile(r"\b(?:semi-?\s*aquatic|aquatic|marine)\b", re.I)

HEDGE_RE = re.compile(
    r"\b(few|some|exception|exceptions|rarely|occasionally|a handful|"
    r"one species|two species|a single species|only one|only two|only a few)\b",
    re.I,
)
NEG_RE = re.compile(r"\b(no|not|without|lack|lacks|lacking|never)\b", re.I)

PASS_A = [
    re.compile(p, re.I)
    for p in (
        r"\blungs?\b",
        r"\bbreathe[sd]?\s+air\b",
        r"\bbreathing\s+air\b",
        r"\bsurfac(?:e|es|ing)\s+to\s+breathe\b",
        r"\bmust\s+surface\b",
        r"\bcome[s]?\s+to\s+the\s+surface\s+to\s+breathe\b",
    )
]
FAIL_A = [
    re.compile(p, re.I)
    for p in (
        r"\blungless\b",
        r"\bno\s+lungs?\b",
        r"\bwithout\s+lungs?\b",
        r"\black(?:s|ing)?\s+lungs?\b",
        r"\bgills\s+instead\s+of\s+lungs\b",
        r"\bdoes\s+not\s+surface\b",
        r"\bnever\s+surfaces\b",
        r"\bdo\s+not\s+need\s+to\s+surface\b",
        r"\bdoes\s+not\s+need\s+to\s+breathe\s+air\b",
        r"\bcan\s*not\s+breathe\s+air\b",
        r"\bunable\s+to\s+breathe\s+air\b",
    )
]
PASS_B = [
    re.compile(p, re.I)
    for p in (
        r"\bnest(?:s|ing|ed)?\b.{0,80}\b(land|beach|shore|sand|bank|soil|ground)\b",
        r"\b(land|beach|shore|sand|bank)\b.{0,80}\bnest(?:s|ing|ed)?\b",
        r"\blay(?:s|ing)?\s+(?:their\s+|the\s+)?eggs?\b.{0,80}\b(land|beach|shore|sand|bank|soil|ground)\b",
        r"\beggs?\b.{0,50}\b(on\s+land|on\s+the\s+beach|on\s+beaches|on\s+shore|in\s+the\s+sand|on\s+the\s+sand)\b",
        r"\bgive[s]?\s+birth\b.{0,80}\b(land|beach|shore|ice|haul-?out|haul)\b",
        r"\bborn\b.{0,40}\b(on\s+land|on\s+the\s+beach|on\s+ice|ashore)\b",
        r"\bpup(?:s|ping)?\b.{0,80}\b(land|beach|shore|ice|cave|haul-?out)\b",
        r"\bterrestrial\s+nest",
        r"\bnesting\s+beach",
    )
]
FAIL_B = [
    re.compile(p, re.I)
    for p in (
        r"\bgive[s]?\s+birth\b.{0,80}\b(under\s*water|underwater|in\s+the\s+water|in\s+water)\b",
        r"\bborn\s+under\s*water\b",
        r"\bborn\s+underwater\b",
        r"\bbirths?\s+(?:take\s+place\s+|occur\s+|are\s+)?(?:in\s+the\s+water|underwater|under\s+water)\b",
        r"\beggs?\b.{0,50}\b(in\s+water|into\s+the\s+water|into\s+water|in\s+the\s+water|underwater|under\s+water)\b",
        r"\blay(?:s|ing)?\s+(?:their\s+|the\s+)?eggs?\b.{0,60}\b(in\s+water|in\s+the\s+water|underwater|under\s+water)\b",
    )
]
FAIL_B_FROG_ONLY = [
    re.compile(p, re.I)
    for p in (
        r"\baquatic\s+larvae\b",
        r"\btadpoles?\b",
        r"\blarval\s+stage\b",
    )
]

WIKI_PAGES = {
    "sea_turtle": ["Sea turtle"],
    "crocodile": ["Crocodile", "Crocodilia"],
    "hippopotamus": ["Hippopotamus"],
    "seal": ["Mediterranean monk seal", "Earless seal"],
    "freshwater_tortoise": ["Freshwater turtle", "Emys orbicularis"],
    "frog": ["Frog"],
}

BAD_HEAD = (
    "reference",
    "see also",
    "external link",
    "bibliograph",
    "gallery",
    "further reading",
    "etymolog",
    "taxonomy",
    "classification",
    "evolution",
    "fossil",
    "mytholog",
    "in culture",
    "cultural",
    "as food",
    "as pet",
    "conservation status",
    "relationship with human",
)
GOOD_HEAD = (
    "biolog",
    "description",
    "characteristic",
    "anatom",
    "morpholog",
    "physiolog",
    "respir",
    "breath",
    "reproduct",
    "breed",
    "nest",
    "life cycle",
    "behaviour",
    "behavior",
    "ecolog",
    "habitat",
    "diet",
    "feeding",
    "appearance",
    "development",
    "range",
    "distribution",
    "natural history",
    "life history",
    "locomotion",
    "adaptation",
    "physical",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def fetch(url: str, dest: Path, expect_md5: str | None = None, expect_blob: str | None = None) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    retrieved = utc_now()
    if dest.exists():
        data = dest.read_bytes()
        if (expect_md5 is None or md5(data) == expect_md5) and (
            expect_blob is None or git_blob_sha1(data) == expect_blob
        ):
            retrieved = datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        else:
            data = b""
    else:
        data = b""
    if not data:
        last = None
        for attempt in range(4):
            try:
                response = requests.get(url, headers=UA, timeout=180, allow_redirects=True)
                response.raise_for_status()
                data = response.content
                dest.write_bytes(data)
                retrieved = utc_now()
                break
            except requests.RequestException as exc:
                last = exc
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"download failed for {url}: {last}")
    meta = {
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(data),
        "sha256": sha256(data),
        "md5": md5(data),
        "path_cached": str(dest),
    }
    if expect_md5 is not None:
        meta["md5_expected"] = expect_md5
        meta["md5_ok"] = meta["md5"] == expect_md5
    if expect_blob is not None:
        meta["git_blob_sha1"] = git_blob_sha1(data)
        meta["git_blob_expected"] = expect_blob
        meta["git_blob_ok"] = meta["git_blob_sha1"] == expect_blob
    return meta


def present_code(value) -> str:
    """Return present, absent, or missing. Accepts the codes named in result.json."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "missing"
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "na", "n/a", "none", "null", "nan", "-999"}:
            return "missing"
        if text in {"1", "yes", "y", "true", "present"}:
            return "present"
        if text in {"0", "no", "n", "false", "absent"}:
            return "absent"
        return "missing"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "missing"
    if pd.isna(number):
        return "missing"
    if number == 1:
        return "present"
    if number == 0:
        return "absent"
    if number == -999:
        return "missing"
    return "missing"


def band(proportion: float, n: int, minimum_n: int, pass_at: float, fail_below: float) -> str:
    if n < minimum_n:
        return "unscored"
    if proportion >= pass_at:
        return "pass"
    if proportion < fail_below:
        return "fail"
    return "mixed"


def norm_binomial(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).replace("_", " ")).strip().lower()


def find_col(columns, predicate):
    for column in columns:
        if predicate(str(column).strip().lower()):
            return column
    return None


def load_amphibio(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.endswith("AmphiBIO_v1.csv") and "reference" not in name.lower()
        ]
        if not names:
            raise RuntimeError(f"AmphiBIO csv missing in {archive.namelist()}")
        raw = archive.read(names[0])
    return pd.read_csv(io.BytesIO(raw), encoding="cp1252", low_memory=False)


def header_row(frame: pd.DataFrame) -> int:
    for index in range(min(15, len(frame))):
        cells = [str(cell).strip().lower() for cell in frame.iloc[index].tolist()]
        if any("microhabitat" in cell for cell in cells):
            return index
    raise RuntimeError("ReptTraits sheet has no microhabitat header in the first 15 rows")


def load_repttraits(path: Path) -> pd.DataFrame:
    book = pd.ExcelFile(path, engine="openpyxl")
    chosen = None
    chosen_header = None
    chosen_rows = -1
    for sheet in book.sheet_names:
        preview = book.parse(sheet, header=None, nrows=15)
        try:
            row = header_row(preview)
        except RuntimeError:
            continue
        full = book.parse(sheet, header=row)
        if len(full) > chosen_rows:
            chosen = full
            chosen_header = row
            chosen_rows = len(full)
    if chosen is None:
        raise RuntimeError(f"no ReptTraits trait sheet in {book.sheet_names}")
    chosen.attrs["header_row"] = chosen_header
    chosen.attrs["n_rows"] = chosen_rows
    return chosen


def reptile_water(row, micro_col, habitat_col) -> str:
    micro = row[micro_col] if micro_col is not None else None
    if not (micro is None or (isinstance(micro, float) and pd.isna(micro)) or str(micro).strip().lower() in {"", "na", "nan"}):
        return "present" if MICRO_WATER_RE.search(str(micro)) else "absent"
    if habitat_col is None:
        return "missing"
    habitat = row[habitat_col]
    if habitat is None or (isinstance(habitat, float) and pd.isna(habitat)) or str(habitat).strip().lower() in {"", "na", "nan"}:
        return "missing"
    return "present" if WATER_HABITAT_RE.search(str(habitat)) else "absent"


def section_included(title: str) -> bool:
    text = title.strip().lower()
    if text in {"", "lead"}:
        return True
    if "natural history" in text or "life history" in text:
        return True
    if any(bad in text for bad in BAD_HEAD):
        return False
    return any(good in text for good in GOOD_HEAD)


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section = "LEAD"
        self.include = True
        self.skip_depth = 0
        self.in_heading = None
        self.heading_buf: list[str] = []
        self.chunks: list[tuple[str, str]] = []
        self.buf: list[str] = []

    def _flush(self):
        if self.include and self.buf:
            self.chunks.append((self.section, "".join(self.buf)))
        self.buf = []

    def handle_starttag(self, tag, attrs):
        classes = " ".join(value for key, value in attrs if key == "class")
        if tag in {"script", "style", "sup"} or "reference" in classes or "mw-editsection" in classes:
            self.skip_depth += 1
            return
        if tag in {"h2", "h3"} and self.skip_depth == 0:
            self._flush()
            self.in_heading = tag
            self.heading_buf = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "sup"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == self.in_heading and self.skip_depth == 0:
            title = re.sub(r"\bedit\b", "", " ".join(self.heading_buf), flags=re.I)
            title = re.sub(r"\s+", " ", title).strip()
            if tag == "h2" or not self.include:
                self.section = title or self.section
                self.include = section_included(self.section)
            else:
                self.section = f"{self.section} / {title}" if self.include else title
                if section_included(title):
                    self.include = True
            self.in_heading = None
            self.heading_buf = []

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_heading:
            self.heading_buf.append(data)
            return
        if self.include:
            self.buf.append(data)

    def text(self) -> str:
        self._flush()
        return "\n".join(chunk for _, chunk in self.chunks)


def sentences_of(html: str) -> list[str]:
    parser = ArticleParser()
    parser.feed(html)
    text = parser.text()
    text = re.sub(r"\[\d+\]", " ", text)
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if len(part.strip()) > 40]


def negated(sentence: str, match: re.Match) -> bool:
    window = sentence[max(0, match.start() - 48) : match.start()]
    words = re.findall(r"[A-Za-z']+", window)
    return bool(NEG_RE.search(" ".join(words[-6:])))


def clause_from_sentences(sentences: list[str], frog: bool) -> dict:
    pass_a, fail_a, pass_b, fail_b = [], [], [], []
    for sentence in sentences:
        hedged = bool(HEDGE_RE.search(sentence))
        for pattern in PASS_A:
            match = pattern.search(sentence)
            if match and not negated(sentence, match):
                pass_a.append(sentence)
                break
        for pattern in FAIL_A:
            match = pattern.search(sentence)
            if match and not hedged and not negated(sentence, match):
                fail_a.append(sentence)
                break
        for pattern in PASS_B:
            match = pattern.search(sentence)
            if match and not negated(sentence, match):
                pass_b.append(sentence)
                break
        fail_patterns = FAIL_B + (FAIL_B_FROG_ONLY if frog else [])
        for pattern in fail_patterns:
            match = pattern.search(sentence)
            if match and not hedged and not negated(sentence, match):
                fail_b.append(sentence)
                break

    def decide(passes, fails):
        if passes and not fails:
            return "pass"
        if fails and not passes:
            return "fail"
        if passes and fails:
            return "mixed"
        return "unscored"

    def samples(rows):
        out = []
        for row in rows[:4]:
            out.append(row[:300])
        return out

    return {
        "A": decide(pass_a, fail_a),
        "B": decide(pass_b, fail_b),
        "evidence": {
            "A_pass": samples(pass_a),
            "A_fail": samples(fail_a),
            "B_pass": samples(pass_b),
            "B_fail": samples(fail_b),
        },
    }


def fetch_wiki(title: str) -> dict:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "parse",
            "page": title,
            "prop": "text|revid",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "disableeditsection": "1",
        },
        headers=UA,
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"wikipedia parse error for {title}: {payload['error']}")
    parse = payload["parse"]
    html = parse["text"]
    if isinstance(html, dict):
        html = html.get("*") or html.get("text") or ""
    raw = response.content
    return {
        "title": parse.get("title", title),
        "revid": parse.get("revid"),
        "html": html,
        "byte_size": len(raw),
        "sha256": sha256(raw),
        "retrieved_at": utc_now(),
        "download_url": response.url,
    }


def combine_text_sources(scored: list[dict]) -> dict:
    """Primary page wins a pass or fail. Later pages fill only unscored or mixed clauses."""
    combined = {"A": "unscored", "B": "unscored", "evidence": {}, "pages": []}
    for item in scored:
        combined["pages"].append(item["title"])
        for clause in ("A", "B"):
            incoming = item[clause]
            current = combined[clause]
            if current in {"unscored", "mixed"} and incoming in {"pass", "fail"}:
                combined[clause] = incoming
            elif current == "unscored" and incoming == "mixed":
                combined[clause] = "mixed"
            elif current in {"pass", "fail"} and incoming in {"pass", "fail"} and current != incoming:
                combined[clause] = "mixed"
        combined["evidence"][item["title"]] = item["evidence"]
    return combined


def proportion_block(n_flag: int, n: int, status: str) -> dict:
    proportion = None if n == 0 else round(n_flag / n, 4)
    return {"n_flag": n_flag, "n": n, "proportion": proportion, "status": status}


def score_reptile_group(frame, mask, minimum_n, pass_at, fail_below, micro_col, habitat_col) -> dict:
    subset = frame.loc[mask]
    flags = [reptile_water(row, micro_col, habitat_col) for _, row in subset.iterrows()]
    coded = [flag for flag in flags if flag != "missing"]
    n_flag = sum(flag == "present" for flag in coded)
    n = len(coded)
    status = band(0 if n == 0 else n_flag / n, n, minimum_n, pass_at, fail_below)
    return proportion_block(n_flag, n, status)


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    result = json.loads(RESULT_PATH.read_text())
    frozen = {
        key: result.get(key)
        for key in (
            "hypothesis",
            "pass_criterion",
            "fail_criterion",
            "planned_datasets",
            "test_contract",
            "interpretation",
        )
    }
    problems = []
    provenance = []

    amphibio_meta = fetch(AMPHIBIO_URL, CACHE / "AmphiBIO_v1.zip", expect_md5=AMPHIBIO_MD5)
    rept_meta = fetch(REPT_URL, CACHE / "ReptTraits-v1-2.xlsx", expect_md5=REPT_MD5)
    phyl_meta = fetch(PHYL_URL, CACHE / "PHYLACINE_Trait_data.csv", expect_blob=PHYL_BLOB)
    for meta, name in (
        (amphibio_meta, "AmphiBIO_v1.zip"),
        (rept_meta, "ReptTraits dataset v1-2.xlsx"),
        (phyl_meta, "Trait_data.csv"),
    ):
        meta["name"] = name
        provenance.append(meta)
    files_ok = amphibio_meta.get("md5_ok") and rept_meta.get("md5_ok") and phyl_meta.get("git_blob_ok")
    if not files_ok:
        problems.append("checksum pin failed")

    amphibio = load_amphibio(CACHE / "AmphiBIO_v1.zip")
    reptiles = load_repttraits(CACHE / "ReptTraits-v1-2.xlsx")
    phyl = pd.read_csv(CACHE / "PHYLACINE_Trait_data.csv", low_memory=False)

    micro_col = find_col(reptiles.columns, lambda name: "microhabitat" in name)
    habitat_col = find_col(
        reptiles.columns,
        lambda name: "habitat" in name and "micro" not in name and "breadth" not in name,
    )
    order_col = find_col(reptiles.columns, lambda name: name == "order")
    family_col = find_col(reptiles.columns, lambda name: name == "family")
    genus_col = find_col(reptiles.columns, lambda name: name == "genus")
    species_col = find_col(reptiles.columns, lambda name: name in {"species", "binomial"})
    repro_col = find_col(reptiles.columns, lambda name: "reproduct" in name)
    if not all([micro_col, order_col, family_col, genus_col]):
        problems.append(
            f"ReptTraits columns missing among {list(reptiles.columns)[:40]}"
        )

    phyl_bin = find_col(phyl.columns, lambda name: "binomial" in name)
    phyl_fam = find_col(phyl.columns, lambda name: name.startswith("family"))
    phyl_mar = find_col(phyl.columns, lambda name: name == "marine")
    phyl_fw = find_col(phyl.columns, lambda name: name == "freshwater")
    phyl_ter = find_col(phyl.columns, lambda name: name == "terrestrial")
    if not all([phyl_bin, phyl_fam, phyl_mar, phyl_fw]):
        problems.append(f"PHYLACINE columns missing among {list(phyl.columns)[:20]}")

    groups: dict[str, dict] = {}

    def genus_series():
        return reptiles[genus_col].astype(str).str.strip().str.lower()

    def order_series():
        return reptiles[order_col].astype(str).str.strip().str.lower()

    def family_series():
        return reptiles[family_col].astype(str).str.strip().str.lower()

    marine_mask = genus_series().isin(MARINE_GENERA) & order_series().str.contains("testudin", na=False)
    sea = score_reptile_group(reptiles, marine_mask, 4, 0.80, 0.50, micro_col, habitat_col)
    groups["sea_turtle"] = {"L": sea["status"], "L_detail": sea, "n_rows": int(marine_mask.sum())}

    fresh_mask = (
        order_series().str.contains("testudin", na=False)
        & ~genus_series().isin(MARINE_GENERA)
        & (family_series() != "testudinidae")
    )
    fresh = score_reptile_group(reptiles, fresh_mask, 30, 0.50, 0.25, micro_col, habitat_col)
    groups["freshwater_tortoise"] = {
        "L": fresh["status"],
        "L_detail": fresh,
        "n_rows": int(fresh_mask.sum()),
    }

    croc_family_mask = family_series().str.contains("crocodylidae", na=False)
    croc_order_mask = order_series().str.contains("crocodil", na=False)
    croc_mask = croc_family_mask
    croc = score_reptile_group(reptiles, croc_mask, 8, 0.80, 0.50, micro_col, habitat_col)
    croc_fallback = False
    if croc["status"] == "unscored" and croc["n"] < 8:
        croc_mask = croc_order_mask
        croc = score_reptile_group(reptiles, croc_mask, 8, 0.80, 0.50, micro_col, habitat_col)
        croc_fallback = True
    groups["crocodile"] = {
        "L": croc["status"],
        "L_detail": croc,
        "n_rows": int(croc_mask.sum()),
        "used_order_fallback": croc_fallback,
    }

    descriptive = {}
    if repro_col is not None:
        for label, mask in (
            ("sea_turtle", marine_mask),
            ("freshwater_tortoise", fresh_mask),
            ("crocodile", croc_mask),
        ):
            modes = reptiles.loc[mask, repro_col].astype(str).str.strip().str.lower()
            modes = modes[~modes.isin({"", "nan", "na", "none"})]
            descriptive[f"reproductive_mode_{label}"] = {
                key: int(value) for key, value in modes.value_counts().head(6).items()
            }
    for label, mask in (
        ("alligatoridae", family_series().str.contains("alligatoridae", na=False)),
        ("gavialidae", family_series().str.contains("gavialidae", na=False)),
    ):
        descriptive[label] = score_reptile_group(reptiles, mask, 1, 0.80, 0.50, micro_col, habitat_col)

    binom = phyl[phyl_bin].map(norm_binomial)
    hip_rows = phyl.loc[binom == "hippopotamus amphibius"]
    if hip_rows.empty:
        hip_status = "unscored"
        hip_detail = {"n": 0, "marine": None, "freshwater": None, "terrestrial": None}
    else:
        row = hip_rows.iloc[0]
        marine = present_code(row[phyl_mar])
        freshwater = present_code(row[phyl_fw])
        terrestrial = present_code(row[phyl_ter]) if phyl_ter else "missing"
        if marine == "present" or freshwater == "present":
            hip_status = "pass"
        elif marine == "absent" and freshwater == "absent":
            hip_status = "fail"
        else:
            hip_status = "unscored"
        hip_detail = {
            "n": int(len(hip_rows)),
            "marine": marine,
            "freshwater": freshwater,
            "terrestrial": terrestrial,
        }
    groups["hippopotamus"] = {"L": hip_status, "L_detail": hip_detail}

    family_names = phyl[phyl_fam].astype(str).str.strip().str.lower()
    phocid = phyl.loc[family_names == "phocidae"]
    phocid_flags = []
    monk_state = "missing_row"
    for _, row in phocid.iterrows():
        marine = present_code(row[phyl_mar])
        freshwater = present_code(row[phyl_fw])
        if marine == "missing" and freshwater == "missing":
            flag = "missing"
        elif marine == "present" or freshwater == "present":
            flag = "present"
        else:
            flag = "absent"
        phocid_flags.append(flag)
        if norm_binomial(row[phyl_bin]) == "monachus monachus":
            monk_state = flag
    coded = [flag for flag in phocid_flags if flag != "missing"]
    n_flag = sum(flag == "present" for flag in coded)
    n = len(coded)
    seal_status = band(0 if n == 0 else n_flag / n, n, 10, 0.80, 0.50)
    if monk_state == "absent":
        seal_status = "fail"
    groups["seal"] = {
        "L": seal_status,
        "L_detail": proportion_block(n_flag, n, seal_status),
        "monachus_monachus": monk_state,
    }
    otariid = phyl.loc[family_names == "otariidae"]
    ot_flags = []
    for _, row in otariid.iterrows():
        marine = present_code(row[phyl_mar])
        freshwater = present_code(row[phyl_fw])
        if marine == "present" or freshwater == "present":
            ot_flags.append("present")
        elif marine == "absent" and freshwater == "absent":
            ot_flags.append("absent")
    descriptive["otariidae"] = proportion_block(
        sum(flag == "present" for flag in ot_flags),
        len(ot_flags),
        "descriptive",
    )

    order_a = amphibio["Order"].astype(str).str.strip().str.lower()
    family_a = amphibio["Family"].astype(str).str.strip().str.lower()
    ranid = amphibio.loc[(order_a == "anura") & (family_a == "ranidae")].copy()
    habitat_cols = ["Fos", "Ter", "Aqu", "Arb"]
    ranid_habitat = []
    for _, row in ranid.iterrows():
        codes = {column: present_code(row[column]) for column in habitat_cols}
        if all(code == "missing" for code in codes.values()):
            ranid_habitat.append("missing")
        else:
            ranid_habitat.append("present" if codes["Aqu"] == "present" else "absent")
    coded = [flag for flag in ranid_habitat if flag != "missing"]
    n_flag = sum(flag == "present" for flag in coded)
    n = len(coded)
    frog_l = band(0 if n == 0 else n_flag / n, n, 30, 0.50, 0.25)
    groups["frog"] = {"L": frog_l, "L_detail": proportion_block(n_flag, n, frog_l), "n_rows": int(len(ranid))}

    breed_n = 0
    lar_only = 0
    dir_only = 0
    for _, row in ranid.iterrows():
        if present_code(row["Aqu"]) != "present":
            continue
        direct = present_code(row["Dir"])
        larval = present_code(row["Lar"])
        viviparous = present_code(row["Viv"])
        if direct == "missing" and larval == "missing" and viviparous == "missing":
            continue
        breed_n += 1
        if larval == "present" and direct != "present":
            lar_only += 1
        if direct == "present" and larval != "present":
            dir_only += 1
    if breed_n < 20:
        frog_b_table = "unscored"
    elif lar_only / breed_n >= 0.70:
        frog_b_table = "fail"
    elif dir_only / breed_n >= 0.70:
        frog_b_table = "pass"
    else:
        frog_b_table = "mixed"
    groups["frog"]["B_amphibio"] = {
        "status": frog_b_table,
        "n": breed_n,
        "lar_without_dir": lar_only,
        "dir_without_lar": dir_only,
        "lar_without_dir_proportion": None if breed_n == 0 else round(lar_only / breed_n, 4),
        "dir_without_lar_proportion": None if breed_n == 0 else round(dir_only / breed_n, 4),
    }

    anura = amphibio.loc[order_a == "anura"]
    anura_flags = []
    for _, row in anura.iterrows():
        codes = [present_code(row[column]) for column in habitat_cols]
        if all(code == "missing" for code in codes):
            continue
        anura_flags.append(present_code(row["Aqu"]) == "present")
    descriptive["anura_aqu"] = proportion_block(
        sum(anura_flags),
        len(anura_flags),
        "descriptive",
    )

    wiki_provenance = []
    wiki_failed = False
    wiki_by_group = {}
    for group, titles in WIKI_PAGES.items():
        scored = []
        for title in titles:
            try:
                page = fetch_wiki(title)
            except Exception as exc:  # noqa: BLE001 — recorded as an unavailable page
                wiki_failed = True
                problems.append(f"wikipedia {title}: {exc}")
                continue
            time.sleep(0.4)
            wiki_provenance.append(
                {
                    "name": page["title"],
                    "download_url": page["download_url"],
                    "retrieved_at": page["retrieved_at"],
                    "byte_size": page["byte_size"],
                    "sha256": page["sha256"],
                    "revid": page["revid"],
                }
            )
            decided = clause_from_sentences(sentences_of(page["html"]), frog=(group == "frog"))
            decided["title"] = page["title"]
            decided["revid"] = page["revid"]
            scored.append(decided)
            if group != "frog" and decided["A"] in {"pass", "fail"} and decided["B"] in {"pass", "fail"}:
                break
            if group == "frog":
                break
        wiki_by_group[group] = combine_text_sources(scored) if scored else {
            "A": "unscored",
            "B": "unscored",
            "evidence": {},
            "pages": [],
        }

    disagree_frog = False
    for group in groups:
        wiki = wiki_by_group.get(group, {"A": "unscored", "B": "unscored", "evidence": {}, "pages": []})
        groups[group]["A"] = wiki["A"]
        groups[group]["wiki_pages"] = wiki["pages"]
        groups[group]["evidence"] = wiki["evidence"]
        if group == "frog" and groups[group]["B_amphibio"]["status"] in {"pass", "fail"}:
            groups[group]["B"] = groups[group]["B_amphibio"]["status"]
            groups[group]["B_source"] = "amphibio"
            if wiki["B"] in {"pass", "fail"} and wiki["B"] != groups[group]["B"]:
                disagree_frog = True
        else:
            groups[group]["B"] = wiki["B"]
            groups[group]["B_source"] = "wikipedia" if group != "frog" else "wikipedia_after_amphibio_unscored"
        states = [groups[group]["L"], groups[group]["A"], groups[group]["B"]]
        if "fail" in states:
            groups[group]["group"] = "fail"
        elif states == ["pass", "pass", "pass"]:
            groups[group]["group"] = "pass"
        else:
            groups[group]["group"] = "unscored"

    pass_n = sum(item["group"] == "pass" for item in groups.values())
    fail_n = sum(item["group"] == "fail" for item in groups.values())
    unscored_n = sum(item["group"] == "unscored" for item in groups.values())
    fully = sum(
        item["L"] in {"pass", "fail"} and item["A"] in {"pass", "fail"} and item["B"] in {"pass", "fail"}
        for item in groups.values()
    )
    trait_l = sum(item["L"] in {"pass", "fail"} for item in groups.values())
    mixed_clauses = 0
    for item in groups.values():
        mixed_clauses += sum(item[clause] == "mixed" for clause in ("L", "A", "B"))

    if not files_ok or (wiki_failed and pass_n + fail_n < 4):
        verdict = "inconclusive"
        reason = "data-unavailable"
    elif pass_n == 6:
        verdict = "supports"
        reason = None
    elif fail_n >= 3:
        verdict = "refutes"
        reason = None
    elif fail_n in {1, 2} and pass_n >= 1:
        verdict = "mixed"
        reason = None
    else:
        verdict = "inconclusive"
        reason = "underpowered"

    confidence = 0.35
    confidence += 0.05 * fully
    if groups["frog"]["B_source"] == "amphibio":
        confidence += 0.10
    if trait_l >= 4:
        confidence += 0.10
    if disagree_frog:
        confidence -= 0.10
    confidence -= 0.05 * mixed_clauses
    confidence = round(min(0.8, max(0.25, confidence)), 2)

    summary = []
    for name in (
        "sea_turtle",
        "crocodile",
        "hippopotamus",
        "seal",
        "freshwater_tortoise",
        "frog",
    ):
        item = groups[name]
        summary.append(
            f"{name}: {item['group']} (L={item['L']}, A={item['A']}, B={item['B']}, B_source={item['B_source']})"
        )
    summary.append(
        f"groups passing all three clauses: {pass_n}; failing: {fail_n}; unscored: {unscored_n}"
    )

    measured = {
        "value": pass_n,
        "unit": "named groups passing all three clauses",
        "n": pass_n + fail_n,
        "uncertainty": None,
        "extra": {
            "pass_count": pass_n,
            "fail_count": fail_n,
            "unscored_count": unscored_n,
            "groups_with_all_three_clauses_scored": fully,
            "confidence_formula": confidence,
            "frog_wikipedia_disagrees_with_amphibio": disagree_frog,
            "groups": {
                name: {
                    key: groups[name][key]
                    for key in groups[name]
                    if key != "evidence"
                }
                for name in groups
            },
            "descriptive": descriptive,
            "problems": problems,
        },
    }

    outcome = {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "data_kind": "biological" if files_ok else "none",
        "measured": measured,
        "results_summary": summary,
        "method": (
            "Downloaded the pinned AmphiBIO zip, ReptTraits v1.2 workbook, and PHYLACINE 1.2.1 trait table, "
            "checked the MD5 or git blob pin, and scored water-living from AmphiBIO Aqu, ReptTraits microhabitat, "
            "and PHYLACINE Marine/Freshwater using the pre-registered group definitions and cuts. "
            "Fetched the named English Wikipedia articles, kept the lead and natural-history sections, and applied "
            "the pre-registered sentence patterns for lungs or surfacing, including the gerund surfacing to breathe, "
            "and for where eggs or young are placed. A negation in the six words before a fail pattern cancels it. "
            "Microhabitat tokens aquatic and marine count as water-living together with semi-aquatic. "
            "Ranid breeding mode came from AmphiBIO Dir and Lar when that table met its sample floor. "
            "A group passes only if water-living, air-breathing, and breeding site all pass."
        ),
        "provenance_files": provenance,
        "provenance_wiki": wiki_provenance,
        "evidence": {name: groups[name].get("evidence") for name in groups},
    }
    (DERIVED / "outcome.json").write_text(json.dumps(outcome, indent=2) + "\n")
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    if "--apply" in sys.argv:
        current = json.loads(RESULT_PATH.read_text())
        for key, value in frozen.items():
            if current.get(key) != value:
                raise SystemExit(f"refusing to apply: pre-registered field changed: {key}")
        current["status"] = "complete"
        current["verdict"] = verdict
        if reason:
            current["reason"] = reason
        else:
            current.pop("reason", None)
        current["confidence"] = confidence
        current["data_kind"] = outcome["data_kind"]
        current["measured"] = measured
        current["results_summary"] = summary
        current["method"] = outcome["method"]
        current["datasets"] = datasets_block(provenance, wiki_provenance)
        RESULT_PATH.write_text(json.dumps(current, indent=2) + "\n")
        reloaded = json.loads(RESULT_PATH.read_text())
        for key, value in frozen.items():
            if reloaded.get(key) != value:
                raise SystemExit(f"apply mutated pre-registered field: {key}")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "summary": summary}, indent=2))


def datasets_block(files, wiki) -> list[dict]:
    file_rows = []
    for meta in files:
        file_rows.append(
            {
                "name": meta["name"],
                "download_url": meta["download_url"],
                "retrieved_at": meta["retrieved_at"],
                "byte_size": meta["byte_size"],
                "sha256": meta["sha256"],
            }
        )
    wiki_rows = []
    for meta in wiki:
        wiki_rows.append(
            {
                "name": meta["name"],
                "download_url": meta["download_url"],
                "retrieved_at": meta["retrieved_at"],
                "byte_size": meta["byte_size"],
                "sha256": meta["sha256"],
                "revid": meta["revid"],
            }
        )
    return [
        {
            "id": "amphibio-v1-figshare-4644424",
            "name": "AmphiBIO v1, amphibian ecological traits",
            "landing_url": "https://doi.org/10.6084/m9.figshare.4644424.v5",
            "doi": "10.6084/m9.figshare.4644424.v5",
            "version": "v5",
            "license": "CC BY 4.0",
            "files": [file_rows[0]],
            "role": "Ranidae habitat (Aqu) and breeding strategy (Dir, Lar, Viv)",
        },
        {
            "id": "repttraits-v1-2-figshare-24572683",
            "name": "ReptTraits v1.2 ecological traits of reptiles",
            "landing_url": "https://doi.org/10.6084/m9.figshare.24572683.v4",
            "doi": "10.6084/m9.figshare.24572683.v4",
            "version": "v1.2 file on article v4",
            "license": "CC BY 4.0",
            "files": [file_rows[1]],
            "role": "microhabitat of sea turtles, crocodylids, and non-marine non-testudinid turtles",
        },
        {
            "id": "phylacine-1.2.1-trait-data",
            "name": "PHYLACINE 1.2.1 mammal trait table",
            "landing_url": "https://doi.org/10.5281/zenodo.3690867",
            "doi": "10.5281/zenodo.3690867",
            "version": "1.2.1",
            "license": "No SPDX id on the GitHub repository; cite Faurby et al. 2018 (10.1002/ecy.2443) and the 1.2.1 Zenodo release",
            "files": [file_rows[2]],
            "role": "Marine and Freshwater flags for Hippopotamus amphibius and Phocidae",
        },
        {
            "id": "wikipedia-en-natural-history-extracts",
            "name": "English Wikipedia articles named in the pre-registration",
            "landing_url": "https://en.wikipedia.org/wiki/Main_Page",
            "doi": None,
            "version": "revision ids on each file",
            "license": "CC BY-SA 4.0",
            "files": wiki_rows,
            "role": "sentence-level proxy for lungs or surfacing and for where eggs or young are placed",
        },
    ]


if __name__ == "__main__":
    main()
