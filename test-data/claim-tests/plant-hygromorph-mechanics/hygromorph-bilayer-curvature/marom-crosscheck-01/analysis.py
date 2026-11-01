#!/usr/bin/env python3
"""Runs the shared cross-check, which fills in result.json for both claims it covers
(hygromorph-antisymmetric-twist and hygromorph-bilayer-curvature). See the script it calls."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[2] / "hygromorph-antisymmetric-twist/marom-crosscheck-01/analysis.py"), run_name="__main__")
