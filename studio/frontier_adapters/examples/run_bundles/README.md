# run_bundles: frozen bundles for fish3d, scales, behavior and lifecycle

Four `frontier-bundle-0.1` files (31 records: 7 Claim, 11 Action, 13 Evidence), one per chain, built by
`python3 -m frontier_adapters.run_bundles --repo . --source-commit 10cde736c0d15971b97c35692b0de8ddeea2299b --out <dir>`
from immutable git blobs. Every hash the producers state was recomputed; a mismatch refuses the chain. All records are
PROPOSED and arrive `imported_unreviewed`. Nothing here was written to any store; root handles production imports.

- Compute and render are separate Actions; render Evidence is `context_only`. Actions are imported records of what each
  producer receipt reports, and each title says whether the receipt carries an exit code (fish3d and scales: no).
- Lifecycle is a source assessment plus one closed-form sizing check: no simulator Action, by design.
- Kept visible: the scale model's out-of-band `rise_10_90_h`, the synchronous control that does not reproduce the measured
  impairment, and the behavior run's `render.py` hash that differs between its simulation arms and its render.
- Not a calibration of any fish. Artifacts are `urn:sha256` / `referenced`; no URL, no licence, no secret-like text
  (`find_secretish` refuses the freeze).
