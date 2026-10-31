#!/usr/bin/env python3
"""Build mentions.json for the darwin-origin ch06-10 slice.

Scans (a) the claim and quote fields of every claim whose chapter is VI–X and (b) the book
text of chapters VI–X for the name patterns in taxa_seed.py. Each hit becomes one mention
with a verbatim quote and either a claim id or a file/line locator as source.

Run from the repository root:  python3 organisms/darwin-origin/ch06-10/scripts/build_mentions.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from taxa_seed import TAXA, TEXT_START, TEXT_END, CHAPTERS  # noqa: E402

ROOT = HERE.parents[3]
SLICE = HERE.parent
TEXT = ROOT / "books" / "darwin-origin" / "inputs" / "pg1228.txt"
CLAIMS = ROOT / "books" / "darwin-origin" / "claims.json"


def compile_patterns(taxon):
    return [re.compile(p, re.I) for p in taxon["patterns"]]


def claim_mentions(claims):
    out = []
    for c in claims:
        for t in TAXA:
            pats = compile_patterns(t)
            hit = None
            for field in ("quote", "claim"):
                text = c[field]
                for p in pats:
                    m = p.search(text)
                    if m:
                        hit = (m.group(0), text)
                        break
                if hit:
                    break
            if hit:
                out.append({
                    "taxon_slug": t["slug"],
                    "name_as_written": hit[0],
                    "source": {"claim_id": c["id"]},
                    "quote": hit[1],
                })
    return out


def text_mentions(lines):
    """lines: list of (lineno, text) for the chapter range."""
    joined = "\n".join(txt for _, txt in lines)
    offsets = []
    pos = 0
    for n, txt in lines:
        offsets.append((pos, pos + len(txt), n))
        pos += len(txt) + 1

    def line_of(idx):
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if offsets[mid][1] < idx:
                lo = mid + 1
            else:
                hi = mid
        return lo

    out = []
    for t in TAXA:
        seen = set()
        for p in compile_patterns(t):
            for m in p.finditer(joined):
                i0, i1 = line_of(m.start()), line_of(max(m.start(), m.end() - 1))
                ls, le = offsets[i0][2], offsets[i1][2]
                if ls in t["skip_lines"] or le in t["skip_lines"]:
                    continue
                if ls in seen:
                    continue
                seen.add(ls)
                quote = " ".join(txt.strip() for _, txt in lines[i0:i1 + 1])
                out.append({
                    "taxon_slug": t["slug"],
                    "name_as_written": re.sub(r"\s+", " ", m.group(0)),
                    "source": {"file": "books/darwin-origin/inputs/pg1228.txt", "line_start": ls, "line_end": le},
                    "quote": quote,
                })
    out.sort(key=lambda x: (x["source"]["line_start"], x["taxon_slug"]))
    return out


def main():
    claims = [c for c in json.loads(CLAIMS.read_text())["claims"] if c.get("chapter") in CHAPTERS]
    all_lines = TEXT.read_text(encoding="utf-8").split("\n")
    lines = [(n, all_lines[n - 1]) for n in range(TEXT_START, TEXT_END + 1)]
    mentions = claim_mentions(claims) + text_mentions(lines)
    (SLICE / "mentions.json").write_text(json.dumps(mentions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    slugs = {m["taxon_slug"] for m in mentions}
    print(f"{len(claims)} claims, {len(mentions)} mentions, {len(slugs)} taxa with mentions")
    missing = [t["slug"] for t in TAXA if t["slug"] not in slugs]
    if missing:
        print("taxa in seed with no mention:", missing)


if __name__ == "__main__":
    main()
