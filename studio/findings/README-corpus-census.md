# Three corpora, three zeros, three different missing fields

A read-only census of the two corpora we proposed to seed from, plus the one already imported.
**Strictly importable with zero importer-authored fields: 0 of 880 Delphi claims, 0 of 830 SciDEX
claims, 0 of 250 register problems.** Single-reader, not Codex-reviewed.

| corpus | n | blocks import | provenance |
|---|---|---|---|
| Delphi | 880 | `access` absent on all | **859 carry a verbatim quote + source URL + locator + sha256** |
| SciDEX | 830 | `context` absent as a field | 795 cite a DOI/PMID; **no content hash anywhere** |
| morphoswarm register | 250 | the four actionability fields | 34 quote+locator, 68 topic-only, **148 no source** |

The three zeros are not the same zero, and that is the finding. Each corpus is missing a
*different* field, so none of them is simply "low quality" — they were each built to answer a
different question, and a store that demands all of it at the door admits none of them.

## Delphi's provenance is the best of the three, and it was re-verified not assumed

859 of 880 literature claims carry a verbatim quote, a source URL, a locator (line range or page)
and a sha256. Re-checked against **live** Gutenberg text with matching hashes: Darwin **247/247**,
Thompson **291/291** (45 of those only after stripping source footnote markers), Wolfram 10/10
sampled.

The 21 math claims are the weak set: a citation and, for 18, a resolving DOI, but **no locator, no
quote, no hash** — and 3 of their source IRIs are Delphi-internal and **404**. Missing across all
880: `access`, `assumptions`, `limitations`, `source_version`.

## A live licence conflict, in the corpus we were about to import

**The Wolfram quotes are © all rights reserved, while the nanopub carrying them is CC-BY.**
That is 321 claims whose wrapper states a licence the quoted content does not have.

This is exactly the hazard the export gate was built for, arriving from the direction nobody was
watching. The gate refuses held content under an *unstated* licence; it cannot detect a *stated*
licence that the underlying content does not actually carry. An independent reviewer named this
case in the abstract hours earlier — "presence is not permission", `license` is free text with no
enum — and here it is concretely, in the first corpus we would have imported.

## 64 agent-authored passages are not in the text they cite

SciDEX's 830 claims are **all agent-authored**. Of the 795 citing a paper, the stored passage was
confirmed verbatim in the stored text for **518**; **64 were NOT found despite the full text being
available**; 163 were uncheckable. Locators are section-name only for 658, and there is no content
hash anywhere.

Set against Delphi's 548-for-548 hash-matched re-verification, that is a measured difference in
provenance fidelity between pipeline extraction from a fixed public-domain text and agent
authorship over the live literature. **64 of 795 is the number to quote, not a rate for "AI
claims" in general** — it is one corpus, one pipeline, and the 163 uncheckable are uncheckable
rather than wrong.

## Privacy hold, binding

The SciDEX repository is **private with unpublished data**: 819 claims team-visible, 11 private.
Nothing from it enters anything public without the owners' consent. This is not a technical
limit to work around.

## The bonus, and it reframes the actionability gap

**SciDEX questions are much closer to our `Problem` than the register is.** All 20 carry
`answer_criteria`; 16 of 20 reach criteria + falsifier + experiment cost through links. What they
lack is a `next_action` and any stop bound, so **0 of 20 are actionable as written** — but they
fail on two fields rather than four, and the two they have are the hard ones. If a curated
question set anywhere is worth adapting the schema toward, it is this one.
