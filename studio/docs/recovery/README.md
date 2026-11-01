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
file must remain stable while copied. Active JSONL transcripts are first staged at a declared complete-line cutoff, checked against a second unbuffered source read; later appends are explicitly outside that cutoff. Prefix rewrites, truncation and symlink replacement are refused. A changing staged file is reported as a capture error; publication
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
The final corrected film was deferred in this first snapshot and was included in the second snapshot below.

The parent reviewer also independently read the actual sb03-restored sanitized dump and
matched its23,236,752 bytes and SHA256 to the dump used in its18-table/application replay.
That ties the off-host recovered bytes directly to the database check. The complete-file
rehash was performed by the restore tool; the parent did not manually rehash every file.

## Public inputs and remote work that are not archived bytes

`results/resources/recovery-external-inputs.json` records the exact23 public genome
accessions, original HTTPS URLs, MD5 checksums and measured compressed sizes (5,805,450,239
bytes total). The original job deliberately deleted each temporary genome after analysis;
its complete output/progress files are preserved. No raw genome corpus is claimed in the
snapshot. To recover a selected assembly, fetch that exact URL to a new bounded destination,
require its recorded byte count and MD5, and record a new SHA256 separately. Do not silently
select a newer assembly. NCBI availability is an external dependency; backup did not re-fetch it.

The existing Evo2 smoke receipt pins a13,766,621,200-byte upstream weight file, exact Hugging
Face revision and SHA256. It is documented as an external model input, not archived model
weights or authorization to replay a provider-stopped task. Hosted model internals are not
recoverable from our request/output receipts. Container/package caches also remain external,
with only actually recorded pins/digests claimed. The inventory preserves the original6.78MB
CFD transport-cap loss explicitly; a later run is not the same missing archive.

Ongoing Nebius/GCP scientific states that have not been returned remain remote-only. Their
existing bounded collectors must finish and produce a later recovery snapshot before those
states can be called backed up. Returned partials are included; the Google lab is never the
sole final destination for retained results.

The first real separate-host service drill exposed a missing dependency: a vanilla PG16
container cannot restore the `vector` extension. That failed attempt is retained. Production
reports `plpgsql1.0` and `vector0.6.0`; the corrected drill selects the official
[`pgvector/pgvector`](https://github.com/pgvector/pgvector) image tag `0.6.0-pg16`, records its
actual immutable digest and PG minor version, and requires the restored extension versions to
match. Future database receipts also record installed extensions. Do not omit pgvector when
rebuilding the database; successful extraction alone would not have discovered this gap.


## Separate-host recovery exercised

The second snapshot, `20261101T0410`, contains the corrected 90-second film, NCA curriculum
returns, design-control records and source refs through the declared capture window. Its
1,586,623,355-byte encrypted archive has SHA256
`4c8cfb98f3529fddb9cb2905c3942a1611cb456ac18283c731118821933d7501`.
The complete off-host extraction verified 15,564 files and 3,305,659,592 logical bytes.

At **9:36:58pm PDT on October31,2026**, a separate-host service drill on sb03 passed from
that recovered source bundle and sanitized dump. It used source
`8a1f0914ec86d7905f5d19a4d20ee70a8f5fd587`, a new Python3.14.4 virtual environment, and a
socket-only PostgreSQL16.1 container with vector0.6.0. Its actual image digest, dependency
freeze, command exit codes and receipts are retained. All18 table counts matched before any
disposable write. Website health/catalog, official MCP authenticated writes and public reads,
idempotent retries, private-record withholding, invalid-bearer401 and credential-log checks
passed. Both application processes and the owned container were stopped and removed. Existing
sb03 services were not changed. This is an isolated service-recovery test, not a domain cutover,
and newer source refs captured afterward are not thereby claimed to have been executed.

Three prior failures remain in the encrypted recovery set: the first lacked pgvector;
the second let the verifier's host Python package shadow its fresh environment; the third
expected the intentionally public-only MCP read surface to return a private fixture. The final
checker runs its client with the new virtual environment's Python in isolated mode, requires
package paths inside it, preserves private-record refusal and separately round-trips a public
software fixture in the disposable loopback-only database. No API access rule was weakened.

Run the reusable service check from a restored tree, choosing a new private short path for
its socket directory. It refuses existing destinations and nested execution:

```sh
systemd-run --user --scope -p CPUQuota=100% -p MemoryMax=3G \
  -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=1200 \
  python -m frontier_compute.backup_service_check \
  --restored RESTORED_DIRECTORY --root NEW_SHORT_CHECK_DIRECTORY \
  --source-sha EXACT_BUNDLED_COMMIT --dump-sha EXACT_SANITIZED_DUMP_SHA256 \
  --video-sha EXACT_CORRECTED_VIDEO_SHA256
```

The checker requires Docker, a new virtual environment and dependency download access. It uses
no host database listener, exposes no public port, retains failed receipts and records cleanup.
The storage download/archive rehash, independent database replay and separate-host application
run are distinct evidence, joined in `results/resources/backup-recovery-service-20261101.json`.

The first final follow-up capture (`20261101T0440`) was withheld from publication because one active Codex transcript changed during copying. Its failed receipt remains preserved. The immutable transcript-prefix staging above was added in response; the archive stable-file gate was not weakened.


## Stable add-on and newer database

The private `20261101T0455` snapshot recovered **17,486 files / 3,707,042,825 logical bytes**
on sb03 at **9:56:00pm PDT**. Its encrypted archive is1,806,700,211 bytes, SHA256
`d95096e63db197efa597c04ad8befee4f59d304a6b5ff1fe3ee78efa74d1e7e3`.
It includes the corrected film, canonical BETSE media, NCA/design-control/CFD returns, source
refs and all four service-drill attempts. Active transcripts have declared complete-line
cutoffs. The recovered bundle was cloned on sb03 and every required commit checked.

A separate new read-only database transaction at **9:52:17pm PDT** contains **3,924 record
versions / 3,918 current heads / 1,970 events**. Its raw dump reproduced all18 source counts
in scratch; sanitization preserved scientific envelopes. All six exact newly imported observed
record references were also found in the sanitized dump's data stream. The private encrypted
`20261101T0500` add-on is47,038,250 bytes, SHA256
`f16301f7bbc2b7d960d70db6cb6e8ea62b02d07c445a051647c1f0071a1440b4`;
actual S3 download and sb03 decrypt/file checks passed. Use this newer sanitized dump with the
base source/artifact recovery. It does not overwrite or relabel the earlier dump.

`results/resources/backup-recovery-stable-addons-20261101.json` joins creation, private-storage,
off-host restore, exact source/video/dump identities and the new import-presence receipts.
The full website/MCP drill remains explicitly tied to its older tested source and dump.
The withheld0440 and0450 captures remain recorded; neither was uploaded. The latter caught
16 print-v4 paths being replaced during active repair. Print-v4 and new science videos are
explicitly deferred until their final publication, as are later cloud states not yet returned.
This is a declared recovery cutoff, not a claim to capture future writes.

## Four-film release and final Project database add-on

`20261101T0610` preserves exact live release `ac95c4c260d19ce8b26ea347e830884132644bfe`:
all four normal-speed films and their source media/captions, print-v4 and review, source refs,
24 declared transcript prefixes, the completed 45-arm mechanics return, and the three private
sequence-source HTML caches. The caches remain encrypted/private and are not public mirrors.
The archive is **848,233,945 bytes**, SHA256
`d6d5b0f5c036412cb63ca18d29cea7e679dabe8265e016d0b28de74e22784317`.
Actual S3 download, public-access denial and sb03 decrypt/rehash passed at **11:10:27pm PDT**:
**561 files / 1,197,455,541 logical bytes**, no capture errors.

Its database predates the new documentary/Project imports. The separate `20261101T0620`
add-on contains a new read-only transaction with **3,936 versions / 1,976 events**, the
complete partial regulatory return, and the incremental source objects through
`46dc3c78431a773c6e942c6b0d6b7b5b8998cde7`. All 18 table counts reproduced in scratch;
operational sanitization preserved scientific envelopes. This archive is **47,470,426 bytes**,
SHA256 `e62b472aaaf551a15c5993d9cfad1ab91d9dfbbda13e538ee72ffa1e2427fe11`.
Actual S3 download and sb03 decrypt verified **18 files / 47,730,362 logical bytes** at
**11:12:44pm PDT**. Snapshot names are identifiers; receipt timestamps define the capture windows.

Restore the earlier base for older artifacts/environment recipes, then these two additive trees.
Clone `0610/restored/metadata/frontier-all-refs.bundle` as a mirror before verifying/fetching
`0620/restored/metadata/source-incremental.bundle`; the incremental bundle requires the base
objects. This exact sequence recovered the source checkpoint on sb03. Use the **0620 sanitized
dump** with fresh credentials. Its actual sb03 digest is
`9c17f8098a9edd4a57c525c77d356e0226717f4159b791b1d901223b32683dc4`
(23,384,829 bytes). The raw encrypted dump remains available for private forensic recovery.

The joined public-safe receipt is `results/resources/backup-recovery-four-film-20261101.json`.
No whole application drill is claimed for these newer bytes: the earlier real separate-host
service drill remains tied to its exact older source and dump. Moving experiments, future writes
and original CPU cylinder states not yet returned remain outside this cutoff. The first broad
inventory attempt refused an unsafe selected path; its local failure was retained, and the
successful explicit frozen-release capture did not weaken the path or stability gates.

### Secondary-project release checkpoint (12:10am PDT, November 1)

Snapshot `20261101T0710` preserves exact deployed revision
`d87e5d15094be6fe89704f8225b17d4719d07b3b`, including the secondary project media and
all source refs captured in an incremental bundle. It also labels later native VLM,
epithelial, regulatory recovery and failed Voxcraft evidence separately from that release.
The fresh read-only database snapshot finished at 12:04:11am PDT: 3,960 record versions,
1,988 events and zero forks. Both raw and sanitized dumps reproduced the recorded
18-table counts in an isolated local PG16 cluster; scientific envelopes were unchanged.

The 799,342,626-byte age archive was uploaded privately to persistent S3, downloaded
and hash-checked, then decrypted on sb03. All 7,601 files / 1,709,971,561 logical bytes
matched at 12:10:54am PDT. Anonymous S3 access returned 403. The incremental source
bundle was verified and fetched into separate recovery refs in the mirror restored from
`20261101T0610`; the exact release commit resolves there. Use that base mirror before
fetching this bundle. The prerequisite commit list is inside encrypted metadata.

The public-safe joined receipt is `results/resources/backup-recovery-studies-20261101.json`.
Preparation failures (missing wrapper PATH/import path, missing pip in the uv venv, and
a missing resume variable) were retained; none overwrote an earlier snapshot. The
successful archive has zero capture errors. This checkpoint does not claim a new full
application drill: the earlier separate-host service drill remains separately dated.
Fresh credentials are required. Live credentials, upload capabilities, later transcript
appends and unreturned running CPU-CFD states are excluded. Public-genome re-fetch
accessions/checksums remain in the external-input inventory. The subsequent UI-only
`795f140` source/deploy change will use a small additive delta, without recapturing this data.

The UI followup is now captured as `20261101T0720`: exact revision
`795f1405e9ebea4554d3c7e4d62b924742aab2ad`. Only five deployed files differ from
`d87e5d1`; 6,551 files are unchanged and none are removed. The 32,157,342-byte
archive contains those files, incremental committed source refs and exact publication
receipts (18 files total). Its S3 download hash and second-host decryption passed;
the incremental bundle verifies/fetches into the `0610` + `0710` recovery mirror and
the exact final commit resolves. Apply this static delta atop `0710`, retaining that
3960-version database snapshot and fresh-credential recipe. This is a source/static
recovery check, not a new application or scientific validation claim. Later simulation
returns and publications remain separately scoped.
