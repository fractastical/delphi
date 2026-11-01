#!/usr/bin/env bash
# Run only through the documented bounded systemd scope. Own cluster, private socket.
set -euo pipefail
test -n "${INVOCATION_ID:-}" || { echo 'Run in the documented systemd scope.' >&2; exit 2; }
test "$(id -u)" != 0 || { echo 'Run initdb as an unprivileged user.' >&2; exit 2; }
frontier_pg_bin="${FRONTIER_PG_BIN:-/usr/lib/postgresql/16/bin}"
frontier_tmp="$(mktemp -d /tmp/frontier-pg.XXXXXXXX)"
chmod 700 "$frontier_tmp"
cleanup() {
  "$frontier_pg_bin/pg_ctl" -D "$frontier_tmp/data" -m immediate -w stop >/dev/null 2>&1 || true
  rm -rf -- "$frontier_tmp"
}
trap cleanup EXIT INT TERM
mkdir "$frontier_tmp/socket"
"$frontier_pg_bin/initdb" -D "$frontier_tmp/data" --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8 > "$frontier_tmp/init.log"
"$frontier_pg_bin/pg_ctl" -D "$frontier_tmp/data" -l "$frontier_tmp/postgres.log" -o "-k $frontier_tmp/socket -c listen_addresses='' -c max_connections=20 -c shared_buffers=32MB -c max_worker_processes=2 -c max_parallel_workers=2" -w start >/dev/null
export FRONTIER_TEST_DSN="host=$frontier_tmp/socket dbname=postgres"
export FRONTIER_TEST_PG_DATA="$frontier_tmp/data"
export FRONTIER_TEST_PG_BIN="$frontier_pg_bin"
export FRONTIER_TEST_PG_LOG="$frontier_tmp/postgres.log"
python -m pytest -q "$@"
