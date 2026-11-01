# Durable readback of the fin Claim reuse review

Public `GET /api/record` readback of the exact versions at `2026-11-01T00:11:02Z` (17:11 PDT on 2026-10-31), saved unmodified (`*.json`) with a
summary in `MANIFEST.json`. No credential was used for the readback, and a check against the reviewer credential file found its string in none of the saved files.

* Review writes: `POST /v1/reviews` as actor `fin-reuse-reviewer` / operator `independent-review-agent`. The submission printed, for each: HTTP 200,
  `local_status` `disputed`, policy `frontier-independent-review-0.1`, below assessment `ad2ed84a-cd8e-488c-9ac3-5e95c2c1bfde` (version `13828b39...`),
  above assessment `5f52fbb4-c367-4cb4-8015-cb1d4c111cf2` (version `4b5749d8...`). These response lines are as printed at submission, not re-fetched; the
  assessment records below are the stored form.
* Evidence local status (readback): both `disputed`, both still the head version.
* Assessment records: decision `disputed`; dimensions source_fidelity, target_fidelity, applicability, computational_replay_formal_check `passed`;
  statistical_adequacy `not_applicable`; independent_replication and empirical_relevance `insufficient`. An Assessment record's own `local_status` reads
  `proposed`; the decision lives in its payload and in the target Evidence's status.
* Actions: unchanged by the review, state `submitted` in the `action` field, local status `proposed`. I did not review the Actions.
* This is a snapshot: statuses can change later. The records are the source of truth, not this file.
