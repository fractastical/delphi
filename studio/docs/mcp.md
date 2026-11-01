# Frontier MCP server

Official `mcp` SDK 1.27.0, stdio and stateless Streamable HTTP transports. Remote
support salvages the collab worker's unfinished implementation, with additional
request-budget, actual-body-byte and authentication-context checks. The earlier
stdio smoke transcript below remains attributed to its original worker.

## Remote endpoint

**Public endpoint: `https://frontier.morphoswarm.ai/mcp`.** Select Streamable HTTP
in an MCP client. Public reads require no login or token. Writing requires an
individual contributor credential. The website is https://frontier.morphoswarm.ai.

The user service binds `127.0.0.1:8972`; an exact nginx `/mcp` location proxies
HTTPS requests. Deployment files are in `deploy/mcp/`. The service and proxy
were installed on October 31, 2026. The official SDK completed initialization,
tool discovery, a real fish search and Project schema retrieval through public
HTTPS; anonymous writes and an invalid supplied token were rejected. The twelve
checks are recorded in `deploy/receipts/mcp-public-check.json`. No scientific
record was written. A plain browser GET receives405: use an MCP client.

The endpoint at release `c804b31` exposes fifteen read/calculation tools and three
credentialed contribution tools. The official public client completed 33 checks,
including an actual simulation, constraint solve, formalization, belief calculation,
exact Project lookup and hash-checked print asset lookup. The receipt is
`deploy/receipts/mcp-expanded-check.json`. These calculations wrote no scientific
records. Discovery used its explicit lexical fallback in that check.
The October 31 About release also deployed `frontier_design_context`, bringing
the live total to 19 tools (16 read/calculation tools and three credentialed
contribution tools). At 3:45pm PDT, the official SDK client completed 35 checks,
including exact-version design context and bounded calculations; no scientific
records were written. The receipt is
[`about-mcp-live-check.json`](../deploy/receipts/about-mcp-live-check.json).
Check the live capability manifest for the currently deployed tool set.
Start with `frontier_capabilities`, then use exact refs from `frontier_search`,
`frontier_discover` or `frontier_graph` with `frontier_get`.

Repeat the deployed connectivity check with:

```bash
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=1G -p MemorySwapMax=0 \
  -p RuntimeMaxSec=180 python deploy/verify_mcp.py --receipt /tmp/frontier-mcp-check.json
```

```bash
python -m frontier mcp --namespace NODE --schema public --transport http \
  --mcp-port 8972 --public-host frontier.morphoswarm.ai --public-read --allow-write
```

`FRONTIER_DSN` is server-side database configuration. Remote mode ignores
`FRONTIER_TOKEN`, even if inherited. `--public-read` permits anonymous reads of
public records, capabilities, artifacts and payload schemas. Without that flag,
every request needs a valid bearer. `--allow-write` registers the existing proposal,
lease and lifecycle tools; it does not authorize anonymous callers or confer roles.

Every remote write requires `Authorization: Bearer <the calling operator's own
credential>`. The SDK bearer backend resolves `Store.principal`, and request-local
authentication context supplies that exact bearer to Store methods. Those methods
enforce identity, namespace, roles, quota, lease ownership and idempotency. Invalid
supplied credentials return401 even in public mode; they never become anonymous.
Public reads remain public-only even for an authenticated caller. No shared
contributor credential, browser cookie authentication, OAuth server, self-service
provisioning, review/import/execution tool or job runner is added.

Transport uses stateless HTTP and JSON responses; no session id is issued. A
session header cannot borrow another principal's identity. POST `/mcp` is served;
GET and other methods return405, other paths404. Query strings are refused,
including token queries. Requests are bounded to131072 actual body bytes,8 active
requests including body/authentication work, and a60s asynchronous deadline.
Store connections/statements retain their own5s limits. Blocking transaction
threads are not abandoned at the deadline, so an in-flight transaction can finish
before cancellation is observed; retries must use the original idempotency key.
Host and Origin are allow-listed by the SDK. Logs record method, fixed route label
and status, omitting query strings, credential headers and unmatched path contents.

Official SDK client shape for anonymous reads:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("https://frontier.morphoswarm.ai/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("frontier_capabilities", {})
```

For a provisioned contributor, supply the credential only as an Authorization
header through the client/secret manager, never in a URL, tool argument, repository
file or process argument. Header support in other clients must be checked with
those clients. Capabilities derive `record_kinds` from current KINDS, and
`frontier://schema/{kind}` derives schemas from current PAYLOADS; new kinds do not
need a separate hard-coded remote vocabulary.

Targeted verification command (isolated PostgreSQL, official SDK clients):

```bash
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 \
  -p RuntimeMaxSec=600 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  bash scripts/test_postgres.sh tests/test_mcp_remote.py tests/test_interfaces.py
```

The focused tests exercise public/private reads, two distinct interleaved writers,
issuer spoofing, wrong roles, idempotent retries/conflicts, lease ownership,
missing/malformed credentials, process-token rejection, session-header isolation,
dynamic schemas, body/host/origin/path/method bounds, verifier concurrency,
deadline handling and fixed-text storage failures. Actual run counts belong in
the branch handoff; definitions alone are not a run.

## Stdio modes

| | Default (`python -m frontier mcp ...`) | Opt-in (`... --allow-write`) |
|---|---|---|
| Tools | 18 read tools (all `readOnlyHint=true`; listed below) | the 18 above plus `frontier_propose`, `frontier_lease`, `frontier_transition` (`readOnlyHint=false`, `destructiveHint=false`, `idempotentHint=true`) |
| Resources | `frontier://capabilities`, `frontier://schema/{kind}` | same |
| Acts as | nobody | the principal that owns `FRONTIER_TOKEN` |

A token in the environment does **not** enable writes. Only the `--allow-write` flag does, and then the server verifies the credential at startup and refuses to start
(exit 2, fixed message, nothing echoed) if the token is missing, unknown, lacks the `contributor` role, or the store is unreachable. Writes are never a silent fallback.

## What the write tools are (all of them call the store's existing methods)

| Tool | Store method | Gate (enforced by the store, not here) |
|---|---|---|
| `frontier_propose(draft, idempotency_key)` | `Store.submit` | role `contributor`; `draft.issuer` must equal the principal's actor; `draft.namespace` must equal this node; exact current predecessor; licence gate; quota; Events are emitted by the store only. Result is `proposed`. |
| `frontier_lease(target, seconds 1..600, idempotency_key)` | `Store.lease` | role `contributor`; atomic; one holder; returns `lease_id` |
| `frontier_transition(target, state, idempotency_key, lease_id?)` | `Store.transition` | `ready` needs role `coordinator`; `running/submitted/blocked/failed/cancelled` need the live lease's holder and exact `lease_id`. `accepted`/`disputed`/`reviewed` are not in the allowed state set and are rejected at the schema. |

**Deliberately absent:** review/accept/dispute, `import_bundle`, `provision`, `initialize`, job execution, network fetch, publication. Acceptance requires an independent
operator acting with that operator's own credential (HTTP `POST /v1/reviews`); a test shows that the same-operator `alias` reviewer is refused by the store for an
action submitted through this MCP server and that a different operator can accept it. `lease_id` is a bearer capability for that lease: keep it inside the leasing agent's session.

## Expanded read and calculation tools

This implementation registers 18 read-only tools in both stdio and
remote modes, including `frontier_plan_experiments`.
Check `frontier_capabilities` on the actual server before relying on a tool,
because subsequent deployment changes may differ from this dated record.

| Tool | What it returns | Important scope |
|---|---|---|
| `frontier_search` | Existing lexical record search | Exact versions and local status are kept separate. |
| `frontier_get` | One exact version | Does not substitute a newer head. |
| `frontier_neighborhood` | Existing depth-one typed links | Bounded by the existing Store API. |
| `frontier_events` | Existing node events | Node-local event history. |
| `frontier_artifacts` | Declared artifact metadata | Does not fetch or verify remote bytes. |
| `frontier_capabilities` | Mode, roles, tools, limits and unavailable operations | Never includes credentials. |
| `frontier_discover` | Lexical or hybrid results | Hybrid uses cached query embeddings only; when a matching vector is unavailable it explicitly reports lexical fallback. It makes zero embedding-provider requests. Relevance is not truth. |
| `frontier_graph` | Bounded public graph overview or a graph rooted at an exact `Ref` | Public records only; exact versions, declared links and truncation are explicit. Depth is at most 3. |
| `frontier_catalogue` | Counts and coverage report from the existing catalogue adapter | Describes the bounded public catalogue, not all records that may exist elsewhere. |
| `frontier_project_inspect` | One exact Project envelope and its pinned members | Project pins remain exact; membership does not establish applicability or acceptance. |
| `frontier_design_context` | Exact Project/member annotations and paginated challenge/reply threads | Every annotation carries its exact anchor and thread pin; authored challenges and replies do not vote, validate, or resolve a design. |
| `frontier_artifact_inspect` | Exact-hash matching Evidence declarations, guarded local-media matches and optional text | `include_text=true` reads published UTF-8 JSON, plain text or CSV only, after rechecking the complete file digest. Maximum file size is 1,000,000 bytes; `max_chars` defaults to 8,000 and is bounded to 1–16,000. Truncation and unavailable/unsupported content are explicit. Remote URIs are never fetched. Declaration alone is not byte verification. |
| `frontier_simulate` | One allowlisted bioelectric or mechanobiology preview | Fixed bounded local adapter; ephemeral `SimulationResult`, never accepted Evidence. No arbitrary code, cloud job or external inference. |
| `frontier_engineer` | Existing finite aircraft-constraint calculation | Ephemeral exact-constraint result. The optional Z3 solver must be installed; otherwise the adapter returns a bounded `solver_unavailable` error. No biological validation is implied. |
| `frontier_proofs` | Five fixed recorded Lean theorem families, assumptions and source/receipt links | Checks current source/dependency pins and the exact published source/receipt bytes on every read. Optional fixed family and bounded Lean text; no compiler, arbitrary path or biological validity claim. |
| `frontier_formalize` | Existing finite expression/formalization proposal | Ephemeral proposal; not a persisted or accepted formal Evidence record. |
| `frontier_belief` | Existing finite scenario calculation | Conditional on declared inputs and explicitly uncalibrated; ephemeral and not accepted. |
| `frontier_plan_experiments` | Prospective linear-Gaussian design comparison | Returns assumption-based covariance and rank diagnostics, no measurements or writes. Check the connected server's capabilities for availability. |

Example calls through the official MCP SDK:

```python
await session.call_tool("frontier_discover", {
    "query": "ion-channel recovery after stimulation",
    "mode": "hybrid",  # cached vectors if available, otherwise explicit lexical fallback
})

await session.call_tool("frontier_project_inspect", {
    "target": {"namespace": "NODE", "kind": "Project", "id": "project-id", "version": "<64-hex-version>"},
})

await session.call_tool("frontier_simulate", {
    "model": "bioelectric",
    "parameters": {"duration_ms": 30, "frame_count": 31},
})
```

### Prospective experiment planning

The `frontier_plan_experiments` tool is implemented here and should
be relied on only when `frontier_capabilities` lists it on the connected server.
It accepts one complete `frontier.experimental-design.request/1` contract under
the argument `contract`. The existing local planner validates exact source and
context pins, dimensionless parameters, finite positive-semidefinite prior
covariance, positive noise covariance, and candidate design shapes. The MCP
wrapper applies additional resource bounds before matrix work:

| Limit | Maximum |
|---|---:|
| Serialized request | 65,536 bytes |
| Parameters / readouts / candidate designs | 8 / 12 / 12 |
| Observation rows per candidate / batches | 32 / 16 |
| Technical repeats / source Claims / input datasets | 64 / 64 / 64 |
| String length / nesting depth | 2,048 characters / 8 |

Example using the frozen mathematical cantilever protocol:

```python
await session.call_tool("frontier_plan_experiments", {
    "contract": frozen_protocol,
})
```

The result is `prospective_assumption_based`. It includes each candidate's
prospective covariance, rank/nullspace diagnostics, and target-variance
reduction per the declared cost unit. It has no measurement rows. Priors, noise,
and costs remain submitted assumptions; the output is not an observed posterior
or a probability of biological success. The embedded ActionProposal is
unsubmitted and unlinked until exact Problem/Project refs are supplied. The tool
does not create records, queue Actions, launch compute, call model providers, or
execute experiments.

Calculations return ephemeral outputs. To make a durable, reviewable
contribution, an authenticated contributor can submit a typed `Evidence` or
`Action` draft with `frontier_propose`. The store validates its existing schema,
actor, namespace, exact target/input refs, idempotency key, quota and any
`cost_stop_bounds`; the resulting Action remains `proposed`. Workers must then
use the existing lease and transition tools and record actual outputs as
separate Evidence. This MCP surface does not claim a calculation was accepted,
does not add an Action execution queue wrapper, and does not invent a Project
pin field absent from the current Action schema. Review and acceptance remain
independent operations through the existing review API.

Structured Project challenges use `POST /v1/design/reviews` with ordinary
`Annotation` records (or authenticated `frontier_propose`) and the
optional `design_review` payload. The challenge pins one exact Project version
through `anchor.record`; an optional `member_index` addresses that Project
version's pinned member list. It records the review dimension, evidence basis
and exact Claim/Evidence refs, scope, alternative, and a falsifiable next test.
Replies are ordinary Annotations using `reply_to`. This discussion carries no
vote tally, automatic resolution, or claim that a debate settles biology.

## Credentials

* Only the process environment: `FRONTIER_DSN` always; `FRONTIER_TOKEN` with `--allow-write`. No tool has a token/DSN/password argument (a test scans every input schema).
* No output carries them: tests scan the capability manifest, resources, tool errors and the server's stderr for the token. Errors are typed and bounded
  (`invalid_request`, `forbidden`, `conflict`, `not_found`, `unauthorized`, `storage_error`); a submitted value is never echoed back and driver text is never forwarded.
* `claude mcp add -e KEY=value` and `.mcp.json` `"env"` entries are stored in plaintext config files. Prefer an environment inherited from a `0600` file outside any repository.

## Capability manifest

`frontier_capabilities` (tool) and `frontier://capabilities` (resource) return: `mode`, `namespace`, `principal` (actor, operator, roles, namespaces, daily write limit; never the credential),
the exact `tools` with `kind` and `requires_role`, `not_available`, `record_kinds`, limits, the allowed transition states and the lease note. Payload JSON schemas: `frontier://schema/{kind}`.

`frontier_artifacts` searches declared artifact metadata and returns the exact
Evidence and producing Action links, context, assumptions, limitations and review
state. It never downloads or verifies bytes. The `payload_extensions` manifest
lists the optional provenance and whiteboard fields. Older strict clients may
reject these fields; do not strip them from an immutable record to force import.

## Exact start-up and smoke instructions

Everything below was executed (bounded scope, exit 0) against a private throwaway PostgreSQL 16 that is deleted at the end. It writes nothing but the schema:

```bash
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=300 bash quickstart.sh   # from the repository root
```

`quickstart.sh`:

```bash
set -euo pipefail
PGBIN=/usr/lib/postgresql/16/bin
T=$(mktemp -d /tmp/frontier-mcp-demo.XXXXXXXX); chmod 700 "$T"; mkdir "$T/socket"
"$PGBIN/initdb" -D "$T/data" --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8 >/dev/null
"$PGBIN/pg_ctl" -D "$T/data" -l "$T/pg.log" -o "-k $T/socket -c listen_addresses='' -c max_connections=20 -c shared_buffers=32MB" -w start >/dev/null
trap '"$PGBIN/pg_ctl" -D "$T/data" -m immediate -w stop >/dev/null 2>&1; rm -rf "$T"' EXIT
export FRONTIER_DSN="host=$T/socket dbname=postgres"
export PYTHONPATH="$PWD" OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python -m frontier init --namespace demo-node --schema demo
# Operator-only provisioning (never exposed over HTTP or MCP). The credential lives in the environment, not in an argument:
export FRONTIER_TOKEN="$(python -c 'import secrets; print("demo-" + secrets.token_urlsafe(32))')"
python - <<'PY'
import os
from frontier.store import Store
Store(os.environ["FRONTIER_DSN"], "demo-node", "demo").provision(
    os.environ["FRONTIER_TOKEN"], "agent-1", "operator-1", ["contributor"], ["demo-node"], 100)
PY
echo "--- read-only smoke"; python -m frontier mcp-smoke --namespace demo-node --schema demo
echo "--- write-enabled smoke (still writes nothing)"; python -m frontier mcp-smoke --namespace demo-node --schema demo --allow-write
```

Earlier worker smoke output, before the artifact tool was added (abridged; reported both smokes `"ok": true`):
* read-only: `"mode": "read_only"`, `"principal": null`, five tools, all `readOnly: true`.
* with `--allow-write`: `"mode": "write_enabled"`, principal `agent-1` / `operator-1` / `["contributor"]`, eight tools, three with `readOnly: false`, no credential in the output.

Running the server for a real client against your own node:

```bash
export FRONTIER_DSN='...'                                  # from your environment/secret store, never the repository
python -m frontier mcp --namespace NODE --schema public    # read-only
FRONTIER_TOKEN=... python -m frontier mcp --namespace NODE --schema public --allow-write
python -m frontier mcp-smoke --namespace NODE --schema public [--allow-write]     # official-SDK client round trip; read-only even with --allow-write
```

Client configuration (the shape; **not tested here**; adjust command/paths and check your client's environment-expansion support):

```json
{"mcpServers": {"frontier": {"command": "python", "args": ["-m", "frontier", "mcp", "--namespace", "NODE", "--schema", "public"],
  "env": {"FRONTIER_DSN": "${FRONTIER_DSN}"}}}}
```

## Tests (isolated database; `scripts/test_postgres.sh`)

`tests/test_interfaces.py`, 8 tests, all through the official SDK client over stdio against a per-test schema: read-only default; token present but no flag stays read-only; write mode fails closed
(no token, unknown token, reviewer-only principal, unreachable DSN with a password marker: none echoed); full proposal -> `ready` -> lease -> `running` -> `submitted` loop with idempotent retry and key-reuse
conflict, wrong `lease_id` refused, acceptance unreachable, same-operator reviewer refused and independent reviewer accepted; role gates are the store's (contributor cannot `ready`, issuer spoof refused);
credentials absent from schemas/outputs/stderr and invalid input not echoed; `mcp-smoke` round trip. Guard-removal mutations (token alone enables writes, token in manifest, errors echo exception text, a review tool
registered, principal check removed) each fail a test.

## Coupling and open points for the Frontier owner

* The earlier stdio implementation called private `Store._auth`. Both transports now use the existing public `Store.principal(token)`; store behavior is unchanged.
* Quota: every write counts against the principal's `daily_write_limit`; a retry with the same key does not consume more.
* A review tool is a separate decision. If wanted, it should be a distinct flag, require a reviewer-only token, and still go through `Store.review` unchanged.
* `site/` and `specs/` still describe the MCP server as read-only; SPEC text is not updated here.


## Share recorded Lean theorems

`frontier_proofs()` returns compact summaries for `geometric-similarity`,
`unit-algebra`, `cantilever-guard`, `steady-oxygen-bound` and
`scaled-threshold-intervals`. `family` accepts only one of those five names; `include_source` defaults to false. For example:

```python
await session.call_tool("frontier_proofs", {
    "family": "cantilever-guard", "include_source": True
})
```

This tool is anonymous wherever public claim reads are anonymous. It returns
assumptions, theorem names, recorded positive/negative exits, toolchain/mathlib
pins and per-file SHA256/byte counts with relative public artifact links.
A safe configured public hostname also supplies HTTPS links. Optional theory
text is bounded to 6,000 characters per family and explicitly reports truncation;
the full-file digest and download link remain available.

The five receipt digests are fixed in code. Original sources/checker dependencies
are checked by the existing source-matched gallery helper; published copies must
also match byte for byte. A missing, edited, symlinked or stale family is withheld
rather than reported as compiled. No caller supplies a path, code or formula, and
no Lean process, model, network fetch, Store write, review or acceptance occurs.
`recorded_compile` names a past receipt; `compile_executed` is false. These are
conditional mathematical statements, not proof of fish biology or feasibility.

The `scaled-threshold-intervals` family contains two generic interval statements,
two recorded-bound parametric instances, two nonempty-premise checks and four
rational counterexamples. Four false inequality/factor variants were rejected.
These are not ten biological laws. It exposes the exact witness, historical
reviewed source audit, independent returned-data review and validator download
pins alongside the Lean source and receipt. Every required dependency and
published copy must match; a changed witness/validator/audit withholds the whole
family. The tool never executes the validator. The 4,272-character theory fits
the existing 6,000-character optional source limit. Its certificate is conditional
on sampled closure brackets at StopTime1000, not source extraction, simulator
fidelity, a stochastic asymptotic threshold or biological validity.
