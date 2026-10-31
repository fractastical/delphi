# Claim extraction instructions: On the Origin of Species (1859, 1st ed.)

Source text: `books/darwin-origin/inputs/pg1228.txt` (Project Gutenberg eBook #1228, the 1859
first edition). Line numbers below refer to this file. The analytical table of contents
(Darwin's own section headings per chapter) is at lines 100–306.

Goal: list every **major claim** Darwin makes in your assigned chapters, so that a later
step can check which of them can be resolved with modern scientific datasets. Each claim
becomes one nanopublication, so each must be a single, self-contained proposition.

## What counts as a major claim

- A general statement about nature that Darwin asserts or argues for (a pattern, a
  mechanism, a historical inference, or a prediction), at the level of his section
  headings or of the conclusions he draws in a section or chapter summary.
- Include his theoretical claims (e.g. natural selection acts slowly) and his factual
  generalizations (e.g. wide-ranging species vary most), and the predictions his theory
  makes (e.g. intermediate forms should be rare in any one formation).
- Exclude single anecdotes and individual observations unless Darwin uses one as the
  basis of a general claim (then state the general claim). Exclude acknowledgements,
  rhetorical asides and claims he only reports in order to reject (but DO include his
  counter-claim).
- Aim for roughly 6–12 claims per chapter; more for long, dense chapters (IV, XIV), fewer
  for short ones. Do not pad. Do not duplicate within your range.

## Output

Write a JSON array to the output file named in your task, UTF-8, pretty-printed. Each
element:

```json
{
  "chapter": "IV",
  "section": "Divergence of Character",
  "label": "Divergence of character maximises the life an area supports",
  "claim": "The greatest amount of life can be supported in an area by great diversification of structure among its inhabitants.",
  "quote": "The truth of the principle, that the greatest amount of life can be supported by great diversification of structure, is seen under many natural circumstances.",
  "line": 3649,
  "claim_kind": "empirical-generalization",
  "scope": "local communities of plants and animals",
  "measurable_quantities": ["species or genus richness per unit area", "biomass or individual density per unit area"],
  "candidate_data": "Plot-level biodiversity-productivity experiments (e.g. Cedar Creek BigBio, Jena Experiment); sPlot vegetation plots",
  "resolvability_triage": "testable-with-existing-data"
}
```

Field rules:

- `chapter`: Roman numeral `I`–`XIV`, or `"Introduction"`.
- `section`: the matching heading from Darwin's table of contents for that chapter
  (copy its wording), or `"Summary"` if from a chapter summary.
- `label`: ≤ 90 characters, plain, no trailing period.
- `claim`: one proposition in clear modern English that is **faithful to what Darwin
  says**. Do not inject modern knowledge (no genes, DNA, Mendel, mutation) and do not
  correct him; a wrong claim is still recorded as he made it. Make it self-contained
  (no "this", "the above").
- `quote`: a **verbatim, contiguous** excerpt from the text that states or most directly
  supports the claim, ≤ 70 words. Copy exactly: original spelling (e.g. "favourable",
  "misseltoe"), curly quotes/apostrophes (’ “ ”), em-dashes (—), and underscores used for
  italics (`_naturally selected_`). Where the excerpt spans line breaks, join with a
  single space. Never stitch two non-adjacent passages, never paraphrase, never add
  ellipses. **Verify every quote** by searching the file (e.g. with `rg -F` on a
  distinctive fragment, then reading the lines) before you write it.
- `line`: the line number in `pg1228.txt` where the quote starts.
- `claim_kind`: one of
  - `empirical-generalization`: a pattern claimed to hold in nature now;
  - `mechanism`: a causal process (how change happens);
  - `historical-inference`: a claim about what happened in the past (descent, extinction, migration);
  - `prediction`: something that, on the theory, should (or should not) be observed;
  - `conceptual`: definitional, methodological or about classification practice, not itself empirical.
- `scope`: which organisms / settings the claim covers.
- `measurable_quantities`: what one would measure to test it (empty array if conceptual).
- `candidate_data`: one sentence naming the **kinds** of modern data that could bear on
  it, naming real, well-known resources where you are confident they exist (e.g. GBIF,
  Paleobiology Database, Open Tree of Life, TimeTree, GenBank/SRA, BioTIME, PREDICTS,
  Living Planet Index, AnAge, Dryad experimental-evolution datasets, LTEE). Never invent
  a dataset name, accession or DOI. Use "none known" if none.
- `resolvability_triage`: your first-pass guess, one of `testable-with-existing-data`,
  `testable-with-new-data`, `partly-testable`, `not-empirically-testable`. This is a
  builder's triage, not an assessment; someone else will assess it.

Before finishing, re-open your output file and check that it parses as JSON and that
every `quote` occurs in `pg1228.txt` (after collapsing whitespace) at or near `line`.
Report back: the output path, the number of claims per chapter, and any quotes you could
not verify.
