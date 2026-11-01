"""Bounded MCP projections over existing Frontier APIs.

This module adds no store policy, model schema, provider calls or execution path.
Read tools preserve the store's exact-reference/visibility checks; calculations
call only existing fixed, bounded local adapters and return ephemeral results.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .artifacts import ArtifactIndex
from .discovery import Discovery, GeminiEmbedder
from .graph import catalogue_report, view as graph_view
from .media import LocalMedia
from .models import Ref
from .store import FrontierError, Store

MAX_DESIGN_REQUEST_BYTES = 64 * 1024
MAX_DESIGN_DEPTH = 8
MAX_DESIGN_NODES = 8192
MAX_DESIGN_STRING_CHARS = 2048
MAX_DESIGN_PARAMETERS = 8
MAX_DESIGN_READOUTS = 12
MAX_DESIGN_CANDIDATES = 12
MAX_DESIGN_OBSERVATIONS = 32


def _check_design_request_limits(contract: dict) -> None:
    """Bound JSON traversal and matrix dimensions before numerical work starts."""
    try:
        encoded = json.dumps(contract, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise ValueError("request must be finite JSON data") from None
    if len(encoded) > MAX_DESIGN_REQUEST_BYTES:
        raise ValueError("experimental-design request exceeds 65,536 bytes")

    nodes = 0

    def visit(value, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_DESIGN_NODES:
            raise ValueError("experimental-design request has too many values")
        if depth > MAX_DESIGN_DEPTH:
            raise ValueError("experimental-design request is nested too deeply")
        if isinstance(value, str):
            if len(value) > MAX_DESIGN_STRING_CHARS:
                raise ValueError("experimental-design string exceeds 2,048 characters")
        elif isinstance(value, dict):
            if len(value) > 64:
                raise ValueError("experimental-design object has too many fields")
            for key, item in value.items():
                if not isinstance(key, str) or len(key) > 64:
                    raise ValueError("experimental-design object key is invalid or too long")
                visit(item, depth + 1)
        elif isinstance(value, list):
            if len(value) > 64:
                raise ValueError("experimental-design list exceeds 64 entries")
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("experimental-design numbers must be finite")
        elif value is not None and not isinstance(value, (bool, int, float)):
            raise ValueError("experimental-design request must contain JSON values only")

    visit(contract, 0)
    if not isinstance(contract, dict):
        raise ValueError("contract must be an object")
    parameters = contract.get("parameters")
    if isinstance(parameters, dict) and isinstance(parameters.get("names"), list) and len(parameters["names"]) > MAX_DESIGN_PARAMETERS:
        raise ValueError("experimental-design supports at most 8 parameters")
    readouts = contract.get("readouts")
    if isinstance(readouts, list) and len(readouts) > MAX_DESIGN_READOUTS:
        raise ValueError("experimental-design supports at most 12 readouts")
    designs = contract.get("designs")
    if isinstance(designs, list):
        if len(designs) > MAX_DESIGN_CANDIDATES:
            raise ValueError("experimental-design supports at most 12 candidate designs")
        for design in designs:
            if not isinstance(design, dict):
                continue  # The core validator will report its bounded shape error.
            observations = design.get("observations")
            if isinstance(observations, list) and len(observations) > MAX_DESIGN_OBSERVATIONS:
                raise ValueError("each candidate supports at most 32 observation rows")
            batches = design.get("batch_count")
            if isinstance(batches, int) and not isinstance(batches, bool) and batches > 16:
                raise ValueError("each candidate supports at most 16 batches")
            if isinstance(observations, list):
                for observation in observations:
                    if isinstance(observation, dict):
                        repeats = observation.get("technical_repeat")
                        if isinstance(repeats, int) and not isinstance(repeats, bool) and repeats > 64:
                            raise ValueError("technical_repeat is bounded to 64")
    for field, maximum in (("source_claims", 64), ("input_datasets", 64)):
        values = contract.get(field)
        if isinstance(values, list) and len(values) > maximum:
            raise ValueError(f"{field} supports at most {maximum} entries")


def register_surfaces(server, store: Store, register, *, read_annotations, public_host: str | None = None) -> None:
    """Register additional bounded read tools on the server built by ``frontier.mcp``."""
    # Cache-only query vectors are used when already present. Discovery.search
    # reports and falls back to lexical search if the embedder/cache is absent;
    # no anonymous (or authenticated) MCP query calls the embedding provider.
    embedder = GeminiEmbedder()
    discovery = Discovery(store, embedder)
    artifacts = ArtifactIndex(store)
    media = LocalMedia(Path(__file__).resolve().parents[1] / "site", scan_ttl=10)

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

    def frontier_design_context(target: Ref,
                                limit: Annotated[int, Field(ge=1, le=50)] = 20,
                                cursor: Annotated[str | None, Field(max_length=16)] = None) -> dict:
        """Read bounded exact-version Project/member annotations with explicit pagination; challenges and replies never settle or resolve the design."""
        from .design_review import project_design_context
        return project_design_context(store, target.model_dump(), limit=limit, cursor=cursor)

    def frontier_artifact_inspect(sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")],
                                  limit: Annotated[int, Field(ge=1, le=20)] = 10,
                                  include_text: bool = False,
                                  max_chars: Annotated[int, Field(ge=1, le=16_000)] = 8000) -> dict:
        """Inspect exact-hash declarations and published bytes; optionally read a bounded UTF-8 JSON/text/CSV excerpt after verifying its complete file hash."""
        digest = sha256.lower()
        declarations = artifacts.search(query=digest, limit=limit)["items"]
        declarations = [row for row in declarations if row["artifact"]["sha256"].lower() == digest]
        local = media.lookup(digest)
        for match in local["matches"]:
            match["public_url"] = f"https://{public_host}{match['href']}" if public_host else None
        return {"schema": "frontier.artifact.inspect/1", "sha256": digest, "declarations": declarations,
                "local_published_bytes": local,
                "preview": media.text_preview(digest, max_chars=max_chars) if include_text else None,
                "scope": "Declarations are not byte verification. Local bytes are hash-checked within the public artifacts subtree; remote URIs are never fetched. Optional text excerpts require a matching complete-file hash and retain explicit size and truncation limits."}

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

    def frontier_plan_experiments(contract: Annotated[dict, Field(description=(
            "One complete frontier.experimental-design.request/1 contract. Bounded prospective covariance only; response values, commands and arbitrary code are not accepted."))]) -> dict:
        """Compare bounded linear-Gaussian experiment designs prospectively; returns no measurements and makes no Action, Store, lab or cloud writes."""
        _check_design_request_limits(contract)
        from engineering.experimental_design import plan_experiments
        result = plan_experiments(contract)
        result["mcp_policy"] = {
            "persisted": False,
            "accepted": False,
            "observed_result": None,
            "measurement_rows": [],
            "scope": "Prospective covariance under the submitted assumptions only. This tool does not execute an experiment or queue its ActionProposal.",
        }
        return result

    for tool in (frontier_discover, frontier_graph, frontier_catalogue, frontier_project_inspect, frontier_design_context,
                 frontier_artifact_inspect, frontier_simulate, frontier_engineer, frontier_formalize,
                 frontier_belief, frontier_plan_experiments):
        register(tool, read_annotations, "read", None)
