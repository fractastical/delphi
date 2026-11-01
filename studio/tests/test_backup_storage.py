import json
from pathlib import Path
import urllib.error

import pytest

from frontier_compute import backup_storage as storage
from frontier_compute.backup import sha_file


def fixture(tmp_path, data=b'age-encryption.org/v1\nENCRYPTED_FIXTURE'):
    source = tmp_path / 'snapshot'
    source.mkdir()
    archive = source / 'snapshot.tar.gz.age'
    archive.write_bytes(data)
    (source / 'receipt.json').write_text(json.dumps({'archive': archive.name, 'capture_errors': 0,
        'archive_sha256': sha_file(archive), 'archive_bytes': len(data)}))
    return source, archive


def test_storage_roundtrip_create_only_and_no_private_manifest(tmp_path, monkeypatch):
    source, archive = fixture(tmp_path)
    calls = []

    def fake_aws(*args):
        calls.append(args)
        if args[1] == 'get-public-access-block':
            return {'PublicAccessBlockConfiguration': dict.fromkeys(
                ['BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets'], True)}
        if args[1] == 'get-object':
            Path(args[-1]).write_bytes(archive.read_bytes())
            return {'ServerSideEncryption': 'AES256', 'ETag': 'fixture'}
        assert args[1] == 'put-object' and '--if-none-match' in args
        assert args[args.index('--if-none-match') + 1] == '*'
        assert 'private-manifest.json' not in str(args)
        return {'ETag': 'fixture'}

    def denied(*args, **kwargs):
        raise urllib.error.HTTPError('test', 403, 'Forbidden', {}, None)

    monkeypatch.setattr(storage, 'aws', fake_aws)
    monkeypatch.setattr(storage.urllib.request, 'urlopen', denied)
    result = storage.publish(source, 'test-unique', tmp_path / 'verification')
    assert result['download_sha256_matched'] and result['anonymous_http_status'] == 403
    assert len(calls) == 4


def test_plaintext_refused_before_any_cloud_call(tmp_path, monkeypatch):
    source, _ = fixture(tmp_path, b'PRIVATE RAW DATABASE CONTENT')
    monkeypatch.setattr(storage, 'aws', lambda *args: pytest.fail('No cloud call allowed'))
    with pytest.raises(ValueError, match='client-encrypted'):
        storage.publish(source, 'test', tmp_path / 'verification')
