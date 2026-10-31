"""Check the public MCP with the official client; never submit a valid write.

Run in a bounded systemd scope. Receipts contain public metadata and hashes only.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Running this file directly puts deploy/, rather than the checkout, on sys.path.
# Expanded checks reuse the repository's fixed request fixtures.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def verify(url: str, expanded: bool = False) -> dict:
    checks = []
    responses = {}

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
        if not passed:
            raise ValueError("MCP check failed: " + name)

    def value(result):
        check("tool result has no error", not result.isError)
        return json.loads(result.content[0].text)

    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                responses["server"] = initialized.serverInfo.model_dump()
                check("official SDK initialization", initialized.serverInfo.name == "Delphi Frontier MCP")
                names = sorted(t.name for t in (await session.list_tools()).tools)
                check("read and contribution tools discoverable", all(n in names for n in (
                    "frontier_capabilities", "frontier_search", "frontier_get", "frontier_propose")))
                responses["tools"] = names
                caps = value(await session.call_tool("frontier_capabilities", {}))
                check("anonymous public identity", caps["principal"] is None and caps["anonymous_reads"] is True)
                check("project and annotation schemas advertised", {"Project", "Annotation"} <= set(caps["record_kinds"]))
                found = value(await session.call_tool("frontier_search", {"query": "fish", "limit": 3}))
                check("public fish search returns records", bool(found.get("results")))
                responses["search_sha256"] = hashlib.sha256(json.dumps(found, sort_keys=True).encode()).hexdigest()
                schema = await session.read_resource("frontier://schema/Project")
                check("project schema resource readable", bool(schema.contents))
                if expanded:
                    expected = {"frontier_discover", "frontier_graph", "frontier_catalogue",
                                "frontier_project_inspect", "frontier_artifact_inspect",
                                "frontier_simulate", "frontier_engineer", "frontier_formalize",
                                "frontier_belief", "frontier_design_context"}
                    check("expanded workspace tools discoverable", expected <= set(names))
                    discovery = value(await session.call_tool("frontier_discover", {"query": "fish"}))
                    check("discovery returns explicit mode without provider calls",
                          bool(discovery.get("items")) and discovery["provider_requests"] == 0
                          and "fallback_used" in discovery)
                    projects = value(await session.call_tool("frontier_search", {"kind": "Project", "limit": 3}))
                    check("live Project available", bool(projects.get("results")))
                    target = projects["results"][0]["ref"]
                    project = value(await session.call_tool("frontier_project_inspect", {"target": target}))
                    check("Project exact pin preserved", project["project"]["record"]["version"] == target["version"])
                    context = value(await session.call_tool("frontier_design_context", {"target": target, "limit": 20}))
                    check("design context preserves exact Project and bounded discussion",
                          context["schema"] == "frontier.project.design-context/1"
                          and context["project"]["record"]["version"] == target["version"]
                          and context["pagination"]["returned"] == len(context["annotations"]) <= 20)
                    responses["design_context"] = {"target": target, "returned": len(context["annotations"]),
                                                   "sha256": hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()}
                    graph = value(await session.call_tool("frontier_graph", {"target": target, "limit": 20}))
                    check("graph exact pin preserved", graph["scope"]["target_ref"] == target)
                    counts = value(await session.call_tool("frontier_catalogue", {}))
                    check("catalogue counted records", counts["scope"]["records_read"] > 0)
                    simulation = value(await session.call_tool("frontier_simulate", {
                        "model": "mechanobio", "parameters": {"duration_s": 1, "frame_count": 5}}))
                    check("simulation actually completed without persistence",
                          simulation["status"] == "completed" and simulation["persisted"] is False
                          and bool(simulation["result"]["frames"]))
                    engineering = value(await session.call_tool("frontier_engineer", {"parameters": {
                        "rho": "1.225", "cl_max": "1", "mass": "0.05", "area": "0.01", "span": "0.25", "speed": "12"}}))
                    check("installed solver calculated feasible scoped design",
                          engineering["result"]["status"] == "feasible" and engineering["persisted"] is False)
                    from engineering.formalize.cases import cantilever_request
                    formal = value(await session.call_tool("frontier_formalize", {"request": cantilever_request()}))
                    check("formalization remains an unaccepted proposal", formal["accepted"] is False and formal["persisted"] is False)
                    from frontier.beliefs import EXAMPLE_SCENARIO
                    belief = value(await session.call_tool("frontier_belief", {"scenario": EXAMPLE_SCENARIO}))
                    check("belief remains conditional and uncalibrated", belief["calibrated"] is False and belief["persisted"] is False)
                    model = Path(__file__).resolve().parents[1] / "site/artifacts/print/stl/A-precursor-short-fin.stl"
                    digest = hashlib.sha256(model.read_bytes()).hexdigest()
                    artifact = value(await session.call_tool("frontier_artifact_inspect", {"sha256": digest}))
                    check("published print bytes found by exact digest", bool(artifact["local_published_bytes"]["matches"]))
                    responses["expanded"] = {"project_ref": target, "artifact_sha256": digest,
                                             "discovery_mode": discovery["mode"], "simulation_status": simulation["status"]}
                # Deliberately invalid draft cannot become a record even if the
                # anonymous permission guard regresses. Check the auth error,
                # rather than accepting schema validation as authorization proof.
                denied = await session.call_tool("frontier_propose", {
                    "draft": {}, "idempotency_key": "publish-check-invalid-anonymous-draft"})
                check("anonymous proposal denied before validation", denied.isError and "unauthorized" in denied.content[0].text)
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "frontier-publish-check", "version": "1"}}}
        invalid = await http.post(url, headers={"Accept": "application/json, text/event-stream",
                                                "Authorization": "Bearer invalid-publication-test"}, json=init)
        check("invalid supplied token rejected", invalid.status_code == 401)
        check("plain browser GET is not MCP transport", (await http.get(url)).status_code == 405)
        system = await http.get(url.removesuffix("/mcp") + "/api/system")
        check("public system metadata readable", system.status_code == 200)
        responses["web_build"] = system.json().get("build")
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "endpoint": url,
            "transport": "Streamable HTTP", "checks": checks, "responses": responses,
            "scientific_records_written": 0,
            "scope": "Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://frontier.morphoswarm.ai/mcp")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expanded", action="store_true", help="Exercise the deployed workspace tools and bounded calculations")
    args = parser.parse_args()
    result = asyncio.run(asyncio.wait_for(verify(args.url, args.expanded), timeout=120))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"checks_passed": len(result["checks"]), "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
