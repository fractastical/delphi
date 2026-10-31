"""dx-nca's controlled glide comparison rows for a form, read from NCA's committed CSV (never copied into this tree).

The CSV is taken with `git show <commit>:<path>` and its sha256 is checked against `sources.NCA_CONTROLLED`, so a
design JSON quotes exactly the file NCA reported.  Rows are SIMULATED (assumed polars, point mass).
"""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from . import sources as src
from .solver_bridge import _git_blob

KEEP = ("V0", "polar", "stall_feasible", "converged", "sink_eq_ms", "LoD_eq", "range_m", "range_ratio", "sink_ratio")


def controlled_rows(repo: Path, genus: str, mass_kg: float, fS: float, fAR: float, S: float, b: float) -> dict:
    ref = src.NCA_CONTROLLED
    raw = _git_blob(repo, ref["commit"], ref["comparison_csv"])
    digest = hashlib.sha256(raw).hexdigest()
    if digest != ref["comparison_csv_sha256"]:
        raise ValueError(f"NCA comparison.csv sha256 {digest} != recorded {ref['comparison_csv_sha256']}")
    rows = [r for r in csv.DictReader(io.StringIO(raw.decode()))
            if r["genus"] == genus and abs(float(r["m"]) - mass_kg) < 1e-12
            and abs(float(r["fS"]) - fS) < 1e-9 and abs(float(r["fAR"]) - fAR) < 1e-9]
    if not rows:
        raise ValueError(f"no NCA rows for {genus} m={mass_kg} fS={fS} fAR={fAR}")
    rel = max(max(abs(float(r["S"]) - S) / S, abs(float(r["b"]) - b) / b) for r in rows)
    return {"evidence_kind": ref["evidence_kind"], "model_version": ref["model_version"],
            "repo": ref["repo"], "branch": ref["branch"], "commit": ref["commit"], "path": ref["comparison_csv"],
            "sha256": digest, "protocol": ref["protocol"], "protocol_sha256": ref["protocol_sha256"],
            "selector": {"genus": genus, "m": mass_kg, "fS": fS, "fAR": fAR},
            "geometry_rel_diff_vs_this_design": rel,
            # this design's S and b are the solver point, rounded to 6 significant figures (<= 5e-6 relative)
            "geometry_matches": rel <= 5e-6, "geometry_match_tolerance": 5e-6,
            "rows": [{k: r[k] for k in KEEP} for r in rows], "caveats": ref["caveats"]}
