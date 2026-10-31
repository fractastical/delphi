#!/usr/bin/env bash
# Run AFTER the instance is started. Idempotent: creates the least-privilege role and the `frontier` database inside THIS instance only.
set -euo pipefail
ROOT="${1:-${FRONTIER_PG_ROOT:-/data/services/delphi-frontier}}"
PGBIN="${FRONTIER_PG_BIN:-/usr/lib/postgresql/16/bin}"
PORT="${FRONTIER_PG_PORT:-5471}"
psqlx() { "$PGBIN/psql" -X -q -v ON_ERROR_STOP=1 -h "$ROOT/run" -p "$PORT" -d postgres "$@"; }
[ -n "$(psqlx -Atc "SELECT 1 FROM pg_roles WHERE rolname = 'frontier_app'")" ] ||
  psqlx -c "CREATE ROLE frontier_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 30"
[ -n "$(psqlx -Atc "SELECT 1 FROM pg_database WHERE datname = 'frontier'")" ] ||
  psqlx -c "CREATE DATABASE frontier OWNER frontier_app ENCODING 'UTF8' TEMPLATE template0"
psqlx -c "REVOKE ALL ON DATABASE frontier FROM PUBLIC"
echo "role frontier_app and database frontier ready (DSN: host=$ROOT/run port=$PORT dbname=frontier user=frontier_app)"
