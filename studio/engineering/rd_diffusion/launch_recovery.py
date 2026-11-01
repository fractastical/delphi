"""Launcher for the EVALUATION-RECOVERY packet. Sets the primary run's explicit FP32 policy BEFORE torch is imported, then runs recovery_eval.py unchanged.
Refuses if torch is already imported.   python3 launch_recovery.py --ckpt checkpoint.pt --train-log train_loss.jsonl --out NEWDIR"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = {"NVIDIA_TF32_OVERRIDE": "0", "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "0"}


def main(argv):
    if "torch" in sys.modules:
        raise SystemExit("torch was imported before the numerical policy was set")
    os.environ.update(ENV)
    import torch

    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    sys.path.insert(0, HERE)
    sys.argv = ["recovery_eval.py", *argv[1:]]
    runpy.run_path(os.path.join(HERE, "recovery_eval.py"), run_name="__main__")


if __name__ == "__main__":
    main(sys.argv)
