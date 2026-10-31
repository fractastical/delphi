"""Minimal client for the Nebius Scientific AI MCP server (Streamable HTTP).

Reads the key from NEBIUS_SCIENTIFIC_AI_API_KEY (falls back to agent/.env).
Usage as a CLI:
    python3 nebius/nebius_mcp.py tools                 # list tool names
    python3 nebius/nebius_mcp.py schema <tool>...      # print tool schemas
    python3 nebius/nebius_mcp.py call <tool> '<json>'  # call a tool, print result
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = os.environ.get("NEBIUS_SCIENTIFIC_AI_MCP_URL", "https://89.169.99.188/mcp")


def _key():
    k = os.environ.get("NEBIUS_SCIENTIFIC_AI_API_KEY")
    if k:
        return k
    env = Path(__file__).resolve().parent.parent / "agent" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("NEBIUS_SCIENTIFIC_AI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("NEBIUS_SCIENTIFIC_AI_API_KEY is not set")


class Client:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.session = None
        self._id = 0
        self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "delphisci", "version": "0.1"},
        })
        self._rpc("notifications/initialized", notify=True)

    def _rpc(self, method, params=None, notify=False, timeout=300):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            self._id += 1
            body["id"] = self._id
        headers = dict(self.headers)
        if self.session:
            headers["mcp-session-id"] = self.session
        req = urllib.request.Request(URL, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            self.session = r.headers.get("mcp-session-id") or self.session
            text = r.read().decode()
        if notify or not text.strip():
            return None
        data = [l[5:].strip() for l in text.splitlines() if l.startswith("data:")]
        msg = json.loads(data[-1] if data else text)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg["result"]

    def tools(self):
        return self._rpc("tools/list")["tools"]

    def call(self, name, args):
        """Call a tool and return its structured result (parsed JSON when possible)."""
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        if res.get("structuredContent") is not None:
            out = res["structuredContent"]
        else:
            text = "".join(c.get("text", "") for c in res.get("content", []))
            try:
                out = json.loads(text)
            except json.JSONDecodeError:
                out = text
        if res.get("isError"):
            raise RuntimeError(f"{name}: {json.dumps(out)[:2000]}")
        return out

    def upload(self, model_id, path, media_type):
        """Upload a file as an immutable artifact; returns the artifact reference."""
        data = Path(path).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        begin = self.call("begin_scientific_artifact_upload", {
            "model_id": model_id, "sha256": sha, "size_bytes": len(data),
            "media_type": media_type, "idempotency_key": f"upload-{sha[:32]}",
        })
        handle = begin.get("handle")
        if handle:
            # Presigned, write-once URL: send only the signed headers.
            req = urllib.request.Request(handle["url"], data, handle.get("headers", {}), method=handle.get("method", "PUT"))
            try:
                urllib.request.urlopen(req, timeout=600).read()
            except urllib.error.HTTPError as e:
                if e.code != 412:  # 412 = these exact bytes were already uploaded
                    raise
            except urllib.error.URLError:
                # Write-once storage can drop the connection on a repeat upload;
                # finalize below verifies the stored bytes either way.
                pass
        fin = self.call("finalize_scientific_artifact_upload", {"upload_id": begin["upload_id"]})
        return {
            "artifact_id": _find(fin, ("artifact_id",)) or begin["artifact"]["artifact_id"],
            "sha256": sha, "size_bytes": len(data),
            "media_type": media_type, "compression": "none",
        }

    def wait(self, operation_id, every=10, limit=3600):
        """Poll an operation until it finishes, then return its result."""
        start = time.time()
        while True:
            op = self.call("get_operation", {"operation_id": operation_id})
            # Per-step progress entries also carry a "state"; use the operation's own status.
            state = str((op.get("operation") or {}).get("status") or op.get("status") or "").lower()
            if any(s in state for s in ("succeed", "complete", "done", "fail", "cancel", "error")):
                break
            if time.time() - start > limit:
                raise TimeoutError(f"{operation_id} still {state}")
            time.sleep(every)
        if "fail" in state or "error" in state or "cancel" in state:
            raise RuntimeError(f"{operation_id} {state}: {json.dumps(op)[:2000]}")
        return self.call("get_operation_result", {"operation_id": operation_id})


def _find(obj, keys):
    """Depth-first search for the first value under any of `keys`."""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] not in (None, ""):
                return obj[k]
        for v in obj.values():
            r = _find(v, keys)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, keys)
            if r is not None:
                return r
    return None


if __name__ == "__main__":
    c = Client()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd == "tools":
        for t in c.tools():
            print(t["name"])
    elif cmd == "schema":
        for t in c.tools():
            if t["name"] in sys.argv[2:]:
                print(json.dumps(t, indent=1))
    elif cmd == "call":
        print(json.dumps(c.call(sys.argv[2], json.loads(sys.argv[3] if len(sys.argv) > 3 else "{}")), indent=1))
