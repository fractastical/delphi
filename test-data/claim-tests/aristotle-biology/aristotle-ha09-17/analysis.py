#!/usr/bin/env python3
"""Lophius lure accounts (aristotle-ha09-17).

Scores the Biology slice of each FishBase Lophius summary with the substrings
fixed in result.json. The fisheries phrase "used as bait" does not count as
the fish using a lure.

Run from this directory: python3 analysis.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0 (aristotle-ha09-17)"}
FB = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/species.parquet"


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def visible_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def biology_slice(text: str) -> str | None:
    match = re.search(r"\bBiology\b", text, re.I)
    if not match:
        return None
    slice_ = text[match.start():]
    end = re.search(r"\b(Life cycle|Diet|Main reference|References|Vulnerability)\b", slice_[20:], re.I)
    if end:
        slice_ = slice_[: 20 + end.start()]
    return slice_[:4000]


def sentence_has(sentence: str, words) -> bool:
    return any(word in sentence for word in words)


def score_slice(slice_: str) -> dict:
    low = slice_.lower()
    anatomy = any(token in low for token in ("illicium", "esca", "filament", "first dorsal spine"))
    burial = any(token in low for token in ("sand", "mud", "bury", "buried", "conceal"))
    use = ("illicium" in low) or ("esca" in low) or ("as a lure" in low) or ("to lure" in low)
    if not use:
        for sentence in re.split(r"[.\n]", low):
            has_lure_noun = any(token in sentence for token in ("filament", "illicium", "esca", "lure"))
            has_action = any(token in sentence for token in ("attract", "prey", "lure"))
            bait_only = "bait" in sentence and not has_lure_noun
            if has_lure_noun and has_action and not bait_only:
                use = True
                break
            if "as a lure" in sentence or "to lure" in sentence:
                use = True
                break
    return {"anatomy": anatomy, "use": use, "burial": burial, "full": anatomy and use and burial}


def fetch_bytes(url: str, dest: Path) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        with requests.get(url, headers=UA, timeout=180, stream=True) as response:
            response.raise_for_status()
            dest.write_bytes(response.content)
    raw = dest.read_bytes()
    stamp = dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc)
    return {
        "download_url": url,
        "retrieved_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    deviations = []
    species_file = fetch_bytes(FB, DATA / "species.parquet")
    species = pd.read_parquet(DATA / "species.parquet")
    genus_col = next(name for name in species.columns if str(name).lower() == "genus")
    epithet_col = next(
        name for name in species.columns
        if str(name).lower() == "species"
    )
    rows = species[
        species[genus_col].astype(str).str.lower().eq("lophius")
        & ~species[epithet_col].astype(str).str.lower().isin(["", "nan", "sp", "spp"])
    ]
    binomials = sorted({
        (str(genus), str(epithet))
        for genus, epithet in zip(rows[genus_col], rows[epithet_col])
    })
    scored = []
    page_files = []
    for genus, epithet in binomials:
        url = f"https://www.fishbase.se/summary/{genus}-{epithet}.html"
        dest = DATA / f"{genus}-{epithet}.html"
        try:
            meta = fetch_bytes(url, dest)
        except requests.RequestException as exc:
            scored.append({"binomial": f"{genus} {epithet}", "fetched": False, "error": str(exc)})
            continue
        page_files.append({"name": dest.name, **meta})
        text = visible_text(dest.read_text(errors="replace"))
        slice_ = biology_slice(text)
        if slice_ is None:
            scored.append({"binomial": f"{genus} {epithet}", "fetched": True, "scored": False})
        else:
            flags = score_slice(slice_)
            scored.append({
                "binomial": f"{genus} {epithet}",
                "fetched": True,
                "scored": True,
                "slice_chars": len(slice_),
                **flags,
            })
        time.sleep(0.4)

    usable = [row for row in scored if row.get("scored")]
    n = len(usable)
    n_anatomy = sum(1 for row in usable if row["anatomy"])
    n_full = sum(1 for row in usable if row["full"])
    if n < 3:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.3
    elif n_anatomy == 0:
        verdict, reason = "refutes", None
        confidence = 0.45
    elif n_full / n >= 2 / 3:
        verdict, reason = "supports", None
        confidence = 0.6
    elif n_anatomy / n >= 2 / 3:
        verdict, reason = "mixed", None
        confidence = 0.5
    else:
        # Residual, already in the script committed before download: anatomy is
        # present on some scored accounts but on fewer than 2/3, and full support
        # is also below 2/3. That is neither the pass nor the absence refutation.
        verdict, reason = "mixed", None
        confidence = 0.5
        deviations.append(
            "The registered pass needs a full-support fraction of at least 2/3, and the "
            "registered refutation needs an anatomy count of 0. This run sits in the residual "
            f"the script already coded as mixed (anatomy {n_anatomy}/{n}, full support {n_full}/{n}). "
            "Thresholds were not changed after the pages were read."
        )
    measured = {
        "value": None if n == 0 else round(n_full / n, 4),
        "unit": "fraction of scored Lophius accounts with anatomy, lure use and burial",
        "n": n,
        "uncertainty": None,
        "extra": {
            "n_anatomy": n_anatomy,
            "n_full": n_full,
            "species": scored,
        },
    }
    summary = [
        f"Lophius binomials in the species table: {len(binomials)}.",
        f"Scored accounts: {n}. Anatomy matches: {n_anatomy}. Full support (anatomy, use, burial): {n_full}.",
        f"Verdict {verdict}.",
    ]
    (DERIVED / "measured.json").write_text(
        json.dumps({"measured": measured, "summary": summary, "deviations": deviations}, indent=2) + "\n"
    )
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if n else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["method"] = (
        "Listed valid Lophius binomials from FishBase v25.04, fetched each species-summary page, "
        "cut the Biology slice, and applied the registered anatomy, lure-use and burial substrings. "
        "The fisheries sense of 'used as bait' was not counted as the fish using a lure."
    )
    result["measured"] = measured
    result["results_summary"] = summary
    if deviations:
        result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "fishbase-v25.04-species-and-lophius-summaries",
            "name": "FishBase v25.04 species table and Lophius species-summary pages",
            "landing_url": "https://www.fishbase.se/",
            "doi": None,
            "version": "v25.04",
            "license": "CC BY-NC 4.0",
            "files": [{"name": "species.parquet", **species_file}, *page_files],
            "role": "which Lophius species exist, and the compiled biology text for each",
        }
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "n": n, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
