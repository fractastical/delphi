"""Transactional read-only dump; credential invalidation occurs only in a new scratch cluster."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


def run(argv, **kw):
    return subprocess.run(list(map(str, argv)), capture_output=True, text=True, check=True, timeout=600, **kw)


def capture(destination, *, socket='/data/services/delphi-frontier/run', port=5471):
    import psycopg
    from psycopg import sql

    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Database backup destination must be new')
    destination.mkdir(mode=0o700, parents=True)
    os.umask(0o077)
    pg = Path('/usr/lib/postgresql/16/bin')
    raw = destination / 'frontier-raw-private.dump'
    operations = []

    def execute(stage, argv):
        result = run(argv)
        operations.append({'stage': stage, 'exit_code': result.returncode, 'completed_utc': datetime.now(timezone.utc).isoformat()})
        return result
    with psycopg.connect(host=socket, port=port, user='frontier_app', dbname='frontier', autocommit=True) as connection:
        connection.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        snapshot = connection.execute('SELECT pg_export_snapshot()').fetchone()[0]
        tables = [r[0] for r in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        counts = {name: connection.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
        private = connection.execute("SELECT visibility,count(*) FROM record_versions GROUP BY visibility").fetchall()
        extensions = dict(connection.execute('SELECT extname,extversion FROM pg_extension ORDER BY extname').fetchall())
        execute('source_pg_dump', [pg / 'pg_dump', '-h', socket, '-p', port, '-U', 'frontier_app', '-Fc', '--snapshot', snapshot, '-f', raw, 'frontier'])
        connection.execute('ROLLBACK')
    cluster, unix = destination / 'scratch-cluster', destination / 'scratch-socket'
    unix.mkdir(mode=0o700)
    execute('scratch_initdb', [pg / 'initdb', '-D', cluster, '--auth=trust', '--no-locale', '--encoding=UTF8', '-U', 'frontier_backup'])
    started = False
    try:
        execute('scratch_start', [pg / 'pg_ctl', '-D', cluster, '-l', destination / 'scratch-postgres.log', '-o', f"-k {unix} -p 5549 -h ''", '-w', 'start'])
        started = True
        execute('scratch_createdb', [pg / 'createdb', '-h', unix, '-p', 5549, '-U', 'frontier_backup', 'frontier_restore'])
        execute('scratch_pg_restore', [pg / 'pg_restore', '-h', unix, '-p', 5549, '-U', 'frontier_backup', '-d', 'frontier_restore', '--no-owner', '--no-acl', '--exit-on-error', raw])
        with psycopg.connect(host=str(unix), port=5549, user='frontier_backup', dbname='frontier_restore') as connection:
            actual = Path(connection.execute('SHOW data_directory').fetchone()[0]).resolve()
            if actual != cluster.resolve() or connection.info.dbname != 'frontier_restore':
                raise ValueError('Refusing sanitization outside isolated scratch cluster')
            restored = {name: connection.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
            if counts != restored:
                raise ValueError('Raw logical dump did not reproduce source snapshot counts')
            scientific_before = connection.execute("SELECT md5(string_agg(version || md5(envelope::text),'' ORDER BY version)) FROM record_versions").fetchone()[0]
            leases = connection.execute('SELECT count(*) FROM action_state WHERE lease_id IS NOT NULL').fetchone()[0]
            connection.execute('TRUNCATE public.principals,public.idempotency')
            connection.execute("UPDATE action_state SET state=CASE WHEN state IN ('leased','running') THEN 'expired' ELSE state END,lease_id=NULL,lease_actor=NULL,lease_operator=NULL,lease_until=NULL")
            scientific_after = connection.execute("SELECT md5(string_agg(version || md5(envelope::text),'' ORDER BY version)) FROM record_versions").fetchone()[0]
            if scientific_before != scientific_after:
                raise ValueError('Scientific records changed during operational credential sanitization')
            sanitized_counts = {name: connection.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
            connection.commit()
        clean = destination / 'frontier-restore-sanitized.dump'
        execute('sanitized_pg_dump', [pg / 'pg_dump', '-h', unix, '-p', 5549, '-U', 'frontier_backup', '-Fc', '-f', clean, 'frontier_restore'])
        receipt = {'schema': 'frontier.logical-backup/1', 'captured_utc': datetime.now(timezone.utc).isoformat(),
                   'source_socket': socket, 'source_port': port, 'source_access': 'Repeatable-read read-only exported snapshot',
                   'table_counts': counts, 'private_record_counts': dict(private), 'raw_restore_counts_identical': True,
                   'postgres_extensions': extensions,
                   'sanitized_table_counts': sanitized_counts, 'leases_invalidated': leases,
                   'sanitization': 'Scratch only: principals and idempotency response cache removed; lease fields cleared and leased/running actions marked expired. Scientific record versions/envelopes unchanged.',
                   'record_envelope_before_after_digest_identical': True,
                   'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()} for p in [raw,clean]},
                   'operation_returncodes': operations,
                   'classification': 'Raw dump is private forensic material and must only leave host encrypted; sanitized dump still contains private scientific records and is not public.'}
        (destination / 'database-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    finally:
        if started:
            run([pg / 'pg_ctl', '-D', cluster, '-m', 'fast', '-w', 'stop'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.destination)))
