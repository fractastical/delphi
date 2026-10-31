#!/usr/bin/env python3
"""Build organisms/darwin-origin/ch11-14/mentions.json from the seed patterns.

Usage: python3 build_mentions.py   (run from anywhere; paths are repo-relative)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
REPO = SLICE.parents[2]
sys.path.insert(0, str(HERE))
import seed  # noqa: E402


def window(text, start, end, width=90):
    a = max(0, start - width)
    b = min(len(text), end + width)
    # trim to word boundaries
    if a > 0:
        sp = text.find(" ", a)
        a = sp + 1 if sp != -1 and sp < start else a
    if b < len(text):
        sp = text.rfind(" ", end, b)
        b = sp if sp != -1 else b
    frag = text[a:b].strip()
    return ("…" if a > 0 else "") + frag + ("…" if b < len(text) else "")


def claim_mentions():
    claims = json.load(open(REPO / "books/darwin-origin/claims.json", encoding="utf-8"))["claims"]
    by_id = {c["id"]: c for c in claims}
    out = []
    for cid, items in seed.CLAIM_MENTIONS.items():
        c = by_id[cid]
        for slug, written, field in items:
            text = c[field]
            m = re.search(r"\b" + re.escape(written) + r"\b", text, re.I)
            if not m:
                # fall back to first word of the written form
                m = re.search(r"\b" + re.escape(written.split()[0]) + r"\b", text, re.I)
            if not m:
                raise SystemExit(f"{cid}: '{written}' not found in {field}")
            out.append({
                "taxon_slug": slug,
                "name_as_written": text[m.start():m.end()],
                "source": {"claim_id": cid, "field": field},
                "quote": window(text, m.start(), m.end()),
            })
    return out


def text_mentions():
    lines = open(REPO / seed.BOOK, encoding="utf-8").read().split("\n")
    # join chapter lines with "\n" and keep offsets so multi-line matches work
    chap = lines[seed.CH_START - 1: seed.CH_END]
    joined = "\n".join(chap)
    starts = []
    pos = 0
    for l in chap:
        starts.append(pos)
        pos += len(l) + 1

    def line_of(off):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo

    out = []
    seen = set()
    for pat, slug in seed.TEXT_PATTERNS:
        for m in re.finditer(pat, joined, re.I):
            l0 = line_of(m.start()) + seed.CH_START
            l1 = line_of(m.end() - 1) + seed.CH_START
            if (l0, slug) in seed.EXCLUDE:
                continue
            key = (l0, slug, m.group(0).lower())
            if key in seen:
                continue
            seen.add(key)
            quote = " ".join(x.strip() for x in lines[l0 - 1:l1]).strip()
            out.append({
                "taxon_slug": slug,
                "name_as_written": " ".join(m.group(0).split()),
                "source": {"file": seed.BOOK, "line_start": l0, "line_end": l1},
                "quote": quote,
            })
    out.sort(key=lambda e: (e["source"]["line_start"], e["taxon_slug"]))
    return out


def main():
    ments = claim_mentions() + text_mentions()
    unknown = {m["taxon_slug"] for m in ments} - set(seed.TAXA_BY_SLUG)
    if unknown:
        raise SystemExit(f"unknown slugs: {unknown}")
    (SLICE / "mentions.json").write_text(json.dumps(ments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n_claim = sum(1 for m in ments if "claim_id" in m["source"])
    print(f"{len(ments)} mentions ({n_claim} from claims, {len(ments) - n_claim} from text), "
          f"{len({m['taxon_slug'] for m in ments})} taxa mentioned")
    missing = set(seed.TAXA_BY_SLUG) - {m["taxon_slug"] for m in ments}
    if missing:
        print("taxa in seed with no mention:", sorted(missing))


if __name__ == "__main__":
    main()
