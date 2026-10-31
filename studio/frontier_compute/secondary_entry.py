"""Run a frozen secondary evaluator on hash-bound public primary artifacts.

This launcher never trains. Missing primary artifacts, failed CUDA controls,
changed transport bytes and an unapproved URL all stop before evaluation.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

from frontier_compute.portable_entry import unpack


PUBLIC_PREFIX = "https://frontier.morphoswarm.ai/artifacts/rd-diffusion/"
MAX_INPUT_BYTES = 12_000_000


def fetch_inputs(spec, archive):
    url = spec["url"]
    if not url.startswith(PUBLIC_PREFIX) or "?" in url or "#" in url or not url.endswith(".tar.xz"):
        raise ValueError("Runtime inputs must use the fixed public artifact route")
    size = spec["bytes"]
    if not isinstance(size, int) or not 0 < size <= MAX_INPUT_BYTES:
        raise ValueError("Runtime input byte budget is invalid")
    with urlopen(url, timeout=45) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Runtime input response or redirect rejected")
        payload = response.read(size + 1)
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != spec["archive_sha256"]:
        raise ValueError("Runtime input bytes or hash differ from the frozen receipt")
    archive.write_bytes(payload)


def main():
    config_path = Path(sys.argv[1])
    config = json.loads(config_path.read_text())
    out = Path(os.environ["COPS_OUT"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = Path("secondary-runtime").resolve()
    work.mkdir(exist_ok=True)
    unpack(Path(config["source_archive"]), config["source"], work)
    source = work / "rd_diffusion"
    env = {**os.environ, "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
    if os.environ.get("PREFLIGHT"):
        subprocess.run(["bash", "job_secondary.sh"], cwd=source, env={**env, "PREFLIGHT": "1"},
                       check=True, timeout=60)
        return
    if not isinstance(config.get("inputs"), dict):
        raise ValueError("Primary audit and frozen public input receipt are not ready")
    # CUDA is required, so an unavailable device cannot silently become a CPU run.
    subprocess.run([sys.executable, "-c", "import torch; assert torch.cuda.is_available()"],
                   env=env, check=True, timeout=30)
    inputs = work / "primary-inputs"
    inputs.mkdir(exist_ok=True)
    archive = work / "primary-inputs.tar.xz"
    fetch_inputs(config["inputs"], archive)
    unpack(archive, config["inputs"], inputs)
    primary = inputs / "evaluation.json"
    checkpoint = inputs / "checkpoint.pt"
    report = json.loads(primary.read_text())
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != report["train"]["checkpoint_sha256"]:
        raise ValueError("Primary evaluation and actual checkpoint bytes disagree")
    (out / "runtime-input-receipt.json").write_text(json.dumps({
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "source": config["source"], "inputs": config["inputs"],
        "scope": "Secondary evaluation only; no training or biological validation",
    }, indent=2) + "\n")
    # Run the same two frozen launcher commands directly. The transport already
    # archives output; an intermediate shell/archive would duplicate bytes and
    # leave a long-lived child behind if only that shell timed out.
    subprocess.run([sys.executable, "launch_secondary.py", "control", "--out", str(out)],
                   cwd=source, env=env, check=True, timeout=180)
    control = json.loads((out / "control.json").read_text())
    if control.get("ok") is not True or control.get("env", {}).get("cuda_available") is not True:
        raise ValueError("Secondary same-allocation CUDA control failed")
    subprocess.run([sys.executable, "launch_secondary.py", "secondary", "--ckpt", str(checkpoint),
                    "--primary", str(primary), "--out", str(out)],
                   cwd=source, env=env, check=True, timeout=1800)


if __name__ == "__main__":
    main()
