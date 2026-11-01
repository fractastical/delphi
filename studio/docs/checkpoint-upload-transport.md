# Bounded checkpoint transport

The proposed GCS transport sends a private, short-lived V4 PUT capability for
each exact object. It gives the scientific worker no OAuth token or private key.
The object creator service account has no direct project roles and only
`roles/storage.objectCreator` on the private artifact bucket. The effective
inherited policy could not be established: Policy Troubleshooter returned
`UNKNOWN_INFO`, which is retained in the receipt.

At 7:17pm PDT on October31, a ten-minute operator-only signing grant was refused
with `iam.serviceAccounts.setIamPolicy` denied. Signing itself was refused with
`iam.serviceAccounts.signBlob` denied. **No IAM change, capability issuance or
test upload occurred.** This transport is not an admission gate that has passed.

The implemented uploader streams a regular file, bounds its size, checks URL
origin/object identity and expiry, requires signed create-only generation-zero
and content-type headers, and sends Content-MD5 for server-side integrity. Its
public receipt contains size, SHA256, generation and expiry, never the URL. A
network ambiguity requires operator download/hash verification; it is not
silently retried. Nine focused software tests and Ruff passed. A tiny real
create-only upload, rejected overwrite, and independent download/hash check are
still required before scientific checkpoint admission.

If a narrow authorized signer becomes available, start with a ten-minute probe
grant on this service account only. Check actual effective create/get/list/
delete/update/setIamPolicy permissions, revoke on excess rights, and sign only
the declared object names. Production links must expire before the lab deadline;
no service-account key is needed. Remove the operator-only signing binding after
the last required capability, record the resulting policy, and export artifacts
off the expiring lab project. Current cleanup state: there is no successful grant
or upload to revoke/delete. The failed attempts and before-policy evidence live
under `results/resources/gcp/signed-upload-*.json`.

The full CFD R2 assay also requires its measured H100 runtime and unchanged
numerical gates. The H100 controls/calibration job does not run R2 cases. Its
small returned diagnostic bundle uses the existing verified log transport.


A separate resumable-session path passed real checks at7:45–7:48pm PDT. The
operator initiated exact create-only objects with existing credentials, then the
worker-style uploader sent no OAuth credentials. Its45-byte probe passed GCS
server-reported MD5 and independent operator SHA256 download checks. An earlier
probe rejected overwrite withHTTP412. The reusable persisted cancellation timer
ran after the initiating process exited, cancelled the pending session with499,
and a later upload to that session returned499. Completed probe objects remain
private and were not deleted. No IAM grants or service-account keys were added.

`frontier_compute/resumable_upload.py` streams8MiB chunks, validates object/host/
generation-zero and size, checks final GCS MD5, and never emits the session URI.
Its private0600 ledger in a0700 directory is outside git and website roots.
`frontier-upload-cancel@.timer` is a persistent every-minute operator schedule;
provider sessions themselves last one week. Cancellation can run up to about65s
after its declared deadline, plus request latency; no short provider TTL is claimed.
Unused production sessions must be cancelled by the timer before lab teardown;
completed objects must be collected and independently hashed off the lab project.

The CFD wrapper uses unchanged native source and copies its small outputs to the
normal log archive. Only coherent manifest-listed checkpoint files are uploaded;
the archive retains the native manifest and external size/hash/object receipts.
The original files remain in the job filesystem until termination. Three failed
transport attempts remain failures; missing exports prevent a complete transport
receipt. Every fullR2 job still reruns the same numerical and runtime gates.
