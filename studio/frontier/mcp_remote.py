"""Remote Streamable HTTP front for the Frontier MCP server (official SDK 1.27 transport, stateless, JSON responses).

Why a second module: cloud agents cannot reach a local PostgreSQL socket or a stdio process, so they connect over HTTPS (nginx -> 127.0.0.1:8972, exact path /mcp).

Authentication is PER REQUEST and PER PRINCIPAL: writes carry `Authorization: Bearer <operator credential>`; reads may be public. The SDK's bearer backend calls
`StoreTokenVerifier`, which asks the store's public `Store.principal(token)`; the verified token travels in the SDK's per-request auth context and the tools hand
THAT token to the same Store methods the stdio server uses. There is no server-wide contributor token. Stateless mode prevents session-bound identity: the tests
interleave distinct principals, including a supplied session header, and require each request to use its own bearer; no session id is issued.
The token is accepted ONLY in the Authorization header: any query string is refused, and the access log is replaced by one that never records a query or a header.

This module adds no tools. Which tools exist, what they do and what is deliberately absent (review, import, provision, execution) is decided in `frontier.mcp.make_mcp`.
"""
import logging
import time
from collections import deque

import anyio
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.requests import HTTPConnection

from .store import Store, Unauthorized

log = logging.getLogger("frontier.mcp.remote")
MAX_BODY = 131072            # the store's own record cap is 65,536 bytes; JSON-RPC framing and arguments fit in twice that
MAX_CONCURRENT = 8
REQUEST_TIMEOUT_S = 60
PATH = "/mcp"


class VerificationUnavailable(Exception):
    """Fixed-text transport failure: underlying storage details never reach logs."""


class StoreTokenVerifier(TokenVerifier):
    """Verifies a bearer with the store's own authentication. The AccessToken carries the raw token only inside the per-request context; it is never logged."""

    def __init__(self, store: Store):
        self.store = store

    async def verify_token(self, token: str) -> AccessToken | None:
        if not 24 <= len(token) <= 512 or not token.isascii() or not token.isprintable() or " " in token:
            return None
        try:
            p = await anyio.to_thread.run_sync(self.store.principal, token)
        except Unauthorized:
            return None
        except Exception:
            raise VerificationUnavailable("Credential verification unavailable") from None
        return AccessToken(token=token, client_id=p["actor"], scopes=[f"role:{r}" for r in sorted(p["roles"])] + [f"operator:{p['operator']}"], expires_at=None)


class Guard:
    """ASGI wrapper around the SDK app: exact path, POST only, no query string, bounded body and concurrency, request timeout, throttle on repeated 401s, and a
    log line that carries only `METHOD PATH STATUS`. Host and Origin validation is the SDK's (TransportSecuritySettings), configured in make_mcp."""

    def __init__(self, app, *, max_body=MAX_BODY, max_concurrent=MAX_CONCURRENT, timeout=REQUEST_TIMEOUT_S, fail_limit=10, fail_window=60, public_verifier=None):
        """public_verifier: when given (the `--public-read` mode) the SDK's bearer middleware is NOT in front of the route; THIS guard authenticates instead, with the
        SDK's own BearerAuthBackend and auth context. No Authorization header = anonymous (tools that need a principal answer `unauthorized`); a header that fails
        verification is a 401 and is NEVER downgraded to anonymous."""
        self.app, self.max_body, self.max_concurrent, self.timeout = app, max_body, max_concurrent, timeout
        self.public_backend = BearerAuthBackend(public_verifier) if public_verifier else None
        self.active, self.fail_limit, self.fail_window, self.fails = 0, fail_limit, fail_window, {}

    @staticmethod
    async def _reply(send, status, code, message, extra=()):
        import json
        body = json.dumps({"error": code, "error_description": message}).encode()
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                                                                                  (b"cache-control", b"no-store"), *extra]})
        await send({"type": "http.response.body", "body": body})

    def _blocked(self, key):
        now, q = time.monotonic(), self.fails.get(key)
        while q and now - q[0] > self.fail_window:
            q.popleft()
        return bool(q) and len(q) >= self.fail_limit

    def _fail(self, key):
        if len(self.fails) > 4096:
            self.fails.clear()
        self.fails.setdefault(key, deque()).append(time.monotonic())

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            return
        method, path = scope["method"], scope["path"]
        headers = [(k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in scope["headers"]]
        h = dict(headers)
        fwd = h.get("x-forwarded-for", "")
        client = (fwd.split(",")[-1].strip() or (scope.get("client") or ("?",))[0])[:64]       # nginx OVERWRITES this header with $remote_addr
        status = {"code": 0}

        async def tracking_send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)
        try:
            if path != PATH:
                return await self._reply(tracking_send, 404, "not_found", "Only /mcp is served here")
            if method != "POST":
                return await self._reply(tracking_send, 405, "method_not_allowed", "POST only", [(b"allow", b"POST")])
            if scope.get("query_string"):
                return await self._reply(tracking_send, 400, "invalid_request", "No query string is accepted; credentials go in the Authorization header only")
            if self._blocked(client):
                return await self._reply(tracking_send, 429, "too_many_attempts", "Too many failed authentications; wait and retry", [(b"retry-after", str(self.fail_window).encode())])
            if "transfer-encoding" in h:
                return await self._reply(tracking_send, 400, "invalid_request", "Transfer encoding unsupported; send Content-Length")
            cl = h.get("content-length")
            if cl is None:
                return await self._reply(tracking_send, 411, "length_required", "Content-Length required")
            if not cl.isascii() or not cl.isdecimal() or len(cl) > 12 or int(cl) == 0:
                return await self._reply(tracking_send, 400, "invalid_request", "Invalid Content-Length")
            if int(cl) > self.max_body:
                return await self._reply(tracking_send, 413, "payload_too_large", f"Body larger than {self.max_body} bytes")
            if self.active >= self.max_concurrent:
                return await self._reply(tracking_send, 503, "busy", "Too many simultaneous requests", [(b"retry-after", b"2")])
            if any(sum(k == name for k, _v in headers) > 1 for name in ("authorization", "content-length")):
                return await self._reply(tracking_send, 400, "invalid_request", "Repeated authentication or length header")
            # Reserve before any await, including authentication: simultaneous slow
            # verifier calls must count against the same request budget as tools.
            self.active += 1
            ctx = auth_context_var.set(None)
            try:
                with anyio.fail_after(self.timeout):
                    body = bytearray()
                    while True:
                        part = await receive()
                        if part["type"] != "http.request":
                            return await self._reply(tracking_send, 400, "invalid_request", "Incomplete request body")
                        chunk = part.get("body", b"")
                        if len(body) + len(chunk) > self.max_body:
                            return await self._reply(tracking_send, 413, "payload_too_large", "Body exceeds request bound")
                        body.extend(chunk)
                        if not part.get("more_body", False):
                            break
                    if len(body) != int(cl):
                        return await self._reply(tracking_send, 400, "invalid_request", "Body length does not match Content-Length")
                    consumed = False

                    async def bounded_receive():
                        nonlocal consumed
                        if not consumed:
                            consumed = True
                            return {"type": "http.request", "body": bytes(body), "more_body": False}
                        return await receive()

                    if self.public_backend is not None and "authorization" in h:
                        res = await self.public_backend.authenticate(HTTPConnection(scope))
                        if res is None:
                            self._fail(client)
                            return await self._reply(tracking_send, 401, "invalid_token", "Authentication required", [(b"www-authenticate", b'Bearer error="invalid_token"')])
                        auth_context_var.set(res[1])
                    await self.app(scope, bounded_receive, tracking_send)
            except VerificationUnavailable:
                if not status["code"]:
                    await self._reply(tracking_send, 503, "unavailable", "Credential verification unavailable")
            except TimeoutError:
                if not status["code"]:
                    await self._reply(tracking_send, 504, "timeout", "Request exceeded its time limit")
            finally:
                self.active -= 1
                auth_context_var.reset(ctx)
            if status["code"] == 401 and self.public_backend is None:
                self._fail(client)
        finally:
            log.info("%s %s %s", method, PATH if path == PATH else "<unmatched>", status["code"])


def serve(store: Store, *, host: str = "127.0.0.1", port: int = 8972, public_host: str = "frontier.morphoswarm.ai", allow_write: bool = False, public_read: bool = False):
    import uvicorn

    from .mcp import make_mcp
    if host != "127.0.0.1":
        raise ValueError("the remote MCP front binds loopback only; nginx terminates TLS in front of it")
    server = make_mcp(store, allow_write=allow_write, remote=True, public_host=public_host, port=port, public_read=public_read)
    app = Guard(server.streamable_http_app(), public_verifier=StoreTokenVerifier(store) if public_read else None)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False, server_header=False, date_header=True, timeout_keep_alive=5,
                limit_concurrency=MAX_CONCURRENT * 2, proxy_headers=False)
