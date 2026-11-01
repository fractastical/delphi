"""Execute the frozen reused-specimen internal validation and observed-update demo."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import time

import numpy as np

from .model import PredictionCache, StaleModelError, blocked_folds, fit, import_observations, predict, version

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/observed-allometry"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def ref(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def score(model, row, outcome):
    actual = row["measurements"][outcome]
    result = {"observation_id": row["id"], "species": row["species"], "catalog_original": row["catalog_original"],
              "observed_cm": actual, "unit": "cm", "flags": []}
    if actual is None:
        result.update(status="not_scored", flags=["missing_outcome_not_scored"])
        return result
    prediction = predict(model, row["measurements"]["sl_cm"])
    result.update(prediction)
    if prediction["status"] == "blocked":
        result["flags"].append(prediction["failure"])
        return result
    result["residual_log10"] = float(np.log10(actual) - prediction["predicted_log10"])
    result["residual_cm"] = actual - prediction["predicted_cm"]
    if prediction["outside_training_SL_range"]:
        result["flags"].append("outside_training_SL_range")
    if prediction["uncertainty_failure"]:
        result["flags"].append(prediction["uncertainty_failure"])
    band = prediction["working_band_cm"]
    result["inside_working_band"] = None if band is None else band[0] <= actual <= band[1]
    if result["inside_working_band"] is False:
        result["flags"].append("outside_working_prediction_band")
    if outcome.removesuffix("_cm") in row["source_ratio_mismatches"]:
        result["flags"].append("source_ratio_mismatch")
    return result


def validation(rows, cfg):
    folds = []
    for scheme in ["species", "catalog"]:
        for split in blocked_folds(rows, scheme):
            train_tokens = {t for r in split["train"] for t in r["catalog_tokens"]}
            test_tokens = {t for r in split["test"] for t in r["catalog_tokens"]}
            if train_tokens & test_tokens:
                raise ValueError("Catalog leakage across blocked split")
            for outcome in cfg["model"]["outcomes"]:
                model = fit(split["train"], outcome)
                folds.append({
                    "scheme": scheme, "group": split["group"], "heldout_block": split["heldout_block"],
                    "outcome": outcome, "train_ids": [r["id"] for r in split["train"]],
                    "test_ids": [r["id"] for r in split["test"]], "purged_catalog_ids": split["purged_ids"],
                    "catalog_overlap": [], "model": model,
                    "heldout": [score(model, r, outcome) for r in split["test"]],
                })
    return folds


def update_demo(rows, cfg):
    selection = cfg["update_demo"]
    group = [r for r in rows if r["group"] == selection["group"]]
    heldout = [r for r in group if r["species"] in selection["heldout_species"]]
    forbidden = {t for r in heldout for t in r["catalog_tokens"]}
    eligible = [r for r in group if not forbidden.intersection(r["catalog_tokens"])]
    initial = [r for r in eligible if r["species"] in selection["version1_species"]]
    added = [r for r in eligible if r["species"] in selection["version2_add_species"]]
    before, after = fit(initial, selection["outcome"]), fit(initial + added, selection["outcome"])
    if before["status"] != "fitted" or after["status"] != "fitted" or not added:
        raise ValueError("Declared observed update cannot be identified")
    query = {"SL_cm": float(np.median([r["measurements"]["sl_cm"] for r in initial])),
             "group": selection["group"], "outcome": selection["outcome"], "unit": "cm"}
    cache = PredictionCache()
    first = cache.put(query, before)
    stale_rejected = False
    try:
        cache.get(query, after["version"])
    except StaleModelError:
        stale_rejected = True
    if not stale_rejected:
        raise RuntimeError("Stale dependent prediction was served")
    refreshed = cache.put(query, after)
    return {
        "schema": "frontier.observed-allometry.update/1", "before": before, "after": after,
        "added_observation_ids": [r["id"] for r in added], "heldout_ids": [r["id"] for r in heldout],
        "query": query, "old_result": first, "refreshed_result": refreshed,
        "stale_cache_rejected": stale_rejected, "cache_history": cache.history,
        "events": ["computed_v1_prediction", "imported_real_additional_subset", "rejected_stale_v1_on_v2_request", "computed_v2_prediction"],
        "prediction_change_cm": refreshed["predicted_cm"] - first["predicted_cm"],
        "heldout_before": [score(before, r, selection["outcome"]) for r in heldout],
        "heldout_after": [score(after, r, selection["outcome"]) for r in heldout],
        "scope": "Actual software observed-subset update on reused data, not newly collected observations; same previously inspected heldout species, not independent external validation. Improvement not presumed.",
    }


def run(out):
    if out.exists():
        raise ValueError("Fresh output directory required")
    start = time.monotonic()
    cfg = json.loads((ART / "protocol.json").read_text())
    contract = json.loads((ART / "import-contract.json").read_text())
    for name in ["protocol.json", "import-contract.json"]:
        path = f"artifacts/observed-allometry/{name}"
        recorded = subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)
        if recorded != (ROOT / path).read_bytes():
            raise ValueError("Uncommitted frozen protocol/import contract")
    if sha256((ART / "import-contract.json").read_bytes()).hexdigest() != cfg["input_contract_sha256"]:
        raise ValueError("Input contract differs from frozen protocol")
    rows = import_observations((ROOT / contract["path"]).read_bytes(), contract)
    dump(out / "observations.json", {"schema": contract["schema"], "dataset_sha256": contract["sha256"], "rows": rows,
                                     "scope": contract["observation_kind"]})
    folds = validation(rows, cfg)
    dump(out / "validation.json", {"folds": folds, "scope": cfg["blocking"]["comparison_scope"]})
    full = [fit([r for r in rows if r["group"] == group], endpoint) for group in cfg["model"]["groups"] for endpoint in cfg["model"]["outcomes"]]
    dump(out / "full-fits.json", {"models": full, "scope": "Descriptive refits of all nonmissing data; never used to score heldout folds"})
    demo = update_demo(rows, cfg)
    dump(out / "update.json", demo)
    summaries = []
    for scheme in ["species", "catalog"]:
        for group in cfg["model"]["groups"]:
            for outcome in cfg["model"]["outcomes"]:
                cases = [x for f in folds if f["scheme"] == scheme and f["group"] == group and f["outcome"] == outcome for x in f["heldout"]]
                scored = [x for x in cases if "residual_log10" in x]
                bands = [x for x in scored if x["inside_working_band"] is not None]
                summaries.append({
                    "scheme": scheme, "group": group, "outcome": outcome, "declared_rows": len(cases), "scored": len(scored),
                    "missing": sum(x["status"] == "not_scored" for x in cases), "blocked": sum(x["status"] == "blocked" for x in cases),
                    "RMSE_log10": float(np.sqrt(np.mean([x["residual_log10"] ** 2 for x in scored]))) if scored else None,
                    "mean_absolute_error_cm": float(np.mean([abs(x["residual_cm"]) for x in scored])) if scored else None,
                    "extrapolated": sum(x.get("outside_training_SL_range", False) for x in scored),
                    "working_band_available": len(bands), "inside_working_band": sum(x["inside_working_band"] for x in bands),
                    "scope": "Descriptive internal prediction errors; denominator is specimen rows within this scheme, not independent species/animals or future biological success",
                })
    dump(out / "summary.json", {"groups": summaries, "imported_rows": len(rows), "folds": len(folds),
                                "missing_pelvic": sum(r["measurements"]["pelvic_cm"] is None for r in rows),
                                "source_ratio_mismatches": [r["id"] for r in rows if r["source_ratio_mismatches"]],
                                "empirical_scope": "Reused preserved-specimen morphometry only; not causal, flight, regulatory or organism validation"})
    environment = {"python": platform.python_version(), "numpy": np.__version__}
    dump(out / "receipt.json", {
        "schema": "frontier.observed-allometry.receipt/1", "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "protocol": ref(ART / "protocol.json"), "import_contract": ref(ART / "import-contract.json"),
        "source_observations": ref(ROOT / contract["path"]), "code": [ref(p) for p in sorted(Path(__file__).parent.glob("*.py"))],
        "environment": environment, "environment_sha256": version(environment), "wall_seconds": time.monotonic() - start,
        "files": [ref(p) for p in sorted(out.iterdir())], "dollars": None, "provider_jobs": 0,
        "status": "computed; per-fold missing/blocked/out-of-range/band-miss flags retained", "model_choice_tuned_on_holdout": False,
    })
    print({"rows": len(rows), "folds": len(folds), "stale_rejected": demo["stale_cache_rejected"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ART / "run")
    args = parser.parse_args()
    run(args.out)
