#!/usr/bin/env python3
"""Deterministic scoring and field-wise aggregation for the frozen pilot."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def majority(values: list[object]) -> object | None:
    if not values:
        return None
    counts = Counter(values)
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return top[0][0] if top[0][1] >= 2 else None


def number(obj: dict, path: tuple[str, str]) -> float | None:
    value = obj.get(path[0], {}).get(path[1])
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def score_one(response: object) -> dict:
    if not isinstance(response, dict):
        return {"task_a": 0, "task_b": 0, "total": 0}
    a = response.get("task_a") if isinstance(response.get("task_a"), dict) else {}
    b = response.get("task_b") if isinstance(response.get("task_b"), dict) else {}
    checks_a = [
        a.get("published_fit_form") == "linear",
        a.get("exponential_log_form_directly_measured") is False,
        isinstance(a.get("linear_factor_24h"), (int, float)) and abs(a["linear_factor_24h"] - 1.144) <= 0.001,
        isinstance(a.get("exponential_factor_24h"), (int, float)) and abs(a["exponential_factor_24h"] - 1.154964) <= 0.001,
        isinstance(a.get("relative_difference_percent"), (int, float)) and abs(a["relative_difference_percent"] - 0.9588) <= 0.1,
        a.get("uncertainty_bands_overlap") is True,
        a.get("synchrony_effect") == "impairs_growth",
        a.get("decision_code") == "keep_exponential_form_as_assumption_and_test_sensitivity",
    ]
    checks_b = [
        b.get("pressure_width_product_unit") == "N/m",
        b.get("dimensions_are_compatible") is True,
        b.get("source_measured_bending_stiffness") is True,
        b.get("pressure_to_ray_load_calibration_in_source") is False,
        isinstance(b.get("measured_EI_min_N_m2"), (int, float)) and abs(b["measured_EI_min_N_m2"] - 1.5e-9) <= 1e-10,
        isinstance(b.get("measured_EI_max_N_m2"), (int, float)) and abs(b["measured_EI_max_N_m2"] - 4e-9) <= 1e-10,
        b.get("measurement_method") == "mechanical_force_deflection",
        b.get("decision_code") == "retain_as_assumption_until_hydrodynamic_load_is_measured_or_validated",
    ]
    return {"task_a": sum(checks_a), "task_b": sum(checks_b), "total": sum(checks_a) + sum(checks_b),
            "checks_a": checks_a, "checks_b": checks_b}


NUMERIC = {
    ("task_a", "linear_factor_24h"), ("task_a", "exponential_factor_24h"),
    ("task_a", "relative_difference_percent"),
    ("task_b", "measured_EI_min_N_m2"), ("task_b", "measured_EI_max_N_m2"),
}


def aggregate(responses: list[dict | None]) -> dict | None:
    valid = [x for x in responses if isinstance(x, dict)]
    if not valid:
        return None
    result: dict = {"task_a": {}, "task_b": {}}
    for section, fields in {
        "task_a": ["source_doi", "published_fit_form", "exponential_log_form_directly_measured",
                   "linear_factor_24h", "exponential_factor_24h", "relative_difference_percent",
                   "uncertainty_bands_overlap", "synchrony_effect", "decision_code"],
        "task_b": ["source_doi", "pressure_width_product_unit", "dimensions_are_compatible",
                   "source_measured_bending_stiffness", "pressure_to_ray_load_calibration_in_source",
                   "measured_EI_min_N_m2", "measured_EI_max_N_m2", "measurement_method", "decision_code"],
    }.items():
        for field in fields:
            values = [x.get(section, {}).get(field) for x in valid
                      if isinstance(x.get(section), dict) and x[section].get(field) is not None]
            if (section, field) in NUMERIC:
                numeric_values = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
                result[section][field] = median(numeric_values)
            else:
                result[section][field] = majority(values)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", default="preregistration.json")
    args = parser.parse_args()
    prereg = json.loads((HERE / args.preregistration).read_text())
    run_dir = HERE / "runs" / prereg["experiment_id"]
    call_paths = sorted(p for p in run_dir.glob("r[1-3]-*-t[1-3].json") if p.is_file())
    calls = [json.loads(p.read_text()) for p in call_paths]
    grouped: dict[tuple[int, str], list[dict | None]] = {}
    report_calls = []
    for call in calls:
        response = call.get("response")
        grouped.setdefault((call["repeat"], call["condition"]), []).append(response)
        score = score_one(response)
        report_calls.append({"file": call["path"] if "path" in call else call.get("condition"),
                             "repeat": call["repeat"], "condition": call["condition"],
                             "turn": call["turn"], "score": score,
                             "usage": call.get("usage"), "http_status": call.get("http_status")})
    aggregates = []
    for (rep, condition), replies in sorted(grouped.items()):
        merged = aggregate(replies)
        aggregates.append({"repeat": rep, "condition": condition, "valid_replies": sum(x is not None for x in replies),
                           "aggregate": merged, "score": score_one(merged)})
    out = {"schema": "frontier.capability-agency.scored-results/1", "individual_calls": report_calls,
           "replicate_aggregates": aggregates,
           "condition_means": {condition: statistics.mean([a["score"]["total"] for a in aggregates
                                                             if a["condition"] == condition])
                               for condition in sorted({a["condition"] for a in aggregates})}}
    (run_dir / "scored_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out["condition_means"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
