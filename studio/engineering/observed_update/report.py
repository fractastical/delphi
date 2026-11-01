"""Report actual reused observations, held-out residuals and update failures."""

from pathlib import Path
from hashlib import sha256
import json

import numpy as np

from .run import ART, dump, ref


def run():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    native = ART / "run"
    rows = json.loads((native / "observations.json").read_text())["rows"]
    summary = json.loads((native / "summary.json").read_text())
    update = json.loads((native / "update.json").read_text())
    receipt = json.loads((native / "receipt.json").read_text())
    folds = json.loads((native / "validation.json").read_text())["folds"]
    context_rows = [
        {"scheme": fold["scheme"], "group": fold["group"], "outcome": fold["outcome"],
         "heldout_block": fold["heldout_block"], "model_version": fold["model"]["version"],
         "observation_id": row["observation_id"], "test_species": row["species"],
         "training_species": fold["model"]["species"],
         "unseen_species_context": row["species"] not in fold["model"]["species"]}
        for fold in folds for row in fold["heldout"]
    ]
    dump(ART / "context-transfer.json", {
        "schema": "frontier.observed-allometry.context-audit/1", "rows": context_rows,
        "scope": "Descriptive postprocessing of saved contexts, not a new acceptance gate or numerical run. Unseen species flags applicability transfer, not a calibrated confidence penalty.",
    })
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8), layout="constrained")
    names = ["Cheilopogon furcatus", "Exocoetus volitans", "Hirundichthys rondeleti"]
    for i, name in enumerate(names):
        subset = [r for r in rows if r["species"] == name]
        axes[0, 0].scatter([r["measurements"]["sl_cm"] for r in subset], [r["measurements"]["pectoral_cm"] for r in subset], s=16, color=f"C{i}", label=name + (" (held out)" if i == 2 else " (training)"))
    for key, style, color in [("before", "--", "C0"), ("after", "-", "C1")]:
        model = update[key]
        grid = np.geomspace(*model["training_SL_cm_range"], 100)
        values = 10 ** (model["coefficients"][0] + model["coefficients"][1] * np.log10(grid))
        axes[0, 0].plot(grid, values, style, color=color, label=f"{key}: {model['n_train']} observed rows")
    axes[0, 0].set(xlabel="Observed standard length (cm)", ylabel="Observed / predicted pectoral length (cm)", title="Points: author-reported observations; lines: fits")
    axes[0, 0].legend(fontsize=7)
    for i, key in enumerate(["old_result", "refreshed_result"]):
        item = update[key]
        lo, hi = item["working_band_cm"]
        y = item["predicted_cm"]
        axes[0, 1].errorbar(i, y, yerr=[[y - lo], [hi - y]], fmt="o", capsize=6, color=f"C{i}")
    axes[0, 1].set_xticks([0, 1], ["v1: 12 rows", "v2: 31 rows"])
    axes[0, 1].set(ylabel="Predicted pectoral length (cm)", title=f"Same {update['query']['SL_cm']:g} cm SL query; stale result rejected")
    axes[0, 1].text(.03, .03, "Working bands, not calibrated confidence\nQuery is a design input, not a new measurement", transform=axes[0, 1].transAxes, fontsize=8)
    for key, label, style in [("heldout_before", "v1 held-out errors", "o"), ("heldout_after", "v2 held-out errors", "x")]:
        cases = update[key]
        axes[1, 0].scatter([x["SL_cm"] for x in cases], [x["residual_log10"] for x in cases], marker=style, label=label)
    axes[1, 0].axhline(0, color="gray", linewidth=.7)
    axes[1, 0].set(xlabel="Held-out standard length (cm)", ylabel="Observed minus predicted log10 length", title="Adding data worsened this held-out species")
    axes[1, 0].legend(fontsize=8)
    selected = [x for x in summary["groups"] if x["scheme"] == "species"]
    axes[1, 1].barh(range(len(selected)), [x["RMSE_log10"] or 0 for x in selected])
    axes[1, 1].set_yticks(range(len(selected)), [x["group"] + " / " + x["outcome"].removesuffix("_cm") for x in selected], fontsize=7)
    axes[1, 1].set(xlabel="Species-blocked RMSE, log10 length", title="All declared groups/endpoints retained")
    fig.suptitle("Observed-data update and internal validation | reused preserved specimens\nNo causal, flight, genetic or organism-validation inference", fontsize=12)
    fig.savefig(ART / "observed-update.png", dpi=120)
    plt.close(fig)
    errors = {key: float(np.sqrt(np.mean([x["residual_log10"] ** 2 for x in update[key]]))) for key in ["heldout_before", "heldout_after"]}
    table = "\n".join(f"| {x['scheme']} | {x['group']} | {x['outcome']} | {x['scored']}/{x['declared_rows']} | {x['missing']} | {x['blocked']} | {x['RMSE_log10']:.3g} | {x['extrapolated']} | {x['inside_working_band']}/{x['working_band_available']} |" for x in summary["groups"])
    text = f"""# Actual observed-data update: a useful worsening result

Imported **{summary['imported_rows']} author-reported specimen rows**, preserving raw source cells, identities and units. The frozen species/catalog validation ran **{summary['folds']} outcome-specific folds**. These are reused observations, not newly collected measurements or an independent external test.

The real update adds 19 Exocoetus volitans observations to 12 Cheilopogon furcatus training rows. At the same training-derived SL query **{update['query']['SL_cm']:g} cm**, predicted pectoral length changes **{update['old_result']['predicted_cm']:.3g} → {update['refreshed_result']['predicted_cm']:.3g} cm**. The v1 cache was actually requested with the v2 model version, refused as stale, and recomputed; both results and the rejection event remain in run/update.json. This is a working model update, not a cosmetic lineage edge.

On the same 18 held-out Hirundichthys rondeleti rows, RMSE **worsens {errors['heldout_before']:.3g} → {errors['heldout_after']:.3g} log10 units**. More observed data did not guarantee better transfer. No model selection, threshold or uncertainty estimate was changed after this result.

The training context also broadens from one species to two: the common query is a descriptive pooled-group prediction, not a calibrated prediction for every flying fish. `context-transfer.json` explicitly marks held-out species absent from each saved training context. That is a postprocessing applicability flag, not a newly introduced pass/fail criterion.

| Blocking | Group | Outcome | Scored / declared | Missing | Blocked | RMSE log10 | Extrapolated | Inside working band / available |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}

Errors include extrapolated cases; missing outcomes are unscored, never zero-filled. Species and catalog validation reuse the same records and must not be pooled as independent evidence. Each species is completely excluded from its training fold; shared catalog-token components are also excluded. Comma-separated catalog labels are conservative dependence links, not verified independent animal IDs. Only three flying-fish species (18/19/12 rows) are available. Source specimen/measurement context, not biological success, defines applicability.

Training-only residual noise uses SSE/(n−2); parameter covariance uses delete-one catalog-component jackknife only when identifiable. The Gaussian ±1.96 prediction bands are **working conditional bands, not calibrated 95% confidence or future coverage claims**. Their observed internal inclusion counts are shown without treating cells/specimens as independent species replicates. Unidentifiable bands stay null; rank/insufficient-sample blocks and every band miss remain in run/validation.json.

Residual variance combines measurement error, model misspecification and specimen/taxon heterogeneity; these components are not separately identified by this fit.

All 18 missing pelvic values remain missing. The corrupt first source pelvic/SL ratio remains unchanged beside the source lengths and derived ratio; no silent replacement occurs. Existing data/fish-controls files, connector download/extraction code and the prospective experimental_design API are unchanged. No SL→mass conversion or Fish1990 raw data is invented.

Model form: log10(fin/(1 cm))=beta0+beta1 log10(SL/(1 cm)), the same allometry form as connectors/fish_controls/build.py:fit. This work adds blocked internal validation, train-only working uncertainty, stable observed/model versions and actual cache invalidation; it is not a new biological law. Full-data descriptive fits are stored separately and were never used to score held-out folds.

Source: Daane2021, DOI10.1016/j.cub.2021.08.054, Data S1A sheet A - fin measurement; exact stored CSV SHA is in import-contract.json. Original workbook is not re-fetched. Native assay wall time **{receipt['wall_seconds']:.3f}s**, under one CPU/thread,2GiB/no-swap/128tasks/1800s bounds. Environment {receipt['environment']}; dollars unknown, no provider/GPU job. Six focused controls passed before production: analytic power law, rank refusal, held-out-response mutation, blocked catalogs, source identity/missingness and stale-cache refusal. Receipt retains source/code/environment/protocol/output hashes.

The figure uses actual source measurements and fitted/predicted values with separate labels. It is a static analysis figure, not measured morphology rendered from the model. Artifact proposals, if prepared, are not DB integration, lease execution, independent review or acceptance. Regulatory/cell/material/flight bridges remain unknown.
"""
    (ART / "RESULTS.md").write_text(text)
    dump(ART / "render-provenance.json", {"schema": "frontier.observed-allometry.render/1", "code": ref(Path(__file__)),
         "inputs": [ref(native / name) for name in ["observations.json", "update.json", "summary.json"]],
         "output": ref(ART / "observed-update.png"), "scope": "Actual author-reported observations plus separately labelled computed lines/bands; no generated observations"})
    bundle = ART / "prepared-bundle-final/bundle.frontier-bundle-0.1.json"
    source = Path(receipt["source_observations"]["path"])
    source_bytes = source.read_bytes()
    if sha256(source_bytes).hexdigest() != receipt["source_observations"]["sha256"]:
        raise ValueError("Direct-download observation source changed")
    (ART / "source-observations.csv").write_bytes(source_bytes)
    narrative = f"""# Observed-data update, with worsening held-out error

Reused 109 author-reported preserved-specimen rows from Daane et al. (2021), Data S1A ([paper](https://doi.org/10.1016/j.cub.2021.08.054)), retaining 18 missing pelvic measurements and the original corrupt ratio cell. The 82 species/catalog-outcome folds use training-only residual variance and catalog jackknife. No new measurements were collected.

Adding 19 observed rows to 12 training rows changes the same 8.35 cm standard-length query from 5.56 to 5.46 cm predicted pectoral length. An actual exact-version cache lookup rejects the old result and recomputes its successor. On 18 held-out H. rondeleti rows, RMSE worsens from {errors['heldout_before']:.3g} to {errors['heldout_after']:.3g} log10 units. More data did not guarantee better transfer.

Only three flying-fish species are present; this is reused-dataset internal validation. Working prediction bands are not calibrated population confidence. Source observations, fitted predictions and computed uncertainty remain distinct. No causal, genetic, flight or organism-success claim is made.

Six typed documentary records are prepared (2 Claims, 1 Problem, 1 Action, 2 Evidence), separating observed-source from predicted-fit evidence. No database import, submission, lease, independent review or acceptance occurred. publication.json declares exact files/hashes for root to copy and verify; public serving is not claimed by this package.
"""
    (ART / "graph-summary.md").write_text(narrative)
    files = ["observed-update.png", "RESULTS.md", "graph-summary.md", "source-observations.csv", "protocol.json", "import-contract.json",
             "run/summary.json", "run/update.json", "run/full-fits.json", "run/validation.json", "run/receipt.json",
             "context-transfer.json", "prepared-bundle-final/bundle.frontier-bundle-0.1.json", "prepared-bundle-final/manifest.json"]
    dump(ART / "publication.json", {"schema": "frontier.observed-allometry.publication/1",
         "status": "PREPARED, not publicly served by this producer; root must copy bytes and verify HTTPS status/hash",
         "files": [{**ref(ART / name), "href": "artifacts/observed-allometry/" + name} for name in files]})
    dump(ART / "index.json", {"schema": "frontier.observed-allometry.index/1", "status": "computed internal validation; update worsens heldout-species RMSE",
         "observed_rows": 109, "folds": summary["folds"], "new_measurements": 0, "stale_cache_rejected": update["stale_cache_rejected"],
         "heldout_RMSE_log10": errors, "biological_success_probability": None, "report": ref(ART / "RESULTS.md"),
         "poster": ref(ART / "observed-update.png"), "receipt": ref(native / "receipt.json"), "empirical_scope": summary["empirical_scope"],
         "prepared_bundle": ref(bundle) if bundle.is_file() else None,
         "bundle_status": "Prepared typed documentary bundle only; no DB import/submission/lifecycle/review",
         "publication": ref(ART / "publication.json"), "graph_narrative": ref(ART / "graph-summary.md")})
    dump(ART / "artifact-manifest.json", {"schema": "frontier.observed-allometry.artifacts/1", "files": [
        ref(path) for path in sorted(ART.rglob("*")) if path.is_file() and path.name != "artifact-manifest.json"
    ]})


if __name__ == "__main__":
    run()
