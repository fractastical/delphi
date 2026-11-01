"""Compare additive seed experiments without hiding incomplete or confounded arms."""

import argparse
from hashlib import sha256
from pathlib import Path

from .analyze import load
from .model import ART, dump
from .seed_experiment import VARIANT, validate


PAIR_FIELDS = (
    "initialization_seed",
    "regime",
    "training_steps",
    "CA_updates_total",
    "initial_model_tensor_sha256",
)


def pair_check(parent, variant):
    """Training inputs and budgets must match independently of outcome."""
    identities = {x["id"] for x in parent}
    if len(identities) != len(parent) or len({x["id"] for x in variant}) != len(
        variant
    ):
        raise ValueError("Duplicate candidate identity")
    lookup = {x["id"]: x for x in variant}
    if set(lookup) - identities:
        raise ValueError("Invented candidate identity")
    return [
        {
            "id": old["id"],
            "parent_status": old["status"],
            "variant_status": lookup.get(old["id"], {}).get("status", "missing"),
            "fields": {
                key: {
                    "parent": old.get(key),
                    "variant": lookup.get(old["id"], {}).get(key),
                    "exact_match": key in old
                    and key in lookup.get(old["id"], {})
                    and old[key] == lookup[old["id"]][key],
                }
                for key in PAIR_FIELDS
            },
        }
        for old in parent
    ]


def compare(variant_root, audit_path, out):
    validate()
    parent_root = ART / "run-original"
    parent, variant = [
        load(root / "summary.json") for root in (parent_root, variant_root)
    ]
    old_receipt, new_receipt = [
        load(root / "job-receipt.json") for root in (parent_root, variant_root)
    ]
    for root, receipt in [(parent_root, old_receipt), (variant_root, new_receipt)]:
        expected = next(
            x["sha256"] for x in receipt["files"] if x["path"] == "summary.json"
        )
        if sha256((root / "summary.json").read_bytes()).hexdigest() != expected:
            raise ValueError("Summary changed after execution")
    audit = load(audit_path)
    if (
        audit["job_receipt_sha256"]
        != sha256((variant_root / "job-receipt.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Audit receipt changed")
    if not audit["fixed_roundoff_visible_metric_reproduction"]:
        raise ValueError("Visible metric reproduction failed; preserve failure instead")
    if (
        new_receipt["protocol_sha256"]
        != sha256((VARIANT / "protocol.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Variant run not bound to declared seed inputs")
    pairs = pair_check(parent["models"], variant["models"])
    source_match = old_receipt["sources"] == new_receipt["sources"]
    environment_match = (
        old_receipt["environment"] == new_receipt["environment"]
        and old_receipt["device"] == new_receipt["device"]
    )
    paired_complete = all(
        x["parent_status"] == "complete"
        and x["variant_status"] == "complete"
        and all(v["exact_match"] for v in x["fields"].values())
        for x in pairs
    )
    rows = []
    for kind in [
        "persistence",
        "left-half",
        "central-square",
        "diagonal-slit",
        "all-erased-negative",
    ]:
        row = {"kind": kind}
        for name, summary in [("parent", parent), ("variant", variant)]:
            runs = [
                x
                for x in summary["evaluations"]
                if x["kind"] == kind and not x["status"].startswith("not-started")
            ]
            row[name] = {
                "executed": len(runs),
                "passed": sum(x["criterion_passed"] for x in runs),
            }
        rows.append(row)
    result = {
        "schema": "frontier.nca.seed-placement-comparison/1",
        "parent_protocol_sha256": old_receipt["protocol_sha256"],
        "variant_protocol_sha256": new_receipt["protocol_sha256"],
        "one_factor_protocol_sha256": sha256(
            (VARIANT / "one-factor-protocol.json").read_bytes()
        ).hexdigest(),
        "parent_receipt_sha256": sha256(
            (parent_root / "job-receipt.json").read_bytes()
        ).hexdigest(),
        "variant_receipt_sha256": sha256(
            (variant_root / "job-receipt.json").read_bytes()
        ).hexdigest(),
        "same_execution_source_bytes": source_match,
        "same_reported_runtime_environment_and_device": environment_match,
        "paired_training_inputs_and_update_budgets_match": paired_complete,
        "recorded_model_input_comparison_conditions_satisfied": source_match
        and environment_match
        and paired_complete,
        "container_image_digest_equivalence": "unknown: historical provider receipt exposes mutable tag only; matching recorded package/device versions is not full image identity",
        "training_pairs": pairs,
        "evaluation_counts_by_kind": rows,
        "parent_status": parent["status"],
        "variant_status": variant["status"],
        "tests_reused_from_parent": True,
        "biological_success_probability": None,
        "scope": "Seed-only computational intervention with reused test cases and shared model/target/training seeds. Outcomes do not establish biological regeneration, fresh-test generalization or independent biological replication. Environment/budget differences remain explicit confounds.",
        "analysis_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    dump(out, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.variant_root, args.audit, args.out)
    print(
        {
            key: result[key]
            for key in [
                "same_execution_source_bytes",
                "same_reported_runtime_environment_and_device",
                "paired_training_inputs_and_update_budgets_match",
                "evaluation_counts_by_kind",
            ]
        }
    )
