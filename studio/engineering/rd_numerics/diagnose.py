"""Locate failed saved-metric reproduction without changing frozen tolerances."""

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from .audit import comparisons, dump, rd, sha


def diagnose(folder, output):
    folder = Path(folder)
    inputs = np.load(folder / "declared-inputs.npz")
    receipt = json.loads((folder / "receipt.json").read_text())
    actual = comparisons(
        folder,
        receipt["completed_configs"],
        inputs["setting_ids"],
        inputs["seed_indices"],
        inputs["save_tau"].tolist(),
    )
    saved = json.loads((folder / "paired-discrepancies.json").read_text())
    failures, scalars = [], []

    def walk(a, b, path=()):
        if isinstance(a, dict):
            for key in a:
                walk(a[key], b[key], path + (key,))
        elif isinstance(a, list):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + (i,))
        elif isinstance(a, float):
            delta = abs(a - b)
            scalars.append((path[-1], delta))
            if not np.isclose(a, b, rtol=1e-10, atol=1e-12):
                failures.append(
                    {
                        "path": list(path),
                        "recomputed": a,
                        "saved": b,
                        "absolute_difference": delta,
                    }
                )
        elif type(a) is not type(b) or a != b:
            failures.append(
                {"path": list(path), "recomputed": a, "saved": b, "categorical": True}
            )

    walk(actual, saved)
    cache, matrices, batched_coefficients = {}, {}, {}
    for error in failures:
        path = error["path"]
        row = actual[path[0]]
        error["condition"] = {
            k: row[k] for k in ("configs", "setting_id", "seed_index", "tau")
        }
        if len(path) != 4 or path[1] != "channels":
            continue
        index = row["configs"][1]
        if index not in cache:
            cache[index] = np.load(folder / f"config-{index}.npz")["fields"]
        field = cache[index][
            row["setting_id"] * 3 + row["seed_index"],
            inputs["save_tau"].tolist().index(row["tau"]),
            path[2],
        ]
        n = len(field)
        if n not in matrices:
            matrices[n] = rd.dct_matrix(n).numpy()
        matrix = matrices[n]
        if index not in batched_coefficients:
            batched_coefficients[index] = (cache[index] @ matrix.T) / np.sqrt(n)
        coeff = batched_coefficients[index][
            row["setting_id"] * 3 + row["seed_index"],
            inputs["save_tau"].tolist().index(row["tau"]),
            path[2],
        ]
        centered = ((field - field.mean()) @ matrix.T) / np.sqrt(n)
        constant = (np.full(n, field.mean()) @ matrix.T) / np.sqrt(n)
        power = float(np.sum(coeff[1:] ** 2))
        high = float(np.sum(coeff[64:] ** 2))
        error["native_finer_field"] = {
            "N": n,
            "mean": float(field.mean()),
            "standard_deviation": float(field.std()),
            "peak_to_peak": float(np.ptp(field)),
            "native_variance": float(field.var()),
            "uncentered_nonconstant_DCT_power": power,
            "uncentered_above63_DCT_power": high,
            "frozen_ratio_denominator": max(power, 1e-24),
            "denominator_floor_active": power < 1e-24,
            "centered_above63_DCT_power_DIAGNOSTIC_ONLY": float(
                np.sum(centered[64:] ** 2)
            ),
            "constant_field_above63_numerical_DCT_power_DIAGNOSTIC_ONLY": float(
                np.sum(constant[64:] ** 2)
            ),
            "constant_field_exact_nonzero_mode_power": 0.0,
        }
    keys = sorted({key for key, _ in scalars})
    report = {
        "status": "FAILED original exact and fixed roundoff-aware derived-metric reproduction",
        "original_bit_for_bit_dict_comparison_equal": actual == saved,
        "analysis_source_sha256": sha(Path(__file__).with_name("analyze.py")),
        "diagnosis_source_sha256": sha(__file__),
        "source_receipt_sha256": sha(folder / "receipt.json"),
        "relative_tolerance": 1e-10,
        "absolute_tolerance": 1e-12,
        "n_failed_scalar_checks": len(failures),
        "categorical_mismatches": sum(bool(x.get("categorical")) for x in failures),
        "mismatched_field_counts": dict(Counter(x["path"][-1] for x in failures)),
        "max_absolute_discrepancy_by_metric": {
            key: max(delta for k, delta in scalars if k == key) for key in keys
        },
        "mismatches": failures,
        "scope": "Original outcomes and thresholds unchanged; constant/centered spectral calculations are separate diagnosis, not replacement metrics or convergence acceptance.",
    }
    dump(output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "mismatches"}, indent=2))
    print(json.dumps(failures[:4], indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    diagnose(args.folder, args.output)
