"""SearchIndex wired into the HTTP Application and the MCP frontier_search tool. Legacy request fields keep working; new ones are optional.
Run bounded: systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash scripts/test_postgres.sh tests/test_search_wiring.py
"""
from http.client import HTTPConnection
import json
from threading import Thread

import pytest

from frontier.http import Application, make_server
from frontier.models import ref
from frontier.search import SearchIndex
from frontier.store import FrontierError
from conftest import TOKENS, claim
from test_interfaces import run, session_for, val

LEGACY_KEYS = {"ref", "issuer", "source_uri", "title", "local_status", "why_matched"}


def save(store, id, statement, **changes):
    d = claim(store, id, **changes)
    d["payload"]["statement"] = statement
    return store.submit(TOKENS["alice"], "w-" + id, d)["record"]


def served(store):
    server = make_server(store)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def request(path, data, token=None, origin=None):
        c = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        c.request("POST", path, json.dumps(data), headers)
        r = c.getresponse()
        out = r.status, json.loads(r.read())
        c.close()
        return out
    return server, worker, request


def test_application_search_keeps_legacy_fields_and_adds_new_ones(store):
    one = save(store, "wire-one", "wiringterm first statement")
    save(store, "wire-two", "wiringterm second statement")
    save(store, "wire-priv", "wiringterm private statement", visibility="private")
    app = Application(store)
    legacy = app.dispatch("/v1/read/search", {"query": "wiringterm", "kind": "Claim", "status": "proposed", "limit": 10})
    assert {r["ref"]["id"] for r in legacy["results"]} == {"wire-one", "wire-two"}
    assert all(LEGACY_KEYS <= set(r) for r in legacy["results"]) and "next_cursor" in legacy
    # same visible set as the legacy Store.search for a legacy request
    assert {r["ref"]["version"] for r in legacy["results"]} == {r["ref"]["version"] for r in store.search("wiringterm", kind="Claim")["results"]}
    # authenticated read through the header token sees the private record; anonymous does not
    assert {r["ref"]["id"] for r in app.dispatch("/v1/read/search", {"query": "wiringterm"}, TOKENS["alice"])["results"]} == {"wire-one", "wire-two", "wire-priv"}
    # new fields
    assert [r["ref"]["id"] for r in app.dispatch("/v1/read/search", {"query": one["version"]})["results"]][0] == "wire-one"
    assert {r["ref"]["id"] for r in app.dispatch("/v1/read/search", {"kinds": ["Claim", "Evidence"], "context": "protocol test"})["results"]} >= {"wire-one"}
    assert app.dispatch("/v1/read/search", {"query": "wiringterm", "kinds": ["Evidence"]})["results"] == []
    # empty-string filters mean "no filter", as before
    assert len(app.dispatch("/v1/read/search", {"query": "wiringterm", "kind": "", "status": ""})["results"]) == 2


def test_legacy_after_listing_and_cursor_aliases_page_without_gaps(store):
    ids = [save(store, f"page-{i}", f"pagingterm {i}")["version"] for i in range(5)]
    app = Application(store)
    # legacy: empty query, ordered by version, "after" = the previous page's last version
    seen, after = [], ""
    while True:
        page = app.dispatch("/v1/read/search", {"kind": "Claim", "limit": 2, "after": after})
        seen += [r["ref"]["version"] for r in page["results"]]
        if not page["next_cursor"]:
            break
        after = page["next_cursor"]  # the next_cursor is accepted under the legacy name too
    assert seen == sorted(ids) and len(seen) == 5
    # legacy bare-version `after` on an empty query: exactly the versions greater than it, in version order
    first = app.dispatch("/v1/read/search", {"kind": "Claim", "limit": 50, "after": sorted(ids)[1]})
    assert [r["ref"]["version"] for r in first["results"]] == sorted(ids)[2:]
    assert [r["ref"]["version"] for r in first["results"]] == [r["ref"]["version"] for r in store.search(kind="Claim", after=sorted(ids)[1])["results"]]
    # with a query the bare version is refused rather than silently reordered; next_cursor works under `cursor` and `after`
    with pytest.raises(FrontierError):
        app.dispatch("/v1/read/search", {"query": "pagingterm", "after": sorted(ids)[0]})
    p1 = app.dispatch("/v1/read/search", {"query": "pagingterm", "limit": 2})
    via_cursor = app.dispatch("/v1/read/search", {"query": "pagingterm", "limit": 2, "cursor": p1["next_cursor"]})
    via_after = app.dispatch("/v1/read/search", {"query": "pagingterm", "limit": 2, "after": p1["next_cursor"]})
    assert via_cursor == via_after and via_cursor["results"] and not {r["ref"]["id"] for r in via_cursor["results"]} & {r["ref"]["id"] for r in p1["results"]}


def test_http_search_validation_and_isolation_over_the_wire(store):
    save(store, "http-pub", "httpsearchterm public")
    save(store, "http-priv", "httpsearchterm private", visibility="private")
    server, worker, request = served(store)
    try:
        code, body = request("/v1/read/search", {"query": "httpsearchterm"})
        assert code == 200 and [r["ref"]["id"] for r in body["results"]] == ["http-pub"] and "lexical only" in body["search_kind"]
        code, body = request("/v1/read/search", {"query": "httpsearchterm"}, TOKENS["alice"])
        assert code == 200 and {r["ref"]["id"] for r in body["results"]} == {"http-pub", "http-priv"}
        assert request("/v1/read/search", {"limit": 51})[0] == 400
        assert request("/v1/read/search", {"kind": "Claim", "kinds": ["Claim"]})[0] == 400
        assert request("/v1/read/search", {"cursor": "x", "after": "y"})[0] == 400
        assert request("/v1/read/search", {"nonsense": 1})[0] == 400, "unknown request fields are rejected"
        assert request("/v1/read/search", {"kinds": ["NotAKind"]})[0] == 400
        assert request("/v1/read/search", {"cursor": "garbage"})[0] == 400
        assert request("/v1/read/search", {"token": TOKENS["alice"]})[0] == 400, "credentials never travel in the body"
        assert request("/v1/read/search", {"query": "x"}, "test-only-not-a-provisioned-token-xyz")[0] == 401
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_mcp_frontier_search_exposes_new_and_legacy_fields_without_private_records(store):
    pub = save(store, "mcp-pub", "mcpsearchterm public")
    save(store, "mcp-priv", "mcpsearchterm private", visibility="private")

    async def exercise():
        async with session_for(store) as session:
            tools = {t.name: t for t in (await session.list_tools()).tools}
            props = set(tools["frontier_search"].inputSchema["properties"])
            assert {"query", "kind", "status", "limit", "after"} <= props, "legacy fields stay"
            assert {"kinds", "source", "scope", "context", "include_history", "cursor"} <= props
            assert all(t.annotations.readOnlyHint for t in tools.values())
            legacy = val(await session.call_tool("frontier_search", {"query": "mcpsearchterm", "kind": "Claim", "status": "proposed", "limit": 5}))
            assert [r["ref"]["id"] for r in legacy["results"]] == ["mcp-pub"] and LEGACY_KEYS <= set(legacy["results"][0])
            pinned = val(await session.call_tool("frontier_search", {"query": pub["version"], "kinds": ["Claim"], "source": "https://example.org/"}))
            assert pinned["results"][0]["ref"] == ref(pub) and "exact version pin" in pinned["results"][0]["why_matched"]
            assert pinned["results"][0]["curation"]["promoted"] is False
            both = await session.call_tool("frontier_search", {"kind": "Claim", "kinds": ["Claim"]})
            assert both.isError
            assert (await session.call_tool("frontier_search", {"limit": 51})).isError
            caps = val(await session.call_tool("frontier_capabilities", {}))
            assert "no embeddings" in caps["search"]["engine"] and caps["limits"]["search_page_max"] == 50
    run(exercise())


def test_search_cli_creates_indexes_idempotently(store):
    import os
    import subprocess
    import sys
    env = {**os.environ, "FRONTIER_DSN": store.dsn, "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
           "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
    for _ in range(2):
        out = subprocess.run([sys.executable, "-m", "frontier.search", "--namespace", store.namespace, "--schema", store.schema],
                             env=env, capture_output=True, text=True, timeout=60)
        assert out.returncode == 0 and "search indexes ready" in out.stdout, out.stderr[-300:]
    with store.connection() as c:
        assert c.execute("SELECT 1 FROM pg_indexes WHERE schemaname=%s AND indexname='record_search_fts'", (store.schema,)).fetchone()
    assert SearchIndex(store).search("anything")["results"] == []
