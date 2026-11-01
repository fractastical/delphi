"""Read-only second pass over pinned GEO metadata; never fetch linked data."""

from collections import Counter
import json
from pathlib import Path
import re

from .audit import parse_soft, sha, write


def literal_candidates(fields):
    result = {"time": [], "replicate": [], "assembly": [], "annotation": []}
    for key, values in fields.items():
        for value in values:
            if key.startswith("Sample_characteristics") or key == "Sample_title":
                if re.search(r"\b\d+(?:\.\d+)?\s*(?:dpa|dpf|hpf)\b", value, re.I):
                    result["time"].append({"selector": key, "literal": value})
                if re.search(r"(?<![A-Za-z0-9])rep(?:licate)?\s*\d+\b|biological replicate:", value, re.I):
                    result["replicate"].append({"selector": key, "literal": value})
            if key in ("Sample_data_processing", "Sample_genome_build"):
                for match in re.finditer(r"GRCz\d+|danRer\d+", value):
                    result["assembly"].append({"selector": key, "literal": match.group(), "source_text": value})
                for match in re.finditer(r"Ensembl release \d+|Lawson Lab [^.;]*?(?:4\.3\.2|v\s*4\.3\.2)", value):
                    result["annotation"].append({"selector": key, "literal": match.group(), "source_text": value})
    return result


def review(out):
    receipt_bytes = (out / "receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    coverage_bytes = (out / "coverage.json").read_bytes()
    original = json.loads(coverage_bytes)
    records = {}
    for item in receipt["requests"]:
        data = (out / item["path"]).read_bytes()
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("response bytes changed")
        records[item["accession"]] = parse_soft(data, item["accession"])
    per_sample = {acc: literal_candidates(fields) for acc, fields in records.items() if acc.startswith("GSM")}
    targets = []
    files = []
    for acc, fields in records.items():
        for key, values in fields.items():
            if "supplementary_file" in key:
                for value in values:
                    if value != "NONE":
                        files.append({"accession": acc, "selector": key, "url_literal": value, "fetched": False, "bytes": None, "sha256": None})
    for row in original["coverage"]:
        ids = sorted({gsm for acc in row["series_ids"] for gsm in records[acc].get("Series_sample_id", [])})
        assays = Counter(value for acc in ids for value in records[acc].get("Sample_library_strategy", []))
        characteristics = sorted({value for acc in ids for key, values in records[acc].items() if key.startswith("Sample_characteristics") for value in values})
        targets.append({
            "target": row["target"], "sample_count": len(ids), "sample_ids": ids,
            "assembly_literals": sorted({x["literal"] for acc in ids for x in per_sample[acc]["assembly"]}),
            "annotation_literals": sorted({x["literal"] for acc in ids for x in per_sample[acc]["annotation"]}),
            "library_strategy_counts": dict(assays),
            "characteristic_values_literal": characteristics,
            "samples_with_time_literal_in_title_or_characteristic": sum(bool(per_sample[acc]["time"]) for acc in ids),
            "samples_with_replicate_literal_in_title_or_characteristic": sum(bool(per_sample[acc]["replicate"]) for acc in ids),
            "confirmed_biologically_independent_sample_count": None,
            "cell_barcode_labels_checked": False,
            "downstream_identity_gate": "unresolved; analysis stops before biological replicate pooling or cell-specific inference",
        })
    result = {
        "schema": "frontier.regulatory-metadata-review/1",
        "scope": "Literal second-pass metadata extraction; original coverage.json retained unchanged.",
        "protocol_sha256": receipt["protocol_sha256"], "protocol_commit": receipt["protocol_commit"],
        "collector_commit": receipt["source_commit"], "collector_sha256": receipt["source_sha256"],
        "review_code_sha256": sha(Path(__file__).read_bytes()),
        "receipt_sha256": sha(receipt_bytes), "original_coverage_sha256": sha(coverage_bytes),
        "targets": targets, "per_sample_candidates": per_sample, "unfetched_processed_file_manifest": files,
        "interpretation_limits": [
            "Title rep1/rep2 and characteristic biological replicate labels are preserved as labels, not proof of donor independence or assay pairing.",
            "Time-like values under the original key passages are exposed as literal candidates, not silently renamed time metadata.",
            "Assembly names are literal substring matches with source text; their presence is not coordinate compatibility.",
            "No file linked by supplementary URL was fetched, sized or checksummed; cell annotations are not verified.",
        ],
    }
    write(out / "coverage-reviewed.json", result)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = review(args.out)
    print(json.dumps({"targets": len(result["targets"]), "samples": len(result["per_sample_candidates"]), "unfetched_links": len(result["unfetched_processed_file_manifest"])}))
