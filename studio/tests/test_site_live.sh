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
if [ "${SITE_E2E_DESIGN:-0}" = "1" ]; then
$PY - "$T/credentials/writer.cred" <<'PYE'
import os, sys
from frontier.store import Store
store = Store(os.environ["FRONTIER_DSN"], "site-e2e", "public"); tok = open(sys.argv[1]).read().strip()
claim = store.search(kind="Claim", limit=1, token=tok)["results"][0]["ref"]
src = {"uri": "https://example.org/e2e", "locator": "e2e", "source_version": "v1", "content_sha256": "a" * 64, "content_available": False, "access": "public reference, unavailable bytes", "license": "CC0-1.0"}
proj = {"namespace": "site-e2e", "kind": "Project", "id": "project-flying-fish-mission", "issuer": "e2e-writer", "source_uri": "urn:e2e", "payload": {"title": "E2E mission", "mission": "Exercise the design review surface.", "source": src, "limitations": ["E2E fixture; no biological conclusion."], "scale_coverage": [{"scale": "organism", "status": "unknown", "note": "e2e"}], "members": [{"ref": claim, "role": "subsystem", "subsystem": "fin ray model", "scale": "organism", "relationship": "informs", "applicability": "Declared scope only.", "rationale": "E2E pin."}], "requirements": [], "open_questions": []}}
pref = store.submit(tok, "e2e-project", proj)["record"]; pref = {k: pref[k] for k in ("namespace", "kind", "id", "version")}
ch = {"namespace": "site-e2e", "kind": "Annotation", "id": "e2e-challenge", "issuer": "e2e-writer", "source_uri": "urn:e2e", "payload": {"kind": "challenge", "body": "E2E: a static measurement is assumed to hold under loading.", "anchor": {"record": pref}, "design_review": {"dimension": "biology", "member_index": 0, "evidence_basis": "assumption", "scope": "The pinned member only.", "evidence_refs": [], "alternative": "Depends on strain rate.", "falsifiable_next_test": "Cyclic loading vs static."}}}
cref = store.submit(tok, "e2e-challenge", ch)["record"]; cref = {k: cref[k] for k in ("namespace", "kind", "id", "version")}
rp = {"namespace": "site-e2e", "kind": "Annotation", "id": "e2e-reply", "issuer": "e2e-writer", "source_uri": "urn:e2e", "payload": {"kind": "comment", "body": "E2E reply: which fin?", "anchor": {"record": pref}, "reply_to": cref}}
store.submit(tok, "e2e-reply", rp)
print("design seeded", pref["version"][:12])
PYE
fi
PUBLIC=""; [ "${SITE_E2E_PUBLIC:-0}" = "1" ] && PUBLIC="--public-read"
$PY -m frontier.web --namespace site-e2e --schema public --port $PORT --site "$SITE" --insecure-cookies $PUBLIC 2>"$T/web.log" & WEBPID=$!
for _ in $(seq 100); do curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break; sleep 0.1; done
$PY "$SITE/../tests/${SITE_E2E_DRIVER:-site_live_driver.py}" "http://127.0.0.1:$PORT" "$FRONTIER_ACCESS_TOKEN" "$OUT" "${SITE_E2E_PUBLIC:-0}"
