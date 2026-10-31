-- Vector discovery tables. Additive only: no change to any existing table. Run by Discovery.initialize() with the store's search_path
-- extended by the schema that holds the pgvector extension. The extension itself is created by a superuser (see docs/discovery.md);
-- pgvector 0.6.0 is not a "trusted" extension, so a non-superuser service role cannot create it.
-- Only PUBLIC record versions and the declared metadata of their artifacts are ever written here. Vectors are 768-dimensional.

CREATE TABLE IF NOT EXISTS discovery_documents (
  doc_id          text PRIMARY KEY,                  -- record:<version> | artifact:<evidence version>:<artifact sha256>:<role>
  doc_type        text NOT NULL CHECK (doc_type IN ('record','artifact')),
  version         text NOT NULL REFERENCES record_versions(version),   -- the immutable record version this vector describes
  namespace       text NOT NULL,
  kind            text NOT NULL,
  record_id       text NOT NULL,
  artifact_sha256 text,
  artifact_role   text,
  title           text NOT NULL,
  input_text      text NOT NULL,                     -- exactly what was embedded (public text only), bounded
  input_sha256    text NOT NULL,                     -- sha256 of input_text (utf-8)
  text_recipe     text NOT NULL,
  truncated       boolean NOT NULL DEFAULT false,
  provider        text NOT NULL,
  model           text NOT NULL,
  dimensions      integer NOT NULL CHECK (dimensions = 768),
  task_type       text NOT NULL,
  embedding       vector(768) NOT NULL,
  embedded_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS discovery_documents_hnsw ON discovery_documents USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS discovery_documents_version ON discovery_documents(version);
CREATE INDEX IF NOT EXISTS discovery_documents_kind ON discovery_documents(kind, doc_type);
CREATE INDEX IF NOT EXISTS discovery_documents_fts ON discovery_documents USING GIN (to_tsvector('simple', input_text));

CREATE TABLE IF NOT EXISTS discovery_failures (
  id            bigserial PRIMARY KEY,
  run_id        text NOT NULL,
  doc_id        text NOT NULL,
  error_class   text NOT NULL,
  message       text NOT NULL,                       -- sanitized; never a credential
  attempted_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS discovery_failures_doc ON discovery_failures(doc_id);

CREATE TABLE IF NOT EXISTS discovery_runs (
  run_id        text PRIMARY KEY,
  started_at    timestamptz NOT NULL,
  finished_at   timestamptz,
  provider      text NOT NULL,
  model         text NOT NULL,
  dimensions    integer NOT NULL,
  text_recipe   text NOT NULL,
  requests      integer NOT NULL DEFAULT 0,
  summary       jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS discovery_query_cache (
  query_hash    text PRIMARY KEY,                    -- sha256 of normalized query + provider + model + dimensions + task type
  query_text    text NOT NULL,
  model         text NOT NULL,
  embedding     vector(768) NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  hits          integer NOT NULL DEFAULT 0
);
