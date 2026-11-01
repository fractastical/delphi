"""Prepare typed, unsigned documentary records from immutable observed-update blobs.

Uses the established adapter Chain/build_bundle and receiving-model/license gates.
Does not submit, lease, transition, import, review or publish any database record.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import platform

import numpy as np

from frontier_adapters.engineering_manifest import Chain, build_bundle, link_checks, resolve_commit

from .model import version
from .run import ART, ROOT, dump


def prepare(source_commit, created_at, out):
    source_commit = resolve_commit(str(ROOT), source_commit)
    c = Chain(str(ROOT), source_commit, "delphi-frontier", "mechanobio-observed-update", created_at, "observed-allometry")
    prefix = "artifacts/observed-allometry"
    receipt = c.jblob(prefix + "/run/receipt.json")
    for item in receipt["files"] + receipt["code"] + [receipt["protocol"], receipt["import_contract"], receipt["source_observations"]]:
        c.same_hash("producer-pin:" + item["path"], item["path"], item["sha256"])
    update = c.jblob(prefix + "/run/update.json")
    summary = c.jblob(prefix + "/run/summary.json")
    original = receipt["source_observations"]["path"]
    source_uri = "urn:frontier:observed-allometry:documentary-import"

    def source(path):
        return {"uri": None, "locator": f"git:delphi-frontier@{source_commit}:{path}", "source_version": source_commit,
                "content_sha256": c.artifact("output", path)["sha256"], "content_available": False,
                "access": "Immutable git blob read and hashed; pointers only, no original data embedded in this record", "license": None}

    limits = [
        "Prepared documentary records only: no DB submission/import, lease, lifecycle, acceptance or independent review.",
        "Reused author-reported preserved-specimen measurements; no new measurement or independent external validation.",
        "Catalog grouping is a dependence proxy. Only three flying-fish species; no causal, regulatory, flight or organism validation.",
        "Working Gaussian/jackknife bands are not calibrated population confidence; missing and unidentifiable values remain null.",
    ]
    raw_claim = c.add(c.draft("Claim", "observed-allometry-source-rows", {
        "title": "Stored Daane S1A observations retain original missingness and ratio inconsistency",
        "statement": f"The pinned extracted CSV contains {summary['imported_rows']} author-reported specimen rows, with {summary['missing_pelvic']} missing pelvic values and the original inconsistent ratio cell preserved.",
        "context": "A statement about the existing extracted source dataset, not new observation collection or an original-workbook re-extraction.",
        "assumptions": ["The repository's existing source extraction and author specimen identities are retained."],
        "limitations": limits, "source": source(original), "origin": "derived",
    }, source_uri))
    raw_evidence = c.add(c.draft("Evidence", "observed-allometry-source-evidence", {
        "target": raw_claim, "evidence_kind": "observed", "source": source(original),
        "created_time": {"value": None, "basis": "unknown"}, "retrieved_time": {"value": created_at, "basis": "declared"},
        "method": "Reused author-reported measurements from the exact repository CSV, imported with raw cell values, source row and digest. This adapter hashes bytes, not a new observation or original instrument check.",
        "context": "Daane2021 DataS1A preserved museum specimens, standard and fin lengths in cm, distinct taxon groups.",
        "assumptions": ["No imputation or cross-source standard-length-to-mass conversion."],
        "provenance": {"producer": "existing connectors/fish_controls extraction", "adapter": "engineering.observed_update.bundle", "source_commit": source_commit, "not_newly_observed": True},
        "source_dependence": {"group": "same Daane S1A dataset as existing full-data fits", "independent_new_data": False},
        "uncertainty": "Original measurement precision and independent animal/catalog structure not established here.",
        "limitations": limits, "relation": "context_only", "artifacts": [c.artifact("input", original)],
    }, source_uri))
    errors = {key: float(np.sqrt(np.mean([x["residual_log10"] ** 2 for x in update[key]]))) for key in ["heldout_before", "heldout_after"]}
    result_claim = c.add(c.draft("Claim", "observed-allometry-update-outcome", {
        "title": "A real observed-subset update changes prediction but worsens this held-out species",
        "statement": f"Under the frozen allometry recipe, adding 19 observed rows to 12 training rows changes the same {update['query']['SL_cm']:g} cm SL pectoral prediction from {update['old_result']['predicted_cm']:.4g} to {update['refreshed_result']['predicted_cm']:.4g} cm, rejects a stale cached result and recomputes it. Held-out 18-row RMSE increases from {errors['heldout_before']:.4g} to {errors['heldout_after']:.4g} log10 units.",
        "context": update["scope"], "assumptions": ["Fixed log10 OLS; training-only residual noise and catalog jackknife; no held-out tuning."],
        "limitations": limits, "source": source(prefix + "/run/update.json"), "origin": "derived",
    }, source_uri))
    action = c.add(c.draft("Action", "observed-allometry-documentary-analysis", {
        "target": result_claim, "title": "Prepared record of the completed local observed-data analysis; no Store lifecycle",
        "acceptance_criteria": ["Frozen protocol/data/code hashes match, all held-out results and null bands retained, stale-v1 lookup refused and v2 prediction actually recomputed. No improvement required."],
        "required_capabilities": ["Python and NumPy, one CPU, no network or GPU"],
        "cost_stop_bounds": "Declared assay bound 1 CPU/2 GiB/no-swap/128 tasks/1800 s; producer-reported wall time " + str(receipt["wall_seconds"]) + "s; dollar cost unknown.",
        "cache_key": {"target": result_claim["version"], "input": receipt["source_observations"]["sha256"],
                      "code": version(receipt["code"]), "model": "fixed-log10-allometry-catalog-jackknife-v1",
                      "environment": receipt["environment_sha256"], "parameters": receipt["protocol"]["sha256"],
                      "scope": "documentary already-executed internal validation; graph refs were not consumed before the physical run",
                      "acceptance_policy": "frontier-independent-review-0.1"},
        "inputs": [raw_claim, raw_evidence],
    }, source_uri))
    c.add(c.draft("Evidence", "observed-allometry-predicted-evidence", {
        "target": result_claim, "evidence_kind": "predicted", "source": source(prefix + "/run/update.json"),
        "created_time": {"value": None, "basis": "unknown"}, "retrieved_time": {"value": created_at, "basis": "declared"},
        "method": "Producer-executed frozen species/catalog-blocked analysis and observed-subset fit update. Adapter recomputed producer SHA pins from immutable git blobs; it did not rerun fitting or acquire measurements.",
        "context": "Reused preserved-specimen internal validation only; outcomes are predictions/residuals from observed source data.",
        "assumptions": ["No model selection based on held-out responses; training-only uncertainty as declared."],
        "provenance": {"producer_code_commit": receipt["source_commit"], "result_snapshot_commit": source_commit,
                       "adapter_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                       "adapter_path": "engineering/observed_update/bundle.py",
                       "actual_stale_rejected": update["stale_cache_rejected"], "store_execution": False},
        "source_dependence": {"group": "same data/code/author as derived Claim; dependent reused internal folds", "independent_replication": False},
        "uncertainty": "Training-only working bands; held-out error worsened. Not a calibrated organism success probability.",
        "limitations": limits, "relation": "supports", "produced_by": action,
        "artifacts": [c.artifact("output", prefix + "/run/" + name) for name in ["update.json", "validation.json", "summary.json"]]
                     + [c.artifact("protocol", prefix + "/protocol.json"), c.artifact("log", prefix + "/run/receipt.json")],
    }, source_uri))
    c.add(c.draft("Problem", "observed-allometry-transfer-gap", {
        "title": "Can context-specific observed fits transfer without hiding worsening held-out errors?",
        "known_state": "This observed update works technically but worsens held-out-species error; pooled row fitting does not establish species transfer.",
        "question": "Which predeclared context-specific alternative improves independent prediction while retaining missingness and source dependence?",
        "problem_kind": "project_gap", "novelty_status": "software/data applicability gap, not new biological discovery",
        "data_access": "Existing pinned public repository specimen table; no new data downloaded.", "completeness": "actionable",
        "acceptance_criteria": ["Freeze alternatives and new appropriate evaluation context before model selection; report all failed and null outcomes."],
        "falsifiers": ["Held-out errors worsen or assumed bands fail to cover the declared context; no general transfer claim then."],
        "next_action": "Independent review of this documentary bundle before any new experiment or model selection.",
        "required_capabilities": ["source/data statistical review"], "cost_stop_bounds": "Read-only bounded review; no new provider job.",
        "downstream_uses": ["Observed allometry choices and dependent prediction invalidation; not flight/genetic feasibility"],
        "dependencies": [result_claim, action], "source": source(prefix + "/run/update.json"), "approach": "theory_fit",
        "scales": ["organ", "organism"], "context_tags": ["reused-observations", "internal-validation", "unknown-species-transfer"],
    }, source_uri))
    bundle = build_bundle([c])
    if out.exists():
        raise ValueError("Fresh documentary bundle directory required")
    dump(out / "bundle.frontier-bundle-0.1.json", bundle)
    dump(out / "manifest.json", {"schema": "frontier.observed-allometry.bundle/1", "status": "PREPARED ONLY; no DB/import/lease/review/acceptance",
         "source_commit": source_commit, "created_at": created_at,
         "adapter_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
         "adapter_environment": {"python": platform.python_version(), "numpy": np.__version__},
         "counts": {kind: sum(r["kind"] == kind for r in c.records) for kind in ["Claim", "Problem", "Action", "Evidence"]},
         "checks": c.checks + link_checks(c.records), "bundle_sha256": bundle["bundle_sha256"],
         "not_claimed": limits})
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--out", type=Path, default=ART / "prepared-bundle-final")
    args = parser.parse_args()
    result = prepare(args.source_commit, args.created_at, args.out)
    print({"records": len(result["records"]), "bundle_sha256": result["bundle_sha256"]})
