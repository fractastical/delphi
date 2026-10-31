"""Launcher for the SECONDARY packet. Sets the primary run's explicit FP32 policy BEFORE torch is imported, verifies it, then runs either the frozen control or the secondary
evaluation unchanged. Refuses to run if torch was already imported (the policy could then be partly ineffective).
    python3 launch_secondary.py control --out DIR
    python3 launch_secondary.py secondary --ckpt checkpoint.pt --primary evaluation.json --out DIR"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = {"NVIDIA_TF32_OVERRIDE": "0", "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "0"}


def main(argv):
    if "torch" in sys.modules:
        raise SystemExit("torch was imported before the numerical policy was set")
    if len(argv) < 2 or argv[1] not in ("control", "secondary"):
        raise SystemExit(__doc__)
    os.environ.update(ENV)
    import torch

    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    sys.path.insert(0, HERE)
    if argv[1] == "control":
        sys.argv = ["rd_ddpm.py", "control", *argv[2:]]
        runpy.run_path(os.path.join(HERE, "rd_ddpm.py"), run_name="__main__")
    else:
        sys.argv = ["secondary_eval.py", *argv[2:]]
        runpy.run_path(os.path.join(HERE, "secondary_eval.py"), run_name="__main__")


if __name__ == "__main__":
    main(sys.argv)
