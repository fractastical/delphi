"""Run the Lean checks for engineering/constraints: positive file must compile, negative controls must
each fail inside their own labelled block.  Honest by construction: if Lean or the Mathlib build is
unavailable the result says `lean: "not_run"` and nothing is claimed.

CLI:  python -m engineering.formal.lean_checks [receipt.json]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = Path(os.environ.get("FRONTIER_LEAN_PROJECT", "/data/artifacts/mathlib-probe"))
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def lean_available() -> bool:
    return shutil.which("lake") is not None and (PROJECT / "lakefile.toml").exists() and (PROJECT / ".lake").exists()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _compile(src: str, label: str, timeout: int = 600) -> dict:
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / f"{label}.lean"
        f.write_text(src)
        cmd = ["lake", "env", "lean", "-j2", str(f)]
        if shutil.which("systemd-run"):
            cmd = ["systemd-run", "--user", "--scope", "-q", "-p", "TasksMax=128", "-p", "MemoryMax=12G",
                   "-p", "MemorySwapMax=0", "-p", f"RuntimeMaxSec={timeout}"] + cmd
        t = time.time()
        p = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=timeout + 60)
        return {"exit": p.returncode, "out": p.stdout + p.stderr, "seconds": round(time.time() - t, 1)}


def corrupted_certificate(good: str) -> str:
    """Corrupt the solver-emitted certificate: raise vmax so the Lean side condition is false."""
    bad = good.replace("(10 : ℝ)", "(20 : ℝ)").replace("conflict_instance", "neg_corrupted")
    assert bad != good
    return bad


def run(certificate_lean: str) -> dict:
    if not lean_available():
        return {"lean": "not_run", "reason": f"lake or built Mathlib project not found at {PROJECT}"}
    theory = (HERE / "GeometricSimilarity.lean").read_text()
    pos = theory + (HERE / "MutantRefutations.lean").read_text() + "\nopen FlyingFish\n" + certificate_lean + \
        "\n#print axioms conflict_instance\n"
    neg_tpl = (HERE / "NegativeControls.lean").read_text()
    neg = theory + neg_tpl.replace("@@CORRUPTED_CERTIFICATE@@", corrupted_certificate(certificate_lean))
    rp, rn = _compile(pos, "positive"), _compile(neg, "negative")
    # which labelled blocks contain an error
    lines = (theory + neg_tpl.replace("@@CORRUPTED_CERTIFICATE@@", corrupted_certificate(certificate_lean))).splitlines()
    blocks, cur = {}, None
    for i, ln in enumerate(neg.splitlines(), 1):
        m = re.match(r"-- NEG:(\w+) (BEGIN|END)", ln)
        if m:
            if m.group(2) == "BEGIN":
                cur = m.group(1); blocks[cur] = [i, None]
            else:
                blocks[cur][1] = i; cur = None
    err_lines = [int(m.group(1)) for m in re.finditer(r":(\d+):\d+: error", rn["out"])]
    per_block = {k: [l for l in err_lines if a <= l <= b] != [] for k, (a, b) in blocks.items()}
    msgs = {}
    for k, (a, b) in blocks.items():
        for m in re.finditer(r":(\d+):\d+: error: ([^\n]*)", rn["out"]):
            if a <= int(m.group(1)) <= b:
                msgs.setdefault(k, m.group(2)[:140])
    outside = [l for l in err_lines if not any(a <= l <= b for a, b in blocks.values())]
    axioms = re.findall(r"depends on axioms: \[([^\]]*)\]", rp["out"])
    used = set()
    for a in axioms:
        used |= {x.strip() for x in a.split(",") if x.strip()}
    return {
        "lean": "ran",
        "lean_version": subprocess.run(["lean", "--version"], capture_output=True, text=True).stdout.strip(),
        "project": str(PROJECT),
        "theory_sha256": _sha(HERE / "GeometricSimilarity.lean"),
        "positive": {"exit": rp["exit"], "seconds": rp["seconds"], "n_axiom_prints": len(axioms),
                     "axioms_used": sorted(used), "only_standard_axioms": used <= STANDARD_AXIOMS and bool(used),
                     "non_axiom_output": [l for l in rp["out"].splitlines() if "depends on axioms" not in l and l.strip()][:20]},
        "negative": {"exit": rn["exit"], "seconds": rn["seconds"], "each_block_rejected": per_block,
                     "first_error_message": msgs,
                     "errors_outside_blocks": outside},
        "all_ok": rp["exit"] == 0 and used <= STANDARD_AXIOMS and bool(used) and all(per_block.values())
                  and len(per_block) == 4 and not outside and rn["exit"] != 0,
    }


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parents[1]))
    from engineering.constraints import (flying_fish_model, lean_conflict_certificate, q_speed_max, q_wl_min, solve)
    M = flying_fish_model(rho="1.225", CL="1")
    Q = [q_wl_min(150), q_speed_max(10)]
    R = solve(M, Q)
    cert = lean_conflict_certificate(M, R, Q)
    out = {"solver_result": R.to_json(), "lean_certificate_text": cert, "lean_checks": run(cert)}
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out["lean_checks"], indent=2, ensure_ascii=False))
