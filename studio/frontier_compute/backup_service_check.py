"""Exercise restored source/data on a separate host; owned socket-only PG16 and loopback apps."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import time

PG_IMAGE = 'pgvector/pgvector:0.6.0-pg16'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


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
    container_started = False
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
        run('postgres_image_pull', ['docker', 'pull', PG_IMAGE], timeout=300)
        receipt['postgres_image_digest'] = run('postgres_image_identity', [
            'docker', 'image', 'inspect', PG_IMAGE, '--format', '{{index .RepoDigests 0}}']).strip()
        for name in ('pgdata', 'sock'):
            (root / name).mkdir(mode=0o700)
        run('postgres_start', ['docker', 'run', '--detach', '--name', container,
            '--label', 'frontier.recovery.check=' + suffix, '--network', 'none',
            '--user', f'{os.getuid()}:{os.getgid()}', '--cpus', '1', '--memory', '1g',
            '--memory-swap', '1g', '--pids-limit', '128', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
            '--mount', f'type=bind,src={root / "pgdata"},dst=/var/lib/postgresql/data',
            '--mount', f'type=bind,src={root / "sock"},dst=/var/run/postgresql',
            '--env', 'POSTGRES_USER=frontier_recovery', '--env', 'POSTGRES_DB=frontier',
            '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', PG_IMAGE,
            '-c', 'listen_addresses=', '-c', 'unix_socket_permissions=0700', '-c', 'shared_buffers=128MB'])
        container_started = True
        run('independent_expiry', ['systemd-run', '--user', '--unit', expire_unit, '--on-active=15m',
                                  '/usr/bin/docker', 'stop', '--time', '5', container])
        for _ in range(60):
            # The entrypoint briefly starts a temporary initialization server. Require final PID1.
            ready = subprocess.run(['docker', 'exec', container, 'sh', '-c',
                                   'test "$(head -n 1 /var/lib/postgresql/data/postmaster.pid 2>/dev/null)" = 1 && pg_isready -U frontier_recovery -d frontier'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Owned PostgreSQL did not become ready')
        receipt['postgres_version'] = run('postgres_version', ['docker', 'exec', container, 'postgres', '--version']).strip()
        run('pg_restore', ['docker', 'exec', '-i', container, 'pg_restore', '--no-owner', '--no-acl',
                          '--exit-on-error', '-U', 'frontier_recovery', '-d', 'frontier'], input_file=dump)
        probe_file = Path(__file__).with_name('backup_service_probe.py')
        receipt['probe_source_sha256'] = sha(probe_file)
        run('application_probe', [python, '-I', probe_file, '--root', root, '--restored', restored,
                                  '--source', source, '--source-sha', source_sha], timeout=300)
        probe = json.loads((root / 'application-probe-receipt.json').read_text())
        receipt['checks'].update(probe['checks'])
        receipt['application_probe'] = probe
        receipt['success'] = probe['success']
    except BaseException as error:
        receipt['failure_type'] = type(error).__name__
        receipt['failure_stage'] = receipt['operations'][-1]['stage'] if receipt['operations'] else 'preparation'
        raise
    finally:
        probe_receipt = root / 'application-probe-receipt.json'
        receipt['cleanup']['owned_app_children_stopped'] = (
            json.loads(probe_receipt.read_text()).get('owned_app_children_stopped')
            if probe_receipt.exists() else None)
        if container_started:
            label = subprocess.run(['docker', 'inspect', container, '--format', '{{index .Config.Labels "frontier.recovery.check"}}'], capture_output=True, text=True, timeout=15)
            if label.returncode == 0 and label.stdout.strip() == suffix:
                stop = subprocess.run(['docker', 'stop', '--time', '5', container], capture_output=True, timeout=30)
                receipt['cleanup']['owned_container_stop_exit'] = stop.returncode
                with (root / 'postgres-container.log').open('wb') as stream:
                    logs = subprocess.run(['docker', 'logs', container], stdout=stream, stderr=stream, timeout=15)
                receipt['cleanup']['postgres_logs_exit'] = logs.returncode
                if stop.returncode == 0:
                    removed = subprocess.run(['docker', 'rm', container], capture_output=True, timeout=15)
                    receipt['cleanup']['owned_container_remove_exit'] = removed.returncode
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
