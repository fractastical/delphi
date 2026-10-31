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

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def verify(url: str) -> dict:
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
    args = parser.parse_args()
    result = asyncio.run(asyncio.wait_for(verify(args.url), timeout=120))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"checks_passed": len(result["checks"]), "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
