"""Run the frozen protocol's arms under the declared caps, one thread each.

Each arm gets its own directory holding model.xml, build.json, logger.csv, the TIFF
timelapse and run.json. Nothing here interprets a result; analyze.py does that.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import build_model


def run_one(binary: Path, clone: Path, arm: dict, outdir: Path, runtime_max_s: int) -> dict:
    out = outdir / arm["name"]
    base = build_model.fetch_base(clone)
    xml, names = build_model.build(base, arm)
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.xml").write_text(xml)
    (out / "build.json").write_text(json.dumps(
        {"arm": arm, "edits": names, "model_sha256": build_model.sha(xml.encode()),
         "base_sha256": build_model.BASE_SHA256, "tag": build_model.TAG,
         "xml_path": build_model.XML_PATH, "binary_sha256": build_model.BINARY_SHA256}, indent=1))
    # each arm runs with cwd=out, so the binary must be an absolute path
    cmd = ["systemd-run", "--user", "--scope", "-q", "-p", "CPUQuota=200%", "-p", "TasksMax=256",
           "-p", "MemoryMax=2G", "-p", "MemorySwapMax=0", "-p", f"RuntimeMaxSec={runtime_max_s}",
           str(binary.resolve()), "-f", "model.xml", "--no-gnuplot", "--num-threads", "1"]
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=out, capture_output=True, text=True,
                       env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
    wall = time.monotonic() - t0
    (out / "stdout.log").write_text(r.stdout[-200000:])
    (out / "stderr.log").write_text(r.stderr[-50000:])
    rec = {"arm": arm["name"], "exit": r.returncode, "wall_s": round(wall, 2),
           "logger": (out / "logger.csv").exists(),
           "tiff": sorted(p.name for p in out.glob("*.tif*"))}
    (out / "run.json").write_text(json.dumps(rec, indent=1))
    print(f"{arm['name']:22s} exit={r.returncode} wall={wall:7.2f}s log={rec['logger']} tiff={len(rec['tiff'])}",
          flush=True)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--clone", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--group", default=None, help="restrict to one arm group (A, B, C)")
    a = ap.parse_args()
    proto = json.loads(Path(a.protocol).read_text())
    got = build_model.sha(Path(a.binary).read_bytes())
    if got != build_model.BINARY_SHA256:
        raise SystemExit(f"refused: binary sha256 {got}, pinned {build_model.BINARY_SHA256}")
    arms = [x for x in proto["arms"] if a.group is None or x["group"] == a.group]
    outdir = Path(a.out)
    recs = [run_one(Path(a.binary), Path(a.clone), x, outdir, proto["caps"]["runtime_max_s"]) for x in arms]
    (outdir / f"runs-{a.group or 'all'}.json").write_text(json.dumps(recs, indent=1))
    bad = [r["arm"] for r in recs if r["exit"] != 0 or not r["logger"]]
    print(f"\n{len(recs)} arms, {len(bad)} without a usable log: {bad}")


if __name__ == "__main__":
    main()
