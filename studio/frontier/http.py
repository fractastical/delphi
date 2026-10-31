"""Loopback-only HTTP adapter, intentionally without job/tool execution."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from socketserver import ThreadingMixIn
from threading import BoundedSemaphore

from .models import MAX_BUNDLE_BYTES, canonical
from .search import SearchIndex
from .artifacts import ArtifactIndex
from .design_review import project_design_context, submit_design_review
from .store import FrontierError, Store


class Application:
    def __init__(self, store: Store):
        self.store = store
        self.search = SearchIndex(store)  # reads only; the indexes are created by `python -m frontier.search`, search works without them

    def dispatch(self, path, data, token=None, key=None):
        if not isinstance(data, dict):
            raise FrontierError("JSON object required")
        read = {"/v1/read/get": self.store.get, "/v1/read/search": self.search.query,
                "/v1/read/artifacts": ArtifactIndex(self.store).search,
                "/v1/read/neighborhood": self.store.neighborhood, "/v1/read/events": self.store.events,
                "/v1/read/export": self.store.export_bundle}
        write = {"/v1/proposals": self.store.submit, "/v1/reviews": self.store.review,
                 "/v1/actions/lease": self.store.lease, "/v1/actions/transition": self.store.transition,
                 "/v1/import": self.store.import_bundle}
        # Authentication/key fields come solely from transport, never body overrides.
        if "token" in data or "key" in data:
            raise FrontierError("Authentication and idempotency belong in headers")
        if path in read:
            return read[path](**data, token=token)
        if path == "/v1/read/design-context":
            return project_design_context(self.store, data.get("target"), token=token,
                                          limit=data.get("limit", 20), cursor=data.get("cursor"))
        if path == "/v1/design/reviews":
            if set(data) != {"draft"}:
                raise FrontierError("A design review request contains only the Annotation draft")
            return submit_design_review(self.store, token, key, data["draft"])
        if path in write:
            return write[path](**data, token=token, key=key)
        raise FrontierError("Unknown endpoint")


class BoundedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, handler):
        if address[0] != "127.0.0.1":
            raise ValueError("This development adapter binds loopback only")
        self.slots = BoundedSemaphore(8)
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


def make_server(store, port=0):
    app = Application(store)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass  # No tokens, request data, or credentials in default access logs.

        def respond(self, status, payload):
            body = canonical(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                host = self.headers.get("Host", "")
                if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                    raise FrontierError("Invalid loopback Host")
                if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                    raise FrontierError("Cross-origin requests disabled")
                if self.headers.get("Transfer-Encoding"):
                    raise FrontierError("Transfer encoding unsupported")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BUNDLE_BYTES:
                    raise FrontierError("Body length must be 1..2000000 bytes")
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise FrontierError("JSON content type required")
                data = json.loads(self.rfile.read(length))
                auth = self.headers.get("Authorization", "")
                token = auth[7:] if auth.startswith("Bearer ") else None
                result = app.dispatch(self.path, data, token, self.headers.get("Idempotency-Key"))
                self.respond(200, result)
            except FrontierError as e:
                self.respond(e.http_status, {"error": e.code, "message": str(e)})
            except (ValueError, TypeError, KeyError, RecursionError):
                # Pydantic exceptions can include submitted values; never echo those.
                self.respond(400, {"error": "invalid_request", "message": "Invalid bounded JSON request"})
            except Exception:
                self.respond(500, {"error": "storage_error", "message": "Transaction failed"})

    return BoundedHTTPServer(("127.0.0.1", port), Handler)
