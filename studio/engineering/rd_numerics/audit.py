"""Paired training-only Schnakenberg grid/time audit; never train/read holdouts."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import torch

from engineering.rd_diffusion import rd_ddpm as rd

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = [(64, 0.02), (64, 0.01), (64, 0.005), (128, 0.005), (256, 0.005)]
PAIRS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def common_grid(fields, size=64):
    """Analytic cosine projection, normalized continuous cosine coefficients."""
    n = fields.shape[-1]
    matrix = rd.dct_matrix(n).numpy()
    coefficients = (fields @ matrix.T) / np.sqrt(n)
    common = coefficients[..., :size] @ rd.dct_matrix(size).numpy() * np.sqrt(size)
    power = np.sum(coefficients[..., 1:] ** 2, axis=-1)
    high = np.sum(coefficients[..., size:] ** 2, axis=-1)
    fraction = high / np.maximum(power, 1e-24)
    return common, fraction


def solve(params, seeds, n, dt, taus, device):
    us, vs = [], []
    for (a, b, _d, length), seed in zip(params, seeds):
        u0, v0 = a + b, b / (a + b) ** 2
        du, dv = rd.ic_modal(
            seed,
            rd.S["K_modes"],
            length,
            n,
            rd.S["eps"] * abs(u0),
            rd.S["eps"] * abs(v0),
        )
        us.append(u0 + du)
        vs.append(v0 + dv)

    def make(x):
        return torch.as_tensor(np.asarray(x), dtype=torch.float64, device=device)

    steps = [round(t / dt) for t in taus]
    _, _, saves = rd.advance(
        make(us),
        make(vs),
        *[make(params[:, i]) for i in range(4)],
        steps[-1],
        dt=dt,
        save_steps=steps,
    )
    return torch.stack([torch.stack([u, v], 1) for u, v in saves], 1).cpu().numpy()


def controls(device):
    n, k, tau, length = 64, 7, 0.2, 5.0
    x = (np.arange(n) + 0.5) * length / n
    wave = np.cos(k * np.pi * x / length)
    matrix = rd.dct_matrix(n).numpy()
    q = (np.arange(n) * np.pi / length) ** 2
    actual = ((wave @ matrix.T) * np.exp(-q * tau)) @ matrix
    exact = wave * np.exp(-((k * np.pi / length) ** 2) * tau)
    # Mutate only the populated coefficient, avoiding exponential overflow/noise.
    wrong = wave * np.exp((k * np.pi / length) ** 2 * tau)
    errors = {
        "orthonormal_max_abs": float(abs(matrix @ matrix.T - np.eye(n)).max()),
        "heat_cosine_max_abs": float(abs(actual - exact).max()),
        "wrong_sign_max_abs": float(abs(wrong - exact).max()),
    }
    p = np.array([[0.1, 0.9, 20.0, 40.0]])
    f = solve(p, np.array([0]), 64, 0.02, [0.2], "cpu")
    source, _ = rd.simulate(p, np.array([0]), device="cpu", save_tau=[0.2])
    errors["source_wrapper_max_abs"] = float(abs(f - source).max())
    errors["common_projection_identity_max_abs"] = float(
        abs(common_grid(f)[0] - f).max()
    )
    errors["CPU_CUDA_max_abs"] = None
    if device == "cuda":
        g = solve(p, np.array([0]), 64, 0.02, [0.2], "cuda")
        errors["CPU_CUDA_max_abs"] = float(abs(f - g).max())
    errors["passed"] = bool(
        errors["orthonormal_max_abs"] < 1e-11
        and errors["heat_cosine_max_abs"] < 1e-11
        and errors["wrong_sign_max_abs"] > 1
        and errors["source_wrapper_max_abs"] < 1e-11
        and errors["common_projection_identity_max_abs"] < 1e-11
        and (device != "cuda" or errors["CPU_CUDA_max_abs"] < 1e-9)
    )
    return errors


def comparisons(folder, completed, ids, seedidx, taus):
    rows = []
    for left, right in PAIRS:
        if left not in completed or right not in completed:
            continue
        one = np.load(folder / f"config-{left}.npz")["fields"]
        two = np.load(folder / f"config-{right}.npz")["fields"]
        u, _ = common_grid(one)
        v, high = common_grid(two)
        for run, (sid, seed) in enumerate(zip(ids, seedidx)):
            for ti, tau in enumerate(taus):
                a, b = u[run, ti], v[run, ti]
                finite = bool(np.isfinite(a).all() and np.isfinite(b).all())
                bounded = finite and bool(max(abs(a).max(), abs(b).max()) <= 1000)
                row = {
                    "configs": [left, right],
                    "setting_id": int(sid),
                    "seed_index": int(seed),
                    "tau": tau,
                    "finite_pair": finite,
                    "bounded_common_grid_pair": bounded,
                    "channels": None,
                    "u_dominant_modes": None,
                    "mode_changed": None,
                }
                # Native failure determines whether a comparison is valid.
                native_ok = bool(
                    np.isfinite(one[run, ti]).all()
                    and np.isfinite(two[run, ti]).all()
                    and max(abs(one[run, ti]).max(), abs(two[run, ti]).max()) <= 1000
                )
                row["valid_native_pair"] = native_ok
                if native_ok:
                    row["channels"] = [
                        {
                            "common_grid_RMS_abs": float(
                                np.sqrt(np.mean((a[c] - b[c]) ** 2))
                            ),
                            "common_grid_relative_L2": float(
                                np.linalg.norm(a[c] - b[c])
                                / max(np.linalg.norm(b[c]), 1e-12)
                            ),
                            "native_mean_difference": float(
                                one[run, ti, c].mean() - two[run, ti, c].mean()
                            ),
                            "native_amplitude_std_difference": float(
                                one[run, ti, c].std() - two[run, ti, c].std()
                            ),
                            "finer_power_fraction_above_common_cutoff": float(
                                high[run, ti, c]
                            ),
                        }
                        for c in range(2)
                    ]
                    modes = [int(rd.dominant_mode(z[run, ti, 0])) for z in (one, two)]
                    row["u_dominant_modes"] = modes
                    row["mode_changed"] = modes[0] != modes[1]
                rows.append(row)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--control-only", action="store_true")
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args()
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    pins = {
        str(f.relative_to(ROOT)): sha(f)
        for f in (
            Path(__file__),
            ROOT / "engineering/rd_numerics/PREREG.md",
            Path(rd.__file__),
            ROOT / "engineering/rd_diffusion/config.json",
        )
    }
    dump(out / "input-code-pins.json", pins)
    if args.preflight:
        print("Training-only source/import preflight; no integration", flush=True)
        return
    device = "cpu" if args.control_only else "cuda"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no CPU fallback")
    control = controls(device)
    dump(out / "controls.json", control)
    if not control["passed"]:
        raise RuntimeError("Frozen software/platform controls failed")
    if args.control_only:
        return
    ids = np.repeat(np.arange(16), 3)
    seedidx = np.tile(np.arange(3), 16)
    seeds = ids * 1000 + seedidx
    params = rd.settings_table()[ids]
    taus = rd.S["save_tau"]
    np.savez_compressed(
        out / "declared-inputs.npz",
        setting_ids=ids,
        seed_indices=seedidx,
        ic_seeds=seeds,
        params=params,
        save_tau=taus,
    )
    dump(
        out / "environment.json",
        {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "cuda_version": torch.version.cuda,
            "GPU": torch.cuda.get_device_name(),
            "float_dtype": "float64",
            "TF32": False,
            "threads": torch.get_num_threads(),
        },
    )
    completed = []
    started = time.perf_counter()
    for index, (n, dt) in enumerate(CONFIGS):
        t0 = time.perf_counter()
        fields = solve(params, seeds, n, dt, taus, device)
        # Preserve actual failed values in NPZ; strict JSON stores only finite counts.
        finite = np.isfinite(fields).all((2, 3))
        exceeded = np.nan_to_num(abs(fields), nan=np.inf).max((2, 3)) > 1000
        negative = (fields < 0).any((2, 3))
        np.savez_compressed(
            out / f"config-{index}.npz",
            fields=fields,
            finite=finite,
            exceeded=exceeded,
            negative=negative,
        )
        completed.append(index)
        dump(
            out / f"config-{index}.json",
            {
                "index": index,
                "N": n,
                "dt_tau": dt,
                "wall_seconds": time.perf_counter() - t0,
                "expected_runs": 48,
                "saved_times": taus,
                "nonfinite_snapshots": int((~finite).sum()),
                "exceeded_snapshots": int(exceeded.sum()),
                "negative_snapshots": int(negative.sum()),
                "fields_sha256": sha(out / f"config-{index}.npz"),
            },
        )
        rows = comparisons(out, completed, ids, seedidx, taus)
        dump(out / "paired-discrepancies.json", rows)
        dump(
            out / "receipt.json",
            {
                "schema": "frontier.rd-numerics.audit/1",
                "complete": len(completed) == len(CONFIGS),
                "completed_configs": completed,
                "expected_configs": CONFIGS,
                "expected_runs_per_config": 48,
                "paired_rows": len(rows),
                "elapsed_seconds": time.perf_counter() - started,
                "scope": "Training-only descriptive discretization audit; no convergence PASS, empirical accuracy unknown; no grid-time interaction estimate",
                "source_pins": pins,
                "files": {
                    f.name: sha(f)
                    for f in out.iterdir()
                    if f.is_file() and f.name != "receipt.json"
                },
            },
        )
        print(
            f"COMPLETED config{index} N{n} dt{dt} wall{time.perf_counter() - t0:.3f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
