"""Write artifacts/biodesign-compiler/{assemblies/*.json,report.json,manifest.json}. Deterministic; no network, no GPU.

    python3 -m engineering.biodesign_compiler.run [--check]
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from engineering.biodesign_compiler import compile as bc

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "biodesign-compiler"
CONTRACT = {
    "schema": "frontier.biodesign.contract/1",
    "consumers": ["gallery", "history", "experimentation"],
    "files": {"assemblies/<id>.json": bc.ASSEMBLY_SCHEMA, "report.json": bc.REPORT_SCHEMA},
    "axes": list(bc.AXES),
    "must_display": ["axes separately, never one badge", "unresolved_bridges beside every variant", "the retained v3b convergence failure"],
    "must_not_say": ["a whole genome was designed", "a variant is biologically valid", "an unresolved bridge is a violated constraint"],
}


def build() -> dict[str, str]:
    cache: dict = {}
    r = bc.run(ROOT, cache)
    files = {f"assemblies/{a['id']}.json": json.dumps(a, indent=1, sort_keys=True) + "\n" for a in r["assemblies"]}
    # hypothetical change impact: an in-memory pin change, no file edited
    a0 = r["assemblies"][0]
    h = copy.deepcopy(a0)
    h["components"]["genetic_blueprint"]["sha256"] = "1" * 64
    imp = bc.impact(a0, h)
    again = bc.compile_assembly(ROOT, a0, cache=cache[a0["id"]])
    report = {"schema": BC_REPORT, "git_note": "inputs are the pinned files at this commit", "contract": CONTRACT,
              "compiled": r["compiled"], "comparison": r["comparison"], "layer_revision_diff": r["layer_revision_diff"],
              "controls": r["controls"],
              "change_impact_example": {"hypothetical": "genetic_blueprint pin altered in memory only", **imp,
                                         "unchanged_inputs_reuse": {"second_compile_reused_stages": again["reused_from_cache"]}},
              "retained_failures": [c["assembly"] for c in r["compiled"] if c["axes"]["numerical"]["status"].startswith("fail")]}
    files["report.json"] = json.dumps(report, indent=1, sort_keys=True, default=str) + "\n"
    man = {"schema": "frontier.artifact-manifest/1", "files": [{"path": f"artifacts/biodesign-compiler/{k}", "sha256": bc.sha(v.encode()), "bytes": len(v)} for k, v in sorted(files.items())]}
    files["manifest.json"] = json.dumps(man, indent=2) + "\n"
    return files


BC_REPORT = bc.REPORT_SCHEMA

if __name__ == "__main__":
    files = build()
    if "--check" in sys.argv:
        bad = [k for k, v in files.items() if not (OUT / k).exists() or (OUT / k).read_text() != v]
        print("PASS" if not bad else f"STALE {bad}")
        sys.exit(1 if bad else 0)
    (OUT / "assemblies").mkdir(parents=True, exist_ok=True)
    for k, v in files.items():
        (OUT / k).write_text(v)
    print("wrote", len(files), "files")
