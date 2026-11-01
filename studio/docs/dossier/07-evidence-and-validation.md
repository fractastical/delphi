# Evidence, validation, and the corrections ledger

## What was actually measured

Three entries are published as **measured** (a receipt in the tree records a run, its hash
and its result), each with its own scope line:

| What | Result | Covers — and does not |
|---|---|---|
| Lean check of the constraint certificate (offline run) | all recorded checks passed | three encoded constraints and four mutants; **not biology** |
| Glide simulation numerical controls | all pass | analytic and step-halving controls of a point-mass model; **not a fish** |
| Attestation quote check, 15 items | 15 of 15 quotes found; **judgment 4 of 15 clean** | a hand-picked sample; **not a population rate** |

The attestation check is worth reading closely because it went against us. All 15 quotes
existed, but on judgement only 4 were clean: 3 were flagged `stance_overstated`, 4
`scope_narrower_than_question`, 2 had the question's core only partly answered by the
cited source, 3 were dated, 1 was not biology. On fit, 7 were direct and 8 partial.

**The lesson is stated on the site:** a quote can be present and still not state what the
stance claims, or answer only part of the question. A hash or a matched string establishes
neither. This is a finding about the weakness of citation-matching as evidence — produced
by our own tooling, about our own corpus.

## Claim reuse with a null result

One versioned claim (`eng-finmech-claim-ei-crit`, pinned by content hash) was used by two
distinct scoped actions with causal order checked, including a **below-threshold** case —
that is, a case where reuse produced a negative answer. Exact rationals are carried
through rather than floats. We publish the null result because a reuse demonstration that
only ever succeeds demonstrates nothing.

## The review-corrections ledger

Five corrections are recorded as a **retrospective process trace**, with a schema, a hash,
and an explicit statement of what it is not.

| id | What changed |
|---|---|
| `doe-centered-margin` | Retracted a claim that measurement halves a 0.50 misclassification rate; the stated benefit is now small, because the finalist is probably already inside the regime. Root read the code and the arithmetic; the author had only run it. |
| `sequence-compiler-typed-inputs` | A reader built adversarial typed inputs the author's tests had not, and compared snapshots to git objects; string-flag and arbitrary-string-digest behaviour was treated as blocking until fixed. |
| `compiler-cache-and-pins` | Reviewers supplied cases (pinned-byte change, repointed pin, missing file); cache reuse is no longer trusted on the manifest alone, and stale pins now produce typed **blocked** results instead of passes. |
| `contributor-count-labels` | A headline contributor number moved from **4 to an 11 floor**, and 31 stopped being described as active. |
| `doe-mutant-control` | An analytic screen's agreement with 192 recorded flags became meaningful **only after the control could fail**. Information used: only the author's own gate; no other agent was involved. |

### What the ledger explicitly does not claim

Quoted from the record itself:

- *"that collective work outperforms a single agent"*
- *"any agent-count based advantage"*
- *"any scientific breakthrough count"*
- *"a percentage improvement between differing check sets"*

And on independence: *"All reviewers are agents or sessions of one fleet sharing one git
identity; none is an independent lab."* Classes are labelled `author_self_correction`,
`root_review`, `separate_harness_review`, `native_review`. The counterfactual is stated
too: *"For every entry it is unknown whether one agent re-reading its own work could have
found the same issue; this ledger cannot answer that."*

Four of the five corrections did involve information one party had and another did not —
code read versus only run, adversarial inputs the author had not built, cases the
reviewers supplied, out-of-band knowledge of authorship. The fifth is explicitly a
self-correction. We think that is a real and interesting pattern. We do not think it is a
controlled experiment, and we do not present it as one.

## Interface and deployment checks

- **MCP:** 12 of 12 recorded checks passed, including rejection of anonymous writes, with
  zero scientific records written.
- **Browser critique:** an independent critique session audited desktop and mobile and
  produced five major findings; source-download and table fixes were integrated and a
  recheck was scheduled. A complete Playwright critique of **every** route remains an
  open goal item.
- **Deploy safety:** releases are immutable archives of one commit; deploys health-check
  three times and roll back automatically on failure.

## What was not tested

- **No wet-lab experiment.** Nothing shows that a genotype produces a fin shape.
- **No registered calibration** between any two biological scales.
- **No controlled multi-agent versus single-agent arm.**
- **SPEC-005's 11 acceptance items are all unchecked.**
- Total spend and total model usage: unknown.
- Which commit is deployed is listed in the repository's own unknowns as not derivable
  from files.
