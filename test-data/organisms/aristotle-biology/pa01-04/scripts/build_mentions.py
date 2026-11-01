#!/usr/bin/env python3
"""Build test-data/organisms/aristotle-biology/pa01-04/mentions.json from the seed patterns.

Claim mentions: every aristotle-pa claim whose `quote` (else `claim`) matches a taxon pattern,
with source {claim_id, field}. Text mentions: one per (line, taxon, form written) in pa.txt
lines 6-481, skipped when a claim covering that line already quotes the same taxon. Quotes are
the sentence containing the name, verbatim.

Usage: python3 build_mentions.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
REPO = SLICE.parents[3]
sys.path.insert(0, str(HERE))
import seed  # noqa: E402

COMPILED = [(t["slug"], re.compile("|".join(f"(?:{p})" for p in t["patterns"]), re.I)) for t in seed.TAXA]


def sentence(text, start, end, maxlen=320):
    """The sentence around text[start:end], trimmed to at most maxlen characters around the match."""
    a = max(text.rfind(". ", 0, start), text.rfind("; ", 0, start), text.rfind("? ", 0, start))
    a = 0 if a == -1 else a + 2
    ends = [i for i in (text.find(". ", end), text.find("; ", end), text.find("? ", end)) if i != -1]
    b = min(ends) + 1 if ends else len(text)
    if b - a > maxlen:
        a2 = max(a, start - maxlen // 2)
        b2 = min(b, end + maxlen // 2)
        if a2 > a:
            a2 = text.find(" ", a2) + 1
        if b2 < b:
            b2 = text.rfind(" ", 0, b2)
        return ("…" if a2 > a else "") + text[a2:b2].strip() + ("…" if b2 < b else "")
    return text[a:b].strip()


def claim_mentions():
    claims = json.load(open(REPO / "claim-sources/aristotle-biology/claims.json", encoding="utf-8"))["claims"]
    out = []
    for c in claims:
        if not c["id"].startswith("aristotle-pa"):
            continue
        for slug, rx in COMPILED:
            for field in ("quote", "claim"):
                m = rx.search(c.get(field) or "")
                if m:
                    out.append({
                        "taxon_slug": slug,
                        "name_as_written": " ".join(m.group(0).split()),
                        "source": {"claim_id": c["id"], "field": field},
                        "quote": sentence(c[field], m.start(), m.end()),
                    })
                    break
    return out, claims


def text_mentions(claim_ments, claims):
    lines = (REPO / seed.BOOK).read_text(encoding="utf-8").split("\n")
    by_id = {c["id"]: c for c in claims}
    covered = set()
    for m in claim_ments:
        if m["source"]["field"] != "quote":
            continue
        c = by_id[m["source"]["claim_id"]]
        for ln in range(c["lineStart"], c["lineEnd"] + 1):
            covered.add((ln, m["taxon_slug"]))
    out = []
    for ln in range(seed.LINE_START, seed.LINE_END + 1):
        text = lines[ln - 1]
        if not text.strip() or text.startswith("#"):
            continue
        for slug, rx in COMPILED:
            if (ln, slug) in covered:
                continue
            seen = set()
            for m in rx.finditer(text):
                form = " ".join(m.group(0).split())
                if form.lower() in seen:
                    continue
                seen.add(form.lower())
                out.append({
                    "taxon_slug": slug,
                    "name_as_written": form,
                    "source": {"file": seed.BOOK, "line_start": ln, "line_end": ln},
                    "quote": sentence(text, m.start(), m.end()),
                })
    return out


def main():
    cm, claims = claim_mentions()
    tm = text_mentions(cm, claims)
    ments = cm + tm
    (SLICE / "mentions.json").write_text(json.dumps(ments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(ments)} mentions ({len(cm)} from {len({m['source']['claim_id'] for m in cm})} claims, {len(tm)} from text), "
          f"{len({m['taxon_slug'] for m in ments})} taxa mentioned")
    missing = set(seed.TAXA_BY_SLUG) - {m["taxon_slug"] for m in ments}
    if missing:
        print("taxa in seed with no mention:", sorted(missing))


if __name__ == "__main__":
    main()
