import asyncio
from contextlib import asynccontextmanager
import os
import subprocess
import tempfile
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
from threading import Thread

import pytest

from frontier.http import BoundedHTTPServer, make_server
from frontier.models import ref
from conftest import TOKENS, action, claim


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


ROOT = Path(__file__).resolve().parents[1]
READ_TOOLS = {"frontier_search", "frontier_get", "frontier_neighborhood", "frontier_events", "frontier_capabilities"}
WRITE_TOOLS = {"frontier_propose", "frontier_lease", "frontier_transition"}
SECRET_NAMES = {"token", "dsn", "password", "credential", "authorization", "secret", "api_key", "apikey"}


def server_env(store, token=None, dsn=None):
    env = {"FRONTIER_DSN": dsn or store.dsn, "PYTHONPATH": str(ROOT), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    if token:
        env["FRONTIER_TOKEN"] = token
    return env


@asynccontextmanager
async def session_for(store, token=None, allow_write=False, errlog=None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    args = ["-m", "frontier", "mcp", "--namespace", store.namespace, "--schema", store.schema] + (["--allow-write"] if allow_write else [])
    params = StdioServerParameters(command=sys.executable, args=args, env=server_env(store, token))
    async with stdio_client(params, errlog=errlog or sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def run(coro, timeout=60):
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


def val(result):
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


def test_official_mcp_stdio_reads_same_persisted_record(store):
    record = store.submit(TOKENS["alice"], "mcp-source", claim(store))["record"]

    async def exercise():
        async with session_for(store) as session:
            tools = (await session.list_tools()).tools
            assert {t.name for t in tools} == READ_TOOLS
            assert all(t.annotations.readOnlyHint for t in tools)
            value = val(await session.call_tool("frontier_get", {"target": ref(record)}))
            assert value["record"] == record
            assert (await session.call_tool("frontier_search", {"limit": 51})).isError
            caps = val(await session.call_tool("frontier_capabilities", {}))
            assert caps["mode"] == "read_only" and caps["principal"] is None and caps["namespace"] == store.namespace
            assert {t["name"] for t in caps["tools"]} == READ_TOOLS and "review" in " ".join(caps["not_available"])
            resources = {str(r.uri) for r in (await session.list_resources()).resources}
            assert "frontier://capabilities" in resources
            schema = json.loads((await session.read_resource("frontier://schema/Claim")).contents[0].text)
            assert "statement" in schema["properties"]
            assert json.loads((await session.read_resource("frontier://capabilities")).contents[0].text)["mode"] == "read_only"
    run(exercise())


def test_mcp_stays_read_only_when_a_token_is_merely_present(store):
    async def exercise():
        async with session_for(store, token=TOKENS["alice"], allow_write=False) as session:
            assert {t.name for t in (await session.list_tools()).tools} == READ_TOOLS
            assert val(await session.call_tool("frontier_capabilities", {}))["principal"] is None
            assert (await session.call_tool("frontier_propose", {"draft": claim(store), "idempotency_key": "x"})).isError
    run(exercise())
    assert store.search(kind="Claim")["results"] == []              # nothing was written


def mcp_cli(store, *extra, token=None, dsn=None):
    return subprocess.run([sys.executable, "-m", "frontier", "mcp", "--namespace", store.namespace, "--schema", store.schema, *extra],
                          env={**server_env(store, token, dsn), "PATH": os.environ["PATH"]}, input="", capture_output=True, text=True, timeout=30)


def test_mcp_write_mode_fails_closed_without_leaking(store):
    no_token = mcp_cli(store, "--allow-write")
    assert no_token.returncode == 2 and "FRONTIER_TOKEN" in no_token.stderr
    unknown = "wrong-token-marker-XYZ-0123456789"
    r = mcp_cli(store, "--allow-write", token=unknown)
    assert r.returncode == 2 and unknown not in r.stdout + r.stderr and "write tools not enabled" in r.stderr
    store.provision("test-only-reviewer-only-token-000", "rhea", "operator-r", ["reviewer"], [store.namespace], 10)
    r = mcp_cli(store, "--allow-write", token="test-only-reviewer-only-token-000")
    assert r.returncode == 2 and "cannot write this namespace as a contributor" in r.stderr
    marker = "s3cr3t-dsn-marker"
    r = mcp_cli(store, "--allow-write", token=TOKENS["alice"], dsn=f"host=/nonexistent-socket-dir dbname=x password={marker}")
    assert r.returncode == 2 and marker not in r.stdout + r.stderr


def test_mcp_write_roundtrip_from_proposal_to_independent_acceptance(store):
    from frontier.store import Forbidden
    errlog = tempfile.TemporaryFile("w+")
    claim_draft = claim(store)

    async def exercise():
        seen = []
        async with session_for(store, token=TOKENS["alice"], allow_write=True, errlog=errlog) as s:
            tools = (await s.list_tools()).tools
            names = {t.name for t in tools}
            assert names == READ_TOOLS | WRITE_TOOLS
            assert not any(w in n for n in names for w in ("review", "accept", "dispute", "import", "provision"))
            assert {t.name for t in tools if not t.annotations.readOnlyHint} == WRITE_TOOLS
            caps = val(await s.call_tool("frontier_capabilities", {}))
            assert caps["mode"] == "write_enabled" and caps["principal"]["actor"] == "alice" and caps["principal"]["operator"] == "operator-a"
            assert set(caps["principal"]["roles"]) == {"contributor", "coordinator"}
            # proposal: stored as 'proposed', never accepted; a retry with the same key is the same response; another body under that key conflicts
            first = val(await s.call_tool("frontier_propose", {"draft": claim_draft, "idempotency_key": "mcp-claim-1"}))
            assert first["local_status"] == "proposed"
            assert val(await s.call_tool("frontier_propose", {"draft": claim_draft, "idempotency_key": "mcp-claim-1"})) == first
            other = dict(claim_draft, id="another")
            clash = await s.call_tool("frontier_propose", {"draft": other, "idempotency_key": "mcp-claim-1"})
            assert clash.isError and "conflict" in clash.content[0].text
            seen.append(clash.content[0].text)
            claim_ref = ref(first["record"])
            # the action loop: propose -> ready (coordinator) -> lease -> running -> submitted
            act = val(await s.call_tool("frontier_propose", {"draft": action(store, claim_ref), "idempotency_key": "mcp-action-1"}))
            act_ref = ref(act["record"])
            assert val(await s.call_tool("frontier_get", {"target": act_ref}))["action"]["state"] == "proposed"
            val(await s.call_tool("frontier_transition", {"target": act_ref, "state": "ready", "idempotency_key": "mcp-ready"}))
            lease = val(await s.call_tool("frontier_lease", {"target": act_ref, "seconds": 120, "idempotency_key": "mcp-lease"}))
            lid = lease["lease_id"]
            bad = await s.call_tool("frontier_transition", {"target": act_ref, "state": "running", "lease_id": "not-the-lease", "idempotency_key": "mcp-bad"})
            assert bad.isError and "forbidden" in bad.content[0].text
            val(await s.call_tool("frontier_transition", {"target": act_ref, "state": "running", "lease_id": lid, "idempotency_key": "mcp-run"}))
            val(await s.call_tool("frontier_transition", {"target": act_ref, "state": "submitted", "lease_id": lid, "idempotency_key": "mcp-sub"}))
            assert val(await s.call_tool("frontier_get", {"target": act_ref}))["action"]["state"] == "submitted"
            # acceptance is unreachable through MCP
            for state in ("accepted", "disputed", "reviewed"):
                assert (await s.call_tool("frontier_transition", {"target": act_ref, "state": state, "idempotency_key": "mcp-" + state})).isError
            return act_ref, claim_ref, lid, seen
    act_ref, claim_ref, lid, seen = run(exercise())
    # independent boundary, enforced by the store and unchanged by MCP: same operator cannot accept, a different operator can
    with pytest.raises(Forbidden):
        store.review(TOKENS["alias"], "alias-review", assessment(act_ref, "alias"))
    accepted = store.review(TOKENS["bob"], "bob-review", assessment(act_ref, "bob"))
    assert accepted["local_status"] == "accepted"

    async def after():
        async with session_for(store) as s:
            got = val(await s.call_tool("frontier_get", {"target": act_ref}))
            assert got["action"]["state"] == "accepted" and got["local_review"]["status"] == "accepted"
    run(after())
    errlog.seek(0)
    server_stderr = errlog.read()
    assert TOKENS["alice"] not in "".join(seen) + server_stderr and lid not in server_stderr


def assessment(target, reviewer):
    from conftest import assessment as make
    return make(target, reviewer)


def test_mcp_role_gates_are_the_stores(store):
    async def exercise():
        async with session_for(store, token=TOKENS["carol"], allow_write=True) as s:
            caps = val(await s.call_tool("frontier_capabilities", {}))
            assert caps["principal"]["roles"] == ["contributor"]
            proposed = val(await s.call_tool("frontier_propose", {"draft": dict(claim(store), issuer="carol"), "idempotency_key": "carol-claim"}))
            act = val(await s.call_tool("frontier_propose", {"draft": dict(action(store, ref(proposed["record"])), issuer="carol"), "idempotency_key": "carol-act"}))
            r = await s.call_tool("frontier_transition", {"target": ref(act["record"]), "state": "ready", "idempotency_key": "carol-ready"})
            assert r.isError and "forbidden" in r.content[0].text.lower()
            spoof = await s.call_tool("frontier_propose", {"draft": dict(claim(store, id="spoof"), issuer="alice"), "idempotency_key": "carol-spoof"})
            assert spoof.isError and "forbidden" in spoof.content[0].text
    run(exercise())


def test_mcp_never_takes_or_returns_credentials_and_errors_do_not_echo_input(store):
    token, marker = TOKENS["alice"], "LEAK-MARKER-9f3a"
    errlog = tempfile.TemporaryFile("w+")

    async def exercise():
        blob = []
        async with session_for(store, token=token, allow_write=True, errlog=errlog) as s:
            for t in (await s.list_tools()).tools:
                blob.append(json.dumps(t.inputSchema))
                assert not (set(t.inputSchema.get("properties", {})) & SECRET_NAMES)
            blob.append(json.dumps(val(await s.call_tool("frontier_capabilities", {}))))
            blob.append((await s.read_resource("frontier://capabilities")).contents[0].text)
            bad = dict(claim(store), payload={"title": marker, "statement": marker})          # missing required fields
            r = await s.call_tool("frontier_propose", {"draft": bad, "idempotency_key": "leak-1"})
            assert r.isError and marker not in r.content[0].text and "invalid_request" in r.content[0].text
            blob.append(r.content[0].text)
            r = await s.call_tool("frontier_get", {"target": ref(store.submit(TOKENS["alice"], "x1", claim(store))["record"]) | {"version": "0" * 64}})
            assert r.isError
            blob.append(r.content[0].text)
        return "\n".join(blob)
    text = run(exercise())
    errlog.seek(0)
    assert token not in text and token not in errlog.read()


def test_mcp_smoke_command_is_a_read_only_client_roundtrip(store):
    base = [sys.executable, "-m", "frontier", "mcp-smoke", "--namespace", store.namespace, "--schema", store.schema]
    env = {**server_env(store), "PATH": os.environ["PATH"]}
    r = subprocess.run(base, env=env, capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["ok"] and out["mode"] == "read_only" and {t["name"] for t in out["tools"]} == READ_TOOLS
    r = subprocess.run(base + ["--allow-write"], env={**env, "FRONTIER_TOKEN": TOKENS["alice"]}, capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["mode"] == "write_enabled" and out["principal"]["actor"] == "alice"
    assert TOKENS["alice"] not in r.stdout + r.stderr and {t["name"] for t in out["tools"]} == READ_TOOLS | WRITE_TOOLS
    assert store.search()["results"] == []                              # the smoke test wrote nothing
    r = subprocess.run(base + ["--allow-write"], env=env, capture_output=True, text=True, timeout=60)      # no token => fail closed
    assert r.returncode != 0
