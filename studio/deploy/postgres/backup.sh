#!/usr/bin/env bash
# Logical backup of the Frontier database into the instance's private backups directory (mode 700, files 600). Keeps the newest 14.
set -euo pipefail
ROOT="${1:-${FRONTIER_PG_ROOT:-/data/services/delphi-frontier}}"
PGBIN="${FRONTIER_PG_BIN:-/usr/lib/postgresql/16/bin}"
PORT="${FRONTIER_PG_PORT:-5471}"
umask 077
out="$ROOT/backups/frontier-$(date -u +%Y%m%dT%H%M%SZ).dump"
"$PGBIN/pg_dump" -h "$ROOT/run" -p "$PORT" -U frontier_app -Fc -f "$out" frontier
ls -1t "$ROOT"/backups/frontier-*.dump | tail -n +15 | xargs -r rm --
echo "wrote $out"
