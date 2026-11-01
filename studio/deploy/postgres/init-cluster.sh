#!/usr/bin/env bash
# Dedicated PostgreSQL 16 INSTANCE for Delphi Frontier: its own data directory, socket directory and configuration under ONE root.
# Unix-socket only (no TCP listener), private mode-700 directories, peer authentication. Idempotent. It does not start, install, enable or
# stop anything, and it never touches another cluster (no pg_createcluster, no /var/lib/postgresql, no port 5xxx listener).
#
#   bash deploy/postgres/init-cluster.sh [ROOT]          default ROOT=/data/services/delphi-frontier
#   FRONTIER_PG_BIN overrides /usr/lib/postgresql/16/bin
set -euo pipefail
ROOT="${1:-${FRONTIER_PG_ROOT:-/data/services/delphi-frontier}}"
PGBIN="${FRONTIER_PG_BIN:-/usr/lib/postgresql/16/bin}"
PORT="${FRONTIER_PG_PORT:-5471}"       # only names the socket file (.s.PGSQL.$PORT); nothing listens on a TCP port
OSUSER="$(id -un)"
test "$(id -u)" != 0 || { echo 'run as an unprivileged service user' >&2; exit 2; }
DATA="$ROOT/pgdata"; RUN="$ROOT/run"
umask 077
# Never adopt something that is not ours: a pre-existing, non-empty ROOT or a data directory without our marker is refused untouched.
if [ -e "$ROOT" ] && [ ! -f "$ROOT/.frontier-instance" ] && [ -n "$(ls -A "$ROOT" 2>/dev/null | grep -vx app)" ]; then
  echo "refusing: $ROOT exists, is not empty (other than an app/ checkout) and is not a Frontier instance (no .frontier-instance marker); nothing changed" >&2; exit 3
fi
if [ -f "$DATA/PG_VERSION" ] && [ ! -f "$ROOT/.frontier-instance" ]; then
  echo "refusing: $DATA is an existing cluster that this script did not create; nothing changed" >&2; exit 3
fi
mkdir -p "$ROOT" "$RUN" "$ROOT/backups" "$ROOT/credentials"
chmod 700 "$ROOT" "$RUN" "$ROOT/backups" "$ROOT/credentials"
if [ ! -f "$DATA/PG_VERSION" ]; then
  "$PGBIN/initdb" -D "$DATA" --auth-local=peer --auth-host=reject --no-locale --encoding=UTF8 >/dev/null
  echo "created by deploy/postgres/init-cluster.sh" > "$ROOT/.frontier-instance"
fi
chmod 700 "$DATA"
conf="$DATA/postgresql.conf"
sed -i '/^# BEGIN frontier-managed/,/^# END frontier-managed/d' "$conf"
cat >> "$conf" <<CONF
# BEGIN frontier-managed
listen_addresses = ''
port = $PORT
unix_socket_directories = '$RUN'
unix_socket_permissions = 0700
max_connections = 40
superuser_reserved_connections = 3
shared_buffers = 256MB
work_mem = 8MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB
max_worker_processes = 4
max_parallel_workers = 2
max_parallel_workers_per_gather = 1
wal_level = replica
fsync = on
synchronous_commit = on
full_page_writes = on
password_encryption = scram-sha-256
logging_collector = off
log_connections = off
log_disconnections = off
log_statement = 'none'
log_min_duration_statement = -1
log_line_prefix = '%m [%p] '
# END frontier-managed
CONF
# Peer authentication over the private socket only: the OS user maps to the least-privilege application role. No password exists anywhere.
cat > "$DATA/pg_hba.conf" <<HBA
# managed by deploy/postgres/init-cluster.sh
local   frontier   frontier_app   peer map=frontier
local   all        $OSUSER        peer
HBA
cat > "$DATA/pg_ident.conf" <<IDENT
# managed by deploy/postgres/init-cluster.sh
frontier   $OSUSER   frontier_app
IDENT
chmod 600 "$DATA/pg_hba.conf" "$DATA/pg_ident.conf"
echo "frontier PostgreSQL instance prepared at $ROOT (socket $RUN/.s.PGSQL.$PORT); nothing started"
