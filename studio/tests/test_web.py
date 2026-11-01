"""Real-HTTP tests of the website/API adapter, the admin tool and the deploy files, against isolated PostgreSQL (scripts/test_postgres.sh)."""
import http.client
import json
import logging
import os
import re
import socket
import stat
import subprocess
import sys
from pathlib import Path
from threading import Thread

import pytest

from conftest import TOKENS, assessment, claim
from frontier import admin
from frontier.models import ref
from frontier.store import Store
from frontier.web import WebConfig, make_web_server, resolve_static

ROOT = Path(__file__).resolve().parents[1]
GATE = "test-access-token-0123456789abcdef"
SECRET = "OUTSIDE-SECRET-MARKER-7731"


class Web:
    def __init__(self, store, site, **cfg):
        self.store = store
        cfg.setdefault("cookie_secure", False)
        self.cfg = WebConfig.with_tokens(*(() if cfg.get("public_read") else (GATE,)), site_dir=site, **cfg)
        self.server = make_web_server(store, self.cfg)
        self.port = self.server.server_port
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None
        self.csrf = None

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def req(self, method, path, body=None, headers=None, raw_headers=None, cookie=True):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = dict(headers or {})
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            h.setdefault("Content-Type", "application/json")
        if cookie and self.cookie:
            h.setdefault("Cookie", self.cookie)
        c.request(method, path, body, h)
        r = c.getresponse()
        data = r.read()
        out = (r.status, {k.lower(): v for k, v in r.getheaders()}, data)
        c.close()
        return out

    def json(self, *a, **k):
        s, h, d = self.req(*a, **k)
        return s, (json.loads(d) if d and h.get("content-type", "").startswith("application/json") else d), h

    def login(self, token=GATE):
        s, body, h = self.json("POST", "/api/session", {"token": token}, cookie=False)
        if s == 200:
            self.cookie = h["set-cookie"].split(";")[0]
            self.csrf = body["csrf"]
        return s, body, h


@pytest.fixture
def site(tmp_path):
    s = tmp_path / "site"
    (s / "sub").mkdir(parents=True)
    (s / "index.html").write_text("<!doctype html><title>Frontier</title><p>hello</p>")
    (s / "app.css").write_text("body{}")
    (s / "sub" / "page.html").write_text("<p>sub</p>")
    (s / "sub" / ".hidden.html").write_text("hidden")
    (s / ".env").write_text(SECRET)
    (s / "tool.py").write_text("print(1)")
    (tmp_path / "secret.txt").write_text(SECRET)
    (s / "link.txt").symlink_to(tmp_path / "secret.txt")
    (s / "emptydir").mkdir()
    return s


@pytest.fixture
def web(store, site):
    w = Web(store, site)
    yield w
    w.close()


@pytest.fixture
def authed(web):
    assert web.login()[0] == 200
    return web


# ------------------------------------------------------------------ health, gate, host/origin
def test_health_is_public_and_carries_no_detail(web):
    s, body, h = web.json("GET", "/api/health", cookie=False)
    assert s == 200 and body == {"status": "ok", "service": "delphi-frontier", "mode": "live"}
    assert h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store"
    assert web.req("HEAD", "/api/health", cookie=False)[2] == b""
    assert web.req("POST", "/api/health", cookie=False)[0] == 405


def test_public_design_context_and_credentialed_challenge_preserve_exact_pins(store, site):
    from urllib.parse import urlencode
    from test_design_review import challenge, project
    member_record = store.submit(TOKENS["alice"], "web-design-member", claim(store))["record"]
    project_record = store.submit(TOKENS["alice"], "web-design-project", project(store, ref(member_record)))["record"]
    target = ref(project_record)
    w = Web(store, site, public_read=True)
    try:
        path = "/api/design/context?" + urlencode(target)
        status, body, _ = w.json("GET", path)
        assert status == 200 and body["project"]["record"]["version"] == target["version"]
        assert body["annotations"] == [] and body["pagination"]["next_cursor"] is None
        assert w.json("GET", path + "&limit=51")[0] == 400
        assert w.json("GET", path + "&cursor=invalid")[0] == 400
        draft = challenge(store, target)
        assert w.json("POST", "/v1/design/reviews", {"draft": draft})[0] == 401
        headers = {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "web-design-challenge"}
        status, result, _ = w.json("POST", "/v1/design/reviews", {"draft": draft}, headers=headers)
        assert status == 200 and result["local_status"] == "proposed"
        status, body, _ = w.json("GET", path + "&limit=1")
        assert status == 200 and len(body["annotations"]) == 1
        assert body["annotations"][0]["record"]["payload"]["anchor"]["record"] == target
        assert body["project"]["local_review"]["status"] == "proposed"
    finally:
        w.close()


def test_everything_else_is_gated_and_html_navigation_goes_to_login(web):
    for path in ("/api/catalog", "/api/record", "/api/events", "/api/session"):
        assert web.req("GET", path, cookie=False)[0] == 401
    assert web.req("GET", "/app.css", cookie=False)[0] == 401
    s, h, _ = web.req("GET", "/", headers={"Accept": "text/html"}, cookie=False)
    assert s == 302 and h["location"] == "/login"
    s, h, body = web.req("GET", "/login", cookie=False)
    assert s == 200 and b'type="password"' in body and "frame-ancestors 'none'" in h["content-security-policy"]


def test_public_site_option_opens_only_the_static_shell(store, site):
    w = Web(store, site, public_site=True)
    try:
        assert w.req("GET", "/", cookie=False)[0] == 200
        assert w.req("GET", "/api/catalog", cookie=False)[0] == 401
    finally:
        w.close()


def test_public_discovery_uses_one_search_instance_and_preserves_mode(store, site):
    calls = []
    def search(query, **kwargs):
        calls.append((query, kwargs))
        return {"query": query, "mode": "hybrid", "items": [], "index": {"documents": 3}}
    w = Web(store, site, public_read=True, discovery_search=search)
    try:
        for path in ("/api/discovery?q=fin", "/api/discovery?q=fin&cache_only=1&kind=Claim&limit=4"):
            status, result, _ = w.json("GET", path, cookie=False)
            assert status == 200 and result["mode"] == "hybrid"
        assert calls == [("fin", {"kind": None, "limit": 12, "mode": "hybrid", "cache_only": False}),
                         ("fin", {"kind": "Claim", "limit": 4, "mode": "hybrid", "cache_only": True})]
        for suffix in ("&cache_only=yes", "&provider=evil", "&q=duplicate"):
            assert w.req("GET", "/api/discovery?q=fin" + suffix)[0] == 400
    finally:
        w.close()


def test_public_graph_requires_pinned_refs_and_does_not_expose_private(store, site):
    from urllib.parse import urlencode
    public = store.submit(TOKENS["alice"], "graph-public", claim(store))["record"]
    private = store.submit(TOKENS["alice"], "graph-private", claim(store, id="private-graph", visibility="private"))["record"]
    w = Web(store, site, public_read=True)
    try:
        status, result, _ = w.json("GET", "/api/graph?" + urlencode(ref(public)))
        assert status == 200 and result["nodes"] and private["version"] not in json.dumps(result)
        assert w.req("GET", "/api/graph?" + urlencode(ref(private)))[0] == 404
        for suffix in ("id=x", "depth=4", "limit=301", "limit=0", "unknown=x"):
            assert w.req("GET", "/api/graph?" + suffix)[0] == 400
    finally:
        w.close()


def test_discovery_and_graph_keep_private_mode_gate(web):
    for path in ("/api/discovery?q=fin", "/api/graph"):
        assert web.req("GET", path, cookie=False)[0] == 401


def test_reference_fasta_is_plain_text_only_in_guarded_artifacts(web, site):
    data = b">reference-only\nACGTACGT\n"
    (site / "artifacts").mkdir(exist_ok=True)
    for ext in (".fasta", ".fa"):
        (site / "artifacts" / ("reference" + ext)).write_bytes(data)
        (site / ("reference" + ext)).write_bytes(data)
        assert resolve_static(site, "/reference" + ext) is None
    web.login()
    for ext in (".fasta", ".fa"):
        status, headers, body = web.req("GET", "/artifacts/reference" + ext)
        assert status == 200 and body == data
        assert headers["content-type"].startswith("text/plain")


def test_source_documents_and_result_csv_serve_exact_bytes(web, site):
    docs = site / "data" / "docs"
    docs.mkdir(parents=True)
    (docs / "model.md").write_bytes(b"# Model\nThe source assumption.\n")
    (site / "data" / "designs.csv").write_bytes(b"id,mass\na,0.3\n")
    assert web.login()[0] == 200
    for path, mime in (("/data/docs/model.md", "text/plain"), ("/data/designs.csv", "text/csv")):
        status, headers, body = web.req("GET", path)
        assert status == 200 and headers["content-type"].startswith(mime)
        assert body == (site / path.lstrip("/")).read_bytes()
    assert web.req("GET", "/.env")[0] == 404


def test_anonymous_simulation_preview_requires_csrf_and_rejects_untrusted_models(store, site):
    w = Web(store, site, public_read=True)
    try:
        path = "/api/simulations/run"
        assert w.json("POST", path, {"model": "shell"})[0] == 401
        _, session, headers = w.json("GET", "/api/session")
        w.cookie = headers["set-cookie"].split(";")[0]
        headers = {"Origin": f"http://127.0.0.1:{w.port}", "X-CSRF-Token": session["csrf"]}
        status, result, _ = w.json("POST", path, {"model": "shell"}, headers)
        assert status == 400 and result["persisted"] is False
        status, result, _ = w.json("POST", path, {"model": "bioelectric", "parameters": {"duration_ms": 10}}, headers)
        assert status == 200 and result["status"] == "completed" and result["persisted"] is False
        assert result["result"]["voltage_mV"]
    finally:
        w.close()


def test_public_media_projection_matches_served_bytes_and_counts_remain_public(store, site):
    from hashlib import sha256
    data = b"a declared computed result\n"
    (site / "artifacts").mkdir()
    (site / "artifacts" / "result.txt").write_bytes(data)
    store.submit(TOKENS["alice"], "count-public", claim(store))
    private = store.submit(TOKENS["alice"], "count-private", claim(store, id="hidden-count", visibility="private"))["record"]
    w = Web(store, site, public_read=True)
    try:
        status, result, _ = w.json("GET", "/api/media?sha256=" + sha256(data).hexdigest())
        assert status == 200 and len(result["matches"]) == 1
        match = result["matches"][0]
        assert match["bytes_verified"] and w.req("GET", match["href"])[2] == data
        assert w.req("GET", "/api/media?sha256=../secret")[0] == 400
        status, result, _ = w.json("GET", "/api/counts")
        assert status == 200 and result["scope"]["records_read"] == 1
        assert private["version"] not in json.dumps(result)
        assert result["cache_seconds"] == 30
    finally:
        w.close()


def test_public_read_without_gate_opens_public_records_but_never_writes_or_private_data(store, site):
    from urllib.parse import urlencode
    public = store.submit(TOKENS["alice"], "public-read", claim(store))["record"]
    private = store.submit(TOKENS["alice"], "private-read", claim(store, id="private", visibility="private"))["record"]
    w = Web(store, site, public_read=True)
    try:
        assert not w.cfg.gate_tokens
        for path in ("/", "/app.css", "/api/catalog", "/api/artifacts", "/api/events"):
            assert w.req("GET", path, cookie=False)[0] == 200
        assert w.req("GET", "/login")[1]["location"] == "/"
        assert w.json("POST", "/v1/read/get", {"target": ref(public)}, cookie=False)[0] == 200
        assert w.req("GET", "/api/record?" + urlencode(ref(private)), cookie=False)[0] == 404
        assert b'"private"' not in w.req("GET", "/api/catalog", cookie=False)[2]
        for path in ("/v1/proposals", "/v1/reviews", "/v1/import", "/v1/actions/lease", "/v1/actions/transition"):
            assert w.json("POST", path, {}, cookie=False)[0] == 401
        assert w.req("GET", "/.env", cookie=False)[0] == 404
    finally:
        w.close()


def test_public_calculation_gets_anonymous_csrf_session_without_operator_permission(store, site):
    from frontier.web import Route
    path = "/api/engineering/solve"
    w = Web(store, site, public_read=True, routes={"POST " + path: Route(lambda req: (200, {"result": req["body"]["x"] + 1}))})
    try:
        origin = {"Origin": f"http://127.0.0.1:{w.port}"}
        assert w.json("POST", path, {"x": 2}, origin)[0] == 401
        status, session, headers = w.json("GET", "/api/session")
        assert status == 200 and session["public_access"] is True and session["authenticated"] is False
        w.cookie = headers["set-cookie"].split(";")[0]
        assert "HttpOnly" in headers["set-cookie"] and "SameSite=Strict" in headers["set-cookie"]
        assert w.json("GET", "/api/session")[1]["csrf"] == session["csrf"]
        assert w.json("POST", path, {"x": 2}, origin)[0] == 403
        headers = {**origin, "X-CSRF-Token": session["csrf"]}
        assert w.json("POST", path, {"x": 2}, headers)[:2] == (200, {"result": 3})
        assert w.json("POST", path, {"x": 2}, {**headers, "Origin": "https://evil.example"})[0] == 403
        assert w.json("POST", "/v1/proposals", {"draft": claim(store)}, headers)[0] == 401
        assert w.json("POST", "/v1/proposals", {"draft": claim(store)}, {**headers, "Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "public-bearer"})[0] == 200
    finally:
        w.close()


def test_host_and_origin_are_checked_on_every_request(authed):
    def raw(headers, path="/api/catalog"):
        c = http.client.HTTPConnection("127.0.0.1", authed.port, timeout=5)
        c.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
        for k, v in headers.items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()
        r.read()
        c.close()
        return r.status
    ck = {"Cookie": authed.cookie}
    assert raw({**ck, "Host": "evil.example"}) == 400
    assert raw({**ck}) == 400                                                       # no Host at all
    assert raw({**ck, "Host": "frontier.morphoswarm.ai"}) == 200                    # the public name nginx forwards
    assert raw({**ck, "Host": f"127.0.0.1:{authed.port}", "Origin": "https://evil.example"}) == 403
    assert raw({**ck, "Host": f"127.0.0.1:{authed.port}", "Origin": "null"}) == 403
    assert raw({**ck, "Host": f"127.0.0.1:{authed.port}", "Origin": "http://localhost:1"}) == 403
    assert raw({**ck, "Host": f"127.0.0.1:{authed.port}", "Origin": "https://frontier.morphoswarm.ai"}) == 200
    assert raw({**ck, "Host": f"127.0.0.1:{authed.port}", "Origin": f"http://127.0.0.1:{authed.port}"}) == 200


# ------------------------------------------------------------------ sessions
def test_login_cookie_attributes_with_secure_enabled(store, site):
    w = Web(store, site, cookie_secure=True)
    try:
        s, body, h = w.login()
        assert s == 200 and body["authenticated"] and body["csrf"]
        attrs = [a.strip() for a in h["set-cookie"].split(";")]
        assert attrs[0].startswith("__Host-frontier_session=") and len(attrs[0].split("=")[1]) >= 40
        assert {"HttpOnly", "SameSite=Strict", "Path=/", "Secure"} <= set(attrs) and not any(a.lower().startswith("domain") for a in attrs)
        assert any(a.startswith("Max-Age=") for a in attrs)
    finally:
        w.close()


def test_wrong_token_is_refused_uniformly_and_a_good_one_opens_a_session(web):
    for bad in ("wrong", GATE[:-1], GATE + "x", "", "x" * 600):
        s, body, _ = web.login(bad)
        assert s == 401 and body["error"] == "unauthorized" and (bad == "" or bad not in json.dumps(body))
    assert web.json("POST", "/api/session", {"token": GATE, "extra": 1}, cookie=False)[0] == 400
    assert web.json("POST", "/api/session", {"token": 5}, cookie=False)[0] == 401
    assert web.req("POST", "/api/session", "token=" + GATE, {"Content-Type": "text/plain"}, cookie=False)[0] == 400
    assert web.login()[0] == 200
    s, body, _ = web.json("GET", "/api/session")
    assert s == 200 and body["authenticated"] and body["csrf"] == web.csrf


def test_repeated_failures_are_throttled_even_for_the_right_token(web):
    codes = [web.login("nope-nope-nope")[0] for _ in range(10)]
    assert codes == [401] * 10
    s, body, h = web.login()
    assert s == 429 and h["retry-after"] == "60" and body["error"] == "too_many_attempts"


def test_form_login_sets_the_cookie_and_redirects(web):
    s, h, _ = web.req("POST", "/login", "token=" + GATE, {"Content-Type": "application/x-www-form-urlencoded"}, cookie=False)
    assert s == 303 and h["location"] == "/" and "HttpOnly" in h["set-cookie"]
    web.cookie = h["set-cookie"].split(";")[0]
    assert web.req("GET", "/")[0] == 200
    s, _, body = web.req("POST", "/login", "token=wrong-wrong-wrong", {"Content-Type": "application/x-www-form-urlencoded"}, cookie=False)
    assert s == 401 and b"Invalid access token" in body and b"wrong-wrong-wrong" not in body
    assert web.req("POST", "/login", json.dumps({"token": GATE}), {"Content-Type": "application/json"}, cookie=False)[0] == 400


def test_logout_needs_origin_and_csrf_and_really_ends_the_session(authed):
    good_origin = f"http://127.0.0.1:{authed.port}"
    assert authed.req("DELETE", "/api/session")[0] == 403                                                          # no Origin
    assert authed.req("DELETE", "/api/session", headers={"Origin": good_origin})[0] == 403                          # no CSRF
    assert authed.req("DELETE", "/api/session", headers={"Origin": good_origin, "X-CSRF-Token": "wrong"})[0] == 403
    assert authed.req("DELETE", "/api/session", headers={"Origin": "https://evil.example", "X-CSRF-Token": authed.csrf})[0] == 403
    assert authed.req("GET", "/api/catalog")[0] == 200                                                             # still signed in
    s, h, _ = authed.req("DELETE", "/api/session", headers={"Origin": good_origin, "X-CSRF-Token": authed.csrf})
    assert s == 204 and "Max-Age=0" in h["set-cookie"]
    assert authed.req("GET", "/api/catalog")[0] == 401                                                             # server-side invalidation


def test_forged_and_expired_sessions_do_not_work(store, site):
    w = Web(store, site, session_ttl=0)
    try:
        assert w.req("GET", "/api/catalog", headers={"Cookie": "frontier_session=" + "A" * 43}, cookie=False)[0] == 401
        w.login()
        assert w.req("GET", "/api/catalog")[0] == 401                                  # ttl 0: expired at once
    finally:
        w.close()


# ------------------------------------------------------------------ catalog / record / events
def seed(store):
    a = store.submit(TOKENS["alice"], "w1", claim(store, id="claim-a"))["record"]
    b = store.submit(TOKENS["alice"], "w2", claim(store, id="claim-b", source_uri="https://example.org/other"))["record"]
    return a, b


def test_catalog_returns_full_envelopes_with_status_kept_separate(authed):
    a, b = seed(authed.store)
    s, body, h = authed.json("GET", "/api/catalog?kind=Claim")
    assert s == 200 and body["mode"] == "live" and body["namespace"] == authed.store.namespace and body["search_mode"] == "store_lexical"
    assert "relevance is not truth" in body["search_kind"] and body["next_cursor"] is None
    kinds = {r["record"]["kind"] for r in authed.json("GET", "/api/catalog?limit=50")[1]["results"]}
    assert kinds == {"Claim", "Event"}                  # Events are records too; the catalog does not hide them, callers filter by kind
    by_id = {r["record"]["id"]: r for r in body["results"]}
    assert set(by_id) == {"claim-a", "claim-b"} and by_id["claim-a"]["record"] == a             # the full, unmodified envelope
    assert by_id["claim-a"]["local_status"] == "proposed" and by_id["claim-a"]["is_head"] is True
    assert "local_status" not in a and "status" not in a["payload"]
    assessed = authed.store.review(TOKENS["bob"], "w-review", assessment(ref(a), "bob"))
    _, body, _ = authed.json("GET", "/api/catalog?kind=Claim&query=claim-a")
    only = body["results"][0]
    assert only["local_status"] == "accepted" and only["record"] == a                             # status moved, record bytes did not
    assert assessed["local_status"] == "accepted"


def test_catalog_filters_pagination_and_bounds(authed):
    seed(authed.store)
    s, p1, _ = authed.json("GET", "/api/catalog?limit=1")
    assert s == 200 and len(p1["results"]) == 1 and p1["next_cursor"]
    _, p2, _ = authed.json("GET", "/api/catalog?limit=1&after=" + p1["next_cursor"])
    assert p2["results"][0]["record"]["id"] != p1["results"][0]["record"]["id"]
    assert authed.json("GET", "/api/catalog?kind=Problem")[1]["results"] == []
    for bad in ("limit=51", "limit=0", "limit=abc", "kind=Bogus", "status=bogus", "after=xyz", "bogus=1", "limit=1&limit=2", "query=" + "x" * 201):
        assert authed.json("GET", "/api/catalog?" + bad)[0] == 400, bad


def test_catalog_labels_the_search_backend_that_actually_ran(store, site):
    calls = []

    def custom(**kw):
        calls.append(kw)
        return store.search(**kw)
    w = Web(store, site, catalog_search=custom, search_mode="custom_test_index")
    try:
        w.login()
        _, body, _ = w.json("GET", "/api/catalog?query=abc&limit=3")
        assert body["search_mode"] == "custom_test_index" and calls == [{"query": "abc", "kind": None, "status": None, "limit": 3, "after": ""}]
    finally:
        w.close()


def test_record_needs_a_pinned_ref_and_never_serves_private_records(authed):
    a, _ = seed(authed.store)
    q = "&".join(f"{k}={v}" for k, v in ref(a).items())
    s, body, _ = authed.json("GET", "/api/record?" + q)
    assert s == 200 and body["record"] == a and body["local_status"] == "proposed" and body["mode"] == "live"
    assert authed.json("GET", "/api/record?" + q.replace(a["version"], "0" * 64))[0] == 404
    marker = "ECHO-MARKER-5512"
    for bad in ("/api/record", "/api/record?namespace=x", "/api/record?" + q + "&extra=1", f"/api/record?namespace={marker}&kind=Claim&id=a&version=zzz"):
        s, _, body = authed.req("GET", bad)
        assert s == 400 and marker.encode() not in body
    private = authed.store.submit(TOKENS["alice"], "w-priv", claim(authed.store, id="priv", visibility="private"))["record"]
    pq = "&".join(f"{k}={v}" for k, v in ref(private).items())
    assert authed.json("GET", "/api/record?" + pq)[0] == 404
    assert "priv" not in json.dumps(authed.json("GET", "/api/catalog")[1])
    assert "priv" not in json.dumps(authed.json("GET", "/api/events?limit=50")[1])


def test_events_are_bounded_and_paged(authed):
    seed(authed.store)
    s, body, _ = authed.json("GET", "/api/events?limit=1")
    assert s == 200 and len(body["events"]) == 1 and body["next_cursor"]
    _, nxt, _ = authed.json("GET", "/api/events?limit=50&after=" + str(body["next_cursor"]))
    assert nxt["events"][0]["sequence"] > body["events"][-1]["sequence"]
    for bad in ("limit=51", "limit=0", "after=-1", "after=x", "foo=1"):
        assert authed.json("GET", "/api/events?" + bad)[0] == 400, bad


# ------------------------------------------------------------------ static files
def test_static_is_served_with_safe_headers_only_to_signed_in_browsers(authed):
    s, h, body = authed.req("GET", "/")
    assert s == 200 and b"hello" in body and h["content-type"].startswith("text/html") and h["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in h["content-security-policy"] and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert authed.req("GET", "/app.css")[1]["content-type"].startswith("text/css")
    assert authed.req("GET", "/sub/page.html")[0] == 200 and authed.req("GET", "/sub/")[0] == 404
    assert authed.req("HEAD", "/")[2] == b"" and authed.req("HEAD", "/")[0] == 200


@pytest.mark.parametrize("path", ["/../secret.txt", "/%2e%2e/secret.txt", "/%2e%2e%2fsecret.txt", "/..%2fsecret.txt", "/a/../../secret.txt", "/sub/../../secret.txt",
                                  "//etc/passwd", "/\\..\\secret.txt", "/%5c..%5csecret.txt", "/%00", "/app.css%00.html", "/.env", "/%2eenv", "/sub/.hidden.html",
                                  "/link.txt", "/tool.py", "/emptydir/", "/nope.html", "/%252e%252e/secret.txt", "/%ff", "/sub//page.html", "/./app.css"])
def test_path_traversal_and_unlisted_files_are_never_served(authed, path):
    s, _, body = authed.req("GET", path)
    assert s in (400, 404) and SECRET.encode() not in body


def test_overlong_target_methods_and_resolver_rules(authed, site, tmp_path):
    assert authed.req("GET", "/" + "a" * 3000)[0] == 414
    for m in ("PUT", "PATCH", "OPTIONS"):
        s, h, _ = authed.req(m, "/app.css")
        assert s == 405 and "GET" in h["allow"]
    assert authed.req("POST", "/api/catalog")[0] == 405
    assert resolve_static(site, "/app.css") == (site / "app.css").resolve()
    assert resolve_static(site, "/") == (site / "index.html").resolve()
    assert resolve_static(site, "/link.txt") is None and resolve_static(site, "/../secret.txt") is None
    big = site / "big.html"
    big.write_bytes(b"x" * 8_000_001)
    assert resolve_static(site, "/big.html") is None


# ------------------------------------------------------------------ writes stay behind operator credentials
def test_a_browser_session_never_authorises_a_write(authed):
    draft = claim(authed.store)
    assert authed.req("POST", "/v1/proposals", {"draft": draft}, {"Idempotency-Key": "k1"})[0] == 401                  # cookie alone
    s, body, _ = authed.json("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "k1"}, cookie=False)
    assert s == 200 and body["local_status"] == "proposed"
    s, again, _ = authed.json("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "k1"})
    assert s == 200 and again == body                                                                               # idempotent retry, cookie ignored
    assert authed.json("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer " + TOKENS["alice"]}, cookie=False)[0] == 400   # no key
    assert authed.json("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer wrong-wrong-wrong-wrong-wrong", "Idempotency-Key": "k2"})[0] == 401
    assert authed.json("POST", "/v1/proposals", {"draft": draft, "token": TOKENS["alice"]}, {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "k3"})[0] == 400
    _, cat, _ = authed.json("GET", "/api/catalog?kind=Claim")
    assert [r["record"]["id"] for r in cat["results"]] == ["claim"]                                                  # the write is visible to the browser read path


def test_write_endpoint_input_limits_and_origin(authed):
    bearer = {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "lim"}
    assert authed.req("POST", "/v1/proposals", "{}", {**bearer, "Content-Type": "text/plain"})[0] == 400
    assert authed.req("POST", "/v1/proposals", "{not json", {**bearer, "Content-Type": "application/json"})[0] == 400
    assert authed.req("POST", "/v1/proposals", {"draft": claim(authed.store)}, {**bearer, "Origin": "https://evil.example"})[0] == 403
    assert authed.req("GET", "/v1/proposals")[0] == 405
    assert authed.req("POST", "/v1/nope", {}, bearer)[0] == 400
    # oversize is refused from the header alone; the body is never read
    c = http.client.HTTPConnection("127.0.0.1", authed.port, timeout=5)
    c.putrequest("POST", "/v1/proposals")
    for k, v in {**bearer, "Content-Type": "application/json", "Content-Length": "3000000"}.items():
        c.putheader(k, v)
    c.endheaders()
    assert c.getresponse().status == 413
    c.close()
    c = http.client.HTTPConnection("127.0.0.1", authed.port, timeout=5)
    c.putrequest("POST", "/v1/proposals")
    for k, v in {**bearer, "Content-Type": "application/json"}.items():
        c.putheader(k, v)
    c.endheaders()
    assert c.getresponse().status == 411
    c.close()
    c = http.client.HTTPConnection("127.0.0.1", authed.port, timeout=5)
    c.putrequest("POST", "/v1/proposals")
    for k, v in {**bearer, "Content-Type": "application/json", "Transfer-Encoding": "chunked"}.items():
        c.putheader(k, v)
    c.endheaders()
    assert c.getresponse().status == 400
    c.close()


def test_protocol_reads_accept_a_session_or_a_bearer_but_not_nothing(authed):
    a, _ = seed(authed.store)
    body = {"target": ref(a)}
    assert authed.req("POST", "/v1/read/get", body, cookie=False)[0] == 401
    assert authed.json("POST", "/v1/read/get", body)[0] == 200
    assert authed.json("POST", "/v1/read/get", body, {"Authorization": "Bearer " + TOKENS["alice"]}, cookie=False)[0] == 200


@pytest.mark.parametrize("public_read", [False, True])
def test_identity_requires_its_own_bearer_even_with_public_access_or_session(store, site, public_read):
    w = Web(store, site, public_read=public_read)
    try:
        if not public_read:
            assert w.login()[0] == 200
        assert w.json("POST", "/v1/read/identity", {})[0] == 401
        assert w.json("POST", "/v1/read/identity", {}, {"Authorization": "Bearer unknown"})[0] == 401
        headers = {"Authorization": "Bearer " + TOKENS["alice"]}
        status, body, response_headers = w.json("POST", "/v1/read/identity", {}, headers)
        assert status == 200 and body == {"principal": store.principal(TOKENS["alice"])}
        assert response_headers["cache-control"] == "no-store"
        assert TOKENS["alice"] not in json.dumps(body)
        assert w.json("POST", "/v1/read/identity", {"actor": "bob"}, headers)[0] == 400
        assert w.json("POST", "/v1/read/identity", {"token": TOKENS["alice"]})[0] == 400
        assert w.json("POST", "/v1/proposals", {"draft": claim(store)},
                      {"Idempotency-Key": "identity-is-not-session-auth"})[0] == 401
        bob = {"Authorization": "Bearer " + TOKENS["bob"]}
        assert w.json("POST", "/v1/read/identity", {}, bob)[1]["principal"]["actor"] == "bob"
    finally:
        w.close()


# ------------------------------------------------------------------ logs and persistence
def test_logs_carry_method_path_status_and_never_secrets(store, site, caplog):
    caplog.set_level(logging.INFO, logger="frontier.web")
    w = Web(store, site)
    try:
        w.login()
        bearer = "Bearer " + TOKENS["alice"]
        w.req("GET", "/api/catalog?query=SECRET-QUERY-TEXT")
        w.req("POST", "/v1/proposals", {"draft": claim(store)}, {"Authorization": bearer, "Idempotency-Key": "log1"}, cookie=False)
        w.req("GET", "/api/record?namespace=x&kind=Claim&id=a&version=" + "0" * 64)
        w.req("GET", "/%2e%2e/secret.txt")
        w.login("a-wrong-token-1234567890")
        sid = w.cookie.split("=", 1)[1]
    finally:
        w.close()
    text = caplog.text
    for forbidden in (GATE, TOKENS["alice"], sid, w.csrf, "SECRET-QUERY-TEXT", "a-wrong-token-1234567890", "Bearer", "Cookie"):
        assert forbidden not in text, forbidden
    assert "GET /api/catalog 200" in text and "POST /v1/proposals 200" in text and "POST /api/session 401" in text


def test_data_survives_a_restart_but_sessions_do_not(store, site):
    w1 = Web(store, site)
    w1.login()
    old_cookie = w1.cookie
    draft = claim(store)
    s, proposed, _ = w1.json("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "persist"}, cookie=False)
    assert s == 200
    w1.close()
    w2 = Web(Store(store.dsn, store.namespace, store.schema), site)          # a new process's worth of state over the same database
    try:
        assert w2.req("GET", "/api/catalog", headers={"Cookie": old_cookie}, cookie=False)[0] == 401     # sessions are in memory
        w2.login()
        _, cat, _ = w2.json("GET", "/api/catalog?kind=Claim")
        assert cat["results"][0]["record"] == proposed["record"]
        s, replay, _ = w2.json("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer " + TOKENS["alice"], "Idempotency-Key": "persist"}, cookie=False)
        assert s == 200 and replay == proposed                                                              # idempotency record persisted too
    finally:
        w2.close()


def test_construction_refuses_unsafe_configurations(store, site):
    with pytest.raises(ValueError):
        WebConfig.with_tokens("short")
    with pytest.raises(ValueError):
        WebConfig.with_tokens()
    with pytest.raises(ValueError):
        make_web_server(store, WebConfig(site_dir=site))
    from frontier.web import WebServer
    with pytest.raises(ValueError):
        WebServer(("0.0.0.0", 0), object)
    assert GATE not in repr(WebConfig.with_tokens(GATE)) and "sha256" not in repr(WebConfig.with_tokens(GATE))


def test_cli_refuses_to_start_without_an_access_token(store, tmp_path):
    env = {"PATH": os.environ["PATH"], "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(ROOT)}
    r = subprocess.run([sys.executable, "-m", "frontier.web", "--namespace", store.namespace, "--schema", store.schema, "--port", "0"],
                       env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "FRONTIER_ACCESS_TOKEN" in r.stderr
    r = subprocess.run([sys.executable, "-m", "frontier.web", "--namespace", store.namespace, "--schema", store.schema, "--port", "0"],
                       env={**env, "FRONTIER_ACCESS_TOKEN": "short"}, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "short" not in r.stderr.replace("FRONTIER_ACCESS_TOKEN", "")


def test_cli_process_serves_over_a_real_socket_with_the_environment_token(store, site):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    env = {"PATH": os.environ["PATH"], "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(ROOT), "MORPHOSWARM_STUDIO_TOKEN": GATE, "OMP_NUM_THREADS": "1"}
    p = subprocess.Popen([sys.executable, "-m", "frontier.web", "--namespace", store.namespace, "--schema", store.schema, "--port", str(port),
                          "--site", str(site), "--insecure-cookies"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        import time
        for _ in range(100):
            try:
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                c.request("GET", "/api/health")
                if c.getresponse().status == 200:
                    break
            except OSError:
                time.sleep(0.1)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        c.request("POST", "/api/session", json.dumps({"token": GATE}), {"Content-Type": "application/json"})
        assert c.getresponse().status == 200
    finally:
        p.terminate()
        _, err = p.communicate(timeout=10)
    assert GATE not in err and "listening 127.0.0.1" in err


# ------------------------------------------------------------------ admin tool
@pytest.fixture
def credir(tmp_path):
    d = tmp_path / "creds"
    d.mkdir(mode=0o700)
    d.chmod(0o700)
    return d


def prov(store, credir, name="agent.cred", actor="agent-1", operator="op-1", roles=("contributor",)):
    return admin.provision(store, actor=actor, operator=operator, roles=set(roles), namespaces=[store.namespace], daily_limit=50, credential_file=credir / name)


def test_admin_bootstrap_is_idempotent_and_status_is_read_only(stores):
    s = stores()
    first = admin.bootstrap(s)
    second = admin.bootstrap(s)
    assert first["initialized"] and second["records"] == first["records"] == 0
    listed = admin.status(s)
    assert {p["actor"] for p in listed["principals"]} == {"alice", "bob", "carol", "alias"}      # identities only
    assert not any("hash" in k or "token" in k for p in listed["principals"] for k in p)
    s.submit(TOKENS["alice"], "adm-s1", claim(s))
    assert admin.status(s)["by_kind_and_local_status"] == [{"kind": "Claim", "local_status": "proposed", "count": 1}, {"kind": "Event", "local_status": "proposed", "count": 1}]


def test_admin_provision_writes_a_private_credential_file_and_prints_no_secret(store, credir):
    out = prov(store, credir)
    f = credir / "agent.cred"
    assert out["status"] == "provisioned" and stat.S_IMODE(f.stat().st_mode) == 0o600
    token = f.read_text().strip()
    assert token not in json.dumps(out) and store.principal(token)["actor"] == "agent-1" and store.principal(token)["roles"] == ["contributor"]
    again = prov(store, credir)
    assert again["status"] == "already_provisioned" and f.read_text().strip() == token                    # idempotent, never overwritten
    with pytest.raises(admin.AdminError, match="different principal"):
        prov(store, credir, actor="someone-else")
    f.write_text("frontier-unknown-credential-000000000000\n")
    with pytest.raises(admin.AdminError, match="not recognised"):
        prov(store, credir)
    f.chmod(0o644)
    with pytest.raises(admin.AdminError, match="accessible to others"):
        prov(store, credir)


def test_admin_refuses_unsafe_locations_and_role_mixing(store, credir, tmp_path):
    loose = tmp_path / "loose"
    loose.mkdir(mode=0o755)
    loose.chmod(0o755)
    with pytest.raises(admin.AdminError, match="chmod 700"):
        prov(store, loose)
    inside_repo = ROOT / "tests" / "_cred_scratch"
    inside_repo.mkdir(mode=0o700, exist_ok=True)
    try:
        with pytest.raises(admin.AdminError, match="outside any git work tree"):
            prov(store, inside_repo)
    finally:
        inside_repo.rmdir()
    with pytest.raises(admin.AdminError, match="does not exist"):
        prov(store, credir / "nope", name="x")
    with pytest.raises(admin.AdminError, match="stays separate"):
        prov(store, credir, name="mix", roles=("reviewer", "contributor"))
    with pytest.raises(admin.AdminError, match="non-empty subset"):
        prov(store, credir, name="bad", roles=("admin",))
    assert not (credir / "mix").exists() and not (credir / "bad").exists()


def test_admin_keeps_reviewer_authority_on_its_own_operator(store, credir):
    prov(store, credir, name="w.cred", actor="writer-1", operator="op-writer", roles=("contributor", "coordinator"))
    with pytest.raises(admin.AdminError, match="other side of the review boundary"):
        prov(store, credir, name="r1.cred", actor="rev-1", operator="op-writer", roles=("reviewer",))
    prov(store, credir, name="r2.cred", actor="rev-1", operator="op-rev", roles=("reviewer",))
    with pytest.raises(admin.AdminError, match="other side of the review boundary"):
        prov(store, credir, name="w2.cred", actor="writer-2", operator="op-rev", roles=("contributor",))
    assert not (credir / "r1.cred").exists() and not (credir / "w2.cred").exists()


def test_admin_provisioned_reviewer_can_accept_only_what_another_operator_submitted(store, credir):
    from frontier.store import Forbidden
    prov(store, credir, name="w.cred", actor="writer-1", operator="op-writer", roles=("contributor",))
    prov(store, credir, name="r.cred", actor="rev-1", operator="op-rev", roles=("reviewer",))
    w, r = (credir / "w.cred").read_text().strip(), (credir / "r.cred").read_text().strip()
    rec = store.submit(w, "adm-1", claim(store, issuer="writer-1"))["record"]
    seeded_status = store.get(ref(rec))["local_review"]["status"]
    assert seeded_status == "proposed"                                         # nothing is auto-accepted
    with pytest.raises(Forbidden):
        store.review(w, "adm-self", assessment(ref(rec), "writer-1"))          # writer has no reviewer role
    assert store.review(r, "adm-rev", assessment(ref(rec), "rev-1"))["local_status"] == "accepted"


def test_admin_cli_never_prints_or_takes_a_credential(store, credir):
    env = {"PATH": os.environ["PATH"], "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(ROOT)}
    base = [sys.executable, "-m", "frontier.admin"]
    common = ["--namespace", store.namespace, "--schema", store.schema]
    r = subprocess.run(base + ["bootstrap"] + common, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout)["initialized"] is True
    cmd = base + ["provision"] + common + ["--actor", "cli-agent", "--operator", "op-cli", "--roles", "contributor", "--credential-file", str(credir / "cli.cred")]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    token = (credir / "cli.cred").read_text().strip()
    assert r.returncode == 0 and token not in r.stdout + r.stderr and json.loads(r.stdout)["status"] == "provisioned" and token not in " ".join(cmd)
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "already_provisioned"
    r = subprocess.run(base + ["status"] + common, env=env, capture_output=True, text=True, timeout=60)
    assert token not in r.stdout and "cli-agent" in r.stdout
    r = subprocess.run(base + ["provision"] + common + ["--actor", "x", "--operator", "y", "--roles", "reviewer,contributor", "--credential-file", str(credir / "z.cred")],
                       env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "stays separate" in r.stderr


# ------------------------------------------------------------------ deploy files (static checks; installation is root's)
DEPLOY = ROOT / "deploy"


def test_nginx_vhost_is_exact_name_loopback_and_redacted():
    conf = (DEPLOY / "nginx" / "frontier.morphoswarm.ai.conf").read_text()
    code = "\n".join(line for line in conf.splitlines() if not line.strip().startswith("#"))
    assert re.search(r"server_name\s+frontier\.morphoswarm\.ai\s*;", code) and "*.morphoswarm.ai" not in code and "morphoswarm.ai;" in code
    assert code.count("server_name") == 1 and "listen 443 ssl" in code
    assert "proxy_pass http://127.0.0.1:8971;" in code and "access_log /var/log/nginx/frontier.access.log morphoswarm_redacted;" in code
    assert "log_format" not in code and "$args" not in code and "$request_uri" not in code and "$http_cookie" not in code
    # The MCP proxy must forward each caller's bearer without logging it.
    auth_lines = [line.strip() for line in code.splitlines() if "$http_authorization" in line]
    assert auth_lines == ["proxy_set_header Authorization $http_authorization;"]
    assert "ssl_certificate /etc/ssl/morphoswarm.ai/fullchain.pem;" in code and "ssl_certificate_key /etc/ssl/morphoswarm.ai/privkey.pem;" in code
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in code and "proxy_set_header Host $host;" in code
    assert not re.search(r"(?i)token\s*=|bearer\s+\w{10,}", code)
    for global_directive in ("worker_processes", "events {", "http {", "user ", "error_log /"):
        assert global_directive not in code


@pytest.mark.parametrize("unit", ["delphi-frontier-postgres.service", "delphi-frontier-web.service"])
def test_systemd_units_are_bounded_and_carry_no_secrets(unit):
    text = (DEPLOY / "systemd" / unit).read_text()
    for needed in ("MemoryMax=", "MemorySwapMax=0", "TasksMax=", "Restart=", "NoNewPrivileges=yes"):
        assert needed in text, needed
    assert "RuntimeMaxSec" not in text                                   # services are persistent by design
    assert not re.search(r"(?i)(token|password|secret)\s*=\s*\S{8,}", text.replace("EnvironmentFile", ""))
    if unit.endswith("web.service"):
        assert "--port 8971" in text and "OMP_NUM_THREADS=1" in text and "delphi-frontier-postgres.service" in text
        assert "ExecStart=/data/services/delphi-frontier/venv/bin/python -m frontier.web" in text and "miniconda" not in text
        assert "EnvironmentFile=-%h/.config/delphi-frontier/web.env" in text and "host=/data/services/delphi-frontier/run port=5471 dbname=frontier user=frontier_app" in text
    else:
        assert "-D /data/services/delphi-frontier/pgdata" in text and "UMask=0077" in text and "KillSignal=SIGINT" in text


def test_postgres_scripts_are_unix_socket_only_and_never_touch_other_clusters():
    init = "\n".join(line for line in (DEPLOY / "postgres" / "init-cluster.sh").read_text().splitlines() if not line.strip().startswith("#"))
    assert "listen_addresses = ''" in init and "unix_socket_permissions = 0700" in init and "chmod 700" in init
    assert "auth-host=reject" in init and "peer map=frontier" in init
    assert "5432" not in init and "pg_createcluster" not in init and "/var/lib/postgresql" not in init


# ------------------------------------------------------------------ /api/artifacts (root's ArtifactIndex) and the gated extension-route hook
def seed_artifacts(store):
    from conftest import evidence
    target = store.submit(TOKENS["alice"], "ac", claim(store))["record"]
    for i in range(4):
        d = evidence(store, ref(target))
        d["id"] = f"e-{i}"
        d["visibility"] = "private" if i == 3 else "public"
        d["payload"]["context"] = "geometry roundtrip fixture, not a fish experiment"
        d["payload"]["artifacts"] = [{"title": f"Mesh {i}", "uri": "https://example.org/mesh.stl" if i == 0 else "urn:sha256:" + str(i) * 64,
                                      "sha256": str(i) * 64, "byte_size": 256, "media_type": "model/stl", "role": "geometry", "availability": "unavailable"}]
        store.submit(TOKENS["alice"], f"e-{i}", d)


def test_artifacts_endpoint_is_gated_public_only_paged_and_never_fetches(authed):
    seed_artifacts(authed.store)
    assert authed.req("GET", "/api/artifacts", cookie=False)[0] == 401
    s, body, _ = authed.json("GET", "/api/artifacts?q=geometry&role=geometry&limit=2")
    assert s == 200 and body["mode"] == "live" and len(body["items"]) == 2 and body["next_cursor"]
    _, rest, _ = authed.json("GET", "/api/artifacts?query=geometry&role=geometry&limit=2&after=" + body["next_cursor"])
    got = body["items"] + rest["items"]
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None and {i["artifact"]["sha256"] for i in got} == {str(i) * 64 for i in range(3)}   # the private one never appears
    assert all(i["artifact_bytes_verified"] is False and i["local_status"] == "proposed" for i in got)
    assert any(i["artifact"]["uri"] == "https://example.org/mesh.stl" for i in got)            # a declaration is data; the endpoint never opens it
    from conftest import evidence
    for hostile in ("file:///etc/passwd", "http://127.0.0.1:1/x", "https://user:pw@example.org/x"):
        d = evidence(authed.store, ref(authed.store.search(kind="Claim")["results"][0]["ref"]))
        d["id"] = "hostile"
        d["payload"]["artifacts"] = [{"title": "x", "uri": hostile, "sha256": "9" * 64, "byte_size": 1, "media_type": "text/plain", "role": "log", "availability": "unavailable"}]
        with pytest.raises(Exception):
            authed.store.submit(TOKENS["alice"], "h" + str(abs(hash(hostile))), d)                # the store refuses local/credentialed pointers outright
    assert authed.json("GET", "/api/artifacts?role=code")[1]["items"] == []
    assert authed.json("GET", "/api/artifacts?evidence_kind=observed")[1]["items"] == []
    for bad in ("limit=51", "limit=0", "limit=x", "role=executable", "evidence_kind=guess", "q=" + "x" * 201, "q=a&query=a", "bogus=1", "after=%25%25%25%25",
                "q=geometry&after=" + body["next_cursor"]):
        assert authed.json("GET", "/api/artifacts?" + bad)[0] == 400, bad


def test_web_and_artifact_modules_have_no_fetch_or_exec_capability():
    import ast
    imported, called = set(), set()
    for name in ("web.py", "artifacts.py"):
        for node in ast.walk(ast.parse((ROOT / "frontier" / name).read_text())):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Call):
                called.add(("builtin:" if isinstance(node.func, ast.Name) else "attr:") + (node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")))
    assert not imported & {"urllib.request", "http.client", "requests", "httpx", "subprocess", "socket", "importlib", "ctypes", "pickle"}, imported
    assert not called & {"builtin:eval", "builtin:exec", "builtin:open", "builtin:compile", "builtin:__import__", "attr:system", "attr:popen", "attr:urlopen", "attr:create_connection"}, called


def route_web(store, site, handler, **kw):
    from frontier.web import Route
    return Web(store, site, routes={"POST /api/engineering/solve": Route(handler, **kw)})


def test_extension_route_needs_session_origin_csrf_and_a_small_json_object(store, site):
    from frontier.store import FrontierError
    calls = []

    def solver(req):
        calls.append(req)
        if req["body"].get("explode"):
            raise RuntimeError("SECRET-INTERNAL-DETAIL")
        if req["body"].get("refuse"):
            err = FrontierError("Unsupported request")
            err.http_status, err.code = 422, "unsupported"
            raise err
        return 200, {"ok": True, "echo": req["body"], "store_namespace": req["store"].namespace}
    w = route_web(store, site, solver)
    try:
        path = "/api/engineering/solve"
        origin = {"Origin": f"http://127.0.0.1:{w.port}"}
        assert w.req("POST", path, {"x": 1}, origin, cookie=False)[0] == 401
        w.login()
        assert w.req("POST", path, {"x": 1}, {})[0] == 403                                              # no Origin
        assert w.req("POST", path, {"x": 1}, {"Origin": "https://evil.example", "X-CSRF-Token": w.csrf})[0] == 403
        assert w.req("POST", path, {"x": 1}, origin)[0] == 403                                          # no CSRF header
        assert w.req("POST", path, {"x": 1}, {**origin, "X-CSRF-Token": "wrong"})[0] == 403
        assert calls == []
        good = {**origin, "X-CSRF-Token": w.csrf}
        s, body, _ = w.json("POST", path, {"x": 1}, good)
        assert s == 200 and body["echo"] == {"x": 1} and body["store_namespace"] == store.namespace and calls[-1]["method"] == "POST"
        assert w.req("POST", path, [1, 2], good)[0] == 400 and w.req("POST", path, "nope", {**good, "Content-Type": "application/json"})[0] == 400
        assert w.req("POST", path, json.dumps({"x": 1}), {**good, "Content-Type": "text/plain"})[0] == 400
        assert w.req("POST", path, json.dumps({"pad": "x" * 1100}), {**good, "Content-Type": "application/json"})[0] == 413      # > 1024 bytes
        assert len(calls) == 1
        s, body, _ = w.json("POST", path, {"refuse": 1}, good)
        assert s == 422 and body["error"] == "unsupported"
        s, _, raw = w.req("POST", path, {"explode": 1}, good)
        assert s == 500 and b"SECRET-INTERNAL-DETAIL" not in raw
        assert w.req("GET", path)[0] == 405 and "POST" in w.req("GET", path)[1]["allow"]
        w.req("DELETE", "/api/session", headers=good)
        assert w.req("POST", path, {"x": 1}, good)[0] == 401                                          # session gone
    finally:
        w.close()


def test_extension_route_bounds_concurrency_and_rejects_shadowing(store, site):
    from threading import Event
    from frontier.web import Route
    started, release = Event(), Event()

    def slow(req):
        started.set()
        release.wait(10)
        return 200, {"done": True}
    w = route_web(store, site, slow, max_concurrent=1)
    try:
        w.login()
        headers = {"Origin": f"http://127.0.0.1:{w.port}", "X-CSRF-Token": w.csrf}
        first = []
        t = Thread(target=lambda: first.append(w.req("POST", "/api/engineering/solve", {"a": 1}, headers)[0]))
        t.start()
        assert started.wait(5)
        s, h, _ = w.req("POST", "/api/engineering/solve", {"a": 2}, headers)
        assert s == 503 and h["retry-after"] == "2"
        release.set()
        t.join(10)
        assert first == [200] and w.req("POST", "/api/engineering/solve", {"a": 3}, headers)[0] == 200      # slot freed
    finally:
        release.set()
        w.close()
    for key in ("POST /api/catalog", "POST /api/artifacts", "PUT /api/x", "POST /elsewhere", "POST /api/../v1/x", "POST /api/A"):
        with pytest.raises(ValueError):
            WebConfig.with_tokens(GATE, routes={key: Route(lambda r: (200, {}))})
    with pytest.raises(ValueError):
        Route(lambda r: (200, {}), max_body=10**6)


# ------------------------------------------------------------------ engineering solver wiring (root's engineering_api, late import)
def test_engineering_route_is_a_clear_503_when_the_solver_module_is_absent(authed, monkeypatch):
    monkeypatch.setitem(sys.modules, "frontier.engineering_api", None)
    headers = {"Origin": f"http://127.0.0.1:{authed.port}", "X-CSRF-Token": authed.csrf}
    s, body, _ = authed.json("POST", "/api/engineering/solve", {"rho": "1.2"}, headers)
    assert s == 503 and body["error"] == "engineering_unavailable" and "result" not in body
    assert authed.req("POST", "/api/engineering/solve", {"rho": "1.2"}, {}, cookie=False)[0] == 401
    assert authed.req("POST", "/api/engineering/solve", {"rho": "1.2"}, {"Origin": headers["Origin"]})[0] == 403      # no CSRF
    assert authed.req("POST", "/api/engineering/solve", json.dumps({"pad": "x" * 1100}), {**headers, "Content-Type": "application/json"})[0] == 413


def test_engineering_route_passes_the_solvers_answer_and_typed_errors_through_unchanged(authed, monkeypatch):
    import types
    from frontier.store import FrontierError
    seen = []

    def solve_design(data):
        seen.append(data)
        if data.get("busy"):
            e = FrontierError("Solver busy")
            e.http_status, e.code = 503, "busy"
            raise e
        if data.get("bad"):
            raise FrontierError("Invalid design request")
        return {"schema": "frontier.engineering.solve/1", "result": {"echo": data}}
    monkeypatch.setitem(sys.modules, "frontier.engineering_api", types.SimpleNamespace(solve_design=solve_design))
    headers = {"Origin": f"http://127.0.0.1:{authed.port}", "X-CSRF-Token": authed.csrf}
    s, body, _ = authed.json("POST", "/api/engineering/solve", {"rho": "1.2", "relax_envelopes": True}, headers)
    assert s == 200 and body == {"schema": "frontier.engineering.solve/1", "result": {"echo": {"rho": "1.2", "relax_envelopes": True}}}
    assert seen == [{"rho": "1.2", "relax_envelopes": True}]
    assert authed.json("POST", "/api/engineering/solve", {"busy": 1}, headers)[0] == 503
    s, body, _ = authed.json("POST", "/api/engineering/solve", {"bad": 1}, headers)
    assert s == 400 and body["error"] == "invalid_request"
    assert len(seen) == 3
    assert authed.req("POST", "/api/engineering/solve", [1], headers)[0] == 400 and len(seen) == 3                      # arrays never reach the solver


# ------------------------------------------------------------------ runtime2: SearchIndex default, /api/attention, /api/beliefs/solve
def test_main_defaults_to_the_search_index_and_labels_it(store, site):
    from frontier.web import default_search
    fn, label = default_search(store)
    assert label == "search_index" and fn.__name__ == "query"
    seed(store)
    w = Web(store, site, catalog_search=fn, search_mode=label)
    try:
        w.login()
        s, body, _ = w.json("GET", "/api/catalog?kind=Claim&query=claim-a")
        assert s == 200 and body["search_mode"] == "search_index" and "lexical" in body["search_kind"]
        row = body["results"][0]
        assert row["record"]["id"] == "claim-a" and row["local_status"] == "proposed" and row["why_matched"]
        assert "score" in row["match"] and "curation" in row["match"] and "match" not in row["record"]               # explanation kept apart from the record
        s, p1, _ = w.json("GET", "/api/catalog?limit=1")
        assert p1["next_cursor"] and w.json("GET", "/api/catalog?limit=1&after=" + p1["next_cursor"])[0] == 200        # the index's own cursor round-trips
        for bad in ("limit=51", "kind=Bogus", "status=bogus", "after=not-a-cursor", "bogus=1"):
            assert w.json("GET", "/api/catalog?" + bad)[0] == 400, bad
    finally:
        w.close()


def test_cli_default_catalog_uses_the_search_index_and_legacy_flag_restores_the_old_one(store, site):
    def run_cli(*extra):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        env = {"PATH": os.environ["PATH"], "FRONTIER_DSN": store.dsn, "PYTHONPATH": str(ROOT), "FRONTIER_ACCESS_TOKEN": GATE, "OMP_NUM_THREADS": "1"}
        p = subprocess.Popen([sys.executable, "-m", "frontier.web", "--namespace", store.namespace, "--schema", store.schema, "--port", str(port),
                              "--site", str(site), "--insecure-cookies", *extra], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import time
            for _ in range(100):
                try:
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                    c.request("GET", "/api/health")
                    if c.getresponse().status == 200:
                        break
                except OSError:
                    time.sleep(0.1)
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            c.request("POST", "/api/session", json.dumps({"token": GATE}), {"Content-Type": "application/json"})
            r = c.getresponse()
            r.read()
            cookie = r.getheader("Set-Cookie").split(";")[0]
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            c.request("GET", "/api/catalog?limit=1", headers={"Cookie": cookie})
            return json.loads(c.getresponse().read())["search_mode"]
        finally:
            p.terminate()
            p.wait(10)
    assert run_cli() == "search_index"
    assert run_cli("--legacy-catalog") == "store_lexical"


def fake_attention(calls):
    def build_view(records, events, annotations, now):
        calls.append({"records": records, "events": events, "annotations": annotations, "now": now})
        return {"stand_in": True, "problems": len([r for r in records if r["kind"] == "Problem"])}
    return build_view


def test_attention_is_gated_public_only_cached_and_parameterless(store, site):
    calls = []
    seed(store)
    store.submit(TOKENS["alice"], "att-priv", claim(store, id="hidden-private", visibility="private"))
    w = Web(store, site, attention_build=fake_attention(calls), attention_ttl=60)
    try:
        assert w.req("GET", "/api/attention", cookie=False)[0] == 401
        w.login()
        s, body, _ = w.json("GET", "/api/attention")
        assert s == 200 and body["mode"] == "live" and body["namespace"] == store.namespace and body["view"]["stand_in"] is True
        assert body["inputs"]["public_only"] is True and body["inputs"]["annotations"] == 0 and "annotation documents" in body["inputs"]["note"]
        c = calls[0]
        assert {r["id"] for r in c["records"]} == {"claim-a", "claim-b"} and all(r["kind"] != "Event" for r in c["records"])       # public records, no events in records
        assert c["events"] and all("sequence" in e and e["envelope"]["kind"] == "Event" for e in c["events"]) and c["annotations"] == []
        assert "hidden-private" not in json.dumps(c) and all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\+00:00|Z)", c["now"]) for _ in [0])
        assert body["inputs"]["records"] == 2 and body["inputs"]["events"] == len(c["events"])
        w.json("GET", "/api/attention")
        assert len(calls) == 1                                                                                 # reused within the ttl
        for bad in ("now=2020-01-01T00:00:00Z", "records=1", "x"):
            assert w.json("GET", "/api/attention?" + bad)[0] == 400
        assert w.req("POST", "/api/attention", {})[0] in (405, 400, 403)
        assert GATE not in json.dumps(body) and TOKENS["alice"] not in json.dumps(body)
    finally:
        w.close()


def test_attention_refuses_to_build_a_partial_view_and_is_503_when_the_layer_is_absent(store, site, monkeypatch):
    seed(store)
    w = Web(store, site, attention_build=fake_attention([]), attention_max_records=1)
    try:
        w.login()
        s, body, _ = w.json("GET", "/api/attention")
        assert s == 422 and body["error"] == "view_too_large"
    finally:
        w.close()
    monkeypatch.setitem(sys.modules, "attention.view", None)
    monkeypatch.setitem(sys.modules, "attention", None)
    w = Web(store, site)
    try:
        w.login()
        s, body, _ = w.json("GET", "/api/attention")
        assert s == 503 and body["error"] == "attention_unavailable" and "view" not in body
    finally:
        w.close()


def beliefs_post(w, body, **kw):
    return w.json("POST", "/api/beliefs/solve", body, {"Origin": f"http://127.0.0.1:{w.port}", "X-CSRF-Token": w.csrf})


def test_beliefs_route_is_503_when_the_director_adapter_is_absent(authed, monkeypatch):
    monkeypatch.setitem(sys.modules, "frontier.beliefs_api", None)
    s, body, _ = beliefs_post(authed, {"schema": "frontier-beliefs-0.1"})
    assert s == 503 and body["error"] == "beliefs_unavailable" and "result" not in body and "status" not in body


def test_beliefs_route_passes_the_adapters_envelopes_and_labelled_errors_through_verbatim(authed, monkeypatch):
    import types
    from frontier.store import FrontierError
    seen = []

    def solve_scenario(data):
        seen.append(data)
        if data.get("bad"):
            e = FrontierError("Scenario rejected: needs 2..6 states")
            e.code, e.http_status = "invalid_request", 400
            e.body = {"schema": "frontier.beliefs.api/1", "status": "error", "calibrated": False, "error": {"code": "invalid_request", "message": e.args[0]}}
            raise e
        if data.get("busy"):
            e = FrontierError("Two belief solves are already running")
            e.code, e.http_status = "solver_busy", 429
            e.body = {"schema": "frontier.beliefs.api/1", "status": "error", "calibrated": False, "error": {"code": "solver_busy", "message": "retry"}}
            raise e
        return {"schema": "frontier.beliefs.api/1", "status": "unknown", "calibrated": False, "reason": "Compute budget exhausted"} if data.get("slow") else \
               {"schema": "frontier.beliefs.api/1", "status": "ok", "calibrated": False, "result": {"decision": {"actions": {"a": {"expected_value": "17/5"}}}}}
    monkeypatch.setitem(sys.modules, "frontier.beliefs_api", types.SimpleNamespace(solve_scenario=solve_scenario))
    s, body, _ = beliefs_post(authed, {"x": 1})
    assert s == 200 and body["calibrated"] is False and body["result"]["decision"]["actions"]["a"]["expected_value"] == "17/5" and seen == [{"x": 1}]
    s, body, _ = beliefs_post(authed, {"slow": 1})
    assert s == 200 and body["status"] == "unknown"                                  # the adapter's own timeout answer is not turned into an HTTP error
    s, body, _ = beliefs_post(authed, {"bad": 1})
    assert s == 400 and body["calibrated"] is False and body["error"]["code"] == "invalid_request" and "2..6 states" in body["error"]["message"]
    s, body, _ = beliefs_post(authed, {"busy": 1})
    assert s == 429 and body["error"]["code"] == "solver_busy" and body["calibrated"] is False


def test_beliefs_route_against_the_real_adapter_example_and_malformed_inputs(authed):
    from frontier.beliefs import EXAMPLE_SCENARIO
    s, body, _ = beliefs_post(authed, EXAMPLE_SCENARIO)
    assert s == 200 and body["schema"] == "frontier.beliefs.api/1" and body["status"] == "ok" and body["calibrated"] is False and "assumed_scope" in body
    evs = [a["expected_value"] for a in body["result"]["decision"]["actions"].values() if "expected_value" in a]
    assert any(isinstance(v, str) and "/" in v for v in evs)                         # exact rationals stay strings
    s, body, _ = beliefs_post(authed, {"schema": "frontier-beliefs-0.1", "variables": "x"})
    assert s == 400 and body["calibrated"] is False and body["status"] == "error"
    s, body, _ = beliefs_post(authed, {"unknown_field": 1})
    assert s == 400 and body["calibrated"] is False


def test_formalize_route_checks_real_constraints_and_preserves_the_gate(authed):
    from engineering.formalize.cases import cantilever_request, oca2_request

    origin = f"http://127.0.0.1:{authed.port}"
    headers = {"Origin": origin, "X-CSRF-Token": authed.csrf}
    request = cantilever_request()
    status, result, _ = authed.json("POST", "/api/formalize/propose", request, headers)
    assert status == 200 and result["status"] == "checked"
    assert result["calibrated"] is False and result["lean"] == "not_run"
    assert result["checks"] and result["not_established"]
    status, refused, _ = authed.json("POST", "/api/formalize/propose", oca2_request(), headers)
    assert status == 200 and refused["status"] == "refused"
    assert authed.req("POST", "/api/formalize/propose", request, headers, cookie=False)[0] == 401
    assert authed.req("POST", "/api/formalize/propose", request, {"Origin": origin})[0] == 403
    assert authed.req("POST", "/api/formalize/propose", {"padding": "x" * 16400}, headers)[0] == 413


def test_beliefs_route_has_the_same_gate_and_a_32k_body_bound(authed, monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "frontier.beliefs_api", types.SimpleNamespace(solve_scenario=lambda d: {"ok": True}))
    w = authed
    path, origin = "/api/beliefs/solve", {"Origin": f"http://127.0.0.1:{w.port}"}
    assert w.req("POST", path, {"x": 1}, origin, cookie=False)[0] == 401
    assert w.req("POST", path, {"x": 1}, {})[0] == 403
    assert w.req("POST", path, {"x": 1}, {"Origin": "https://evil.example", "X-CSRF-Token": w.csrf})[0] == 403
    assert w.req("POST", path, {"x": 1}, origin)[0] == 403
    assert w.req("GET", path)[0] == 405
    good = {**origin, "X-CSRF-Token": w.csrf, "Content-Type": "application/json"}
    assert w.req("POST", path, json.dumps({"pad": "x" * 40000}), good)[0] == 413
    assert w.req("POST", path, json.dumps({"pad": "x" * 30000}), good)[0] == 200
    assert w.req("POST", path, "[1]", good)[0] == 400


def test_attention_module_is_an_allow_listed_choice_and_absent_is_503(store, site, monkeypatch):
    from frontier.web import ATTENTION_MODULES
    assert ATTENTION_MODULES == ("attention.view", "frontier_attention.view", "frontier.attention.view", "frontier.attention")
    for name in ATTENTION_MODULES:
        monkeypatch.setitem(sys.modules, name, None)
    w = Web(store, site, attention_module="frontier.attention")
    try:
        w.login()
        s, body, _ = w.json("GET", "/api/attention")
        assert s == 503 and body["error"] == "attention_unavailable"
    finally:
        w.close()
    w = Web(store, site, attention_module="os.path")                  # not on the allow-list: refused, never imported
    try:
        w.login()
        assert w.json("GET", "/api/attention")[0] == 400
    finally:
        w.close()


def test_video_types_are_served_only_from_guarded_artifacts_with_range_support(authed, site):
    art = site / "artifacts"
    art.mkdir(exist_ok=True)
    payload = bytes(range(256)) * 40
    (art / "clip.mp4").write_bytes(payload)
    (art / "clip.webm").write_bytes(payload)
    (site / "other").mkdir(exist_ok=True)
    (site / "other" / "clip.mp4").write_bytes(payload)
    for name, mime in (("clip.mp4", "video/mp4"), ("clip.webm", "video/webm")):
        s, h, body = authed.req("GET", "/artifacts/" + name)
        assert s == 200 and h["content-type"] == mime and h["accept-ranges"] == "bytes" and body == payload and "content-disposition" not in h
        s, h, body = authed.req("GET", "/artifacts/" + name, headers={"Range": "bytes=10-19"})
        assert s == 206 and body == payload[10:20] and h["content-range"] == f"bytes 10-19/{len(payload)}" and h["content-length"] == "10"
        s, h, body = authed.req("GET", "/artifacts/" + name, headers={"Range": "bytes=-5"})
        assert s == 206 and body == payload[-5:]
        s, h, body = authed.req("GET", "/artifacts/" + name, headers={"Range": f"bytes={len(payload) - 3}-"})
        assert s == 206 and body == payload[-3:]
        assert authed.req("GET", "/artifacts/" + name, headers={"Range": "bytes=999999-"})[0] == 416
        assert authed.req("GET", "/artifacts/" + name, headers={"Range": "bytes=5-2"})[0] == 416
        assert authed.req("GET", "/artifacts/" + name, headers={"Range": "items=1-2"})[0] == 416
        assert authed.req("GET", "/artifacts/" + name, headers={"Range": "bytes=0-1,5-6"})[0] == 416
        assert authed.req("HEAD", "/artifacts/" + name)[2] == b""
        assert authed.req("GET", "/artifacts/" + name, cookie=False)[0] == 401
    assert authed.req("GET", "/other/clip.mp4")[0] == 404                       # the same type elsewhere in the site is not served
    assert authed.req("GET", "/artifacts/%2e%2e/other/clip.mp4")[0] == 404
    (art / "token-clip.mp4").write_bytes(payload)
    assert authed.req("GET", "/artifacts/token-clip.mp4")[0] == 404
    from frontier import web
    assert web.resolve_static(site, "/artifacts/clip.mp4") is not None
    big = art / "big.mp4"
    with big.open("wb") as f:
        f.truncate(web.MAX_VIDEO_BYTES + 1)                                      # sparse file; refused by size, never read
    assert web.resolve_static(site, "/artifacts/big.mp4") is None


@pytest.mark.parametrize("suffix,content_type", [(".tar.xz", "application/x-xz"), (".zip", "application/zip")])
def test_warmstart_archive_is_an_opaque_download_only_under_artifacts(authed, site, tmp_path, suffix, content_type):
    """Publishing a frozen simulator input must not open arbitrary archives or paths."""
    import lzma

    art = site / "artifacts"
    art.mkdir(exist_ok=True)
    payload = lzma.compress(b"frozen simulation inputs")
    (art / ("bundle" + suffix)).write_bytes(payload)
    status, headers, body = authed.req("GET", "/artifacts/bundle" + suffix)
    assert status == 200 and body == payload
    assert headers["content-type"] == content_type
    assert headers["content-disposition"].split(";", 1)[0] == "attachment"
    assert headers["x-content-type-options"] == "nosniff"
    (site / ("outside" + suffix)).write_bytes(payload)
    (art / ("credentials" + suffix)).write_bytes(payload)
    outside = tmp_path / ("outside-archive" + suffix)
    outside.write_bytes(payload)
    (art / ("linked" + suffix)).symlink_to(outside)
    for path in ("/outside" + suffix, "/artifacts/credentials" + suffix, "/artifacts/linked" + suffix):
        assert authed.req("GET", path)[0] == 404


def test_video_captions_serve_as_webvtt_only_inside_artifacts(authed, site, tmp_path):
    art = site / "artifacts"
    art.mkdir(exist_ok=True)
    payload = b"WEBVTT\n\n00:00.000 --> 00:01.000\nA simulated result.\n"
    (art / "captions.vtt").write_bytes(payload)
    status, headers, body = authed.req("GET", "/artifacts/captions.vtt")
    assert status == 200 and body == payload
    assert headers["content-type"] == "text/vtt; charset=utf-8"
    assert headers["x-content-type-options"] == "nosniff"
    assert "attachment" not in headers.get("content-disposition", "")
    (site / "outside.vtt").write_bytes(payload)
    (art / "token-captions.vtt").write_bytes(payload)
    (tmp_path / "external.vtt").write_bytes(payload)
    (art / "link.vtt").symlink_to(tmp_path / "external.vtt")
    for path in ("/outside.vtt", "/artifacts/token-captions.vtt", "/artifacts/link.vtt"):
        assert authed.req("GET", path)[0] == 404


def test_anonymous_session_minting_is_limited_per_client_and_a_cookie_holder_is_not_counted(store, site):
    """The session table is capped and evicts the oldest, so unlimited anonymous minting would sign everyone else out of the calculators."""
    w = Web(store, site, public_read=True, anon_sessions_per_window=3)
    try:
        assert [w.req("GET", "/api/session", cookie=False)[0] for _ in range(3)] == [200, 200, 200]
        status, headers, _ = w.req("GET", "/api/session", cookie=False)
        assert status == 429 and "retry-after" in headers
        assert w.req("GET", "/api/health", cookie=False)[0] == 200            # the limit is on minting, not on the site
    finally:
        w.close()
    w = Web(store, site, public_read=True, anon_sessions_per_window=3)
    try:
        assert w.req("GET", "/api/session", cookie=False)[0] == 200
        w.cookie = None
        s, body, h = w.json("GET", "/api/session", cookie=False)
        w.cookie = h["set-cookie"].split(";")[0]
        for _ in range(6):                                                     # an existing session is reused, never re-minted
            assert w.req("GET", "/api/session")[0] == 200
    finally:
        w.close()
