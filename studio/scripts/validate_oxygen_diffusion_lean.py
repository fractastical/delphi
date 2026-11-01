#!/usr/bin/env python3
"""Compile the oxygen rule and require both coefficient mutants to be rejected."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEAN_SOURCE = ROOT / "engineering/formalize/lean/OxygenDiffusionBound.lean"
MUTANT_SOURCE = ROOT / "engineering/formalize/lean/OxygenDiffusionBound_negative_corrupt_law.lean"
OUTPUT = ROOT / "artifacts/oxygen-diffusion-rule/lean-receipt.json"
BUILD = ROOT / "artifacts/oxygen-diffusion-rule/build"
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args: list[str], *, env: dict[str, str], timeout: int = 300) -> dict[str, Any]:
    started = time.monotonic()
    p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    return {"argv": args, "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
            "seconds": round(time.monotonic() - started, 3)}


def validate() -> dict[str, Any]:
    mathlib_project = Path(os.environ.get("FRONTIER_LEAN_PROJECT", "/data/artifacts/mathlib-probe")).resolve()
    lake = shutil.which("lake") or str(Path.home() / ".elan/bin/lake")
    lean = shutil.which("lean") or str(Path.home() / ".elan/bin/lean")
    if not mathlib_project.is_dir() or not LEAN_SOURCE.is_file() or not MUTANT_SOURCE.is_file():
        raise FileNotFoundError("Lean project or frozen source file missing")

    path_result = subprocess.run([lake, "env", "printenv", "LEAN_PATH"], cwd=mathlib_project,
                                 capture_output=True, text=True, timeout=60, check=True)
    lean_path = path_result.stdout.strip()
    if not lean_path:
        raise RuntimeError("Mathlib project exported an empty LEAN_PATH")
    BUILD.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LEAN_PATH"] = f"{BUILD}:{lean_path}"

    version = subprocess.run([lean, "--version"], env=env, capture_output=True, text=True, timeout=30, check=True).stdout.strip()
    manifest_path = mathlib_project / "lake-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mathlib = next((p for p in manifest.get("packages", []) if p.get("name") == "mathlib"), None)
    if not mathlib:
        raise RuntimeError("Mathlib package pin missing from lake-manifest.json")

    positive = _run([lean, "-o", str(BUILD / "OxygenDiffusionBound.olean"), str(LEAN_SOURCE)], env=env)
    if positive["exit"] != 0:
        raise RuntimeError(f"positive Lean source failed: {positive['stderr'][-2000:]}")
    axiom_rows = re.findall(r"depends on axioms: \[([^\]]*)\]", positive["stdout"])
    parsed_axioms = [sorted(x.strip() for x in row.split(",") if x.strip()) for row in axiom_rows]
    if len(parsed_axioms) != 6 or any(set(row) - STANDARD_AXIOMS for row in parsed_axioms):
        raise RuntimeError(f"axiom audit did not match six standard-axiom results: {parsed_axioms}")
    if "sorryAx" in positive["stdout"] or "sorryAx" in positive["stderr"]:
        raise RuntimeError("positive proof depends on sorryAx")

    negative = _run([lean, str(MUTANT_SOURCE)], env=env)
    negative_text = negative["stdout"] + negative["stderr"]
    error_lines = [int(row) for row in re.findall(r"OxygenDiffusionBound_negative_corrupt_law\.lean:(\d+):\d+: error:", negative_text)]
    negative_lines = MUTANT_SOURCE.read_text(encoding="utf-8").splitlines()
    expected_error_lines = [
        number
        for number, line in enumerate(negative_lines, start=1)
        if line.strip() in {
            "nlinarith [hD, ha, hC0, hR, hmul]",
            "nlinarith [hD, ha, hC0, hL, hmul]",
            "example : 0 ≤ mutatedSphereCenterOxygen 1 1 (6 / 5) (5 / 2) := by",
            "example : 0 ≤ mutatedSlabCenterOxygen 1 1 3 2 := by",
        }
    ]
    if (
        negative["exit"] == 0
        or sorted(error_lines) != sorted(expected_error_lines)
        or negative_text.count("linarith failed to find a contradiction") != 2
        or negative_text.count("error: unsolved goals") != 2
        or negative_text.count("⊢ False") != 4
    ):
        raise RuntimeError(f"coefficient mutants were not rejected as expected: {negative_text[-2000:]}")

    return {
        "schema": "frontier.oxygen-diffusion-lean-receipt/1",
        "status": "pass",
        "lean_version": version,
        "mathlib": {"url": mathlib.get("url"), "revision": mathlib.get("rev"),
                    "input_revision": mathlib.get("inputRev"), "manifest_sha256": sha256(manifest_path)},
        "source": {"path": str(LEAN_SOURCE.relative_to(ROOT)), "sha256": sha256(LEAN_SOURCE)},
        "mutant_source": {"path": str(MUTANT_SOURCE.relative_to(ROOT)), "sha256": sha256(MUTANT_SOURCE)},
        "positive": {**positive, "theorem_axiom_sets": parsed_axioms,
                     "only_standard_axioms": True, "sorryAx": False,
                     "olean_sha256": sha256(BUILD / "OxygenDiffusionBound.olean")},
        "corrupted_coefficients": {"exit": negative["exit"], "expected_failures": 4,
                                   "actual_failure_diagnostics": len(error_lines),
                                   "failure_roles": [
                                       "two parametric equivalence proofs cannot establish the original threshold under mutated coefficients",
                                       "two exact rational witnesses show the mutated center is negative at the original threshold",
                                   ],
                                   "diagnostic_lines": error_lines,
                                   "assertion_scope": ["sphere coefficient 6→5", "slab coefficient 2→1"],
                                   "stdout": negative["stdout"], "stderr": negative["stderr"],
                                   "correct_law_twins_compiled": all(line > 24 for line in error_lines)},
        "limitations": [
            "Lean checks the algebraic implication after the source-to-equation interpretation; it does not independently verify that translation.",
            "The theorem assumes steady diffusion, constant consumption, the stated ideal geometry and the boundary/no-flux conditions.",
            "No empirical tissue parameters, cell-viability threshold, repair outcome, or organism-level conclusion is established."
        ]
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "lean": result["lean_version"],
                      "positive_exit": result["positive"]["exit"],
                      "mutant_rejections": result["corrupted_coefficients"]["actual_failure_diagnostics"],
                      "receipt": str(OUTPUT.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
