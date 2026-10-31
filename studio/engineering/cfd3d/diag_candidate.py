"""CPU-only diagnostic: rebuild fish3d's candidate.json (no meshes) on the cloud image and return it in full.

Why: GPU job aijob-e00s3bqbccez3bjpm9 rebuilt all 12 STLs byte-identically but its candidate_sha256 was 52d15c7c...
instead of 4a3b912e... . This returns the cloud candidate bytes and the environment facts needed to explain it:
CPU model and flags, numpy SIMD dispatch, libc, Python, and the candidate recomputed with numpy's AVX-512 dispatch
disabled. No mesh, no Julia, no GPU. Writes $COPS_OUT/diag/*; rc 0 if every variant ran.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

JOB = Path.cwd()
OUT = Path(os.environ.get("COPS_OUT", "out")) / "diag"
PK = json.loads((JOB / "engineering/cfd3d/packet.json").read_text())
INNER = r'''
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from engineering.fish3d import build as B
b = B.canon(B.candidate())
open(sys.argv[2], "wb").write(b)
from numpy._core._multiarray_umath import __cpu_features__ as f
print(json.dumps({"candidate_sha256": hashlib.sha256(b).hexdigest(), "numpy": np.__version__,
                  "cpu_features_on": sorted(k for k, v in f.items() if v)}))
'''
VARIANTS = {"default": None, "no_avx512": "X86_V4 AVX512_ICL AVX512_SPR", "no_avx2_avx512": "X86_V3 X86_V4 AVX512_ICL AVX512_SPR"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    env_facts = {"python": sys.version, "libc": platform.libc_ver(), "machine": platform.machine(),
                 "packet_sha256": os.environ.get("CFD3D_PACKET_SHA256")}
    try:
        cpu = Path("/proc/cpuinfo").read_text().split("\n\n")[0]
        env_facts["cpu_model"] = next((ln.split(":", 1)[1].strip() for ln in cpu.splitlines()
                                       if ln.startswith("model name")), None)
        env_facts["cpu_avx512_flags"] = sorted({w for ln in cpu.splitlines() if ln.startswith("flags")
                                                for w in ln.split() if w.startswith("avx512")})
    except OSError as e:
        env_facts["cpu_error"] = str(e)
    gv = Path(os.environ.get("CFD3D_WORK", "/work")) / "diag_gv"
    rc = subprocess.run([sys.executable, "-m", "venv", str(gv)]).returncode
    pins = [p for p in PK["geometry"]["pip"] if p.split("==")[0] in ("numpy", "manifold3d", "trimesh")]
    rc = rc or subprocess.run([str(gv / "bin/pip"), "install", "-q", "--no-cache-dir", *pins]).returncode
    (OUT / "inner.py").write_text(INNER)
    res = {"schema": "cfd3d-candidate-diag-0.1", "expected_candidate_sha256": PK["geometry"]["candidate_sha256"],
           "cloud_gpu_job_candidate_sha256": "52d15c7cec23d7678c9d2b683a6a2c4a15eb91d847c946a6cf19f06c22908a4a",
           "env": env_facts, "pip": pins, "pip_rc": rc, "variants": {}}
    for name, dis in VARIANTS.items():
        env = dict(os.environ)
        if dis:
            env["NPY_DISABLE_CPU_FEATURES"] = dis
        p = subprocess.run([str(gv / "bin/python"), "-I", str(OUT / "inner.py"), str(JOB / "fish3d_src"),
                            str(OUT / f"candidate.{name}.json")], env=env, capture_output=True, text=True, timeout=300)
        row = {"rc": p.returncode, "disable": dis, "stderr_tail": p.stderr[-800:]}
        if p.returncode == 0:
            row.update(json.loads(p.stdout.strip().splitlines()[-1]))
            row["matches_expected"] = row["candidate_sha256"] == res["expected_candidate_sha256"]
        res["variants"][name] = row
    (OUT / "diag.json").write_text(json.dumps(res, indent=1))
    print("CFD3D diag " + json.dumps({k: {"sha": v.get("candidate_sha256"), "ok": v.get("matches_expected")}
                                      for k, v in res["variants"].items()}), flush=True)
    return 0 if rc == 0 and all(v["rc"] == 0 for v in res["variants"].values()) else 1


def preflight() -> int:
    need = ["fish3d_src/engineering/fish3d/build.py", "fish3d_src/engineering/geometry/forms.py",
            "fish3d_src/artifacts/print/sources/daane2021-S1A-summary.json"]
    missing = [p for p in need if not (JOB / p).exists()]
    for p in JOB.rglob("*.py"):
        compile(p.read_text(), str(p), "exec")      # syntax only; writes nothing
    compile(INNER, "inner", "exec")
    print(json.dumps({"preflight": not missing, "missing": missing, "variants": list(VARIANTS)}))
    return 0 if not missing else 8


if __name__ == "__main__":
    sys.exit(preflight() if os.environ.get("PREFLIGHT") == "1" else main())
