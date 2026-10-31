# Claim extraction instructions: On Growth and Form (1917, 1st ed.)

Source text: `books/thompson-growth-form/inputs/pg55264.txt` (Project Gutenberg eBook #55264,
D'Arcy Wentworth Thompson, *On Growth and Form*, Cambridge University Press, 1917). Line
numbers below refer to this file. The table of contents is at lines 166–209. The main text
runs from line 980 (Chapter I) to line 25437 (end of the Epilogue); the footnotes are
collected after that (lines 25438–28917) and the index follows.

Goal: list every **major claim** Thompson makes in your assigned range, so that a later
step can check which of them can be resolved with modern scientific datasets. Each claim
becomes one nanopublication, so each must be a single, self-contained proposition.

## What counts as a major claim

- A general statement about living things that Thompson asserts or argues for: a pattern,
  a physical or mathematical law that organic form or growth follows, a mechanism, a
  historical inference, or a prediction, at the level of the conclusions he draws in a
  passage or at the end of an argument.
- Include his central theses (e.g. that the forms of cells and tissues are largely
  determined by surface tension and other physical forces, not by heredity or adaptation)
  and his specific quantitative claims (e.g. how strength, surface or speed scale with
  linear size; that a shell grows as a logarithmic spiral; that related forms are related
  by a simple Cartesian transformation).
- Exclude worked examples, numerical tables and individual measurements unless Thompson
  uses them as the basis of a general claim (then state the general claim). Exclude
  claims that are purely about physics or mathematics with no biological content (e.g. a
  theorem about soap films stated for its own sake), acknowledgements, historical asides
  about other authors, and claims he only reports in order to reject (but DO include his
  counter-claim).
- Aim for roughly 6–14 claims per chapter; more for long, dense chapters (III, V, XI,
  XVI, XVII), fewer for short ones (VI, X, Epilogue). Do not pad. Do not duplicate within
  your range.
- Take quotes from the main text. Use a footnote only if the claim is stated nowhere in
  the main text; then give the footnote's own line number.

## Output

Write a JSON array to the output file named in your task, UTF-8, pretty-printed. Each
element:

```json
{
  "chapter": "II",
  "section": "Strength and weight scale differently with size",
  "label": "Strength grows as the square, weight as the cube, of linear size",
  "claim": "Because muscular strength is proportional to cross-sectional area and weight to volume, a larger animal of the same shape has less strength relative to its weight.",
  "quote": "<a verbatim excerpt you have located in pg55264.txt>",
  "line": 1234,
  "claim_kind": "mathematical-law",
  "scope": "terrestrial animals of similar shape and different size",
  "measurable_quantities": ["body mass", "muscle cross-sectional area", "maximum force or load carried"],
  "candidate_data": "Allometric datasets of muscle force and body mass across species; AnimalTraits",
  "resolvability_triage": "testable-with-existing-data"
}
```

The example's `line` and `quote` are placeholders; never copy them.

Field rules:

- `chapter`: Roman numeral `I`–`XVII`, or `"Epilogue"`.
- `section`: Thompson's chapters have no section headings, so give a short topic phrase
  (≤ 8 words) naming the part of the chapter the claim comes from, e.g. "Rate of growth
  and age", "Cell division and surface tension". Reuse the same phrase for claims from the
  same passage.
- `label`: ≤ 90 characters, plain, no trailing period.
- `claim`: one proposition in clear modern English that is **faithful to what Thompson
  says**. Do not inject later knowledge (no DNA, gene regulatory networks, Turing
  patterns, modern allometry exponents) and do not correct him; a wrong claim is still
  recorded as he made it. Where he states a mathematical relation, state it (e.g.
  "surface varies as the square and volume as the cube of length"). Make it
  self-contained (no "this", "the above").
- `quote`: a **verbatim, contiguous** excerpt from the text that states or most directly
  supports the claim, ≤ 70 words. Copy exactly: original spelling ("shew", "colour"),
  curly quotes/apostrophes (’ “ ”), em-dashes (—), Greek, accents, and underscores used
  for italics (`_e.g._`). Where the excerpt spans line breaks, join with a single space.
  **Leave out** the transcriber's page markers such as `{123}` and footnote markers such
  as `[45]`, and the space either side of a page marker collapses to one space. Never
  stitch two non-adjacent passages, never paraphrase, never add ellipses. Avoid excerpts
  that are mostly formula notation. **Verify every quote** by searching the file (e.g.
  with `rg -F` on a distinctive fragment, then reading the lines) before you write it.
- `line`: the line number in `pg55264.txt` where the quote starts.
- `claim_kind`: one of
  - `mathematical-law`: a biological form, pattern or growth process is claimed to follow
    a stated mathematical relation or physical principle (a scaling law, logarithmic
    spiral, minimal surface, Cartesian transformation, mechanical optimum);
  - `empirical-generalization`: a pattern claimed to hold in nature, not stated as a law;
  - `mechanism`: a causal process (how a form comes about);
  - `historical-inference`: a claim about what happened in the past (descent, evolution);
  - `prediction`: something that, on his account, should (or should not) be observed;
  - `conceptual`: definitional, methodological or philosophical, not itself empirical
    (e.g. that biology must become mathematical to be a science).
- `scope`: which organisms / structures / settings the claim covers.
- `measurable_quantities`: what one would measure to test it (empty array if conceptual).
- `candidate_data`: one sentence naming the **kinds** of modern data that could bear on
  it, naming real, well-known resources where you are confident they exist (e.g.
  MorphoSource, Phenoscape, AnimalTraits, AnAge, PanTHERIA, TRY plant traits, GBIF, the
  Paleobiology Database, the Allen Cell Explorer, Image Data Resource, published growth
  curve datasets on Dryad). Never invent a dataset name, accession or DOI. Use "none
  known" if none.
- `resolvability_triage`: your first-pass guess, one of `testable-with-existing-data`,
  `testable-with-new-data`, `partly-testable`, `not-empirically-testable`. This is a
  builder's triage, not an assessment; someone else will assess it.

Before finishing, re-open your output file and check that it parses as JSON and that
every `quote` occurs in `pg55264.txt` (after removing `{n}` and `[n]` markers and collapsing
whitespace) at or near `line`. Report back: the output path, the number of claims per
chapter, and any quotes you could not verify.
