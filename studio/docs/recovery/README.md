# Recovering Frontier on a fresh host

The backup is an encrypted private recovery set. It is not a public artifact catalog. Raw
database dumps and transcripts may contain confidential scientific records and historical
capabilities. Never publish a decrypted tree, the private manifest, or either database dump.

## What is captured

- A PostgreSQL 16 custom-format dump from a read-only exported transaction snapshot,
  table counts from that same snapshot, and a separately sanitized recovery dump.
- All advertised source refs in a verified Git bundle, including unmerged branches;
  registered Frontier worktree statuses, binary diffs, and modified/untracked files.
- The shared Frontier artifact tree, scoped service/job journals and handoff files.
- Hackathon-window Codex/Claude JSONL sessions selected by exact Frontier path/URL
  markers; unrelated projects are not swept into the backup.
- Service templates with environment values removed, release history, dependency
  specifications in source, and a per-file hash/size/mode manifest.

The capture is a declared time window, not an atomic filesystem snapshot. Each individual
file must remain stable while copied. A changing file is reported as a capture error; publication
refuses a snapshot with capture errors. The database has its own transactional snapshot.
The receipt's `bundled-refs.txt` describes actual bundled refs; an earlier worktree inventory
can describe an earlier capture moment.

Exclusions are explicit in the encrypted manifest: credentials and `.env` files, private keys,
runtime upload-capability/injection directories, sockets/PIDs, raw PG cluster files,
dependency caches/toolchains, symlinks and generated release copies. Dependencies and releases
are rebuilt from source pins. A video still under review can be explicitly deferred; it must
be included in a later snapshot after publication. The raw dump is retained encrypted for
forensics. Default recovery uses the sanitized dump: old principals and idempotency cache are
removed, active leases invalidated, and scientific record envelopes retained unchanged.

## Storage and keys

The persistent destination is private AWS S3 in `us-west-2`, independent of the expiring
Google lab project:

`s3://morphoswarm-backups-024848463001/backups/delphi-frontier/snapshots/`

Snapshots use client-side `age` encryption plus SSE-S3. Publication requires all four S3
public-access blocks, uses create-only PUT, downloads the ciphertext and verifies its SHA256,
then checks that anonymous object access returns 403. Object names are unique; the tool neither
overwrites nor prunes historical snapshots. A public-safe receipt accompanies each archive.

The recipient list contains existing SSH public keys only. The sb03 private key remains on
sb03; its decrypt ability was exercised with an actual encrypted fixture. The user RSA
recipient is a second recovery route, but possession was not independently tested. The sb02
recipient permits local replay, but is not the sole recipient. Private keys are never copied.
Access to S3 and possession of a decryption key are separate requirements; sb03's own AWS role
currently cannot read this bucket. An authorized operator can copy the encrypted object to
sb03 over SSH, or establish a new scoped S3 read role during disaster recovery.

## Reusable commands

Run process-spawning work under a whole-tree scope, for example:

```sh
systemd-run --user --scope -p CPUQuota=100% -p MemoryMax=2G \
  -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=1800 COMMAND
```

Creation uses a new private staging directory. `backup_database` requires psycopg3 and PG16;
the archive and storage tools use Python's standard library, `age`, and AWS CLI v2.
Never point scratch output at an existing cluster.

```sh
python -m frontier_compute.backup_database --destination STAGING/database-v2
python -m frontier_compute.backup_inventory --repo FRONTIER_REPO \
  --staging STAGING --recipients PRIVATE_RECIPIENTS_FILE
python -m frontier_compute.backup create --config STAGING/snapshot-config.json \
  --output NEW_SNAPSHOT_DIRECTORY
python -m frontier_compute.backup_storage --snapshot NEW_SNAPSHOT_DIRECTORY \
  --name UNIQUE_UTC_ID --verification NEW_DOWNLOAD_DIRECTORY
```

Database capture never changes production. Sanitization happens only after verifying the
scratch database name and actual data directory. Source and restored counts must match;
the scientific-envelope aggregate digest must remain unchanged by sanitization.

Recovery starts with the downloaded ciphertext and an authorized local key:

```sh
aws s3 cp s3://BUCKET/PREFIX/snapshot.tar.gz.age downloaded.tar.gz.age
sha256sum downloaded.tar.gz.age   # compare the independent storage receipt
python -m frontier_compute.backup restore --archive downloaded.tar.gz.age \
  --identity PRIVATE_SSH_KEY --destination NEW_EMPTY_RECOVERY_DIRECTORY
git bundle verify NEW_EMPTY_RECOVERY_DIRECTORY/metadata/frontier-all-refs.bundle
git clone NEW_EMPTY_RECOVERY_DIRECTORY/metadata/frontier-all-refs.bundle restored-source
```

Restore authenticates encryption, rejects nonregular archive members and path traversal,
verifies every content hash/size, and refuses to overwrite an existing destination. Its receipt
records actual restored counts and source capture errors. It does not start services, alter
production, or automatically apply worktree patches. Select the intended source ref using
`metadata/bundled-refs.txt` and release history; review worktree patches before applying them.

## Rebuild the service

Use a fresh Linux service account with PostgreSQL16, Python3.12 or later, `age`, Git and a
Python virtual environment. Install the selected source's exact `pyproject.toml` dependencies;
optional simulator packages are separate from the website/MCP runtime. Retain each simulator's
original requirements/environment receipt when replaying science.

1. Use `deploy/postgres/init-cluster.sh NEW_SERVICE_ROOT` on an empty destination. It creates a
   dedicated socket-only cluster with no TCP listener; it does not start it.
2. Start that new cluster and run `deploy/postgres/create-db.sh NEW_SERVICE_ROOT` to create the
   application role/database. Check these scripts against the selected source before execution.
3. Restore `database/frontier-restore-sanitized.dump` into the **new empty database**, using
   PG16 `pg_restore --no-owner --no-acl --exit-on-error`. Record its actual exit code. Restore
   as the application owner so its tables have the intended ownership. Never use `--clean`
   against an existing production database.
4. Compare all 18 table counts to the sanitized counts in `database/database-receipt.json`;
   verify zero principals/idempotency rows and zero lease IDs. Reissue contributor credentials
   using the current application CLI. Do not restore old runtime bearer values.
5. Rebuild the release from its exact Git SHA with `deploy/release.py`. Review the bundled
   systemd/nginx templates, restore public Frontier reads and authenticated writes, and preserve
   Studio/Orchestra's separate protection boundaries. Runtime `.env` values must be recreated.
6. Run the selected source's live web/MCP checks, catalog checks and artifact hash checks on
   loopback first. Record which checks actually executed before exposing a replacement host.

The initial DB replay was exercised independently against fresh socket-only PG16 databases,
including real application health/catalog reads. This establishes dump compatibility; a full
fresh-host service rollout remains a separate operational check. Do not equate archive checksum
verification with a complete service recovery.

## First recovered snapshot

`20261101T0350` was captured from 8:49:35–8:51:13pm PDT on October31,2026. The
1,440,390,756-byte encrypted archive is stored under the corresponding unique S3 prefix.
Its SHA256 is `100e8bbbad91c1219b1489199d3d20c11b5a1dbe93656b78a98ac6fb165f3b94`.
An actual S3 download matched that digest. The downloaded object was copied to sb03, decrypted
using its existing private key, and all 14,677 files / 3,099,904,825 logical bytes passed
hash/size verification at 8:57:23pm PDT. A mirror clone and Git bundle verification passed
on sb03. `results/resources/backup-recovery-20261101.json` joins these separate receipts.

The first receipt lists two missing selected files. Both were tracked deletions in the
`nca-flow` worktree's `pilot_tmp` directory: original contents remain in the source bundle,
and deletion state remains in the binary patch. This is explicitly distinguished from missing
untracked evidence; subsequent tooling fails publication for an unexplained missing selection.
The final corrected film remains deferred until its publication manifest is ready.
