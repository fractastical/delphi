# Frontier completion-gap audit — 2026-11-01

## Scope and evidence rules

The source baseline is `795f1405e9ebea4554d3c7e4d62b924742aab2ad`. I read
`GOAL.md`, `tasks/BUILD.md`, SPEC-005–009, SPEC-013–017, the cited implementation and
artifact files, and the prior goal/evidence audit. I separately reviewed the later
descendant `5b3d8ad4635b733c1e44850d2ccbea6b201a34d1` for its independent fixed-horizon
review and backup receipt. These are additive evidence after the baseline, not a claim
that those files were present in `795f140`.

At **2026-11-01 07:25:26 UTC (00:25:26 PDT)** I made read-only requests to the public
System, cache-only hybrid discovery and exact-version graph APIs. No store writes or
compute jobs were made. Status terms below apply to the named acceptance only; none
asserts biological validity.

## Requirement-to-evidence matrix

| Delivery item | Status | Direct evidence and limit |
|---|---|---|
| **Self-validation loop** (GOAL lines 69–72; SPEC-017) | **Partial; a valid failure outcome exists, but the joined loop is not implemented** | `engineering/biodesign_compiler/compile.py` keeps expression→growth, growth→stiffness and sequence→cell-program interfaces unresolved; `artifacts/biodesign-compiler/genotype-validation.json` has five explicit unknown interfaces. `engineering/experimental_design/planner.py` and `artifacts/experimental-design/result.json` implement a bounded prospective linear-Gaussian planner. Its status is `prospective_assumption_based`, `measurement_rows` is empty, and it has no parent observation/update iteration. The saved 240-run epithelial sweep is a real executed model assay; its frozen fixed-horizon **FAIL** is an informative, independently checked outcome, not a reason to reject the loop. The remaining gap is linkage: no one exact candidate version currently binds its checks, Evidence/outputs, changed-input invalidation and next pinned Action as one inspectable cycle. The independent review in `5b3d8ad` rehashed all 971 returned files, checked 240 models and 1,442,280 rows, and confirmed the fixed-horizon verdict; it also found no spatial frames and no biological calibration. These are strong scoped components, not the full SPEC-017 chain from candidate → independent checks → changed evidence → next pinned action. See [SPEC-017](../../specs/SPEC-017-self-validation.md), [planner result](../../artifacts/experimental-design/result.json), [genotype validation slices](../../artifacts/biodesign-compiler/genotype-validation.json), and `5b3d8ad:docs/audits/epithelial-sweep-review-2026-11-01.md`. |
| **Cross-scale interface uncertainty and assurance** (GOAL lines 112–115; SPEC-008/017) | **Partial; uncertainty is real and visible in artifacts, not resolved end-to-end** | `artifacts/coupled-mechanics/result.json` retains explicit refusal reasons for incompatible pressure/fin frames and unresolved thin members; a separate pressure transfer has numerical controls but does not establish feedback or whole-animal flight. `artifacts/assurance-experiments/summary.json` compares candidates under 64 shared *assumed-input* draws and leaves empirical accuracy unknown. The compiler's I1–I5 remain unknown. These are useful interface tests and explicit gaps; they do not produce evidence-backed transfer calibration or a composed biological validation slice. Leave this GOAL item open. |
| **Prospective experiment planning and observed-data update** (GOAL lines 123–124; SPEC-013/017) | **Planner subcriterion achieved; integrated adaptive pathway partial** | The cantilever planner reports covariance, identifiability and equal-assumed-cost comparisons, including the rank-1 deflection-only versus rank-2 mixed-measurement result. It records no synthetic measurement rows. A distinct observed-allometry update exists and its held-out error worsened after adding observations; that is a retained negative result, not a calibrated cross-scale update. The public/project path still needs to connect a specific proposed instrument/readout, accepted observation, updated version and downstream invalidation. `GOAL.md`'s `[ ]` for a checked prospective planner is stale as to the generic planner implementation, but valid for the larger contextual UI + observed-update loop. |
| **Vector discovery and assessment** (GOAL line 108; SPEC-007) | **Retrieval implemented; assessment evidence is narrow/stale** | Public `GET /api/discovery?q=fish&limit=2&mode=hybrid&cache_only=1` returned two results with `score_kind=rrf_k60_lexical_plus_vector`; index metadata reported **4,607 documents**, 768 dimensions, Gemini embedding model, and update time `2026-10-31T23:56:57-07:00`. Because `cache_only=1`, this proves cached vector/hybrid retrieval, not a new embedding call. The retained 28-query known-item assessment used one judge and a 2,410-document snapshot; it found hybrid tied vector for all 28 queries. It is not a current-index broad relevance evaluation and does not show fusion beats vector-only. Therefore the checklist phrase “actual vector discovery” is stale as a missing-feature claim; its evaluation requirement remains incomplete. |
| **Interactive graph and source views** (GOAL line 108; SPEC-007) | **Bounded graph exploration achieved; artifact inspection incomplete** | Public `GET /api/graph` on exact Project `delphi-frontier/Project/project-flying-fish-mission@1177c6099f296d831bc67bf96cca8e89bee7997d39393e6a8cfb58e33f4c8fd1`, depth 1, returned **80 nodes, 144 edges, 21 edges outside the requested view**, including 56 Artifact nodes and 17 Evidence nodes. The response explicitly says artifact bytes are not fetched/verified (`bytes_verified=false`). The graph UI supports exact pins, keyboard node navigation and bounded neighborhood rendering. Thus graph functionality exists; the remaining gap is breadth of route/interaction critique and linking declared artifacts to verified bytes, not absence of a graph. |
| **Private backups and fresh-host recovery** (GOAL lines 105–107) | **Current 795 source/static delta and database are covered off-host; the latest full-service replay remains incomplete** | Read the full recovery receipt in `5b3d8ad`, including nested `final_ui_delta`. Snapshot `20261101T0710` covers the 3,960-version/1,988-event database and source revision `d87e5d15094be6fe89704f8225b17d4719d07b3b`; snapshot `20261101T0720` adds the exact `795f1405e9ebea4554d3c7e4d62b924742aab2ad` UI/static delta (5 changed deployed files, 6,551 unchanged, no removals), 18-file/32,157,342-byte archive, and source bundle. Its ciphertext hash/download and `sb03` restore of all 18 files were checked; the incremental bundle verifies/fetches and exact 795 commit resolves. The 0720 record says to reuse the 0710 database because the UI change made no database import, so this is not a source/DB revision mismatch. Separately, an actual fresh-host web/MCP service drill passed on `sb03` using older source `8a1f0914ec86d7905f5d19a4d20ee70a8f5fd587` and the earlier 3,912-record dump `1cbe54fed0b5cfc55d473e017638f5616c823e7c2e998f3ee269e486359a3d62`. The latest 795 source plus 3,960-version database have file/source verification and isolated PG replay, but no new app/service rollout: the latest recovery receipt still says `full_restore_verified=false`. Later unreturned work needs another additive capture. |
| **24-hour resource queue** (GOAL line 104; `tasks/BUILD.md`, queue artifact) | **Planning artifact exists; public System surface is stale** | Baseline `results/infra/queue.json` is `frontier.compute-queue/1`, observed `2026-11-01T06:43:08Z`, with a 24-hour horizon, 26 task/provider records, 32 preparation entries, owners, budgets, stop gates and explicit unknown spend. Later infra checkpoint `10b5749` adds newer queue/resource snapshots; use each artifact's observation time rather than treating the plan as live telemetry. At audit time public `/api/system.resources` instead reported `jobs_reported=0` and no jobs, because its one compute receipt pin was stale. The queue is not a utilization meter, and the public System view does not consume it. The GOAL checkbox that says “leave a 24-hour resource queue” is stale as a missing artifact; operationally refreshed, timestamped status remains incomplete. |
| **Integrated release and public System integrity** (GOAL line 103) | **Public release responds; integrity and receipt freshness need clearer evidence** | Public `/api/system` identified the release directory marker `795f1405…` and `marker_matches_name=true`; `checkout_sha=null` is expected for an immutable git-archive release without `.git`, not a defect by itself. The endpoint did not complete its independent tree-content check (`contents.checked=false`, budget/read reason), so the marker alone does not prove current bytes. The public build report is an author/worker report: four focused reuse/navigation/build checks passed and gitleaks reported no findings; it is not the whole product acceptance. The receipt-pin correction below is local to this audit branch and is **not yet live**. |

## System receipt-pin correction

The public System snapshot at the timestamp above reported zero jobs because
`deploy/system/receipt-pins.json` pinned the old SHA
`f534829fe1d9f0ab5e0c69754ccb0000e6b35bb4ca2333a031a1392019402e8b`, while the current
`results/compute/receipts.json` SHA was
`f3e443825bbcda9ddbdce87904791cf8f437f0b976312957b982f71e3289f4e2`. The current receipt
contains 11 entries, including failed and cancelling jobs; its `price` explicitly says
unavailable, not zero.

Before refreshing the pin, I checked the contents rather than trusting the summary:

- All 11 referenced controller manifests exist and match their recorded SHA-256.
- All 47 returned-file digests match files in the current `results/compute` tree. The
  receipt retains pre-relocation `results/...` paths; validation located the relocated
  files by basename and required an exact digest match.
- The reported set is preserved as mixed outcomes: 9 provider `COMPLETED`, 1 `FAILED`,
  1 `CANCELLING`; controller exit statuses include successes, failures and one missing
  return code. These are job receipts, not a count of successful scientific conclusions.
- Spend remains unknown and utilization remains uncomputed.

The audit branch updates the pin to the verified current receipt and records the previous
pin and the reason it was withheld. A focused regression test checks that all 11 outcomes
are surfaced without inventing cost or utilization. This correction only changes the
public data source after its evidence matches; no job is marked successful by the pin.

## Two highest-impact next implementations for the demo

1. **Show one real self-validation cycle across a selected design.** Bind an exact assembly
   version to its existing candidate contract, show each virtual instrument/check with its
   positive, negative or blocked status and source/result pins, change one input to
   demonstrate downstream invalidation, then create the next authenticated *proposed*
   Action. Keep the epithelial fixed-horizon FAIL and unknown genotype interfaces visible.
   This joins existing components without presenting simulated success as biological
   evidence.
2. **Make System's operational view consume one timestamped queue/receipt projection.**
   Show the 24-hour queue horizon and owners separately from provider states, include
   failed/cancelling jobs and unknown spend, expose the exact backup cutoff/recovery level,
   and identify when a release is a marker-only archive rather than an independently
   measured tree. This removes the current public “0 jobs” contradiction while preserving
   the distinction between planned capacity, provider state and measured utilization.

## Checks performed for this audit branch

- Read-only public API requests listed above; the System resource report is nested under
  `/api/system.resources`.
- Hash-checked the 11 controller manifests and 47 returned-file contents against the
  current receipt before changing its pin.
- Under a bounded systemd scope, the focused command
  `env PYTHONPATH=. bash scripts/test_postgres.sh tests/test_system_status.py -k shipped_compute_pin`
  passed: **1 passed, 24 deselected**. The fixture-backed module run had **24 passed, 1 failed** before the title assertion was
  corrected: it expected `Delphi Studio`, while current `GOAL.md` is titled
  `MorphoSwarm Studio`. After aligning that stale assertion with the current document title,
  the complete focused module passed: **25 passed**. No acceptance criterion was relaxed.
