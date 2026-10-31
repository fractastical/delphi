# Hybrid lexical + vector discovery

Status: implemented on branch `work/frontier-discovery`; single-reader, not independently reviewed. Web wiring (`GET /api/discovery`) belongs to root.

## What it is

* **Real embeddings.** Each PUBLIC record version and each declared artifact (metadata only; bytes are never fetched) is embedded from a fixed, versioned text recipe (`frontier-discovery-text-v1`: kind, title and the kind's content fields, at most 6,000 characters; missing fields are skipped, nothing is invented). Provider and model: Google Generative Language API, `gemini-embedding-001`, 768 dimensions (the model's native output is 3,072; 768 is requested via `outputDimensionality`, and every vector is L2-normalised here), document task `RETRIEVAL_DOCUMENT`, query task `RETRIEVAL_QUERY`.
* **Storage.** PostgreSQL + pgvector (`vector(768)`, HNSW cosine index). `discovery_documents` pins every vector to the immutable record `version`, the artifact `sha256` and role, the sha256 of the exact embedded text, the recipe, provider, model, dimensions and task type, and keeps the embedded text (public only). `discovery_failures`, `discovery_runs` and `discovery_query_cache` record failures, runs and query vectors. Nothing existing is changed.
* **Privacy.** Private records and their artifacts are never selected, embedded or returned. No credential or database location appears in any output.
* **Hybrid ranking.** Reciprocal-rank fusion (k = 60) of two independent rankings: the existing lexical `SearchIndex` (exact id/version/source tiers, full-text, literal) and pgvector cosine. Relevance is retrieval similarity to the query, **not truth, quality or epistemic confidence**; review status is shown separately in `local_status`, and every response says so (`relevance_note`).
* **Honest fallback.** If the provider, the extension or the index is unavailable (or the query-embedding rate limit or timeout is hit) the response is the lexical ranking with `mode: "lexical"`, `requested_mode`, and `unavailable_reason`.
* **Bounded query embedding.** 8 s timeout, in-process LRU (256) plus a persisted cache keyed by normalised query, model and dimensions, at most 20 live provider calls per minute per process, and `cache_only=True` (autocomplete) never calls the provider.
* Event records are indexed with the rest (all public kinds) but left out of results unless `kind='Event'` is asked for, because they are operational log lines.

## Contract

```python
from frontier.discovery import Discovery, GeminiEmbedder
d = Discovery(store, GeminiEmbedder())          # or Discovery(store, None) for lexical-only
d.search(query, kind=None, limit=12, mode="hybrid", cache_only=False) -> {
  "query", "mode",                               # mode actually used: lexical | vector | hybrid
  "items": [{"type": "record"|"artifact", "ref": {"namespace","kind","id","version"}, "artifact_sha256"?: str,
             "title", "snippet", "kind", "local_status", "score", "score_kind", "why_matched": [str]}],
  "index": {"model","dimensions","documents","updated_at","provider","text_recipe"},
  "relevance_note": str, "unavailable_reason"?: str, "requested_mode"?: str }
```
`score_kind` is `rrf_k60_lexical_plus_vector`, `cosine_similarity` or `lexical_rank_reciprocal`. Module-level `discovery.search(store, query, ...)` is a thin wrapper. Raises `FrontierError` for a bad query (1..200 characters), kind, limit (1..50) or mode.

## Setup (root)

1. A PostgreSQL superuser creates the extension once in the Frontier database: `CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;` (pgvector 0.6.0 is installed on the host but is not a trusted extension, so the service role cannot create it; `initialize()` says exactly this if it is missing).
2. `FRONTIER_DSN=... python -m frontier.discovery index --namespace NS [--receipt receipt.json]` creates the tables and embeds what is missing. It is bounded (`--max-requests`, default 100 provider calls), resumable and idempotent: a re-run embeds only new or changed text. `status` and `search` subcommands exist.
3. The credential for embeddings is read in process from `GEMINI_API_KEY` or `~/.config/morphoswarm/gemini.env` (override: `FRONTIER_GEMINI_ENV_FILE`). The web process needs it only for live query embedding; without it, hybrid falls back to labelled lexical (cached queries still work).

## Live index (2026-10-31) and the refresh job

After root enabled pgvector in the dedicated Frontier database, `python -m frontier.discovery index --namespace delphi-frontier --max-requests 100` indexed the live node: **2,444 of 2,444 planned documents embedded, 0 failures, 49 provider requests** (Claim 914, Problem 262, Event 1,200, Evidence 9 plus 51 declared artifacts, Action 8; one model, `gemini-embedding-001`, 768 dimensions). Every indexed version is public (0 non-public; the node held no private record at the time). Receipt: `imports/2026-10-31-discovery-live-index-receipt.json`.

Recurring job: `python -m frontier.discovery refresh --namespace delphi-frontier [--max-requests 20] [--receipt log.jsonl]` embeds only records and artifacts that are new or changed (a run with nothing new makes **zero** provider calls), under a small request budget, with a PostgreSQL advisory lock so overlapping runs skip. Exit code 0 on success or skip, 2 if any document failed, 3 if the provider or extension is unavailable. `deploy/discovery/` has a systemd user service and a 10-minute timer template (placeholders for paths and an environment file; no credential in the repository). Indexing sends up to `--workers` (default 4) provider requests at once.

Latency, measured on the live node (single process, uncached query unless noted): a hybrid search took about 950 ms before and about 270 ms after two changes: the lexical candidate query now uses three index-friendly branches instead of one OR that forced a sequential scan with per-row `to_tsvector` (lexical alone: about 630 ms to about 40 ms; the existing 17 search tests still pass), and the lexical and embedding paths now run concurrently. A repeated query is served from the cache in about 60 ms. The provider call itself is about 200 ms.

## Measured earlier: indexing receipt on a private copy

A private temporary PostgreSQL cluster was loaded with a copy of the live node's 2,375 public head records and indexed (the source node was only read): **2,410 of 2,410 planned documents embedded, 0 failures, 49 provider requests, 51 s**; 2 inputs were truncated at 6,000 characters. By kind: Claim 912, Problem 261, Event 1,191, Evidence 6 plus 35 declared artifacts, Action 5. Manifest sha256 and full coverage: `findings/discovery-index-receipt.json`. The live node itself has not been indexed (it lacks the extension).

## Measured: relevance on frozen judged pairs (`findings/discovery-assessment.json`)

28 query/target pairs were frozen (commit `09fee92`, sha256 `9d272254…`) before any retrieval output existed: targets are a mechanical sample of live public Claims and Problems; queries were written after reading only the target's title and first 330 characters; 14 are paraphrases that avoid the target's distinctive words and 14 are short keyword queries. One relevant record per query, one judge. Nothing was tuned: RRF k = 60 as shipped.

| mode | at rank 1 | in top 5 | in top 10 | found in top 50 | MRR |
|---|---|---|---|---|---|
| lexical (existing search) | 10 of 28 | 10 | 10 | 10 | 0.357 |
| vector | 25 of 28 | 27 | 28 | 28 | 0.935 |
| hybrid (RRF) | 25 of 28 | 27 | 28 | 28 | 0.935 |

By style: lexical found 0 of 14 paraphrase queries (by construction they avoid the target's words) and 10 of 14 keyword queries (it requires every query term to occur, with no stemming, so 4 keyword queries missed); vector and hybrid found 14 of 14 keyword and 14 of 14 paraphrase queries within the top 10 (11 of 14 paraphrases at rank 1). Per query, hybrid ranked the target better than lexical in 18, never worse, and identically in 10; hybrid and vector ranked every target identically.

**What this does and does not show.** On these pairs, adding vectors found the intended record where the existing lexical search could not, for meaning-level queries. It does **not** show hybrid beating vector alone (they tie on every pair), and it does not test exact-identifier or version-pin queries, where the lexical side is what guarantees the exact record (covered by a test, not by this assessment). It is 28 known-item pairs, one judge, one relevant record each (other records may also be relevant, so every number is a lower bound), on a corpus of about 1,200 non-event documents; it is not a general accuracy figure and has no confidence interval.

## Tests

`tests/test_discovery.py` (17 tests, offline; a deterministic test double stands in for the provider and is never presented as semantic search): schema, text recipe, pins and hashes, private records never embedded or returned, incremental re-index and head supersession, poisoned-document isolation, request budget and resume, dry run, contract shape, fusion and semantic-only matches, artifacts, kind filter and Event exclusion, labelled fallbacks, query cache/rate limit/timeout/cache-only, validation, and the Gemini adapter's request shape, normalisation and error hygiene.
