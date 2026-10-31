"""Compile UnitAlgebra.lean + controls and the negative blocks; write a hashed receipt.

Scope: arithmetic of unit conversion only. Nothing here is evidence of biological correspondence.
If Lean or built Mathlib is unavailable the result is {"lean": "not_run"} and nothing is claimed.

CLI:  python -m engineering.formal.unit_algebra_checks [receipt.json]
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from engineering.formal import lean_checks as L

HERE = Path(__file__).resolve().parent
BLOCKS = ("comp_adds", "interval_no_positivity", "inverse_without_nonzero", "dim_sub")
AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def run() -> dict:
    if not L.lean_available():
        return {"lean": "not_run", "reason": f"lake or built Mathlib project not found at {L.PROJECT}"}
    theory = (HERE / "UnitAlgebra.lean").read_text()
    pos = theory + (HERE / "UnitAlgebraControls.lean").read_text()
    neg = theory + (HERE / "UnitAlgebraNegative.lean").read_text()
    rp, rn = L._compile(pos, "ua_positive"), L._compile(neg, "ua_negative")
    blocks, cur = {}, None
    for i, ln in enumerate(neg.splitlines(), 1):
        m = re.match(r"-- NEG:(\w+) (BEGIN|END)", ln)
        if m:
            if m.group(2) == "BEGIN":
                cur = m.group(1); blocks[cur] = [i, None]
            else:
                blocks[cur][1] = i; cur = None
    err_lines = [int(m.group(1)) for m in re.finditer(r":(\d+):\d+: error", rn["out"])]
    rejected = {k: any(a <= l <= b for l in err_lines) for k, (a, b) in blocks.items()}
    outside = [l for l in err_lines if not any(a <= l <= b for a, b in blocks.values())]
    used = set()
    n_prints = 0
    for m in re.finditer(r"depends on axioms: \[([^\]]*)\]", rp["out"]):
        n_prints += 1
        used |= {x.strip() for x in m.group(1).split(",") if x.strip()}
    pos_errors = [l for l in rp["out"].splitlines() if ": error" in l]
    return {
        "lean": "ran", "scope": "arithmetic of unit conversion only; no biological correspondence",
        "lean_version": subprocess.run(["lean", "--version"], capture_output=True, text=True).stdout.strip(),
        "provenance": L.provenance({"positive": pos, "negative": neg}) | {
            "unit_algebra_files": {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in
                                   ("UnitAlgebra.lean", "UnitAlgebraControls.lean", "UnitAlgebraNegative.lean",
                                    "unit_algebra_checks.py")}},
        "positive": {"exit": rp["exit"], "errors": pos_errors, "axiom_prints": n_prints, "axioms_used": sorted(used),
                     "only_standard_axioms": bool(used) and used <= AXIOMS},
        "negative": {"exit": rn["exit"], "each_block_rejected": rejected, "errors_outside_blocks": outside},
        "all_ok": rp["exit"] == 0 and not pos_errors and n_prints == 6 and used <= AXIOMS and bool(used)
                  and set(rejected) == set(BLOCKS) and all(rejected.values()) and not outside and rn["exit"] != 0,
    }


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parents[1]))
    out = run()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in out if k != "provenance"}, indent=2, ensure_ascii=False))
