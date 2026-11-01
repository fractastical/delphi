# MCP contribution round trip: a software protocol test

Status: single-reader, not independently reviewed. Everything is `proposed`; nothing is accepted or reviewed. **Not a biological finding.**

`scripts/mcp_demo.py` drives this node's own MCP server over stdio with the official SDK client, in write-enabled mode, as one principal:

1. Observes the interface in a read-only session and a write-enabled session (tool listings, capability manifests, an anonymous search sample).
2. `frontier_propose` a software-test **Claim**, then an **Action** whose `proposal` block (intent `analysis`) states method, alternatives, controls, outcomes and limits.
3. `frontier_transition` to `ready` (coordinator role), `frontier_lease`, `frontier_transition` to `running`.
4. Runs the bounded check (a pure function of the snapshot, six invariants: read-only mode has only read-only tools; write mode adds exactly propose, lease, transition; every tool is in the manifest; no credential-like argument; no review/accept/import/provision tool name; the anonymous search returns only public records).
5. `frontier_propose` an **Evidence** with `produced_by` = the Action and artifact digests for the exact input snapshot, output verdicts and code (`urn:sha256:` pointers; the node never stores or fetches those bytes), then `frontier_transition` to `submitted` ("complete" in MCP; acceptance is not reachable there).
6. Reads everything back through MCP (`frontier_get`, `frontier_artifacts`) and writes a receipt.

## Result on the live node (2026-10-31)

Principal `codex-03` / operator `local-fleet` (the same operator proposed, ran and submitted, so nothing is independent). 6 of 6 invariants held; Evidence `relation: supports`.

| record | id | state |
|---|---|---|
| Claim | `software-protocol-test-mcp-interface-invariants` | proposed |
| Action | `...-action` | proposed; execution state `submitted` |
| Evidence | `...-evidence` | proposed; `produced_by` the Action |

Exact versions, hashes and steps: `imports/2026-10-31-mcp-roundtrip-receipt.json`; files whose sha256 are the artifact digests: `imports/mcp-demo-input.json`, `imports/mcp-demo-output.json`, and `scripts/mcp_demo.py` at the recorded commit. The artifact index lists the three artifacts with `artifact_bytes_verified: false`. No existing scientific record was touched.

## Safety properties (each pinned by a test; six mutations each fail one)

* The credential is read from a mode-600 file, put only in the child server's environment, and never printed or recorded. The lease id (a bearer capability) is held in memory only. The receipt carries no database location.
* Fixed record ids and read-first state: a completed run re-verifies and writes nothing; a partial run resumes; another author's record under the same id, a wrong principal, or a missing coordinator role stops the run before any write (exit 3).
* The check cannot pass vacuously (an empty search sample fails I5).

## Limits

* Proposer, runner and submitter are one operator. The Evidence is a software assessment of this node's own interface on one deployment and one code version.
* `evidence_kind` is `source_assessment` because the enumeration has no software-test value (an open point for the owner of `models.py`).
* Known defect, left in place so the Evidence's code digest keeps matching the committed file: the receipt field `read_back.event_types_seen_in_first_page` is empty (the script read one page of a long event log). The receipt's `amendment_after_run` records the full-log verification: 7 events, no review or accept event, no review receipt.
