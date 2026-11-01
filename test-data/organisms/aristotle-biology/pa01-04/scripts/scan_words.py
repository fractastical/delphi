#!/usr/bin/env python3
"""Exploration helper: capitalised words in Parts of Animals I-IV (pa.txt lines 6-481) with counts."""
import collections
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
lines = (REPO / "claim-sources/aristotle-biology/inputs/pa.txt").read_text(encoding="utf-8").split("\n")[5:481]
text = "\n".join(lines)
c = collections.Counter(m.group(1) for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]+)\b", text, re.M))
print(" ".join(f"{w}:{n}" for w, n in sorted(c.items())))
