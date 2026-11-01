"""Official SDK read-only proof-catalogue probe, stdio or deployed HTTP.

No token is read or sent. Stdio uses FRONTIER_DSN only for server setup; the
proof tool reads fixed local files and does not query or mutate records.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontier.proofs import FAMILY_IDS, MAX_SOURCE_CHARS  # noqa: E402


@asynccontextmanager
async def transport(url):
    if url:
        async with streamable_http_client(url) as (read, write, _):
            yield read, write
    else:
        env = {key: os.environ[key] for key in ["FRONTIER_DSN"] if key in os.environ}
        env.update(PYTHONPATH=str(Path(__file__).resolve().parents[1]), OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        params = StdioServerParameters(command=sys.executable, args=["-m", "frontier", "mcp", "--namespace", "delphi-frontier"], env=env)
        async with stdio_client(params) as (read, write):
            yield read, write


async def probe(url, out):
    async with transport(url) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            tools = (await session.list_tools()).tools
            tool = next(t for t in tools if t.name == "frontier_proofs")
            assert tool.annotations.readOnlyHint and not tool.annotations.openWorldHint
            caps = json.loads((await session.call_tool("frontier_capabilities", {})).content[0].text)
            assert caps["principal"] is None
            summary = await session.call_tool("frontier_proofs", {})
            assert not summary.isError
            result = json.loads(summary.content[0].text)
            assert {f["id"] for f in result["families"]} == set(FAMILY_IDS) and result["withheld"] == []
            assert not result["compile_executed"] and not result["biological_validation"]
            assert all("source" not in f for f in result["families"])
            sources = {}
            for family in FAMILY_IDS:
                full = await session.call_tool("frontier_proofs", {"family": family, "include_source": True})
                assert not full.isError
                source = json.loads(full.content[0].text)["families"][0]["source"]
                assert len(source["text"]) <= MAX_SOURCE_CHARS and not source["truncated"]
                assert sha256(source["text"].encode()).hexdigest() == source["full_file_sha256"]
                sources[family] = {"characters": len(source["text"]), "sha256": source["full_file_sha256"]}
    receipt = {"schema": "frontier.proofs.probe/1", "checked_at": datetime.now(timezone.utc).isoformat(),
               "transport": "anonymous HTTP" if url else "read-only stdio", "endpoint": url,
               "server": info.serverInfo.model_dump(), "tool_count": len(tools), "tool_schema": tool.inputSchema,
               "principal": None, "authorization_supplied": False, "summary": result,
               "optional_source_characters": len(source["text"]), "optional_source_SHA_matches": True,
               "optional_sources": sources,
               "writes": 0, "compile_executed": False}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print({"families": len(sources), "tools": len(tools), "optional_source_SHA_matches": True, "writes": 0, "compile_executed": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Existing MCP endpoint; omitted uses local stdio. No server is deployed by this probe.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(probe(args.url, args.out))
