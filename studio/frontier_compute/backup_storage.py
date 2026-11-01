"""Create-only private S3 publication of an age archive, then actual download verification."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

from frontier_compute.backup import sha_file, utc

BUCKET = 'morphoswarm-backups-024848463001'
REGION = 'us-west-2'
PREFIX = 'backups/delphi-frontier/snapshots/'


def aws(*args):
    result = subprocess.run(['aws', '--region', REGION, '--no-cli-pager', *map(str, args)],
                            capture_output=True, text=True, check=True, timeout=1800)
    return json.loads(result.stdout or '{}')


def publish(snapshot, name, verification):
    snapshot, verification = Path(snapshot), Path(verification)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', name):
        raise ValueError('Invalid unique snapshot name')
    receipt = json.loads((snapshot / 'receipt.json').read_text())
    archive = snapshot / 'snapshot.tar.gz.age'
    if receipt['archive'] != archive.name or receipt['capture_errors']:
        raise ValueError('Incomplete snapshot is not publishable')
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 5_000_000_000:
        raise ValueError('Archive is not a bounded regular file')
    with archive.open('rb') as stream:
        if stream.read(22) != b'age-encryption.org/v1\n':
            # Header is 22 bytes including newline; no plaintext uploads.
            raise ValueError('Expected client-encrypted age archive')
    digest = sha_file(archive)
    if digest != receipt['archive_sha256'] or archive.stat().st_size != receipt['archive_bytes']:
        raise ValueError('Archive differs from creation receipt')
    if verification.exists():
        raise ValueError('Verification directory must be new')
    verification.mkdir(mode=0o700, parents=True)
    os.umask(0o077)
    block = aws('s3api', 'get-public-access-block', '--bucket', BUCKET)['PublicAccessBlockConfiguration']
    if set(block) != {'BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets'} or not all(block.values()):
        raise ValueError('All bucket public access blocks must be enabled')
    key = PREFIX + name + '/' + archive.name
    put = aws('s3api', 'put-object', '--bucket', BUCKET, '--key', key, '--body', archive,
              '--if-none-match', '*', '--server-side-encryption', 'AES256',
              '--metadata', json.dumps({'sha256': digest}))
    downloaded = verification / archive.name
    get = aws('s3api', 'get-object', '--bucket', BUCKET, '--key', key, downloaded)
    if sha_file(downloaded) != digest or downloaded.stat().st_size != receipt['archive_bytes']:
        raise ValueError('Downloaded ciphertext does not match archive')
    url = f'https://{BUCKET}.s3.{REGION}.amazonaws.com/{key}'
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            public_status = response.status
    except urllib.error.HTTPError as error:
        public_status = error.code
    if public_status != 403:
        raise ValueError(f'Unexpected anonymous access response: {public_status}')
    result = {'schema': 'frontier.private-backup-storage/1', 'verified_utc': utc(),
              'uri': f's3://{BUCKET}/{key}', 'archive_sha256': digest,
              'archive_bytes': downloaded.stat().st_size, 'download_sha256_matched': True,
              'anonymous_http_status': public_status, 'public_access_block': block,
              'server_encryption': get.get('ServerSideEncryption'), 'create_only': True,
              'put_etag': put.get('ETag'), 'download_etag': get.get('ETag'),
              'credentials_uploaded': False, 'full_restore_verified': False}
    path = verification / 'storage-receipt.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    # Only non-secret summary accompanies the ciphertext. The private manifest stays encrypted.
    aws('s3api', 'put-object', '--bucket', BUCKET, '--key', PREFIX + name + '/storage-receipt.json',
        '--body', path, '--if-none-match', '*', '--server-side-encryption', 'AES256')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--verification', required=True)
    a = p.parse_args()
    print(json.dumps(publish(a.snapshot, a.name, a.verification)))
