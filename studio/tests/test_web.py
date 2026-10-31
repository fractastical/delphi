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
        self.cfg = WebConfig.with_tokens(GATE, site_dir=site, **cfg)
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
    code = "\n".join(l for l in conf.splitlines() if not l.strip().startswith("#"))
    assert re.search(r"server_name\s+frontier\.morphoswarm\.ai\s*;", code) and "*.morphoswarm.ai" not in code and "morphoswarm.ai;" in code
    assert code.count("server_name") == 1 and "listen 443 ssl" in code
    assert "proxy_pass http://127.0.0.1:8971;" in code and "access_log /var/log/nginx/frontier.access.log morphoswarm_redacted;" in code
    assert "log_format" not in code and "$args" not in code and "$request_uri" not in code and "$http_cookie" not in code and "$http_authorization" not in code
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
        assert "EnvironmentFile=-%h/.config/delphi-frontier/web.env" in text and "host=/data/services/delphi-frontier/run port=5471 dbname=frontier user=frontier_app" in text
    else:
        assert "-D /data/services/delphi-frontier/pgdata" in text and "UMask=0077" in text and "KillSignal=SIGINT" in text


def test_postgres_scripts_are_unix_socket_only_and_never_touch_other_clusters():
    init = "\n".join(l for l in (DEPLOY / "postgres" / "init-cluster.sh").read_text().splitlines() if not l.strip().startswith("#"))
    assert "listen_addresses = ''" in init and "unix_socket_permissions = 0700" in init and "chmod 700" in init
    assert "auth-host=reject" in init and "peer map=frontier" in init
    assert "5432" not in init and "pg_createcluster" not in init and "/var/lib/postgresql" not in init
