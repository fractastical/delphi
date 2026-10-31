"""Container entry for the cfd3d GPU packet (stdlib only).

Stages; a failed gate stops every later stage. out/status.json is the machine-readable completion contract:
  completion  "complete" (every stage ok) | "partial" (gates passed, some fish case/render/output failed or skipped)
              | "failed" (a gate failed or an exception)
  rc          0 complete, 10 partial, 2-7 the failed gate, 1 exception
  science     always "model diagnostics only": the C1 physical reference gate FAILED locally (packet.json
              reference_gate), so no stage here can license a physical-validation claim.
Time: every stage gets min(its own timeout, time left before outer_budget_s - emit_margin_s); a fish case starts
only if its timeout plus the render timeout fits in what is left.
PREFLIGHT=1: check files, JSON/TOML and Python syntax only; no download, no Julia, no CUDA.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.request
from pathlib import Path

JOB = Path.cwd()
OUT = Path(os.environ.get("COPS_OUT", "out"))
WORK = Path(os.environ.get("CFD3D_WORK", "/work/cfd3d"))
PK = json.loads((JOB / "engineering/cfd3d/packet.json").read_text())
T0 = time.time()
status: dict = {"schema": "cfd3d-gpu-status-0.2", "packet_sha256": os.environ.get("CFD3D_PACKET_SHA256"),
                "science": "model diagnostics only; C1 physical reference gate FAILED (see reference_gate)",
                "reference_gate": PK["reference_gate"], "completion": "running", "rc": None, "stages": {}}


def left() -> float:
    return PK["outer_budget_s"] - PK["emit_margin_s"] - (time.time() - T0)


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


def finish(rc: int) -> int:
    status["rc"] = rc
    status["completion"] = {0: "complete", 10: "partial"}.get(rc, "failed")
    save()
    log(f"done completion={status['completion']} rc={rc}")
    return rc


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(argv, timeout, env=None, log_to=None) -> int:
    timeout = min(timeout, left())
    if timeout <= 0:
        return 124
    with open(log_to, "w") if log_to else open(os.devnull, "w") as fh:
        try:
            return subprocess.run(argv, env=env, timeout=timeout, stdout=fh, stderr=subprocess.STDOUT).returncode
        except subprocess.TimeoutExpired:
            return 124


def julia_env(threads: int, gpu: bool = True) -> dict:
    return dict(os.environ, JULIA_DEPOT_PATH=str(WORK / "depot"), JULIA_NUM_THREADS=str(threads),
                JULIA_PKG_PRECOMPILE_AUTO="0", CFD3D_GPU="1" if gpu else "0", OPENBLAS_NUM_THREADS="1")


def tail(p: Path, n=12) -> str:
    return "\n".join(p.read_text(errors="replace").splitlines()[-n:]) if p.exists() else ""


# Pins every package at the recorded version, then refuses unless the resolved Manifest's canonical
# (name, uuid, version, git-tree-sha1) list hashes to the digest of the local Manifest.
ENV_JL = r'''
using Pkg, SHA
pins = [split(l) for l in eachline(ARGS[1]) if !isempty(l)]
Pkg.add([PackageSpec(name=String(n), uuid=Base.UUID(String(u)), version=VersionNumber(String(v))) for (n, u, v) in pins];
        preserve=Pkg.PRESERVE_ALL)
m = Pkg.TOML.parsefile(joinpath(dirname(Base.active_project()), "Manifest.toml"))
rows = sort([string(n, " ", e["uuid"], " ", e["version"], " ", e["git-tree-sha1"])
             for (n, es) in m["deps"] for e in es if haskey(e, "version") && haskey(e, "git-tree-sha1")])
d = bytes2hex(sha256(join(rows .* "\n")))
println("CANON ", d)
d == ARGS[2] || (println("ENV MISMATCH"); exit(3))
Pkg.precompile()
using WaterLily, WaterLilyMeshBodies, CUDA
println("CUDA functional ", CUDA.functional())
'''


def preflight() -> int:
    """Packaging check only: files present, JSON/TOML parse, Python compiles. No network, Julia or CUDA."""
    need = ["engineering/cfd3d/" + f for f in ("controls.jl", "fish.jl", "render.py", "gates_cpu.json",
                                               "env_gpu/Project.toml", "env_gpu/pins.tsv")] + \
           ["fish3d_src/engineering/fish3d/build.py", "fish3d_src/engineering/geometry/forms.py",
            "fish3d_src/engineering/geometry/mesh.py", "fish3d_src/engineering/geometry/sources.py",
            "fish3d_src/artifacts/print/sources/daane2021-S1A-summary.json"]
    missing = [p for p in need if not (JOB / p).exists()]
    for p in JOB.rglob("*.py"):
        compile(p.read_text(), str(p), "exec")      # syntax only; writes nothing
    for p in JOB.rglob("*.json"):
        json.loads(p.read_text())
    tomllib.loads((JOB / "engineering/cfd3d/env_gpu/Project.toml").read_text())
    pins = (JOB / "engineering/cfd3d/env_gpu/pins.tsv").read_text().splitlines()
    bad_pins = [ln for ln in pins if len(ln.split()) != 3]
    ok = not missing and not bad_pins and len(pins) > 50
    print(json.dumps({"preflight": ok, "missing": missing, "bad_pins": bad_pins, "pins": len(pins),
                      "fish_cases": [c["case_id"] for c in PK["fish_cases"]],
                      "outer_budget_s": PK["outer_budget_s"], "max_out_bytes": PK["max_out_bytes"]}))
    return 0 if ok else 8


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    status["packet_json_sha256"] = sha(JOB / "engineering/cfd3d/packet.json")
    # 1. telemetry (not a gate)
    smi = shutil.which("nvidia-smi")
    if smi:
        (OUT / "nvidia-smi.txt").write_text(subprocess.run([smi], capture_output=True, text=True).stdout)
        subprocess.Popen([smi, "--query-gpu=timestamp,utilization.gpu,memory.used,power.draw", "--format=csv",
                          "-l", "5"], stdout=open(OUT / "telemetry.csv", "w"), stderr=subprocess.DEVNULL)
    stage("telemetry", bool(smi))
    # 2. julia
    jl = PK["julia"]
    tgz = WORK / "julia.tgz"
    urllib.request.urlretrieve(jl["url"], tgz)
    if not stage("julia", sha(tgz) == jl["sha256"], sha256=sha(tgz)):
        return finish(2)
    with tarfile.open(tgz) as tf:
        tf.extractall(WORK, filter="fully_trusted")    # official tarball, sha256 checked; keeps its symlinks
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
    pins, got, cand = PK["geometry"]["stl_sha256"], {}, None
    gdir = WORK / "geometry"
    if rc == 0:
        built = next(gout.iterdir())
        (OUT / "geometry").mkdir(parents=True, exist_ok=True)
        for f in ("candidate.json", "components.json", "build.json"):   # always returned, pass or fail
            if (built / f).exists():
                shutil.copy(built / f, OUT / "geometry" / f)
        gdir.mkdir(exist_ok=True)
        shutil.copy(built / "components.json", gdir / "components.json")
        for k in pins:
            src = built / "components" / f"{k}.stl"
            got[k] = sha(src) if src.exists() else None
            if src.exists():
                shutil.copy(src, gdir / f"{k}.stl")
        cand = json.loads((built / "components.json").read_text())["candidate_sha256"]
    ok = rc == 0 and got == pins and cand == PK["geometry"]["candidate_sha256"]
    if not stage("geometry", ok, rc=rc, candidate=cand, mismatched=[k for k in pins if got.get(k) != pins[k]],
                 tail=tail(OUT / "logs/fish3d_build.log", 4) if rc else ""):
        return finish(3)
    # 4. julia env from exact pins, digest-checked against the local Manifest
    env_dir = WORK / "env"
    env_dir.mkdir(exist_ok=True)
    shutil.copy(JOB / "engineering/cfd3d/env_gpu/Project.toml", env_dir / "Project.toml")
    (WORK / "env.jl").write_text(ENV_JL)
    rc = run([julia, f"--project={env_dir}", str(WORK / "env.jl"), str(JOB / PK["julia_env"]["pins"]),
              PK["julia_env"]["canonical_sha256"]], 1800, env=julia_env(1), log_to=OUT / "logs/env.log")
    if (env_dir / "Manifest.toml").exists():
        shutil.copy(env_dir / "Manifest.toml", OUT / "resolved-Manifest.toml")
    if not stage("env", rc == 0, rc=rc, tail=tail(OUT / "logs/env.log", 6)):
        return finish(4)
    ctl = str(JOB / "engineering/cfd3d/controls.jl")
    pin = PK["local_cpu_pins"]
    # 5. CPU platform gate (reproduces local model behaviour; NOT a physical reference)
    rc = run([julia, f"--project={env_dir}", ctl, str(OUT / "cpu_platform.json"), "PLATFORM"], 900,
             env=julia_env(2, gpu=False), log_to=OUT / "logs/cpu_gate.log")
    r = json.loads((OUT / "cpu_platform.json").read_text()) if rc == 0 else {}
    ok = rc == 0 and r["C0"]["max_abs_div"] <= 1e-8 and r["C0"]["max_abs_u_minus_U"] <= 1e-8 and \
        abs(r["sphere_D8"]["Cd_mean"] - pin["sphere_D8_Cd"]) <= pin["rel_tol_cpu"] * abs(pin["sphere_D8_Cd"])
    if not stage("cpu_gate", ok, rc=rc, D8=r.get("sphere_D8", {}).get("Cd_mean"), pin=pin["sphere_D8_Cd"]):
        return finish(5)
    # 6. CUDA platform gate
    rc = run([julia, f"--project={env_dir}", ctl, str(OUT / "gpu_platform.json"), "PLATFORM"], 900,
             env=julia_env(2), log_to=OUT / "logs/cuda_gate.log")
    r = json.loads((OUT / "gpu_platform.json").read_text()) if rc == 0 else {}
    tol = pin["rel_tol_gpu"]
    ok = rc == 0 and r["device"] != "cpu" and r["C0"]["max_abs_div"] <= 1e-8 and \
        abs(r["sphere_D8"]["Cd_mean"] - pin["sphere_D8_Cd"]) <= tol * abs(pin["sphere_D8_Cd"]) and \
        abs(r["sphere_D16"]["Cd_mean"] - pin["sphere_D16_Cd"]) <= tol * abs(pin["sphere_D16_Cd"])
    if not stage("cuda_gate", ok, rc=rc, device=r.get("device"), D8=r.get("sphere_D8", {}).get("Cd_mean"),
                 D16=r.get("sphere_D16", {}).get("Cd_mean"), tail=tail(OUT / "logs/cuda_gate.log", 6) if rc else ""):
        return finish(6)
    incomplete = False
    # 7. diagnostics: does the C1 bias shrink at D32? (never a gate)
    rc = run([julia, f"--project={env_dir}", ctl, str(OUT / "gpu_diag.json"), "GPU_DIAG"], 900, env=julia_env(2),
             log_to=OUT / "logs/diag.log")
    incomplete |= not stage("diag", rc == 0, rc=rc)
    # 8. fish cases
    fish = str(JOB / "engineering/cfd3d/fish.jl")
    render = JOB / "engineering/cfd3d/render.py"
    for c in PK["fish_cases"]:
        need = c["timeout_s"] + (PK["render_timeout_s"] if c.get("render") else 0)
        if need > left():
            incomplete |= not stage(f"fish:{c['case_id']}", False, skipped=f"needs {need} s, {left():.0f} s left")
            continue
        cj = WORK / f"{c['case_id']}.json"
        cj.write_text(json.dumps(dict(c, geometry_dir=str(gdir), reference_gate="C1 sphere reference FAILED")))
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
            rrc = run([str(gv / "bin/python"), "-I", str(render), str(wd)], PK["render_timeout_s"],
                      log_to=OUT / f"logs/{c['case_id']}.render.log")
            if rrc == 0:
                shutil.copytree(wd / "render", od / "render")
        ok = rc == 0 and rrc in (None, 0)
        coeffs = json.loads((wd / "case.json").read_text())["coefficients"] if rc == 0 else None
        incomplete |= not stage(f"fish:{c['case_id']}", ok, rc=rc, render_rc=rrc, coeffs=coeffs)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    incomplete |= not stage("output", size <= PK["max_out_bytes"], bytes=size)
    return finish(10 if incomplete else 0)


if __name__ == "__main__":
    if os.environ.get("PREFLIGHT") == "1":
        sys.exit(preflight())
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        stage("exception", False, error=f"{type(e).__name__}: {e}")
        sys.exit(finish(1))
