# Register import: provenance fields, attestations and what they do not show

Status: single-reader, not independently reviewed. Script `scripts/import_register.py`; tests `tests/test_register_import.py`.
Nothing was fetched: no quote, locator or identifier was checked against a source.

## What changed and why

The importer used to read only `why_source` and `references` and ignored `attestations`. It therefore reported
**34 / 68 / 148** problems by provenance path (a locator and quote / topic-level reference only / "no source at all").
That 148 was a property of the field the importer read, not of the register: every one of the 250 problems carries
`attestations`. The importer now reads all three fields, keeps them separate, and copies every item verbatim.

The previous split is still reproduced (`previous_mapping` in the report: 34 / 68 / 148 on register sha256
`a0155552…`) so the correction can be audited.

## Counts (register sha256 `a0155552a2bcda40688d38e95c4069828922d21042c87c9c6cf96311de94f7d7`, 250 problems)

Source references, attestations and `why_source` are different things and are counted separately.

| field | problems | entries | note |
|---|---|---|---|
| `why_source` | 34 | 34 | pmcid, locator and quote on all 34; 33 of the 34 quotes also appear among the attestations |
| `references` | 74 | 108 | all 108 resolvable (102 pmcid, 6 doi); 0 carry a locator or a quote; 100 distinct sources |
| `attestations` | 250 | 465 | 416 stance `open`, 49 `settled`; 462 pmcid, 3 url-only; all 465 carry a locator and a quote |

Attestation detail: 331 distinct PMCIDs plus 1 distinct URL (332 distinct sources); 137 problems rest on exactly one
distinct source; one source underlies up to 5 problems, so a count of sources is not a count of independent evidence;
37 problems carry at least one `settled` attestation (none has all settled, and all 250 have at least one `open`); by kind:
research 312, review 132, perspective 12, challenge-list 7, preprint 1, survey-future-work 1.
The 3 url-only attestations are the same Wolfram blog page, on the three rule 30 problems; they are not biology literature.
(A probe by the market worker counted "247 of 250 with pmcid, locator and quote": those are the 247 problems whose
attestation carries a pmcid; the other 3 are these url entries.)

Which field fed the single `Problem.source` of each draft (a mapping choice, not a count of what the register cites):
`why_source` 34, first open attestation 216, `references` 0, no resolvable source 0. So "148 unsourced" becomes
**0 problems with no citation in the register**, and 216 + 34 = 250 drafts now point at a locator-bearing citation.
This does not make any of them better supported; see the limits.

## What each draft keeps

* `original.register_provenance`: `why_source`, `references` and `attestations`, every item verbatim and in register order.
  An attestation item adds only `index`, a derived `uri` (from its own pmcid or url) and
  `quote_checked_against_source: false`. This block is kept even when the whole-record copy `original.register_record` is dropped for
  size. If the record is still too large, each quote is replaced by `quote: null`, `quote_omitted_for_size: true` and its sha256; a
  quote is **never truncated**, because a shortened quote is a different passage.
* `source`: the `why_source` citation if present; otherwise the **first attestation with stance `open`** that has a resolvable id,
  a locator and a quote; otherwise the weaker `references` entry; otherwise nothing. A `settled` attestation never stands as
  the source of a question's openness. The `access` text states that the quote is the curator's transcription, that nothing was
  retrieved, and what the citation does and does not support.
* `novelty_status`: adds the per-problem attestation counts (total, open, settled, distinct sources).

## What this does not do

* **No promotion.** All 250 stay `completeness="recorded"`; the four actionability fields are still empty. `actionable` stays 0.
* **Not a primary-literature open problem.** The questions are a curator's. A cited source calling a facet open is evidence
  about that facet, not that the question as phrased is an open problem in the field. `problem_kind` is therefore
  `project_gap` for all 250, not `sourced_field_open_problem` (SPEC-001 open question 3). The enum has no value that says
  "curator's question"; a distinct value would be a `models.py` change, which this work did not make.
* **Quotes are unverified.** They are the curator's transcriptions. Whether a quote is in the paper, at the locator, and
  supports the question is unchecked. A reviewer should sample them before any claim rests on them.
* **Stance is the curator's.** `settled` marks a facet some cited source treats as settled; what that does to the question's
  scope is unreviewed and unstated here.
* Counts of sources are not counts of independent evidence.

## Reproduce

```
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
  python3 -I scripts/import_register.py /home/ubuntu/git/morphoswarm/data/problems/register.yaml --out drafts.jsonl
bash scripts/test_postgres.sh tests/test_register_import.py     # 12 tests; six mutations of the importer each fail one
```
