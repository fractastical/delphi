# Frontier database snapshot

`frontier-2026-11-01.sql.gz` — a `pg_dump` of the live MorphoSwarm Frontier node's
`public` schema, taken 2026-11-01.

| | |
|---|---|
| Source | PostgreSQL 16 with pgvector, the node behind https://frontier.morphoswarm.ai |
| Compressed | 22.7 MB · uncompressed 77.6 MB · live database 94 MB |
| sha256 | see `frontier-2026-11-01.sql.gz.sha256` |
| Tables | 18 |

## Restore

```sh
createdb frontier
gunzip -c frontier-2026-11-01.sql.gz | psql frontier
```

The dump carries no owner or privilege statements, so it restores as whoever runs it.

## Row counts at dump time

| Table | Rows |
|---|---:|
| `action_state` | 70 |
| `discovery_documents` | 4607 |
| `discovery_failures` | 312 |
| `discovery_query_cache` | 16 |
| `discovery_runs` | 119 |
| `events` | 1988 |
| `forks` | 0 |
| `heads` | 3954 |
| `idempotency` | 380 |
| `imported_review_claims` | 0 |
| `local_states` | 3960 |
| `node_config` | 1 |
| `principals` | 5 |
| `record_versions` | 3960 |
| `reviews` | 2 |
| `schema_migrations` | 1 |
| `typed_edges` | 2529 |
| `write_receipts` | 380 |

## What was deliberately left out

**`principals` rows are excluded; its schema is kept.** That table holds five
`token_hash` values — hashes of contributor bearer tokens. Publishing password-equivalent
hashes in a public repository would be careless even though they are hashed, so the data
is withheld and the structure retained. Everything else is dumped in full.

A credential scan of the dump returned two apparent matches, both false positives: public
nanopublication IRIs of the form `https://w3id.org/np/ra...` that happen to contain the
letters `sk-`. No key, token or password is present.

## What this snapshot is and is not

It is the state of one node at one moment. Records carry their own review status, and an
upstream label in a record is an assertion by that upstream, never acceptance by this
node. Nothing here is biologically validated.
