# Collective review evidence: five corrections, with receipts

Question: did review across harnesses change what we claim? This is a **retrospective process trace of five
corrections**, not a controlled multi-agent benchmark. It does not show that collective work beats a single
agent, uses no agent counts as evidence, and counts no scientific breakthroughs. Machine-readable ledger:
`results/coordination/review-corrections.json` (checked by `tests/test_review_corrections.py`).

Read level of every source: full text of the cited handoff, commit message or diff for the commits named;
none of the underlying science was re-run for this note. No web sources.

## Who reviewed whom
Every reviewer is an agent or session of one fleet, sharing one git identity. None is an independent lab.
Classes used: `author_self_correction`, `root_review`, `separate_harness_review`, `native_review`.

| # | Issue | Submitted | Reviewer class | Correction | Recheck | Decision changed |
|---|---|---|---|---|---|---|
| 1 | DOE misclassification used a centered margin | `11b5c30` | root_review | `4d9628f` | v3 run, `result.json` | Withdrew 0.50/0.13/0.10; benefit now small (0.043/0.028/0.023) |
| 2 | Compiler accepted string `"false"` and a non-digest | `3b2ca99` | separate_harness_review | `1a08432` | `b02b51a` reconciled receipt | Residuals blocked until fixed; claims kept to bookkeeping |
| 3 | Compiler cache served stale passes | before `f2f0c69` | native_review, root_review | `f2f0c69`, `68117a9`, `189c0e5` | 19 tests, `run --check` | Cache no longer trusted on manifest alone |
| 4 | Contributor ledger mislabelled 31 live processes | `1ff9f00` | root_review | `474fb8e` | JSON counts 4 then 11 | Headline moved 4 to an 11 floor; 31 not "active" |
| 5 | A DOE control could not fail | `ad18627` | author_self_correction | `895487f` | mutant changes 86 of 192 flags | Agreement with recorded flags became meaningful |

## Notes that matter
- **Example 2:** the reviewer's first pass was 17 of 19 scoped checks and the reconciled pass is 29 of 29.
  These are **different check sets** (the later set adds conditions), so no before/after percentage or
  improvement rate is claimed.
- **What each side contributed:** root read arithmetic and code (1, 4) and knew authorship the ledger could
  not derive (4); the separate harness built typed inputs the owner's tests lacked (2); native review
  supplied the stale-pin cases (3); the author's own declared gate caught (5). Entry 3's reproduction was the
  author's.
- **Entry 4 is a counting correction, not a capability.** The 11 rests partly on root's attestation.
- **Provenance gaps:** entry 1's earlier outputs were overwritten before commit; only a labelled
  regeneration exists (`artifacts/crossscale-doe/superseded/SUPERSEDED.json`). Entry 3's pre-fix bytes exist
  only in git history; no baseline was reconstructed. Entry 4's review text was a chat message to the author
  session; the durable trace is the handoff and the diff.
- **Counterfactual unknown:** for each entry it is unknown whether a single agent re-reading its own work
  could have found the same problem. Entry 5 shows one agent can; the rest do not show it either way.
- Commits for entries 2 and 3 live on the branches `work/sequence-compiler-review` and
  `codex/biodesign-compiler-20261031`; the commit hashes resolve in this repository.
