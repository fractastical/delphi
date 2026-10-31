"""Container entry for the cfd3d GPU packet (stdlib only; runs under compute_ops cops_run.py).

Stages, each with its own stop rule; a failed stage stops every later one and is written to out/status.json:
  1. telemetry   nvidia-smi snapshot + 5 s samples to out/telemetry.csv
  2. julia       official Julia tarball, sha256 pinned in packet.json
  3. geometry    rebuild fish3d 994aac4 with pinned PyPI wheels; every STL sha256 must equal the pin
  4. env         Pkg.instantiate of the pinned GPU Manifest
  5. cpu_gate    C0 + sphere D8 on this container's CPU must reproduce the local CPU pins
  6. cuda_gate   CUDA.functional; C0 on GPU exact; sphere D8/D16 on GPU within tolerance of the local CPU pins
  7. diag        sphere D32 (two domains): diagnostics, not gates
  8. fish        the fish cases, each with its own timeout; video rendered here from full-resolution slices
Outputs are bounded by packet.json "max_out_bytes"; raw slices never leave the container.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

JOB = Path.cwd()
OUT = Path(os.environ.get("COPS_OUT", "out"))
WORK = Path(os.environ.get("CFD3D_WORK", "/work/cfd3d"))
PK = json.loads((JOB / "engineering/cfd3d/packet.json").read_text())
T0 = time.time()
status: dict = {"schema": "cfd3d-gpu-status-0.1", "packet_sha256": os.environ.get("CFD3D_PACKET_SHA256"), "stages": {}}


def log(msg: str) -> None:
    print(f"CFD3D {time.time() - T0:7.1f}s {msg}", flush=True)


def save() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.json").write_text(json.dumps(status, indent=1))


def stage(name: str, ok: bool, **info) -> bool:
    status["stages"][name] = {"ok": ok, "t_s": round(time.time() - T0, 1), **info}
    save()
    log(f"stage {name} ok={ok} {json.dumps(info)[:400]}")
    return ok


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(argv, timeout, env=None, log_to=None) -> int:
    with open(log_to, "w") if log_to else open(os.devnull, "w") as fh:
        try:
            return subprocess.run(argv, env=env, timeout=timeout, stdout=fh, stderr=subprocess.STDOUT).returncode
        except subprocess.TimeoutExpired:
            return 124


def julia_env(threads: int) -> dict:
    return dict(os.environ, JULIA_DEPOT_PATH=str(WORK / "depot"), JULIA_NUM_THREADS=str(threads),
                JULIA_PKG_PRECOMPILE_AUTO="0", CFD3D_GPU="1", OPENBLAS_NUM_THREADS="1")


def tail(p: Path, n=30) -> str:
    return "\n".join(p.read_text(errors="replace").splitlines()[-n:]) if p.exists() else ""


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    status["packet_json_sha256"] = sha(JOB / "engineering/cfd3d/packet.json")
    # 1. telemetry
    smi = shutil.which("nvidia-smi")
    if smi:
        (OUT / "nvidia-smi.txt").write_text(subprocess.run([smi], capture_output=True, text=True).stdout)
        tel = open(OUT / "telemetry.csv", "w")
        subprocess.Popen([smi, "--query-gpu=timestamp,utilization.gpu,memory.used,power.draw", "--format=csv",
                          "-l", "5"], stdout=tel, stderr=subprocess.DEVNULL)
    stage("telemetry", bool(smi))
    # 2. julia
    jl = PK["julia"]
    tgz = WORK / "julia.tgz"
    urllib.request.urlretrieve(jl["url"], tgz)
    if not stage("julia", sha(tgz) == jl["sha256"], sha256=sha(tgz)):
        return 2
    subprocess.run(["tar", "xzf", str(tgz), "-C", str(WORK)], check=True)
    julia = str(WORK / jl["dir"] / "bin" / "julia")
    # 3. geometry: rebuild fish3d from its own code with pinned wheels; refuse any byte drift
    gv = WORK / "gv"
    rc = run([sys.executable, "-m", "venv", str(gv)], 300)
    rc = rc or run([str(gv / "bin/pip"), "install", "--no-cache-dir", *PK["geometry"]["pip"]], 900,
                   log_to=OUT / "logs/pip.log")
    gout = WORK / "fish3d"
    rc = rc or run([str(gv / "bin/python"), "-I", "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); from engineering.fish3d.build import main; "
                    "sys.exit(main(['--out', sys.argv[2]]))", str(JOB / "fish3d_src"), str(gout)], 600,
                   log_to=OUT / "logs/fish3d_build.log")
    pins = PK["geometry"]["stl_sha256"]
    gdir = WORK / "geometry"
    got = {}
    if rc == 0:
        built = next(gout.iterdir())
        gdir.mkdir(exist_ok=True)
        shutil.copy(built / "components.json", gdir / "components.json")
        for k in pins:
            src = built / "components" / f"{k}.stl"
            got[k] = sha(src) if src.exists() else None
            if src.exists():
                shutil.copy(src, gdir / f"{k}.stl")
        cand = json.loads((built / "components.json").read_text())["candidate_sha256"]
    ok = rc == 0 and got == pins and cand == PK["geometry"]["candidate_sha256"]
    if not stage("geometry", ok, rc=rc, mismatched=[k for k in pins if got.get(k) != pins[k]]):
        return 3
    # 4. env
    env_dir = JOB / "engineering/cfd3d/env_gpu"
    rc = run([julia, f"--project={env_dir}", "-e", "using Pkg; Pkg.instantiate(); Pkg.precompile(); "
              "using WaterLily, WaterLilyMeshBodies, CUDA; println(CUDA.functional())"], 1500,
             env=julia_env(1), log_to=OUT / "logs/env.log")
    if not stage("env", rc == 0, rc=rc, tail=tail(OUT / "logs/env.log", 8)):
        return 4
    ctl = str(JOB / "engineering/cfd3d/controls.jl")
    pin = PK["local_cpu_pins"]
    # 5. CPU gate on this container's CPU (CFD3D_GPU=0)
    cenv = dict(julia_env(2), CFD3D_GPU="0")
    rc = run([julia, f"--project={env_dir}", ctl, str(OUT / "cpu_platform.json"), "PLATFORM"], 900, env=cenv,
             log_to=OUT / "logs/cpu_gate.log")
    r = json.loads((OUT / "cpu_platform.json").read_text()) if rc == 0 else {}
    ok = rc == 0 and r["C0"]["max_abs_div"] <= 1e-8 and r["C0"]["max_abs_u_minus_U"] <= 1e-8 and \
        abs(r["sphere_D8"]["Cd_mean"] - pin["sphere_D8_Cd"]) <= pin["rel_tol_cpu"] * abs(pin["sphere_D8_Cd"])
    if not stage("cpu_gate", ok, rc=rc, D8=r.get("sphere_D8", {}).get("Cd_mean"), pin=pin["sphere_D8_Cd"]):
        return 5
    # 6. CUDA gate
    rc = run([julia, f"--project={env_dir}", ctl, str(OUT / "gpu_platform.json"), "PLATFORM"], 900,
             env=julia_env(2), log_to=OUT / "logs/cuda_gate.log")
    r = json.loads((OUT / "gpu_platform.json").read_text()) if rc == 0 else {}
    tol = pin["rel_tol_gpu"]
    ok = rc == 0 and r["device"] != "cpu" and r["C0"]["max_abs_div"] <= 1e-8 and \
        abs(r["sphere_D8"]["Cd_mean"] - pin["sphere_D8_Cd"]) <= tol * abs(pin["sphere_D8_Cd"]) and \
        abs(r["sphere_D16"]["Cd_mean"] - pin["sphere_D16_Cd"]) <= tol * abs(pin["sphere_D16_Cd"])
    if not stage("cuda_gate", ok, rc=rc, device=r.get("device"), D8=r.get("sphere_D8", {}).get("Cd_mean"),
                 D16=r.get("sphere_D16", {}).get("Cd_mean")):
        return 6
    # 7. diagnostics (never stop the run)
    rc = run([julia, f"--project={env_dir}", ctl, str(OUT / "gpu_diag.json"), "GPU_DIAG"], 900, env=julia_env(2),
             log_to=OUT / "logs/diag.log")
    stage("diag", rc == 0, rc=rc)
    # 8. fish cases
    fish = str(JOB / "engineering/cfd3d/fish.jl")
    render = JOB / "engineering/cfd3d/render.py"
    for c in PK["fish_cases"]:
        if time.time() - T0 > PK["stop_new_case_after_s"]:
            stage(f"fish:{c['case_id']}", False, skipped="stop_new_case_after_s reached")
            continue
        cj = WORK / f"{c['case_id']}.json"
        cj.write_text(json.dumps(dict(c, geometry_dir=str(gdir))))
        wd = WORK / "cases" / c["case_id"]
        rc = run([julia, f"--project={env_dir}", fish, str(cj), str(wd)], c["timeout_s"], env=julia_env(2),
                 log_to=OUT / f"logs/{c['case_id']}.log")
        od = OUT / c["case_id"]
        od.mkdir(parents=True, exist_ok=True)
        for f in ("case.json", "forces.json"):
            if (wd / f).exists():
                shutil.copy(wd / f, od / f)
        if rc == 0 and c.get("return_surface"):
            shutil.copytree(wd / "surface", od / "surface")
        rrc = None
        if rc == 0 and c.get("render"):
            rrc = run([str(gv / "bin/python"), "-I", str(render), str(wd)], 900, log_to=OUT / f"logs/{c['case_id']}.render.log")
            if rrc == 0:
                shutil.copytree(wd / "render", od / "render")
        stage(f"fish:{c['case_id']}", rc == 0, rc=rc, render_rc=rrc,
              coeffs=json.loads((wd / "case.json").read_text())["coefficients"] if rc == 0 else None)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    stage("output", size <= PK["max_out_bytes"], bytes=size)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        stage("exception", False, error=f"{type(e).__name__}: {e}")
        sys.exit(1)
