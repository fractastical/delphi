#!/usr/bin/env python3
"""Exploration helper: keyword-in-context for regexes in Parts of Animals I-IV.

Usage: python3 kwic.py PATTERN [PATTERN ...]
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
lines = (REPO / "claim-sources/aristotle-biology/inputs/pa.txt").read_text(encoding="utf-8").split("\n")
for pat in sys.argv[1:]:
    print(f"== {pat}")
    for i in range(5, 481):
        for m in re.finditer(pat, lines[i], re.I):
            a, b = max(0, m.start() - 110), min(len(lines[i]), m.end() + 110)
            print(f"  {i + 1}: …{lines[i][a:b]}…")
