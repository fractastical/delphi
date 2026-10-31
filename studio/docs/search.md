# Search: indexed lexical and exact discovery

Status: implemented on branch `work/frontier-search`; 14 tests in `tests/test_search.py` pass, with the 18 existing tests
(32 total) under `bash scripts/test_postgres.sh` in the bounded scope. Single-reader, not independently reviewed. Performance was not
measured; the store holds a few hundred records and no scaling claim is made.

## What it is, and what it is not

PostgreSQL full-text candidate retrieval (`simple` dictionary, GIN expression index over the store's own `search_text`) **plus** a
literal substring fallback, ranked by integer tiers, with structured filters, bounded keyset pagination, a `why_matched`
explanation, exact version pins, and explicit opposing/disputed references.

It is **not** semantic search and **not** a hybrid. There are no embeddings and none are claimed. Embeddings could later supply extra
*candidates*; they would not change the pins, the access rule or the labels. Ranking is lexical and says nothing about truth or
quality: **ranking never reads review status or curation labels**, so nothing is silently promoted.

No data is copied. `search_schema.sql` adds indexes only (a test asserts the table list is unchanged). `store.py`, `models.py`,
`http.py` and `__main__.py` are untouched; the module reuses `Store.connection()`, `Store._read_principal()` and the store's visibility
rule (`visibility='public' OR namespace in the principal's namespaces`).

## API

```python
from frontier.search import SearchIndex
index = SearchIndex(store)          # store: frontier.store.Store
index.initialize()                  # operator-only, idempotent; run after Store.initialize()
index.search(query: str = "", *, kinds: str | Sequence[str] | None = None, status: str | Sequence[str] | None = None,
             source: str | None = None, scope: str | None = None, context: str | None = None,
             include_history: bool = False, limit: int = 20, cursor: str = "", token: str | None = None) -> dict
```

Raises `FrontierError` for bad parameters (before any database access) and `Unauthorized` for an unknown token. Bounds: query at most
200 characters; `limit` 1..50; `source` 3..200 characters; `context` 1..200 characters; `kinds`/`status` from the store's own
vocabularies.

| parameter | meaning |
|---|---|
| `query` | Free text. Empty means every record within the filters. Also detected as an exact 64-hex **version**, exact **record id**, or exact **source URI**. |
| `kinds` | One kind or a list: `Problem`, `Claim`, `Evidence`, `Assessment`, `Action`, `Actor`, `ResourceOffer`, `Interest`, `Event`. |
| `status` | Node-local review status: `proposed`, `imported_unreviewed`, `accepted`, `disputed`, `rejected` (one or a list). |
| `source` | URI **prefix** matched against both the envelope `source_uri` and the payload's own `source.uri` (two different fields). |
| `scope` | `public`, `private`, or a namespace id. Narrows only; it never widens what the token may read. |
| `context` | Literal substring of `payload.context` (Claim and Evidence records). |
| `include_history` | Default false = current heads only. An exact version query always returns that pinned version, head or not. |
| `cursor` | The `next_cursor` of the previous page. It is tied to the query and filters; a different query is refused. |

### Result

```
{"results": [ {
    "ref": {namespace, kind, id, version},      # the exact immutable version; never a floating "latest"
    "is_head": bool, "title", "issuer", "source_uri", "visibility",
    "local_status": "...", "score": int,
    "why_matched": [str], "matched_fields": [str], "snippet": str|None, "snippet_withheld": str|None,
    "source": {uri, locator, source_version, content_available, license, content_sha256_declared, access} | None,
    "curation": {"source_fidelity": "no_source|reference_only|locator_present|not_applicable", "labels": [str], "promoted": false},
    "disputes": {"local_status", "disputing_reviews": [{assessment, decision}], "cited_evidence": [{evidence, cited_by_assessment, evidence_kind}],
                 "diverging_versions": [{version}], "truncated": bool},
    "evidence_references": [{evidence, evidence_kind, source_fidelity}] } ],
 "next_cursor": str|None, "search_kind": "...", "ordering": "...", "limit": int, "heads_only": bool}
```

## Ranking (integer tiers, deterministic)

Exact version 9000, exact record id 8000, exact source URI 7000, title equals the query 3000, title contains it 2000, whole-query
literal match in the record text 1500, plus a full-text rank bucket 0..999 (`ts_rank_cd`, scaled and floored). Ties break on version
ascending. Pagination is a keyset on `(score DESC, version ASC)`, so a record inserted between pages can neither duplicate nor
drop a record already listed (tested). The literal fallback is what finds equations and symbols that the tokenizer splits or drops
(for example `2n^2 < (L/π)^2 < 5n^2`, or `<` alone); non-ASCII text is stored unescaped, so Unicode literals match.

## Explicit opposing and disputed references

Only explicit relations, never inferred from text or from the absence of a dispute:

* **disputing_reviews**: recorded review receipts (`reviews` table) whose decision is `disputed` or `rejected`. An Assessment uploaded
  through `submit` without a receipt is **not** counted (tested).
* **cited_evidence**: the evidence those disputing reviews cite through their dimension evidence links. The direction belongs to the
  review; search does not decide it.
* **diverging_versions**: a different version of the same record id held as an import fork.
* **evidence_references**: Evidence records that target the result. Listed neutrally; for or against is not inferred.

Every referenced record obeys the same visibility rule as the result. Lists are capped at 10 per result with a `truncated` flag.

## Source-aware curation labels

Labels describe; they never rank, change a status or promote. Source support is kept as three classes, never merged into one
"sourced" flag: `no_source` (no URI and no locator), `reference_only` (a URI, no locator: a topic-level reference), `locator_present`
(a locator is recorded; **whether the source supports the text is not checked**). Separate labels cover content (held under a stated
licence, held with **no stated licence**, digest declared but bytes not held, no digest), review status (not independently reviewed;
imported and not reviewed here; accepted under this node's policy, not a scientific endorsement; disputed; rejected) and, for a
Problem, whether it is `recorded` (not actionable) or declares the four actionability fields (declared, not verified).
A record asserting held content with no licence never yields a snippet (the same rule the store enforces on `get`).

## Known limits

* `simple` dictionary: no stemming, no synonyms, no typo tolerance; `websearch_to_tsquery` syntax (quotes, `or`, leading `-`) is honoured.
* The literal fallback is a substring scan over the candidate filter, not index-assisted; fine at this size, unmeasured beyond it.
* `why_matched` and snippets are computed in Python from the record text; they explain, while PostgreSQL computes the ranking.
* A version-hash query also returns the `Event` records that cite that version, at lower rank.
* Review status is node-local. Nothing here federates across nodes.

## Wiring (for the integrator; not done here)

`/v1/read/search` and the `frontier_search` MCP tool still call `Store.search`. To switch, call
`SearchIndex(store).search(...)` with the same `token`, and call `SearchIndex(store).initialize()` where the store is initialised.

## Tests

`systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash scripts/test_postgres.sh tests/test_search.py`
Covered: access isolation (anonymous, namespace-less principal, owner; private evidence and exact-version pins), kind/context/equation
retrieval, exact identifiers and version pins, ranking order, stable pagination across inserts, opposing and disputed references
(including the forged-Assessment case), bounded reference lists, curation labels, indexes-only, read-only behaviour, and parameter bounds.
