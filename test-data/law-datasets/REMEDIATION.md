# Remediation: five rounds, five different processes

Every slice record goes through five rounds after scouting. Each round is a different process,
and each LLM round runs on a different provider from the scout and from the other LLM rounds
(`laws.json` `providers.rotation`; `validate.mjs --final` enforces it). Rounds run in order on the
whole slice; each appends one entry to the record's `remediation` array and moves anything it
removes to `dropped` with `dropped_reason` (nothing is deleted).

| Round | Process | Kind | What it does |
|---|---|---|---|
| 1 | `link-resolver` | script (`r1-resolve.mjs`) | Re-fetches every URL and DOI, compares DOI metadata title and year with the record, drops non-resolving or wrong-work identifiers, fixes dead links that have a DOI. |
| 2 | `blind-relevance-audit` | LLM, provider B | Works blind (sees the law, claims and variables, not the scout's summary). Opens each source, checks it holds the variables and taxa claimed, checks `reported.quote` is verbatim in the source, corrects `verdict`, `scope`, `n`, `relevance`; drops fabricated or irrelevant sources. |
| 3 | `taxon-and-age-resolver` | script (`r3-taxa.mjs`) | Resolves taxa in GBIF (and PBDB for fossils): ids, kingdom check, geologic age against PBDB range. Flags, never drops. |
| 4 | `gap-filler` | LLM, provider C | Reads `coverage.gaps`, the flags and the taxon/age spread, then adds sources for under-covered clades, intervals, methods and decades. Additions carry `added_in_round: 4` and are checked against the live source like any other. |
| 5 | `final-adjudicator` | LLM, provider D, then lint | Re-verifies round 4's additions and every flag, resolves flags (fix, keep with a note, or drop), deduplicates, rewrites `coverage` and `summary` to match the final record, runs `validate.mjs --final` and fixes what it reports. |

## Rules for LLM rounds (2, 4, 5)

- Same evidence rules as scouting (INSTRUCTIONS.md): only what you fetched, quotes verbatim, never
  invent a DOI, URL, number or author, describe don't test, no supports/refutes language.
- The model that built a record never audits it. You are told your model id; write it in your
  remediation entry. If your provider matches the scout's or an earlier LLM round's, stop and say so.
- Blind where stated: round 2 must not read earlier `remediation` entries or the scout's `summary`.
- Every change is logged in your entry's `actions` (`{source_id, action, reason}`), where `action`
  is one of `verified`, `corrected`, `dropped`, `added`, `flag-resolved`, `flag-kept`.
- Don't touch other slices, claim files, `docs/`, or the scripts.
- A dropped source is moved to `dropped` with `dropped_in_round` and `dropped_reason`.
- Run `node test-data/law-datasets/validate.mjs <law>/<kingdom>` before you finish.

## The remediation entry

```json
{ "round": 2, "process": "blind-relevance-audit", "kind": "cursor-subagent", "model": "gemini-4-argon-medium",
  "at": "2026-11-01T02:10:00Z",
  "summary": "Opened 34 sources: 29 verified, 3 corrected, 2 dropped.",
  "counts": { "checked": 34, "verified": 29, "corrected": 3, "dropped": 2, "added": 0 },
  "actions": [ { "source_id": "abc", "action": "dropped", "reason": "page is a different paper; the quote is not in it" } ] }
```

## Order of operations for one slice

```sh
node test-data/law-datasets/validate.mjs <law>/<kingdom>                  # after scouting
node test-data/law-datasets/r1-resolve.mjs <law>/<kingdom>                # round 1
#   round 2: subagent on provider B  (prompt: remediation/round2.md)
node test-data/law-datasets/r3-taxa.mjs <law>/<kingdom>                   # round 3
#   round 4: subagent on provider C  (prompt: remediation/round4.md)
#   round 5: subagent on provider D  (prompt: remediation/round5.md)
node test-data/law-datasets/validate.mjs --final <law>/<kingdom>
```

Two assessor-style rules from `BEST_PRACTICES.md` apply: nothing here is "expert-validated", and a
record that never reached round 5 is shown as unremediated in every view.
