"""Publish the frozen observed-update downloads and one concise evidence card.

The caller supplies tracked byte reads and the usual build_site output mapping.
No filesystem scan, network, Store, numerical fitting or model import occurs.
"""

from hashlib import sha256
import json
import math
from pathlib import PurePosixPath

DIRECTORY = "artifacts/observed-allometry"
PUBLICATION_SHA256 = "b5bdee560dead327da5095aa29bfb6fd1526e81216d03257e98663ea971ab7e5"
IMPORT_RECEIPT_SHA256 = "1b4172269d89914eddff17b7bb4aef63068fdba4db9f08b00d23209a52a5aae7"
EXPECTED = (
    "observed-update.png", "RESULTS.md", "graph-summary.md", "source-observations.csv", "protocol.json", "import-contract.json",
    "run/summary.json", "run/update.json", "run/full-fits.json", "run/validation.json", "run/receipt.json", "context-transfer.json",
    "prepared-bundle-final/bundle.frontier-bundle-0.1.json", "prepared-bundle-final/manifest.json", "CORRECTION.md",
    "component-purge-correction.json", "component-purge-comparison.json", "run-component-purge-v2-complete/receipt.json",
    "run-component-purge-v2-complete/summary.json", "run-component-purge-v2-complete/validation.json",
    "run-component-purge-v2-complete/update.json", "prepared-bundle-component-purge-v2/bundle.frontier-bundle-0.1.json",
    "prepared-bundle-component-purge-v2/manifest.json",
)


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def build(ins, out):
    """Verify all 23 declared downloads before adding any output; return a card."""
    raw = ins.read(f"{DIRECTORY}/publication.json")
    if len(raw) > 32768:
        raise ValueError("Observed publication manifest too large")
    manifest = json.loads(raw)
    files = manifest["files"]
    expected = {f"{DIRECTORY}/{name}" for name in EXPECTED}
    paths = [item["path"] for item in files]
    if len(paths) != 23 or len(set(paths)) != 23 or set(paths) != expected:
        raise ValueError("Observed publication requires exactly the fixed 23 safe paths")
    for item in files:
        path = PurePosixPath(item["path"])
        if path.is_absolute() or ".." in path.parts or str(path) != item["path"] or item["href"] != item["path"]:
            raise ValueError("Unsafe observed publication path or href")
    if sha256(raw).hexdigest() != PUBLICATION_SHA256:
        raise ValueError("Observed publication manifest digest changed")
    staged = {"@" + DIRECTORY + "/publication.json": raw}
    pins, content = {}, {}
    for item in files:
        path = item["path"]
        blob = ins.read(path)
        if not isinstance(item["bytes"], int) or not 0 <= item["bytes"] <= 2_000_000:
            raise ValueError("Observed artifact size outside bound")
        if sha256(blob).hexdigest() != item["sha256"] or len(blob) != item["bytes"]:
            raise ValueError("Observed artifact digest/size mismatch: " + path)
        staged["@" + path] = blob
        pins[path], content[path.removeprefix(DIRECTORY + "/")] = item, blob
    if sum(len(blob) for blob in staged.values()) > 4_000_000:
        raise ValueError("Observed publication exceeds total byte bound")
    def parsed(name):
        return json.loads(content[name])
    update = parsed("run-component-purge-v2-complete/update.json")
    summary = parsed("run-component-purge-v2-complete/summary.json")
    comparison = parsed("component-purge-comparison.json")
    if summary["imported_rows"] != 109 or summary["folds"] != 82 or not update["stale_cache_rejected"]:
        raise ValueError("Observed displayed identities/counts differ")
    if comparison["original_component_overlap_folds"] or len(comparison["comparisons"]) != 5 or not all(x["all_scientific_fields_exactly_equal"] for x in comparison["comparisons"]):
        raise ValueError("Observed correction comparison differs")
    for directory in ["run", "run-component-purge-v2-complete"]:
        receipt = parsed(directory + "/receipt.json")
        for item in receipt["files"]:
            if item["path"] in pins and (pins[item["path"]]["sha256"], pins[item["path"]]["bytes"]) != (item["sha256"], item["bytes"]):
                raise ValueError("Observed native receipt differs from publication")
    errors = {name: math.sqrt(sum(x["residual_log10"]**2 for x in update[name]) / len(update[name])) for name in ["heldout_before", "heldout_after"]}
    current = parsed("prepared-bundle-component-purge-v2/bundle.frontier-bundle-0.1.json")
    receipt_raw = ins.read(f"{DIRECTORY}/live-import/public-receipt.json")
    if len(receipt_raw) > 65536:
        raise ValueError("Observed import receipt too large")
    receipt = json.loads(receipt_raw)
    if receipt.get("receipt_sha256") != IMPORT_RECEIPT_SHA256 or _digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}) != IMPORT_RECEIPT_SHA256:
        raise ValueError("Observed import receipt digest changed")
    refs = [{k: record[k] for k in ["namespace", "kind", "id", "version"]} for record in current["records"]]
    if receipt["refs"] != refs or receipt["inserted_total"] != 6 or receipt["forks_recorded"] != 0:
        raise ValueError("Observed import receipt identities/counts differ")
    if any(v["verified_ok"] != 6 or v["problems"] or v["status_counts"] != {"imported_unreviewed": 6} for v in receipt["verification"].values()):
        raise ValueError("Observed imported records were not read back unreviewed")
    staged[f"@{DIRECTORY}/live-import/public-receipt.json"] = receipt_raw
    out.update(staged)
    return {
        "id": "observed-allometry-update", "title": "Observed-data update: added specimens worsen held-out transfer",
        "scales": ["organ", "organism"], "evidence_kind": "Reused observed measurements and separately labelled fitted predictions",
        "model": {"name": "Fixed log10 fin-length allometry; blocked internal validation",
                  "context": "109 preserved-specimen rows, 82 species/catalog-outcome folds. Adding 19 rows to 12 changes a cached prediction, but held-out-species error worsens. Only three flying-fish species; no independent biological validation."},
        "facts": {"observed_rows": 109, "folds": 82, "new_measurements": 0, "missing_pelvic": summary["missing_pelvic"],
                  "query_SL_cm": update["query"]["SL_cm"], "prediction_before_cm": update["old_result"]["predicted_cm"],
                  "prediction_after_cm": update["refreshed_result"]["predicted_cm"], "heldout_RMSE_log10": errors,
                  "stale_cache_rejected": True, "biological_success_probability": None},
        "poster_href": f"{DIRECTORY}/observed-update.png", "poster_is_figure": True, "poster_state": "present_verified",
        "poster": {"file": "observed-update.png", "sha256": pins[f"{DIRECTORY}/observed-update.png"]["sha256"]},
        "video_state": "none", "video_href": None, "video": {"file": None, "sha256": None, "note": "Observed/predicted static plot; no physical trajectory."},
        "report": f"{DIRECTORY}/RESULTS.md", "correction_report": f"{DIRECTORY}/CORRECTION.md", "manifest": f"{DIRECTORY}/publication.json",
        "downloads": files, "artifacts": files, "record_refs": refs, "record_status": "imported_unreviewed; Action proposed",
        "import_receipt_href": f"{DIRECTORY}/live-import/public-receipt.json",
        "current_bundle_href": f"{DIRECTORY}/prepared-bundle-component-purge-v2/bundle.frontier-bundle-0.1.json",
        "historical_bundle_href": f"{DIRECTORY}/prepared-bundle-final/bundle.frontier-bundle-0.1.json",
        "limitations": ["Reused-dataset internal validation; observations, predictions and uncertainty remain distinct.",
                        "RMSE worsened; more data did not guarantee better transfer. Working bands are not calibrated population confidence.",
                        "Original corrupt ratio/missingness and historical outputs preserved. Transitive catalog fix has exactly equal scientific outputs on this dataset.",
                        "Documentary import is not Claim reuse or analysis lease execution. No acceptance/review, causal, regulatory or flight validation."],
        "sources": [{"label": "Daane et al.2021 DataS1A", "locator": "doi:10.1016/j.cub.2021.08.054; A - fin measurement"}],
        "native": True,
    }
