# run_bundles_betse: frozen bundle for the BETSE generic tissue patch

One `frontier-bundle-0.1` (8 records: 2 Claim, 3 Action, 3 Evidence) built from immutable git blobs at root tip
`b53e0cd5399f6d7a6657b86f33052cb1ffda00b5` (which contains BETSE commit `4daceb5`):
`python3 -m frontier_adapters.run_bundles --repo . --source-commit b53e0cd5399f6d7a6657b86f33052cb1ffda00b5 --only betse --out <dir>`.
All records are PROPOSED and arrive `imported_unreviewed`. Nothing was written to any store; root handles production imports.

- Five scenarios (baseline, k_up, gj_block, k_up_gj_block, baseline_dt), seven checks, one video. Every stated config and
  trajectory hash was recomputed from the blob; a mismatch refuses the chain.
- Generic 2-D tissue with BETSE defaults. Fin applicability is UNKNOWN; nothing is calibrated to any fish. The Kcnj13 channel
  candidate is a source link only and set no parameter.
- Kept visible: the 310 K default, and simulated resting Vm of -23.5 mV against a leak-only GHK value of 0.70 mV that the
  producer did not decompose.
- The receipt carries no exit code, command or wall time, and states no hash for the video or poster; the Action titles say so
  and those two digests are adapter-computed.
- The repository's `tests/test_bioelectric_tissue.py` defines 7 tests; this adapter counted them and did not run them.
