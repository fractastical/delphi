-- Search indexes over the EXISTING append-only tables. No table, column or data copy is added; only indexes.
-- Idempotent. Run by SearchIndex.initialize() with the store's search_path. PostgreSQL 16 target.
-- record_versions is append-only (frontier_immutable trigger on UPDATE/DELETE); CREATE INDEX is DDL and does not touch rows.

-- Full-text candidate retrieval over the store's own search_text (lowercased id + canonical payload JSON).
-- 'simple' dictionary: no stemming and no stop words, so identifiers, symbols and code-like tokens are not rewritten.
CREATE INDEX IF NOT EXISTS record_search_fts ON record_versions USING GIN (to_tsvector('simple', search_text));

-- Exact and prefix lookups the ranking and the source filter use.
CREATE INDEX IF NOT EXISTS record_title_lower ON record_versions ((lower(envelope #>> '{payload,title}')));
CREATE INDEX IF NOT EXISTS record_source_uri_prefix ON record_versions ((lower(source_uri)) text_pattern_ops);
CREATE INDEX IF NOT EXISTS record_payload_source_prefix ON record_versions ((lower(envelope #>> '{payload,source,uri}')) text_pattern_ops);
CREATE INDEX IF NOT EXISTS record_kind_namespace ON record_versions(kind, namespace);

-- Dispute and fork lookups for the explicit opposing-evidence references.
CREATE INDEX IF NOT EXISTS review_target ON reviews(target_version);
CREATE INDEX IF NOT EXISTS fork_imported ON forks(imported_version);
