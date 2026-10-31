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
if os.environ.get("PREFLIGHT"):
    r = subprocess.run([sys.executable, "-c", "import engineering.windtunnel.remote, torch; print('preflight ok: import', torch.__version__)"], cwd=dst, env=env, capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-300:]); sys.exit(r.returncode)
out = os.path.join(os.environ["COPS_OUT"], "out")
r = subprocess.run([sys.executable, "-m", "engineering.windtunnel.remote", "run", "artifacts/windtunnel/cuda-protocol.json", "--output", out], cwd=dst, env=env)
sys.exit(r.returncode)
