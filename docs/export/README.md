# Claims export

Flat, one-row-per-claim copy of the claim graph, built by `node scripts/site/build-export.mjs`
from [`docs/claims.json`](../claims.json). Do not edit by hand.

- [`claims.csv`](claims.csv): UTF-8, comma-separated, CRLF line ends, header row, quoted where needed.
- [`claims.json`](claims.json): the same rows as `{ built, count, claims: [...] }`.

1702 claims: 63 proved, 1 partially proved, 2 disproved,
128 tested against data, 1508 untested.

## Fields

| field | values | meaning |
|---|---|---|
| `id` | text | Stable claim id, e.g. `darwin1859-ch01-09`. |
| `title` | text | One-line summary of the claim. |
| `statement` | text | The claim, stated in full. |
| `author` | text | Whose claim it is. |
| `work` | text | Book or paper the claim comes from. |
| `year` | number | Year of that work (negative = BCE). |
| `chapter` | text | Chapter or section, where there is one. |
| `quote` | text | Passage in the source the claim was extracted from. |
| `claim_type` | text | Kind of claim, e.g. `empirical-generalization`, `mathematical-law`. |
| `is_mathematical` | true / false | A formal mathematical statement that a proof could settle. |
| `status` | `proved`, `partially_proved`, `disproved`, `tested`, `untested` | Summary, strongest first. **`untested` means no proof and no data test yet, not that the claim is false.** |
| `proof` | `lean`, `literature`, `partial`, `disproved`, `none` | How a mathematical claim was proved: checked in Lean 4, or proved in the published literature. |
| `data_test` | `supports`, `refutes`, `mixed`, `inconclusive`, `none` | Result of testing the claim against public data. `none` = not tested. |
| `data_test_kind` | `biological`, `physical`, `computational`, `none` | What the data measured. Only `biological` shows a claim holds in organisms; `computational` shows it holds as mathematics. |
| `data_test_url` | URL | Full record of the test (hypothesis, data, method, caveats). Empty if untested. |
| `published` | true / false | Whether the claim is published as a nanopublication. |
| `nanopub_url` | URL | The nanopublication, when published. |

## What is left out

Internal and model-generated fields: hash keys, AI assessor truth and testability scores, Lean
module details, MorphoLib links, registry and draft flags, and pre-registration contracts. They are
still in [`docs/claims.json`](../claims.json) and available over the `delphisci` MCP server.
