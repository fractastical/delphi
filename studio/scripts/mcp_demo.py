"""A real MCP contribution round trip: a software protocol test, NOT a biological finding.

    FRONTIER_DSN='host=... dbname=...' python3 scripts/mcp_demo.py --namespace NS --credential-file PATH \\
        --expect-actor ACTOR --expect-operator OPERATOR [--execute]

What it does, entirely through the node's own MCP server over stdio (official SDK client):
  1. checks the interface in a read-only session and in a write-enabled session (a bounded, deterministic check of declared properties),
  2. proposes one software-test Claim and one Action (with the Action.proposal block), makes the Action ready (coordinator),
     leases it, starts it (running), runs that check, proposes an Evidence record with `produced_by` pointing at the Action and with
     the exact input, output and code sha256 digests, and submits the Action,
  3. reads everything back through MCP (get, search, artifacts, events) and writes a public receipt.

Honest limits, repeated in the records: the Claim is about this node's software interface; it says nothing about biology. Everything stays
`proposed`; nothing is reviewed or accepted (there is no review tool in MCP, and the same operator could not review it anyway). The
test, the server and the submitter are one operator, so the Evidence is not independent. Re-running is safe: record ids are fixed, state is
read first, and a completed run only re-verifies and writes nothing. Existing scientific records are never touched.

The credential is read from a mode-600 file, placed only in the child server's environment, and never printed, recorded or passed as an
argument. The lease id (a bearer capability) is held in memory only and is not recorded. Output carries no database location.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from frontier.models import POLICY, canonical, digest  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()
NS_DEFAULT = "delphi-frontier"
SOURCE_URI = "urn:frontier:software-protocol-test"
CLAIM_ID = "software-protocol-test-mcp-interface-invariants"
ACTION_ID = CLAIM_ID + "-action"
EVIDENCE_ID = CLAIM_ID + "-evidence"
SECRETISH = re.compile(r"token|dsn|password|secret|credential|authorization|api[_-]?key", re.I)
FORBIDDEN_TOOL_WORDS = ("review", "accept", "dispute", "import", "provision", "initialize")
READ_TOOLS = {"frontier_search", "frontier_get", "frontier_neighborhood", "frontier_events", "frontier_artifacts", "frontier_capabilities"}
WRITE_TOOLS = {"frontier_propose", "frontier_lease", "frontier_transition"}
EXIT_STOP = 3


class Stop(Exception):
    """Unexpected state: nothing further is written."""


# ----------------------------------------------------------------------------------------------------------------------
# The bounded check: a pure function of an observed interface snapshot.
# ----------------------------------------------------------------------------------------------------------------------
def run_check(snap: dict) -> list[dict]:
    """Deterministic and side-effect free. Each item states an invariant, whether it held on the snapshot, and the count it was checked on."""
    ro, rw = snap["read_only"], snap["write_enabled"]
    names = lambda s: {t["name"] for t in s["tools"]}  # noqa: E731
    out = []

    def item(i, statement, passed, detail):
        out.append({"id": i, "statement": statement, "passed": bool(passed), "detail": detail})

    item("I1", "Read-only mode registers exactly the tools its capability manifest names, all marked read-only, and no write tool",
         names(ro) == set(ro["manifest_tools"]) == READ_TOOLS and all(t["read_only"] for t in ro["tools"]) and not names(ro) & WRITE_TOOLS,
         {"tools_checked": len(ro["tools"])})
    item("I2", "Write-enabled mode registers exactly the manifest's tools: the read tools plus propose, lease and transition, and only those three are not read-only",
         names(rw) == set(rw["manifest_tools"]) == READ_TOOLS | WRITE_TOOLS and {t["name"] for t in rw["tools"] if not t["read_only"]} == WRITE_TOOLS,
         {"tools_checked": len(rw["tools"])})
    item("I3", "No tool in either mode accepts a credential-like argument (token, dsn, password, secret, credential, authorization, api key)",
         not any(SECRETISH.search(p) for s in (ro, rw) for t in s["tools"] for p in t["input_properties"]),
         {"arguments_checked": sum(len(t["input_properties"]) for s in (ro, rw) for t in s["tools"])})
    item("I4", "No registered tool name contains review, accept, dispute, import, provision or initialize",
         not any(w in n for s in (ro, rw) for n in names(s) for w in FORBIDDEN_TOOL_WORDS), {"names_checked": len(names(ro) | names(rw))})
    item("I5", "The anonymous read-only search returned only public records",
         ro["search_sample"]["n"] > 0 and ro["search_sample"]["public"] == ro["search_sample"]["n"], {"records_checked": ro["search_sample"]["n"]})
    item("I6", "Read-only mode acts as nobody; write mode reports a principal that lists no credential-like key",
         ro["principal_is_null"] and rw["principal_is_set"] and not rw["principal_has_secretish_key"], {})
    return out


def check_relation(verdict: list[dict]) -> str:
    return "supports" if verdict and all(v["passed"] for v in verdict) else "refutes"


def snapshot_from(mode: str, tools, caps: dict, search: dict) -> dict:
    snap = {"mode": mode, "manifest_mode": caps["mode"], "manifest_tools": sorted(t["name"] for t in caps["tools"]),
            "tools": sorted(({"name": t.name, "read_only": bool(t.annotations and t.annotations.readOnlyHint),
                              "input_properties": sorted((t.inputSchema or {}).get("properties", {}))} for t in tools), key=lambda x: x["name"]),
            "search_sample": {"n": len(search["results"]), "public": sum(1 for r in search["results"] if r.get("visibility") == "public")},
            "principal_is_null": caps["principal"] is None, "principal_is_set": caps["principal"] is not None,
            "principal_has_secretish_key": bool(caps["principal"]) and any(SECRETISH.search(k) for k in caps["principal"])}
    return snap


def file_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


# ----------------------------------------------------------------------------------------------------------------------
# Record builders (pure)
# ----------------------------------------------------------------------------------------------------------------------
def claim_draft(namespace: str, actor: str, commit: str) -> dict:
    return {"namespace": namespace, "kind": "Claim", "id": CLAIM_ID, "issuer": actor, "source_uri": SOURCE_URI, "visibility": "public", "predecessor": None,
            "payload": {
                "title": "Software protocol test: MCP interface invariants (not a biological finding)",
                "statement": ("In the Delphi Frontier MCP server, read-only mode registers only read-only tools, write-enabled mode registers exactly three additional "
                              "write tools (propose, lease, transition), every registered tool is named in the capability manifest, no tool takes a credential-like "
                              "argument, no tool name offers review, acceptance, import or provisioning, and the anonymous read-only search returns only public records."),
                "context": "A software integration diagnostic of this node's own interface. It contains no biology and makes no claim about any organism, gene, model or experiment.",
                "assumptions": ["The tool listing and capability manifest returned by the running server describe the code that is deployed.",
                                "The check observes declared properties of the interface, not the server's behaviour under adversarial input."],
                "limitations": ["Software protocol test only; not a biological or scientific finding and not evidence for any Delphi scientific claim.",
                                "One operator proposed it, ran the check and submitted the result, so nothing here is independent.",
                                "It is not reviewed or accepted. It covers six listed invariants on one deployment and one code version."],
                "source": {"uri": None, "locator": f"frontier/mcp.py and scripts/mcp_demo.py at repository commit {commit}", "source_version": commit,
                           "content_sha256": None, "content_available": False,
                           "access": "The software under test is this node's own code. No external source; this record does not serve the bytes.", "license": None},
                "origin": "hypothesis"}}


def action_draft(namespace: str, actor: str, claim_ref: dict, code_sha: str, env: str) -> dict:
    return {"namespace": namespace, "kind": "Action", "id": ACTION_ID, "issuer": actor, "source_uri": SOURCE_URI, "visibility": "public", "predecessor": None,
            "payload": {
                "target": claim_ref, "title": "Run the MCP interface invariant check (software protocol test)",
                "acceptance_criteria": ["All six listed invariants hold on the observed interface snapshot, or the failing ones are reported.",
                                        "The exact input, output and code sha256 digests are recorded in an Evidence record that names this Action as its producer."],
                "required_capabilities": ["mcp-client"],
                "cost_stop_bounds": "At most 120 seconds and two local stdio sessions to the node's own MCP server; no network, GPU or metered call. Stop on the first unexpected state.",
                "cache_key": {"target": claim_ref["version"], "input": "mcp-interface-snapshot-v1", "code": code_sha, "model": "none", "environment": env,
                              "parameters": "read-only session and write-enabled session; anonymous search limit 50", "scope": "software-protocol-only",
                              "acceptance_policy": POLICY},
                "proposal": {
                    "intent": "analysis",
                    "method": "Start the node's MCP server in read-only mode and in write-enabled mode, list tools and read the capability manifest in each, take an anonymous search sample, and evaluate six fixed invariants as a pure function of that snapshot.",
                    "assumptions": ["The servers started by this client are the code under test."],
                    "alternatives": [{"label": "no-check", "description": "Record the Claim with no run.", "tradeoff": "Cheaper, but nothing would be tested and no Action would complete through MCP."}],
                    "expected_information": "Whether the stated interface invariants hold on this deployment; no information about biology.",
                    "decision_context": "Whether the MCP contribution loop (propose, ready, lease, run, evidence, submit) works end to end on the live node.",
                    "expected_outputs": ["interface snapshot (JSON)", "verdict per invariant (JSON)"],
                    "controls": ["The check is a pure function: the same snapshot gives the same verdict.", "Hashes of the input and output files are recorded and can be recomputed."],
                    "analysis_plan": "Compute each invariant on the snapshot; report passes and failures verbatim; do not alter a failing result.",
                    "outcomes": [{"label": "all-pass", "criterion": "All six invariants hold", "decision_consequence": "The Evidence supports the software Claim; it is still unreviewed and not independent."},
                                 {"label": "some-fail", "criterion": "At least one invariant fails", "decision_consequence": "The Evidence refutes the Claim as stated; the failing interface property needs a fix."}],
                    "selection_basis": "manual", "selection_rationale": "Chosen by the operator to exercise the live contribution loop; not selected by any utility or forecast.",
                    "limitations": ["Software protocol test; no scientific content.", "Proposer, runner and submitter are the same operator."]}}}


def evidence_draft(namespace: str, actor: str, claim_ref: dict, action_ref: dict, arts: dict, verdict: list[dict], commit: str, when: str) -> dict:
    passed = sum(1 for v in verdict if v["passed"])
    mk = lambda title, sha, size, role, media: {"title": title, "uri": "urn:sha256:" + sha, "sha256": sha, "byte_size": size, "media_type": media,  # noqa: E731
                                                "role": role, "availability": "referenced", "license": None}
    return {"namespace": namespace, "kind": "Evidence", "id": EVIDENCE_ID, "issuer": actor, "source_uri": SOURCE_URI, "visibility": "public", "predecessor": None,
            "payload": {
                "target": claim_ref, "evidence_kind": "source_assessment",
                "source": {"uri": None, "locator": f"scripts/mcp_demo.py at repository commit {commit}", "source_version": commit, "content_sha256": arts["code"]["sha256"],
                           "content_available": False, "access": "The test script and server code are in this project's repository; this record declares their digests and does not serve the bytes.", "license": None},
                "created_time": {"value": when, "basis": "declared"}, "retrieved_time": {"value": when, "basis": "declared"},
                "method": f"A pure function evaluated six interface invariants on a snapshot of the node's MCP tool listings, capability manifests and an anonymous search sample. {passed} of {len(verdict)} held.",
                "context": "Software protocol test of this node's own MCP interface. Not a biological observation; the evidence kind 'source_assessment' is used because the enumeration has no software-test value.",
                "assumptions": ["The snapshot is faithful to the running server.", "The six invariants are the ones the Claim states."],
                "provenance": {"tool": "scripts/mcp_demo.py", "commit": commit, "run": "mcp stdio, official SDK client", "verdict": [{k: v[k] for k in ("id", "passed")} for v in verdict]},
                "source_dependence": {"group": "same-operator-same-code", "independence": "none: the code under test, the test and the submission share one operator"},
                "uncertainty": "Deterministic checks of declared properties; no statistical uncertainty. A different deployment or code version may differ.",
                "limitations": ["Not a biological finding and not evidence for any scientific Delphi claim.", "Not independent, not reviewed, not accepted.",
                                "Digests identify the input and output files kept in the repository's imports directory; the node does not store those bytes."],
                "relation": check_relation(verdict), "produced_by": action_ref,
                "artifacts": [mk("Interface snapshot (input)", arts["input"]["sha256"], arts["input"]["size"], "input", "application/json"),
                              mk("Invariant verdicts (output)", arts["output"]["sha256"], arts["output"]["size"], "output", "application/json"),
                              mk("Test script scripts/mcp_demo.py (code)", arts["code"]["sha256"], arts["code"]["size"], "code", "text/x-python")]}}


# ----------------------------------------------------------------------------------------------------------------------
# MCP plumbing
# ----------------------------------------------------------------------------------------------------------------------
def read_credential(path: str) -> str:
    p = Path(path)
    if p.stat().st_mode & 0o077:
        raise Stop(f"credential file {p.name} is readable by group or others; refusing to use it")
    token = p.read_text().strip()
    if not token or "\n" in token:
        raise Stop(f"credential file {p.name} is empty or malformed")
    return token


def val(result):
    if result.isError:
        text = result.content[0].text if result.content else "error"
        raise Stop("MCP tool error: " + text[:200])
    return json.loads(result.content[0].text)


class Servers:
    def __init__(self, namespace: str, schema: str, dsn: str, token: str):
        self.namespace, self.schema, self.dsn, self.token = namespace, schema, dsn, token
        self.errlog = tempfile.TemporaryFile("w+")

    def params(self, write: bool):
        from mcp import StdioServerParameters
        env = {"FRONTIER_DSN": self.dsn, "PYTHONPATH": str(REPO), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "PYTHONDONTWRITEBYTECODE": "1"}
        if write:
            env["FRONTIER_TOKEN"] = self.token
        args = ["-m", "frontier", "mcp", "--namespace", self.namespace, "--schema", self.schema] + (["--allow-write"] if write else [])
        return StdioServerParameters(command=sys.executable, args=args, env=env, cwd=str(REPO))

    def open(self, write: bool):
        from contextlib import asynccontextmanager
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        @asynccontextmanager
        async def cm():
            async with stdio_client(self.params(write), errlog=self.errlog) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    yield s
        return cm()

    def token_in_stderr(self) -> bool:
        self.errlog.seek(0)
        return self.token in self.errlog.read()


async def head_of(s, kind: str, rid: str, actor: str):
    """The exact current head of (kind, id) through MCP, or None. Stops if it was not written by this actor from this source."""
    res = val(await s.call_tool("frontier_search", {"query": rid, "kinds": [kind], "limit": 5}))
    hits = [r for r in res["results"] if r["ref"]["id"] == rid]
    if not hits:
        return None
    if len(hits) != 1 or hits[0]["issuer"] != actor or hits[0]["source_uri"] != SOURCE_URI:
        raise Stop(f"{kind}/{rid}: unexpected author or duplicate head")
    got = val(await s.call_tool("frontier_get", {"target": hits[0]["ref"]}))
    return {"ref": hits[0]["ref"], "record": got["record"], "action": got["action"], "status": got["local_review"]["status"], "is_head": got["is_head"]}


async def observe(servers: Servers):
    async with servers.open(False) as s:
        ro_tools = (await s.list_tools()).tools
        ro_caps = val(await s.call_tool("frontier_capabilities", {}))
        ro_search = val(await s.call_tool("frontier_search", {"limit": 50}))
    async with servers.open(True) as s:
        rw_tools = (await s.list_tools()).tools
        rw_caps = val(await s.call_tool("frontier_capabilities", {}))
        rw_search = val(await s.call_tool("frontier_search", {"limit": 5}))
    return {"read_only": snapshot_from("read_only", ro_tools, ro_caps, ro_search), "write_enabled": snapshot_from("write_enabled", rw_tools, rw_caps, rw_search)}


def git(*args) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


async def run(a) -> dict:
    token = read_credential(a.credential_file)
    dsn = os.environ["FRONTIER_DSN"]
    servers = Servers(a.namespace, a.schema, dsn, token)
    commit = git("rev-parse", "HEAD")
    code_committed = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", "scripts/mcp_demo.py"]).returncode == 0
    code_bytes = SELF.read_bytes()
    code_sha = sha256(code_bytes).hexdigest()
    if a.execute and not code_committed and not a.allow_dirty_code:
        raise Stop("scripts/mcp_demo.py has uncommitted changes; the code digest would not match any commit")
    env = f"python {platform.python_version()}; mcp sdk {importlib.metadata.version('mcp')}"
    async def do_check():
        """The bounded check: observe both modes of the node's own MCP server, then evaluate the invariants as a pure function."""
        snap = await observe(servers)
        verdict = run_check(snap)
        in_bytes, out_bytes = file_bytes(snap), file_bytes({"invariants": verdict, "relation": check_relation(verdict)})
        arts = {"input": {"sha256": sha256(in_bytes).hexdigest(), "size": len(in_bytes)}, "output": {"sha256": sha256(out_bytes).hexdigest(), "size": len(out_bytes)},
                "code": {"sha256": code_sha, "size": len(code_bytes)}}
        return verdict, in_bytes, out_bytes, arts

    def describe(verdict, arts):
        return {"mode": "execute" if a.execute else "dry_run", "namespace": a.namespace, "actor": a.expect_actor, "operator": a.expect_operator,
                "invariants_passed": f"{sum(1 for v in verdict if v['passed'])} of {len(verdict)}", "relation_if_recorded": check_relation(verdict), "artifacts": arts,
                "commit": commit, "code_committed": code_committed}

    async with servers.open(True) as s:
        caps = val(await s.call_tool("frontier_capabilities", {}))
        pr = caps["principal"] or {}
        if caps["mode"] != "write_enabled" or pr.get("actor") != a.expect_actor or pr.get("operator") != a.expect_operator \
                or not {"contributor", "coordinator"} <= set(pr.get("roles", [])) or a.namespace not in pr.get("namespaces", []):
            raise Stop(f"credential belongs to {pr.get('actor')!r}/{pr.get('operator')!r} with roles {pr.get('roles')}; expected "
                       f"{a.expect_actor!r}/{a.expect_operator!r} as contributor and coordinator in {a.namespace}")
        claim = await head_of(s, "Claim", CLAIM_ID, a.expect_actor)
        action = await head_of(s, "Action", ACTION_ID, a.expect_actor)
        evid = await head_of(s, "Evidence", EVIDENCE_ID, a.expect_actor)
        state = action["action"]["state"] if action and action["action"] else None
        pre = {"claim": bool(claim), "action_state": state, "evidence": bool(evid)}
        if (evid and state == "submitted") or not a.execute:
            verdict, in_bytes, out_bytes, arts = await do_check()
            plan = {**describe(verdict, arts), "existing": pre,
                    "outcome": "already_complete" if evid and state == "submitted" else "would_run"}
            return {"plan": plan, "steps": [], "verdict": verdict, "in_bytes": in_bytes, "out_bytes": out_bytes, "written": False, "leak": servers.token_in_stderr()}
        if (action and state not in ("proposed", "ready")) or (evid and state != "submitted"):
            raise Stop(f"existing Action is in state {state!r} with evidence={bool(evid)}; cannot resume safely (the lease id is not recoverable)")
        steps = []

        async def call(step, tool, args, summary):
            out = val(await s.call_tool(tool, args))
            steps.append({"step": step, "tool": tool, **summary(out)})
            return out

        actor, ns = a.expect_actor, a.namespace
        tag = digest({"claim": claim_draft(ns, actor, commit)["payload"]})[:16]
        if not claim:
            d = claim_draft(ns, actor, commit)
            out = await call("propose_claim", "frontier_propose", {"draft": d, "idempotency_key": f"mcp-demo:claim:{tag}"},
                             lambda o: {"id": CLAIM_ID, "version": o["record"]["version"], "local_status": o["local_status"], "idempotency_key": f"mcp-demo:claim:{tag}"})
            claim_ref = {k: out["record"][k] for k in ("namespace", "kind", "id", "version")}
        else:
            claim_ref = claim["ref"]
        if not action:
            d = action_draft(ns, actor, claim_ref, code_sha, env)
            key = f"mcp-demo:action:{digest(d['payload'])[:16]}"
            out = await call("propose_action", "frontier_propose", {"draft": d, "idempotency_key": key},
                             lambda o: {"id": ACTION_ID, "version": o["record"]["version"], "local_status": o["local_status"], "idempotency_key": key})
            action_ref = {k: out["record"][k] for k in ("namespace", "kind", "id", "version")}
            state = "proposed"
        else:
            action_ref = action["ref"]
        if state == "proposed":
            await call("ready", "frontier_transition", {"target": action_ref, "state": "ready", "idempotency_key": f"mcp-demo:ready:{action_ref['version'][:24]}"},
                       lambda o: {"state": o["state"], "idempotency_key": f"mcp-demo:ready:{action_ref['version'][:24]}"})
        lease = await call("lease", "frontier_lease", {"target": action_ref, "seconds": 300, "idempotency_key": f"mcp-demo:lease:{action_ref['version'][:24]}"},
                           lambda o: {"state": o["state"], "seconds": 300, "idempotency_key": f"mcp-demo:lease:{action_ref['version'][:24]}", "lease_id": "held in memory only; not recorded"})
        lid = lease["lease_id"]
        await call("start", "frontier_transition", {"target": action_ref, "state": "running", "lease_id": lid, "idempotency_key": f"mcp-demo:running:{action_ref['version'][:24]}"},
                   lambda o: {"state": o["state"], "idempotency_key": f"mcp-demo:running:{action_ref['version'][:24]}"})
        # The bounded check runs HERE, while the Action is running and the lease is held.
        verdict, in_bytes, out_bytes, arts = await do_check()
        plan = describe(verdict, arts)
        when = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ev = evidence_draft(ns, actor, claim_ref, action_ref, arts, verdict, commit, when)
        ekey = f"mcp-demo:evidence:{digest({k: v for k, v in ev['payload'].items() if k not in ('created_time', 'retrieved_time')})[:16]}"
        out = await call("propose_evidence", "frontier_propose", {"draft": ev, "idempotency_key": ekey},
                         lambda o: {"id": EVIDENCE_ID, "version": o["record"]["version"], "local_status": o["local_status"], "idempotency_key": ekey})
        evid_ref = {k: out["record"][k] for k in ("namespace", "kind", "id", "version")}
        await call("complete", "frontier_transition", {"target": action_ref, "state": "submitted", "lease_id": lid, "idempotency_key": f"mcp-demo:submitted:{action_ref['version'][:24]}"},
                   lambda o: {"state": o["state"], "idempotency_key": f"mcp-demo:submitted:{action_ref['version'][:24]}"})
        # read-back through MCP
        rb = {}
        for name, r in (("claim", claim_ref), ("action", action_ref), ("evidence", evid_ref)):
            g = val(await s.call_tool("frontier_get", {"target": r}))
            rb[name] = {"ref": r, "is_head": g["is_head"], "local_status": g["local_review"]["status"], "action_state": (g["action"] or {}).get("state")}
        art = val(await s.call_tool("frontier_artifacts", {"query": "software protocol test", "limit": 50}))
        rb["artifact_index"] = [{"role": x["artifact"]["role"], "sha256": x["artifact"]["sha256"], "evidence": x["evidence"]["id"], "produced_by": (x["produced_by"] or {}).get("id"),
                                 "local_status": x["local_status"], "artifact_bytes_verified": x["artifact_bytes_verified"]}
                                for x in art["items"] if x["evidence"]["id"] == EVIDENCE_ID]
        ev_page = val(await s.call_tool("frontier_events", {"after": 0, "limit": 50}))
        mine = {x["envelope"]["payload"]["event_type"] for x in ev_page["events"] if x["envelope"]["payload"].get("target", {}).get("id") in (CLAIM_ID, ACTION_ID, EVIDENCE_ID)} if ev_page.get("events") else set()
        rb["event_types_seen_in_first_page"] = sorted(mine)
        return {"plan": {**plan, "existing": pre, "outcome": "completed"}, "steps": steps, "verdict": verdict, "in_bytes": in_bytes, "out_bytes": out_bytes, "written": True,
                "refs": {"claim": claim_ref, "action": action_ref, "evidence": evid_ref}, "read_back": rb, "leak": servers.token_in_stderr()}


def find_stop(e):
    if isinstance(e, Stop):
        return e
    for sub in getattr(e, "exceptions", ()):
        found = find_stop(sub)
        if found:
            return found
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--namespace", default=NS_DEFAULT)
    ap.add_argument("--schema", default="public")
    ap.add_argument("--credential-file", required=True)
    ap.add_argument("--expect-actor", required=True)
    ap.add_argument("--expect-operator", required=True)
    ap.add_argument("--out-dir", default=str(REPO / "imports"), help="where the input/output files and the receipt are written")
    ap.add_argument("--receipt-name", default="2026-10-31-mcp-roundtrip-receipt.json")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--allow-dirty-code", action="store_true", help="tests only: accept an uncommitted script (the receipt says so)")
    a = ap.parse_args(argv)
    try:
        r = asyncio.run(asyncio.wait_for(run(a), timeout=300))
    except Stop as e:
        print(json.dumps({"ok": False, "stopped": str(e)}))
        return EXIT_STOP
    except Exception as e:  # noqa: BLE001 - never print a traceback or text that could carry a connection string or credential
        stop = find_stop(e)  # a Stop raised inside the client's task group arrives wrapped in an ExceptionGroup
        if stop:
            print(json.dumps({"ok": False, "stopped": str(stop)}))
            return EXIT_STOP
        print(json.dumps({"ok": False, "error": type(e).__name__}))
        return 2
    if r["leak"]:
        print(json.dumps({"ok": False, "error": "credential would have appeared in server stderr; output suppressed"}))
        return 2
    out = Path(a.out_dir)
    if r["written"]:
        out.mkdir(parents=True, exist_ok=True)
        (out / "mcp-demo-input.json").write_bytes(r["in_bytes"])
        (out / "mcp-demo-output.json").write_bytes(r["out_bytes"])
        receipt = {"what": "A real MCP contribution round trip on the live node: a SOFTWARE PROTOCOL TEST, not a biological finding.",
                   "all_records_are": "proposed; nothing reviewed or accepted; not independent (one operator)", **r["plan"], "steps": r["steps"],
                   "records": r["refs"], "read_back": r["read_back"], "invariants": r["verdict"],
                   "files": {"input": "imports/mcp-demo-input.json", "output": "imports/mcp-demo-output.json", "code": "scripts/mcp_demo.py"},
                   "hash_check": "sha256 of the three files equals the digests in the Evidence artifacts",
                   "not_recorded": "credential, lease id, database location",
                   "evidence_kind_note": "Evidence uses 'source_assessment' because the enumeration has no software-test value (an open point for the owner of models.py)."}
        tmp = out / (a.receipt_name + ".tmp")
        tmp.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
        os.replace(tmp, out / a.receipt_name)
    print(json.dumps({"ok": True, "outcome": r["plan"]["outcome"], "invariants_passed": r["plan"]["invariants_passed"], "relation": r["plan"]["relation_if_recorded"],
                      "written": r["written"], "existing": r["plan"]["existing"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
