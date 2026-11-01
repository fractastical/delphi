#!/usr/bin/env bash
# Re-run everything from a clean checkout. Needs python3 with venv. About 1 hour on 10 cores
# (part 1 is the long one; part 2 is dominated by the 8 x 300 null replicates).
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -q numpy scipy pandas requests statsmodels
.venv/bin/python fetch_gift.py          # GIFT API -> data/ (git-ignored) + derived/gift_manifest.csv.gz, gift_richness.csv
.venv/bin/python part1_null.py          # sampling null + Preston canonical -> derived/part1_*
.venv/bin/python part2_analysis.py      # GIFT island SAR, ch12-04 comparison, grok n=2 null -> derived/part2_*
.venv/bin/python part2_grok_fine.py     # exploratory fine density sweep (post hoc, see DEVIATIONS.md)
.venv/bin/python build_result.py        # result.json from derived/*
shasum -a 256 -c PREREG.sha256 2>/dev/null | head -1 || true
