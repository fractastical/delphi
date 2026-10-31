#!/usr/bin/env bash
# Live end-to-end of the site against a SCRATCH runtime (dedicated PostgreSQL instance in /tmp, loopback web service, deleted at the end).
#   FRONTIER_REPO=<tree with frontier/web.py (+ frontier/engineering_api.py)> PYTHON=<python with z3 and playwright> \
#   systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash tests/test_site_live.sh
set -euo pipefail
test -n "${INVOCATION_ID:-}" || { echo 'run inside the bounded systemd scope' >&2; exit 2; }
SITE="$(cd "$(dirname "$0")/../site" && pwd)"; REPO="${FRONTIER_REPO:?set FRONTIER_REPO}"; PY="${PYTHON:-python}"
PGBIN="${FRONTIER_PG_BIN:-/usr/lib/postgresql/16/bin}"; OUT="${SITE_E2E_OUT:-/tmp}"
T="$(mktemp -d /tmp/frontier-site-e2e.XXXXXXXX)"; chmod 700 "$T"; PORT=$((20000 + RANDOM % 20000))
export FRONTIER_PG_ROOT="$T" FRONTIER_PG_PORT=$((41000 + RANDOM % 2000)) PYTHONPATH="$REPO" OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export FRONTIER_ACCESS_TOKEN="gate-$($PY -c 'import secrets; print(secrets.token_urlsafe(32))')"
WEBPID=""
cleanup() { [ -z "$WEBPID" ] || kill "$WEBPID" 2>/dev/null || true; "$PGBIN/pg_ctl" -D "$T/pgdata" -m immediate -w stop >/dev/null 2>&1 || true; rm -rf -- "$T"; }
trap cleanup EXIT
bash "$REPO/deploy/postgres/init-cluster.sh" "$T" >/dev/null; "$PGBIN/pg_ctl" -D "$T/pgdata" -l "$T/pg.log" -w start >/dev/null
bash "$REPO/deploy/postgres/create-db.sh" "$T" >/dev/null
export FRONTIER_DSN="host=$T/run port=$FRONTIER_PG_PORT dbname=frontier user=frontier_app"
cd "$REPO"; $PY -m frontier.admin bootstrap --namespace site-e2e --schema public >/dev/null
$PY -m frontier.admin provision --namespace site-e2e --actor e2e-writer --operator op-writer --roles contributor,coordinator --credential-file "$T/credentials/writer.cred" >/dev/null
$PY - "$T/credentials/writer.cred" <<'PYE'
import os, sys
from frontier.store import Store
from frontier.seed import seed
store = Store(os.environ["FRONTIER_DSN"], "site-e2e", "public")
n = seed(store, open(sys.argv[1]).read().strip(), "e2e-writer")
print("seeded", len(n) if hasattr(n, "__len__") else n)
PYE
$PY -m frontier.web --namespace site-e2e --schema public --port $PORT --site "$SITE" --insecure-cookies 2>"$T/web.log" & WEBPID=$!
for _ in $(seq 100); do curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break; sleep 0.1; done
$PY "$SITE/../tests/site_live_driver.py" "http://127.0.0.1:$PORT" "$FRONTIER_ACCESS_TOKEN" "$OUT"
