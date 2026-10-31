# Bulk run record (2026-10-31, 18:25Z to about 18:55Z)

`checkpoint.json` (state, counts, two waves), `receipts.jsonl`, `curation-report.json`. The 6 MB of drafts and snapshots are not committed.

**Known gap in `receipts.jsonl`.** It holds 74 receipts, all HTTP 200, none with `Retry-After`, for about 100 HTTP requests (17 + 83;
the 2 session-setup posts per wave are never logged). The remaining ~24 are the **catalog-phase** requests of the two waves
(overview, nine `delphi_graph` calls, one control): `delphi_bulk.run` took its receipt cursor after the catalog phase, so they
were not written. That is fixed (see `test_catalog_phase_requests_are_in_the_receipt_log`, which fails on the old code). The runs
did not stop or error, but **this record cannot show that those ~24 requests were free of rate limiting**: a 429 there would
have been waited out silently. The data they returned is covered by the controls in the report (catalog count equals the
overview's total; a nonexistent thinker matches 0).
