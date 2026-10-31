# Live import run, 2026-10-31 (UTC 19:05)

Imported into the live Frontier store (namespace `delphi-frontier`) by actor `corpus-importer` through `Store.import_bundle`, from frozen records:
the exact six-record NCA chain (1 bundle) and 878 production Delphi claims (9 bundles), all under their own namespace `node-a`, all
`imported_unreviewed`. Code: `frontier_adapters.import_cli` @ `d88a406`. The credential file was read inside the process and appears nowhere here.

* `import-receipt.json`: the machine-readable receipt (`receipt_sha256` inside). `site-chain-ids.json`: exact ids for the rendered chain.
* `plan-*.json`: bundle digests and idempotency keys; `receipt-import.jsonl`: one line per bundle written; `receipt-rerun.jsonl`: the identical re-run (changed no count).
* `verify-*.json`: every record read back by exact ref with no credential. `plan-biomodels-NOT-IMPORTED.json`: a 7-record plan built from another worker's file, preflighted
  read-only and **not executed**.
* The 6 MB of bundles are not committed; they are rebuilt deterministically by `import_cli build` from the frozen inputs (digests in the plans).
