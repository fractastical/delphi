"""EVALUATION RECOVERY of the frozen RD-DDPM primary (separately declared; the original primary run stays FAILED and is not rewritten).
Loads the exact returned checkpoint (sha256 bound below), retrains NOTHING, regenerates the training rows only for the baseline pool, and calls the UNCHANGED rd_ddpm
evaluate(), marginals() and timings() with the original settings, splits, seeds and baselines. Each stage writes durable BEGIN/END receipts so a future timeout is localised.
Outputs go to a NEW directory with explicit recovery provenance; no file here is, or claims to be, the original evaluation.json.
Run through launch_recovery.py (explicit FP32 policy set before torch is imported).
    python3 launch_recovery.py --ckpt checkpoint.pt --train-log train_loss.jsonl --out DIR [--smoke --expect-sha SHA]"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import traceback

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rd_ddpm as R

CHECKPOINT_SHA256 = "1a0a185cdacd49e8a65aa77ece1cd8f51033533c996025b3f4da907cd2b2ae76"  # predeclared from infra's actual return (5,421,109 bytes)
POLICY = {
    "NVIDIA_TF32_OVERRIDE": "0",
    "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "0",
    "torch.backends.cuda.matmul.allow_tf32": False,
    "torch.backends.cudnn.allow_tf32": False,
    "torch.set_float32_matmul_precision": "highest",
}
TRAIN_LOG_SHA256 = "2ecdd2ceb6eec513a634ec7edcaf5e37cc15cba3d3717c90c5ad7ab41dc05862"  # predeclared from infra's actual return (36,009 bytes)
PRODUCTION_STEPS = [
    1,
    *range(100, 30001, 100),
]  # the exact 301-step sequence of the frozen primary


def runtime_policy():
    return {
        "NVIDIA_TF32_OVERRIDE": os.environ.get("NVIDIA_TF32_OVERRIDE"),
        "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": os.environ.get(
            "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE"
        ),
        "torch.backends.cuda.matmul.allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "torch.backends.cudnn.allow_tf32": torch.backends.cudnn.allow_tf32,
        "torch.set_float32_matmul_precision": torch.get_float32_matmul_precision(),
    }


def normalization_gate(mean_regen, std_regen, mean_ckpt, std_ckpt):
    """PRODUCTION GATE: regenerated per-channel mean/std must EQUAL the checkpoint's (np.array_equal). The relative difference is a diagnostic only and never relaxes the gate."""
    mean_regen, std_regen = np.asarray(mean_regen), np.asarray(std_regen)
    mean_ckpt, std_ckpt = np.asarray(mean_ckpt), np.asarray(std_ckpt)
    same_shape = (
        mean_regen.shape == mean_ckpt.shape and std_regen.shape == std_ckpt.shape
    )
    equal = bool(
        same_shape
        and np.array_equal(mean_regen, mean_ckpt)
        and np.array_equal(std_regen, std_ckpt)
    )
    diag = {
        "exactly_equal": equal,
        "gate": "np.array_equal on mean and std (no tolerance)",
        "ok": equal,
    }
    if same_shape:
        diag["max_abs_difference_mean"] = float(np.abs(mean_regen - mean_ckpt).max())
        diag["max_abs_difference_std"] = float(np.abs(std_regen - std_ckpt).max())
        diag["max_relative_difference_DIAGNOSTIC_ONLY"] = float(
            max(
                np.abs(mean_regen - mean_ckpt).max() / np.abs(mean_ckpt).max(),
                np.abs(std_regen - std_ckpt).max() / np.abs(std_ckpt).max(),
            )
        )
    return diag


def check_log_steps(path, smoke=False, smoke_steps=None):
    """The returned training log must be exactly the 301-step sequence 1,100,...,30000 (production) before any held-out generation."""
    steps = [json.loads(line)["step"] for line in open(path) if line.strip()]
    want = PRODUCTION_STEPS if not smoke else smoke_steps
    if steps != want:
        raise SystemExit(
            f"training log step sequence differs from the expected {len(want)}-step sequence ({len(steps)} steps found)"
        )
    return steps


def durable(path, text, mode="w"):
    with open(path, mode) as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


class Stages:
    """BEGIN/END receipts around each unchanged function; written and fsynced immediately."""

    def __init__(self, out):
        self.out, self.t0 = out, time.time()

    def log(self, **kw):
        record = {
            "t_since_start_s": time.time() - self.t0,
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **kw,
        }
        encoded = json.dumps(record)
        durable(os.path.join(self.out, "stage_log.jsonl"), encoded + "\n", "a")
        print("RECOVERY_STAGE " + encoded, flush=True)

    def run(self, name, fn):
        self.log(stage=name, event="BEGIN")
        t = time.time()
        try:
            r = fn()
        except BaseException as e:  # noqa: BLE001 - recorded, then re-raised
            self.log(
                stage=name,
                event="FAIL",
                seconds=time.time() - t,
                error=repr(e),
                traceback=traceback.format_exc()[-1500:],
            )
            raise
        self.log(stage=name, event="END", seconds=time.time() - t)
        return r


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--train-log", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--expect-sha", default=None, help="SMOKE ONLY")
    ap.add_argument("--allow-policy-mismatch", action="store_true", help="SMOKE ONLY")
    a = ap.parse_args()
    if not a.smoke and (a.expect_sha is not None or a.allow_policy_mismatch):
        raise SystemExit(
            "--expect-sha and --allow-policy-mismatch are smoke-only; production uses the predeclared checkpoint hash and the explicit FP32 policy"
        )
    expect_sha = a.expect_sha if a.smoke and a.expect_sha else CHECKPOINT_SHA256
    os.makedirs(a.out, exist_ok=True)
    if os.listdir(a.out):
        raise SystemExit("recovery output directory must be new and empty")
    st = Stages(a.out)
    st.log(stage="start", event="BEGIN", argv=sys.argv[1:])
    policy = runtime_policy()
    if policy != POLICY and not a.allow_policy_mismatch:
        raise SystemExit(
            f"numerical policy mismatch (use launch_recovery.py): {policy} != {POLICY}"
        )
    got = sha_file(a.ckpt)
    if got != expect_sha:
        raise SystemExit(f"checkpoint sha256 {got} != predeclared {expect_sha}")
    log_sha = sha_file(a.train_log)
    if not a.smoke and log_sha != TRAIN_LOG_SHA256:
        raise SystemExit(
            f"train log sha256 {log_sha} != predeclared {TRAIN_LOG_SHA256}"
        )
    tc_smoke = R.CFG["smoke"]
    check_log_steps(a.train_log, a.smoke, [1, *range(25, tc_smoke["steps"] + 1, 25)])
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev != "cuda" and not a.smoke:
        raise SystemExit("no CUDA: refusing the full recovery")
    sm = R.CFG["smoke"]
    taus = sm["save_tau"] if a.smoke else R.S["save_tau"]
    table = R.settings_table()
    ck = torch.load(a.ckpt, map_location=dev, weights_only=False)
    if ck.get("config_sha256") != R.sha_file(os.path.join(R.HERE, "config.json")):
        raise SystemExit("checkpoint config sha256 differs from the frozen config")
    net = R.Net().to(dev)
    net.load_state_dict(ck["ema"])
    net.eval()
    mean, std = ck["mean"], ck["std"]
    sch = R.schedule(R.CFG["model"]["T_diffusion"], dev)

    # 1. training rows for the baseline pool only (no optimiser step anywhere in this file)
    def build():
        if a.smoke:
            return R.build_split(
                "train",
                dev,
                table,
                ids=list(range(*sm["train_ids"])),
                seed_idx=[0],
                save_tau=taus,
            )
        return R.build_split("train", dev, table, save_tau=taus)

    tr = st.run("train_data_regeneration", build)
    c, f, sid, _ = R.flatten(tr, taus)
    m2, s2 = f.mean((0, 2), keepdims=True), f.std((0, 2), keepdims=True)
    norm = normalization_gate(m2, s2, mean, std)
    durable(
        os.path.join(a.out, "stage_train_data.json"),
        json.dumps(
            {
                "normalization_match": norm,
                "runs": int(len(tr["failed"])),
                "failed_runs": int(tr["failed"].sum()),
                "rows": int(len(c)),
                "fields_sha256_REGENERATED": R.sha(f.tobytes()),
                "solver_seconds": tr["solver_seconds"],
                "note": "the original dataset checksum was never returned; this checksum is of REGENERATED data, not an original measurement",
            },
            indent=1,
        ),
    )
    if not norm["ok"]:
        raise SystemExit(
            f"regenerated normalisation is NOT exactly equal to the checkpoint's ({norm}); failure preserved in stage_train_data.json; recovery stopped before any held-out generation"
        )
    ev = {
        "train_params": c[:, :4],
        "train_fields": f,
        "train_setting": sid,
        "train_tau": c[:, 4],
        "spc": sm["samples_per_condition"]
        if a.smoke
        else R.CFG["eval"]["samples_per_condition"],
    }
    # 2. unchanged evaluation functions
    res, E, G, rows, taus_, fields, failed, ids = st.run(
        "ensemble_eval",
        lambda: R.evaluate(net, mean, std, sch, table, dev, a.out, ev, a.smoke),
    )
    durable(
        os.path.join(a.out, "stage_ensemble_eval.json"),
        json.dumps(
            res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)
        ),
    )
    marg = (
        "skipped in smoke"
        if a.smoke
        else st.run(
            "marginals", lambda: R.marginals(net, mean, std, sch, table, dev, taus)
        )
    )
    durable(
        os.path.join(a.out, "stage_marginals.json"),
        json.dumps(
            marg, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)
        ),
    )
    tim = st.run("timings", lambda: R.timings(net, mean, std, sch, table, dev, a.smoke))
    durable(
        os.path.join(a.out, "stage_timings.json"),
        json.dumps(
            tim, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)
        ),
    )
    # 3. assemble a recovery evaluation.json with the original structure and explicit provenance
    log = [json.loads(line) for line in open(a.train_log) if line.strip()]
    shutil.copy2(a.ckpt, os.path.join(a.out, "checkpoint.pt"))
    shutil.copy2(a.train_log, os.path.join(a.out, "train_loss.jsonl"))
    rep = {
        "RECOVERY": True,
        "recovery_provenance": {
            "what": "evaluation recovery of the frozen primary, separately declared; the original primary run FAILED (timeout, no evaluation.json/examples.npz) and remains FAILED",
            "weights": "exact returned checkpoint, sha256 bound before the run",
            "retraining": "none; no optimiser step is executed by this program",
            "functions": "rd_ddpm.evaluate, marginals, timings unchanged (code sha256 below)",
            "recovery_code_sha256": sha_file(os.path.abspath(__file__)),
            "training_receipt_source": "returned checkpoint metadata and returned train_loss.jsonl; last logged elapsed_s is a logged value, NOT the precise total training wall time",
            "original_dataset_checksum": "never returned; the regenerated checksum is not an original measurement",
            "normalization_match": norm,
        },
        "env": R.env_receipt(dev),
        "smoke": bool(a.smoke),
        "numerical_policy": {
            "expected": POLICY,
            "runtime": policy,
            "matches": policy == POLICY,
        },
        "dataset": {
            "train": {
                "runs": int(len(tr["failed"])),
                "failed_runs": int(tr["failed"].sum()),
                "failed_setting_ids": sorted(
                    set(int(i) for i in tr["setting_id"][tr["failed"]])
                )[:200],
                "rows": int(len(c)),
                "solver_seconds_REGENERATED": tr["solver_seconds"],
                "fields_sha256_REGENERATED": R.sha(f.tobytes()),
                "setting_ids_sha256": R.sha(np.unique(sid).tobytes()),
                "n_settings": int(len(np.unique(sid))),
            },
            "settings_table_sha256": R.sha(table.tobytes()),
            "config_sha256": R.sha_file(os.path.join(R.HERE, "config.json")),
            "code_sha256": R.sha_file(os.path.join(R.HERE, "rd_ddpm.py")),
        },
        "train": {
            "steps": int(ck["steps"]),
            "n_train_rows_metadata": int(ck["n_train_rows"]),
            "checkpoint_sha256": got,
            "train_log_sha256": log_sha,
            "first_loss": log[0]["loss"],
            "final_loss": log[-1]["loss"],
            "mean_last_10_logged": float(np.mean([x["loss"] for x in log[-10:]])),
            "last_logged_elapsed_s": log[-1]["elapsed_s"],
            "seconds": None,
            "frozen_before_holdout_generation": True,
            "frozen_note": "checkpoint hash was bound before this recovery generated any held-out data",
            "cuda_max_mem_mb": None,
            "gpu_after": None,
        },
        "ensemble_eval": res,
        "held_out_marginals": marg,
        "timings": tim,
        "total_seconds": time.time() - st.t0,
        "costs_separate": {
            "train_data_solver_seconds_REGENERATED": tr["solver_seconds"],
            "train_seconds": None,
            "ensemble_solver_seconds": res["ensemble_solver_seconds"],
        },
    }
    R.jdump(rep, os.path.join(a.out, "evaluation.json"))
    st.log(stage="assemble", event="END")
    print(
        json.dumps(
            {"ok": True, "recovery": True, "total_seconds": rep["total_seconds"]}
        )
    )


if __name__ == "__main__":
    main()
