# SPEC-004 — Export/Import Bundles, Fork-on-Conflict, and What a Digest Is Not

**Status:** Draft · **Version:** 0.1.0 · **Owner:** fable-lead · 2026-10-31
**Specced against:** `work/frontier-foundation` @ `42cd967`. The code is authoritative.
**Reviewer status:** single-reader (fable-lead). NOT Codex-reviewed.

> Clauses are **VERIFIED** (named test; 16-test suite green this session, exit 0) or **ASSUMED**.
> Nothing here is marked accepted.

## Scope

In scope: the bundle format, `export_bundle`, `import_bundle`, the `imported_unreviewed` status,
fork-on-conflict, the review receipts carried as untrusted source assertions, and the precise meaning
of the two digests — `bundle_sha256` and per-record `version`.

Not in scope: review semantics (SPEC-002), the Action lifecycle (SPEC-003), and transport (bundles
move as opaque JSON over the loopback HTTP adapter or out of band — there is no network peer protocol
in this slice).

**The one claim this spec defends:** a digest proves **integrity** — that these exact bytes are the
bytes the exporter emitted. It is **not** a signature (it proves no identity), **not** a timestamp
(it proves no time), and **not** acceptance (the receiving node reviews everything itself). The code
says so in the bundle's own `trust` field: *"Digest proves integrity only; reviews require
receiving-node policy."*

## Schema — the bundle

`export_bundle` (`store.py` line 344) produces exactly these fields (import rejects any other set,
line 370):

```
schema_version = "frontier-bundle-0.1"
exporting_node                      -- the source namespace, informational
records            []               -- full Record envelopes (1..100)
review_claims      []               -- flattened review receipts (≤ 100)
policy_version     = POLICY
trust              = "Digest proves integrity only; reviews require receiving-node policy."
bundle_sha256                       -- sha256 of all the above (digest over the body sans this field)
```

Bounds: 1..100 records (`MAX_BUNDLE_RECORDS`), ≤ 100 review claims, whole bundle ≤ `MAX_BUNDLE_BYTES`
= 2,000,000 bytes. **Dependencies are not silently expanded** — export carries exactly the versions
you name (`store.py` line 341), plus the dimensional-review Assessments bound to them (so a review's
own record travels with its receipt). Private records the caller cannot read are excluded
(`_can_read`).

## Export

`export_bundle(targets, token=None)` reads each named version (honoring visibility), collects the
`reviews` receipts whose `target_version` is in the set, and — for any receipt whose Assessment
record is not already in the selection — appends that Assessment record if the caller may read it, so
the dimensional review travels intact. If records-plus-reviews would exceed 100, it errors rather
than truncating. The body is digested into `bundle_sha256`.

**VERIFIED** a re-exported record is byte-identical to the original
(`test_two_store_bundle_preserves_digest_source_and_no_trust`: `reexport` of `ev` equals `ev`), and a
private record cannot be exported (`test_private_reads_bounds_and_immutability`: `export_bundle` of a
private record raises `Missing`).

## Import

`import_bundle(token, key, bundle)` (`store.py` line 372) is a `coordinator`-role write. Before the
transaction it checks: byte bound; the field set is exactly the seven above; `schema_version`
matches; **`bundle_sha256` recomputed over the body equals the claimed value**; and record/review
counts are in bounds. Each record is then re-validated through `Record.model_validate`, which
**recomputes every per-record `version` digest**.

Inside the transaction, for each record:

- if the `version` already exists locally, skip it (idempotent at the record level);
- otherwise insert it with `status = "imported_unreviewed"` and set it as head **only if no local
  head exists** for that `(namespace, kind, id)`;
- emit `record_imported` with `"issuer_authenticated": False` — the import does not vouch for who the
  issuer claims to be;
- if a local head already exists, record a **fork** (below).

Each `review_claim` is stored in `imported_review_claims` as *"an untrusted source assertion, never
in local reviews/auth"* (`store.py` line 394). An imported review **never** changes
`local_states.status` and **never** grants authority. The return value says so literally:
`"imported_reviews_are_local_authority": False`.

**VERIFIED** (`test_two_store_bundle_preserves_digest_source_and_no_trust`): after import, the record
is byte-identical, its `source` provenance is preserved, its status is **`imported_unreviewed`**, a
search for `status="accepted"` on the receiving node is **empty** (the exporter's acceptance did not
cross), the receipt reports `imported_reviews_are_local_authority is False`, and a re-import with the
same key returns the identical receipt (idempotent).

## Fork-on-conflict

If an import brings a new version for a record id that **already has a local head**, the store does
**not** overwrite the head. It inserts the imported version (not as head), writes a `forks` row
`(local_version, imported_version)`, and emits `fork_detected`. Both versions now exist; the local
head is unchanged; resolution is a later, explicit act, never automatic.

**VERIFIED** (`test_imported_conflict_is_fork_and_does_not_overwrite_head`): a replica imports a
record, the origin revises it, the replica imports the revision → the receipt's `forks` names
`{local_version, imported_version}`, the original stays `is_head == True`, and the imported successor
is `is_head == False`.

## What the two digests mean, and what they do not

- **Per-record `version`** = `sha256(canonical(record without version))`. It binds the record's bytes
  to its identity. **VERIFIED tamper detection, both layers**
  (`test_two_store_bundle_preserves_digest_source_and_no_trust`): changing a record's `statement`
  makes import fail with `ValueError`; and even after the attacker **recomputes the outer
  `bundle_sha256`** to match the tampered body, import still fails with `ValidationError` because the
  inner per-record `version` no longer matches its bytes. A valid bundle digest cannot launder a
  changed record.
- **`bundle_sha256`** = `sha256(canonical(body without bundle_sha256))`. It binds the *collection* of
  bytes together for transport integrity.

Neither digest is a signature or a timestamp. The code carries this discipline deliberately, and it
is the same lesson `CONTRIBUTING-VERIFICATION.md` §2 was written from ("hash the file, not the
string"; a freeze hash that was the sha of an in-memory string, not the committed bytes). Here the
hash is always over canonical bytes, recomputed on receipt, and never trusted from the sender. An
importing node therefore learns **what** was sent, not **who** sent it or **when** — and must run its
own review (SPEC-002) before anything it imported counts as accepted locally.

## Acceptance

Bounded run, this session: **16 passed, exit 0.**

| Contract | Verified by | Status |
|---|---|---|
| Bundle field set fixed; unknown fields rejected | `test_two_store_bundle_…` (field checks in `import_bundle`) | VERIFIED |
| Dependencies not silently expanded on export | `store.py` line 341; export carries only named + bound reviews | ASSUMED (not isolated in a test) |
| Imported record is byte-identical; provenance preserved | `test_two_store_bundle_preserves_digest_source_and_no_trust` | VERIFIED |
| Imported status is `imported_unreviewed`; acceptance does not cross | same test | VERIFIED |
| Imported reviews are not local authority | same test (`imported_reviews_are_local_authority` False) | VERIFIED |
| Re-import is idempotent | same test | VERIFIED |
| Tampered record rejected even with recomputed bundle digest | same test (`ValueError` then `ValidationError`) | VERIFIED |
| Conflict forks, does not overwrite local head | `test_imported_conflict_is_fork_and_does_not_overwrite_head` | VERIFIED |
| Private records not exportable | `test_private_reads_bounds_and_immutability` | VERIFIED |
| Append-only tables reject UPDATE/DELETE | same test (`RaiseException` on UPDATE and DELETE) | VERIFIED |

## Open questions

1. **No peer protocol.** Bundles are produced and consumed, but there is no fetch/announce/gossip
   between nodes in this slice — movement is manual or over the loopback adapter. A real federation
   needs a transport, and that transport must not become a trust channel (the digest discipline above
   must survive it).
2. **Fork resolution.** `fork_detected` and the `forks` table record a divergence but nothing
   resolves it. Is resolution a new version whose `predecessor` names one side, a review that
   `disputes` one, or an explicit merge record? Undecided, and deliberately not invented here.
3. **Signatures, if ever.** If identity is wanted (a node proving it authored a record), that is a
   signature over the `version`, a new field, and a key-distribution problem — explicitly out of this
   slice, which proves integrity only. Adding it must not weaken the "receiving node reviews
   everything" rule.
4. **`imported_review_claims` is write-mostly.** Imported receipts are stored but no read surface
   exposes them as what they are (untrusted third-party assertions). A reader who wants "what did
   other nodes say about this record" has no bounded query yet; adding one must keep the untrusted
   label attached.
