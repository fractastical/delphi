"""Apply the pre-return collection contract without repairing secondary results."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from frontier_compute.diffusion_audit import METHODS


def nonfinite_paths(value, path=""):
    if isinstance(value, dict):
        if value.get("status") == "nonfinite":
            return [path]
        return [p for key, child in value.items()
                for p in nonfinite_paths(child, path + "/" + str(key))]
    if isinstance(value, list):
        return [p for i, child in enumerate(value)
                for p in nonfinite_paths(child, path + "/" + str(i))]
    return [path] if isinstance(value, float) and not math.isfinite(value) else []


def rank_pair_w1(generated, solver):
    """Independent equal-size rank formula; native float32 amplitude, float64 area."""
    ag = generated[:, 0].std(-1)
    reference = solver[:, 0].std(-1)
    absolute = float(np.abs(np.sort(ag.astype(np.float64))
                            - np.sort(reference.astype(np.float64))).mean())
    denominator = float(reference.mean())
    return {"absolute_w1": absolute, "denominator": denominator,
            "relative_w1": absolute / denominator if denominator else None,
            "median_solver_std_u": float(np.median(reference))}


def audit(part, contract_path):
    part, contract_path = Path(part), Path(contract_path)
    contract = json.loads(contract_path.read_text())
    expected = contract["expected"]
    report_path = part / "secondary/secondary_evaluation.json"
    report = json.loads(report_path.read_text())
    control = json.loads((part / "control/control.json").read_text())
    receipt = json.loads((part / "runtime-input-receipt.json").read_text())
    structural_failures, metric_failures = [], []

    def check(condition, label):
        if not condition:
            structural_failures.append(label)

    check(control.get("ok") is True and control.get("env", {}).get("cuda_available") is True,
          "same-job CUDA controls missing or failed")
    check(report.get("smoke") is False and report.get("device") == "cuda", "full CUDA evaluation missing")
    for key, expected_key in (("ckpt_sha256", "checkpoint_sha256"),
                              ("code_sha256", "source_sha256"),
                              ("secondary_code_sha256", "secondary_source_sha256")):
        check(report.get(key) == expected[expected_key], key + " mismatch")
    check(receipt["inputs"]["checkpoint_sha256"] == expected["checkpoint_sha256"], "input checkpoint mismatch")
    check(report.get("numerical_policy_matches_primary") is True, "numerical policy mismatch")
    markers = nonfinite_paths(report)
    if markers:
        metric_failures.append(f"{len(markers)} nonfinite metric markers retained")
    rows = report["ensemble"]["per_condition"]
    expected_keys = [(sid, tau) for sid in expected["condition_ids"] for tau in expected["taus"]]
    check([(r.get("setting_id"), r.get("tau")) for r in rows] == expected_keys,
          "condition order/cardinality differs from frozen 160 conditions")
    check(report["ensemble"].get("n_conditions") == expected["conditions"], "reported condition count mismatch")
    check(report["ensemble"].get("ensemble_failed_runs") == 0, "solver failure count nonzero")
    for row in rows:
        label = f"{row.get('setting_id')}/{row.get('tau')}"
        check(row.get("n_solver") == 32 and "skipped" not in row, label + " incomplete solver ensemble")
        for method in METHODS:
            check(isinstance(row.get(method), dict) and "amp_w1_exact_rel" in row[method],
                  label + "/" + method + " missing metric")
    for split, count in expected["marginal_count_by_time"].items():
        group = report["marginals_exact"].get(split, {})
        check(set(group) == {str(t) for t in expected["taus"]}, split + " time coverage mismatch")
        check(all(r.get("n") == count and r.get("n_generated_finite") == count for r in group.values()),
              split + " marginal count/finiteness mismatch")

    npz_path = part / "secondary/generated_ensemble_full.npz"
    recalculation = []
    with np.load(npz_path, allow_pickle=False) as arrays:
        dims = {"generated": "generated_shape", "solver": "solver_shape", "solver_failed": "failure_mask_shape"}
        for name, shape in dims.items():
            check(list(arrays[name].shape) == expected[shape], name + " shape mismatch")
        check(np.array_equal(arrays["setting_ids"], expected["condition_ids"]), "array setting IDs mismatch")
        check(np.array_equal(arrays["taus"], expected["taus"]), "array times mismatch")
        check(not arrays["solver_failed"].any(), "retained solver failure mask nonzero")
        check(arrays["generated"].dtype == arrays["solver"].dtype == np.float32, "retained field dtype mismatch")
        arrays_finite = {name: bool(np.isfinite(arrays[name]).all()) for name in arrays.files}
        check(all(arrays_finite.values()), "retained array contains nonfinite values")
        if not structural_failures:
            for i, row in enumerate(rows):
                si, ti = divmod(i, len(expected["taus"]))
                value = rank_pair_w1(arrays["generated"][i], arrays["solver"][si, :, ti])
                saved = row["ddpm"]["amp_w1_exact_rel"]
                finite = isinstance(saved, (int, float)) and math.isfinite(saved)
                same = finite and value["relative_w1"] is not None and math.isclose(
                    value["relative_w1"], saved,
                    rel_tol=contract["independent_recalculation"]["rtol"],
                    abs_tol=contract["independent_recalculation"]["atol"])
                recalculation.append({"setting_id": row["setting_id"], "tau": row["tau"],
                                      **value, "saved_relative_w1": saved,
                                      "within_frozen_tolerance": bool(same),
                                      "absolute_difference": abs(value["relative_w1"] - saved)
                                      if finite and value["relative_w1"] is not None else None})
    finite_rows = [r for r in recalculation if r["relative_w1"] is not None]
    mismatches = [r for r in finite_rows if not r["within_frozen_tolerance"]]
    undefined = [r for r in recalculation if r["relative_w1"] is None]
    if mismatches:
        metric_failures.append(f"{len(mismatches)} finite DDPM metrics exceed frozen independent-recalculation tolerance")
    if undefined:
        metric_failures.append(f"{len(undefined)} DDPM relative metrics have zero solver-amplitude denominator")
    gate = expected["stratum_gate_std_u"]
    strata = {"patterned": sum(r["median_solver_std_u"] >= gate for r in recalculation),
              "near_uniform": sum(r["median_solver_std_u"] < gate for r in recalculation)}
    for name, count in strata.items():
        check(report["stratified_by_solver_amplitude"][name]["n_conditions"] == count,
              name + " stratum count mismatch")
    rounding_matches = sum(
        float(np.float32(r["absolute_w1"]) / np.float32(r["denominator"])) == r["saved_relative_w1"]
        for r in finite_rows
    )
    return {"schema": "frontier.rd-ddpm.secondary-collection-audit/1",
            "complete": not structural_failures and not metric_failures,
            "structural_checks_pass": not structural_failures,
            "structural_failures": structural_failures, "metric_failures": metric_failures,
            "nonfinite_metric_paths": markers, "arrays_finite": arrays_finite,
            "condition_count": len(rows), "strata_recomputed": strata,
            "separate_rounding_diagnosis": {
                "finite_rows": len(finite_rows), "exact_float32_scalar_division_matches": rounding_matches,
                "method": "Cast independently computed float64 W1 numerator to float32, divide by native float32 denominator, compare exactly. This reproduces source NumPy scalar promotion; it does not replace the frozen float64 recalculation criterion.",
                "numpy_local": np.__version__, "numpy_remote": control["env"].get("numpy"),
                "max_relative_discrepancy_before_rounding": max(
                    (r["absolute_difference"] / abs(r["saved_relative_w1"])
                     for r in finite_rows if r["saved_relative_w1"] != 0), default=0),
                "acceptance_unchanged": True},
            "independent_recalculation": {"contract": contract["independent_recalculation"],
                "finite_compared": len(finite_rows), "mismatches": len(mismatches),
                "undefined": len(undefined),
                "max_abs_difference": max((r["absolute_difference"] for r in mismatches), default=0),
                "rows": recalculation},
            "sha256": {"contract": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
                       "secondary_evaluation": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                       "retained_arrays": hashlib.sha256(npz_path.read_bytes()).hexdigest()},
            "scope": "Frozen collection and independent DDPM metric checks. Failure retained; no raw output replaced. Baseline/marginal fields were not returned, so their sample metrics were not independently recalculated."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.part, args.contract)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("complete", "structural_checks_pass", "structural_failures", "metric_failures", "strata_recomputed")}))
    raise SystemExit(0 if result["complete"] else 1)
