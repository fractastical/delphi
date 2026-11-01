# Attestation check: a 15-item curation demonstration (not a verification of the register)

Status: single-reader, not independently reviewed. Written 2026-10-31 (Seattle). Files in this directory:
`select_attestation_sample.py` (rule, committed as `30b41e3` **before any fetch**), `attestation-sample-15.json` (the fixed sample),
`check_attestation_sample.py` (bounded fetch and quote match), `attestation-check-15.json` (mechanical result),
`attestation-facet-review-15.json` (my judgment of facet versus question, kept separate from the mechanical result).

## What this is and is not

It reads 15 of the register's 465 attestations (3.2%) against their cited sources, to show what curation checking finds.
The 15 were chosen by a sha256-keyed rule, not at random and not to be representative: 3 with stance `settled`, 1 Wolfram url
attestation, 11 with stance `open` and a pmcid, from distinct problems and sources (10 research, 3 review, 1 perspective,
1 challenge-list). **Nothing here verifies the other 450 attestations or the 250 problems.** No record was changed, nothing was
promoted, `completeness` is unchanged, and nothing was imported live.

## Check 1, mechanical: is the quote in the cited source?

Method (declared in the script before the run): Europe PMC full-text XML for each PMCID; r.jina.ai reader proxy only if a public
page answered 403; the Wolfram page directly. Quote match after one normalisation (Unicode NFKC, lower case, typographic quotes and
dashes folded, whitespace collapsed; a second pass keeping letters and digits only is reported as such). No fuzzy match counts.
Statuses: `verified` (quote present in retrieved full text), `quote_not_found`, `source_only` (identifier resolves, no full text),
`access_failure`.

Result: **15 of 15 `verified`: the quote text is present in the retrieved full text.** 14 PMC articles came from Europe PMC
full-text XML; the Wolfram page answered HTTP 200 directly. The Jina proxy was never needed and no 403 occurred. `source_only`: 0.
`access_failure`: 0. `quote_not_found`: 0. For the 14 PMC items the quote sits inside a section whose heading matches the register's
locator (after fixing a separator bug in my first comparison, see below); the Wolfram page has no section structure, and the last
heading segment of its locator is present in the page text, but the quote's position was not tied to it. The Wolfram quote matched
only after the letters-and-digits pass.

Caveats on check 1: the text compared is Europe PMC's copy of each article, not the publisher's version of record. A quote being
present does not show that it says what the register's stance claims; that is check 2. The first run had a locator comparison bug
(it joined headings with spaces while the register separates them with ` > `, so 3 correct locators were reported `False`); I fixed
the comparison and re-ran. Statuses were identical in both runs; the retrieved-byte digests differed between runs (the service's
XML is not byte-stable), so the digests in the result file are for the second run only.

## Check 2, judgment: does the quoted facet support the stance, and does it cover the question?

Single-reader. Judged from the quote, its section, the article title and year, and the curator's question; **the papers were not
read in full.** Tally over the 15 (`attestation-facet-review-15.json`):

| | yes / direct | partly / partial | no |
|---|---|---|---|
| quote supports the attestation's stance | 10 | 4 | 1 |
| facet covers the question as phrased | 7 direct | 8 partial | 0 |

Only **4 of 15** are a clean `yes` and `direct` with no flag. Flags (an item can carry several):
* `stance_overstated` ×3. Actual mismatches:
  * **teleost-genome-duplication-diversification-causality** (stance `open`): the quote says the dating results remain compatible
    with a prolonged rediploidization process and that this "remains a viable mechanism". It states compatibility, not that the
    causal question is unresolved. The quote does **not** support `open`.
  * **zebrafish-nodal-signal-to-fate** and **heart-regeneration-loss-polyploidy-thyroid** (stance `settled`): each quote is one
    study's own conclusion (the Nodal article's title states its finding), recorded as a settled facet. Whether the field treats
    either as settled is not in the quote.
* `question_core_partly_answered_by_cited_source` ×2 (the same two): a source the register cites for the question appears to claim
  an answer to its core, so the question is not plainly open as phrased.
* `scope_narrower_than_question` ×4 (fin ageing: the age facet only; mural cells: the vein half only; deep cells: the first
  half only; neuromast: the self-renewal facet only), `generic_openness` ×1 (somite network: "not completely resolved" without the
  named network), `dated` ×3 (openness as of 2012, 2015, and a 2017 article quoting a 2010 reference; later work not checked),
  `not_biology` ×1 (the Wolfram rule 30 prize problem).

The three `settled` items: one supported (fin ageing, for the age facet in two species), two only partly. No `settled` attestation
was used as a source of openness by the importer, which is the behaviour this check supports.

## What follows, and what does not

* The register's quotes are, in this sample, genuine passages of the cited sources: no fabricated quote found in 15.
* The stance label and the fit to the question are weaker than the quote's presence: 11 of 15 carry a caveat, and one `open`
  stance is not supported by its quote. This is a demonstration that item-level review changes what a record can claim, not an error
  rate for the register (n=15, not random, one reader).
* Nothing is promoted: `curated_question` and `recorded` stay as imported. A reviewer should look at the three overstated items
  and at the `not_biology` item first.
