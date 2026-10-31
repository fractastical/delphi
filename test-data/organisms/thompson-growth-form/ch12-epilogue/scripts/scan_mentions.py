#!/usr/bin/env python3
"""Scan the Ch. XII-Epilogue claims and book text for animal mentions -> mentions.json.

Usage: python3 scan_mentions.py   (run from anywhere; paths are repo-relative)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from taxa_terms import TAXA  # noqa: E402

REPO = HERE.parents[4]
SLICE = HERE.parent
TEXT_PATH = "claim-sources/thompson-growth-form/inputs/pg55264.txt"
CLAIMS_PATH = "claim-sources/thompson-growth-form/claims.json"
CHAPTERS = {"XII", "XIII", "XIV", "XV", "XVI", "XVII", "Epilogue"}
LINE_START, LINE_END = 19561, 25432  # "CHAPTER XII" heading .. last line of the Epilogue

def compile_pattern(p: str):
    # Patterns containing a capital letter (Latin names, proper nouns) are case-sensitive;
    # vernacular patterns are not.
    return re.compile(p, 0 if re.search(r"[A-Z]", p.replace("\\b", "")) else re.IGNORECASE)


COMPILED = [(t["slug"], [compile_pattern(p) for p in t["patterns"]]) for t in TAXA]


def clean(s: str) -> str:
    s = re.sub(r"\{\d+\}", "", s)  # page markers
    s = re.sub(r"\[\d+\]", "", s)  # footnote markers
    s = s.replace("_", "")  # Gutenberg italic markers
    return re.sub(r"\s+", " ", s).strip()


def match_all(text: str):
    """Yield (slug, matched_string) for every taxon whose pattern hits `text`."""
    for slug, pats in COMPILED:
        for p in pats:
            m = p.search(text)
            if m:
                yield slug, m.group(0)
                break


def main():
    claims = json.loads((REPO / CLAIMS_PATH).read_text())["claims"]
    claims = [c for c in claims if c["chapter"] in CHAPTERS]
    lines = (REPO / TEXT_PATH).read_text(encoding="utf-8").split("\n")

    mentions = []
    # 1. claims: look in the claim and the quote fields
    for c in claims:
        seen = set()
        for field in ("claim", "quote"):
            txt = clean(c[field])
            for slug, hit in match_all(txt):
                if slug in seen:
                    continue
                seen.add(slug)
                # verbatim phrase: the sentence/clause around the hit
                i = txt.lower().find(hit.lower())
                prev = txt.rfind(". ", 0, i)
                lo = prev + 2 if prev >= 0 else 0
                hi = txt.find(". ", i)
                hi = len(txt) if hi == -1 else hi + 1
                mentions.append({
                    "taxon_slug": slug,
                    "name_as_written": hit[:-2] if hit.endswith(("’s", "'s")) else hit,
                    "source": {"claim_id": c["id"]},
                    "quote": txt[lo:hi].strip(),
                })
    # 2. book text, line by line
    for n in range(LINE_START, LINE_END + 1):
        raw = lines[n - 1]
        txt = clean(raw)
        if not txt:
            continue
        for slug, hit in match_all(txt):
            mentions.append({
                "taxon_slug": slug,
                "name_as_written": hit[:-2] if hit.endswith(("’s", "'s")) else hit,
                "source": {"file": TEXT_PATH, "line_start": n, "line_end": n},
                "quote": txt,
            })

    out = SLICE / "mentions.json"
    out.write_text(json.dumps(mentions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    slugs = {m["taxon_slug"] for m in mentions}
    claim_slugs = {m["taxon_slug"] for m in mentions if "claim_id" in m["source"]}
    print(f"{len(mentions)} mentions, {len(slugs)} taxa ({len(claim_slugs)} named in claims) -> {out}")
    unused = [t["slug"] for t in TAXA if t["slug"] not in slugs]
    if unused:
        print("taxa in table with no mention:", unused)


if __name__ == "__main__":
    main()
