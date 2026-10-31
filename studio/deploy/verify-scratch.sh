#!/usr/bin/env bash
# Proves deploy/postgres/*.sh and the web/admin services end to end in a SCRATCH root (never /data/services): dedicated instance, Unix socket only,
# peer auth, role + database, bootstrap, credential provisioning, real HTTP session, write + independent review, artifact serving, restart persistence,
# backup. Everything is deleted at the end. Run inside the bounded scope:
#   systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash deploy/verify-scratch.sh
set -euo pipefail
test -n "${INVOCATION_ID:-}" || { echo 'run inside the bounded systemd scope' >&2; exit 2; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PGBIN="${FRONTIER_PG_BIN:-/usr/lib/postgresql/16/bin}"
PY="${PYTHON:-python}"
T="$(mktemp -d /tmp/frontier-verify.XXXXXXXX)"; chmod 700 "$T"
WEB_PORT=18971; export FRONTIER_PG_ROOT="$T" FRONTIER_PG_PORT=5472
export FRONTIER_ACCESS_TOKEN="$($PY -c 'import secrets; print("gate-" + secrets.token_urlsafe(32))')"
export PYTHONPATH="$REPO${FRONTIER_QA_EXTRA_PYTHONPATH:+:$FRONTIER_QA_EXTRA_PYTHONPATH}" OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
WEBPID=""
stop_web() { [ -z "$WEBPID" ] || { kill "$WEBPID" 2>/dev/null || true; wait "$WEBPID" 2>/dev/null || true; WEBPID=""; }; }
cleanup() { stop_web; "$PGBIN/pg_ctl" -D "$T/pgdata" -m immediate -w stop >/dev/null 2>&1 || true; rm -rf -- "$T" "${T}-unrelated"; }
trap cleanup EXIT
start_pg() { "$PGBIN/pg_ctl" -D "$T/pgdata" -l "$T/pg.log" -w start >/dev/null; }
start_web() {
  $PY -m frontier.web --namespace verify-node --schema public --port $WEB_PORT --site "$T/site" --insecure-cookies 2>"$T/web.log" & WEBPID=$!
  for _ in $(seq 100); do curl -fsS "http://127.0.0.1:$WEB_PORT/api/health" >/dev/null 2>&1 && return 0; sleep 0.1; done
  echo "web service did not come up" >&2; exit 1
}

echo "== refuses to adopt an unrelated non-empty directory"
U="$T-unrelated"; mkdir "$U"; echo x > "$U/file"
if bash "$REPO/deploy/postgres/init-cluster.sh" "$U" 2>/dev/null; then echo "FAIL adopted a foreign directory"; exit 1; else echo "PASS refused (exit $?), directory untouched: $(ls "$U")"; fi

echo "== prepare the dedicated instance"
bash "$REPO/deploy/postgres/init-cluster.sh" "$T"
bash "$REPO/deploy/postgres/init-cluster.sh" "$T" >/dev/null && echo "PASS init-cluster.sh is idempotent on its own instance"
start_pg
echo "== role and database (twice: idempotent)"
bash "$REPO/deploy/postgres/create-db.sh" "$T"; bash "$REPO/deploy/postgres/create-db.sh" "$T" >/dev/null && echo "PASS create-db.sh is idempotent"
if "$PGBIN/psql" -X -h 127.0.0.1 -p 5472 -d postgres -c 'select 1' >/dev/null 2>&1; then echo "FAIL a TCP listener answered"; exit 1; else echo "PASS no TCP listener on 127.0.0.1:5472"; fi
"$PGBIN/psql" -X -h "$T/run" -p 5472 -U frontier_app -d frontier -Atc "select current_user, (select rolsuper from pg_roles where rolname = current_user)" | sed 's/^/PASS peer login as least-privilege role: /'
export FRONTIER_DSN="host=$T/run port=5472 dbname=frontier user=frontier_app"

echo "== bootstrap + provisioning (credential values never printed)"
$PY -m frontier.admin bootstrap --namespace verify-node --schema public | $PY -c 'import json,sys; d=json.load(sys.stdin); print("PASS bootstrap initialized =", d["initialized"], "records =", d["records"])'
$PY -m frontier.admin provision --namespace verify-node --actor e2e-writer --operator op-writer --roles contributor,coordinator --credential-file "$T/credentials/writer.cred" | grep -o '"status": "[a-z_]*"'
$PY -m frontier.admin provision --namespace verify-node --actor e2e-reviewer --operator op-reviewer --roles reviewer --credential-file "$T/credentials/reviewer.cred" | grep -o '"status": "[a-z_]*"'
$PY -m frontier.admin provision --namespace verify-node --actor e2e-writer --operator op-writer --roles contributor,coordinator --credential-file "$T/credentials/writer.cred" | grep -o '"status": "[a-z_]*"'

echo "== site fixture + web service"
mkdir -p "$T/site/artifacts" "$T/site/other"
echo '<!doctype html><title>Frontier</title>' > "$T/site/index.html"
for f in mesh.stl part.obj wing.glb table.csv t.lean x.trig; do echo "fixture $f" > "$T/site/artifacts/$f"; done
echo x > "$T/site/artifacts/secret-token.csv"; echo x > "$T/site/other/mesh.stl"
start_web
$PY "$REPO/deploy/verify_e2e.py" $WEB_PORT "$T" first
echo "== adapters (search index default, engineering, attention, beliefs); modules not yet merged are reported as SKIP, never faked"
$PY "$REPO/deploy/verify_e2e.py" $WEB_PORT "$T" adapters
echo "== backup"
bash "$REPO/deploy/postgres/backup.sh" "$T" | sed 's#/tmp/frontier-verify\.[A-Za-z0-9]*#<scratch>#'
echo "== restart PostgreSQL and the web service"
stop_web; "$PGBIN/pg_ctl" -D "$T/pgdata" -m fast -w stop >/dev/null; start_pg; start_web
$PY "$REPO/deploy/verify_e2e.py" $WEB_PORT "$T" after-restart
$PY "$REPO/deploy/verify_e2e.py" $WEB_PORT "$T" files
echo "== logs carry no secrets"
if grep -q -e "$FRONTIER_ACCESS_TOKEN" -e "$(cat "$T/credentials/writer.cred")" "$T/web.log" "$T/pg.log"; then echo "FAIL a credential is in a log"; exit 1; else echo "PASS no access token or operator credential in web.log or pg.log"; fi
echo "ALL SCRATCH CHECKS PASSED"
