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


def require_gate(path, backend_policy=None):
    if not path.exists():
        raise RuntimeError("Same-allocation CUDA control gate is missing")
    gate = json.loads(path.read_text())
    if gate.get("packet_sha256") != PACKET_SHA or gate.get("ok") is not True:
        raise RuntimeError("Same-allocation CUDA control gate failed or belongs to another packet")
    if backend_policy is not None and gate.get("backend_policy_sha256") != backend_policy:
        raise RuntimeError("Same-allocation gate belongs to another numerical backend policy")


def ieee_argv():
    """Set explicit full-FP32 backend policy before executing unchanged source."""
    return [sys.executable, "-c", "import json,os,runpy,sys,torch; "
            "torch.backends.cuda.matmul.allow_tf32=False; torch.backends.cudnn.allow_tf32=False; "
            "torch.set_float32_matmul_precision('highest'); "
            "print('BACKEND_POLICY '+json.dumps({'NVIDIA_TF32_OVERRIDE':os.environ.get('NVIDIA_TF32_OVERRIDE'),"
            "'matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32,'cudnn_allow_tf32':torch.backends.cudnn.allow_tf32,"
            "'float32_matmul_precision':torch.get_float32_matmul_precision()}),flush=True); "
            "sys.argv=['rd_ddpm.py']+sys.argv[1:]; runpy.run_path('rd_ddpm.py',run_name='__main__')"]


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
    policy_path = Path("inputs/diffusion-backend-policy.json")
    policy = hashlib.sha256(policy_path.read_bytes()).hexdigest() if policy_path.exists() else None
    strict = mode in ("precision-control", "precision-train-evaluate")
    strict_env = {**env, "NVIDIA_TF32_OVERRIDE": "0", "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "0"}
    if os.environ.get("PREFLIGHT"):
        subprocess.run(argv + ["preflight", "--out", str(out)], cwd=source, env=env, check=True, timeout=60)
        return
    if mode in ("control", "precision-control"):
        subprocess.run(argv + ["preflight", "--out", str(out)], cwd=source, env=env, check=True, timeout=60)
        if strict:
            if policy is None:
                raise RuntimeError("Frozen numerical backend policy is missing")
            baseline = out / "default-backend"
            baseline.mkdir(exist_ok=True)
            probe = subprocess.run(argv + ["control", "--out", str(baseline)], cwd=source, env=env, check=False, timeout=180)
            (out / "default-probe-exit.json").write_text(json.dumps({"rc": probe.returncode}))
            if probe.returncode not in (0, 3):
                raise RuntimeError("Default diagnostic failed outside numerical control")
        subprocess.run((ieee_argv() if strict else argv) + ["control", "--out", str(out)],
                       cwd=source, env=strict_env if strict else env, check=True, timeout=180)
        control = json.loads((out / "control.json").read_text())
        if control.get("ok") is not True:
            raise RuntimeError("CUDA control did not pass")
        gate.write_text(json.dumps({"packet_sha256": PACKET_SHA, "ok": True,
                                    "control_sha256": hashlib.sha256((out / "control.json").read_bytes()).hexdigest(),
                                    "backend_policy_sha256": policy if strict else None}))
        shutil.copyfile(gate, out / "gate.json")
        if strict:
            shutil.copyfile(policy_path, out / "backend-policy.json")
    elif mode in ("train-evaluate", "precision-train-evaluate"):
        if strict and policy is None:
            raise RuntimeError("Frozen numerical backend policy is missing")
        require_gate(gate, policy if strict else None)
        # The frozen run function selects a backend. Require CUDA explicitly so
        # a missing device cannot silently turn the cloud training into CPU work.
        subprocess.run([sys.executable, "-c", "import torch; assert torch.cuda.is_available()"], cwd=source, env=env, check=True, timeout=30)
        subprocess.run((ieee_argv() if strict else argv) + ["run", "--out", str(out)],
                       cwd=source, env=strict_env if strict else env, check=True, timeout=1800)
        for name in ("checkpoint.pt", "evaluation.json", "examples.npz", "train_loss.jsonl"):
            if not (out / name).is_file():
                raise RuntimeError("Missing diffusion output: " + name)
    else:
        raise ValueError("Unknown diffusion stage")


if __name__ == "__main__":
    main()
