# GCP CPU artifact export contract

The Frontier CPU worker writes to the private bucket `delphi-frontier-cpu-artifacts-20261031`
in `us-central1`. Uniform bucket-level access and public access prevention are enabled. Its
dedicated identity, `frontier-cpu-worker@scienceclaw26bos-3016.iam.gserviceaccount.com`, has only
bucket-level `roles/storage.objectCreator`. It cannot list, read, overwrite, or delete objects.
Do not attach the project's default Compute service account, which has broader project access.

## VM upload

Embed the stdlib-only `frontier_compute/gcp_artifacts.py` alongside the worker and run it after
each immutable output snapshot. The worker obtains a short-lived OAuth token from the GCE metadata
server and uses resumable HTTPS uploads. It reads no key file and writes no credential to a log.

```sh
python3 /work/frontier/gcp_artifacts.py upload \
  --bucket delphi-frontier-cpu-artifacts-20261031 \
  --prefix jobs/frontier-cpu-20261031-01/<task-id>/<snapshot-id> \
  --output-dir /work/frontier/snapshot \
  --record /work/frontier/run-record.json \
  --max-total-bytes 3000000000 \
  --partial
```

Omit `--partial` only when every output file has been copied into the immutable snapshot and the
task exit code is known. A final manifest means the export finished; the scientific job's result is
still the separate `job.exit_code`. Nonzero exit codes can be fully exported. Progress manifests
are appended after each file, and a final manifest is appended last. Each artifact gets an
unpredictable object name with a SHA-256 and byte count in both the manifest and GCS custom
metadata. Repeated exports must use unique snapshot prefixes; this avoids overwrite rights and
preserves every checkpoint. Export code refuses symlinks, traversal paths, secret-like metadata
keys/arguments, and output sets above their configured cap.

The run record has exactly these required fields:

```json
{
  "job_id": "frontier-cpu-20261031-01",
  "task_id": "example-task",
  "source_commit": "source commit identifier",
  "source_sha256": "64 lowercase hex characters",
  "input_sha256": {"input-name": "64 lowercase hex characters"},
  "parameters": {"declared_parameter": 1},
  "command": ["python3", "-m", "package.task"],
  "exit_code": null
}
```

`started_utc` and `finished_utc` are optional. During a running snapshot, use `exit_code: null`.
Never put environment dumps, access tokens, service-account keys, or arbitrary user secrets in the
record. Console logs are retained as ordinary output artifacts.

## Local collection

Run the collector from the operator workstation with an authenticated `gcloud` identity that can
read the artifact bucket. Give it the task prefix (the parent of all snapshot prefixes) so it
chooses the newest progress/final manifest by GCS generation, downloads only files referenced by
that manifest, verifies SHA-256 and size, and retains each snapshot separately:

```sh
python3 -m frontier_compute.gcp_artifacts collect \
  --bucket delphi-frontier-cpu-artifacts-20261031 \
  --prefix jobs/frontier-cpu-20261031-01/<task-id> \
  --destination /data/artifacts/delphi-evolve-rethink/gcp \
  --max-total-bytes 2000000000
```

Add `--require-complete` when a final manifest is required. The collector writes a local
`collection_receipt.json` beside each collected snapshot, with provider object names, manifest
digest, exact job metadata, and artifact hashes. It refuses path traversal, symlink destinations,
hash/size mismatches, missing objects, and exceeding the configured byte cap. Local copies are
durable independently of the GCP lab account's expiry.

## Current provisioning record

The bucket and bucket-only writer binding were created on 2026-10-31. No VM or artifact object was
created by this collector change. VM admission, network policy, startup deadline, and shutdown are
owned by the infrastructure dispatcher. The local collector uses the authenticated operator's
`gcloud auth print-access-token` flow; the VM never receives that token.
