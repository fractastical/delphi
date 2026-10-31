# Claim extraction instructions: A New Kind of Science (Wolfram, 2002)

Source text: `wolfram-nks/inputs/cache/nks.txt`, the main text (pages 1–846, chapters 1–12)
of the online edition at https://www.wolframscience.com/nks/. Each printed page starts with
a marker line `=== pN ===` (N = printed page number). Within a page, `# ` and `## ` lines are
chapter and section headings, `[Caption] ` lines are figure captions, and every other line is
a paragraph. A paragraph that runs onto the next page continues after that page's marker.
The book's Notes section (pp. 849–1197) is not included and is out of scope.

The book is © 2002 Stephen Wolfram, LLC. Its copyright notice permits individual verbatim
quotations for scholarly purposes when the book is cited, which is how quotes are used here.
Do not copy the text anywhere other than your output file, and keep quotes short (below).

Goal: list every **major claim** Wolfram makes in your assigned pages, so that a later step
can check which of them can be resolved with currently available datasets (or computation).
Each claim becomes one nanopublication, so each must be a single, self-contained proposition.

## What counts as a major claim

- A general statement Wolfram asserts or argues for, at the level of his section headings
  or of the conclusions he draws in a section: about what simple programs do, about how a
  natural or social phenomenon arises, about physics, mathematics, perception, computation,
  or about science itself.
- Include his discoveries as he states them (e.g. that some very simple rules produce
  behavior that looks random), his models of nature (e.g. that a given growth pattern is
  produced by a simple program), his physics hypotheses, his general principles and the
  predictions he says follow from them.
- Exclude descriptions of one figure or one rule's picture unless Wolfram uses it as the
  basis of a general claim (then state the general claim). Exclude autobiography, praise,
  rhetorical asides, and positions he only reports in order to reject (but DO include his
  counter-claim).
- Aim for roughly 12–20 claims per chapter (proportionally for a part-chapter); more for
  dense theoretical ranges, fewer for survey-like ones. Do not pad. Do not duplicate within
  your range.

## Output

Write a JSON array to the output file named in your task, UTF-8, pretty-printed. The example
below shows the format only. **Do not reuse its label or claim wording**; if your range
contains this claim, write your own label and restatement from your own reading.

```json
{
  "label": "Nature need not follow only traditional mathematical rules",
  "claim": "There is no reason to expect that the rules followed by systems in nature are limited to those of traditional mathematics such as equations; more general rules of the kind embodied in simple programs may govern them.",
  "quote": "there is in fact no reason to think that systems like those we see in nature should follow only such traditional mathematical rules.",
  "page": 1,
  "claim_kind": "general-principle",
  "scope": "natural systems studied by the exact sciences",
  "measurable_quantities": [],
  "candidate_data": "none known",
  "resolvability_triage": "not-empirically-testable"
}
```

Field rules:

- `label`: ≤ 90 characters, plain, no trailing period.
- `claim`: one proposition in clear modern English that is **faithful to what Wolfram
  says**. Do not inject later developments (the 2004 publication of the Rule 110 proof, the
  2007 2,3 Turing machine prize, the 2020 Wolfram Physics Project, later critiques) and do not
  correct him; a claim later disputed is still recorded as he made it. Make it
  self-contained (no "this", "the above", "such systems" without saying which).
- `quote`: a **verbatim, contiguous** excerpt that states or most directly supports the
  claim, **at most 60 words**. Copy exactly, including em-dashes (—) and curly quotes if
  present. Never include the `=== pN ===` marker, a `# `/`## ` heading prefix or the
  `[Caption] ` prefix; if a quote crosses a page or paragraph break, join with a single
  space. Never stitch two non-adjacent passages, never paraphrase, never add ellipses.
  **Verify every quote** by searching the file (e.g. `rg -F` on a distinctive fragment, then
  reading the lines) before you write it.
- `page`: the printed page number on which the quote starts (from the preceding marker).
- `claim_kind`: one of
  - `computational-observation`: what simple programs (cellular automata, Turing machines,
    substitution systems, …) do, checkable in principle by running them;
  - `mathematical`: a statement that is in principle provable or refutable (e.g. that a
    particular rule is universal, that a problem is undecidable);
  - `model-of-nature`: that a natural, biological, technological or social phenomenon arises
    from, or is captured by, a simple program or mechanism;
  - `physical-hypothesis`: about the fundamental structure of the universe (space, time,
    particles, gravity, quantum phenomena);
  - `general-principle`: a broad thesis meant to apply across systems (e.g. computational
    irreducibility, the Principle of Computational Equivalence);
  - `prediction`: something that, on his account, should (or should not) be observed;
  - `conceptual`: definitional, methodological, historical, or about how science is done,
    not itself empirical.
- `scope`: which systems / phenomena the claim covers.
- `measurable_quantities`: what one would measure or compute to test it (empty array if
  conceptual).
- `candidate_data`: one sentence naming the **kinds** of existing data or computational
  resources that could bear on it, naming real, well-known resources where you are
  confident they exist (e.g. OEIS, NIST Digital Library of Mathematical Functions, PDG
  Review of Particle Physics, LIGO/GWOSC open data, Planck Legacy Archive, Johns Hopkins
  Turbulence Database, CRSP or other market tick data, published shell-pattern image
  collections). Never invent a dataset name, accession or DOI. Use "none known" if none.
- `resolvability_triage`: your first-pass guess, one of `testable-with-existing-data`,
  `testable-with-new-data`, `partly-testable`, `not-empirically-testable`. Treat claims
  settled by running programs or by proof as `testable-with-existing-data` only if the
  computation or proof is feasible today with public tools. This is a builder's triage, not
  an assessment; someone else will assess it.

Before finishing, re-open your output file and check that it parses as JSON and that every
`quote` occurs in `nks.txt` (after collapsing whitespace and ignoring page markers) on or
just after the stated `page`. Report back: the output path, the number of claims per
chapter, and any quotes you could not verify.
