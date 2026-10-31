"""Graph projection and reuse measurement. Hand-worked expectations are explained beside each assertion.
PG tests use the ephemeral cluster from scripts/test_postgres.sh and never touch the live service. Fixtures are test-only inventions."""
import ast
import json
from pathlib import Path

import pytest

from frontier import graph
from frontier.models import POLICY, ref
from frontier.store import FrontierError, Missing
from conftest import TOKENS, claim, source

A = TOKENS["alice"]


def rec_ref(r):
    return {k: r[k] for k in ("namespace", "kind", "id", "version")}


def submit(store, key, draft):
    return store.submit(A, key, draft)["record"]


def ev_draft(store, target, id="ev", relation="supports", produced_by=None, artifacts=None, **payload_changes):
    p = {"target": target, "evidence_kind": "simulated", "source": source(), "created_time": {"value": None, "basis": "unknown"},
         "retrieved_time": {"value": "2026-10-31T15:00:00+00:00", "basis": "declared"}, "method": f"method {id}", "context": "fixture", "assumptions": ["a"],
         "provenance": {"p": 1}, "source_dependence": {"group": "g"}, "uncertainty": "u", "limitations": ["fixture"], "relation": relation}
    if produced_by:
        p["produced_by"] = produced_by
    if artifacts:
        p["artifacts"] = artifacts
    p.update(payload_changes)
    return {"namespace": store.namespace, "kind": "Evidence", "id": id, "issuer": "alice", "source_uri": "urn:test", "payload": p}


def action_draft(store, target, id="act", inputs=()):
    ck = {"target": target["version"], "input": "i", "code": "c", "model": "m", "environment": "e", "parameters": "p", "scope": "s", "acceptance_policy": POLICY}
    return {"namespace": store.namespace, "kind": "Action", "id": id, "issuer": "alice", "source_uri": "urn:test",
            "payload": {"target": target, "title": f"action {id}", "acceptance_criteria": ["x"], "required_capabilities": [], "cost_stop_bounds": "b", "cache_key": ck,
                        "inputs": list(inputs)}}


def art(sha, role="output", title="file"):
    return {"title": title, "uri": "urn:sha256:" + sha, "sha256": sha, "byte_size": 3, "media_type": "text/plain", "role": role, "availability": "referenced", "license": None}


def by_kind(g, kind):
    return [e for e in g["edges"] if e["kind"] == kind]


# ------------------------------------------------------------------ real neighborhoods from stored records
def test_neighborhood_has_typed_labelled_edges_with_origin(store):
    c = submit(store, "c", claim(store, "c1"))
    a = submit(store, "a", action_draft(store, rec_ref(c), "act1", inputs=[rec_ref(c)]))
    e = submit(store, "e", ev_draft(store, rec_ref(c), "ev1", relation="supports", produced_by=rec_ref(a), artifacts=[art("a" * 64, "output", "result.json"), art("b" * 64, "code", "run.py")]))
    g = graph.view(store, rec_ref(c), depth=1, limit=50)
    ids = {n["ref"]["id"] for n in g["nodes"] if n["ref"]}
    assert ids == {"c1", "act1", "ev1"} and g["schema"] == "frontier-graph-0.1" and g["truncated"] is False
    sup = by_kind(g, "supports")[0]
    assert sup["from"].endswith("Evidence/ev1@" + e["version"]) and sup["to"].endswith("Claim/c1@" + c["version"])
    assert sup["asserted"] is True and sup["origin"] == {"basis": "explicit_reference", "field": "payload.target", "declared_by": "alice"} and "declared" in sup["label"]
    assert {k["kind"] for k in g["edges"] if k["from"].startswith("node-a/Action")} == {"targets", "uses"}      # Action -> Claim twice, as target and as input: two edges
    g0 = graph.view(store, rec_ref(c), depth=0, limit=50)
    assert [n["ref"]["id"] for n in g0["nodes"]] == ["c1"] and g0["edges"] == []                           # depth 0 is the record alone
    assert len(by_kind(g, "has_artifact")) == 2 and len(by_kind(g, "produced_by")) == 1                     # artifacts ride with their owning Evidence
    assert {n["artifact_sha256"] for n in g["nodes"] if n["type"] == "Artifact"} == {"a" * 64, "b" * 64}
    n_ev = next(n for n in g["nodes"] if n["ref"] and n["ref"]["id"] == "ev1")
    assert n_ev["local_status"] == "proposed" and n_ev["is_head"] is True and n_ev["attrs"]["evidence_kind"] == "simulated" and n_ev["distance"] == 1
    assert g["counts"]["by_edge_kind"]["has_artifact"] == 2 and g["counts"]["asserted_edges"] == 1


def test_versions_and_namespaces_are_never_collapsed(store):
    c1 = submit(store, "c1", claim(store, "cc"))
    d2 = claim(store, "cc"); d2["predecessor"] = c1["version"]; d2["payload"] = {**d2["payload"], "title": "second version"}
    c2 = submit(store, "c2", d2)
    g = graph.view(store, rec_ref(c2), depth=1, limit=20)
    assert [n["ref"]["version"] for n in sorted(g["nodes"], key=lambda n: n["distance"])] == [c2["version"], c1["version"]]
    pred = by_kind(g, "predecessor")[0]
    assert pred["from"].endswith("@" + c2["version"]) and pred["to"].endswith("@" + c1["version"])
    heads = {n["ref"]["version"]: n["is_head"] for n in g["nodes"]}
    assert heads == {c2["version"]: True, c1["version"]: False}


def test_pure_projection_keeps_equal_ids_in_different_namespaces_apart():
    def mk(ns):
        body = {"namespace": ns, "kind": "Claim", "id": "same", "issuer": "i", "source_uri": "u", "visibility": "public", "predecessor": None, "payload": {"title": ns}}
        return {**body, "created_at": "t", "version": graph.digest(body)}
    a, b = mk("node-a"), mk("node-b")
    out = graph.project({a["version"]: a, b["version"]: b}, {}, set(), {}, public_present={a["version"], b["version"]}, budget=10)
    assert sorted(n["id"] for n in out["nodes"]) == [f"node-a/Claim/same@{a['version']}", f"node-b/Claim/same@{b['version']}"]


def test_unknown_record_kind_is_handled_generically_without_duplicating_known_fields():
    def mk(kind, id_, payload):
        body = {"namespace": "n", "kind": kind, "id": id_, "issuer": "i", "source_uri": "u", "visibility": "public", "predecessor": None, "payload": payload}
        return {**body, "created_at": "t", "version": graph.digest(body)}
    c = mk("Claim", "c", {"title": "claim"})
    proj = mk("Project", "p1", {"name": "A project", "members": [rec_ref(c)], "target": rec_ref(c)})       # a kind this module has never heard of
    out = graph.project({c["version"]: c, proj["version"]: proj}, {}, set(), {}, public_present={c["version"], proj["version"]}, budget=10)
    kinds = sorted((e["kind"], e["origin"]["field"]) for e in out["edges"])
    assert kinds == [("refers_to", "payload.members[0]"), ("targets", "payload.target")]                   # the known 'target' is not also emitted as refers_to
    assert any(n["type"] == "Project" and n["title"] == "A project" for n in out["nodes"])


def test_tentative_claim_id_edges_are_marked_and_never_called_exact(store):
    c = submit(store, "c", claim(store, "th-x"))
    pd = {"namespace": store.namespace, "kind": "Problem", "id": "P1", "issuer": "alice", "source_uri": "urn:t", "payload": {
        "title": "P", "known_state": "k", "question": "q", "problem_kind": "project_gap", "novelty_status": "n", "data_access": "d", "completeness": "recorded",
        "required_capabilities": [], "downstream_uses": [], "source": source(), "original": {"claim_ids": ["th-x"]}, "scales": ["tissue"]}}
    p = submit(store, "p", pd)
    g = graph.view(store, rec_ref(p), depth=1, limit=20)
    t = by_kind(g, "names_claim_id")
    assert len(t) == 1 and t[0]["tentative"] is True and t[0]["asserted"] is False and t[0]["origin"]["basis"] == "source_field_untyped"
    assert t[0]["to"].endswith("Claim/th-x@" + c["version"]) and next(n for n in g["nodes"] if n["type"] == "Problem")["scale"] == ["tissue"]
    assert g["counts"]["tentative_edges"] == 1


def test_artifact_ownership_one_node_per_digest_one_edge_per_owner(store):
    c = submit(store, "c", claim(store, "c1"))
    sha = "c" * 64
    submit(store, "e1", ev_draft(store, rec_ref(c), "ev1", artifacts=[art(sha, "output", "from ev1")]))
    submit(store, "e2", ev_draft(store, rec_ref(c), "ev2", artifacts=[art(sha, "input", "from ev2")]))
    g = graph.view(store, rec_ref(c), depth=2, limit=50)
    nodes = [n for n in g["nodes"] if n["type"] == "Artifact"]
    edges = by_kind(g, "has_artifact")
    assert len(nodes) == 1 and len(edges) == 2 and {e["role"] for e in edges} == {"output", "input"} and {e["use_title"] for e in edges} == {"from ev1", "from ev2"}
    assert nodes[0]["attrs"]["bytes_verified"] is False and nodes[0]["attrs"]["fetched"] is False and all(e["origin"]["basis"] == "derived_ownership" for e in edges)


# ------------------------------------------------------------------ private records never leak
def snapshot(g):
    return json.dumps(g, sort_keys=True)


def test_private_records_do_not_leak_through_nodes_edges_counts_or_traversal(store):
    c = submit(store, "c", claim(store, "c1"))
    pub_ev = submit(store, "e", ev_draft(store, rec_ref(c), "pub-ev"))
    before_nb = snapshot(graph.view(store, rec_ref(c), depth=3, limit=100))
    before_ov = snapshot(graph.view(store))
    priv_ev = submit(store, "pe", {**ev_draft(store, rec_ref(c), "priv-ev", artifacts=[art("d" * 64, "output", "SECRET.csv")]), "visibility": "private"})
    priv_claim = submit(store, "pc", {**claim(store, "priv-claim"), "visibility": "private"})
    submit(store, "pe2", {**ev_draft(store, rec_ref(priv_claim), "priv-ev2"), "visibility": "private"})
    after_nb = snapshot(graph.view(store, rec_ref(c), depth=3, limit=100))
    after_ov = snapshot(graph.view(store))
    assert before_nb == after_nb and before_ov == after_ov                                                   # byte-identical: counts, edges, labels, traversal
    assert "priv-" not in after_nb + after_ov and "SECRET" not in after_nb + after_ov and ("d" * 64) not in after_nb + after_ov
    with pytest.raises(Missing) as private:
        graph.view(store, rec_ref(priv_ev))
    with pytest.raises(Missing) as absent:
        graph.view(store, {**rec_ref(priv_ev), "version": "0" * 64})
    assert str(private.value) == str(absent.value) == "No such public record version"                         # a private record and a missing one answer identically
    assert graph.view(store)["counts"]["public_records_available"] == 2                                      # claim + public evidence only


def test_references_to_unavailable_records_are_indistinguishable_placeholders():
    def mk(kind, id_, payload):
        body = {"namespace": "n", "kind": kind, "id": id_, "issuer": "i", "source_uri": "u", "visibility": "public", "predecessor": None, "payload": payload}
        return {**body, "created_at": "t", "version": graph.digest(body)}
    ghost = {"namespace": "n", "kind": "Claim", "id": "ghost", "version": "9" * 64}
    e = mk("Evidence", "e", {"target": ghost, "evidence_kind": "simulated", "relation": "refutes"})
    out = graph.project({e["version"]: e}, {}, set(), {}, public_present={e["version"]}, budget=10)
    ph = [n for n in out["nodes"] if n["type"] == "unresolved"]
    assert len(ph) == 1 and ph[0]["ref"] == ghost and ph[0]["title"] == "not available in this public view" and out["unresolved_references"] == 1
    edge = out["edges"][0]
    assert edge["kind"] == "refutes" and edge["origin"]["basis"] == "unresolved_reference"
    # the same input whether the target is private or never existed: the projection cannot tell, so neither can a reader


# ------------------------------------------------------------------ bounds
def test_overview_and_neighborhood_are_bounded_with_explicit_truncation(store):
    c = submit(store, "c", claim(store, "hub"))
    for i in range(6):
        submit(store, f"e{i}", ev_draft(store, rec_ref(c), f"ev{i}"))
    ov = graph.view(store, limit=3)
    assert len(ov["nodes"]) <= 3 and ov["truncated"] is True and ov["counts"]["public_records_available"] == 7 and ov["scope"]["mode"] == "overview"
    nb = graph.view(store, rec_ref(c), depth=1, limit=4)
    assert len(nb["nodes"]) == 4 and nb["truncated"] is True
    full = graph.view(store, rec_ref(c), depth=1, limit=50)
    assert len(full["nodes"]) == 7 and full["truncated"] is False
    # structure first: with a limit that cannot hold everything, the overview keeps connected records before isolated ones
    submit(store, "iso", claim(store, "isolated"))
    ov2 = graph.view(store, limit=4)
    assert "hub" in {n["ref"]["id"] for n in ov2["nodes"]}
    for bad in ({"depth": -1}, {"depth": graph.MAX_DEPTH + 1}, {"limit": 0}, {"limit": graph.MAX_LIMIT + 1}, {"depth": True}):
        with pytest.raises(FrontierError):
            graph.view(store, **bad)
    with pytest.raises(FrontierError):
        graph.view(store, {"namespace": store.namespace, "kind": "Claim", "id": "hub"})                      # not an exact version
    with pytest.raises(FrontierError, match="events are a log"):
        graph.view(store, {"namespace": store.namespace, "kind": "Event", "id": "x", "version": "1" * 64})


def test_view_is_read_only_and_never_fetches_uris(store):
    submit(store, "c", claim(store, "c1"))
    def counts():
        with store.connection() as cx:
            return [cx.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in ("record_versions", "local_states", "typed_edges", "events", "heads", "write_receipts", "idempotency")]
    before = counts()
    graph.view(store); graph.reuse_report(store)
    assert counts() == before
    tree = ast.parse(Path(graph.__file__).read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and (m.split(".")[0] in ("urllib", "requests", "socket", "subprocess", "http", "httpx") or m.startswith("psycopg")) for m in imported)


# ------------------------------------------------------------------ reuse measurement
def _mk(kind, id_, issuer, payload=None, ns="n"):
    body = {"namespace": ns, "kind": kind, "id": id_, "issuer": issuer, "source_uri": "u", "visibility": "public", "predecessor": None, "payload": payload or {}}
    return {**body, "created_at": "t", "version": graph.digest(body)}


def _ev(rec, etype, op):
    return {"kind": "Event", "payload": {"event_type": etype, "target": {"version": rec["version"]}, "actor": "x", "operator": op}}


def test_reuse_measurement_hand_worked():
    X, Y, Z = (_mk("Claim", n, "agent-c") for n in "XYZ")
    r = lambda c: rec_ref(c)
    A1 = _mk("Action", "A1", "agent-a", {"inputs": [r(X), r(Y)]})
    A2 = _mk("Action", "A2", "agent-b", {"inputs": [r(X)]})
    A3 = _mk("Action", "A3", "agent-a", {"inputs": [r(Y)]})
    A4 = _mk("Action", "A4", "agent-a", {"inputs": [r(Z)]})
    W = _mk("Evidence", "W", "agent-a", {"produced_by": r(A1), "target": r(X), "artifacts": [art("1" * 64), art("2" * 64)]})
    V = _mk("Evidence", "V", "agent-b", {"produced_by": r(A2), "target": r(X), "artifacts": [art("1" * 64)]})
    recs = [X, Y, Z, A1, A2, A3, A4, W, V]
    events = [_ev(A1, "record_proposed", "op1"), _ev(A1, "action_running", "op-exec"), _ev(A2, "record_imported", "op-imp"),
              _ev(A3, "record_proposed", "op2"), _ev(A4, "record_proposed", "op1"), _ev(A4, "action_accepted", "op-exec")]
    subs = {A1["version"]: {"operator": "op1"}, A2["version"]: {"operator": "op-imp"}, A3["version"]: {"operator": "op2"}, A4["version"]: {"operator": "op1"},
            X["version"]: {"operator": "op1"}, Y["version"]: {"operator": "op-imp"}, Z["version"]: {"operator": "op1"}}
    status = {A2["version"]: "imported_unreviewed"}
    m = graph.measure_reuse(recs, events, subs, status)["metrics"]
    # edges: (A1,X) (A1,Y) (A2,X) (A3,Y) (A4,Z) = 5. Users: X={A1,A2}, Y={A1,A3}, Z={A4}  -> 2 of 3 inputs used by >= 2 distinct Actions
    assert (m["declared_input_reuse_all_actions"]["numerator"], m["declared_input_reuse_all_actions"]["denominator"]) == (2, 3)
    # imported subset = A2 only: X used once -> 0 of 1 (a declaration, not executed work)
    assert (m["declared_input_reuse_imported_actions"]["numerator"], m["declared_input_reuse_imported_actions"]["denominator"]) == (0, 1)
    # executed subset = A1 (running) and A4 (accepted): X, Y by A1 only, Z by A4 only -> 0 of 3. Reuse is DECLARED across 3 Actions but executed in none twice.
    assert (m["executed_input_reuse_locally_executed_actions"]["numerator"], m["executed_input_reuse_locally_executed_actions"]["denominator"]) == (0, 3)
    # operators known on both ends: (A1 op1,X op1) same, (A1,Y op-imp) diff, (A2 op-imp,X op1) diff, (A3 op2,Y op-imp) diff, (A4 op1,Z op1) same -> 3 of 5
    assert (m["cross_operator_reuse_edges"]["numerator"], m["cross_operator_reuse_edges"]["denominator"]) == (3, 5)
    assert (m["evidence_from_locally_executed_actions"]["numerator"], m["evidence_from_locally_executed_actions"]["denominator"]) == (1, 2)       # W via A1
    assert (m["evidence_from_imported_actions"]["numerator"], m["evidence_from_imported_actions"]["denominator"]) == (1, 2)                       # V via A2
    assert (m["identical_artifact_bytes_in_multiple_evidence"]["numerator"], m["identical_artifact_bytes_in_multiple_evidence"]["denominator"]) == (1, 2)   # sha 1 in W and V; sha 2 only in W
    out = graph.measure_reuse(recs, events, subs, status)
    pop = out["populations"]
    assert pop["actions"] == 4 and pop["actions_imported"] == 1 and pop["actions_locally_executed"] == 2 and pop["input_edges"] == 5
    assert pop["operators_on_actions"] == ["op-imp", "op1", "op2"] and pop["agents_on_actions"] == ["agent-a", "agent-b"]      # 3 operators vs 2 agents, counted apart
    assert pop["operators_who_executed"] == ["op-exec"]
    assert len(out["per_edge_trace"]) == 5 and {t["action_origin"] for t in out["per_edge_trace"]} == {"locally_executed", "imported_declaration", "proposed_only"}
    assert "time saved" in out["not_measured"] and "any swarm or scaling advantage (no controlled comparison exists)" in out["not_measured"]


def test_versions_of_one_action_or_evidence_record_are_not_distinct_users():
    X = _mk("Claim", "X", "a")
    A_v1 = _mk("Action", "A", "a", {"inputs": [rec_ref(X)], "title": "v1"})
    A_v2 = _mk("Action", "A", "a", {"inputs": [rec_ref(X)], "title": "v2"})                      # same record id, a new version, same input
    B = _mk("Action", "B", "a", {"inputs": [rec_ref(X)]})
    E1 = _mk("Evidence", "E", "a", {"artifacts": [art("7" * 64)], "note": 1})
    E2 = _mk("Evidence", "E", "a", {"artifacts": [art("7" * 64)], "note": 2})                    # a later version of the same Evidence re-declaring the same file
    m = graph.measure_reuse([X, A_v1, A_v2], [], {}, {})["metrics"]
    assert (m["declared_input_reuse_all_actions"]["numerator"], m["declared_input_reuse_all_actions"]["denominator"]) == (0, 1)      # one Action record, two versions: not reuse
    m = graph.measure_reuse([X, A_v1, B], [], {}, {})["metrics"]
    assert (m["declared_input_reuse_all_actions"]["numerator"], m["declared_input_reuse_all_actions"]["denominator"]) == (1, 1)      # two distinct records: reuse
    assert graph.measure_reuse([E1, E2], [], {}, {})["metrics"]["identical_artifact_bytes_in_multiple_evidence"]["numerator"] == 0


def test_import_event_alone_never_counts_as_execution_and_empty_input_is_zero_over_zero():
    X = _mk("Claim", "X", "a")
    A = _mk("Action", "A", "a", {"inputs": [rec_ref(X)]})
    m = graph.measure_reuse([X, A], [_ev(A, "record_imported", "imp")], {}, {A["version"]: "imported_unreviewed"})
    assert m["populations"]["actions_locally_executed"] == 0 and m["populations"]["actions_imported"] == 1
    assert m["metrics"]["executed_input_reuse_locally_executed_actions"]["denominator"] == 0
    empty = graph.measure_reuse([], [], {}, {})["metrics"]
    assert empty["declared_input_reuse_all_actions"]["numerator"] == 0 == empty["declared_input_reuse_all_actions"]["denominator"]


def test_reuse_report_on_a_real_store_separates_declared_from_executed_and_operators_from_agents(stores):
    s = stores("node-a")
    c = submit(s, "c", claim(s, "c1"))
    a1 = submit(s, "a1", action_draft(s, rec_ref(c), "act1", inputs=[rec_ref(c)]))
    submit(s, "a2", action_draft(s, rec_ref(c), "act2", inputs=[rec_ref(c)]))
    rep = graph.reuse_report(s)
    m = rep["metrics"]["declared_input_reuse_all_actions"]
    assert (m["numerator"], m["denominator"]) == (1, 1)                                                  # one Claim pinned as input by two distinct Actions
    assert rep["metrics"]["executed_input_reuse_locally_executed_actions"]["denominator"] == 0           # nothing has run yet: proposed only
    assert {t["action_origin"] for t in rep["per_edge_trace"]} == {"proposed_only"}
    # run act1 for real: ready (coordinator alice), lease (carol), running (carol)
    s.transition(A, "ready", ref(a1), "ready")
    lease = s.lease(TOKENS["carol"], "lease", ref(a1), 60)
    s.transition(TOKENS["carol"], "run", ref(a1), "running", lease_id=lease["lease_id"])
    rep = graph.reuse_report(s)
    ex = rep["metrics"]["executed_input_reuse_locally_executed_actions"]
    assert (ex["numerator"], ex["denominator"]) == (0, 1)                                                # executed once: declared reuse is not executed reuse
    assert rep["populations"]["actions_locally_executed"] == 1 and rep["populations"]["operators_who_executed"] == ["operator-c"]
    assert rep["populations"]["operators_on_actions"] == ["operator-a"] and rep["populations"]["agents_on_actions"] == ["alice"]
    assert {t["action_origin"] for t in rep["per_edge_trace"]} == {"locally_executed", "proposed_only"}
    assert rep["scope"]["namespaces"] == ["node-a"] and rep["scope"]["records_read"] == 3


def test_every_query_runs_in_a_read_only_transaction(store):
    submit(store, "c", claim(store, "c1"))
    seen = []
    real = store.connection

    from contextlib import contextmanager

    @contextmanager
    def spy():
        with real() as cx:
            orig = cx.execute

            def logged(q, *a, **k):
                seen.append(str(q))
                return orig(q, *a, **k)
            try:
                cx.execute = logged
            except AttributeError:
                pass
            yield cx
    store.connection = spy
    try:
        graph.view(store)
        graph.reuse_report(store)
    finally:
        store.connection = real
    assert seen and sum(1 for q in seen if q.strip().startswith("SET TRANSACTION READ ONLY")) >= 2
    assert not any(q.strip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER") for q in seen)


def test_public_neighbors_outside_the_view_are_counted_not_made_unresolved(store):
    c = submit(store, "c", claim(store, "c1"))
    e = submit(store, "e", ev_draft(store, rec_ref(c), "ev1"))
    g = graph.view(store, rec_ref(e), depth=0, limit=10)                                                   # the Claim is public and present, just not in this view
    assert [n["type"] for n in g["nodes"]] == ["Evidence"] and g["edges"] == []
    assert g["counts"]["edges_omitted_outside_view"] == 1 and g["counts"]["unresolved_references"] == 0


def test_overview_reports_truncation_when_public_history_is_not_shown(store):
    c1 = submit(store, "c1", claim(store, "cc"))
    d2 = claim(store, "cc"); d2["predecessor"] = c1["version"]; d2["payload"] = {**d2["payload"], "title": "second"}
    submit(store, "c2", d2)
    g = graph.view(store, limit=5)
    assert len(g["nodes"]) == 1 and g["counts"]["public_records_available"] == 2 and g["truncated"] is True    # the older version exists publicly but the overview shows heads


def test_a_ref_must_match_the_stored_record_exactly(store):
    c = submit(store, "c", claim(store, "c1"))
    for change in ({"id": "other"}, {"namespace": "node-b"}, {"kind": "Problem"}):
        with pytest.raises(Missing):
            graph.view(store, {**rec_ref(c), **change})
