# Sequence/compiler and SPEC-017 independent review

Review status: scoped follow-up executed on reconciled compiler `1a084328`;
the two recorded residual cases now reject. This report concerns bookkeeping,
identity and validator rules, not measured biological function.

SPEC-017 was read at root `cd0290f`; this worktree is based on root `c7b6f9e`.
The actual ledger is `7d51169`, SHA256
`5ecebe0d8f123457cceb2630fa2597542f8885f3052023504e96db80d32d3b87`.
No compiler owner files, source records, scientific runs or acceptance criteria
were changed by this reviewer.

## Executed draft checks

A frozen-in-memory copy of the owner working-tree compiler, file SHA256
`ac385331f7e98faa13214beb8623e0fdb947562ce7e3d78b6471aa6e193abb88`, was
loaded by `artifacts/audits/sequence-compiler/check.py`. The actual ledger's four
natural FASTA references parsed. All 32 existing model-output JSON artifacts were
refused as sequence text. All 44 entries were consumed, but the nested source-native
LEN context became null normalized fields. These are integration refusals/context
loss, not false function predictions. Raw output is `draft-check.json` beside the
check script. Initial launch lacked PYTHONPATH and failed before the probes; the
corrected bounded launch executed them.

The same draft's `evaluate_validation` reported `all_required_pass=true` for:

- A purported plan and result both pinned to unrelated plaintext, with caller
  `status=pass` and boolean positive/negative counts. File identity was checked;
  plan/result meaning and counts were not bound to file contents.
- A plan whose entire check set consisted of nonendpoint `not_applicable` checks.
  No endpoint had executed.

The owner was sent exact findings and the reproducer through
`messages/sequence-compiler-independent-review.md` and authorized tmux messages.
The owner is fixing the source; draft outputs remain historical findings.

## Source findings requiring final recheck

1. Bind normalized nucleotide hash/length to the selected actual artifact record;
   preserve file digest separately. JSON outputs require an exact unique row
   selection. Preserve the source-native nested context alongside any explicit
   normalized map, with unknown fields left unknown. Preserve `direction`,
   `functional_validation`, source references and desired versus demonstrated
   readouts. Natural references are not experimental alleles.
2. Bind versioned plan/result content, candidate/check/endpoint identities,
   required checks, status/counts and execution/dependence metadata to pinned
   bytes. A source pin does not authenticate arbitrary caller metadata. Boolean,
   NaN, negative and noninteger case counts must not count as evaluated cases.
3. A calibrated DNA-to-expression transfer must depend on the exact candidate
   nucleotide/input identity, not only matching allele/construct context strings.
   Per-candidate forward checks currently check sequence integrity but the source
   measurement interface does not require the corresponding sequence dependency.
   Other interfaces require their own relevant upstream input/transfer pins.
   A changed DNA reference cannot inherit a transfer merely by reusing labels.

## Specification review

SPEC-017 explicitly distinguishes numerical/formal verification from biology,
forbids a model validating its optimized sequence, names evidence dependence,
requires meaningful negative cases and forbids empty collections passing. Those
are appropriate boundaries. Two operational requirements should be made explicit
when implementing its acceptance:

- A passing validation plan must include at least one actual required endpoint
  that executed. Nonendpoint `not_applicable` checks cannot collectively produce
  a pass or remove the endpoint by omitting its row. Required-check identifiers
  and result counts must be typed, unique and bound to frozen source records.
- A purportedly independent functional check needs a declared, inspected data and
  model dependency chain, not only a different agent/validator name or file hash.
  Optimization readouts, copied predictions and deterministic transforms of them
  remain dependent; a forward/inverse round trip remains model consistency.
  Record overlap, calibration/fitting usage, reused-source groups and missing
  independent observations. Do not make missing independence into a new model
  score.

These clarify enforcement of the existing specification, not permission to claim
functional DNA or a genome-to-organism model. The actual ledger still leaves LEN
GRCz11 sequence identity, context-matched candidate function and all biological
expression-to-material/flight transfer unknown or blocked. The LEN deletion
result specifically preserves the distinction between induced expression and
required fin regeneration.

## Earlier committed-source integration (preserved)

Executed the same bounded reviewer against compiler
`3b2ca996e6095e3e4b20ed0255c687f31007e403`, file SHA256
`44fae76024e13280c4ff4497479a51df6155678ca366d6d2e5b52a9897933ada`,
and the clean ledger below. The exact compiler source snapshot and raw returned
checks are retained in `fixed-check.compiler.py.txt` and `fixed-check.json`.
The snapshot digest was compared with the committed Git object.

Seventeen declared integration/refusal conditions now behave as expected:
all 36 sequences and 44 entries are consumed; source context and direction are
preserved; model-output function remains unknown; unrelated plaintext cannot
authenticate a validation result; properly bound boolean counts fail at the
count gate; properly bound all-NA records fail the missing-endpoint gate; valid
typed bookkeeping passes; natural DNA identity passes and a wrong declared digest
fails; I1 exact-candidate matching passes while a different candidate digest fails.
Two actual prior model outputs remain `proposals_only`, with zero endorsed
candidates; source-context gaps remain `invalid_document`, with all five
biological interfaces unknown. These checks do not establish functional DNA.

Two additional declared typed-boundary conditions **fail** in that committed
source (17/19 scoped checks, not a biological success fraction):

- `endpoint="false"` as a string is coerced truthy in a pinned plan and can
  satisfy the endpoint condition. Require strict boolean endpoint/executable
  types and unique, nonempty check IDs before evaluation.
- A downstream I3 input string `not-a-digest` is accepted with no reason by
  `_check_inputs`. It is nonempty but is not a verified digest/pin. Use a declared
  typed-value contract or a strict digest/reference policy; do not label arbitrary
  strings verified dependencies.

Both residuals were sent directly to root/owner02. No existing biological
calibration is established by the baseline, so neither finding changes any real
functional result. `final-receipt.json` pins the source, ledger, script and outputs;
focused Ruff passed. No full suite or provider inference was run.

## Current reconciled source and DOE follow-up

The bounded follow-up used exact pushed compiler
`1a084328ae49ae2c065465d1c400cb8df3d6f78f`, file SHA256
`14d47e69283e1561447f6b52c315e3c5df4ea75069f7d8dcfbb18189cbe454cb`,
the same clean ledger `e187efb`, and corrected DOE `4d9628f`.
`reconciled-check.json`, `reconciled-check.compiler.py.txt` and
`reconciled-receipt.json` retain the exact read-only check and source pins.
The old 17/19 receipt and outputs remain unchanged, tied to review `7d5d06b`.

All **29 declared scoped conditions** behave as expected. This count includes
the 19 original integration conditions, exact DOE input identity, eight explicitly
uncalibrated instrument bindings, deterministic regeneration of four compiler
artifacts, and tiny isolated source-binding controls. It is not a biological
success rate or a general validation claim.

Both residual cases reject at their intended gates: string endpoint flags are
malformed rather than truthy, and arbitrary downstream strings are refused as
non-digests. Actual ledger sequences, source contexts/directions, model-output
unknown function and proposal-versus-evidence status remain intact. No candidate
is endorsed and no biological interface becomes calibrated.

The actual protocol, instrument-contracts and manifest bytes exactly match their
`4d9628f` Git objects. The compiler reads eight current typed contracts, carrying
`computed_uncalibrated` or `proposed_uncalibrated` status. Raw protocol file pins
are distinct from the contract's canonical-JSON protocol digest. A changed raw
file without a new pin is refused; isolated whitespace plus a matching new raw
pin preserves the same canonical identity; a wrong canonical reference is
refused. These fixture edits never modify owner files or scientific results.

The changed compiler lines were read. No additional substantive bypass was found
within those changes and these bounded probes. No general fuzzing or full test
suite was attempted. Focused Ruff passed.

## Optional final Delphi video scope review

Viewed both final 60/120-second contact sheets and the 120-second cut's 100-second
full frame; read the actual edited storyboard and TTS narration source. Exact
six input file hashes and sampled findings are in `video-portal-qa.json`.
The sampled visuals retain illustrative/schematic warnings, end-loaded theorem
scope, intended compiler output versus current artifact checks, authenticated
proposals versus executed results, and retained model nonconvergence. No blocking
source-versus-result or biological overclaim was identified in those samples or
the read narration text. Functional replacements are framed for context-specific
testing, not guaranteed interchangeability or flight.

This was not continuous full-video playback or audio listening. The absence of
misleading frames elsewhere was not established. No video files were edited.

## Publication and molecular-queue checks

The clean ledger delivery is `e187efb`, rooted directly on root `4662d6b`, with
ledger SHA256
`b4d34d42cab74ea70900ceb12ae5d7614f4977d3408cc35392208d6aab4715b4`.
It replaces article full-text artifacts with URL/digest/locator/license-audit
receipts. No redistribution grant was found in those exact HTML caches. The
original cached bytes/history remain private and unchanged. The initial draft
integration above used the historical ledger; final integration must use the
clean one. Sequence/context content is unchanged.

Infra asked whether the reference differences justified a new molecular
inference. Executed `protein_reference_check.py` on the exact clean raw records:
fgf20a genome and transcript CDS both translate to NP_001032180.1, 208 identical
amino acids. kcnh2a's source-selected NP_001036187.2 is 1,253 amino acids; genome
CDS translation differs from RefSeq at five positions, consistent with the source
annotation. Exact inputs/differences are in `protein-reference-identity.json`.
These are reference-strain differences, not demonstrated causal fin alleles.
Neither comparison supplies an independent structural/conductance or fin-function
endpoint; no new inference job is justified from these differences alone.
