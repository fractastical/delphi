# Claim extraction instructions: Michael Levin's papers

Source texts: `claim-sources/levin-papers/inputs/<key>.txt`, one file per paper, listed with authors,
journal, year, DOI and PMCID in `claim-sources/levin-papers/inputs/sources.json`. Each is the Europe PMC
open-access full text (all CC BY) converted to plain text: one paragraph per line, `## ` and
`### ` lines are the paper's own section headings, and figures, tables, references and back matter
are omitted. Formulas without a text form appear as `[formula]`. Line numbers below refer to
these files.

Goal: list every **major claim** made in your assigned papers, so that a later step can check
which of them can be resolved with modern scientific datasets. Each claim becomes one
nanopublication, so each must be a single, self-contained proposition.

## What counts as a major claim

- A statement about living (or engineered living) systems that the authors assert or argue for:
  a pattern, a principle, a mechanism, an evolutionary inference, a prediction, or a result of
  their own experiments or simulations, at the level of the conclusions drawn in a passage or
  at the end of an argument.
- Include Levin's central theses (e.g. that bioelectric networks store and process
  pattern-level information that guides morphogenesis; that cells and tissues are competent
  agents pursuing anatomical goals; that the boundary of a "self" is set by the scale of the
  goals a system can pursue; that cognition lies on a continuum reaching below neurons) **and**
  the concrete findings of the empirical and computational papers (e.g. that a given
  depolarization suppresses tumour formation, that a given gap-junction blocker produces heads
  of other species, that simulated competent cells speed or slow evolutionary search). For an
  experimental paper, the findings and the interpretation the authors draw from them are both
  claims; record them separately when they differ.
- Exclude methods, protocols and individual measurements unless the authors use them as the
  basis of a general claim (then state the claim). Exclude acknowledgements, background
  statements the authors attribute to others without endorsing, literature summaries, and
  claims they report only in order to reject (but DO include their counter-claim). Exclude
  claims about pure mathematics, physics, computing or AI with no biological content, unless
  the paper uses them as an argument about living systems (then state that argument).
- Aim for roughly one claim per 600–900 words of main text: about 6–10 for a short paper,
  15–30 for a long one. Do not pad. Do not duplicate within your papers; where a paper repeats
  a thesis, take the clearest statement once.
- Take quotes from the abstract or main text. The abstract is fine when it is the clearest
  statement of a finding.

## Output

Write a JSON array to the output file named in your task, UTF-8, pretty-printed. Each
element:

```json
{
  "paper": "2014-tumor",
  "label": "Depolarizing surrounding cells is sufficient to raise tumour incidence",
  "claim": "In Xenopus embryos, depolarizing the membrane potential of cells near oncogene-expressing cells increases the fraction of embryos that form tumour-like structures.",
  "quote": "<a verbatim excerpt you have located in inputs/2014-tumor.txt>",
  "line": 42,
  "claim_kind": "experimental-result",
  "scope": "Xenopus laevis embryos expressing human oncogenes",
  "measurable_quantities": ["resting membrane potential of host cells", "tumour incidence per embryo"],
  "candidate_data": "Published Xenopus electrophysiology and tumour-incidence counts in the paper's supplementary data; Xenbase expression data.",
  "resolvability_triage": "testable-with-new-data"
}
```

The example's `label`, `claim`, `line` and `quote` are placeholders; never copy them.

Field rules:

- `paper`: the paper's key (the input file name without `.txt`).
- `label`: ≤ 90 characters, plain, no trailing period.
- `claim`: one proposition in clear modern English that is **faithful to what the authors say**,
  including its hedges ("may", "suggests", "in this model") and its stated scope (organism,
  model, conditions). Do not correct, strengthen or weaken it, and do not import later
  literature or your own view of whether it is true; a contested claim is recorded as made.
  Where Levin uses terms such as "goal", "memory", "intelligence", "agent" or "self" in a
  technical sense, keep his term and, if the paper defines it, state the claim so that the
  definition is clear. Make it self-contained (no "this", "the above", "our model" without
  saying which model).
- `quote`: a **verbatim, contiguous** excerpt from the paper's text file that states or most
  directly supports the claim, ≤ 70 words, all from one line (one paragraph). Copy exactly,
  including curly quotes, dashes, citation brackets such as `[12]` or `(Levin, 2019)`, and
  accents. Never stitch two non-adjacent passages, never paraphrase, never add ellipses. Avoid
  excerpts containing `[formula]`. **Verify every quote** by searching the file (e.g. with
  `rg -F` on a distinctive fragment, then reading the line) before you write it.
- `line`: the line number in the paper's text file where the quote is.
- `claim_kind`: one of
  - `experimental-result`: a finding the paper reports from its own wet-lab experiments
    (what was done, to what, and what was observed);
  - `simulation-result`: a finding the paper reports from its own computational model or
    simulation (state the model it holds in);
  - `mathematical-law`: a living system is claimed to follow a stated mathematical relation or
    formal principle (e.g. free-energy minimization, a scaling relation);
  - `empirical-generalization`: a pattern claimed to hold in nature across systems, not a result
    of the paper's own experiments;
  - `mechanism`: a causal process (how a form, behaviour or outcome comes about);
  - `historical-inference`: a claim about evolutionary history;
  - `prediction`: something that, on the authors' account, should (or should not) be observed,
    including proposed experiments with an expected outcome;
  - `conceptual`: definitional, methodological or philosophical, not itself empirical
    (e.g. that cognition should be defined by competency in navigating a problem space).
- `scope`: which organisms, cells, models or settings the claim covers.
- `measurable_quantities`: what one would measure to test it (empty array if conceptual).
- `candidate_data`: one sentence naming the **kinds** of modern data that could bear on it,
  naming real, well-known resources where you are confident they exist (e.g. Xenbase,
  PlanMine, SmedGD, the Gene Expression Omnibus, BioModels, the Cell Image Library, the Image
  Data Resource, Dryad, Zenodo, the paper's own deposited data if the text names it). Never
  invent a dataset name, accession or DOI. Use "none known" if none.
- `resolvability_triage`: your first-pass guess, one of `testable-with-existing-data`,
  `testable-with-new-data`, `partly-testable`, `not-empirically-testable`. This is a builder's
  triage, not an assessment; someone else will assess it.

Before finishing, re-open your output file and check that it parses as JSON and that every
`quote` occurs verbatim on line `line` of the named paper's text file (after collapsing runs of
whitespace). Report back: the output path, the number of claims per paper, and any quotes you
could not verify.
