"""Compare a frozen partial-arm recovery against prior rows without hiding omissions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def indexed(rows, arm):
    result = {}
    for row in rows:
        if row["arm"] == arm:
            if row["id"] in result:
                raise ValueError("duplicate result id within an arm")
            result[row["id"]] = row
    return result


def complete(row):
    return bool(row) and not row.get("not_run") and not row.get("out_of_budget")


def compare(prior_rows, new_rows, missing_ids, repeat_ids, tolerance=1e-6):
    if not missing_ids or not repeat_ids or set(missing_ids) & set(repeat_ids):
        raise ValueError("nonempty disjoint completion and repeat sets required")
    prior = indexed(prior_rows, "perturb")
    baseline = indexed(prior_rows, "base")
    new = indexed(new_rows, "perturb")
    if set(new) - set(missing_ids) - set(repeat_ids):
        raise ValueError("unexpected result ids outside frozen selection")
    failures, differences, omitted = [], [], []
    for identifier in repeat_ids:
        old, fresh = prior.get(identifier), new.get(identifier)
        if not complete(old) or not complete(fresh):
            failures.append({"id": identifier, "reason": "repeat missing or incomplete"})
            continue
        delta = abs(float(old["amp"]) - float(fresh["amp"]))
        passed = (
            old["diverged"] == fresh["diverged"]
            and old["pattern"] == fresh["pattern"]
            and (not (old["pattern"] and fresh["pattern"]) or old["mode"] == fresh["mode"])
            and math.isfinite(delta) and delta <= tolerance
        )
        if math.isfinite(delta):
            differences.append(delta)
        if not passed:
            failures.append({"id": identifier, "reason": "frozen repeat criteria failed", "amplitude_delta": delta if math.isfinite(delta) else None})
    flag_changes, mode_changes, settled_changes, divergent = [], [], [], []
    for identifier in missing_ids:
        fresh, base = new.get(identifier), baseline.get(identifier)
        if not complete(fresh) or not complete(base):
            omitted.append(identifier)
        elif fresh.get("diverged") or base.get("diverged"):
            divergent.append(identifier)
        else:
            if fresh["pattern"] != base["pattern"]:
                flag_changes.append(identifier)
            if fresh["pattern"] and base["pattern"] and fresh["mode"] != base["mode"]:
                mode_changes.append(identifier)
            if fresh.get("settled") != base.get("settled"):
                settled_changes.append(identifier)
    return {
        "schema": "frontier.partial-arm-completion/1",
        "completion_requested": len(missing_ids), "repeat_requested": len(repeat_ids),
        "returned_rows": len(new), "omitted_completion_ids": omitted,
        "divergent_completion_ids": divergent,
        "pattern_flag_changes_vs_unperturbed": flag_changes,
        "patterned_mode_changes_vs_unperturbed": mode_changes,
        "settled_flag_changes_vs_unperturbed": settled_changes,
        "perturbation": {"relative_initial_state_noise": 1e-10, "seed_rule": "1000000 + cell id", "source": "PROTOCOL6.md; frozen atlas_entry perturb arm"},
        "repeat_amplitude_max_absolute_difference": max(differences, default=None),
        "repeat_absolute_tolerance": tolerance,
        "repeat_failures": failures, "repeat_checks_passed": not failures,
        "biological_validity": None,
        "scope": "Completed initial-state perturbation coverage and stability within the frozen model envelope at relative noise1e-10. This is not broad physical-parameter or biological robustness.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prior", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("selection", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    def read_rows(path):
        return [json.loads(line) for line in path.read_text().splitlines()]
    selection = json.loads(args.selection.read_text())
    report = compare(read_rows(args.prior), read_rows(args.new), selection["completion_only_ids"], selection["repeat_control_ids"])
    report["source_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (args.prior, args.new, args.selection)}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))
