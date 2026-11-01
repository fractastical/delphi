# Actual observed-data update: a useful worsening result

Imported **109 author-reported specimen rows**, preserving raw source cells, identities and units. The frozen species/catalog validation ran **82 outcome-specific folds**. These are reused observations, not newly collected measurements or an independent external test.

The real update adds 19 Exocoetus volitans observations to 12 Cheilopogon furcatus training rows. At the same training-derived SL query **8.35 cm**, predicted pectoral length changes **5.56 → 5.46 cm**. The v1 cache was actually requested with the v2 model version, refused as stale, and recomputed; both results and the rejection event remain in run/update.json. This is a working model update, not a cosmetic lineage edge.

On the same 18 held-out Hirundichthys rondeleti rows, RMSE **worsens 0.0471 → 0.0661 log10 units**. More observed data did not guarantee better transfer. No model selection, threshold or uncertainty estimate was changed after this result.

The training context also broadens from one species to two: the common query is a descriptive pooled-group prediction, not a calibrated prediction for every flying fish. `context-transfer.json` explicitly marks held-out species absent from each saved training context. That is a postprocessing applicability flag, not a newly introduced pass/fail criterion.

| Blocking | Group | Outcome | Scored / declared | Missing | Blocked | RMSE log10 | Extrapolated | Inside working band / available |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| species | flying fish | pectoral_cm | 49/49 | 0 | 0 | 0.0599 | 2 | 45/49 |
| species | flying fish | pelvic_cm | 37/49 | 12 | 0 | 0.334 | 7 | 25/37 |
| species | flying halfbeak | pectoral_cm | 19/19 | 0 | 0 | 0.194 | 7 | 2/19 |
| species | flying halfbeak | pelvic_cm | 15/19 | 4 | 0 | 0.646 | 15 | 14/15 |
| species | halfbeak | pectoral_cm | 22/22 | 0 | 0 | 0.0549 | 7 | 20/22 |
| species | halfbeak | pelvic_cm | 20/22 | 2 | 0 | 0.0572 | 5 | 8/8 |
| species | needlefish | pectoral_cm | 19/19 | 0 | 0 | 0.0821 | 7 | 3/4 |
| species | needlefish | pelvic_cm | 19/19 | 0 | 0 | 0.0798 | 7 | 4/4 |
| catalog | flying fish | pectoral_cm | 49/49 | 0 | 0 | 0.0559 | 2 | 45/49 |
| catalog | flying fish | pelvic_cm | 37/49 | 12 | 0 | 0.292 | 4 | 26/37 |
| catalog | flying halfbeak | pectoral_cm | 19/19 | 0 | 0 | 0.118 | 2 | 19/19 |
| catalog | flying halfbeak | pelvic_cm | 15/19 | 4 | 0 | 0.201 | 3 | 14/15 |
| catalog | halfbeak | pectoral_cm | 22/22 | 0 | 0 | 0.0364 | 6 | 20/22 |
| catalog | halfbeak | pelvic_cm | 20/22 | 2 | 0 | 0.0523 | 5 | 17/20 |
| catalog | needlefish | pectoral_cm | 19/19 | 0 | 0 | 0.0586 | 5 | 18/19 |
| catalog | needlefish | pelvic_cm | 19/19 | 0 | 0 | 0.0488 | 5 | 19/19 |

Errors include extrapolated cases; missing outcomes are unscored, never zero-filled. Species and catalog validation reuse the same records and must not be pooled as independent evidence. Each species is completely excluded from its training fold; shared catalog-token components are also excluded. Comma-separated catalog labels are conservative dependence links, not verified independent animal IDs. Only three flying-fish species (18/19/12 rows) are available. Source specimen/measurement context, not biological success, defines applicability.

Training-only residual noise uses SSE/(n−2); parameter covariance uses delete-one catalog-component jackknife only when identifiable. The Gaussian ±1.96 prediction bands are **working conditional bands, not calibrated 95% confidence or future coverage claims**. Their observed internal inclusion counts are shown without treating cells/specimens as independent species replicates. Unidentifiable bands stay null; rank/insufficient-sample blocks and every band miss remain in run/validation.json.

Residual variance combines measurement error, model misspecification and specimen/taxon heterogeneity; these components are not separately identified by this fit.

All 18 missing pelvic values remain missing. The corrupt first source pelvic/SL ratio remains unchanged beside the source lengths and derived ratio; no silent replacement occurs. Existing data/fish-controls files, connector download/extraction code and the prospective experimental_design API are unchanged. No SL→mass conversion or Fish1990 raw data is invented.

Model form: log10(fin/(1 cm))=beta0+beta1 log10(SL/(1 cm)), the same allometry form as connectors/fish_controls/build.py:fit. This work adds blocked internal validation, train-only working uncertainty, stable observed/model versions and actual cache invalidation; it is not a new biological law. Full-data descriptive fits are stored separately and were never used to score held-out folds.

Source: Daane2021, DOI10.1016/j.cub.2021.08.054, Data S1A sheet A - fin measurement; exact stored CSV SHA is in import-contract.json. Original workbook is not re-fetched. Native assay wall time **0.115s**, under one CPU/thread,2GiB/no-swap/128tasks/1800s bounds. Environment {'python': '3.13.12', 'numpy': '2.4.4'}; dollars unknown, no provider/GPU job. Six focused controls passed before production: analytic power law, rank refusal, held-out-response mutation, blocked catalogs, source identity/missingness and stale-cache refusal. Receipt retains source/code/environment/protocol/output hashes.

The figure uses actual source measurements and fitted/predicted values with separate labels. It is a static analysis figure, not measured morphology rendered from the model. Artifact proposals, if prepared, are not DB integration, lease execution, independent review or acceptance. Regulatory/cell/material/flight bridges remain unknown.
