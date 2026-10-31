"""Tiny injected launcher: verify and unpack the cfd3d packet, then run its gpu_entry (stdlib only).

    python3 engineering/cfd3d/cfd3d_launch.py artifacts/cfd3d/packet/cfd3d-packet.tar.gz SHA256
"""
import hashlib
import os
import subprocess
import sys
import tarfile
from pathlib import Path

tgz, want = Path(sys.argv[1]), sys.argv[2]
got = hashlib.sha256(tgz.read_bytes()).hexdigest()
if got != want:
    print(f"CFD3D refused: packet sha256 {got} != {want}", flush=True)
    sys.exit(9)
dst = Path("/work/cfd3d_job")
dst.mkdir(parents=True, exist_ok=True)
with tarfile.open(tgz) as tf:
    tf.extractall(dst, filter="data")
sys.exit(subprocess.run([sys.executable, "engineering/cfd3d/gpu_entry.py"], cwd=dst,
                        env=dict(os.environ, CFD3D_PACKET_SHA256=got)).returncode)
