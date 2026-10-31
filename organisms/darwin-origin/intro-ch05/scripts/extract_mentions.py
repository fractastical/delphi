#!/usr/bin/env python3
"""Build organisms/darwin-origin/intro-ch05/mentions.json.

Two sweeps, both driven by PATTERNS in taxa_seed.py:
  1. claims: every row of books/darwin-origin/claims.json whose chapter is Introduction
     or I-V; `claim` and `quote` fields are scanned.
  2. text: lines 313-5289 of books/darwin-origin/inputs/pg1228.txt (Introduction through
     the end of Chapter V).

Usage: python3 extract_mentions.py   (run from anywhere; paths are repo-relative)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
from taxa_seed import PATTERNS, TAXA  # noqa: E402

TEXT_FILE = "books/darwin-origin/inputs/pg1228.txt"
LINE_START, LINE_END = 313, 5289          # inclusive, 1-based
CHAPTERS = {"Introduction", "I", "II", "III", "IV", "V"}

COMPILED = [
    (re.compile(r"(?<![A-Za-z-])(?:%s)(?![A-Za-z])" % pat, re.I), slug, flt)
    for pat, slug, flt in PATTERNS
]
for _, slug, _ in COMPILED:
    assert slug in TAXA, slug


def scan(text, key):
    """Yield (slug, name_as_written) for non-overlapping matches, earlier patterns win."""
    taken = []
    out = []
    for rx, slug, flt in COMPILED:
        if flt is not None and key not in flt:
            continue
        for m in rx.finditer(text):
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            taken.append((s, e))
            out.append((s, slug, m.group(0)))
    out.sort()
    return [(slug, name) for _, slug, name in out]


def main():
    claims = json.loads((ROOT / "books/darwin-origin/claims.json").read_text(encoding="utf-8"))["claims"]
    sel = [c for c in claims if c["chapter"] in CHAPTERS]
    mentions = []
    seen = set()

    for c in sel:
        for field in ("claim", "quote"):
            for slug, name in scan(c[field], c["id"]):
                k = (c["id"], slug, name.lower())
                if k in seen:
                    continue
                seen.add(k)
                mentions.append({
                    "taxon_slug": slug,
                    "name_as_written": name,
                    "source": {"claim_id": c["id"], "field": field},
                    "quote": c[field],
                })

    lines = (ROOT / TEXT_FILE).read_text(encoding="utf-8").split("\n")
    for ln in range(LINE_START, LINE_END + 1):
        line = lines[ln - 1]
        for slug, name in scan(line, ln):
            k = (ln, slug, name.lower())
            if k in seen:
                continue
            seen.add(k)
            mentions.append({
                "taxon_slug": slug,
                "name_as_written": name,
                "source": {"file": TEXT_FILE, "line_start": ln, "line_end": ln},
                "quote": line.strip(),
            })

    (SLICE / "mentions.json").write_text(json.dumps(mentions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n_claim = sum(1 for m in mentions if "claim_id" in m["source"])
    slugs = {m["taxon_slug"] for m in mentions}
    print(f"claims scanned: {len(sel)}; mentions: {len(mentions)} ({n_claim} from claims, {len(mentions) - n_claim} from text); taxa: {len(slugs)}")
    unused = set(TAXA) - slugs
    if unused:
        print("seed taxa with no mention:", sorted(unused))


if __name__ == "__main__":
    main()
