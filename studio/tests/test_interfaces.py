import asyncio
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
from threading import Thread

import pytest

from frontier.http import BoundedHTTPServer, make_server
from frontier.models import ref
from conftest import TOKENS, claim


def test_http_real_authenticated_proposal_and_shared_read(store):
    server = make_server(store)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def request(path, data, token=None, key=None, origin=None):
        c = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if key:
            headers["Idempotency-Key"] = key
        if origin:
            headers["Origin"] = origin
        c.request("POST", path, json.dumps(data), headers)
        response = c.getresponse()
        result = response.status, json.loads(response.read())
        c.close()
        return result
    try:
        draft = claim(store)
        assert request("/v1/proposals", {"draft": draft}, key="no-token")[0] == 401
        code, proposed = request("/v1/proposals", {"draft": draft}, TOKENS["alice"], "http-proposal")
        assert code == 200
        assert proposed["local_status"] == "proposed"
        code, fetched = request("/v1/read/get", {"target": ref(proposed["record"])})
        assert code == 200 and fetched["record"] == proposed["record"]
        assert store.get(ref(proposed["record"])) == fetched
        assert request("/v1/read/search", {"limit": 51})[0] == 400
        assert request("/v1/read/search", {}, origin="https://untrusted.example")[0] == 400
        assert request("/v1/actions/transition", {"target": ref(proposed["record"]), "state": "accepted"}, TOKENS["alice"], "bad")[0] == 400
        assert request("/v1/read/search", {"token": TOKENS["alice"]})[0] == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    with pytest.raises(ValueError):
        BoundedHTTPServer(("0.0.0.0", 0), object)


def test_official_mcp_stdio_reads_same_persisted_record(store):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    record = store.submit(TOKENS["alice"], "mcp-source", claim(store))["record"]

    async def exercise():
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "frontier", "mcp", "--namespace", store.namespace, "--schema", store.schema],
            env={"FRONTIER_DSN": store.dsn, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                 "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 4
                assert all(t.annotations.readOnlyHint for t in tools.tools)
                result = await session.call_tool("frontier_get", {"target": ref(record)})
                assert not result.isError
                value = json.loads(result.content[0].text)
                assert value["record"] == record
                oversized = await session.call_tool("frontier_search", {"limit": 51})
                assert oversized.isError
    asyncio.run(asyncio.wait_for(exercise(), timeout=30))
