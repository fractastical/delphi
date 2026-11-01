"""Run Morpheus' official Example-CellCycle-MultiScale headless, with controls.

Source XML is read from a pinned upstream blob, never from a working copy.
Every edit made to it is a named string replacement recorded in the manifest.
Nothing here is calibrated to a fish or any other organism.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

UPSTREAM = "https://gitlab.com/morpheus.lab/morpheus.git"
TAG = "v2.3.9"
XML_PATH = "Examples/Multiscale/MultiscaleModel.xml"
BINARY_URL = "https://gitlab.com/morpheus.lab/morpheus/-/package_files/178666119/download"

# (name, old, new). Each must match exactly once or the run refuses.
BASE_EDITS = [
    ("version-2", '<MorpheusModel version="1">', '<MorpheusModel version="2">'),
    ("surface-mode", '<SurfaceConstraint target="0.95"', '<SurfaceConstraint mode="aspherity" target="0.95"'),
    ("log-states", '<Symbol symbol-ref="dist"/>\n            </Input>',
     '<Symbol symbol-ref="CDK1"/><Symbol symbol-ref="APC"/><Symbol symbol-ref="g_l"/>'
     '<Symbol symbol-ref="d"/><Symbol symbol-ref="cell.volume"/>\n            </Input>'),
    ("frame-step", '<Gnuplotter clean="true" time-step="0.1"', '<Gnuplotter clean="true" time-step="0.02"'),
]
FEEDBACK_OFF = ("feedback-off", "α1+(g_l) - β1", "α1+0*(g_l) - β1")


def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stage(clone: Path, stop: float, seed: int, feedback: bool) -> tuple[str, list[str], str]:
    raw = sh("git", "-C", str(clone), "show", f"{TAG}:{XML_PATH}")
    edits = list(BASE_EDITS)
    edits.append(("stop-time", '<StopTime value="2"/>', f'<StopTime value="{stop}"/>'))
    edits.append(("seed", '<RandomSeed value="3445"/>', f'<RandomSeed value="{seed}"/>'))
    if not feedback:
        edits.append(FEEDBACK_OFF)
    xml, names = raw, []
    for name, old, new in edits:
        if xml.count(old) != 1:
            raise SystemExit(f"refused: edit {name!r} matches {xml.count(old)} times")
        xml = xml.replace(old, new)
        names.append(name)
    return xml, names, sha(raw.encode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clone", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--gnuplot", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--stop", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=3445)
    ap.add_argument("--feedback-off", action="store_true")
    a = ap.parse_args()
    out = Path(a.out) / a.arm
    out.mkdir(parents=True, exist_ok=True)
    xml, names, src_sha = stage(Path(a.clone), a.stop, a.seed, not a.feedback_off)
    (out / "model.xml").write_text(xml)
    cmd = ["systemd-run", "--user", "--scope", "-q", "-p", "CPUQuota=100%", "-p", "TasksMax=128",
           "-p", "MemoryMax=4G", "-p", "MemorySwapMax=0", "-p", "RuntimeMaxSec=600",
           a.binary, "-f", "model.xml", "--gnuplot-path", a.gnuplot]
    r = subprocess.run(cmd, cwd=out, capture_output=True, text=True,
                       env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
    (out / "stdout.log").write_text("\n".join(ln for ln in r.stdout.splitlines() if "seeking" not in ln))
    (out / "manifest.json").write_text(json.dumps({
        "arm": a.arm, "exit": r.returncode, "tag": TAG, "xml_path": XML_PATH,
        "source_sha256": src_sha, "edits": names, "stop": a.stop, "seed": a.seed,
        "feedback": not a.feedback_off, "binary_sha256": sha(Path(a.binary).read_bytes()),
        "binary_url": BINARY_URL}, indent=1))
    print(a.arm, "exit", r.returncode)


if __name__ == "__main__":
    main()
