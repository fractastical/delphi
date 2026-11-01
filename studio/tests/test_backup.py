import json
import subprocess

import pytest

from frontier_compute.backup import configured_files, create_snapshot, exclusion, restore_snapshot, safe_relative, stable_copy


@pytest.mark.parametrize('path', ['credentials/key', 'gcp/upload-capabilities/x.json', 'a/_inject/part-000', '.env', 'a/key.pem', 'a/token.token'])
def test_credentials_and_injected_capabilities_excluded(path):
    assert exclusion(path)


def test_actual_encrypted_roundtrip_and_dedup(tmp_path):
    identity = tmp_path / 'identity'
    subprocess.run(['age-keygen', '-o', str(identity)], capture_output=True, check=True)
    public = subprocess.run(['age-keygen', '-y', str(identity)], capture_output=True, text=True, check=True).stdout
    recipient = tmp_path / 'recipient'
    recipient.write_text(public)
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'evidence.json').write_text('{"observation": "actual fixture"}')
    (source / 'duplicate.json').write_bytes((source / 'evidence.json').read_bytes())
    (source / 'credentials').mkdir()
    (source / 'credentials/secret.token').write_text('MUST_NOT_BE_ARCHIVED')
    (source / 'linked').symlink_to(source / 'evidence.json')
    config = {'recipients': str(recipient), 'roots': [{'label': 'artifacts', 'path': str(source)}],
              'max_total_bytes': 10000, 'max_file_bytes': 1000}
    receipt = create_snapshot(config, tmp_path / 'backup')
    assert receipt['file_count'] == 2 and receipt['unique_blob_count'] == 1
    assert receipt['capture_errors'] == 0
    archive = tmp_path / 'backup/snapshot.tar.gz.age'
    assert b'actual fixture' not in archive.read_bytes()
    result = restore_snapshot(archive, identity, tmp_path / 'restored')
    assert result['files_restored'] == 2
    assert (tmp_path / 'restored/artifacts/evidence.json').read_bytes() == (source / 'evidence.json').read_bytes()
    assert not (tmp_path / 'restored/artifacts/credentials').exists()
    assert not (tmp_path / 'restored/artifacts/linked').exists()
    with pytest.raises(ValueError, match='must be new'):
        restore_snapshot(archive, identity, tmp_path / 'restored')
    manifest = json.loads((tmp_path / 'backup/private-manifest.json').read_text())
    assert any('credentials' in x['path'] for x in manifest['excluded'])


@pytest.mark.parametrize('path', ['../x', '/x', 'a/../../x', 'a\\x', 'a//x'])
def test_restore_path_refuses_traversal(path):
    with pytest.raises(ValueError):
        safe_relative(path)


def test_file_bound_and_link_refused(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'123')
    with pytest.raises(ValueError):
        stable_copy(source, tmp_path / 'copy', 2)
    linked = tmp_path / 'link'
    linked.symlink_to(source)
    with pytest.raises(OSError):
        stable_copy(linked, tmp_path / 'copy', 10)


def test_expected_tracked_deletion_is_distinct_from_missing_input(tmp_path):
    base = {'path': str(tmp_path / 'gone'), 'logical': 'worktrees/one/gone'}
    missing = list(configured_files({'roots': [], 'files': [base]}))[0]
    assert missing[2].startswith('MissingFileError:')
    deletion = list(configured_files({'roots': [], 'files': [{**base, 'expected_tracked_deletion': True}]}))[0]
    assert deletion[2] == 'Tracked deletion retained in binary patch and source bundle'


def test_source_disappearing_during_capture_is_a_publication_blocker(tmp_path, monkeypatch):
    from frontier_compute import backup
    identity = tmp_path / 'identity'
    subprocess.run(['age-keygen', '-o', str(identity)], capture_output=True, check=True)
    recipient = tmp_path / 'recipient'
    recipient.write_text(subprocess.run(['age-keygen', '-y', str(identity)], capture_output=True, text=True, check=True).stdout)
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'stable').write_text('Retained control')
    (source / 'disappearing').write_text('Inventory saw this file')
    original = backup.stable_copy

    def race(path, destination, bound):
        if path.name == 'disappearing':
            path.unlink()
        return original(path, destination, bound)

    monkeypatch.setattr(backup, 'stable_copy', race)
    result = backup.create_snapshot({'recipients': str(recipient),
        'roots': [{'path': str(source), 'label': 'evidence'}],
        'max_total_bytes': 10000, 'max_file_bytes': 1000}, tmp_path / 'snapshot')
    assert result['file_count'] == 1 and result['capture_errors'] == 1
    manifest = json.loads((tmp_path / 'snapshot/private-manifest.json').read_text())
    failure = manifest['capture_errors'][0]
    assert failure['capture_error'] is True and failure['reason'].startswith('FileNotFoundError:')
