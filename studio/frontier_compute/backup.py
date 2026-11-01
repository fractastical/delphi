"""Bounded, content-addressed encrypted snapshots; no plaintext off-host payloads."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import tempfile

EXCLUDED_PARTS = {'.git', '.venv', '.local', '__pycache__', '.pytest_cache',
                  'node_modules', 'pgdata', 'credentials', 'secrets',
                  'upload-capabilities', '_inject', '_dry', 'depot', 'toolchain', 'scratch-cluster', 'scratch-socket'}
EXCLUDED_SUFFIXES = ('.token', '.pem', '.key', '.pyc', '.sock', '.pid')


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def safe_relative(name):
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or '\\' in name or '\x00' in name
            or any(x in ('', '.', '..') for x in name.split('/'))):
        raise ValueError('Unsafe snapshot path')
    return p


def exclusion(relative):
    p = safe_relative(relative)
    for part in p.parts:
        if part in EXCLUDED_PARTS or part.startswith('.venv') or part.endswith('-deps'):
            return 'credential/runtime injection or rebuildable cache directory'
        if part == '.env' or part.startswith('.env.'):
            return 'environment credential file'
    if p.name.endswith(EXCLUDED_SUFFIXES):
        return 'private credential or ephemeral process file'
    return None


def files_for_root(root, label):
    root = Path(root).resolve(strict=True)
    safe_relative(label)
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            path = parent / name
            relative = path.relative_to(root).as_posix()
            reason = exclusion(relative)
            if reason or path.is_symlink():
                dirs.remove(name)
                yield None, label + '/' + relative, reason or 'symlink directory'
        for name in sorted(files):
            path = parent / name
            relative = path.relative_to(root).as_posix()
            reason = exclusion(relative)
            if path.is_symlink():
                reason = 'symlink file'
            elif not path.is_file():
                reason = 'nonregular file'
            yield (None if reason else path), label + '/' + relative, reason


def stable_copy(source, destination, max_bytes):
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream, Path(destination).open('wb') as target:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise ValueError('Source file is not regular or exceeds snapshot bound')
        h, size = hashlib.sha256(), 0
        while block := stream.read(min(1 << 20, max_bytes + 1 - size)):
            size += len(block)
            if size > max_bytes:
                raise ValueError('Growing source exceeds snapshot bound')
            h.update(block)
            target.write(block)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Source changed during capture')
        if size != before.st_size:
            raise ValueError('Source byte count changed')
    return {'sha256': h.hexdigest(), 'bytes': size, 'mode': before.st_mode & 0o777,
            'mtime_ns': before.st_mtime_ns}


def add_bytes(archive, name, data):
    info = tarfile.TarInfo(name)
    info.size, info.mode = len(data), 0o600
    archive.addfile(info, io.BytesIO(data))


def configured_files(config):
    for root in config['roots']:
        yield from files_for_root(root['path'], root['label'])
    for row in config.get('files', []):
        logical = row['logical']
        safe_relative(logical)
        reason = exclusion(logical)
        path = Path(row['path'])
        if path.is_symlink():
            reason = 'symlink file'
        elif not path.is_file():
            reason = ('Tracked deletion retained in binary patch and source bundle'
                      if row.get('expected_tracked_deletion') and not path.exists()
                      else 'MissingFileError: missing or nonregular selected file')
        yield (None if reason else path), logical, reason


def create_snapshot(config, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Snapshot output must be new')
    output.mkdir(mode=0o700, parents=True)
    os.chmod(output, 0o700)
    recipients = Path(config['recipients']).resolve(strict=True)
    if not 1 <= config['max_total_bytes'] <= 100_000_000_000:
        raise ValueError('Invalid total bound')
    rows, excluded, seen, total = [], [], set(), 0
    manifest = {'schema': 'frontier.encrypted-snapshot/1', 'started_utc': utc(),
                'roots': config['roots'], 'files': rows, 'excluded': excluded,
                'scope': 'Per-file stable capture over a declared window; database dump has its own transactional snapshot. Credentials and runtime capabilities excluded; raw retained logs are encrypted.'}
    encrypted = output / 'snapshot.tar.gz.age'
    with tempfile.TemporaryDirectory(prefix='capture-', dir=output) as scratch:
        process = subprocess.Popen(['age', '--encrypt', '-R', str(recipients), '-o', str(encrypted)],
                                   stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdin, mode='w|gz', compresslevel=1) as archive:
                for source, logical, reason in configured_files(config):
                    if any(part in config.get('deferred_components', []) for part in PurePosixPath(logical).parts):
                        excluded.append({'path': logical, 'reason': 'Deferred until final publication manifest and commit'})
                        continue
                    if source is None:
                        excluded.append({'path': logical, 'reason': reason})
                        continue
                    copy = Path(scratch) / 'file'
                    try:
                        item = stable_copy(source, copy, min(config['max_file_bytes'], config['max_total_bytes'] - total))
                    except (OSError, ValueError) as error:
                        excluded.append({'path': logical, 'reason': type(error).__name__ + ': ' + str(error)[:180]})
                        continue
                    total += item['bytes']
                    if total > config['max_total_bytes']:
                        raise ValueError('Snapshot total byte bound exceeded')
                    if item['sha256'] not in seen:
                        info = tarfile.TarInfo('blobs/' + item['sha256'])
                        info.size, info.mode = item['bytes'], 0o600
                        with copy.open('rb') as incoming:
                            archive.addfile(info, incoming)
                        seen.add(item['sha256'])
                    rows.append({'path': logical, **item})
                manifest.update(finished_utc=utc(), file_count=len(rows), unique_blob_count=len(seen),
                                logical_bytes=total, capture_errors=[x for x in excluded if x['reason'].startswith(('OSError:', 'ValueError:', 'MissingFileError:'))])
                if not rows:
                    raise ValueError('No files captured')
                add_bytes(archive, 'manifest.json', json.dumps(manifest, indent=2).encode())
            process.stdin.close()
            error = process.stderr.read(4096)
            if process.wait(timeout=120) != 0:
                raise RuntimeError('Encryption process failed: ' + error.decode(errors='replace')[:300])
        except BaseException:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=30)
            raise
    receipt = {'schema': 'frontier.encrypted-backup-receipt/1', 'created_utc': utc(),
               'archive': encrypted.name, 'archive_sha256': sha_file(encrypted),
               'archive_bytes': encrypted.stat().st_size, 'file_count': len(rows),
               'unique_blob_count': len(seen), 'logical_bytes': total,
               'excluded_count': len(excluded), 'capture_errors': len(manifest['capture_errors']),
               'recipients_sha256': sha_file(recipients), 'client_encryption': 'age',
               'restorable_verified': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    # Local manifest may describe private records; it is never uploaded unencrypted.
    (output / 'private-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return receipt


def restore_snapshot(encrypted, identity, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Restore destination must be new; existing trees are never overwritten')
    destination.mkdir(mode=0o700, parents=True)
    blobs = destination / '.blobs'
    blobs.mkdir(mode=0o700)
    manifest = None
    restored_blob_bytes = 0
    process = subprocess.Popen(['age', '--decrypt', '-i', str(identity), str(encrypted)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|gz') as archive:
            for member in archive:
                if not member.isfile():
                    raise ValueError('Only regular snapshot members are allowed')
                if member.name == 'manifest.json':
                    if manifest is not None or member.size > 100_000_000:
                        raise ValueError('Invalid snapshot manifest')
                    manifest = json.load(archive.extractfile(member))
                    continue
                parts = safe_relative(member.name).parts
                if len(parts) != 2 or parts[0] != 'blobs' or len(parts[1]) != 64 or any(x not in '0123456789abcdef' for x in parts[1]):
                    raise ValueError('Unexpected snapshot member')
                restored_blob_bytes += member.size
                if restored_blob_bytes > 100_000_000_000:
                    raise ValueError('Restored blob total exceeds bound')
                path = blobs / parts[1]
                if path.exists() or member.size > 20_000_000_000:
                    raise ValueError('Duplicate or oversized snapshot blob')
                with path.open('xb') as target:
                    shutil.copyfileobj(archive.extractfile(member), target, 1 << 20)
                if sha_file(path) != parts[1]:
                    raise ValueError('Restored blob digest mismatch')
        process.stdout.close()
        if process.wait(timeout=120) != 0:
            raise ValueError('Encrypted snapshot authentication failed')
        if not manifest or manifest.get('schema') != 'frontier.encrypted-snapshot/1' or not manifest.get('files'):
            raise ValueError('Missing or invalid manifest')
        paths = set()
        for item in manifest['files']:
            relative = safe_relative(item['path'])
            if relative.parts[0] == '.blobs' or str(relative) in paths:
                raise ValueError('Duplicate or reserved restored path')
            paths.add(str(relative))
            digest = item.get('sha256')
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(x not in '0123456789abcdef' for x in digest)
                    or type(item.get('bytes')) is not int or item['bytes'] < 0):
                raise ValueError('Invalid manifest blob identity')
            source = blobs / digest
            if source.stat().st_size != item['bytes'] or sha_file(source) != item['sha256']:
                raise ValueError('Manifest file bytes do not match blob')
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(item['mode'] & 0o700)
        result = {'schema': 'frontier.backup-restore-check/1', 'verified_utc': utc(),
                  'archive_sha256': sha_file(encrypted), 'files_restored': len(paths),
                  'logical_bytes': sum(x['bytes'] for x in manifest['files']),
                  'capture_errors': manifest.get('capture_errors', []),
                  'source_finished_utc': manifest['finished_utc']}
        (destination / 'restore-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--config', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    restore = sub.add_parser('restore')
    restore.add_argument('--archive', type=Path, required=True)
    restore.add_argument('--identity', type=Path, required=True)
    restore.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = (create_snapshot(json.loads(args.config.read_text()), args.output) if args.command == 'create'
              else restore_snapshot(args.archive, args.identity, args.destination))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
