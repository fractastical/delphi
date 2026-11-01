"""Compare preserved original and corrected assay outputs without rewriting either."""

import argparse
import json
from pathlib import Path

from .model import catalog_components
from .run import ART, dump, ref


def compare(original, corrected, out):
    original, corrected = original.resolve(), corrected.resolve()
    rows = json.loads((original / "observations.json").read_text())["rows"]
    validation = json.loads((original / "validation.json").read_text())["folds"]
    leaks = []
    for fold in validation:
        components = catalog_components([r for r in rows if r["group"] == fold["group"]])
        overlap = {components[x] for x in fold["train_ids"]} & {components[x] for x in fold["test_ids"]}
        if overlap:
            leaks.append({"scheme": fold["scheme"], "group": fold["group"], "outcome": fold["outcome"], "heldout_block": fold["heldout_block"], "overlap": sorted(overlap)})
    ignored = {"version", "model_version", "code_sha256"}
    def scientific(value):
        if isinstance(value, dict):
            return {k: scientific(v) for k, v in value.items() if k not in ignored}
        if isinstance(value, list):
            return [scientific(v) for v in value]
        return value
    comparisons = []
    for name in ["observations.json", "validation.json", "full-fits.json", "summary.json", "update.json"]:
        left, right = original / name, corrected / name
        a, b = json.loads(left.read_text()), json.loads(right.read_text())
        comparisons.append({"file": name, "original": ref(left), "corrected": ref(right),
                            "bytes_equal": left.read_bytes() == right.read_bytes(),
                            "all_scientific_fields_exactly_equal": scientific(a) == scientific(b)})
    dump(out, {"schema": "frontier.observed-allometry.correction-audit/1", "original_component_overlap_folds": leaks,
               "original_fold_count": len(validation), "comparisons": comparisons,
               "ignored_metadata_keys": sorted(ignored), "numeric_tolerance": None,
               "scope": "Exact comparison of all fields excluding the three explicitly named code/version identifiers. No tolerance, model or acceptance change. General transitive-chain bug is fixed even if this particular source dataset has no leaking folds.",
               "original_receipt": ref(original / "receipt.json"), "corrected_receipt": ref(corrected / "receipt.json"),
               "audit_code": ref(Path(__file__)), "correction": ref(ART / "component-purge-correction.json")})
    return comparisons, leaks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=ART / "run")
    parser.add_argument("--corrected", type=Path, default=ART / "run-component-purge-v2-complete")
    parser.add_argument("--out", type=Path, default=ART / "component-purge-comparison.json")
    args = parser.parse_args()
    comparisons, leaks = compare(args.original, args.corrected, args.out)
    print({"files_equal_excluding_declared_metadata": sum(x["all_scientific_fields_exactly_equal"] for x in comparisons), "compared": len(comparisons), "original_leaking_folds": len(leaks)})
