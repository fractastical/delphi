import asyncio
from contextlib import asynccontextmanager
import os
import subprocess
import tempfile
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
from threading import Thread

import pytest

from frontier.http import BoundedHTTPServer, make_server
from frontier.models import ref
from conftest import TOKENS, action, claim, evidence, source


def test_http_real_authenticated_proposal_and_shared_read(store):
    server = make_server(store)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def request(path, data, token=None, key=None, origin=None):
        c = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if key:
            headers["Idempotency-Key"] = key
        if origin:
            headers["Origin"] = origin
        c.request("POST", path, json.dumps(data), headers)
        response = c.getresponse()
        result = response.status, json.loads(response.read())
        c.close()
        return result
    try:
        draft = claim(store)
        assert request("/v1/proposals", {"draft": draft}, key="no-token")[0] == 401
        code, proposed = request("/v1/proposals", {"draft": draft}, TOKENS["alice"], "http-proposal")
        assert code == 200
        assert proposed["local_status"] == "proposed"
        code, fetched = request("/v1/read/get", {"target": ref(proposed["record"])})
        assert code == 200 and fetched["record"] == proposed["record"]
        assert store.get(ref(proposed["record"])) == fetched
        assert request("/v1/read/search", {"limit": 51})[0] == 400
        assert request("/v1/read/search", {}, origin="https://untrusted.example")[0] == 400
        assert request("/v1/actions/transition", {"target": ref(proposed["record"]), "state": "accepted"}, TOKENS["alice"], "bad")[0] == 400
        assert request("/v1/read/search", {"token": TOKENS["alice"]})[0] == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    with pytest.raises(ValueError):
        BoundedHTTPServer(("0.0.0.0", 0), object)


ROOT = Path(__file__).resolve().parents[1]
READ_TOOLS = {"frontier_search", "frontier_get", "frontier_neighborhood", "frontier_events", "frontier_capabilities", "frontier_artifacts", "frontier_proofs",
              "frontier_discover", "frontier_graph", "frontier_catalogue", "frontier_project_inspect", "frontier_artifact_inspect",
              "frontier_design_context", "frontier_simulate", "frontier_engineer", "frontier_formalize", "frontier_belief",
              "frontier_plan_experiments"}
WRITE_TOOLS = {"frontier_propose", "frontier_lease", "frontier_transition"}
SECRET_NAMES = {"token", "dsn", "password", "credential", "authorization", "secret", "api_key", "apikey"}


def server_env(store, token=None, dsn=None):
    env = {"FRONTIER_DSN": dsn or store.dsn, "PYTHONPATH": str(ROOT), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    if token:
        env["FRONTIER_TOKEN"] = token
    return env


def test_mcp_artifact_text_reads_verified_published_bytes(store, tmp_path, monkeypatch):
    from hashlib import sha256
    from frontier import mcp_surfaces
    from frontier.media import LocalMedia

    contents = b'{"units":"Pa","pressure":12.5}'
    path = tmp_path / "artifacts" / "output.json"
    path.parent.mkdir()
    path.write_bytes(contents)
    projection = LocalMedia(tmp_path)
    monkeypatch.setattr(mcp_surfaces, "LocalMedia", lambda *args, **kwargs: projection)
    registered = {}
    def register(function, *args):
        registered[function.__name__] = function
    mcp_surfaces.register_surfaces(None, store, register, read_annotations={}, public_host="example.org")
    inspect = registered["frontier_artifact_inspect"]
    digest = sha256(contents).hexdigest()
    metadata = inspect(digest)
    assert metadata["preview"] is None and metadata["declarations"] == []
    result = inspect(digest, include_text=True, max_chars=10)
    assert result["preview"]["text"] == contents.decode()[:10]
    assert result["preview"]["full_file_hash_verified"] and result["preview"]["truncated"]
    assert result["local_published_bytes"]["matches"][0]["public_url"] == "https://example.org/artifacts/output.json"


@asynccontextmanager
async def session_for(store, token=None, allow_write=False, errlog=None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    args = ["-m", "frontier", "mcp", "--namespace", store.namespace, "--schema", store.schema] + (["--allow-write"] if allow_write else [])
    params = StdioServerParameters(command=sys.executable, args=args, env=server_env(store, token))
    async with stdio_client(params, errlog=errlog or sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def run(coro, timeout=60):
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


def val(result):
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


def test_official_mcp_stdio_reads_same_persisted_record(store):
    record = store.submit(TOKENS["alice"], "mcp-source", claim(store))["record"]

    async def exercise():
        async with session_for(store) as session:
            tools = (await session.list_tools()).tools
            assert {t.name for t in tools} == READ_TOOLS
            assert all(t.annotations.readOnlyHint for t in tools)
            proofs = val(await session.call_tool("frontier_proofs", {}))
            assert len(proofs["families"]) == 4 and proofs["withheld"] == []
            assert not proofs["compile_executed"] and not proofs["biological_validation"]
            assert all("source" not in f for f in proofs["families"])
            oxygen = val(await session.call_tool("frontier_proofs", {"family": "steady-oxygen-bound", "include_source": True}))
            assert len(oxygen["families"]) == 1 and oxygen["withheld"] == []
            assert len(oxygen["families"][0]["check_results"]) == 6
            assert oxygen["families"][0]["contextual_reuse"]["status"] == "exact project versions matched the live registry"
            assert "sphere_center_oxygen_bound" in oxygen["families"][0]["theorem_names"]
            theorem = val(await session.call_tool("frontier_proofs", {"family": "cantilever-guard", "include_source": True}))
            assert "cantilever_guard_hypotheses_satisfiable" in theorem["families"][0]["source"]["text"]
            assert (await session.call_tool("frontier_proofs", {"family": "../../secret"})).isError

            value = val(await session.call_tool("frontier_get", {"target": ref(record)}))
            assert value["record"] == record
            assert (await session.call_tool("frontier_search", {"limit": 51})).isError
            assert (await session.call_tool("frontier_artifacts", {"limit": 51})).isError
            assert val(await session.call_tool("frontier_artifacts", {}))["items"] == []
            caps = val(await session.call_tool("frontier_capabilities", {}))
            assert caps["mode"] == "read_only" and caps["principal"] is None and caps["namespace"] == store.namespace
            assert {t["name"] for t in caps["tools"]} == READ_TOOLS and "review" in " ".join(caps["not_available"])
            resources = {str(r.uri) for r in (await session.list_resources()).resources}
            assert "frontier://capabilities" in resources
            schema = json.loads((await session.read_resource("frontier://schema/Claim")).contents[0].text)
            assert "statement" in schema["properties"]
            assert json.loads((await session.read_resource("frontier://capabilities")).contents[0].text)["mode"] == "read_only"
    run(exercise())


def test_mcp_experimental_design_is_bounded_ephemeral_and_read_only(store):
    from copy import deepcopy
    from engineering.experimental_design.cantilever_demo import build_cantilever_protocol

    contract = build_cantilever_protocol()
    event_count = len(store.events(limit=50)["events"])

    async def exercise():
        async with session_for(store) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            names = set(tools)
            assert names == READ_TOOLS
            assert "frontier_plan_experiments" in names
            assert tools["frontier_plan_experiments"].annotations.readOnlyHint is True
            capabilities = val(await session.call_tool("frontier_capabilities", {}))
            entry = next(tool for tool in capabilities["tools"] if tool["name"] == "frontier_plan_experiments")
            assert entry["kind"] == "read" and entry["requires_role"] is None
            assert capabilities["manifest_version"] == "frontier-mcp-capabilities-0.4"
            assert capabilities["limits"]["experimental_design"]["parameters"] == 8
            assert capabilities["limits"]["experimental_design"]["candidate_designs"] == 12
            planned = val(await session.call_tool("frontier_plan_experiments", {"contract": contract}))
            designs = {row["id"]: row for row in planned["designs"]}
            assert planned["status"] == "prospective_assumption_based"
            assert planned["selected_design_id"] == "mixed_load_deflection"
            assert designs["deflection_only"]["identifiability"]["rank"] == 1
            assert designs["mixed_load_deflection"]["identifiability"]["rank"] == 2
            assert planned["measurement_rows"] == []
            assert planned["mcp_policy"]["persisted"] is False
            assert planned["action_artifact"]["state"] == "proposal_unlinked"

            invalid = deepcopy(contract)
            invalid["parameters"]["prior_covariance"] = [[-1.0, 0.0], [0.0, 1.0]]
            assert (await session.call_tool("frontier_plan_experiments", {"contract": invalid})).isError

            too_many = deepcopy(contract)
            too_many["parameters"]["names"] = [f"p{i}" for i in range(9)]
            assert (await session.call_tool("frontier_plan_experiments", {"contract": too_many})).isError

            too_many_candidates = deepcopy(contract)
            too_many_candidates["designs"] *= 7
            assert (await session.call_tool("frontier_plan_experiments", {"contract": too_many_candidates})).isError

            too_many_observations = deepcopy(contract)
            too_many_observations["designs"][0]["observations"] *= 17
            assert (await session.call_tool("frontier_plan_experiments", {"contract": too_many_observations})).isError

            too_many_repeats = deepcopy(contract)
            too_many_repeats["designs"][0]["observations"][0]["technical_repeat"] = 65
            assert (await session.call_tool("frontier_plan_experiments", {"contract": too_many_repeats})).isError

            oversized_text = deepcopy(contract)
            oversized_text["title"] = "x" * 2049
            assert (await session.call_tool("frontier_plan_experiments", {"contract": oversized_text})).isError

            oversized_request = deepcopy(contract)
            oversized_request["context"]["open_gaps"] = ["x" * 1800] * 40
            assert (await session.call_tool("frontier_plan_experiments", {"contract": oversized_request})).isError

    run(exercise())
    assert len(store.events(limit=50)["events"]) == event_count


def test_expanded_mcp_surfaces_use_exact_refs_and_bounded_local_calculators(store):
    claim_record = store.submit(TOKENS["alice"], "surface-claim", claim(store, id="surface-claim"))["record"]
    claim_ref = ref(claim_record)
    problem = {"namespace": store.namespace, "kind": "Problem", "id": "surface-problem", "issuer": "alice",
               "source_uri": "urn:frontier:mcp-test", "payload": {
                   "title": "Software research question", "known_state": "A protocol fixture only.",
                   "question": "Can this bounded test request be replayed?", "problem_kind": "computational_open_question",
                   "novelty_status": "fixture", "data_access": "No external data.", "completeness": "actionable",
                   "acceptance_criteria": ["The MCP queue stores a proposed Action"], "falsifiers": ["Action state is not proposed"],
                   "next_action": "Run the isolated protocol test", "required_capabilities": ["local-test"],
                   "cost_stop_bounds": "One local test run; no provider calls.", "downstream_uses": ["Protocol coverage"],
                   "dependencies": [], "source": source(), "approach": "unknown", "scales": ["organism"], "context_tags": ["test"]}}
    problem_record = store.submit(TOKENS["alice"], "surface-problem", problem)["record"]
    problem_ref = ref(problem_record)
    project = {"namespace": store.namespace, "kind": "Project", "id": "surface-project", "issuer": "alice",
               "source_uri": "urn:frontier:mcp-test", "payload": {
                   "title": "MCP surface fixture", "mission": "Exercise project pins only.", "source": source(),
                   "limitations": ["Software fixture; no scientific claim."],
                   "scale_coverage": [{"scale": "organism", "status": "unknown", "note": "Test-only."}],
                   "members": [{"ref": claim_ref, "role": "mission", "subsystem": "test fixture", "relationship": "informs",
                                "applicability": "Protocol tests only.", "rationale": "Exercise exact project-member pins."}],
                   "requirements": [], "open_questions": [{"text": "A pinned test question.", "problem": problem_ref, "blocks": []}]}}
    project_record = store.submit(TOKENS["alice"], "surface-project", project)["record"]
    artifact_sha = "a" * 64
    evidence_draft = evidence(store, claim_ref)
    evidence_draft["id"] = "surface-evidence"
    evidence_draft["payload"]["artifacts"] = [{"title": "Declared test output", "uri": "https://example.org/test-output.json",
        "sha256": artifact_sha, "byte_size": 12, "media_type": "application/json", "role": "output",
        "availability": "referenced", "license": None}]
    store.submit(TOKENS["alice"], "surface-evidence", evidence_draft)

    async def exercise():
        async with session_for(store) as session:
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == READ_TOOLS
            discovered = val(await session.call_tool("frontier_discover", {"query": "Protocol fixture", "mode": "hybrid"}))
            assert discovered["provider_requests"] == 0 and "fallback_used" in discovered
            if discovered["fallback_used"]:
                assert discovered.get("unavailable_reason")
            assert discovered["items"]
            graph = val(await session.call_tool("frontier_graph", {"target": problem_ref, "depth": 2, "limit": 30}))
            assert graph["scope"]["target_ref"] == problem_ref and graph["counts"]["public_records_available"] >= 3
            counts = val(await session.call_tool("frontier_catalogue", {}))
            assert counts["scope"]["records_read"] >= 4
            inspected = val(await session.call_tool("frontier_project_inspect", {"target": ref(project_record)}))
            assert inspected["project"]["record"]["version"] == project_record["version"]
            assert inspected["members"]["members"][0]["pin"] == claim_ref
            design_context = val(await session.call_tool("frontier_design_context", {"target": ref(project_record), "limit": 5}))
            assert design_context["project"]["record"]["version"] == project_record["version"]
            assert design_context["pagination"]["truncated"] is False
            asset = val(await session.call_tool("frontier_artifact_inspect", {"sha256": artifact_sha}))
            assert len(asset["declarations"]) == 1 and asset["preview"] is None
            assert asset["declarations"][0]["artifact"]["sha256"] == artifact_sha
            preview = val(await session.call_tool("frontier_artifact_inspect", {"sha256": artifact_sha, "include_text": True, "max_chars": 100}))
            assert preview["preview"]["status"] == "unavailable" and preview["preview"]["text"] is None
            bad_preview = await session.call_tool("frontier_artifact_inspect", {"sha256": artifact_sha, "include_text": True, "max_chars": 16001})
            assert bad_preview.isError
            sim = val(await session.call_tool("frontier_simulate", {"model": "mechanobio", "parameters": {"duration_s": 1, "frame_count": 5}}))
            assert sim["status"] == "completed" and sim["persisted"] is False and sim["evidence_kind"] == "SimulationResult"
            assert sim["result"]["frames"]
            engineering_result = await session.call_tool("frontier_engineer", {"parameters": {
                "rho": "1.225", "cl_max": "1", "mass": "0.05", "area": "0.01", "span": "0.25", "speed": "12"}})
            if engineering_result.isError:
                # The solver is an existing optional dependency. Its adapter must fail closed
                # with a fixed error when that extra is absent, without leaking child details.
                assert "solver_unavailable" in engineering_result.content[0].text
                assert "ModuleNotFoundError" not in engineering_result.content[0].text
            else:
                engineering = val(engineering_result)
                assert engineering["result"]["status"] == "feasible" and engineering["persisted"] is False
            from engineering.formalize.cases import cantilever_request
            formal = val(await session.call_tool("frontier_formalize", {"request": cantilever_request()}))
            assert formal["persisted"] is False and formal["accepted"] is False
            from frontier.beliefs import EXAMPLE_SCENARIO
            belief = val(await session.call_tool("frontier_belief", {"scenario": EXAMPLE_SCENARIO}))
            assert belief["calibrated"] is False and belief["persisted"] is False and belief["accepted"] is False
            unauth_write = await session.call_tool("frontier_propose", {"draft": claim(store), "idempotency_key": "read-only-denied"})
            assert unauth_write.isError

    run(exercise(), timeout=120)


def test_authorized_mcp_queues_action_but_does_not_execute_or_accept(store):
    claim_draft = claim(store, id="queued-claim")

    async def exercise():
        async with session_for(store, token=TOKENS["alice"], allow_write=True) as session:
            claim_queued = val(await session.call_tool("frontier_propose", {"draft": claim_draft, "idempotency_key": "typed-claim"}))
            target = ref(claim_queued["record"])
            problem_draft = {"namespace": store.namespace, "kind": "Problem", "id": "queued-problem", "issuer": "alice",
                "source_uri": "urn:frontier:mcp-test", "payload": {
                    "title": "Test research question", "known_state": "Protocol fixture only.",
                    "question": "Can this typed draft be queued?", "problem_kind": "computational_open_question",
                    "novelty_status": "fixture", "data_access": "No external data.", "completeness": "actionable",
                    "acceptance_criteria": ["The draft is proposed"], "falsifiers": ["No proposal is returned"],
                    "next_action": "Inspect the proposal", "required_capabilities": ["local-test"],
                    "cost_stop_bounds": "No provider calls; one store submission.", "downstream_uses": ["MCP protocol test"],
                    "dependencies": [], "source": source(), "approach": "unknown", "scales": ["organism"], "context_tags": ["test"]}}
            project_draft = {"namespace": store.namespace, "kind": "Project", "id": "queued-project", "issuer": "alice",
                "source_uri": "urn:frontier:mcp-test", "payload": {"title": "Test project", "mission": "Exercise typed proposal.",
                    "source": source(), "limitations": ["Protocol fixture, not a scientific result."],
                    "scale_coverage": [{"scale": "organism", "status": "unknown", "note": "Test-only."}],
                    "members": [{"ref": target, "role": "mission", "subsystem": "test", "relationship": "informs",
                                 "applicability": "Test only.", "rationale": "Exercise exact project pin."}],
                    "requirements": [], "open_questions": []}}
            annotation_draft = {"namespace": store.namespace, "kind": "Annotation", "id": "queued-annotation", "issuer": "alice",
                "source_uri": "urn:frontier:mcp-test", "payload": {"kind": "comment", "body": "A protocol-test annotation.", "anchor": {"record": target}}}
            drafts = [claim_draft, problem_draft, evidence(store, target), project_draft, annotation_draft, action(store, target)]
            expected_kinds = {"Claim", "Problem", "Evidence", "Project", "Annotation", "Action"}
            queued_kinds = set()
            for draft in drafts:
                result = val(await session.call_tool("frontier_propose", {
                    "draft": draft, "idempotency_key": "typed-" + draft["kind"].lower()}))
                assert result["local_status"] == "proposed"
                queued_kinds.add(result["record"]["kind"])
                if draft["kind"] == "Action":
                    state = val(await session.call_tool("frontier_get", {"target": ref(result["record"])}))
                    assert state["action"]["state"] == "proposed"
            assert queued_kinds == expected_kinds
            caps = val(await session.call_tool("frontier_capabilities", {}))
            assert "review" in " ".join(caps["not_available"])
            assert "frontier_review" not in {tool["name"] for tool in caps["tools"]}

    run(exercise())


def test_mcp_stays_read_only_when_a_token_is_merely_present(store):
    async def exercise():
        async with session_for(store, token=TOKENS["alice"], allow_write=False) as session:
            assert {t.name for t in (await session.list_tools()).tools} == READ_TOOLS
            assert val(await session.call_tool("frontier_capabilities", {}))["principal"] is None
            assert (await session.call_tool("frontier_propose", {"draft": claim(store), "idempotency_key": "x"})).isError
    run(exercise())
    assert store.search(kind="Claim")["results"] == []              # nothing was written


def mcp_cli(store, *extra, token=None, dsn=None):
    return subprocess.run([sys.executable, "-m", "frontier", "mcp", "--namespace", store.namespace, "--schema", store.schema, *extra],
                          env={**server_env(store, token, dsn), "PATH": os.environ["PATH"]}, input="", capture_output=True, text=True, timeout=30)


def test_mcp_write_mode_fails_closed_without_leaking(store):
    no_token = mcp_cli(store, "--allow-write")
    assert no_token.returncode == 2 and "FRONTIER_TOKEN" in no_token.stderr
    unknown = "wrong-token-marker-XYZ-0123456789"
    r = mcp_cli(store, "--allow-write", token=unknown)
    assert r.returncode == 2 and unknown not in r.stdout + r.stderr and "write tools not enabled" in r.stderr
    store.provision("test-only-reviewer-only-token-000", "rhea", "operator-r", ["reviewer"], [store.namespace], 10)
    r = mcp_cli(store, "--allow-write", token="test-only-reviewer-only-token-000")
    assert r.returncode == 2 and "cannot write this namespace as a contributor" in r.stderr
    marker = "s3cr3t-dsn-marker"
    r = mcp_cli(store, "--allow-write", token=TOKENS["alice"], dsn=f"host=/nonexistent-socket-dir dbname=x password={marker}")
    assert r.returncode == 2 and marker not in r.stdout + r.stderr


def test_mcp_write_roundtrip_from_proposal_to_independent_acceptance(store):
    from frontier.store import Forbidden
    errlog = tempfile.TemporaryFile("w+")
    claim_draft = claim(store)

    async def exercise():
        seen = []
        async with session_for(store, token=TOKENS["alice"], allow_write=True, errlog=errlog) as s:
            tools = (await s.list_tools()).tools
            names = {t.name for t in tools}
            assert names == READ_TOOLS | WRITE_TOOLS
            assert not any(w in n for n in names for w in ("review", "accept", "dispute", "import", "provision"))
            assert {t.name for t in tools if not t.annotations.readOnlyHint} == WRITE_TOOLS
            caps = val(await s.call_tool("frontier_capabilities", {}))
            assert caps["mode"] == "write_enabled" and caps["principal"]["actor"] == "alice" and caps["principal"]["operator"] == "operator-a"
            assert set(caps["principal"]["roles"]) == {"contributor", "coordinator"}
            # proposal: stored as 'proposed', never accepted; a retry with the same key is the same response; another body under that key conflicts
            first = val(await s.call_tool("frontier_propose", {"draft": claim_draft, "idempotency_key": "mcp-claim-1"}))
            assert first["local_status"] == "proposed"
            assert val(await s.call_tool("frontier_propose", {"draft": claim_draft, "idempotency_key": "mcp-claim-1"})) == first
            other = dict(claim_draft, id="another")
            clash = await s.call_tool("frontier_propose", {"draft": other, "idempotency_key": "mcp-claim-1"})
            assert clash.isError and "conflict" in clash.content[0].text
            seen.append(clash.content[0].text)
            claim_ref = ref(first["record"])
            # the action loop: propose -> ready (coordinator) -> lease -> running -> submitted
            act = val(await s.call_tool("frontier_propose", {"draft": action(store, claim_ref), "idempotency_key": "mcp-action-1"}))
            act_ref = ref(act["record"])
            assert val(await s.call_tool("frontier_get", {"target": act_ref}))["action"]["state"] == "proposed"
            val(await s.call_tool("frontier_transition", {"target": act_ref, "state": "ready", "idempotency_key": "mcp-ready"}))
            lease = val(await s.call_tool("frontier_lease", {"target": act_ref, "seconds": 120, "idempotency_key": "mcp-lease"}))
            lid = lease["lease_id"]
            bad = await s.call_tool("frontier_transition", {"target": act_ref, "state": "running", "lease_id": "not-the-lease", "idempotency_key": "mcp-bad"})
            assert bad.isError and "forbidden" in bad.content[0].text
            val(await s.call_tool("frontier_transition", {"target": act_ref, "state": "running", "lease_id": lid, "idempotency_key": "mcp-run"}))
            val(await s.call_tool("frontier_transition", {"target": act_ref, "state": "submitted", "lease_id": lid, "idempotency_key": "mcp-sub"}))
            assert val(await s.call_tool("frontier_get", {"target": act_ref}))["action"]["state"] == "submitted"
            # acceptance is unreachable through MCP
            for state in ("accepted", "disputed", "reviewed"):
                assert (await s.call_tool("frontier_transition", {"target": act_ref, "state": state, "idempotency_key": "mcp-" + state})).isError
            return act_ref, claim_ref, lid, seen
    act_ref, claim_ref, lid, seen = run(exercise())
    # independent boundary, enforced by the store and unchanged by MCP: same operator cannot accept, a different operator can
    with pytest.raises(Forbidden):
        store.review(TOKENS["alias"], "alias-review", assessment(act_ref, "alias"))
    accepted = store.review(TOKENS["bob"], "bob-review", assessment(act_ref, "bob"))
    assert accepted["local_status"] == "accepted"

    async def after():
        async with session_for(store) as s:
            got = val(await s.call_tool("frontier_get", {"target": act_ref}))
            assert got["action"]["state"] == "accepted" and got["local_review"]["status"] == "accepted"
    run(after())
    errlog.seek(0)
    server_stderr = errlog.read()
    assert TOKENS["alice"] not in "".join(seen) + server_stderr and lid not in server_stderr


def assessment(target, reviewer):
    from conftest import assessment as make
    return make(target, reviewer)


def test_mcp_role_gates_are_the_stores(store):
    async def exercise():
        async with session_for(store, token=TOKENS["carol"], allow_write=True) as s:
            caps = val(await s.call_tool("frontier_capabilities", {}))
            assert caps["principal"]["roles"] == ["contributor"]
            proposed = val(await s.call_tool("frontier_propose", {"draft": dict(claim(store), issuer="carol"), "idempotency_key": "carol-claim"}))
            act = val(await s.call_tool("frontier_propose", {"draft": dict(action(store, ref(proposed["record"])), issuer="carol"), "idempotency_key": "carol-act"}))
            r = await s.call_tool("frontier_transition", {"target": ref(act["record"]), "state": "ready", "idempotency_key": "carol-ready"})
            assert r.isError and "forbidden" in r.content[0].text.lower()
            spoof = await s.call_tool("frontier_propose", {"draft": dict(claim(store, id="spoof"), issuer="alice"), "idempotency_key": "carol-spoof"})
            assert spoof.isError and "forbidden" in spoof.content[0].text
    run(exercise())


def test_mcp_never_takes_or_returns_credentials_and_errors_do_not_echo_input(store):
    token, marker = TOKENS["alice"], "LEAK-MARKER-9f3a"
    errlog = tempfile.TemporaryFile("w+")

    async def exercise():
        blob = []
        async with session_for(store, token=token, allow_write=True, errlog=errlog) as s:
            for t in (await s.list_tools()).tools:
                blob.append(json.dumps(t.inputSchema))
                assert not (set(t.inputSchema.get("properties", {})) & SECRET_NAMES)
            blob.append(json.dumps(val(await s.call_tool("frontier_capabilities", {}))))
            blob.append((await s.read_resource("frontier://capabilities")).contents[0].text)
            bad = dict(claim(store), payload={"title": marker, "statement": marker})          # missing required fields
            r = await s.call_tool("frontier_propose", {"draft": bad, "idempotency_key": "leak-1"})
            assert r.isError and marker not in r.content[0].text and "invalid_request" in r.content[0].text
            blob.append(r.content[0].text)
            r = await s.call_tool("frontier_get", {"target": ref(store.submit(TOKENS["alice"], "x1", claim(store))["record"]) | {"version": "0" * 64}})
            assert r.isError
            blob.append(r.content[0].text)
        return "\n".join(blob)
    text = run(exercise())
    errlog.seek(0)
    assert token not in text and token not in errlog.read()


def test_mcp_smoke_command_is_a_read_only_client_roundtrip(store):
    base = [sys.executable, "-m", "frontier", "mcp-smoke", "--namespace", store.namespace, "--schema", store.schema]
    env = {**server_env(store), "PATH": os.environ["PATH"]}
    r = subprocess.run(base, env=env, capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["ok"] and out["mode"] == "read_only" and {t["name"] for t in out["tools"]} == READ_TOOLS
    r = subprocess.run(base + ["--allow-write"], env={**env, "FRONTIER_TOKEN": TOKENS["alice"]}, capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["mode"] == "write_enabled" and out["principal"]["actor"] == "alice"
    assert TOKENS["alice"] not in r.stdout + r.stderr and {t["name"] for t in out["tools"]} == READ_TOOLS | WRITE_TOOLS
    assert store.search()["results"] == []                              # the smoke test wrote nothing
    r = subprocess.run(base + ["--allow-write"], env=env, capture_output=True, text=True, timeout=60)      # no token => fail closed
    assert r.returncode != 0
