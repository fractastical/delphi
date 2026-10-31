# Frontier runtime: dedicated PostgreSQL instance, website/API adapter, nginx

Single-reader (collab), not Codex-reviewed. **Prepared, not installed or started.** Root owns install, start and routing. This document does not switch the apex
`morphoswarm.ai`, does not touch `studio.morphoswarm.ai`, and changes no nginx global setting.

## What exists

| Piece | Files | State |
|---|---|---|
| Dedicated PostgreSQL 16 **instance** (not a schema in a shared cluster) | `deploy/postgres/init-cluster.sh`, `create-db.sh`, `backup.sh`; unit `deploy/systemd/delphi-frontier-postgres.service` | `init-cluster.sh` was run once for the real root `/data/services/delphi-frontier` (created only because neither the root nor any `PG_VERSION` existed): directories 700, `pgdata` initialised, config written. **Not started.** No role/database yet (they need a running server: `create-db.sh`). |
| Website/API adapter (loopback 127.0.0.1:8971) | `frontier/web.py`; unit `deploy/systemd/delphi-frontier-web.service` | tested (below); not installed |
| Operator tool | `frontier/admin.py` (`bootstrap`, `provision`, `status`) | tested |
| nginx vhost for `frontier.morphoswarm.ai` | `deploy/nginx/frontier.morphoswarm.ai.conf` | `nginx -t` passes in a scratch config; not installed |
| Public principal lookup | `Store.principal(token)` in `store.py` (additive) | tested through admin |

## The instance

Root `/data/services/delphi-frontier` (mode 700): `pgdata/`, `run/` (the private socket directory), `backups/`, `credentials/`, marker `.frontier-instance`, and, when root creates it, `app/` (a checkout of merged `main`).
Unix socket only: `listen_addresses = ''`, socket `run/.s.PGSQL.5471` (the number only names the file), `unix_socket_permissions = 0700`, `pg_hba.conf` = `local frontier frontier_app peer map=frontier` and `local all <service user> peer`
(no `host` lines, no `trust`, no password anywhere). Role `frontier_app` is `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 30` and owns database `frontier`; the OS service user maps to it through `pg_ident.conf`.
DSN: `host=/data/services/delphi-frontier/run port=5471 dbname=frontier user=frontier_app`. The Frontier schema lives in that database's `public` schema (`--schema public`).
`init-cluster.sh` **refuses** (exit 3, nothing changed) a root that is non-empty and lacks our marker (an `app/` directory is allowed) or a data directory it did not create, so it can never adopt or reconfigure an unrelated cluster; it rewrites only its own `pg_hba.conf`, `pg_ident.conf` and its marked block in `postgresql.conf`.
Service bounds: PostgreSQL `MemoryMax=2G MemorySwapMax=0 TasksMax=64`; web `MemoryMax=1G MemorySwapMax=0 TasksMax=64`, `OMP/OPENBLAS/MKL_NUM_THREADS=1`. Both are persistent (no `RuntimeMaxSec`); tests and builds keep `RuntimeMaxSec=600`.

## Web adapter: contract

All responses carry `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `X-Robots-Tag: noindex`; HTML gets a strict CSP. Host must be `frontier.morphoswarm.ai` or loopback:port; an `Origin`, when present, must be the public origin or loopback:port.

| Request | Gate | Notes |
|---|---|---|
| `GET /api/health` | none | `{"status","service","mode":"live"}`, 503 if the database is unreachable; nothing else |
| `POST /api/session` `{"token"}`; `GET`; `DELETE` | token compared in constant time; 10 failures/60 s per client then 429 | cookie `__Host-frontier_session` (`frontier_session` with `--insecure-cookies`), `HttpOnly; SameSite=Strict; Path=/; Secure; Max-Age=8h`; server-side session; `DELETE` needs Origin + `X-CSRF-Token` |
| `GET/POST /login` | none | plain HTML form, no script; `?token=` sign-in links are deliberately **not** supported (URL secrets leak into history and Referer) |
| `GET /api/catalog?query&kind&status&limit<=50&after` | session | full record envelopes, `local_status` kept separate, `next_cursor`, `namespace`, `mode: live`, `search_mode` (what actually ran; `store_lexical` until a search index is wired through `WebConfig.catalog_search`). Events are records and are listed unless you filter by `kind`. |
| `GET /api/record?namespace&kind&id&version` | session | pinned Ref only; 404 for private or absent |
| `GET /api/events?after&limit<=50` | session | |
| `GET /api/artifacts?q\|query&role&evidence_kind&limit<=50&after` | session | root's `ArtifactIndex`; declarations only, `artifact_bytes_verified: false`; no URL is ever fetched |
| `POST /api/engineering/solve` (<= 1024 B JSON object) | session + Origin + CSRF | late import of `frontier.engineering_api.solve_design(data)`; its answer and its `FrontierError`s (invalid, busy) pass through; **503 `engineering_unavailable`** if the module is absent, with nothing computed |
| `POST /v1/*` | reads: session or bearer; **writes: operator `Authorization: Bearer` + `Idempotency-Key` only** | a browser session never authorises a write; same `Application` as the loopback protocol adapter (`frontier/http.py`, unchanged) |
| anything else `GET/HEAD` | session (or `--public-site` for the static shell only) | static files from `site/`, see below |

Extension point: `WebConfig(routes={"POST /api/<name>": Route(handler, max_body=1024, max_concurrent=2)})`; gated like the solver (session, Origin, CSRF for POST); a custom route cannot shadow a built-in. Handlers return `(status, object)` and may raise `FrontierError`; any other exception becomes a generic 500 and is never echoed.

Static files: only inside `site/`, extension allow-list, no dotfiles, no symlink escapes, no directory listings, <= 8 MB; names containing secret/token/credential/password/private/.pem/.key/.env are never served. Under **`site/artifacts/` only**, also `.stl` (`model/stl`, downloaded), `.obj` (`model/obj`, downloaded), `.glb` (`model/gltf-binary`, downloaded), `.csv`, `.lean` (`text/plain`), `.trig` (`application/trig`), <= 16 MB; the same names elsewhere in `site/` are 404.

Logs: `METHOD PATH STATUS` only. Never the query string, a header, a cookie or a body. nginx uses the existing `morphoswarm_redacted` format (`$uri`, never the query string).

## Credentials and the review boundary

* Browser gate: `FRONTIER_ACCESS_TOKEN`, else `MORPHOSWARM_STUDIO_TOKEN`, both from the service's `EnvironmentFile`s (`-%h/.config/morphoswarm/studio.env`, `-%h/.config/delphi-frontier/web.env`). The adapter refuses to start without a token of at least 16 characters and never prints one. The studio file holds the studio's other settings too; for a smaller blast radius create `web.env` and delete the studio line from the unit.
* Operator credentials: `python -m frontier.admin provision --namespace N --actor A --operator O --roles contributor,coordinator --credential-file PATH`. The credential is generated, written once to `PATH` (mode 600, `O_EXCL`, inside a private directory that is not in a git work tree) and never printed or passed as an argument. Re-running is a no-op if the file already matches; it never overwrites.
* Independent review stays independent: one principal cannot hold both reviewer and contributor/coordinator, and an operator id cannot span the two sides. Nothing here seeds records or accepts anything; seeded records stay `proposed` until a separate reviewer credential acts.

## Install steps for root (NOT executed)

```bash
# 0. checkout of merged main at /data/services/delphi-frontier/app  (init-cluster.sh tolerates an app/ directory)
cd /data/services/delphi-frontier/app
# 1. the instance (already prepared; re-running is safe)
cp deploy/systemd/delphi-frontier-postgres.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now delphi-frontier-postgres
bash deploy/postgres/create-db.sh
# 2. schema + principals (credentials land in mode-600 files, nothing printed)
export FRONTIER_DSN="host=/data/services/delphi-frontier/run port=5471 dbname=frontier user=frontier_app"
python -m frontier.admin bootstrap --namespace delphi-frontier --schema public
python -m frontier.admin provision --namespace delphi-frontier --actor <writer> --operator <op-a> --roles contributor,coordinator --credential-file /data/services/delphi-frontier/credentials/<writer>.cred
python -m frontier.admin provision --namespace delphi-frontier --actor <reviewer> --operator <op-b> --roles reviewer --credential-file /data/services/delphi-frontier/credentials/<reviewer>.cred
# 3. web
cp deploy/systemd/delphi-frontier-web.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now delphi-frontier-web
curl -sS http://127.0.0.1:8971/api/health
# 4. nginx (root)
sudo cp deploy/nginx/frontier.morphoswarm.ai.conf /etc/nginx/conf.d/ && sudo nginx -t && sudo systemctl reload nginx
curl -sS https://frontier.morphoswarm.ai/api/health
```

The namespace (`delphi-frontier` in the unit) is fixed by the first `bootstrap`; the store refuses a different one afterwards. Backups: `bash deploy/postgres/backup.sh` (custom-format dumps, mode 600, newest 14).

## Receipts (what was actually run; Seattle PDT, 2026-10-31)

* `bash scripts/test_postgres.sh` on the branch before the artifact/engineering additions: **81 passed**. After them only the affected tests were re-run (artifact, extension-route, engineering, static, traversal, capability): **all passed**.
* `deploy/verify-scratch.sh` (bounded scope, scratch root in `/tmp`, deleted at the end): refusal to adopt a foreign directory; instance prepared twice; role+database created twice; no TCP listener; peer login as the non-superuser role; bootstrap; credential provisioning (`provisioned`, `provisioned`, `already_provisioned`); real HTTP session; write with an operator bearer; session alone refused; independent reviewer accepts and the writer's own credential cannot; six artifact types served from `site/artifacts/` and refused elsewhere; credential-looking name and traversal refused; backup written; **PostgreSQL and the web service both restarted and the record, its accepted review and its idempotency record survived**; directory modes 700, credential files 600; `pg_hba` local peer only; no secret in `web.log` or `pg.log`. Final line `ALL SCRATCH CHECKS PASSED`.
* Guard-removal mutations of the web/admin code, each failing a test: Origin check, Host check, directory containment, CSRF check, query string in logs, `HttpOnly`, reviewer-role mixing, credential file mode. One mutation survived and is **equivalent, not a hole**: removing the web layer's "writes need a bearer header" pre-check changes nothing observable because the store itself answers 401.
* `nginx -t` on a scratch config containing the vhost with a throwaway certificate: successful; the same file with a deliberately broken `proxy_pass`: failed.
* Real instance: `init-cluster.sh` run once at `/data/services/delphi-frontier` after confirming the root and any `PG_VERSION` were absent, no process or socket existed. Result: files only, mode 700, `pg_hba` local peer only. Nothing started.

## Not done / not verified

* Nothing installed, started or reloaded; the real instance has no role or database yet.
* The studio gate was not read or changed. Whether the studio's `MORPHOSWARM_STUDIO_TOKEN` is the right audience token is root's call; a dedicated `FRONTIER_ACCESS_TOKEN` is supported and preferred for a smaller blast radius.
* `engineering_api.py` and `SearchIndex` are root's; the adapter only wires them (late import; `WebConfig.catalog_search`).
* No TLS test against the real certificate (root-only files), no load test, no browser test; sessions are in memory (a restart signs everyone out); the sign-in throttle is per client address and in memory.
* systemd sandboxing beyond `NoNewPrivileges` (`ProtectSystem`, `PrivateTmp`) is not enabled because it needs user namespaces in a user manager; candidate hardening once root confirms the host supports it.
