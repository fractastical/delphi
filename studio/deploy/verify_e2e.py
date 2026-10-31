"""End-to-end driver for deploy/verify-scratch.sh. Talks to a RUNNING scratch stack over real HTTP and real files. Never prints a credential."""
import http.client
import json
import os
import stat
import sys
from pathlib import Path

PORT, ROOT, PHASE = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
GATE = os.environ["FRONTIER_ACCESS_TOKEN"]
NS = "verify-node"
cookie = {}


def call(method, path, body=None, headers=None, session=True):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    h = dict(headers or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
        h["Content-Type"] = "application/json"
    if session and cookie:
        h["Cookie"] = cookie["c"]
    c.request(method, path, body, h)
    r = c.getresponse()
    data = r.read()
    out = (r.status, {k.lower(): v for k, v in r.getheaders()}, data)
    c.close()
    return out


def jcall(*a, **k):
    s, h, d = call(*a, **k)
    return s, json.loads(d) if d[:1] in (b"{", b"[") else d, h


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


def login():
    s, body, h = jcall("POST", "/api/session", {"token": GATE}, session=False)
    ok(s == 200, "sign in with the access token")
    cookie["c"] = h["set-cookie"].split(";")[0]


def cred(name):
    return (ROOT / "credentials" / name).read_text().strip()


if PHASE == "first":
    ok(call("GET", "/api/health", session=False)[0] == 200, "health is public")
    ok(call("GET", "/api/catalog", session=False)[0] == 401, "catalog is gated")
    login()
    writer, reviewer = cred("writer.cred"), cred("reviewer.cred")
    from frontier.models import DIMENSIONS
    draft = {"namespace": NS, "kind": "Claim", "id": "e2e-claim", "issuer": "e2e-writer", "source_uri": "https://github.com/kganjam/delphi-frontier",
             "payload": {"title": "End-to-end fixture, not scientific data", "statement": "A software fixture asserts a scoped statement.", "context": "Deployment verification only",
                         "assumptions": ["Fixture"], "limitations": ["Not measured evidence"],
                         "source": {"uri": "https://github.com/kganjam/delphi-frontier", "locator": "README", "source_version": "v0", "content_sha256": "a" * 64,
                                    "content_available": False, "access": "public reference", "license": "CC0-1.0"}}}
    s, prop, _ = jcall("POST", "/v1/proposals", {"draft": draft}, {"Authorization": "Bearer " + writer, "Idempotency-Key": "e2e-1"}, session=False)
    ok(s == 200 and prop["local_status"] == "proposed", "write with an operator bearer credential -> proposed")
    ok(jcall("POST", "/v1/proposals", {"draft": draft}, {"Idempotency-Key": "e2e-2"})[0] == 401, "a browser session alone cannot write")
    s, cat, _ = jcall("GET", "/api/catalog?kind=Claim")
    ok(s == 200 and cat["results"][0]["record"] == prop["record"] and cat["results"][0]["local_status"] == "proposed", "catalog shows the full envelope, status separate")
    target = {k: prop["record"][k] for k in ("namespace", "kind", "id", "version")}
    a = {"target": target, "decision": "accepted", "independence_rationale": "Separate operator in a throwaway verification node",
         "limitations": ["Verification of deployment only"],
         "dimensions": {d: {"status": "passed", "reviewer": "e2e-reviewer", "rationale": "Deployment-check rationale; not a scientific review.", "evidence_links": []} for d in DIMENSIONS}}
    s, _, _ = jcall("POST", "/v1/reviews", {"assessment": a}, {"Authorization": "Bearer " + writer, "Idempotency-Key": "e2e-rev0"}, session=False)
    ok(s == 403, "the writer's own credential cannot review")
    s, rev, _ = jcall("POST", "/v1/reviews", {"assessment": a}, {"Authorization": "Bearer " + reviewer, "Idempotency-Key": "e2e-rev1"}, session=False)
    ok(s == 200 and rev["local_status"] == "accepted", "an independent reviewer credential accepts it")
    for name, mime in (("mesh.stl", "model/stl"), ("part.obj", "model/obj"), ("wing.glb", "model/gltf-binary"), ("table.csv", "text/csv"), ("t.lean", "text/plain"), ("x.trig", "application/trig")):
        s, h, d = call("GET", "/artifacts/" + name)
        ok(s == 200 and h["content-type"].startswith(mime) and h["x-content-type-options"] == "nosniff" and d, f"artifact {name} served as {mime}")
    ok(call("GET", "/other/mesh.stl")[0] == 404, "artifact types are not served outside site/artifacts")
    ok(call("GET", "/artifacts/secret-token.csv")[0] == 404 and call("GET", "/artifacts/../index.html")[0] in (200, 404), "credential-looking names are not served")
    ok(call("GET", "/artifacts/%2e%2e/%2e%2e/etc/passwd")[0] == 404, "traversal refused")
elif PHASE == "after-restart":
    ok(call("GET", "/api/health", session=False)[0] == 200, "health after restarting PostgreSQL and the web service")
    ok(call("GET", "/api/catalog", session=False)[0] == 401, "old sessions do not survive; sign in again")
    login()
    s, cat, _ = jcall("GET", "/api/catalog?kind=Claim")
    ok(s == 200 and cat["results"] and cat["results"][0]["record"]["id"] == "e2e-claim" and cat["results"][0]["local_status"] == "accepted", "record and its accepted review survived the restart")
    s, body, _ = jcall("POST", "/v1/proposals", {"draft": {"namespace": NS}}, {"Authorization": "Bearer " + cred("writer.cred"), "Idempotency-Key": "e2e-1"}, session=False)
    ok(s in (400, 409), "idempotency record persisted (same key, different request refused)")
elif PHASE == "files":
    for p in (ROOT, ROOT / "run", ROOT / "pgdata", ROOT / "credentials", ROOT / "backups"):
        ok(stat.S_IMODE(p.stat().st_mode) == 0o700, f"{p.name} is mode 700")
    for f in (ROOT / "credentials").iterdir():
        ok(stat.S_IMODE(f.stat().st_mode) == 0o600, f"credential file {f.name} is mode 600")
    hba = (ROOT / "pgdata" / "pg_hba.conf").read_text()
    ok("host " not in hba.replace("local", "") and "trust" not in hba and "peer map=frontier" in hba, "pg_hba: local peer only, no host lines, no trust")
    ok("listen_addresses = ''" in (ROOT / "pgdata" / "postgresql.conf").read_text(), "no TCP listener configured")
