#!/usr/bin/env python3
"""Build mentions.json for the thompson-growth-form ch01-05 slice.

Sources:
  1. claims.json rows with chapter in I..V: the `claim` and `quote` fields.
  2. The Gutenberg text (inputs/pg55264.txt) lines 980-9881 (CHAPTER I .. end of CHAPTER V).

A mention is one (taxon, claim) pair or one (taxon, text line) pair. Text lines that lie inside
the lineStart..lineEnd range of a chapter I-V claim that already mentions the taxon are skipped
so the same passage is not recorded twice. Page markers {12} and footnote markers [3] are removed
from quotes, following BEST_PRACTICES.md section 5.

Usage: python3 build_mentions.py   (run from anywhere; paths are resolved from the repo root)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
REPO = SLICE.parents[2]
sys.path.insert(0, str(HERE))
from taxa_table import TAXA  # noqa: E402

TEXT_FILE = "thompson-growth-form/inputs/pg55264.txt"
CLAIMS_FILE = REPO / "thompson-growth-form" / "claims.json"
CHAPTERS = {"I", "II", "III", "IV", "V"}
LINE_START, LINE_END = 980, 9881  # CHAPTER I heading .. line before CHAPTER VI heading

MARKERS = re.compile(r"\s?\{\s*\d+\}|\[\d+\]")


def clean(s: str) -> str:
    return MARKERS.sub("", s).strip()


def compile_taxa():
    out = []
    for t in TAXA:
        pats = [re.compile(p) for p in t["patterns"]]
        excl = re.compile(t["exclude"]) if t.get("exclude") else None
        out.append((t["slug"], pats, excl))
    return out


def find(taxa, text):
    """Yield (slug, matched_string) for every taxon matching `text`.

    Gutenberg italics markers (_Fundulus_) are turned into spaces so that \b works."""
    text = text.replace("_", " ")
    for slug, pats, excl in taxa:
        if excl and excl.search(text):
            continue
        for p in pats:
            m = p.search(text)
            if m:
                yield slug, m.group(0)
                break


def phrase_around(text, needle, width=120):
    """A verbatim fragment of `text` containing `needle`, cut at clause boundaries."""
    i = text.find(needle)
    if i < 0:
        return text
    start = max(0, i - width)
    end = min(len(text), i + len(needle) + width)
    frag = text[start:end]
    if start > 0:
        frag = "…" + frag.split(" ", 1)[1] if " " in frag else "…" + frag
    if end < len(text):
        frag = frag.rsplit(" ", 1)[0] + "…" if " " in frag else frag + "…"
    return frag


def main():
    taxa = compile_taxa()
    claims = [c for c in json.loads(CLAIMS_FILE.read_text())["claims"] if c["chapter"] in CHAPTERS]
    lines = (REPO / TEXT_FILE).read_text(encoding="utf-8").split("\n")

    mentions = []
    claimed = {}  # slug -> list of (lineStart, lineEnd)
    for c in claims:
        seen = set()
        for field in ("quote", "claim"):
            for slug, hit in find(taxa, c[field]):
                if slug in seen:
                    continue
                seen.add(slug)
                mentions.append({
                    "taxon_slug": slug,
                    "name_as_written": hit,
                    "source": {"claim_id": c["id"], "field": field},
                    "quote": clean(phrase_around(c[field], hit)),
                })
                claimed.setdefault(slug, []).append((c["lineStart"], c["lineEnd"]))

    for n in range(LINE_START, LINE_END + 1):
        raw = lines[n - 1]
        if not raw.strip():
            continue
        for slug, hit in find(taxa, raw):
            if any(a <= n <= b for a, b in claimed.get(slug, [])):
                continue
            mentions.append({
                "taxon_slug": slug,
                "name_as_written": hit,
                "source": {"file": TEXT_FILE, "line_start": n, "line_end": n},
                "quote": clean(raw),
            })

    (SLICE / "mentions.json").write_text(json.dumps(mentions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    slugs = {m["taxon_slug"] for m in mentions}
    missing = [t["slug"] for t in TAXA if t["slug"] not in slugs]
    print(f"claims in ch I-V: {len(claims)}; mentions: {len(mentions)}; taxa mentioned: {len(slugs)}")
    if missing:
        print("taxa in table with no mention:", missing)


if __name__ == "__main__":
    main()
