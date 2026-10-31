"""Bounded MCP projections over existing Frontier APIs.

This module adds no store policy, model schema, provider calls or execution path.
Read tools preserve the store's exact-reference/visibility checks; calculations
call only existing fixed, bounded local adapters and return ephemeral results.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .artifacts import ArtifactIndex
from .discovery import Discovery, GeminiEmbedder
from .graph import catalogue_report, view as graph_view
from .media import LocalMedia
from .models import Ref
from .store import FrontierError, Store


def register_surfaces(server, store: Store, register, *, read_annotations, public_host: str | None = None) -> None:
    """Register additional bounded read tools on the server built by ``frontier.mcp``."""
    # Cache-only query vectors are used when already present. Discovery.search
    # reports and falls back to lexical search if the embedder/cache is absent;
    # no anonymous (or authenticated) MCP query calls the embedding provider.
    embedder = GeminiEmbedder()
    discovery = Discovery(store, embedder)
    artifacts = ArtifactIndex(store)
    media = LocalMedia(Path(__file__).resolve().parents[1] / "site")

    def frontier_discover(query: Annotated[str, Field(min_length=1, max_length=200)],
                          kind: str | None = None,
                          limit: Annotated[int, Field(ge=1, le=20)] = 12,
                          mode: Literal["hybrid", "lexical"] = "hybrid") -> dict:
        """Search with cached hybrid vectors when available; otherwise explicitly fall back to lexical search, without provider calls."""
        result = discovery.search(query, kind=kind, limit=limit, mode=mode, cache_only=True)
        result["requested_mode"] = mode
        result["fallback_used"] = mode == "hybrid" and result["mode"] != "hybrid"
        result["provider_requests"] = embedder.requests
        result["search_policy"] = "MCP uses cached query embeddings only; a cache/index/provider absence yields lexical fallback and an explicit reason."
        return result

    def frontier_graph(target: Ref | None = None,
                       depth: Annotated[int, Field(ge=1, le=3)] = 1,
                       limit: Annotated[int, Field(ge=1, le=120)] = 60) -> dict:
        """Read a bounded public graph view around an exact version, or an overview; returns typed edges and truncation counts."""
        return graph_view(store, target.model_dump() if target else None, depth=depth, limit=limit)

    def frontier_catalogue() -> dict:
        """Return measured public-catalogue counts, unknown categories, and the report's record cap."""
        return catalogue_report(store)

    def frontier_project_inspect(target: Ref) -> dict:
        """Inspect one exact Project version and its pinned members; newer heads are reported, never substituted."""
        if target.kind != "Project":
            raise FrontierError("target must pin a Project")
        pinned = target.model_dump()
        return {"schema": "frontier.project.inspect/1", "project": store.get(pinned),
                "members": store.project_members(pinned),
                "scope": "Exact Project version; member pins and local review state are explicit; membership is not applicability or acceptance."}

    def frontier_artifact_inspect(sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")],
                                  limit: Annotated[int, Field(ge=1, le=20)] = 10) -> dict:
        """Inspect matching Evidence declarations and check for matching bytes in this release's guarded public artifacts tree."""
        digest = sha256.lower()
        declarations = artifacts.search(query=digest, limit=limit)["items"]
        declarations = [row for row in declarations if row["artifact"]["sha256"].lower() == digest]
        local = media.lookup(digest)
        for match in local["matches"]:
            match["public_url"] = f"https://{public_host}{match['href']}" if public_host else None
        return {"schema": "frontier.artifact.inspect/1", "sha256": digest, "declarations": declarations,
                "local_published_bytes": local, "preview": None,
                "scope": "Declarations are not byte verification. Local bytes are hash-checked by LocalMedia within the public artifacts subtree; remote URIs are never fetched. No text preview is available."}

    def frontier_simulate(model: Literal["bioelectric", "mechanobio"],
                          parameters: Annotated[dict, Field(description="Finite parameters for the selected allowlisted simulation model; no code or command fields.")]) -> dict:
        """Run one bounded allowlisted bioelectric or mechanobiology preview; returns an ephemeral SimulationResult, never accepted Evidence."""
        from .simulation_api import run_preview
        result = run_preview({"model": model, "parameters": parameters})
        result["mcp_policy"] = "Ephemeral bounded calculation only; no Action or Evidence is created, and no biological validation is implied."
        return result

    def frontier_engineer(parameters: Annotated[dict, Field(description="Finite request for the existing aircraft-constraint solver; code, commands and formulas are not accepted.")]) -> dict:
        """Run the existing bounded engineering-constraint solver; returns an ephemeral scoped calculation, not a biological finding."""
        from .engineering_api import solve_design
        result = solve_design(parameters)
        result["persisted"] = False
        result["accepted"] = False
        return result

    def frontier_formalize(request: Annotated[dict, Field(description="Finite expression request in frontier.formalize.request/1; no supplied code or shell command.")]) -> dict:
        """Run the bounded exact-expression/Lean proposal service; the result is not a persisted formal Evidence record."""
        from .formalize.service import propose
        return {"schema": "frontier.mcp.formalize/1", "persisted": False, "accepted": False,
                "result": propose(request),
                "scope": "A formalization result is a computation/proposal; no Evidence is created or independently reviewed by this tool."}

    def frontier_belief(scenario: Annotated[dict, Field(description="Finite scenario in frontier.beliefs.api/1; only the existing scenario grammar is accepted.")]) -> dict:
        """Run the bounded finite-scenario belief solver; consequences are conditional on declared inputs and remain uncalibrated."""
        from .beliefs_api import solve_scenario
        result = solve_scenario(scenario)
        result["persisted"] = False
        result["accepted"] = False
        return result

    for tool in (frontier_discover, frontier_graph, frontier_catalogue, frontier_project_inspect,
                 frontier_artifact_inspect, frontier_simulate, frontier_engineer, frontier_formalize,
                 frontier_belief):
        register(tool, read_annotations, "read", None)
