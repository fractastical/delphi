-- PostgreSQL 16 target. Every version/event and review receipt is append-only.
CREATE TABLE IF NOT EXISTS node_config (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1), namespace TEXT NOT NULL,
  schema_version INTEGER NOT NULL CHECK (schema_version = 1)
);
CREATE TABLE IF NOT EXISTS principals (
  token_hash TEXT PRIMARY KEY, actor TEXT NOT NULL, operator TEXT NOT NULL,
  roles JSONB NOT NULL, namespaces JSONB NOT NULL,
  daily_write_limit INTEGER NOT NULL CHECK (daily_write_limit BETWEEN 1 AND 1000)
);
CREATE TABLE IF NOT EXISTS record_versions (
  version TEXT PRIMARY KEY CHECK (version ~ '^[0-9a-f]{64}$'),
  namespace TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN
  ('Problem','Claim','Evidence','Assessment','Action','Actor','ResourceOffer','Interest','Event','Project','Annotation')),
  record_id TEXT NOT NULL, issuer TEXT NOT NULL, source_uri TEXT NOT NULL,
  visibility TEXT NOT NULL CHECK (visibility IN ('public','private')),
  predecessor TEXT, created_at TIMESTAMPTZ NOT NULL, envelope JSONB NOT NULL,
  search_text TEXT NOT NULL,
  UNIQUE(namespace,kind,record_id,version)
);
CREATE INDEX IF NOT EXISTS record_identity ON record_versions(namespace,kind,record_id);
CREATE TABLE IF NOT EXISTS heads (
  namespace TEXT NOT NULL, kind TEXT NOT NULL, record_id TEXT NOT NULL,
  version TEXT NOT NULL REFERENCES record_versions(version),
  PRIMARY KEY(namespace,kind,record_id)
);
CREATE TABLE IF NOT EXISTS local_states (
  version TEXT PRIMARY KEY REFERENCES record_versions(version),
  status TEXT NOT NULL CHECK (status IN ('proposed','imported_unreviewed','accepted','disputed','rejected')),
  policy_version TEXT NOT NULL, submitter_actor TEXT NOT NULL, submitter_operator TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS typed_edges (
  source_version TEXT NOT NULL REFERENCES record_versions(version), relation TEXT NOT NULL,
  target_namespace TEXT NOT NULL, target_kind TEXT NOT NULL, target_id TEXT NOT NULL,
  target_version TEXT NOT NULL,
  PRIMARY KEY(source_version, relation, target_version)
);
CREATE INDEX IF NOT EXISTS edge_target ON typed_edges(target_version);
CREATE TABLE IF NOT EXISTS events (
  sequence BIGSERIAL PRIMARY KEY, event_version TEXT UNIQUE NOT NULL REFERENCES record_versions(version),
  event_type TEXT NOT NULL, target_version TEXT NOT NULL REFERENCES record_versions(version),
  actor TEXT NOT NULL, operator TEXT NOT NULL, witnessed_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
  actor TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
  response JSONB NOT NULL, witnessed_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(actor,key)
);
CREATE TABLE IF NOT EXISTS write_receipts (
  id BIGSERIAL PRIMARY KEY, actor TEXT NOT NULL, operator TEXT NOT NULL,
  witnessed_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS receipt_quota ON write_receipts(operator,witnessed_at);
CREATE TABLE IF NOT EXISTS reviews (
  assessment_version TEXT PRIMARY KEY REFERENCES record_versions(version),
  target_version TEXT NOT NULL REFERENCES record_versions(version),
  reviewer TEXT NOT NULL, operator TEXT NOT NULL, decision TEXT NOT NULL,
  policy_version TEXT NOT NULL, witnessed_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS action_state (
  version TEXT PRIMARY KEY REFERENCES record_versions(version),
  state TEXT NOT NULL CHECK (state IN ('proposed','ready','leased','running','submitted','reviewed','accepted','disputed','failed','blocked','expired','cancelled')),
  lease_id TEXT, lease_actor TEXT, lease_operator TEXT, lease_until TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS forks (
  namespace TEXT NOT NULL, kind TEXT NOT NULL, record_id TEXT NOT NULL,
  local_version TEXT NOT NULL REFERENCES record_versions(version),
  imported_version TEXT NOT NULL REFERENCES record_versions(version),
  PRIMARY KEY(local_version,imported_version)
);
CREATE TABLE IF NOT EXISTS imported_review_claims (
  digest TEXT PRIMARY KEY, exporting_node TEXT NOT NULL, receipt JSONB NOT NULL,
  received_at TIMESTAMPTZ NOT NULL
);
-- Additive migration, idempotent. A store initialised before Project/Annotation has a CHECK that rejects the new kinds and
-- `CREATE TABLE IF NOT EXISTS` does not touch it. Replace only that constraint; no row is read for update or rewritten, and the
-- old rows (which passed the narrower list) are unchanged byte for byte. NOT VALID then VALIDATE avoids a long exclusive scan.
CREATE TABLE IF NOT EXISTS schema_migrations (
  id TEXT PRIMARY KEY, description TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL
);
DO $$
DECLARE cname TEXT;
BEGIN
  SELECT c.conname INTO cname FROM pg_constraint c
   WHERE c.conrelid = to_regclass('record_versions') AND c.contype = 'c'
     AND pg_get_constraintdef(c.oid) LIKE '%''Problem''%' AND pg_get_constraintdef(c.oid) NOT LIKE '%''Annotation''%';
  IF cname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE record_versions DROP CONSTRAINT %I', cname);
    ALTER TABLE record_versions ADD CONSTRAINT record_versions_kind_check CHECK (kind IN
      ('Problem','Claim','Evidence','Assessment','Action','Actor','ResourceOffer','Interest','Event','Project','Annotation')) NOT VALID;
    ALTER TABLE record_versions VALIDATE CONSTRAINT record_versions_kind_check;
  END IF;
END; $$;
INSERT INTO schema_migrations(id,description,applied_at)
  VALUES ('projects-annotations-1','record kinds Project and Annotation added to the record_versions kind check',CURRENT_TIMESTAMP)
  ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION frontier_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Frontier immutable table: append only'; END; $$;
DO $$
DECLARE name TEXT;
BEGIN
  FOREACH name IN ARRAY ARRAY['record_versions','typed_edges','events','reviews','write_receipts','idempotency','forks','imported_review_claims','schema_migrations'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = name || '_immutable' AND tgrelid = to_regclass(name)) THEN
      EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION frontier_immutable()', name || '_immutable', name);
    END IF;
  END LOOP;
END; $$;
