"""Warm-worker workload: the wind-tunnel worker's frozen portable CUDA bundle (code and protocol authored by the wind-tunnel worker, branch work/fish-windtunnel @ db354c9; not edited here).
Verifies the archive sha256 and every file sha256 from portable-bundle.json, extracts, and runs their exact command with --output set to $COPS_OUT/out. PREFLIGHT=1: verify + import only."""
import hashlib, json, os, subprocess, sys, tarfile
ARCH = "inputs/windtunnel/portable-cuda-bundle.tar.gz"; MAN = "inputs/windtunnel/portable-bundle.json"
sha = lambda b: hashlib.sha256(b).hexdigest()
man = json.load(open(MAN)); raw = open(ARCH, "rb").read()
assert sha(raw) == man["archive_sha256"] and len(raw) == man["archive_bytes"], "archive hash mismatch"
dst = "/work/job/wt" if os.path.isdir("/work/job") else os.path.join(os.environ.get("COPS_OUT", "."), "wt_extract")
os.makedirs(dst, exist_ok=True)
tarfile.open(ARCH).extractall(dst)
for f, m in man["files"].items():
    b = open(os.path.join(dst, f), "rb").read()
    assert sha(b) == m["sha256"] and len(b) == m["bytes"], f"file hash mismatch: {f}"
print("bundle verified:", len(man["files"]), "files", flush=True)
env = dict(os.environ, PYTHONPATH=dst, OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONUNBUFFERED="1")
protocol = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else "artifacts/windtunnel/cuda-protocol.json"
if len(sys.argv) > 1:
    proposal = json.load(open(protocol))
    if proposal.get("prerequisite", {}).get("repeat_passed") is not True:
        raise ValueError("AoA sweep requires a recorded passing CPU/CUDA parity result")
    if not os.environ.get("PREFLIGHT"):
        gate = json.load(open("infra-parity-gate.json"))
        if gate.get("repeat_passed") is not True:
            raise ValueError("same-allocation CPU/CUDA parity prerequisite failed")
if os.environ.get("PREFLIGHT"):
    r = subprocess.run([sys.executable, "-c", "import engineering.windtunnel.remote, torch; print('preflight ok: import', torch.__version__)"], cwd=dst, env=env, capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-300:]); sys.exit(r.returncode)
out = os.path.join(os.environ["COPS_OUT"], "out")
r = subprocess.run([sys.executable, "-m", "engineering.windtunnel.remote", "run", protocol, "--output", out], cwd=dst, env=env)
if len(sys.argv) == 1 and r.returncode == 0:
    checks = json.load(open(os.path.join(out, "checks.json")))
    json.dump(checks, open("infra-parity-gate.json", "w"), indent=2)
    if checks.get("repeat_passed") is not True:
        raise ValueError("CPU/CUDA parity failed; subsequent AoA workloads must refuse")
sys.exit(r.returncode)
