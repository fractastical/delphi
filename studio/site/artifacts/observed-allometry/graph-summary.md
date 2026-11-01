# Observed-data update, with worsening held-out error

Reused 109 author-reported preserved-specimen rows from Daane et al. (2021), Data S1A ([paper](https://doi.org/10.1016/j.cub.2021.08.054)), retaining 18 missing pelvic measurements and the original corrupt ratio cell. The 82 species/catalog-outcome folds use training-only residual variance and catalog jackknife. No new measurements were collected.

Adding 19 observed rows to 12 training rows changes the same 8.35 cm standard-length query from 5.56 to 5.46 cm predicted pectoral length. An actual exact-version cache lookup rejects the old result and recomputes its successor. On 18 held-out H. rondeleti rows, RMSE worsens from 0.0471 to 0.0661 log10 units. More data did not guarantee better transfer.

Only three flying-fish species are present; this is reused-dataset internal validation. Working prediction bands are not calibrated population confidence. Source observations, fitted predictions and computed uncertainty remain distinct. No causal, genetic, flight or organism-success claim is made.

Six typed documentary records are prepared (2 Claims, 1 Problem, 1 Action, 2 Evidence), separating observed-source from predicted-fit evidence. No database import, submission, lease, independent review or acceptance occurred. publication.json declares exact files/hashes for root to copy and verify; public serving is not claimed by this package.
