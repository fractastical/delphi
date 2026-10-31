# Frontier runtime: dedicated PostgreSQL instance, website/API adapter, nginx

## Current access policy (October 31, 2026)

The dedicated PostgreSQL instance, web service and exact-host nginx vhost are now
installed and running. The earlier implementation notes below describe the
pre-installation state. The first deployed receipt is
`deploy/receipts/first-live-check.json`.

The owner requested public browsing: the web unit sets `FRONTIER_PUBLIC_READ=1`.
This opens the site and public record reads without an audience token. Anonymous
visitors get an automatically issued CSRF session for the bounded engineering and
belief calculators; it conveys no contributor identity or write permission.

Contributor clients may inspect their own identity with `POST /v1/read/identity`,
an empty JSON object and an `Authorization: Bearer` header. The response contains
the principal's actor, operator, roles, namespaces and daily write limit, never
the token. Public access and a browser session do not authorize this endpoint.
Use the authenticated actor when composing contributions; ordinary proposal
authorization, exact-version references and idempotency still apply.
Private records remain filtered, and contribution, review, import and action
transitions still require operator bearer credentials and their existing roles.
`--public-site` retains its older shell-only meaning; private mode is still the
default when neither `--public-read` nor its environment flag is set.

Frontier's vhost has no IP restriction. Orchestra's separate vhosts retain their
IP allowlist and application token checks. No Orchestra configuration was changed.
The legacy audience EnvironmentFiles remain temporarily so rollback to the first
gated release can still start; public mode ignores those token values.

Check the public deployment with `deploy/verify_live.py --public-read --receipt
<path> [--screenshots <directory>]` inside the documented bounded systemd scope.

Single-reader (collab), not Codex-reviewed. Root owns install, start and routing. (Updated for root's `085b49c`: search index default, attention, belief adapter, video artifacts, venv unit path.) This document does not switch the apex
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
| `GET /api/catalog?query&kind&status&limit<=50&after` | session | full record envelopes, `local_status` kept separate, `next_cursor`, `namespace`, `mode: live`, `search_mode`: **`search_index`** by default (`SearchIndex(store).query`; the index's own explanation is in each row's `match`, apart from the record), `store_lexical` only with `--legacy-catalog`. `after` accepts the index's `next_cursor` or a bare 64-hex version for an empty query. Events are records and are listed unless you filter by `kind`. |
| `GET /api/attention` (no parameters) | session | `{mode, namespace, generated_at, inputs{records, events, annotations: 0, public_only}, view}` where `view = attention.view.build_view(records, events, [], now)` built from PUBLIC stored records and events only, reused for 5 s; **422 `view_too_large`** (never a partial view) above 2000 records / 5000 events; **503 `attention_unavailable`** if the module is absent. Module name is configuration from an allow-list (`--attention-module`, default `attention.view`; also `frontier_attention.view`, `frontier.attention.view`, `frontier.attention`). No annotation documents are loaded (the store cannot hold them), so unlock edges are absent from this view. |
| `GET /api/record?namespace&kind&id&version` | session | pinned Ref only; 404 for private or absent |
| `GET /api/events?after&limit<=50` | session | |
| `GET /api/artifacts?q\|query&role&evidence_kind&limit<=50&after` | session | root's `ArtifactIndex`; declarations only, `artifact_bytes_verified: false`; no URL is ever fetched |
| `POST /api/engineering/solve` (<= 1024 B JSON object) | session + Origin + CSRF | late import of `frontier.engineering_api.solve_design(data)`; its answer and its `FrontierError`s (invalid, busy) pass through; **503 `engineering_unavailable`** if the module is absent, with nothing computed |
| `GET /api/system` (no parameters) | session | read-only snapshot, cached 30 s, with **every section labelled `measured` or `worker_report`**. *Measured now*: public-row counts by kind and local status (versions and heads), event counts by type, database size and uptime (all in a READ ONLY transaction); this process (uptime, RSS, threads, CPU seconds); shared-host `/proc` totals (load, memory, CPU pressure) labelled *not attributable to any job, team or service*; the state of our two systemd user units and the checkout's `git rev-parse HEAD`, via two FIXED commands sharing a 2 s budget. *Worker reports* (file sha256 shown, contents unverified): `tasks/BUILD.md` rows and findings, `specs/SPEC-*.md` titles and status lines, `GOAL.md`, `build-info.json` (`{release_sha, built_at, checks[]}` written at release; compared with the measured checkout SHA), and **pinned provider receipts** (`deploy/system/receipt-pins.json`: repo-relative path + sha256; a changed file is withheld). Actual cost is `unknown` and utilization `not_computed` unless a pinned receipt carries a billed figure (none does); the sum of job-reported wall seconds is labelled as not billed time. Never output: environment, tokens, credential paths, host or user names, other processes' command lines, other teams' jobs. |
| `POST /api/beliefs/solve` (<= 32 KB JSON object) | session + Origin + CSRF | late import of `frontier.beliefs_api.solve_scenario(data)` (director's adapter: validation, isolated 8 s child, two slots). Its envelope (`schema frontier.beliefs.api/1`, `status`, `calibrated: false`, `assumed_scope`, `result`) is passed through verbatim, **including its error bodies** (400 `invalid_request`, 413, 429 `solver_busy`, 503), which are served as the adapter built them. **503 `beliefs_unavailable`** if the module is absent. This adapter never runs the solver in a web thread. |
| `POST /v1/*` | reads: session or bearer; **writes: operator `Authorization: Bearer` + `Idempotency-Key` only** | a browser session never authorises a write; same `Application` as the loopback protocol adapter (`frontier/http.py`, unchanged) |
| anything else `GET/HEAD` | session (or `--public-site` for the static shell only) | static files from `site/`, see below |

Extension point: `WebConfig(routes={"POST /api/<name>": Route(handler, max_body=1024, max_concurrent=2)})`; gated like the solver (session, Origin, CSRF for POST); a custom route cannot shadow a built-in. Handlers return `(status, object)` and may raise `FrontierError`; any other exception becomes a generic 500 and is never echoed.

Static files: only inside `site/`, extension allow-list, no dotfiles, no symlink escapes, no directory listings, <= 8 MB; names containing secret/token/credential/password/private/.pem/.key/.env are never served. Under **`site/artifacts/` only**, also `.stl` (`model/stl`, downloaded), `.obj` (`model/obj`, downloaded), `.glb` (`model/gltf-binary`, downloaded), `.csv`, `.lean` (`text/plain`), `.trig` (`application/trig`), <= 16 MB, and `.mp4` (`video/mp4`) / `.webm` (`video/webm`), <= 64 MB, streamed from disk in 64 KB chunks with single-range support (`Accept-Ranges: bytes`, `206`/`416`; Safari needs this) and never read whole into memory; the same names elsewhere in `site/` are 404, and no endpoint takes a path.

Logs: `METHOD PATH STATUS` only. Never the query string, a header, a cookie or a body. nginx uses the existing `morphoswarm_redacted` format (`$uri`, never the query string).

## Credentials and the review boundary

* Browser gate: `FRONTIER_ACCESS_TOKEN`, else `MORPHOSWARM_STUDIO_TOKEN`, both from the service's `EnvironmentFile`s (`-%h/.config/morphoswarm/studio.env`, `-%h/.config/delphi-frontier/web.env`). The adapter refuses to start without a token of at least 16 characters and never prints one. The studio file holds the studio's other settings too, so the checked-in public-read unit no longer loads it (public-read mode reads no access token); a gated rollback needs `web.env` with `FRONTIER_ACCESS_TOKEN` instead.
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
# 3. web (the unit's ExecStart is root's venv: /data/services/delphi-frontier/venv/bin/python; no new venv is created by this branch)
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
* `engineering_api.py`, `beliefs_api.py`, `SearchIndex` and the market `attention` package are not mine; the adapter only wires them (late imports; `WebConfig.catalog_search`). Root's venv python is a symlink into `/home/ubuntu/miniconda3/bin`, so the service still depends on that conda interpreter even though its packages are in the venv.
* Measured 2026-10-31, in-process, inside `frontier.beliefs`'s own caps: seeded random scenarios of 13.9 KB and 28 KB took 24 s and 232 s. That is why a web thread must never call `solve` directly. `beliefs_api` bounds it with its isolated 8 s child; this is a fact about the module, not a defect in the adapter.
* No TLS test against the real certificate (root-only files), no load test, no browser test; sessions are in memory (a restart signs everyone out); the sign-in throttle is per client address and in memory.
* systemd sandboxing beyond `NoNewPrivileges` (`ProtectSystem`, `PrivateTmp`) is not enabled because it needs user namespaces in a user manager; candidate hardening once root confirms the host supports it.

## System page data (added for `GET /api/system`)

* Static fallback while the endpoint is not deployed: `python -m frontier.system_status --manifest > site/data/system-manifest.json` (worker reports only; its `measured` field says "not measured"; mode of every section is `worker_report`). The site build is root's; this branch does not write into `site/`.
* `build-info.json` at the checkout root is NOT created by this branch. Whoever cuts a release writes it (`release_sha` = the 40-hex commit, `checks[]` with `name`, `command`, `exit`, `passed`, `total`, `at`); without it the page says "absent" and invents nothing. Test counts must come from an execution receipt, never from counting `def test_` lines (BUILD.md finding).
* The one shipped receipt pin is `results/compute/receipts.json` at sha256 `f534829f…2e8b` (read from `work/frontier-compute@beea7c3`). That file is not in this branch, so until it is merged the page says "not present in this checkout"; if the gpuops worker later changes it, the page says "changed since it was pinned" and shows nothing from it until the pin is updated.

## Releases and rollback (`deploy/release.py`, standard library only)

Layout under `/data/services/delphi-frontier`: `releases/<40-hex sha>/` (an immutable `git archive` of exactly that committed SHA plus `build-info.json` and `.release-complete`),
`releases/history.jsonl` (append-only), `app` (symlink the unit runs from, swapped atomically) and `app.previous` (where `app` pointed before the last switch). It never touches the
database, never deletes or edits a release, and starts nothing by itself. **`deploy` and `rollback` only print a plan unless `--apply` is given.**

```bash
R=/data/services/delphi-frontier/app/deploy/release.py        # or any checkout's deploy/release.py
python3 $R status                                                       # read-only: app, previous, releases, last history lines
python3 $R prepare --repo /path/to/checkout --sha <40-hex> --checks receipt.json     # archive + build-info; refuses failing or foreign checks
python3 $R deploy   --sha <40-hex>                                      # plan only
python3 $R deploy   --sha <40-hex> --apply [--health-timeout 30]        # swap, restart, health, automatic fall-back
python3 $R rollback [--to <sha>] --apply                                # previous release (or a named prepared one), same safeguards
python3 $R verify   --sha <sha> --repo /path/to/checkout                # read-only: recompute the git tree hash of releases/<sha>; equal to git's? (ignores and REPORTS build-info.json, .release-complete, __pycache__)
python3 $R adopt    --sha <sha> --repo /path/to/checkout [--apply]      # one-time: let a hand-built release be rolled back TO, ONLY if byte-identical to the commit; --repo is required
python3 $R deploy   --sha <sha> --apply --nginx-install                 # ONLY with this flag does it touch nginx (sudo, fixed steps, reverted if `nginx -t` fails)
```

* **Checks receipt** (`--checks`): `{"schema": "frontier.release.checks/1", "sha": "<the same 40-hex>", "checks": [{"name", "command", "exit": <int>, "passed", "total", "at", "result"}]}`.
  A receipt naming another SHA is refused; any non-zero `exit` refuses the release (exit code 4) unless `--allow-failed-checks`, which is recorded as `checks_all_passed: false`.
  Write it from real execution results; test counts are never derived by counting source lines. `build-info.json` carries the SHA, the tree SHA, the sha256 of the exact `git archive` stream,
  the checks and the receipt's sha256; `/api/system` shows it labelled as an author report.
* **Deploy steps**: preflight (the release is complete, its `build-info.json` names the SHA, and `import frontier.web ...` succeeds under the service venv, else nothing changes) → write `app.previous`
  → atomic `app` swap (`rename(2)` over the symlink; readers never see it missing) → `systemctl --user restart delphi-frontier-web.service` → health: unit `active` and `/api/health` `ok`
  three times in a row and no self-restart (`NRestarts` unchanged) → on ANY failure restore `app` and `app.previous` exactly as they were, restart, and check health again.
  A first deployment that fails removes only the symlink it just made.
* **Exit codes**: 0 ok or plan; 2 usage; 3 refused (nothing changed); 4 checks failed; 10 failed and rolled back cleanly; **11 failed AND the roll back failed (needs a person)**; 12 nginx test failed and was reverted.
* **Fixed commands only** (`check_argv`): `git -C` read/archive, `systemctl --user restart|is-active|show` of the one unit, one import smoke test with the service venv, and, with `--nginx-install` only, `sudo -n` `install`/`cp`/`mv`/`nginx -t`/`systemctl reload nginx` on the one vhost path. An unknown vhost is moved aside, never deleted.
* Database schema changes are not part of a release switch. `python -m frontier.admin bootstrap` is idempotent (`CREATE ... IF NOT EXISTS`); a release that needs a schema change must stay compatible with the previous release's code so a roll back is safe.
* `deploy/verify_live.py` (root's) is the live HTTP verification; `release.py` does not call it. Its own health check is `/api/health` only.

`/api/system` after these changes: `release.sha` is `git rev-parse HEAD` when the tree is a git checkout, otherwise the name of the `releases/<sha>` directory the code runs from (an archive has no `.git`),
with `release.dir_name_matches_release_marker` checking that name against `.release-complete`; `deployed_sha` repeats it as a top-level string. `build.*` is the author report (label shown) and
`build.matches_checkout` compares it with that measured SHA (`build.compared_with` says which). `store.counts_scope` states that counts cover every public namespace in the database, with `versions_by_namespace`;
`store.namespace` is only this node's own.

**Byte-level integrity (what a directory name is and is not).** A `releases/<40-hex>` directory name is a claim. `prepare` recomputes the git tree hash of what it extracted and refuses unless it equals `git rev-parse <sha>^{tree}`;
`verify` does the same for any release and reports exactly what it ignored; `adopt` accepts a hand-built directory only if it is byte-identical to the commit (mode bits included) apart from `build-info.json` and `__pycache__`, and says which
paths differ otherwise. On the live node, `verify --sha 9e6045ed... --repo <checkout>` (read-only, run 2026-10-31) found the directory identical to the commit: tree `876c2a4f...`, ignoring `build-info.json` and `frontier/__pycache__/`. `/api/system` reports the directory name only as
`release.directory_claim` (never as `deployed_sha`, which is `git rev-parse HEAD` or null) and shows whether the files still hash to the tree recorded in `build-info.json` (cached 600 s; it is a tamper-evidence check, not a live watch).
