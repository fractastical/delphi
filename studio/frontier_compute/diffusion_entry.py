"""Execute frozen diffusion control/training stages with a same-allocation gate."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


PACKET_SHA = "76eb4a7b273f71db51d6f8d35481dfe94a36b49414372c919d3387e67d75821c"


def require_gate(path):
    if not path.exists():
        raise RuntimeError("Same-allocation CUDA control gate is missing")
    gate = json.loads(path.read_text())
    if gate.get("packet_sha256") != PACKET_SHA or gate.get("ok") is not True:
        raise RuntimeError("Same-allocation CUDA control gate failed or belongs to another packet")


def main():
    mode = sys.argv[1]
    archive = Path("artifacts/rd-diffusion/packet/rd_ddpm_packet.tar.gz")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PACKET_SHA:
        raise ValueError("Diffusion packet hash mismatch")
    work = Path("rd-runtime").resolve()
    work.mkdir(exist_ok=True)
    with tarfile.open(archive) as packet:
        packet.extractall(work, filter="data")
    source = work / "rd_diffusion"
    gate = work / "control_gate.json"
    out = Path(os.environ["COPS_OUT"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
    argv = [sys.executable, "rd_ddpm.py"]
    if os.environ.get("PREFLIGHT"):
        subprocess.run(argv + ["preflight", "--out", str(out)], cwd=source, env=env, check=True, timeout=60)
        return
    if mode == "control":
        subprocess.run(argv + ["preflight", "--out", str(out)], cwd=source, env=env, check=True, timeout=60)
        subprocess.run(argv + ["control", "--out", str(out)], cwd=source, env=env, check=True, timeout=180)
        control = json.loads((out / "control.json").read_text())
        if control.get("ok") is not True:
            raise RuntimeError("CUDA control did not pass")
        gate.write_text(json.dumps({"packet_sha256": PACKET_SHA, "ok": True,
                                    "control_sha256": hashlib.sha256((out / "control.json").read_bytes()).hexdigest()}))
        shutil.copyfile(gate, out / "gate.json")
    elif mode == "train-evaluate":
        require_gate(gate)
        # The frozen run function selects a backend. Require CUDA explicitly so
        # a missing device cannot silently turn the cloud training into CPU work.
        subprocess.run([sys.executable, "-c", "import torch; assert torch.cuda.is_available()"], cwd=source, env=env, check=True, timeout=30)
        subprocess.run(argv + ["run", "--out", str(out)], cwd=source, env=env, check=True, timeout=1800)
        for name in ("checkpoint.pt", "evaluation.json", "examples.npz", "train_loss.jsonl"):
            if not (out / name).is_file():
                raise RuntimeError("Missing diffusion output: " + name)
    else:
        raise ValueError("Unknown diffusion stage")


if __name__ == "__main__":
    main()
