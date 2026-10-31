"""Official SDK 1.27.0 MCP interface over the persistent store.

DEFAULT is read-only (the bounded reads plus a capability manifest). Writes are an explicit opt-in:
`python -m frontier mcp --allow-write` with a process credential in FRONTIER_TOKEN. Even then:

* the credential comes ONLY from the process environment. No tool accepts a token, DSN or password argument and no tool output or error
  carries one (tests scan every output and every tool schema);
* every write calls the same `Store` method as the HTTP adapter (`submit`, `lease`, `transition`), so authorisation, role gates, namespace
  limits, quotas, idempotency and the append-only/immutability triggers are the store's, not re-implemented here;
* there is NO review/accept/dispute tool. Acceptance needs an independent operator acting with that operator's own credential
  (HTTP `/v1/reviews`); an agent holding a contributor token cannot reach it through this server. `import_bundle`, `provision`, `initialize`
  and anything that executes, fetches or publishes are not exposed either (SPEC-002: `provision` is never exposed over MCP).
"""
import functools
import json
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from .models import KINDS, MAX_BUNDLE_RECORDS, MAX_RECORD_BYTES, PAYLOADS, POLICY, SCHEMA, Ref
from .search import SEARCH_KIND, SearchIndex
from .artifacts import ArtifactIndex
from .store import FrontierError, Store

MANIFEST_VERSION = "frontier-mcp-capabilities-0.1"
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
# Append-only store: nothing is destroyed; a retry with the same idempotency key and request returns the stored response.
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
IdempotencyKey = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$",
                                      description="Caller-chosen retry key, 1..128 of A-Za-z0-9_.:-. Reuse it ONLY to retry the identical request.")]
TransitionState = Literal["ready", "running", "submitted", "blocked", "cancelled", "failed"]
NOT_AVAILABLE = [
    "review / accept / dispute: independent reviewers act through HTTP POST /v1/reviews with their own operator credential",
    "import_bundle, provision, initialize (operator-only)",
    "job execution, network fetch, publication (the store coordinates and records; it runs nothing)",
]


def _sanitised(exc: Exception) -> ToolError:
    """Typed, bounded errors. Never echo submitted values, tokens, DSNs or driver text."""
    if isinstance(exc, FrontierError):
        return ToolError(f"{exc.code}: {exc}")
    if isinstance(exc, ValidationError):
        problems = [{"loc": ".".join(str(x) for x in e["loc"]), "msg": e["msg"]}
                    for e in exc.errors(include_input=False, include_url=False, include_context=False)[:10]]
        return ToolError("invalid_request: " + json.dumps(problems))
    if isinstance(exc, (ValueError, TypeError, KeyError, RecursionError)):
        return ToolError("invalid_request: invalid bounded request")
    return ToolError("storage_error: transaction failed")


def _guard(fn):
    @functools.wraps(fn)
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except ToolError:
            raise
        except Exception as e:      # noqa: BLE001 - everything is mapped to a sanitised typed error
            raise _sanitised(e) from None
    return run


def resolve_principal(store: Store, token: str) -> dict:
    """The configured credential's identity, WITHOUT the credential. Uses the store's own authentication (read-only)."""
    with store.connection() as c:
        p = store._auth(c, token)       # noqa: SLF001 - reuse, not reimplement; a public Store.principal() would remove this coupling
    return {"actor": p["actor"], "operator": p["operator"], "roles": list(p["roles"]), "namespaces": list(p["namespaces"]),
            "daily_write_limit": p["daily_write_limit"]}


def make_mcp(store: Store, *, allow_write: bool = False, token: str | None = None) -> FastMCP:
    principal = None
    if allow_write:
        if not token:
            raise ValueError("write mode needs the process credential")
        principal = resolve_principal(store, token)             # fails closed on an unknown token (store.Unauthorized)
        if "contributor" not in principal["roles"] or store.namespace not in principal["namespaces"]:
            raise ValueError("the configured principal cannot write this namespace as a contributor; refusing to enable write tools")
    server = FastMCP("Delphi Frontier MCP", log_level="ERROR", instructions=(
        "Bounded access to a Delphi Frontier node. Call frontier_capabilities first: it states the mode, the configured principal (never the credential), "
        "the exact tools and what is deliberately not available. Exact versions, source assertions and node-local review status stay separate. "
        + ("WRITE MODE: frontier_propose, frontier_lease and frontier_transition act as the configured principal; there is no review/accept tool and "
           "acceptance needs an independent operator elsewhere." if allow_write else "READ-ONLY: no write tools are registered.")))
    tools: list[dict] = []

    def register(fn, annotations, kind, requires):
        tools.append({"name": fn.__name__, "kind": kind, "requires_role": requires, "summary": (fn.__doc__ or "").strip().split("\n")[0]})
        server.tool(annotations=annotations)(_guard(fn))

    index = SearchIndex(store)

    def frontier_search(query: str = "", kind: str | None = None, status: str | list[str] | None = None, limit: int = 20, after: str = "",
                        kinds: list[str] | None = None, source: str | None = None, scope: str | None = None, context: str | None = None,
                        include_history: bool = False, cursor: str = "") -> dict:
        """Search public records: GIN full-text plus literal text, exact version/id/source pins, kind/status/source/scope/context filters, bounded pages (max 50). Lexical only, no embeddings; relevance is not truth."""
        return index.query(query=query, kind=kind, kinds=kinds, status=status, source=source, scope=scope, context=context,
                           include_history=include_history, limit=limit, cursor=cursor, after=after)

    def frontier_get(target: Ref) -> dict:
        """Retrieve one exact public version and its separate node-local review status."""
        return store.get(target.model_dump())

    def frontier_neighborhood(target: Ref, limit: int = 20) -> dict:
        """Read up to 50 typed edges at depth one, including review/dispute relationships."""
        return store.neighborhood(target.model_dump(), limit=limit)

    def frontier_events(after: int = 0, limit: int = 20) -> dict:
        """Read an append-only public event page; consumers deduplicate event versions."""
        return store.events(after=after, limit=limit)

    def frontier_artifacts(query: str = "", role: str | None = None, evidence_kind: str | None = None,
                           limit: int = 20, cursor: str = "") -> dict:
        """Find public artifact declarations with evidence, action, context and review links. Does not fetch or verify bytes."""
        return ArtifactIndex(store).search(query, role=role, evidence_kind=evidence_kind, limit=limit, cursor=cursor)

    for f in (frontier_search, frontier_get, frontier_neighborhood, frontier_events, frontier_artifacts):
        register(f, READ, "read", None)

    def manifest() -> dict:
        return {"manifest_version": MANIFEST_VERSION, "server": "Delphi Frontier MCP", "record_schema": SCHEMA, "review_policy": POLICY,
                "namespace": store.namespace, "mode": "write_enabled" if allow_write else "read_only", "principal": principal,
                "credentials": "Process environment only (FRONTIER_DSN; FRONTIER_TOKEN with --allow-write). Never accepted as a tool argument, never returned.",
                "tools": tools, "not_available": NOT_AVAILABLE, "record_kinds": list(KINDS),
                "schema_resources": "frontier://schema/{kind} returns that kind's payload JSON schema",
                "payload_extensions": ["Claim.origin", "Problem.approach/scales/context_tags", "Action.inputs", "Evidence.relation/produced_by/artifacts"],
                "limits": {"max_record_bytes": MAX_RECORD_BYTES, "max_bundle_records": MAX_BUNDLE_RECORDS, "search_page_max": 50, "lease_seconds": [1, 600]},
                "search": {"engine": SEARCH_KIND, "filters": ["kind|kinds", "status", "source (URI prefix)", "scope", "context", "include_history"], "exact_pins": ["version", "record id", "source URI"], "pagination": "opaque next_cursor, pass back as cursor (or legacy after)"},
                "transition_states_via_mcp": ["ready (coordinator only)", "running", "submitted", "blocked", "cancelled", "failed"],
                "lease_id_note": "A lease_id is a bearer capability for that lease: keep it inside the leasing agent's session. It is not logged by this server.",
                "write_semantics": "Writes return the store's response verbatim: records start 'proposed'; MCP cannot make anything 'accepted'."}

    def frontier_capabilities() -> dict:
        """Manifest of this server: mode, configured principal (never the credential), exact tools, limits and what is deliberately unavailable."""
        return manifest()

    register(frontier_capabilities, READ, "read", None)

    if allow_write:
        def frontier_propose(draft: Annotated[dict, Field(description=(
                "A Draft: namespace (must equal this node), kind, id, issuer (must equal the principal's actor), source_uri, visibility, predecessor "
                "(exact current head version or null), payload. Payload shapes: resource frontier://schema/{kind}."))],
                             idempotency_key: IdempotencyKey) -> dict:
            """Propose a record version as the configured principal. The result is 'proposed', never accepted; Events are emitted by the store only."""
            return store.submit(token, idempotency_key, draft)

        def frontier_lease(target: Ref, seconds: Annotated[int, Field(ge=1, le=600)], idempotency_key: IdempotencyKey) -> dict:
            """Atomically lease one 'ready' (or expired) Action version for 1..600 seconds. Returns lease_id for later transitions."""
            return store.lease(token, idempotency_key, target.model_dump(), seconds)

        def frontier_transition(target: Ref, state: TransitionState, idempotency_key: IdempotencyKey,
                                lease_id: Annotated[str | None, Field(description=(
                                    "Required for running/submitted/blocked/failed/cancelled by the lease holder; omit for coordinator 'ready'."))] = None) -> dict:
            """Move an Action through the execution lifecycle (ready, running, submitted, blocked, cancelled, failed). Acceptance is not reachable here."""
            return store.transition(token, idempotency_key, target.model_dump(), state, lease_id)

        register(frontier_propose, WRITE, "write", "contributor")
        register(frontier_lease, WRITE, "write", "contributor")
        register(frontier_transition, WRITE, "write", "contributor (ready: coordinator)")

    @server.resource("frontier://capabilities", mime_type="application/json")
    def capabilities_resource() -> str:
        return json.dumps(manifest(), sort_keys=True)

    @server.resource("frontier://schema/{kind}", mime_type="application/json")
    def schema_resource(kind: str) -> str:
        if kind not in PAYLOADS:
            raise ValueError("unknown kind")
        return json.dumps(PAYLOADS[kind].model_json_schema(), sort_keys=True)

    return server
