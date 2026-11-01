"""Fresh-venv application probe; no Docker admission or production access."""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def probe(root, restored, source, source_sha):
    root, restored, source = map(Path, (root, restored, source))
    if Path(sys.prefix) != root / 'venv' or sys.prefix == sys.base_prefix:
        raise ValueError('Probe requires the newly created application virtual environment')
    python = Path(sys.executable)
    children = []
    token = None
    suffix = secrets.token_hex(5)
    receipt = {'schema': 'frontier.isolated-application-probe/1', 'success': False, 'checks': {},
               'runtime': {'python': sys.version.split()[0], 'venv': sys.prefix,
                           'isolated_mode': sys.flags.isolated}}
    def stop_signal(*_):
        raise SystemExit('Probe deadline')
    signal.signal(signal.SIGTERM, stop_signal)
    try:
        import psycopg
        from psycopg import sql
        from frontier.store import Store
        import frontier.store
        import mcp
        import typing_extensions
        receipt['runtime']['module_paths'] = {name: module.__file__ for name, module in
            [('frontier.store', frontier.store), ('psycopg', psycopg), ('mcp', mcp), ('typing_extensions', typing_extensions)]}
        if not all(Path(value).resolve().is_relative_to((root / 'venv').resolve())
                   for value in receipt['runtime']['module_paths'].values()):
            raise ValueError('Ambient Python package escaped venv isolation')
        receipt['runtime']['package_versions'] = {name: importlib.metadata.version(name)
            for name in ['psycopg', 'pydantic', 'mcp', 'typing_extensions', 'anyio']}
        expected = json.loads((restored / 'database/database-receipt.json').read_text())['sanitized_table_counts']
        dsn = f'host={root / "sock"} port=5432 dbname=frontier user=frontier_recovery'
        with psycopg.connect(dsn) as conn:
            tables = [x[0] for x in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
            counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
            if counts != expected or conn.execute('SELECT count(*) FROM action_state WHERE lease_id IS NOT NULL').fetchone()[0]:
                raise ValueError('Restored database counts or sanitized leases differ')
            namespace = conn.execute('SELECT namespace FROM node_config').fetchone()[0]
            extensions = dict(conn.execute('SELECT extname,extversion FROM pg_extension ORDER BY extname').fetchall())
            if extensions != {'plpgsql': '1.0', 'vector': '0.6.0'}:
                raise ValueError('Required restored database extension versions differ')
            receipt['postgres_extensions'] = extensions
        receipt['checks']['all18_counts_and_sanitized_leases'] = True
        receipt['table_counts_before_disposable_write'] = counts
        token = secrets.token_urlsafe(48)
        actor = 'recovery-' + suffix
        Store(dsn, namespace).provision(token, actor, 'recovery-operator', ['contributor'], [namespace], 10)
        ports = {'web': free_port(), 'mcp': free_port()}
        while ports['mcp'] == ports['web']:
            ports['mcp'] = free_port()
        env = {'PATH': os.environ.get('PATH', os.defpath), 'FRONTIER_DSN': dsn,
               'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
               'PYTHONDONTWRITEBYTECODE': '1'}
        commands = {
            'web': [python, '-m', 'frontier.web', '--namespace', namespace, '--public-read', '--port', str(ports['web'])],
            'mcp': [python, '-m', 'frontier', 'mcp', '--namespace', namespace, '--allow-write', '--transport', 'http', '--mcp-port', str(ports['mcp'])]}
        for name, argv in commands.items():
            stream = (root / (name + '.log')).open('wb')
            proc = subprocess.Popen(list(map(str, argv)), cwd=source, env=env, stdout=stream, stderr=stream)
            children.append((proc, stream))
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError('Restored ' + name + ' exited before listening')
                try:
                    with socket.create_connection(('127.0.0.1', ports[name]), 0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Restored ' + name + ' did not listen')
        for path in ('/api/health', '/api/catalog?limit=1'):
            with urllib.request.urlopen(f'http://127.0.0.1:{ports["web"]}' + path, timeout=30) as response:
                body = json.load(response)
            if path == '/api/health' and body.get('status') != 'ok':
                raise ValueError('Restored health failed')
            if path.startswith('/api/catalog') and not body.get('results'):
                raise ValueError('Restored catalog unexpectedly empty')
        receipt['checks']['loopback_web_health_and_catalog'] = True

        async def exercise():
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
            from frontier.models import ref
            def value(result):
                if result.isError:
                    raise ValueError('MCP recovery operation failed')
                return json.loads(result.content[0].text)
            draft = {'namespace': namespace, 'kind': 'Claim', 'id': actor, 'issuer': actor,
                'visibility': 'private', 'source_uri': 'urn:frontier:disposable-recovery-check',
                'payload': {'title': 'Disposable software recovery check',
                    'statement': 'This record exercises restored authentication and round-trip only.',
                    'context': 'Isolated recovery database; not scientific evidence',
                    'assumptions': ['Disposable software fixture'], 'limitations': ['No biological claim'],
                    'source': {'uri': 'urn:frontier:disposable-recovery-check', 'locator': None,
                        'source_version': source_sha, 'content_sha256': None, 'content_available': False,
                        'access': 'Software protocol fixture', 'license': None}}}
            async with httpx.AsyncClient(headers={'Authorization': 'Bearer ' + token}, timeout=30) as http:
                async with streamable_http_client(f'http://127.0.0.1:{ports["mcp"]}/mcp', http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        caps = value(await client.call_tool('frontier_capabilities', {}))
                        if caps['principal']['actor'] != actor:
                            raise ValueError('Restored principal identity differs')
                        args = {'draft': draft, 'idempotency_key': actor}
                        first = value(await client.call_tool('frontier_propose', args))
                        second = value(await client.call_tool('frontier_propose', args))
                        if first['record']['version'] != second['record']['version']:
                            raise ValueError('Idempotent retry changed version')
                        got = value(await client.call_tool('frontier_get', {'target': ref(first['record'])}))
                        if got['record']['id'] != actor or got['record']['issuer'] != actor:
                            raise ValueError('Authenticated round-trip differs')
            receipt['checks']['official_mcp_authenticated_private_write_read_and_idempotency'] = True
        asyncio.run(asyncio.wait_for(exercise(), timeout=90))
        request = urllib.request.Request(f'http://127.0.0.1:{ports["mcp"]}/mcp', data=b'{}',
            headers={'Authorization': 'Bearer invalid-disposable-credential-0000', 'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request, timeout=10)
            raise ValueError('Invalid bearer was not rejected')
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise ValueError('Expected401 for invalid bearer') from None
        receipt['checks']['invalid_bearer_refused401'] = True
        if any(token.encode() in p.read_bytes() for p in root.glob('*.log')):
            raise ValueError('Fresh credential appeared in service log')
        receipt['checks']['fresh_credential_not_logged'] = True
        receipt['loopback_ports'] = ports
        receipt['success'] = True
    except BaseException as error:
        receipt['failure_type'] = type(error).__name__
        raise
    finally:
        for proc, stream in children:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            stream.close()
        receipt['owned_app_children_stopped'] = all(proc.poll() is not None for proc, _ in children)
        if token is not None and any(token.encode() in p.read_bytes() for p in root.glob('*.log')):
            receipt['success'] = False
            receipt['checks']['fresh_credential_not_logged'] = False
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (root / 'application-probe-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not receipt['success']:
        raise ValueError('Application probe did not pass')
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'restored', 'source', 'source-sha'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    print(json.dumps(probe(a.root, a.restored, a.source, a.source_sha)))
