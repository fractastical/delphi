"""Read exact imported public records through official MCP and anonymous HTTPS."""

import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

BASE = "https://frontier.morphoswarm.ai"


async def check(plan_path, out):
    plan = json.loads(plan_path.read_text())
    refs = plan["bundles"][0]["refs"]
    targets = [next(r for r in refs if r["kind"] == kind) for kind in ["Claim", "Evidence"]]
    checks = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as http:
        health = await http.get(BASE + "/api/health")
        health.raise_for_status()
        async with streamable_http_client(BASE + "/mcp", http_client=http) as (reader, writer, _):
            async with ClientSession(reader, writer) as session:
                info = await session.initialize()
                caps = await session.call_tool("frontier_capabilities", {})
                caps = json.loads(caps.content[0].text)
                if caps["principal"] is not None or caps["anonymous_reads"] is not True:
                    raise ValueError("Expected anonymous public MCP identity")
                for ref in targets:
                    result = await session.call_tool("frontier_get", {"target": ref})
                    if result.isError:
                        raise ValueError("Public exact MCP read failed")
                    got = json.loads(result.content[0].text)
                    if got["record"]["version"] != ref["version"] or got["local_review"]["status"] != "imported_unreviewed":
                        raise ValueError("Public MCP record/status differs")
                    url = BASE + "/api/record?" + urlencode(ref)
                    response = await http.get(url)
                    response.raise_for_status()
                    api = response.json()
                    if api["record"] != got["record"] or api["local_status"] != "imported_unreviewed":
                        raise ValueError("Anonymous API record/status differs")
                    checks.append({"ref": ref, "public_url": url, "http_status": response.status_code,
                                   "mcp_exact_record_match": True, "mcp_status": "imported_unreviewed",
                                   "api_body_sha256": sha256(response.content).hexdigest(), "api_body_bytes": len(response.content)})
    receipt = {"schema": "frontier.observed-allometry.public-readback/1", "checked_at": datetime.now(timezone.utc).isoformat(),
               "plan_sha256": plan["plan_sha256"], "anonymous": True, "authorization_header_supplied": False,
               "mcp_server": info.serverInfo.model_dump(), "health": health.json(), "checks": checks,
               "writes": 0, "scope": "Exact public Claim/Evidence readback and separate unreviewed status, not scientific review or validation"}
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print({"anonymous_MCP_and_HTTP_exact_reads": len(checks), "writes": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(check(args.plan, args.out))
