# Deviations from PREREG.md

PREREG.md is unedited by the analyst. Deviations are logged here in the order they occurred.

1. **Path rewrite in PREREG.md by a repository-wide change (not by the analyst).** PREREG.md was registered
   at 2026-11-01T10:08:12Z (clock in `PREREG.sha256`) with SHA-256 `568be67d...a9c0`. While this run was in
   progress the repository was reorganised by someone else (folders moved under `engine/` and later moved back),
   and the one path string in PREREG.md line 3 was rewritten between ``engine/problems/problems.json`` and
   ``problems/problems.json``. The file now hashes to `5f052c71...ed5`. Reversing that single substitution
   reproduces the registered hash `568be67d...a9c0` exactly (checked), so the registered text is otherwise
   unchanged. The registered hash in `PREREG.sha256` is kept as the reference. The run directory is
   `problems/runs/metabolic-scaling-exponent/` as instructed (for a while it lived at
   `engine/problems/runs/...`).
