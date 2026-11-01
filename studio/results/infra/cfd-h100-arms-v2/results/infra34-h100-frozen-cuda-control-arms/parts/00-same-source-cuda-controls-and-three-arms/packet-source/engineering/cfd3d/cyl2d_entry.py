"""Worker entry for the cfd3d 2-D cylinder packets, CPU or CUDA (stdlib only, Python >= 3.11).

    python3 engineering/cfd3d/cyl2d_entry.py [PACKET.json] [STAGE ...]
PACKET.json is a file in engineering/cfd3d (default cpu_packet.json; the R2 GPU packet is r2_packet.json);
its "stages" list is the default order; the CUDA control-arm packet (R1, R3_domain, M1_mutant on one device,
one arm at a time) is arms_packet.json. Before the rename (d49cc33) this file was cpu_entry.py; the frozen CPU
packet 95ac40c9 carries that version.

Stages; a failed gate stops every later stage. OUT/status.json is the machine-readable completion contract:
  completion  "complete" (every planned case finished and was evaluated) | "partial" (gates passed, some case
              stopped at its budget with a checkpoint, or failed) | "failed" (a gate failed or an exception)
  rc          0 complete, 10 partial, 2-7 the failed gate, 11 calibration no-go (CUDA packet), 1 exception
  science     never "passed": the cylinder verdict is OUT/eval.json verdict (control_passes,
              pressure_coupling_allowed). The 3-D C1 sphere reference gate FAILED and stays failed; nothing
              here licenses a physical-validation claim for fins, the fish or flight.
Stages:
  julia          download the pinned Julia tarball, refuse on sha256 mismatch (CFD3D_JULIA=path skips it)
  env            instantiate engineering/cfd3d/env exactly from its Manifest; refuse if the Manifest changes
  restart_check  tiny non-contract run straight vs split + resumed in a new process: series and the final
                 state must be bit-identical, and a checkpoint for another run id must be refused (gate)
  scaling        force-free TIMING of R1 at several thread counts (telemetry, not a gate)
  cases          each planned case is its own process tree with its own threads, memory cap and wall budget;
                 it runs in segments (CFD3D_SEGMENT_S) and resumes from its checkpoint until it finishes,
                 its budget ends, or the outer budget minus the emit margin ends
  eval           cyl2d_eval.py over every finished run (frozen contract + band; it fails closed)
CUDA packets add (device "cuda"):
  telemetry      nvidia-smi (not a gate)
  env            built from exact pins, digest-checked, and CUDA.functional() must be true (gate)
  restart_check  also a CUDA arm: straight vs split + resumed on the device, within the same-state tolerance
  platform       same-state CPU/CUDA control: T_same is run on the CPU to t = 100 (developed shedding), then
                 continued from that one checkpoint on the CPU and on the device; the aligned series must agree
                 within the frozen tolerance and a 10-step-shifted comparison must not (gate)
  calibration    force-free TIMING of each planned case on the device with device-memory polling; the cases
                 start only if the frozen rule passes (see st_calibration), otherwise rc 11
  cases          with "cases_sequential", one case at a time in packet order, and a case whose calibrated
                 projection no longer fits the time left is not started (recorded, never run as filler)
  output         OUT bytes against max_out_bytes (failure means partial, not a gate)
PREFLIGHT=1: files, JSON/TOML and Python syntax only; no download and no Julia.
Environment: COPS_OUT (default out), CFD3D_WORK (default /work/cfd3d), CFD3D_OUTER_BUDGET_S overrides the
packet's outer budget (the VM's hard lifetime minus export time, set by the dispatcher), CFD3D_RESUME_FROM.
Checkpoints: Julia rewrites WORK/cases/<id>/<id>.ckpt atomically (tmp + rename) every 30 min and at each segment
end; that live file is never exported. export_ckpt copies it through one open descriptor (so it reads one
complete version) to OUT/checkpoints/<id>-<n>.ckpt.partial, renames it to <id>-<n>.ckpt, and only then lists it
with its sha256 and bytes in OUT/checkpoints/manifest.json. Only manifest-listed files are coherent state;
*.partial never is. Snapshots: every export_every_s per case and whenever a case stops at its budget, never
after a case finishes (its output suffices), and never past export_bytes_max in total (a reserve is kept so the
stop-at-budget snapshot always fits). Resume on a new VM: CFD3D_RESUME_FROM=<a restored OUT/checkpoints>; each
case starts from its newest manifest-listed snapshot whose sha256 matches, and cyl2d.jl still refuses it unless
run id, cyl2d.jl and contract sha256, Julia and WaterLily versions all match.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import tomllib
import urllib.request
from pathlib import Path

JOB = Path(__file__).resolve().parents[2]
HERE = JOB / "engineering/cfd3d"
OUT = Path(os.environ.get("COPS_OUT", "out")).resolve()
WORK = Path(os.environ.get("CFD3D_WORK", "/work/cfd3d")).resolve()
ARGS = sys.argv[1:]
PK_FILE = ARGS.pop(0) if ARGS and ARGS[0].endswith(".json") else "cpu_packet.json"
PK = json.loads((HERE / PK_FILE).read_text())
GPU = PK.get("device", "cpu") == "cuda"
PROJECT = HERE / "env"                     # a pins-built env replaces it (st_env)
JULIA_PIN = json.loads((HERE / "packet.json").read_text())["julia"]
OUTER = float(os.environ.get("CFD3D_OUTER_BUDGET_S", PK["outer_budget_s"]))
EXPORT = OUT / "checkpoints"               # coherent snapshots only (see export_ckpt); never the live file
RESUME = Path(os.environ["CFD3D_RESUME_FROM"]).resolve() if os.environ.get("CFD3D_RESUME_FROM") else None
DRY_RUN = os.environ.get("CFD3D_PLATFORM_DRY_RUN") == "1"   # local check of the platform stage: both arms on CPU
EXPORT_MAX = int(os.environ.get("CFD3D_EXPORT_BYTES_MAX", PK["export_bytes_max"]))
T0 = time.time()
LOCK = threading.Lock()
status: dict = {"schema": "cfd3d-cyl2d-status-0.2", "packet_sha256": os.environ.get("CFD3D_PACKET_SHA256"),
                "platform_dry_run": DRY_RUN,
                "packet_file": PK_FILE, "device": PK.get("device", "cpu"),
                "science": PK["science"], "reference_gate": PK["reference_gate"], "outer_budget_s": OUTER,
                "completion": "running", "rc": None, "stages": {}, "cases": {}}


def left() -> float:
    return OUTER - PK["emit_margin_s"] - (time.time() - T0)


def log(msg: str) -> None:
    print(f"CFD3D-CYL {time.time() - T0:8.1f}s {msg}", flush=True)


def save() -> None:
    with LOCK:
        OUT.mkdir(parents=True, exist_ok=True)
        tmp = OUT / "status.json.tmp"
        tmp.write_text(json.dumps(status, indent=1))
        tmp.replace(OUT / "status.json")


def stage(name: str, ok: bool, **info) -> bool:
    with LOCK:
        status["stages"][name] = {"ok": ok, "t_s": round(time.time() - T0, 1), **info}
    save()
    log(f"stage {name} ok={ok} {json.dumps(info)[:400]}")
    return ok


def finish(rc: int) -> int:
    status["rc"] = rc
    status["completion"] = {0: "complete", 10: "partial",
                            11: "stopped: R2 does not fit (calibration rule); controls and timing kept"}.get(rc, "failed")
    save()
    log(f"done completion={status['completion']} rc={rc}")
    return rc


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def julia_bin() -> Path:
    return Path(os.environ["CFD3D_JULIA"]) if os.environ.get("CFD3D_JULIA") else \
        WORK / JULIA_PIN["dir"] / "bin/julia"


def julia_env(threads: int, gpu: bool = False, **extra) -> dict:
    return dict(os.environ, JULIA_DEPOT_PATH=os.environ.get("CFD3D_DEPOT", str(WORK / "depot")),
                JULIA_NUM_THREADS=str(threads), JULIA_PKG_PRECOMPILE_AUTO="0", JULIA_NUM_PRECOMPILE_TASKS="2",
                CFD3D_GPU="1" if gpu else "0", OPENBLAS_NUM_THREADS="1", **{k: str(v) for k, v in extra.items()})


def capper() -> list[str]:
    """systemd scope prefix when this host can make one (bounds the whole tree); [] otherwise."""
    if not shutil.which("systemd-run"):
        return []
    pre = ["systemd-run", "--scope", "--quiet"] + ([] if os.geteuid() == 0 else ["--user"])
    ok = subprocess.run(pre + ["true"], capture_output=True).returncode == 0
    return pre if ok else []


CAP = None


def run_capped(argv, threads, mem_gb, timeout, log_to, gpu=False, **extra) -> tuple[int, float]:
    """One Julia process tree: systemd caps when available, and always a watchdog on wall time and RSS."""
    global CAP
    if CAP is None:
        CAP = capper()
        with LOCK:
            status["cap_mechanism"] = "systemd-run scope + watchdog" if CAP else "watchdog only (no systemd scope)"
    timeout = min(timeout, left())
    if timeout <= 0:
        return 124, 0.0
    pre = CAP + ["-p", f"MemoryMax={mem_gb}G", "-p", "MemorySwapMax=0", "-p", f"TasksMax={threads + 64}",
                 "-p", f"RuntimeMaxSec={int(timeout) + 120}"] if CAP else []
    t = time.time()
    with open(log_to, "a") as fh:
        # every argv element as str: the frozen CPU packet passed TIMING's int step count here and its scaling
        # stage died with a TypeError on VM03 (infra-to-cfd-argv-failure.md)
        cmd = [str(a) for a in pre + [julia_bin(), "--startup-file=no", *argv]]
        p = subprocess.Popen(cmd, env=julia_env(threads, gpu, **extra),
                             stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        peak = 0.0
        while p.poll() is None:
            rss = tree_rss_gb(p.pid)
            peak = max(peak, rss)
            if rss > mem_gb or time.time() - t > timeout + 60:
                fh.write(f"\nCFD3D-CYL watchdog: killing (rss {rss:.2f} GB, cap {mem_gb} GB, "
                         f"wall {time.time() - t:.0f} s, budget {timeout:.0f} s)\n")
                os.killpg(p.pid, 9)
                p.wait()
                return 137, peak
            time.sleep(5)
    return p.returncode, peak


def tree_rss_gb(pid: int) -> float:
    total = 0
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            st = (d / "stat").read_text().rsplit(")", 1)[1].split()
            if int(st[2]) != pid and int(d.name) != pid:      # field 5 (pgrp): the session started for this tree
                continue
            for ln in (d / "status").read_text().splitlines():
                if ln.startswith("VmRSS:"):
                    total += int(ln.split()[1])
        except (OSError, IndexError, ValueError):
            continue
    return total / 1024 ** 2


def preflight() -> int:
    need = ["engineering/cfd3d/" + f for f in PK["files"]]
    missing = [p for p in need if not (JOB / p).exists()]
    for p in HERE.rglob("*.py"):
        compile(p.read_text(), str(p), "exec")
    for p in HERE.rglob("*.json"):
        json.loads(p.read_text())
    for p in HERE.rglob("*.toml"):
        tomllib.loads(p.read_text())
    ev = PK["env"]
    if ev.get("pins"):
        rows = (JOB / ev["pins"]).read_text().splitlines() if (JOB / ev["pins"]).exists() else []
        man_ok = len(rows) == ev["pin_count"] and all(len(r.split()) == 3 for r in rows)
    else:
        man_ok = sha(HERE / "env/Manifest.toml") == ev["manifest_sha256"]
    ok = not missing and man_ok and sys.version_info >= (3, 11)
    print(json.dumps({"preflight": ok, "packet": PK_FILE, "device": PK.get("device", "cpu"), "missing": missing,
                      "env_pinned": man_ok,
                      "python": sys.version.split()[0], "cases": [c["run_id"] for c in PK["cases"]],
                      "outer_budget_s": OUTER, "threads_total": sum(c["threads"] for c in PK["cases"])}))
    return 0 if ok else 8


def st_julia() -> bool:
    if os.environ.get("CFD3D_JULIA"):
        return stage("julia", julia_bin().exists(), source="CFD3D_JULIA (local)", path=str(julia_bin()))
    WORK.mkdir(parents=True, exist_ok=True)
    tgz = WORK / "julia.tar.gz"
    if not tgz.exists():
        urllib.request.urlretrieve(JULIA_PIN["url"], tgz)
    got = sha(tgz)
    if got != JULIA_PIN["sha256"]:
        return stage("julia", False, sha256=got, want=JULIA_PIN["sha256"])
    with tarfile.open(tgz) as tf:
        try:
            tf.extractall(WORK, filter="fully_trusted")   # official tarball, sha256 checked; keeps its links
        except TypeError:                                 # Python < 3.11.4 has no filter, and trusts fully
            tf.extractall(WORK)
    return stage("julia", julia_bin().exists(), sha256=got)


ENV_JL = r'''
using Pkg
Pkg.instantiate(); Pkg.precompile()
using WaterLily, StaticArrays, JSON, SHA, Serialization
println("CFD3D-ENV WaterLily ", pkgversion(WaterLily), " threads ", Threads.nthreads())
'''


# Pins every package at the recorded version (gpu_entry's proven recipe), then refuses unless the resolved
# Manifest's canonical (name, uuid, version, git-tree-sha1) list hashes to the digest of the local Manifest.
ENV_PINS_JL = r'''
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
using WaterLily, StaticArrays, JSON, Serialization
if ARGS[3] == "cuda"
    using CUDA
    println("CUDA functional ", CUDA.functional(), " ", CUDA.functional() ? CUDA.name(CUDA.device()) : "")
    CUDA.functional() || exit(4)
end
println("CFD3D-ENV WaterLily ", pkgversion(WaterLily))
'''


def st_env() -> bool:
    global PROJECT
    ev = PK["env"]
    if ev.get("pins"):
        env_dir = WORK / "env"
        env_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(JOB / ev["project"], env_dir / "Project.toml")
        (WORK / "env.jl").write_text(ENV_PINS_JL)
        (WORK / "logs").mkdir(parents=True, exist_ok=True)
        rc, _ = run_capped([f"--project={env_dir}", str(WORK / "env.jl"), str(JOB / ev["pins"]),
                            ev["canonical_sha256"], PK.get("device", "cpu")], 2, 8, ev["timeout_s"],
                           WORK / "logs/env.log")
        if (env_dir / "Manifest.toml").exists():
            shutil.copy(env_dir / "Manifest.toml", OUT / "resolved-Manifest.toml")
        PROJECT = env_dir
        return stage("env", rc == 0, rc=rc, log_tail=tail(WORK / "logs/env.log"))
    env = HERE / "env"
    before = sha(env / "Manifest.toml")
    (WORK / "logs").mkdir(parents=True, exist_ok=True)
    rc, _ = run_capped([f"--project={env}", "-e", ENV_JL], 2, 6, PK["env"]["timeout_s"], WORK / "logs/env.log")
    after = sha(env / "Manifest.toml")
    ok = rc == 0 and before == after == PK["env"]["manifest_sha256"]
    return stage("env", ok, rc=rc, manifest_sha256=after, log_tail=tail(WORK / "logs/env.log"))


def tail(p: Path, n: int = 12) -> str:
    return "\n".join(p.read_text(errors="replace").splitlines()[-n:]) if p.exists() else ""


def cyl(out: Path, run_id: str, threads: int, mem_gb: float, timeout: float, log_to: Path, *mode,
        gpu: bool = False, **extra):
    return run_capped([f"--project={PROJECT}", str(HERE / "cyl2d.jl"), str(out), run_id, *mode],
                      threads, mem_gb, timeout, log_to, gpu, **extra)


COMPARE_JL = r'''
using Serialization
a, b = open(deserialize, ARGS[1]), open(deserialize, ARGS[2])
same = a["dt"] == b["dt"] && length(a["arrays"]) == length(b["arrays"]) &&
       all(x == y for (x, y) in zip(a["arrays"], b["arrays"]))
println(same ? "STATE IDENTICAL" : "STATE DIFFERS")
exit(same ? 0 : 1)
'''


TEST_T0 = 8.0      # T_restart's t0 in cyl2d.jl TEST_RUNS (restated here for the after-split Cp count)


def st_restart_check() -> bool:
    rc_spec = PK["restart_check"]
    d = WORK / "restart_check"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    lg, th, mem, to = d / "log.txt", rc_spec["threads"], rc_spec["mem_gb"], rc_spec["timeout_s"]
    r_a, _ = cyl(d / "a.json", "T_restart", th, mem, to, lg, CFD3D_CKPT=d / "a.ckpt")
    r_b1, _ = cyl(d / "b.json", "T_restart", th, mem, to, lg, CFD3D_CKPT=d / "b.ckpt",
                  CFD3D_SEGMENT_STEPS=rc_spec["split_after_steps"])
    split_file_absent = not (d / "b.json").exists()
    r_b2, _ = cyl(d / "b.json", "T_restart", th, mem, to, lg, CFD3D_CKPT=d / "b.ckpt")
    info = {"rc_straight": r_a, "rc_first_segment": r_b1, "rc_resumed": r_b2,
            "first_segment_wrote_no_output": split_file_absent}
    if r_a == 0 and r_b2 == 0:
        a, b = json.loads((d / "a.json").read_text()), json.loads((d / "b.json").read_text())
        info["series_identical"] = all(a[k] == b[k] for k in ("t", "Cd", "Cd_p", "Cl")) and \
            a["surface"]["Cp_wall_mean"] == b["surface"]["Cp_wall_mean"]
        info["segments"] = [a["segments"], b["segments"]]
        info["steps"] = [a["steps"], b["steps"]]
        info["cp_samples"] = [a["surface"]["samples"], b["surface"]["samples"]]
        split_t = b["t"][rc_spec["split_after_steps"] - 1]          # Cp is sampled every 10th step after t0
        info["cp_after_split"] = sum(1 for k, t in enumerate(b["t"], 1) if t > split_t and k % 10 == 0
                                     and t >= TEST_T0)
        cmp = subprocess.run([str(julia_bin()), "--startup-file=no", "-e", COMPARE_JL, str(d / "a.ckpt"),
                              str(d / "b.ckpt")], env=julia_env(1), capture_output=True, text=True, timeout=600)
        info["final_state_identical"] = cmp.returncode == 0
        # negative control: the same checkpoint offered to another run id must be refused
        shutil.copy(d / "b.ckpt", d / "neg.ckpt")
        r_neg, _ = cyl(d / "neg.json", "R1", th, 4, to, d / "neg.txt", CFD3D_CKPT=d / "neg.ckpt")
        info["foreign_checkpoint_refused"] = r_neg != 0 and "checkpoint refused" in (d / "neg.txt").read_text()
    ok = (r_b1 == 75 and info["first_segment_wrote_no_output"] and info.get("series_identical") is True
          and info.get("final_state_identical") is True and info.get("foreign_checkpoint_refused") is True
          and info["segments"] == [1, 2]
          and info["steps"][1] - rc_spec["split_after_steps"] >= rc_spec["min_steps_after_split"]
          and info["cp_after_split"] >= rc_spec["min_cp_samples_after_split"])
    if GPU and ok:
        info["cuda"] = cuda_restart_arm(d, rc_spec)
        ok = info["cuda"]["ok"]
    (OUT / "restart_check.json").write_text(json.dumps(info, indent=1))
    return stage("restart_check", ok, **info)


def series_gap(a: dict, b: dict, shift: int = 0, n: int | None = None) -> dict:
    """Largest differences between two force series, b shifted by `shift` steps, over the first n samples."""
    n = n or min(len(a["Cd"]), len(b["Cd"]) - shift)
    scale = sum(abs(x) for x in a["Cd"][:n]) / n
    rel = {k: max(abs(x - y) for x, y in zip(a[k][:n], b[k][shift:shift + n])) / scale for k in ("Cd", "Cd_p", "Cl")}
    rel["t"] = max(abs(x - y) / abs(x) for x, y in zip(a["t"][:n], b["t"][shift:shift + n]))
    rel["n"] = n
    return rel


def within(gap: dict, tol: dict) -> bool:
    """Every compared quantity at or under its frozen tolerance (forces relative to mean |Cd|)."""
    return all(gap[k] <= tol[k] for k in ("Cd", "Cd_p", "Cl", "t"))


def cuda_restart_arm(d: Path, rc_spec: dict) -> dict:
    """The same split + resume on the device. Bit identity is recorded; the gate is the same-state tolerance."""
    tol = PK["same_state"]["tolerance"]
    lg, mem, to = d / "cuda_log.txt", rc_spec["mem_gb"], rc_spec["timeout_s"]
    r_a, _ = cyl(d / "ga.json", "T_restart", 2, mem, to, lg, gpu=True, CFD3D_CKPT=d / "ga.ckpt")
    r_b1, _ = cyl(d / "gb.json", "T_restart", 2, mem, to, lg, gpu=True, CFD3D_CKPT=d / "gb.ckpt",
                  CFD3D_SEGMENT_STEPS=rc_spec["split_after_steps"])
    r_b2, _ = cyl(d / "gb.json", "T_restart", 2, mem, to, lg, gpu=True, CFD3D_CKPT=d / "gb.ckpt")
    arm = {"rc": [r_a, r_b1, r_b2], "log_tail": tail(lg, 8)}
    if r_a == 0 and r_b1 == 75 and r_b2 == 0:
        a, b = json.loads((d / "ga.json").read_text()), json.loads((d / "gb.json").read_text())
        arm["bit_identical"] = all(a[k] == b[k] for k in ("t", "Cd", "Cd_p", "Cl"))
        arm["gap"] = series_gap(a, b) if len(a["t"]) == len(b["t"]) else None
        arm["gpu"] = [a["gpu"], b["gpu"]]
        arm["ok"] = arm["gap"] is not None and within(arm["gap"], tol) and a["gpu"] is True
    else:
        arm["ok"] = False
    return arm


SERIES_JL = r'''
using Serialization, JSON
base, x, y = (open(deserialize, f) for f in ARGS[1:3])
n0 = length(base["rec"]["t"])
part(s) = Dict(k => s["rec"][k][n0+1:end] for k in ("t", "Cd", "Cd_p", "Cl"))
du = maximum(abs.(x["arrays"][1] .- y["arrays"][1]))
JSON.print(stdout, Dict("n0" => n0, "t0" => base["rec"]["t"][end], "cpu" => part(x), "cuda" => part(y),
                        "max_abs_du" => du, "steps" => [x["rec"]["steps"], y["rec"]["steps"]]))
'''


def st_platform() -> bool:
    """Same-state CPU/CUDA control on T_same (see the module docstring); tolerances frozen in the packet."""
    ss = PK["same_state"]
    d = WORK / "platform"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    lg = d / "log.txt"
    r0, _ = cyl(d / "base.json", "T_same", ss["cpu_threads"], 4, ss["timeout_s"], lg, CFD3D_CKPT=d / "base.ckpt",
                CFD3D_SEGMENT_T=ss["t_state"])
    info = {"rc_base": r0}
    if r0 != 75:
        return stage("platform", False, **info, log_tail=tail(lg))
    shutil.copy(d / "base.ckpt", d / "cpu.ckpt")
    shutil.copy(d / "base.ckpt", d / "cuda.ckpt")
    n = ss["steps"] + ss["shift"]
    r1, _ = cyl(d / "cpu.json", "T_same", ss["cpu_threads"], 4, ss["timeout_s"], lg, CFD3D_CKPT=d / "cpu.ckpt",
                CFD3D_SEGMENT_STEPS=n)
    r2, _ = cyl(d / "cuda.json", "T_same", 2, 6, ss["timeout_s"], lg, gpu=not DRY_RUN, CFD3D_CKPT=d / "cuda.ckpt",
                CFD3D_SEGMENT_STEPS=n)
    info.update(rc_cpu=r1, rc_cuda=r2)
    if r1 != 75 or r2 != 75:
        return stage("platform", False, **info, log_tail=tail(lg))
    p = subprocess.run([str(julia_bin()), "--startup-file=no", f"--project={PROJECT}", "-e", SERIES_JL,
                        str(d / "base.ckpt"), str(d / "cpu.ckpt"), str(d / "cuda.ckpt")], env=julia_env(1),
                       capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        return stage("platform", False, **info, stderr=p.stderr[-1500:])
    r = json.loads(p.stdout)
    tol = ss["tolerance"]
    aligned = series_gap(r["cpu"], r["cuda"], 0, ss["steps"])
    shifted = series_gap(r["cpu"], r["cuda"], ss["shift"], ss["steps"])
    info.update(t_state=r["t0"], steps=r["steps"], aligned=aligned, shifted=shifted, max_abs_du=r["max_abs_du"],
                tolerance=tol, aligned_within=within(aligned, tol), shifted_within=within(shifted, tol))
    (OUT / "platform.json").write_text(json.dumps(dict(info, series=r), indent=1))
    ok = info["aligned_within"] and not info["shifted_within"] and r["max_abs_du"] <= tol["u_abs"]
    if DRY_RUN:                                   # both arms ran on the CPU: evidence about the check, never a pass
        info["dry_run_would_pass"], ok = ok, False
    return stage("platform", ok, **info)


def gpu_memory_poll(stop: threading.Event, rows: list) -> None:
    """Device memory used/total (MiB) every 2 s from nvidia-smi while the calibration runs."""
    smi = shutil.which("nvidia-smi")
    while smi and not stop.wait(2):
        q = subprocess.run([smi, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True)
        try:
            rows.append([int(x) for x in q.stdout.split("\n")[0].split(",")])
        except ValueError:
            continue


CALIB: dict[str, dict] = {}       # run id -> calibrated projection, read by the sequential cases stage


def calib_arms(cb: dict) -> list[dict]:
    """The timed cases: "arms" (one per planned case) or the single-case form ("run_id", "steps_projected")."""
    return cb.get("arms") or [{"run_id": cb["run_id"], "steps_projected": cb["steps_projected"]}]


def time_arm(cb: dict, arm: dict, d: Path) -> tuple[dict, float]:
    stop, mem_rows = threading.Event(), []
    poll = threading.Thread(target=gpu_memory_poll, args=(stop, mem_rows), daemon=True)
    poll.start()
    rid, t_start = arm["run_id"], time.time()
    out = d / f"{rid.lower()}_timing.json" if "arms" in cb else d / "r2_timing.json"
    rc, peak = cyl(out, rid, 2, cb["host_rss_max_gb"], cb["timeout_s"], d / f"log-{rid}.txt", "TIMING", cb["steps"],
                   gpu=True)
    proc_s = time.time() - t_start
    stop.set()
    poll.join(timeout=10)
    info = {"rc": rc, "peak_host_rss_gb": round(peak, 2),
            "gpu_mem_peak_mib": max((r[0] for r in mem_rows), default=None),
            "gpu_mem_total_mib": mem_rows[0][1] if mem_rows else None}
    if rc == 0:
        r = json.loads(out.read_text())
        step_s = r["wall_s"] / r["steps"]
        lo, hi = arm["steps_projected"]
        # process start-up (Julia load, kernel compile, grid set-up) is paid again by the case's own process
        start_s = max(0.0, proc_s - r["wall_s"]) if "arms" in cb else 0.0
        info.update(ms_per_step=round(1e3 * step_s, 3), ns_per_cell_step=r["ns_per_cell_step"],
                    dt_grid_last=r["dt_grid_last"], gpu=r["gpu"], startup_s=round(start_s, 1),
                    projected_wall_s=[round(n * step_s * cb["run_overhead"] + start_s) for n in (lo, hi)])
    mem_ok = info["gpu_mem_peak_mib"] is not None and \
        info["gpu_mem_peak_mib"] <= cb["gpu_mem_frac_max"] * info["gpu_mem_total_mib"]
    info["fits_memory"] = mem_ok and peak <= cb["host_rss_max_gb"]
    info["arm_ok"] = rc == 0 and info.get("gpu") is True and info["fits_memory"]
    return info, peak


def st_calibration() -> bool:
    """Force-free TIMING of every planned case on the device and the frozen go/no-go rule: the cases start only
    if the sum over cases of steps_projected[1] x measured s/step x run_overhead (+ each case's measured process
    start-up, in the arms form) fits in the time left for cases, every device-memory peak is under
    gpu_mem_frac_max of the card and every host RSS under host_rss_max_gb. A no-go stops the packet (rc 11)
    with the controls and these measurements kept. The single-case form (R2 packet) is the one-arm case."""
    cb = PK["calibration"]
    d = WORK / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    arms = {}
    for arm in calib_arms(cb):
        arms[arm["run_id"]], _ = time_arm(cb, arm, d)
        if not arms[arm["run_id"]]["arm_ok"]:
            break                                   # one failed arm decides the no-go; do not spend more device time
    rows = list(arms.values())
    info = {"rule": cb["rule"]} | ({"arms": arms} if "arms" in cb else rows[0])
    timed = len(rows) == len(calib_arms(cb)) and all(r["arm_ok"] for r in rows)
    if timed:
        lo, hi = (sum(r["projected_wall_s"][i] for r in rows) for i in (0, 1))
        case_left = left() - PK["ckpt_margin_s"]
        info.update(projected_wall_s=[lo, hi], left_s=round(left()), fits_time=hi <= case_left,
                    fits_time_lower_only=lo <= case_left < hi)
        CALIB.update(arms if "arms" in cb else {cb["run_id"]: info})
    info["go"] = timed and info.get("fits_time") is True and all(r["fits_memory"] for r in rows)
    (OUT / "calibration.json").write_text(json.dumps(info, indent=1))
    return stage("calibration", info["go"], **info)


def st_telemetry() -> bool:
    smi = shutil.which("nvidia-smi")
    if smi:
        (OUT / "nvidia-smi.txt").write_text(subprocess.run([smi], capture_output=True, text=True).stdout)
    return stage("telemetry", bool(smi))


def st_output() -> bool:
    """The returned science outputs against max_out_bytes; exported checkpoints have their own cap (EXPORT_MAX)."""
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file() and EXPORT not in f.parents)
    return stage("output", size <= PK["max_out_bytes"], bytes=size, cap=PK["max_out_bytes"])


def st_scaling() -> bool:
    sc = PK["scaling"]
    d = WORK / "scaling"
    d.mkdir(parents=True, exist_ok=True)
    rows = {}
    for th in sc["threads"]:
        rc, peak = cyl(d / f"t{th}.json", sc["run_id"], th, sc["mem_gb"], sc["timeout_s"], d / f"t{th}.log",
                       "TIMING", sc["steps"])
        r = json.loads((d / f"t{th}.json").read_text()) if rc == 0 else {}
        rows[th] = {"rc": rc, "peak_rss_gb": round(peak, 2), "ns_per_cell_step": r.get("ns_per_cell_step"),
                    "dt_grid_last": r.get("dt_grid_last")}
    (OUT / "scaling.json").write_text(json.dumps({"mode": "TIMING (force-free)", "rows": rows}, indent=1))
    return stage("scaling", True, rows=rows)        # telemetry, never a gate


def case_worker(c: dict) -> None:
    rid = c["run_id"]
    d = WORK / "cases" / rid
    d.mkdir(parents=True, exist_ok=True)
    out, ck, lg = d / f"{rid}.json", d / f"{rid}.ckpt", d / "log.txt"
    if RESUME and not ck.exists():
        seed = newest_snapshot(rid)
        if seed:
            shutil.copy(seed, ck)
            rec_seed = {"resumed_from": seed.name, "sha256": sha(ck)}
            with LOCK:
                status["cases"].setdefault(rid, {})["seed"] = rec_seed
    rec = {"threads": c["threads"], "mem_gb": c["mem_gb"], "budget_s": c["budget_s"], "segments": [],
           "state": "running", "exports": []}
    with LOCK:
        rec.update(status["cases"].get(rid, {}))
        status["cases"][rid] = rec
    t_export = time.time()
    save()
    t_case = time.time()
    proj = CALIB.get(rid, {}).get("projected_wall_s")
    if PK.get("cases_sequential") and proj and not out.exists() and proj[1] > left() - PK["ckpt_margin_s"]:
        rec.update(state="not started: calibrated projection exceeds time left", projected_wall_s=proj,
                   left_s=round(left()))
        save()
        return
    while not out.exists():
        # the process also compiles, loads and writes a checkpoint: that margin must fit inside what is left
        budget = min(PK["segment_s"], c["budget_s"] - (time.time() - t_case), left() - PK["ckpt_margin_s"])
        if budget < PK["min_segment_s"]:
            rec["state"] = "stopped at budget (checkpoint kept)" if ck.exists() else "not started: no budget"
            if ck.exists():
                export_ckpt(rid, ck, rec, "stopped at budget", reserve=False)
            break
        rc, peak = cyl(out, rid, c["threads"], c["mem_gb"], budget + PK["ckpt_margin_s"], lg,
                       gpu=c.get("gpu", False), CFD3D_CKPT=ck,
                       CFD3D_SEGMENT_S=int(budget), CFD3D_CKPT_EVERY_S=PK["ckpt_every_s"])
        rec["segments"].append({"rc": rc, "peak_rss_gb": round(peak, 2), "t_s": round(time.time() - T0, 1)})
        if rc == 75 and time.time() - t_export >= PK["export_every_s"]:
            export_ckpt(rid, ck, rec, "periodic")
            t_export = time.time()
        save()
        if rc not in (0, 75):
            rec["state"] = f"failed rc={rc}"
            rec["log_tail"] = tail(lg)
            break
    if out.exists():
        r = json.loads(out.read_text())
        rec.update(state="finished", steps=r["steps"], t_end_reached=r["t_end_reached"], finite=r["finite"],
                   wall_s=r["wall_s"], ns_per_cell_step=r["ns_per_cell_step"], segments_in_run=r["segments"])
        (OUT / "runs").mkdir(parents=True, exist_ok=True)
        with gzip.open(OUT / "runs" / f"{rid}.json.gz", "wb", compresslevel=6) as fh:
            fh.write(out.read_bytes())
        rec["output_sha256"] = sha(out)
    if ck.exists():
        rec["checkpoint_local"] = {"path": str(ck), "bytes": ck.stat().st_size, "exported": False}
    save()


EXPORTED = {"bytes": 0}


def export_ckpt(rid: str, ck: Path, rec: dict, why: str, reserve: bool = True) -> None:
    """Copy one complete checkpoint version into OUT/checkpoints and list it in the manifest (see docstring)."""
    with open(ck, "rb") as src:                      # the descriptor pins one version even if Julia renames over
        st = os.fstat(src.fileno())
        size = st.st_size
        if rec.get("exported_version") == (st.st_ino, st.st_mtime_ns):
            rec["exports"].append({"why": why, "skipped": "unchanged since the last export"})
            return
        cap = EXPORT_MAX - (PK["export_reserve_bytes"] if reserve else 0)
        with LOCK:
            if EXPORTED["bytes"] + size > cap:
                rec["exports"].append({"why": why, "skipped": f"would pass the export cap ({cap} B)"})
                return
            EXPORTED["bytes"] += size
            n = len([e for e in rec["exports"] if "file" in e]) + 1
        EXPORT.mkdir(parents=True, exist_ok=True)
        part, final = EXPORT / f"{rid}-{n}.ckpt.partial", EXPORT / f"{rid}-{n}.ckpt"
        h = hashlib.sha256()
        with open(part, "wb") as dst:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                h.update(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
    part.replace(final)
    rec["exported_version"] = (st.st_ino, st.st_mtime_ns)
    row = {"file": final.name, "run_id": rid, "bytes": size, "sha256": h.hexdigest(), "why": why,
           "t_s": round(time.time() - T0, 1)}
    with LOCK:
        rec["exports"].append(row)
        man = EXPORT / "manifest.json"
        rows = json.loads(man.read_text())["snapshots"] if man.exists() else []
        tmp = EXPORT / "manifest.json.partial"
        tmp.write_text(json.dumps({"schema": "cfd3d-ckpt-manifest-0.1", "coherent_only_if_listed": True,
                                   "snapshots": rows + [row]}, indent=1))
        tmp.replace(man)
    log(f"exported checkpoint {final.name} ({size} B, {why})")


def newest_snapshot(rid: str) -> Path | None:
    man = RESUME / "manifest.json"
    if not man.exists():
        return None
    for row in reversed(json.loads(man.read_text())["snapshots"]):
        p = RESUME / row["file"]
        if row["run_id"] == rid and p.exists() and p.stat().st_size == row["bytes"] and sha(p) == row["sha256"]:
            return p
    return None


def st_cases() -> bool:
    if PK.get("cases_sequential"):                  # one device: one arm at a time, in packet order
        for c in PK["cases"]:
            case_worker(c)
    else:
        ts = [threading.Thread(target=case_worker, args=(c,), name=c["run_id"]) for c in PK["cases"]]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    states = {k: v["state"] for k, v in status["cases"].items()}
    return stage("cases", True, states=states, all_finished=all(s == "finished" for s in states.values()))


def st_eval() -> bool:
    runs = [f"{rid}={WORK / 'cases' / rid / f'{rid}.json'}" for rid, v in status["cases"].items()
            if v["state"] == "finished"]
    if not runs:
        return stage("eval", False, reason="no finished run")
    p = subprocess.run([sys.executable, "-I", str(HERE / "cyl2d_eval.py"), str(OUT / "eval.json"), *runs],
                       capture_output=True, text=True, timeout=1200)
    v = json.loads((OUT / "eval.json").read_text())["verdict"] if p.returncode == 0 else None
    return stage("eval", p.returncode == 0, verdict=v, stderr=p.stderr[-2000:])


STAGES = {"telemetry": st_telemetry, "julia": st_julia, "env": st_env, "restart_check": st_restart_check,
          "platform": st_platform, "scaling": st_scaling, "calibration": st_calibration, "cases": st_cases,
          "eval": st_eval, "output": st_output}
GATE_RC = {"julia": 2, "env": 3, "restart_check": 4, "platform": 5, "eval": 7, "calibration": 11}


def facts() -> dict:
    f = {"nproc": os.cpu_count(), "python": sys.version.split()[0]}
    for name, argv in (("lscpu", ["lscpu"]), ("free", ["free", "-g"])):
        if shutil.which(argv[0]):
            f[name] = subprocess.run(argv, capture_output=True, text=True).stdout[-3000:]
    return f


def main(argv: list[str]) -> int:
    if os.environ.get("PREFLIGHT") == "1":
        return preflight()
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    status["host"] = facts()
    status["packet_file_sha256"] = sha(HERE / PK_FILE)
    save()
    incomplete = False
    try:
        for name in argv or PK.get("stages", ["julia", "env", "restart_check", "scaling", "cases", "eval"]):
            ok = STAGES[name]()
            if not ok and name in GATE_RC:
                return finish(GATE_RC[name])
            incomplete |= not ok and name == "output"
    except Exception as e:                                  # noqa: BLE001 - recorded, never swallowed
        status["exception"] = repr(e)
        return finish(1)
    done = all(v["state"] == "finished" for v in status["cases"].values()) and status["cases"]
    return finish(0 if done and not incomplete else 10)


if __name__ == "__main__":
    raise SystemExit(main(ARGS))
