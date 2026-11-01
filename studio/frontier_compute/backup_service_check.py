"""Exercise restored source/data on a separate host; owned socket-only PG16 and loopback apps."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import site
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def check(restored, root, source_sha, dump_sha, video_sha):
    if os.environ.get('FRONTIER_RECOVERY_CHECK_RUNNING'):
        raise ValueError('Nested recovery check refused')
    os.environ['FRONTIER_RECOVERY_CHECK_RUNNING'] = '1'
    if not re.fullmatch('[0-9a-f]{40}', source_sha) or not all(
            re.fullmatch('[0-9a-f]{64}', x) for x in (dump_sha, video_sha)):
        raise ValueError('Exact source/dump/video hashes required')
    root, restored = Path(root).resolve(), Path(restored).resolve(strict=True)
    if root.exists() or len(str(root / 'sock')) > 85:
        raise ValueError('New short private check root required')
    dump = restored / 'database/frontier-restore-sanitized.dump'
    if sha(dump) != dump_sha:
        raise ValueError('Recovered dump hash mismatch')
    os.umask(0o077)
    root.mkdir(mode=0o700, parents=True)
    receipt = {'schema': 'frontier.separate-host-service-recovery/1',
               'started_utc': datetime.now(timezone.utc).isoformat(),
               'source_sha': source_sha, 'recovered_dump_sha256': dump_sha,
               'archive_sha256': json.loads((restored / 'restore-receipt.json').read_text())['archive_sha256'],
               'checker_source_sha256': sha(__file__),
               'operations': [], 'checks': {}, 'cleanup': {}, 'success': False,
               'scope': 'Disposable separate-host recovery only. No public-domain cutover or unrelated service changes.'}
    children, container_started = [], False
    suffix = secrets.token_hex(5)
    container = 'frontier-recovery-' + suffix
    expire_unit = 'frontier-recovery-expire-' + suffix

    def save():
        (root / 'service-recovery-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def run(stage, argv, *, input_file=None, cwd=None, timeout=600):
        with (root / (stage + '.stdout')).open('wb') as out, (root / (stage + '.stderr')).open('wb') as err:
            stream = open(input_file, 'rb') if input_file else subprocess.DEVNULL
            try:
                try:
                    result = subprocess.run(list(map(str, argv)), stdin=stream, stdout=out, stderr=err,
                                            cwd=cwd, timeout=timeout)
                except (OSError, subprocess.TimeoutExpired) as error:
                    receipt['operations'].append({'stage': stage, 'argv': list(map(str, argv)),
                                                  'exit_code': None, 'error': type(error).__name__})
                    save()
                    raise
            finally:
                if input_file:
                    stream.close()
        receipt['operations'].append({'stage': stage, 'argv': list(map(str, argv)), 'exit_code': result.returncode})
        save()
        if result.returncode:
            raise RuntimeError('Recovery stage failed: ' + stage)
        return (root / (stage + '.stdout')).read_text()

    def stop_signal(*_):
        raise SystemExit('Recovery check stopped by deadline')

    signal.signal(signal.SIGTERM, stop_signal)
    try:
        source = root / 'source'
        run('source_clone', ['git', 'clone', '--no-checkout', restored / 'metadata/frontier-all-refs.bundle', source])
        run('source_checkout', ['git', 'checkout', '--detach', source_sha], cwd=source)
        actual_sha = run('source_identity', ['git', 'rev-parse', 'HEAD'], cwd=source).strip()
        if actual_sha != source_sha or sha(source / 'artifacts/demo-video-90/frontier-90s.mp4') != video_sha:
            raise ValueError('Restored deployed source/video identity mismatch')
        receipt['checks']['source_and_final_video_hashes'] = True
        venv = root / 'venv'
        run('venv_create', [sys.executable, '-m', 'venv', venv])
        python = venv / 'bin/python'
        run('dependencies_install', [python, '-m', 'pip', '--disable-pip-version-check', 'install', '--no-input', source])
        run('dependency_versions', [python, '-m', 'pip', 'freeze'])
        receipt['python_version'] = run('python_version', [python, '--version']).strip()
        for lib in (venv / 'lib').glob('python*/site-packages'):
            site.addsitedir(str(lib))
        run('postgres_image_pull', ['docker', 'pull', 'postgres:16-bookworm'], timeout=300)
        receipt['postgres_image_digest'] = run('postgres_image_identity', [
            'docker', 'image', 'inspect', 'postgres:16-bookworm', '--format', '{{index .RepoDigests 0}}']).strip()
        for name in ('pgdata', 'sock'):
            (root / name).mkdir(mode=0o700)
        run('postgres_start', ['docker', 'run', '--detach', '--rm', '--name', container,
            '--label', 'frontier.recovery.check=' + suffix, '--network', 'none',
            '--user', f'{os.getuid()}:{os.getgid()}', '--cpus', '1', '--memory', '1g',
            '--memory-swap', '1g', '--pids-limit', '128', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
            '--mount', f'type=bind,src={root / "pgdata"},dst=/var/lib/postgresql/data',
            '--mount', f'type=bind,src={root / "sock"},dst=/var/run/postgresql',
            '--env', 'POSTGRES_USER=frontier_recovery', '--env', 'POSTGRES_DB=frontier',
            '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:16-bookworm',
            '-c', 'listen_addresses=', '-c', 'unix_socket_permissions=0700', '-c', 'shared_buffers=128MB'])
        container_started = True
        run('independent_expiry', ['systemd-run', '--user', '--unit', expire_unit, '--on-active=15m',
                                  '/usr/bin/docker', 'stop', '--time', '5', container])
        for _ in range(60):
            ready = subprocess.run(['docker', 'exec', container, 'pg_isready', '-U', 'frontier_recovery'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Owned PostgreSQL did not become ready')
        receipt['postgres_version'] = run('postgres_version', ['docker', 'exec', container, 'postgres', '--version']).strip()
        run('pg_restore', ['docker', 'exec', '-i', container, 'pg_restore', '--no-owner', '--no-acl',
                          '--exit-on-error', '-U', 'frontier_recovery', '-d', 'frontier'], input_file=dump)
        import psycopg
        from psycopg import sql
        from frontier.store import Store
        expected = json.loads((restored / 'database/database-receipt.json').read_text())['sanitized_table_counts']
        dsn = f'host={root / "sock"} port=5432 dbname=frontier user=frontier_recovery'
        with psycopg.connect(dsn) as conn:
            tables = [x[0] for x in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
            counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
            if counts != expected or conn.execute('SELECT count(*) FROM action_state WHERE lease_id IS NOT NULL').fetchone()[0]:
                raise ValueError('Restored database counts or sanitized leases differ')
            namespace = conn.execute('SELECT namespace FROM node_config').fetchone()[0]
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
        receipt['failure_stage'] = receipt['operations'][-1]['stage'] if receipt['operations'] else 'preparation'
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
        receipt['cleanup']['owned_app_children_stopped'] = all(proc.poll() is not None for proc, _ in children)
        if container_started:
            label = subprocess.run(['docker', 'inspect', container, '--format', '{{index .Config.Labels "frontier.recovery.check"}}'], capture_output=True, text=True, timeout=15)
            if label.returncode == 0 and label.stdout.strip() == suffix:
                stop = subprocess.run(['docker', 'stop', '--time', '5', container], capture_output=True, timeout=30)
                receipt['cleanup']['owned_container_stop_exit'] = stop.returncode
                if stop.returncode == 0:
                    subprocess.run(['systemctl', '--user', 'stop', expire_unit + '.timer'], capture_output=True, timeout=15)
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('restored', 'root', 'source-sha', 'dump-sha', 'video-sha'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--archive')
    p.add_argument('--identity')
    a = p.parse_args()
    if bool(a.archive) != bool(a.identity):
        p.error('--archive and --identity must be supplied together')
    if a.archive:
        from frontier_compute.backup import restore_snapshot
        restore_snapshot(a.archive, a.identity, a.restored)
    print(json.dumps(check(a.restored, a.root, a.source_sha, a.dump_sha, a.video_sha)))
