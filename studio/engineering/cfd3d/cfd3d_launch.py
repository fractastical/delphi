"""Injected launcher: verify the cfd3d packet sha256, unpack it, run its gpu_entry (stdlib only).

    python3 engineering/cfd3d/cfd3d_launch.py PACKET.tar.xz SHA256 [ENTRY]
ENTRY defaults to engineering/cfd3d/gpu_entry.py (the diagnostic packet passes engineering/cfd3d/diag_candidate.py).
PREFLIGHT=1 unpacks into a temporary directory and runs only the packaging check (no download, Julia or CUDA).
"""
import hashlib
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

tgz, want = Path(sys.argv[1]), sys.argv[2]
entry = sys.argv[3] if len(sys.argv) > 3 else "engineering/cfd3d/gpu_entry.py"
got = hashlib.sha256(tgz.read_bytes()).hexdigest()
if got != want:
    print(f"CFD3D refused: packet sha256 {got} != {want}", flush=True)
    sys.exit(9)
pre = os.environ.get("PREFLIGHT") == "1"
dst = Path(tempfile.mkdtemp(prefix="cfd3d_pre_")) if pre else Path("/work/cfd3d_job")
dst.mkdir(parents=True, exist_ok=True)
with tarfile.open(tgz) as tf:
    tf.extractall(dst, filter="data")
rc = subprocess.run([sys.executable, entry], cwd=dst,
                    env=dict(os.environ, CFD3D_PACKET_SHA256=got)).returncode
print(f"CFD3D launcher rc={rc} preflight={pre} dir={dst}", flush=True)
sys.exit(rc)
