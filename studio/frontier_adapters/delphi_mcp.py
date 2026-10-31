"""Read-only client for the keyless Delphi MCP with an explicit request budget and a receipt per request.

Limits are parameters, not hopes:
  * `min_interval` seconds between HTTP requests (default 1.0)
  * `max_requests` hard cap on HTTP requests for the whole client lifetime
  * `max_wall_s` hard cap on wall-clock time
  * HTTP 429/503: honour `Retry-After` (seconds or HTTP-date), else exponential backoff capped at 60 s;
    `persistent_429` consecutive refusals raise RetrievalStopped. 401/403 raise immediately.
    Nothing here rotates identity, shortens sessions or otherwise routes around a refusal.
Every request appends a receipt {n, utc, tool, args_sha256, http, bytes, response_sha256, retry_after_s}.
"""
from __future__ import annotations

import email.utils
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .common import iso_utc, sha_bytes, sha_obj

URL = "https://delphisci-mcp.fly.dev/mcp"
CLAIM_PREFIX = "https://w3id.org/delphi/resource/claim/"


class RetrievalStopped(RuntimeError):
    """The client stopped on a refusal or a budget. It does not try to continue."""


class NonJson(ValueError):
    pass


def rows_of(r) -> list[dict]:
    if isinstance(r, list):
        return r
    if isinstance(r, dict) and all(k.isdigit() for k in r):
        return [r[k] for k in sorted(r, key=int)]
    raise NonJson(f"unrecognised SPARQL result shape: {type(r).__name__} {str(r)[:100]!r}")


def json_from_text(text: str):
    """Tool results are JSON, or (delphi_overview) a Markdown preface followed by the JSON object."""
    s = text.lstrip()
    if s[:1] in "[{":
        return json.loads(s)
    i = text.find("\n{\n")
    if i < 0:
        raise NonJson(f"response is not JSON and has no JSON object after a preface: {text[:120]!r}")
    return json.loads(text[i + 1:])


def _retry_after(h) -> float | None:
    v = h.get("Retry-After") if h else None
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        try:
            return max(0.0, (email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds())
        except Exception:
            return None


class Delphi:
    def __init__(self, url: str = URL, *, min_interval: float = 1.0, max_requests: int = 150,
                 max_wall_s: float = 3600, persistent_429: int = 3, sleep=time.sleep, clock=time.monotonic):
        self.url, self.sid, self.n = url, None, 0
        self.min_interval, self.max_requests, self.max_wall_s, self.persistent_429 = min_interval, max_requests, max_wall_s, persistent_429
        self._sleep, self._clock = sleep, clock
        self._t0, self._last = clock(), None
        self.requests = 0
        self.receipts: list[dict] = []
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "frontier-adapters", "version": "0.2"}}, log=False)
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, log=False)

    def _budget(self):
        if self.requests >= self.max_requests:
            raise RetrievalStopped(f"request budget exhausted ({self.max_requests})")
        if self._clock() - self._t0 > self.max_wall_s:
            raise RetrievalStopped(f"wall-clock budget exhausted ({self.max_wall_s}s)")

    def _post(self, body, *, log=True, label=None, args_sha=None):
        refused = 0
        while True:
            self._budget()
            if self._last is not None:
                wait = self.min_interval - (self._clock() - self._last)
                if wait > 0:
                    self._sleep(wait)
            h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            if self.sid:
                h["Mcp-Session-Id"] = self.sid
            self.requests += 1
            self._last = self._clock()
            try:
                with urllib.request.urlopen(urllib.request.Request(self.url, json.dumps(body).encode(), h), timeout=120) as r:
                    self.sid = r.headers.get("Mcp-Session-Id") or self.sid
                    raw = r.read()
                status, ra = r.status, None
                break
            except urllib.error.HTTPError as e:
                ra = _retry_after(e.headers)
                if e.code in (401, 403):
                    raise RetrievalStopped(f"access denied (HTTP {e.code}); not retrying") from e
                if e.code in (429, 503):
                    refused += 1
                    self._receipt(label, args_sha, e.code, 0, None, ra, log)
                    if refused >= self.persistent_429:
                        raise RetrievalStopped(f"persistent HTTP {e.code} ({refused} consecutive); stopping, not bypassing") from e
                    self._sleep(ra if ra is not None else min(60.0, 5.0 * 2 ** (refused - 1)))
                    continue
                raise
        txt = raw.decode()
        payload = None
        for line in txt.split("\n"):
            if line.startswith("data:"):
                payload = json.loads(line[5:])
                break
        if payload is None and txt.strip():
            payload = json.loads(txt)
        self._receipt(label, args_sha, status, len(raw), sha_bytes(raw), None, log)
        return payload

    def _receipt(self, label, args_sha, http, nbytes, rsha, ra, log):
        if log and label is not None:
            self.receipts.append({"n": len(self.receipts) + 1, "utc": iso_utc(), "tool": label, "args_sha256": args_sha,
                                  "http": http, "bytes": nbytes, "response_sha256": rsha, "retry_after_s": ra})

    def _rpc(self, method, params, *, log=True, label=None, args_sha=None):
        self.n += 1
        return self._post({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}, log=log, label=label, args_sha=args_sha)

    def text(self, name: str, args: dict) -> tuple[str, int]:
        """Raw tool text and the number of the receipt it produced."""
        r = self._rpc("tools/call", {"name": name, "arguments": args}, label=name, args_sha=sha_obj(args))
        if "error" in r:
            raise RuntimeError(r["error"])
        text = "".join(c.get("text", "") for c in r["result"].get("content", []))
        if r["result"].get("isError"):
            raise RuntimeError(text[:300])
        return text, len(self.receipts)

    def tool(self, name: str, args: dict):
        return json_from_text(self.text(name, args)[0])

    def sparql(self, query: str, source: str = "local") -> list[dict]:
        """SPARQL SELECT rows as a list, whatever shape the service uses. Observed 2026-10-31: first a JSON list, then (same
        day) an object keyed "0","1",... with `{}` for no rows. Anything else raises instead of reading as empty."""
        r = self.tool("delphi_sparql", {"query": query, "source": source})
        return rows_of(r)
