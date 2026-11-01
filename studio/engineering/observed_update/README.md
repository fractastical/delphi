# Observed allometry updates

This module complements the prospective experimental_design planner without changing its API, submitting an Action or collecting measurements. The existing connector owns source download/extraction; this module consumes its pinned CSV and preserves original cells and identities.

model.import_observations(raw, contract) validates source digest, columns, units, positive values, missingness and catalog identities. blocked_folds yields whole-species or linked-catalog components with purging. fit uses training rows only; predict returns conditional allometry and a working band when identifiable. Catalog labels do not prove independent animals. Inspect training species and SL range before transfer.

PredictionCache.get(query, required_version) refuses superseded fits. put actually recomputes the replacement and retains both versions. Versions hash observations, context, code, NumPy version and fit outputs. No calibrated biological-success probability is produced.

The committed protocol predates fitting. Under its declared CPU/memory/task bounds, run python -m engineering.observed_update.run into a fresh directory, then python -m engineering.observed_update.report.

The documentary adapter python -m engineering.observed_update.bundle --source-commit <results-commit> reads immutable blobs through frontier_adapters.engineering_manifest.Chain, validates typed records/license policy/exact links and builds an import-compatible bundle. It never writes a Store. Observed-source Evidence is distinct from predicted-fit Evidence. Prepared records do not prove that graph Claims were consumed before computation or that a Store lifecycle occurred.
