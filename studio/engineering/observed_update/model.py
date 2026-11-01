"""Reusable observed import, blocked allometry and exact-version prediction cache.

Measurements are author-reported preserved-specimen values, not newly collected
observations. Catalog links are conservative dependence proxies, not verified
independent animals. Prediction bands are conditional working assumptions.
"""

import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re

import numpy as np


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def version(value):
    return sha256(canonical(value).encode()).hexdigest()


def import_observations(raw, contract):
    if sha256(raw).hexdigest() != contract["sha256"]:
        raise ValueError("Observed source digest changed")
    reader = csv.DictReader(io.StringIO(raw.decode()))
    if reader.fieldnames != contract["required_columns"]:
        raise ValueError("Observed source columns changed")
    result, ids = [], set()
    for line, row in enumerate(reader, 2):
        identifier = f"daane2021-s1a-fish-{int(row['fish_no']):03d}"
        if identifier in ids:
            raise ValueError("Duplicate observed specimen ID")
        ids.add(identifier)
        if not row["species"] or not row["group"] or not re.fullmatch(r"\d+(?:\s*,\s*\d+)*", row["mcz_catalog_no"]):
            raise ValueError("Unresolved taxon/catalog identity")
        values = {}
        for key in contract["units"]:
            value = None if row[key] == "" else float(row[key])
            if value is not None and (not np.isfinite(value) or value <= 0):
                raise ValueError("Measurement must be positive finite or explicitly missing")
            values[key] = value
        if values["sl_cm"] is None:
            raise ValueError("Missing predictor; no imputation supported")
        mismatches = []
        for endpoint in ["pectoral", "pelvic"]:
            actual = values[endpoint + "_cm"]
            printed = row["sheet_" + endpoint + "_over_sl"]
            if actual is not None and printed and not np.isclose(float(printed), actual / values["sl_cm"], rtol=1e-10, atol=1e-12):
                mismatches.append(endpoint)
        result.append({
            "id": identifier, "fish_no": int(row["fish_no"]), "species": row["species"], "group": row["group"],
            "catalog_original": row["mcz_catalog_no"], "catalog_tokens": sorted(set(row["mcz_catalog_no"].replace(" ", "").split(","))),
            "measurements": values, "raw_source_cells": row,
            "source_ratio_mismatches": mismatches,
            "source": {"dataset_sha256": contract["sha256"], "csv_line": line},
            "kind": "reused_author_reported_observation", "units": contract["units"],
        })
    if len(result) != contract["rows_expected"]:
        raise ValueError("Observed row count changed")
    return result


def catalog_components(rows):
    """Connected components retain shared multi-token catalog dependence."""
    parents = {x["id"]: x["id"] for x in rows}

    def find(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    owner = {}
    for row in sorted(rows, key=lambda x: x["id"]):
        for token in row["catalog_tokens"]:
            if token in owner:
                left, right = find(row["id"]), find(owner[token])
                parents[max(left, right)] = min(left, right)
            else:
                owner[token] = row["id"]
    return {x["id"]: find(x["id"]) for x in rows}


def blocked_folds(rows, scheme):
    for group in sorted({x["group"] for x in rows}):
        subset = [x for x in rows if x["group"] == group]
        components = catalog_components(subset)
        labels = {x["id"]: x["species"] if scheme == "species" else components[x["id"]] for x in subset}
        if scheme not in {"species", "catalog"}:
            raise ValueError("Unknown blocking scheme")
        for label in sorted(set(labels.values())):
            test = [x for x in subset if labels[x["id"]] == label]
            held_components = {components[x["id"]] for x in test}
            candidates = [x for x in subset if labels[x["id"]] != label]
            train = [x for x in candidates if components[x["id"]] not in held_components]
            purged = [x["id"] for x in candidates if components[x["id"]] in held_components]
            yield {"scheme": scheme, "group": group, "heldout_block": label, "train": train, "test": test, "purged_ids": purged}


def coefficients(rows, outcome):
    valid = [x for x in rows if x["measurements"][outcome] is not None]
    if len(valid) < 3:
        return None, valid, "n_train<3"
    x = np.array([r["measurements"]["sl_cm"] for r in valid])
    y = np.array([r["measurements"][outcome] for r in valid])
    design = np.column_stack([np.ones(len(x)), np.log10(x)])
    beta, _, rank, _ = np.linalg.lstsq(design, np.log10(y), rcond=None)
    if rank != 2:
        return None, valid, "rank_deficient"
    return (beta, design, np.log10(y)), valid, None


def fit(rows, outcome):
    groups = {x["group"] for x in rows}
    if len(groups) > 1:
        raise ValueError("Do not pool taxon groups implicitly")
    data, valid, error = coefficients(rows, outcome)
    metadata = {
        "schema": "frontier.observed-allometry.fit/1", "outcome": outcome, "group": next(iter(groups), None),
        "training_ids": sorted(x["id"] for x in valid), "training_metadata_ids": sorted(x["id"] for x in rows),
        "observed_input_sha256": version(rows), "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "numpy_version": np.__version__, "units": "numeric lengths in cm; log10(length/(1cm))",
        "species": sorted({x["species"] for x in valid}), "status": "blocked" if error else "fitted",
        "failure": error, "uncertainty_scope": "Training-only working noise and catalog jackknife, not calibrated population uncertainty",
    }
    if not error:
        beta, design, response = data
        residual = response - design @ beta
        noise = float(residual @ residual / (len(valid) - 2))
        labels = catalog_components(rows)
        clusters = sorted({labels[x["id"]] for x in valid})
        estimates = []
        for cluster in clusters:
            reduced = [x for x in rows if labels[x["id"]] != cluster]
            result, _, failed = coefficients(reduced, outcome)
            if failed:
                break
            estimates.append(result[0])
        covariance = None
        if len(clusters) >= 3 and len(estimates) == len(clusters):
            estimates = np.asarray(estimates)
            centered = estimates - estimates.mean(axis=0)
            covariance = ((len(clusters) - 1) / len(clusters) * centered.T @ centered).tolist()
        metadata.update(
            coefficients=beta.tolist(), n_train=len(valid), noise_variance_log10=noise,
            catalog_components=len(clusters), jackknife_covariance=covariance,
            uncertainty_failure=None if covariance is not None else "catalog_uncertainty_unidentifiable",
            training_SL_cm_range=[min(r["measurements"]["sl_cm"] for r in valid), max(r["measurements"]["sl_cm"] for r in valid)],
            residuals=[{"id": r["id"], "observed_cm": r["measurements"][outcome], "residual_log10": float(e)} for r, e in zip(valid, residual, strict=True)],
        )
    metadata["version"] = version(metadata)
    return metadata


def predict(model, sl_cm):
    if model["status"] != "fitted":
        return {"status": "blocked", "failure": model["failure"]}
    if not np.isfinite(sl_cm) or sl_cm <= 0:
        raise ValueError("Positive finite standard length required")
    h = np.array([1., np.log10(sl_cm)])
    mean = float(h @ np.asarray(model["coefficients"]))
    band, variance = None, None
    if model["jackknife_covariance"] is not None:
        variance = float(h @ np.asarray(model["jackknife_covariance"]) @ h + model["noise_variance_log10"])
        width = 1.959963984540054 * np.sqrt(max(0., variance))
        band = [float(10 ** (mean - width)), float(10 ** (mean + width))]
    return {
        "status": "predicted", "model_version": model["version"], "SL_cm": sl_cm,
        "predicted_log10": mean, "predicted_cm": float(10 ** mean),
        "working_band_cm": band, "working_prediction_variance_log10": variance,
        "outside_training_SL_range": not model["training_SL_cm_range"][0] <= sl_cm <= model["training_SL_cm_range"][1],
        "uncertainty_failure": model["uncertainty_failure"],
    }


class StaleModelError(ValueError):
    pass


class PredictionCache:
    """Exact-version lookup rejects stale values; old entries remain in history."""

    def __init__(self):
        self.entries = {}
        self.history = []

    def put(self, query, model):
        if query["group"] != model["group"] or query["outcome"] != model["outcome"] or query["unit"] != "cm":
            raise ValueError("Allometry query context/unit differs from fitted model")
        result = predict(model, query["SL_cm"])
        entry = {"query": query, "model_version": model["version"], "result": result}
        self.history.append(entry)
        self.entries[version(query)] = entry
        return result

    def get(self, query, required_version):
        entry = self.entries[version(query)]
        if entry["model_version"] != required_version:
            raise StaleModelError("Cached allometry result uses superseded observed-fit version")
        return entry["result"]
