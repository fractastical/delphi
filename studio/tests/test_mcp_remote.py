"""Remote Streamable HTTP MCP: the official 1.27 SDK client against a real `python -m frontier mcp --transport http` process and an isolated PostgreSQL schema.
Two distinct principals, wrong role, absent/wrong auth, idempotency, host/origin/path/body/concurrency bounds, and no credential anywhere in outputs. stdio is covered by
tests/test_interfaces.py (unchanged)."""
import asyncio
import http.client
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from conftest import TOKENS, action, claim
from frontier.models import ref

ROOT = Path(__file__).resolve().parents[1]
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
RHEA = "test-only-reviewer-only-token-0000000"
READ_TOOLS = {"frontier_search", "frontier_get", "frontier_neighborhood", "frontier_events", "frontier_artifacts", "frontier_capabilities", "frontier_proofs",
              "frontier_discover", "frontier_graph", "frontier_catalogue", "frontier_project_inspect", "frontier_artifact_inspect",
              "frontier_design_context", "frontier_simulate", "frontier_engineer", "frontier_formalize", "frontier_belief", "frontier_plan_experiments"}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Remote:
    def __init__(self, store, allow_write=True, extra_env=None, public_read=False):
        self.port = free_port()
        self.errfile = open(f"/tmp/mcp-remote-{self.port}.err", "w+")
        env = {"PATH": os.environ["PATH"], "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(ROOT), "OMP_NUM_THREADS": "1", **(extra_env or {})}
        args = [sys.executable, "-m", "frontier", "mcp", "--transport", "http", "--mcp-port", str(self.port), "--namespace", store.namespace, "--schema", store.schema]
        self.proc = subprocess.Popen(args + (["--allow-write"] if allow_write else []) + (["--public-read"] if public_read else []), env=env, stdout=subprocess.DEVNULL, stderr=self.errfile)
        for _ in range(150):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("remote MCP did not start")
        self.url = f"http://127.0.0.1:{self.port}/mcp"

    def stderr(self):
        self.errfile.flush()
        self.errfile.seek(0)
        return self.errfile.read()

    def close(self):
        self.proc.terminate()
        self.proc.wait(10)
        self.errfile.close()
        os.unlink(f"/tmp/mcp-remote-{self.port}.err")

    def raw(self, method="POST", path="/mcp", body=None, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        h = {"Host": host or f"127.0.0.1:{self.port}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream", **(headers or {})}
        data = json.dumps(body).encode() if isinstance(body, (dict, list)) else (body if isinstance(body, bytes) else None)
        if data is not None and "Content-Length" not in h and h.get("Transfer-Encoding") is None:
            h["Content-Length"] = str(len(data))
        for k, v in h.items():
            if v is not None:
                c.putheader(k, v)
        c.endheaders(data)
        r = c.getresponse()
        out = (r.status, {k.lower(): v for k, v in r.getheaders()}, r.read())
        c.close()
        return out


@pytest.fixture
def remote(store):
    store.provision(RHEA, "rhea", "operator-r", ["reviewer"], [store.namespace], 10)
    r = Remote(store)
    yield r
    r.close()


@pytest.fixture
def readonly_remote(store):
    r = Remote(store, allow_write=False)
    yield r
    r.close()


@asynccontextmanager
async def client(remote, token):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as http:
        async with streamable_http_client(remote.url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as s:
                await s.initialize()
                yield s


def val(result):
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


def run(coro, timeout=90):
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


# ------------------------------------------------------------------ authentication is per request and header-only
def test_absent_wrong_and_malformed_credentials_are_401_and_nothing_is_echoed(remote):
    for headers in ({}, {"Authorization": "Bearer wrong-wrong-wrong-wrong-wrong-0000"}, {"Authorization": "Bearer short"}, {"Authorization": "Basic " + "x" * 30},
                    {"Authorization": "Bearer " + TOKENS["alice"][:-1]}, {"Authorization": "bearer"}):
        s, h, body = remote.raw(body=INIT, headers=headers)
        assert s == 401 and b"invalid_token" in body and "bearer" in h["www-authenticate"].lower() and "resource_metadata" not in h["www-authenticate"]
        assert TOKENS["alice"].encode() not in body and b"wrong-wrong" not in body
    assert remote.raw(body=INIT, headers={"Authorization": "Bearer " + TOKENS["alice"]})[0] == 200


def test_a_token_in_the_query_string_is_refused_even_with_a_valid_header(remote):
    for path in (f"/mcp?access_token={TOKENS['alice']}", f"/mcp?token={TOKENS['alice']}", "/mcp?x=1"):
        s, h, body = remote.raw(path=path, body=INIT, headers={"Authorization": "Bearer " + TOKENS["alice"]})
        assert s == 400 and TOKENS["alice"].encode() not in body
        assert remote.raw(path=path, body=INIT)[0] == 400                                       # and with no header at all: refused before auth
    time.sleep(0.2)
    assert TOKENS["alice"] not in remote.stderr()


def test_failed_authentications_are_throttled_per_client(store):
    r = Remote(store)
    try:
        codes = [r.raw(body=INIT, headers={"Authorization": "Bearer nope-nope-nope-nope-nope-nope-1"})[0] for _ in range(10)]
        assert codes == [401] * 10
        s, h, _ = r.raw(body=INIT, headers={"Authorization": "Bearer " + TOKENS["alice"]})
        assert s == 429 and h["retry-after"] == "60"                                            # even a good credential waits out the block
    finally:
        r.close()


# ------------------------------------------------------------------ transport bounds
def test_host_origin_path_method_and_body_bounds(remote):
    good = {"Authorization": "Bearer " + TOKENS["alice"]}
    assert remote.raw(body=INIT, headers=good, host="evil.example")[0] == 421
    assert remote.raw(body=INIT, headers=good, host="frontier.morphoswarm.ai")[0] == 200       # the name nginx forwards
    assert remote.raw(body=INIT, headers={**good, "Origin": "https://evil.example"})[0] == 403
    assert remote.raw(body=INIT, headers={**good, "Origin": "https://frontier.morphoswarm.ai"})[0] == 200
    assert remote.raw(body=INIT, headers={**good, "Content-Type": "text/plain"})[0] == 400
    for path in ("/", "/mcp/", "/MCP", "/mcp/x", "/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp", "/sse", "/messages/"):
        assert remote.raw(path=path, body=INIT, headers=good)[0] == 404, path
    for method in ("GET", "PUT", "DELETE", "PATCH"):
        s, h, _ = remote.raw(method=method, headers=good)
        assert s == 405 and h["allow"] == "POST", method
    assert remote.raw(body=b"x" * 131073, headers=good)[0] == 413
    assert remote.raw(body=b"{" + b" " * 100000 + b"}", headers=good)[0] in (200, 400, 422)    # within the bound it reaches the SDK's own parser
    s, _, _ = remote.raw(body=None, headers={**good, "Content-Length": None})
    assert s == 411
    assert remote.raw(body=b"x", headers={**good, "Transfer-Encoding": "chunked", "Content-Length": None})[0] == 400
    assert remote.raw(body=b"x", headers={**good, "Content-Length": "abc"})[0] == 400


def test_responses_are_plain_json_with_no_session_state(remote):
    s, h, body = remote.raw(body=INIT, headers={"Authorization": "Bearer " + TOKENS["alice"]})
    assert s == 200 and h["content-type"].startswith("application/json") and "mcp-session-id" not in h
    assert json.loads(body)["result"]["serverInfo"]["name"] == "Delphi Frontier MCP"


# ------------------------------------------------------------------ official SDK client, two distinct principals
def test_two_principals_interleaved_each_act_only_as_themselves(remote, store):
    async def go():
        async with client(remote, TOKENS["alice"]) as a, client(remote, TOKENS["carol"]) as c:
            caps_a = val(await a.call_tool("frontier_capabilities", {}))
            caps_c = val(await c.call_tool("frontier_capabilities", {}))
            caps_a2 = val(await a.call_tool("frontier_capabilities", {}))                       # alice again after carol: no context bleed
            assert caps_a["principal"]["actor"] == caps_a2["principal"]["actor"] == "alice" and caps_c["principal"]["actor"] == "carol"
            assert caps_a["principal"]["operator"] == "operator-a" and caps_c["principal"]["operator"] == "operator-c"
            assert set(caps_a["principal"]["roles"]) == {"contributor", "coordinator"} and caps_c["principal"]["roles"] == ["contributor"]
            assert caps_a["mode"] == "write_enabled" and "streamable-http" in caps_a["transport"] and "Authorization: Bearer" in caps_a["credentials"]
            names = {t["name"] for t in caps_a["tools"]}
            assert {"frontier_propose", "frontier_lease", "frontier_transition"} <= names and not any(w in n for n in names for w in ("review", "accept", "import", "provision", "execute"))
            # concurrent writes by two principals, each stored under its own identity
            ra, rc = await asyncio.gather(
                a.call_tool("frontier_propose", {"draft": claim(store, id="remote-a", issuer="alice"), "idempotency_key": "k-a"}),
                c.call_tool("frontier_propose", {"draft": claim(store, id="remote-c", issuer="carol"), "idempotency_key": "k-c"}))
            assert val(ra)["record"]["issuer"] == "alice" and val(rc)["record"]["issuer"] == "carol"
            # identity comes from the credential, not the draft: carol cannot write as alice
            spoof = await c.call_tool("frontier_propose", {"draft": claim(store, id="spoof", issuer="alice"), "idempotency_key": "k-spoof"})
            assert spoof.isError and "forbidden" in spoof.content[0].text
            # either principal reads the other's public record
            got = val(await a.call_tool("frontier_get", {"target": ref(val(rc)["record"])}))
            assert got["record"]["issuer"] == "carol" and got["local_review"]["status"] == "proposed"
            return caps_a, caps_c
    caps_a, caps_c = run(go())
    assert caps_a["principal"] != caps_c["principal"]


def test_wrong_role_is_the_stores_decision_not_the_transports(remote, store):
    async def go():
        async with client(remote, RHEA) as rhea, client(remote, TOKENS["carol"]) as carol, client(remote, TOKENS["alice"]) as alice:
            r = await rhea.call_tool("frontier_propose", {"draft": claim(store, id="by-reviewer", issuer="rhea"), "idempotency_key": "r1"})
            assert r.isError and "forbidden" in r.content[0].text.lower()                       # reviewer-only principal cannot propose
            claim_rec = val(await alice.call_tool("frontier_propose", {"draft": claim(store, id="c1"), "idempotency_key": "p1"}))["record"]
            act = val(await alice.call_tool("frontier_propose", {"draft": action(store, ref(claim_rec)), "idempotency_key": "p2"}))["record"]
            denied = await carol.call_tool("frontier_transition", {"target": ref(act), "state": "ready", "idempotency_key": "t1"})
            assert denied.isError and "forbidden" in denied.content[0].text.lower()             # contributor without coordinator cannot mark ready
            assert val(await alice.call_tool("frontier_transition", {"target": ref(act), "state": "ready", "idempotency_key": "t2"}))["state"] == "ready"
            lease = val(await carol.call_tool("frontier_lease", {"target": ref(act), "seconds": 60, "idempotency_key": "l1"}))
            stolen = await alice.call_tool("frontier_transition", {"target": ref(act), "state": "running", "lease_id": lease["lease_id"], "idempotency_key": "t3"})
            assert stolen.isError and "forbidden" in stolen.content[0].text.lower()             # alice cannot use carol's lease: the lease is bound to the principal
            assert val(await carol.call_tool("frontier_transition", {"target": ref(act), "state": "running", "lease_id": lease["lease_id"], "idempotency_key": "t4"}))["state"] == "running"
            for state in ("accepted", "disputed"):
                assert (await carol.call_tool("frontier_transition", {"target": ref(act), "state": state, "lease_id": lease["lease_id"], "idempotency_key": "x" + state})).isError
    run(go())
    assert store.search(kind="Claim", query="by-reviewer")["results"] == []                  # the reviewer-only principal's proposal wrote nothing


def test_idempotency_is_per_principal_and_retries_are_safe(remote, store):
    async def go():
        async with client(remote, TOKENS["alice"]) as a, client(remote, TOKENS["carol"]) as c:
            d = claim(store, id="idem", issuer="alice")
            first = val(await a.call_tool("frontier_propose", {"draft": d, "idempotency_key": "same-key"}))
            again = val(await a.call_tool("frontier_propose", {"draft": d, "idempotency_key": "same-key"}))
            assert again == first                                                                # a retry returns the stored response
            clash = await a.call_tool("frontier_propose", {"draft": claim(store, id="idem-other", issuer="alice"), "idempotency_key": "same-key"})
            assert clash.isError and "conflict" in clash.content[0].text
            other = val(await c.call_tool("frontier_propose", {"draft": claim(store, id="idem-c", issuer="carol"), "idempotency_key": "same-key"}))
            assert other["record"]["id"] == "idem-c" and other["record"]["issuer"] == "carol"   # carol's identical key string is a separate namespace
    run(go())
    ids = {r["ref"]["id"] for r in store.search(kind="Claim", limit=50)["results"]}
    assert {"idem", "idem-c"} <= ids and "idem-other" not in ids


# ------------------------------------------------------------------ nothing sensitive leaves the server
def test_no_credential_in_any_output_schema_resource_error_or_log(remote, store):
    tokens = [TOKENS["alice"], TOKENS["carol"], RHEA]
    blob = []

    async def go():
        for tok in tokens:
            async with client(remote, tok) as s:
                for t in (await s.list_tools()).tools:
                    blob.append(json.dumps(t.inputSchema))
                    assert not ({"token", "dsn", "password", "credential", "authorization", "secret"} & set(t.inputSchema.get("properties", {})))
                blob.append(json.dumps(val(await s.call_tool("frontier_capabilities", {}))))
                blob.append((await s.read_resource("frontier://capabilities")).contents[0].text)
                schema = json.loads((await s.read_resource("frontier://schema/Action")).contents[0].text)
                assert "proposal" in schema["properties"] and "inputs" in schema["properties"]
                assert "plan_steps" in json.dumps(schema)
                bad = await s.call_tool("frontier_propose", {"draft": {"namespace": store.namespace, "kind": "Claim", "payload": {"title": "LEAK-MARKER-77"}}, "idempotency_key": "bad1"})
                assert bad.isError and "LEAK-MARKER-77" not in bad.content[0].text
                blob.append(bad.content[0].text)
                blob.append((await s.call_tool("frontier_get", {"target": {"namespace": "x", "kind": "Claim", "id": "nope", "version": "0" * 64}})).content[0].text)
    run(go())
    text = "\n".join(blob)
    time.sleep(0.3)
    for tok in tokens:
        assert tok not in text and tok not in remote.stderr()
    assert "payload_extensions" in text and "Action.proposal" in text and "Action.proposal.plan_steps" in text and "Action.inputs" in text


def test_read_only_server_has_no_write_tools_but_still_requires_a_bearer(readonly_remote, store):
    r = readonly_remote
    assert r.raw(body=INIT)[0] == 401

    async def go():
        async with client(r, TOKENS["alice"]) as s:
            names = {t.name for t in (await s.list_tools()).tools}
            assert names == READ_TOOLS
            caps = val(await s.call_tool("frontier_capabilities", {}))
            assert caps["mode"] == "read_only" and caps["principal"]["actor"] == "alice"
            gone = await s.call_tool("frontier_propose", {"draft": claim(store), "idempotency_key": "x"})
            assert gone.isError
    run(go())
    assert store.search(kind="Claim")["results"] == []


def test_a_process_credential_in_the_environment_is_never_used_by_the_remote_server(store):
    r = Remote(store, extra_env={"FRONTIER_TOKEN": TOKENS["alice"]})
    try:
        assert r.raw(body=INIT)[0] == 401                                                     # an env token does not authenticate anybody
        assert r.raw(body=INIT, headers={"Authorization": "Bearer " + TOKENS["carol"]})[0] == 200
    finally:
        r.close()


# ------------------------------------------------------------------ the guard in isolation (concurrency, timeout, lifespan, log hygiene)
def test_guard_bounds_concurrency_time_and_logs_no_query_or_header(caplog):
    import logging
    from frontier.mcp_remote import Guard
    caplog.set_level(logging.INFO, logger="frontier.mcp.remote")
    gate = asyncio.Event()

    async def slow_app(scope, receive, send):
        if scope["type"] == "lifespan":
            await receive()
            await send({"type": "lifespan.startup.complete"})
            return
        await gate.wait()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-length", b"0")]})
        await send({"type": "http.response.body", "body": b""})

    def scope(path="/mcp", query=b"", extra=()):
        return {"type": "http", "method": "POST", "path": path, "query_string": query, "client": ("9.9.9.9", 1), "headers": [(b"content-length", b"2"), (b"authorization", b"Bearer SECRET-BEARER-VALUE-123456"), *extra]}

    async def call(g, sc):
        out = []

        async def send(m):
            out.append(m)

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}
        await g(sc, receive, send)
        return out

    async def go():
        g = Guard(slow_app, max_concurrent=2, timeout=0.5)
        started = [asyncio.create_task(call(g, scope())) for _ in range(2)]
        await asyncio.sleep(0.1)
        third = await call(g, scope())
        assert third[0]["status"] == 503 and (b"retry-after", b"2") in third[0]["headers"]
        done = await asyncio.gather(*started)                                                # both time out at 0.5 s => 504
        assert [d[0]["status"] for d in done] == [504, 504]
        gate.set()
        ok = await call(Guard(slow_app), scope())
        assert ok[0]["status"] == 200
        # lifespan passes through untouched
        msgs = iter([{"type": "lifespan.startup"}])
        seen = []

        async def lreceive():
            return next(msgs)

        async def lsend(m):
            seen.append(m)
        await Guard(slow_app)({"type": "lifespan"}, lreceive, lsend)
        assert seen == [{"type": "lifespan.startup.complete"}]
        bad = await call(Guard(slow_app), scope(query=b"access_token=SECRET-QUERY-VALUE"))
        assert bad[0]["status"] == 400
    asyncio.run(go())
    text = caplog.text
    assert "SECRET-BEARER-VALUE" not in text and "SECRET-QUERY-VALUE" not in text and "9.9.9.9" not in text and "POST /mcp 503" in text and "POST /mcp 400" in text


def test_the_remote_front_refuses_a_non_loopback_bind_and_a_process_credential(store):
    from frontier.mcp import make_mcp
    from frontier.mcp_remote import serve
    with pytest.raises(ValueError, match="loopback"):
        serve(store, host="0.0.0.0")
    with pytest.raises(ValueError, match="never takes a process credential"):
        make_mcp(store, remote=True, token=TOKENS["alice"], allow_write=True)


# ------------------------------------------------------------------ a session id cannot be used to borrow another principal's identity
def test_a_session_header_cannot_make_one_principals_request_run_as_another(remote):
    def actor(headers, sid=None):
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "frontier_capabilities", "arguments": {}}}
        s, h, b = remote.raw(body=call, headers={**headers, **({"Mcp-Session-Id": sid} if sid else {})})
        assert s == 200
        return json.loads(json.loads(b)["result"]["content"][0]["text"])["principal"]["actor"]
    s, h, _ = remote.raw(body=INIT, headers={"Authorization": "Bearer " + TOKENS["alice"]})
    assert "mcp-session-id" not in h                                                          # the stateless server never issues one
    fake_sid = "f" * 32
    assert actor({"Authorization": "Bearer " + TOKENS["alice"]}, fake_sid) == "alice"
    assert actor({"Authorization": "Bearer " + TOKENS["carol"]}, fake_sid) == "carol"       # measured: with stateful sessions this returned the session creator


# ------------------------------------------------------------------ opt-in public reads; writes still need the caller's own bearer
@pytest.fixture
def public(store):
    r = Remote(store, public_read=True)
    yield r
    r.close()


def test_public_reads_work_anonymously_but_every_write_needs_a_valid_bearer(public, store):
    private = store.submit(TOKENS["alice"], "pr-priv", claim(store, id="hidden-private", visibility="private"))["record"]
    seen = store.submit(TOKENS["alice"], "pr-pub", claim(store, id="open-claim"))["record"]

    async def go():
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        async with streamable_http_client(public.url) as (read, write, _):                      # NO Authorization header
            async with ClientSession(read, write) as anon:
                await anon.initialize()
                proofs = val(await anon.call_tool("frontier_proofs", {"family": "unit-algebra", "include_source": True}))
                assert len(proofs["families"]) == 1 and proofs["withheld"] == []
                assert proofs["families"][0]["recorded_compile"] and not proofs["compile_executed"]
                assert "convert_comp" in proofs["families"][0]["source"]["text"]

                caps = val(await anon.call_tool("frontier_capabilities", {}))
                assert caps["principal"] is None and caps["anonymous_reads"] is True and "Public reads need no credential" in caps["credentials"] and "Every write tool needs a valid bearer" in caps["credentials"]
                got = val(await anon.call_tool("frontier_get", {"target": ref(seen)}))
                assert got["record"]["id"] == "open-claim"
                assert "open-claim" in json.dumps(val(await anon.call_tool("frontier_search", {"query": "open-claim"})))
                hidden = await anon.call_tool("frontier_get", {"target": ref(private)})
                assert hidden.isError and "hidden-private" not in hidden.content[0].text         # public data only
                assert "frontier://schema/Action" in [str(r.uri) for r in (await anon.list_resources()).resources] or (await anon.read_resource("frontier://schema/Action"))
                for tool, args in (("frontier_propose", {"draft": claim(store, id="anon-write", issuer="alice"), "idempotency_key": "an1"}),
                                   ("frontier_lease", {"target": ref(seen), "seconds": 30, "idempotency_key": "an2"}),
                                   ("frontier_transition", {"target": ref(seen), "state": "ready", "idempotency_key": "an3"})):
                    r = await anon.call_tool(tool, args)
                    assert r.isError and "unauthorized" in r.content[0].text, tool
        async with client(public, TOKENS["alice"]) as a, client(public, TOKENS["carol"]) as c:
            assert val(await a.call_tool("frontier_capabilities", {}))["principal"]["actor"] == "alice"
            assert val(await c.call_tool("frontier_capabilities", {}))["principal"]["actor"] == "carol"
            ok = val(await c.call_tool("frontier_propose", {"draft": claim(store, id="carol-public-mode", issuer="carol"), "idempotency_key": "pc1"}))
            assert ok["record"]["issuer"] == "carol"
    run(go())
    assert store.search(kind="Claim", query="anon-write")["results"] == []


def test_a_bad_credential_is_refused_never_downgraded_to_anonymous(public):
    for auth in ("Bearer wrong-wrong-wrong-wrong-wrong-0000", "Bearer short", "Basic " + "x" * 30, "Bearer " + TOKENS["alice"][:-1]):
        s, h, body = public.raw(body=INIT, headers={"Authorization": auth})
        assert s == 401 and b"invalid_token" in body and TOKENS["alice"].encode() not in body, auth
    assert public.raw(body=INIT)[0] == 200                                                    # no header at all: anonymous
    assert public.raw(body=INIT, headers={"Authorization": "Bearer " + TOKENS["alice"]})[0] == 200


def test_public_mode_keeps_every_transport_bound(public):
    assert public.raw(body=INIT, host="evil.example")[0] == 421
    assert public.raw(body=INIT, headers={"Origin": "https://evil.example"})[0] == 403
    assert public.raw(path=f"/mcp?access_token={TOKENS['alice']}", body=INIT)[0] == 400
    assert public.raw(path="/other", body=INIT)[0] == 404 and public.raw(method="GET")[0] == 405
    assert public.raw(body=b"x" * 131073)[0] == 413
    assert public.raw(path="/.well-known/oauth-protected-resource", body=INIT)[0] == 404      # still no OAuth discovery pointing at a server that does not exist


def test_public_read_without_write_opt_in_has_no_write_tools(store):
    r = Remote(store, allow_write=False, public_read=True)
    try:
        async def go():
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
            async with streamable_http_client(r.url) as (read, write, _):
                async with ClientSession(read, write) as s:
                    await s.initialize()
                    assert {t.name for t in (await s.list_tools()).tools} == READ_TOOLS
                    assert val(await s.call_tool("frontier_capabilities", {}))["mode"] == "read_only"
        run(go())
    finally:
        r.close()


def test_public_read_is_a_remote_only_option(store):
    from frontier.mcp import make_mcp
    with pytest.raises(ValueError, match="remote-transport option"):
        make_mcp(store, public_read=True)


async def guard_call(guard, body=b"{}", headers=(), path="/mcp"):
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "path": path, "query_string": b"",
             "client": ("127.0.0.1", 1), "headers": [(b"content-length", b"2"), *headers]}
    await guard(scope, receive, send)
    return messages


def test_request_slot_is_reserved_before_slow_credential_verification():
    from mcp.server.auth.provider import AccessToken
    from frontier.mcp_remote import Guard

    async def go():
        entered, release = asyncio.Event(), asyncio.Event()

        class SlowVerifier:
            async def verify_token(self, _token):
                entered.set()
                await release.wait()
                return AccessToken(token="fixture", client_id="fixture", scopes=[])

        async def app(_scope, _receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        guard = Guard(app, max_concurrent=1, public_verifier=SlowVerifier())
        headers = [(b"authorization", b"Bearer fixture")]
        first = asyncio.create_task(guard_call(guard, headers=headers))
        await entered.wait()
        blocked = await guard_call(guard, headers=headers)
        assert blocked[0]["status"] == 503
        release.set()
        assert (await first)[0]["status"] == 200
        assert guard.active == 0

    run(go())


def test_guard_checks_actual_body_bytes_and_redacts_unmatched_paths(caplog):
    import logging
    from frontier.mcp_remote import Guard
    caplog.set_level(logging.INFO, logger="frontier.mcp.remote")

    async def never_called(*_args):
        raise AssertionError("invalid body reached the application")

    async def go():
        guard = Guard(never_called, max_body=10)
        assert (await guard_call(guard, body=b"x" * 11))[0]["status"] == 413
        assert (await guard_call(guard, body=b"xxx"))[0]["status"] == 400
        duplicate = [(b"authorization", b"Bearer first"), (b"authorization", b"Bearer second")]
        assert (await guard_call(guard, headers=duplicate))[0]["status"] == 400
        assert (await guard_call(guard, path="/SECRET-PATH-MARKER"))[0]["status"] == 404
        assert guard.active == 0

    run(go())
    assert "SECRET-PATH-MARKER" not in caplog.text


def test_anonymous_request_cannot_inherit_a_previous_auth_context():
    from mcp.server.auth.middleware.auth_context import auth_context_var, get_access_token
    from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
    from mcp.server.auth.provider import AccessToken
    from frontier.mcp_remote import Guard, StoreTokenVerifier

    async def app(_scope, _receive, send):
        assert get_access_token() is None
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def go():
        previous = AuthenticatedUser(AccessToken(token="old-fixture", client_id="old", scopes=[]))
        original = auth_context_var.set(previous)
        try:
            assert (await guard_call(Guard(app, public_verifier=StoreTokenVerifier(None))))[0]["status"] == 200
            assert auth_context_var.get() is previous
        finally:
            auth_context_var.reset(original)

    run(go())


def test_verification_failure_returns_fixed_503_without_driver_details(caplog):
    from frontier.mcp_remote import Guard, StoreTokenVerifier

    class BrokenStore:
        def principal(self, _token):
            raise RuntimeError("SECRET-DRIVER-PASSWORD-MARKER")

    async def never_called(*_args):
        raise AssertionError("unverified request reached application")

    async def go():
        guard = Guard(never_called, public_verifier=StoreTokenVerifier(BrokenStore()))
        messages = await guard_call(guard, headers=[(b"authorization", b"Bearer test-only-valid-length-token")])
        assert messages[0]["status"] == 503
        assert "SECRET-DRIVER-PASSWORD-MARKER" not in str(messages)
        assert guard.active == 0

    run(go())
    assert "SECRET-DRIVER-PASSWORD-MARKER" not in caplog.text


def test_public_schemas_follow_all_current_kinds(public):
    from frontier.models import KINDS, PAYLOADS

    async def go():
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        async with streamable_http_client(public.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                caps = val(await session.call_tool("frontier_capabilities", {}))
                assert caps["record_kinds"] == list(KINDS)
                for kind in KINDS:
                    resource = await session.read_resource(f"frontier://schema/{kind}")
                    assert json.loads(resource.contents[0].text) == PAYLOADS[kind].model_json_schema()

    run(go())
