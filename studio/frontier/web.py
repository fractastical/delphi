"""Loopback website/API adapter for the persistent Frontier node.

Binds 127.0.0.1 only (nginx terminates TLS in front of it). It reuses `Application` and the `Store`; it adds no store behaviour.

Access model
* Browser reads (static site + /api/catalog, /api/record, /api/events) need a server-side session created by presenting the access token
  (FRONTIER_ACCESS_TOKEN, else the studio's MORPHOSWARM_STUDIO_TOKEN from the service's EnvironmentFile). Compared in constant time.
  Cookie: HttpOnly; SameSite=Strict; Secure (the `__Host-` prefix when Secure); Path=/. Unsafe cookie-authenticated requests also need the CSRF header and an allowed Origin.
* A session never authorises a write. POST /v1/proposals, /v1/reviews, ... still need an operator `Authorization: Bearer` credential and an `Idempotency-Key`,
  exactly as in the loopback protocol adapter (frontier/http.py), which stays available for protocol tests.
* Host must be the public name or loopback:port; an Origin header, when present, must be the public origin or loopback:port. Anything else is refused.
* /api/health is public and carries no detail. Sign-in links with ?token= are deliberately NOT supported (a URL secret leaks into history and Referer).
* Logs carry method, path (no query), status. Never headers, cookies, bodies or tokens.
"""
import argparse
import hmac
import json
import logging
import os
import re
import secrets
import sys
import time
from collections import deque
from datetime import datetime, timezone
from dataclasses import dataclass, field
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from threading import BoundedSemaphore, Lock
from typing import Callable
from urllib.parse import parse_qs, unquote, urlsplit

from .artifacts import ArtifactIndex
from .http import Application
from .models import KINDS, MAX_BUNDLE_BYTES, Ref, canonical
from .search import SEARCH_KIND, SearchIndex
from .system_status import SystemStatus
from .store import FrontierError, Store

log = logging.getLogger("frontier.web")
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon",
        ".txt": "text/plain; charset=utf-8", ".woff2": "font/woff2"}
# Extra types, served ONLY from <site>/artifacts/ (the guarded artifact subtree), never from the rest of the site.
ARTIFACT_MIME = {".stl": "model/stl", ".obj": "model/obj", ".glb": "model/gltf-binary", ".csv": "text/csv; charset=utf-8",
                 ".lean": "text/plain; charset=utf-8", ".trig": "application/trig",
                 ".mp4": "video/mp4", ".webm": "video/webm"}
STREAMED = {".mp4", ".webm"}                                                  # served by seek+chunk with Range support, never read whole into memory
MAX_VIDEO_BYTES = 64_000_000
ARTIFACT_DOWNLOAD = {".stl", ".obj", ".glb"}                                   # binary models download; text types render as text
SENSITIVE_NAME = re.compile(r"(secret|token|credential|password|passwd|private|apikey|api_key|\.pem|\.key|\.env|id_rsa)", re.I)
MAX_STATIC_BYTES = 8_000_000
MAX_ARTIFACT_BYTES = 16_000_000
MAX_PATH = 2048
CATALOG_PARAMS = {"query", "kind", "status", "limit", "after"}
STATUSES = {"proposed", "imported_unreviewed", "accepted", "disputed", "rejected"}
WRITE_PATHS = ("/v1/proposals", "/v1/reviews", "/v1/actions/lease", "/v1/actions/transition", "/v1/import")


class Throttled(FrontierError):
    code, http_status = "too_many_attempts", 429


@dataclass
class WebConfig:
    gate_tokens: tuple = field(repr=False, default=())          # sha256 digests of accepted access tokens
    site_dir: Path | None = None
    public_hostname: str = "frontier.morphoswarm.ai"
    cookie_secure: bool = True
    session_ttl: int = 8 * 3600
    max_sessions: int = 500
    public_site: bool = False                                    # True: static shell is open, data stays gated
    search_mode: str = "store_lexical"                           # honest label of what /api/catalog actually runs
    catalog_search: Callable | None = None                       # e.g. SearchIndex(store).search once integrated; same keyword signature as Store.search
    artifact_search: Callable | None = None                      # default: ArtifactIndex(store).search
    attention_build: Callable | None = None                      # default: late import of attention.view.build_view (tests inject a stand-in)
    attention_module: str = "attention.view"                     # module exposing build_view(records, events, annotations, now); renamed by config if the package is
    system_root: Path | None = None                              # checkout whose files /api/system describes (default: this checkout)
    system_runner: Callable | None = None                        # tests only: replaces the two fixed commands' runner
    system_ttl: int = 30
    attention_ttl: int = 5                                       # seconds a built view is reused; bounds repeated polling cost
    attention_max_records: int = 2000                            # public records (all versions) and events the view may be built from; more => 422, never a partial view
    attention_max_events: int = 5000
    routes: dict = field(default_factory=dict)                   # extension point: {"POST /api/engineering/solve": Route(handler)}
    login_failures: int = 10
    login_window: int = 60
    csp: str = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")

    def __post_init__(self):
        # The engineering solver (root's frontier/engineering_api.py) is wired by default; a caller-supplied route of the same name wins (tests).
        self.routes.setdefault("POST /api/engineering/solve", Route(engineering_handler, max_body=1024, max_concurrent=8))
        self.routes.setdefault("POST /api/beliefs/solve", Route(beliefs_handler, max_body=32768, max_concurrent=8))
        for key in self.routes:
            method, _, path = key.partition(" ")
            if method not in ("GET", "POST") or not re.fullmatch(r"/api/[a-z0-9][a-z0-9/_-]{0,80}", path) or path in RESERVED_API:
                raise ValueError("custom routes must be 'GET|POST /api/<name>' and must not shadow a built-in endpoint")

    @staticmethod
    def with_tokens(*tokens: str, **kw) -> "WebConfig":
        good = [t for t in tokens if t]
        if not good or any(len(t) < 16 for t in good):
            raise ValueError("an access token of at least 16 characters is required")
        return WebConfig(gate_tokens=tuple(sha256(t.encode()).digest() for t in good), **kw)


def engineering_handler(req):
    """POST /api/engineering/solve -> frontier.engineering_api.solve_design(data) (late import). The solver owns validation, its isolated child
    process, its 8 s bound and its concurrency cap of 2 (it raises FrontierError for invalid/busy); this adapter adds only the gate, the 1024-byte
    body bound and the typed error mapping. If the module is absent the answer is a clear 503 and nothing is computed or invented."""
    try:
        from frontier.engineering_api import solve_design
    except ModuleNotFoundError as e:
        if e.name != "frontier.engineering_api":
            raise
        err = FrontierError("The engineering solver is not installed on this node")
        err.http_status, err.code = 503, "engineering_unavailable"
        raise err from None
    return 200, solve_design(req["body"])


def _unavailable(code, what):
    err = FrontierError(f"{what} is not installed on this node")
    err.http_status, err.code = 503, code
    return err


def beliefs_handler(req):
    """POST /api/beliefs/solve -> frontier.beliefs_api.solve_scenario(scenario) (the director's adapter; late import). That adapter validates the scenario,
    runs the solver in its own isolated 8 s child with two slots and labels EVERY answer, including errors, `calibrated: false`; its envelope is passed
    through unchanged (see `Handler.handle_any`, which serves an exception's `.body` verbatim). If the module is absent: 503 `beliefs_unavailable` and
    nothing is computed. This adapter never runs the solver in a web thread."""
    try:
        from frontier.beliefs_api import solve_scenario
    except ModuleNotFoundError as e:
        if e.name != "frontier.beliefs_api":
            raise
        raise _unavailable("beliefs_unavailable", "The belief solver") from None
    return 200, solve_scenario(req["body"])


ATTENTION_MODULES = ("attention.view", "frontier_attention.view", "frontier.attention.view", "frontier.attention")


def _late_attention(module):
    """Static late imports from a fixed allow-list (the market package's final name is still being settled); absent -> 503, nothing invented."""
    try:
        if module == "attention.view":
            from attention.view import build_view
        elif module == "frontier_attention.view":
            from frontier_attention.view import build_view
        elif module == "frontier.attention.view":
            from frontier.attention.view import build_view
        elif module == "frontier.attention":
            from frontier.attention import build_view
        else:
            raise ValueError("unsupported attention module")
        return build_view
    except ModuleNotFoundError as e:
        if e.name and module.startswith(e.name):
            raise _unavailable("attention_unavailable", "The attention layer") from None
        raise                                           # a missing transitive dependency is a real failure, not "not installed"
    except ImportError:
        raise _unavailable("attention_unavailable", "The attention layer") from None


class AttentionSource:
    """Builds the deterministic attention view from PUBLIC stored records and events only, reused for `ttl` seconds."""

    def __init__(self, store, cfg):
        self.store, self.cfg, self.lock, self.cached = store, cfg, Lock(), None

    def inputs(self):
        with self.store.connection() as c:
            recs = c.execute("SELECT envelope FROM record_versions WHERE visibility='public' AND kind <> 'Event' ORDER BY created_at, version LIMIT %s",
                             (self.cfg.attention_max_records + 1,)).fetchall()
            evs = c.execute("SELECT e.sequence, v.envelope FROM events e JOIN record_versions v ON v.version = e.event_version "
                            "WHERE v.visibility='public' ORDER BY e.sequence LIMIT %s", (self.cfg.attention_max_events + 1,)).fetchall()
        if len(recs) > self.cfg.attention_max_records or len(evs) > self.cfg.attention_max_events:
            err = FrontierError("The public record set is larger than this endpoint will build a view from; no partial view is produced")
            err.http_status, err.code = 422, "view_too_large"
            raise err
        return [r["envelope"] for r in recs], [{"sequence": e["sequence"], "envelope": e["envelope"]} for e in evs]

    def get(self):
        with self.lock:
            now = time.monotonic()
            if self.cached and now - self.cached[0] < self.cfg.attention_ttl:
                return self.cached[1]
            build = self.cfg.attention_build
            if build is None:
                build = _late_attention(self.cfg.attention_module)
            records, events = self.inputs()
            stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            view = build(records, events, [], stamp)
            out = {"mode": "live", "namespace": self.store.namespace, "generated_at": stamp,
                   "inputs": {"records": len(records), "events": len(events), "annotations": 0, "public_only": True,
                              "note": "Typed unlock edges and bounded-action models live in annotation documents the store cannot hold; none are loaded here, "
                                      "so the view shows what the stored records alone support."},
                   "view": view}
            self.cached = (now, out)
            return out


def default_search(store):
    """What the website uses by default: the search index (lexical + exact discovery, the store's own visibility rules). Works without the optional
    indexes that `python -m frontier.search` creates; they only make it faster."""
    return SearchIndex(store).query, "search_index"


RESERVED_API = {"/api/health", "/api/session", "/api/catalog", "/api/record", "/api/events", "/api/artifacts", "/api/attention", "/api/system"}


@dataclass
class Route:
    """A gated extension endpoint, e.g. the engineering solver. Needs a browser session; POST also needs Origin + CSRF.

    handler(request) receives `{"method", "path", "query": dict, "body": dict | None, "store": Store}` and returns `(status, json_object)`.
    It may raise FrontierError for a typed 4xx; any other exception becomes a generic 500 and is never echoed. The adapter bounds the body
    (`max_body` bytes, refused from the header alone) and the number of simultaneous calls (`max_concurrent`, else 503 + Retry-After).
    """
    handler: Callable
    max_body: int = 1024
    max_concurrent: int = 2

    def __post_init__(self):
        if not 1 <= self.max_body <= 65536 or not 1 <= self.max_concurrent <= 8:
            raise ValueError("route bounds out of range")
        self.slots = BoundedSemaphore(self.max_concurrent)


class Sessions:
    def __init__(self, ttl, cap):
        self.ttl, self.cap, self.d, self.lock = ttl, cap, {}, Lock()

    def create(self):
        now = time.monotonic()
        with self.lock:
            for k in [k for k, v in self.d.items() if v["exp"] <= now]:
                del self.d[k]
            while len(self.d) >= self.cap:
                del self.d[min(self.d, key=lambda k: self.d[k]["exp"])]
            sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            self.d[sid] = {"csrf": csrf, "exp": now + self.ttl}
            return sid, csrf

    def get(self, sid):
        with self.lock:
            s = self.d.get(sid)
            if s and s["exp"] > time.monotonic():
                return s
            self.d.pop(sid, None)
            return None

    def drop(self, sid):
        with self.lock:
            self.d.pop(sid, None)


class FailureLimiter:
    def __init__(self, limit, window):
        self.limit, self.window, self.d, self.lock = limit, window, {}, Lock()

    def blocked(self, key):
        now = time.monotonic()
        with self.lock:
            q = self.d.get(key)
            while q and now - q[0] > self.window:
                q.popleft()
            return bool(q) and len(q) >= self.limit

    def fail(self, key):
        with self.lock:
            if len(self.d) > 4096:
                self.d.clear()
            self.d.setdefault(key, deque()).append(time.monotonic())


LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delphi Frontier sign-in</title><style>body{font:16px system-ui,sans-serif;max-width:26rem;margin:4rem auto;padding:0 1rem}
input,button{font:inherit;padding:.6rem;width:100%;box-sizing:border-box;margin-top:.5rem}.err{color:#a40000}</style></head><body>
<h1>Delphi Frontier</h1><p>Enter the access token to open this node.</p><!--MSG-->
<form method="post" action="/login"><label for="t">Access token</label>
<input id="t" name="token" type="password" autocomplete="current-password" required minlength="16" maxlength="512">
<button type="submit">Sign in</button></form></body></html>"""


def resolve_static(site: Path, raw_path: str) -> Path | None:
    """Map a URL path to a file strictly inside `site`, or None. Pure function so traversal rules are testable without a server."""
    try:
        p = unquote(raw_path, errors="strict")
    except UnicodeDecodeError:
        return None
    if not p.startswith("/") or "\x00" in p or "\\" in p or any(ord(c) < 32 for c in p):
        return None
    segs = p.split("/")[1:]
    if segs and segs[-1] == "":
        segs = segs[:-1] + ["index.html"]
    if not segs or any(s in ("", ".", "..") or s.startswith(".") for s in segs):
        return None
    root = site.resolve()
    target = (root / "/".join(segs)).resolve()
    if not target.is_relative_to(root) or SENSITIVE_NAME.search(target.name) or mime_for(root, target) is None:
        return None
    ext = target.suffix.lower()
    limit = MAX_VIDEO_BYTES if ext in STREAMED else MAX_ARTIFACT_BYTES if ext in ARTIFACT_MIME else MAX_STATIC_BYTES
    try:
        if not target.is_file() or target.stat().st_size > limit:
            return None
    except OSError:
        return None
    return target


def mime_for(root: Path, target: Path) -> str | None:
    ext = target.suffix.lower()
    if ext in MIME:
        return MIME[ext]
    if ext in ARTIFACT_MIME and target.is_relative_to(root / "artifacts"):
        return ARTIFACT_MIME[ext]
    return None


def make_handler(app: Application, store: Store, cfg: WebConfig, server_port: Callable[[], int]):
    sessions = Sessions(cfg.session_ttl, cfg.max_sessions)
    limiter = FailureLimiter(cfg.login_failures, cfg.login_window)
    cookie_name = ("__Host-" if cfg.cookie_secure else "") + "frontier_session"
    attention = AttentionSource(store, cfg)
    system = SystemStatus(store, **({"root": cfg.system_root} if cfg.system_root else {}), ttl=cfg.system_ttl, runner=cfg.system_runner)

    class Handler(BaseHTTPRequestHandler):
        server_version = "frontier"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        # ---------------------------------------------------------------- logging (method, path, status only)
        def log_message(self, *_):
            pass

        def log_request(self, code="-", size="-"):
            path = re.sub(r"[^\x21-\x7e]", "?", urlsplit(self.path).path)[:200]
            log.info("%s %s %s", self.command, path, code)

        # ---------------------------------------------------------------- responses
        def _headers(self, extra):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            for k, v in extra:
                self.send_header(k, v)

        def send(self, status, body=b"", ctype="application/json", extra=()):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if ctype == "application/json" else "no-cache")
            if ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy", cfg.csp)
            self._headers(extra)
            self.end_headers()
            if self.command != "HEAD" and status not in (204, 304):
                self.wfile.write(body)

        def json(self, status, obj, extra=()):
            self.send(status, canonical(obj).encode(), extra=extra)

        def error(self, status, code, message, extra=()):
            self.json(status, {"error": code, "message": message}, extra)

        # ---------------------------------------------------------------- request checks
        def allowed_hosts(self):
            p = server_port()
            return {cfg.public_hostname.lower(), f"127.0.0.1:{p}", f"localhost:{p}"}

        def allowed_origins(self):
            p = server_port()
            return {f"https://{cfg.public_hostname.lower()}", f"http://127.0.0.1:{p}", f"http://localhost:{p}"}

        def client_key(self):
            fwd = self.headers.get("X-Forwarded-For", "")
            return (fwd.split(",")[-1].strip() or self.client_address[0])[:64]       # nginx OVERWRITES the header with $remote_addr

        def session(self):
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == cookie_name and v:
                    s = sessions.get(v)
                    if s:
                        return v, s
            return None, None

        def bearer(self):
            auth = self.headers.get("Authorization", "")
            return auth[7:] if auth.startswith("Bearer ") and len(auth) > 7 else None

        def read_body(self, limit):
            if self.headers.get("Transfer-Encoding"):
                raise FrontierError("Transfer encoding unsupported")
            raw = self.headers.get("Content-Length")
            if raw is None:
                err = FrontierError("Content-Length required")
                err.http_status, err.code = 411, "length_required"
                raise err
            n = int(raw)
            if not 0 < n <= limit:
                err = FrontierError(f"Body length must be 1..{limit} bytes")
                err.http_status, err.code = (413 if n > limit else 400), ("payload_too_large" if n > limit else "invalid_request")
                raise err
            return self.rfile.read(n)

        def json_body(self, limit):
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise FrontierError("JSON content type required")
            return json.loads(self.read_body(limit))

        # ---------------------------------------------------------------- dispatch
        def handle_any(self):
            try:
                if len(self.path) > MAX_PATH:
                    return self.error(414, "uri_too_long", "Request target too long")
                parts = urlsplit(self.path)
                path = parts.path
                if (self.headers.get("Host") or "").lower() not in self.allowed_hosts():
                    return self.error(400, "invalid_host", "Unknown Host")
                origin = self.headers.get("Origin")
                if origin is not None and origin not in self.allowed_origins():
                    return self.error(403, "forbidden_origin", "Cross-origin requests are not accepted")
                m = self.command
                if path == "/api/health":
                    return self.health() if m in ("GET", "HEAD") else self.method_not_allowed("GET, HEAD")
                if path == "/api/session":
                    return self.api_session(m, origin)
                if path == "/login":
                    return self.login(m, origin)
                if path.startswith("/v1/"):
                    return self.v1(m, path)
                allowed = [k.split(" ")[0] for k in cfg.routes if k.endswith(" " + path)]
                if allowed:
                    if m not in allowed:
                        return self.method_not_allowed(", ".join(allowed))
                    return self.custom(cfg.routes[f"{m} {path}"], path, parts.query, origin)
                if m not in ("GET", "HEAD"):
                    return self.method_not_allowed("GET, HEAD")
                sid, sess = self.session()
                if not sess and not (cfg.public_site and not path.startswith("/api/")):
                    if path.startswith("/api/") or "text/html" not in (self.headers.get("Accept") or ""):
                        return self.error(401, "unauthorized", "Sign in required")
                    return self.send(302, b"", "text/plain", extra=[("Location", "/login")])
                if path.startswith("/api/"):
                    return self.api_read(path, parts.query)
                return self.static(path)
            except FrontierError as e:
                extra = [("Retry-After", str(cfg.login_window))] if e.http_status == 429 and e.code == "too_many_attempts" else []
                body = getattr(e, "body", None)                       # root's solver adapters attach a fully labelled envelope (e.g. calibrated: false)
                if isinstance(body, dict):
                    self.json(e.http_status, body, extra)
                else:
                    self.error(e.http_status, e.code, str(e), extra)
            except (ValueError, TypeError, KeyError, RecursionError):
                self.error(400, "invalid_request", "Invalid bounded request")      # pydantic errors can echo input; never forward them
            except Exception:       # noqa: BLE001
                self.error(500, "storage_error", "Transaction failed")

        do_GET = do_HEAD = do_POST = do_DELETE = do_PUT = do_PATCH = do_OPTIONS = handle_any

        def method_not_allowed(self, allow):
            self.error(405, "method_not_allowed", "Method not allowed", [("Allow", allow)])

        # ---------------------------------------------------------------- endpoints
        def health(self):
            try:
                with store.connection() as c:
                    c.execute("SELECT 1")
                self.json(200, {"status": "ok", "service": "delphi-frontier", "mode": "live"})
            except Exception:       # noqa: BLE001
                self.json(503, {"status": "unavailable", "service": "delphi-frontier"})

        def token_ok(self, supplied: str) -> bool:
            digest, ok = sha256(supplied.encode()).digest(), False
            for t in cfg.gate_tokens:
                ok |= hmac.compare_digest(digest, t)
            return ok

        def new_session_headers(self):
            old, _ = self.session()
            if old:
                sessions.drop(old)
            sid, csrf = sessions.create()
            attrs = f"{cookie_name}={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age={cfg.session_ttl}" + ("; Secure" if cfg.cookie_secure else "")
            return csrf, [("Set-Cookie", attrs)]

        def attempt(self, supplied) -> bool:
            key = self.client_key()
            if limiter.blocked(key):
                raise Throttled("Too many failed attempts; wait and retry")
            ok = isinstance(supplied, str) and 0 < len(supplied) <= 512 and self.token_ok(supplied)
            if not ok:
                limiter.fail(key)
            return ok

        def api_session(self, m, origin):
            sid, sess = self.session()
            if m == "GET":
                if not sess:
                    return self.error(401, "unauthorized", "No session")
                return self.json(200, {"authenticated": True, "csrf": sess["csrf"]})
            if m == "POST":
                data = self.json_body(2048)
                if not isinstance(data, dict) or set(data) != {"token"}:
                    raise FrontierError("Body must be {\"token\": string}")
                if not self.attempt(data["token"]):
                    return self.error(401, "unauthorized", "Invalid access token")
                csrf, extra = self.new_session_headers()
                return self.json(200, {"authenticated": True, "csrf": csrf, "expires_in": cfg.session_ttl}, extra)
            if m == "DELETE":
                if not sess:
                    return self.error(401, "unauthorized", "No session")
                if origin is None:
                    return self.error(403, "forbidden_origin", "Origin required")
                if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), sess["csrf"]):
                    return self.error(403, "csrf", "CSRF token missing or wrong")
                sessions.drop(sid)
                return self.send(204, b"", extra=[("Set-Cookie", f"{cookie_name}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" + ("; Secure" if cfg.cookie_secure else ""))])
            return self.method_not_allowed("GET, POST, DELETE")

        def login(self, m, origin):
            if m in ("GET", "HEAD"):
                return self.send(200, LOGIN_HTML.replace("<!--MSG-->", "").encode(), "text/html; charset=utf-8")
            if m != "POST":
                return self.method_not_allowed("GET, HEAD, POST")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/x-www-form-urlencoded":
                raise FrontierError("Form content type required")
            form = parse_qs(self.read_body(2048).decode("utf-8", "strict"), keep_blank_values=True, max_num_fields=3)
            if set(form) != {"token"} or len(form["token"]) != 1:
                raise FrontierError("Invalid form")
            if not self.attempt(form["token"][0]):
                return self.send(401, LOGIN_HTML.replace("<!--MSG-->", '<p class="err">Invalid access token.</p>').encode(), "text/html; charset=utf-8")
            _, extra = self.new_session_headers()
            return self.send(303, b"", "text/plain", extra=extra + [("Location", "/")])

        def api_read(self, path, query):
            q = parse_qs(query, keep_blank_values=True, max_num_fields=12)
            if any(len(v) != 1 for v in q.values()):
                raise FrontierError("Repeated parameters are not accepted")
            q = {k: v[0] for k, v in q.items()}
            if path == "/api/catalog":
                if set(q) - CATALOG_PARAMS:
                    raise FrontierError("Unknown parameter")
                limit = int(q.get("limit", "20"))
                if not 1 <= limit <= 50:
                    raise FrontierError("limit must be 1..50")
                kind, status = q.get("kind") or None, q.get("status") or None
                if (kind and kind not in KINDS) or (status and status not in STATUSES):
                    raise FrontierError("Unknown kind or status")
                found = (cfg.catalog_search or store.search)(query=q.get("query", ""), kind=kind, status=status, limit=limit, after=q.get("after", ""))
                rows = []
                for r in found["results"]:
                    got = store.get(r["ref"])
                    row = {"record": got["record"], "local_status": got["local_review"]["status"], "policy_version": got["local_review"]["policy_version"],
                           "is_head": got["is_head"], "action": got["action"], "why_matched": r["why_matched"]}
                    match = {k: r[k] for k in ("score", "matched_fields", "snippet", "snippet_withheld", "curation", "disputes", "evidence_references", "references_complete") if k in r}
                    if match:
                        row["match"] = match                      # the search index's own explanation, kept apart from the record
                    rows.append(row)
                return self.json(200, {"mode": "live", "namespace": store.namespace, "search_mode": cfg.search_mode, "search_kind": found["search_kind"],
                                       "results": rows, "next_cursor": found["next_cursor"]})
            if path == "/api/system":
                if q:
                    raise FrontierError("This endpoint takes no parameters")
                return self.json(200, system.snapshot())
            if path == "/api/attention":
                if q:
                    raise FrontierError("This endpoint takes no parameters")
                return self.json(200, attention.get())
            if path == "/api/artifacts":
                if set(q) - {"q", "query", "role", "evidence_kind", "limit", "after"} or ("q" in q and "query" in q):
                    raise FrontierError("Unknown or conflicting parameter")
                search = cfg.artifact_search or ArtifactIndex(store).search
                return self.json(200, search(q.get("q", q.get("query", "")), role=q.get("role") or None, evidence_kind=q.get("evidence_kind") or None,
                                             limit=int(q.get("limit", "20")), cursor=q.get("after", ""), token=None))
            if path == "/api/record":
                if set(q) != {"namespace", "kind", "id", "version"}:
                    raise FrontierError("A pinned Ref (namespace, kind, id, version) is required")
                got = store.get(Ref.model_validate(q).model_dump())
                return self.json(200, {"mode": "live", "record": got["record"], "local_status": got["local_review"]["status"],
                                       "policy_version": got["local_review"]["policy_version"], "is_head": got["is_head"], "action": got["action"]})
            if path == "/api/events":
                if set(q) - {"after", "limit"}:
                    raise FrontierError("Unknown parameter")
                got = store.events(after=int(q.get("after", "0")), limit=int(q.get("limit", "20")))
                return self.json(200, {"mode": "live", "namespace": store.namespace, **got})
            return self.error(404, "not_found", "Unknown endpoint")

        def v1(self, m, path):
            if m != "POST":
                return self.method_not_allowed("POST")
            token = self.bearer()
            if path in WRITE_PATHS and not token:
                return self.error(401, "unauthorized", "Operator bearer credential required; a browser session never authorises a write")
            if path.startswith("/v1/read/") and not token and not self.session()[1]:
                return self.error(401, "unauthorized", "Sign in or supply a bearer credential")
            data = self.json_body(MAX_BUNDLE_BYTES)
            self.json(200, app.dispatch(path, data, token, self.headers.get("Idempotency-Key")))

        def custom(self, route, path, query, origin):
            sid, sess = self.session()
            if not sess:
                return self.error(401, "unauthorized", "Sign in required")
            body = None
            if self.command == "POST":
                if origin is None:
                    return self.error(403, "forbidden_origin", "Origin required")
                if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), sess["csrf"]):
                    return self.error(403, "csrf", "CSRF token missing or wrong")
                body = self.json_body(route.max_body)
                if not isinstance(body, dict):
                    raise FrontierError("JSON object required")
            q = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True, max_num_fields=12).items()}
            if not route.slots.acquire(blocking=False):
                return self.error(503, "busy", "Too many simultaneous requests", [("Retry-After", "2")])
            try:
                status, obj = route.handler({"method": self.command, "path": path, "query": q, "body": body, "store": store})
            finally:
                route.slots.release()
            self.json(status, obj)

        def stream(self, target):
            size, st = target.stat().st_size, target.stat()
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range")
            if rng:
                m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
                if not m or not (m.group(1) or m.group(2)):
                    return self.error(416, "range_not_satisfiable", "Unsupported Range", [("Content-Range", f"bytes */{size}")])
                if m.group(1):
                    start = int(m.group(1))
                    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                else:
                    start, end = max(size - int(m.group(2)), 0), size - 1
                if start > end or start >= size:
                    return self.error(416, "range_not_satisfiable", "Range outside the file", [("Content-Range", f"bytes */{size}")])
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", ARTIFACT_MIME[target.suffix.lower()])
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("ETag", f'"{st.st_size:x}-{st.st_mtime_ns:x}"')
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self._headers([])
            self.end_headers()
            if self.command == "HEAD":
                return
            with target.open("rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def static(self, path):
            if cfg.site_dir is None:
                return self.error(404, "not_found", "No site configured")
            target = resolve_static(cfg.site_dir, path)
            if target is None:
                return self.error(404, "not_found", "Not found")
            if target.suffix.lower() in STREAMED:
                return self.stream(target)
            body = target.read_bytes()
            extra = [("ETag", '"' + sha256(body).hexdigest()[:16] + '"')]
            if target.suffix.lower() in ARTIFACT_DOWNLOAD:
                extra.append(("Content-Disposition", "attachment"))
            self.send(200, body, mime_for(cfg.site_dir.resolve(), target), extra=extra)

    return Handler


class WebServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, handler):
        if address[0] != "127.0.0.1":
            raise ValueError("The website adapter binds loopback only; nginx faces the network")
        self.slots = BoundedSemaphore(16)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def make_web_server(store: Store, cfg: WebConfig, port: int = 0) -> WebServer:
    if not cfg.gate_tokens:
        raise ValueError("refusing to build an ungated website adapter")
    holder = {}
    server = WebServer(("127.0.0.1", port), make_handler(Application(store), store, cfg, lambda: holder["port"]))
    holder["port"] = server.server_port
    return server


def main(argv=None):
    p = argparse.ArgumentParser(description="Frontier website/API adapter (loopback; nginx in front)")
    p.add_argument("--namespace", required=True)
    p.add_argument("--schema", default="public")
    p.add_argument("--port", type=int, default=8971)
    p.add_argument("--site", type=Path, default=Path("site"))
    p.add_argument("--hostname", default="frontier.morphoswarm.ai")
    p.add_argument("--public-site", action="store_true", help="serve the static shell without sign-in; data endpoints stay gated")
    p.add_argument("--attention-module", default="attention.view", choices=ATTENTION_MODULES, help="module providing build_view (default attention.view); 503 if absent")
    p.add_argument("--legacy-catalog", action="store_true", help="use the old Store.search instead of the search index (debugging only)")
    p.add_argument("--insecure-cookies", action="store_true", help="local development over plain HTTP only: drop the Secure attribute")
    a = p.parse_args(argv)
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(message)s")
    # The access token comes from the service's EnvironmentFile; its value is never printed or logged.
    tokens = [os.environ.get("FRONTIER_ACCESS_TOKEN") or os.environ.get("MORPHOSWARM_STUDIO_TOKEN")]
    try:
        cfg = WebConfig.with_tokens(*tokens, site_dir=a.site, public_hostname=a.hostname, cookie_secure=not a.insecure_cookies, public_site=a.public_site, attention_module=a.attention_module)
    except ValueError:
        print("frontier.web: set FRONTIER_ACCESS_TOKEN (or MORPHOSWARM_STUDIO_TOKEN) to a token of at least 16 characters", file=sys.stderr)
        return 2
    store = Store(os.environ["FRONTIER_DSN"], a.namespace, a.schema)
    if not a.legacy_catalog:
        cfg.catalog_search, cfg.search_mode = default_search(store)
    server = make_web_server(store, cfg, a.port)
    log.info("listening 127.0.0.1:%d namespace=%s schema=%s gated=%s", server.server_port, a.namespace, a.schema, True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
