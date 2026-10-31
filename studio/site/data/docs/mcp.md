# Frontier MCP server

Single-reader (collab), not Codex-reviewed. Official `mcp` SDK 1.27.0, stdio transport. Tested only with the official SDK client; **not tested with Claude Code, Codex or any other MCP client**.

## Modes

| | Default (`python -m frontier mcp ...`) | Opt-in (`... --allow-write`) |
|---|---|---|
| Tools | `frontier_search`, `frontier_get`, `frontier_neighborhood`, `frontier_events`, `frontier_capabilities` (all `readOnlyHint=true`) | the five above plus `frontier_propose`, `frontier_lease`, `frontier_transition` (`readOnlyHint=false`, `destructiveHint=false`, `idempotentHint=true`) |
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

## Credentials

* Only the process environment: `FRONTIER_DSN` always; `FRONTIER_TOKEN` with `--allow-write`. No tool has a token/DSN/password argument (a test scans every input schema).
* No output carries them: tests scan the capability manifest, resources, tool errors and the server's stderr for the token. Errors are typed and bounded
  (`invalid_request`, `forbidden`, `conflict`, `not_found`, `unauthorized`, `storage_error`); a submitted value is never echoed back and driver text is never forwarded.
* `claude mcp add -e KEY=value` and `.mcp.json` `"env"` entries are stored in plaintext config files. Prefer an environment inherited from a `0600` file outside any repository.

## Capability manifest

`frontier_capabilities` (tool) and `frontier://capabilities` (resource) return: `mode`, `namespace`, `principal` (actor, operator, roles, namespaces, daily write limit; never the credential),
the exact `tools` with `kind` and `requires_role`, `not_available`, `record_kinds`, limits, the allowed transition states and the lease note. Payload JSON schemas: `frontier://schema/{kind}`.

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

Output (abridged; full run: both smokes `"ok": true`):
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

* `frontier/mcp.py` calls the private `Store._auth` to resolve the configured principal for the manifest and the startup check. A public read-only `Store.principal(token)` would remove that; not added here (`store.py` is not mine).
* Quota: every write counts against the principal's `daily_write_limit`; a retry with the same key does not consume more.
* A review tool is a separate decision. If wanted, it should be a distinct flag, require a reviewer-only token, and still go through `Store.review` unchanged.
* `site/` and `specs/` still describe the MCP server as read-only; SPEC text is not updated here.
