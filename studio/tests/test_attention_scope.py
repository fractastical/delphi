"""Scope, cross-namespace references, imported Actions and the whole-database census. New file: it does not touch the older attention tests.
Fixtures are test-only inventions; PG tests use the ephemeral cluster from scripts/test_postgres.sh and skip otherwise."""
import os

import pytest

from attention import links, ledger, pg, snapshot, view
from frontier.models import Draft, POLICY, make_record, ref
from test_attention_store import NOW, claim_rec, fake_read, heads_of, prob_with
from test_attention_view import SRC, T, event, problem, rec, rec_ns, problem_ns


def claim_ns(ns, id, **kw):
    return rec_ns(ns, "Claim", id, {"title": id, "statement": "s", "context": "c", "assumptions": ["a"], "limitations": ["l"], "source": SRC, **kw})


def action_ns(ns, id, target, inputs=None, **extra):
    payload = {"target": ref(target), "title": "t", "acceptance_criteria": ["x"], "required_capabilities": [], "cost_stop_bounds": "b",
               "cache_key": {"target": target["version"], "input": "i", "code": "c", "model": "m", "environment": "e", "parameters": "p", "scope": "s", "acceptance_policy": POLICY}}
    if inputs is not None:
        payload["inputs"] = inputs
    payload.update(extra)
    d = Draft.model_construct(namespace=ns, kind="Action", id=id, issuer="importer", source_uri="urn:x", visibility="public", predecessor=None, payload=payload)
    from frontier.models import SCHEMA, digest
    body = {**{k: getattr(d, k) for k in ("namespace", "kind", "id", "issuer", "source_uri", "visibility", "predecessor", "payload")}, "schema_version": SCHEMA, "created_at": T}
    return {**body, "version": digest(body)}


# ------------------------------------------------------------------ resolution of typed references relative to what was read
def test_resolve_ref_names_where_a_reference_points_and_never_assumes():
    a1 = problem_ns("node-a", "P1")
    b1 = problem_ns("node-b", "P1")
    versions = {(r["namespace"], r["kind"], r["id"], r["version"]) for r in (a1, b1)}
    heads = {("node-a", "Problem", "P1"): a1["version"], ("node-b", "Problem", "P1"): b1["version"]}
    ok = links.resolve_ref(ref(b1), versions, heads, {"node-a", "node-b"})
    assert ok == {"status": "exact_version_present"}
    other = links.resolve_ref(ref(problem_ns("node-b", "P1", title="older")), versions, heads, {"node-a", "node-b"})
    assert other == {"status": "namespace_head_is_other_version", "head_version": b1["version"]}
    not_read = links.resolve_ref(ref(problem_ns("node-c", "P9")), versions, heads, {"node-a", "node-b"})
    assert not_read == {"status": "namespace_not_read", "namespace": "node-c"}
    assert links.resolve_ref(ref(problem_ns("node-a", "P404")), versions, heads, {"node-a", "node-b"}) == {"status": "not_found"}
    assert links.resolve_ref(ref(b1), None, None, None) == {"status": "unknown_scope"}


def test_cross_namespace_dependency_is_resolved_by_exact_version_or_flagged_out_of_scope():
    b1 = problem_ns("node-b", "P1")
    a2 = problem_ns("node-a", "P2", dependencies=[ref(b1)])           # a node-a Problem depending on a node-b Problem
    P, C = heads_of(a2, b1)
    versions = {(r["namespace"], r["kind"], r["id"], r["version"]) for r in (a2, b1)}
    hk = {("node-a", "Problem", "P2"): a2["version"], ("node-b", "Problem", "P1"): b1["version"]}
    both = links.coupled_links(P, C, all_versions=versions, heads_by_key=hk, namespaces_read={"node-a", "node-b"})
    dep = next(l for l in both["links"] if l["link_kind"] == "depends_on")
    assert dep["cross_namespace"] is True and dep["resolution"]["status"] == "exact_version_present"
    # read only node-a: the same reference is reported as pointing at a namespace this snapshot did not read
    P1, C1 = heads_of(a2)
    only_a = links.coupled_links(P1, C1, all_versions={("node-a", "Problem", "P2", a2["version"])}, heads_by_key={("node-a", "Problem", "P2"): a2["version"]},
                                 namespaces_read={"node-a"})
    dep = next(l for l in only_a["links"] if l["link_kind"] == "depends_on")
    assert dep["resolution"] == {"status": "namespace_not_read", "namespace": "node-b"}


def test_same_claim_id_in_another_namespace_is_listed_never_linked():
    ca, cb = claim_ns("node-a", "th-x"), claim_ns("node-b", "th-x", title="other node's claim")
    pa = problem_ns("node-a", "PA", original={"claim_ids": ["th-x"], "depends_on": [], "unlocks": []})
    P, C = heads_of(pa, ca, cb)
    out = links.coupled_links(P, C)
    (lk,) = [l for l in out["links"] if l["link_kind"] == "concerns_claim"]
    assert lk["to"]["namespace"] == "node-a" and [e["namespace"] for e in lk["same_id_elsewhere"]] == ["node-b"]
    assert lk["same_id_elsewhere"][0]["version"] == cb["version"] and lk["to"]["version"] == ca["version"]


# ------------------------------------------------------------------ imported Actions and Action.inputs / proposal / plans
def test_imported_action_has_no_local_lifecycle_and_inputs_are_resolved_exactly():
    c = claim_ns("node-a", "turing-x")
    absent = claim_ns("node-a", "never-read")
    act = action_ns("node-a", "orx-1", c, inputs=[ref(c), ref(absent)], proposal={"kind": "plan"}, plans=[{"step": 1}])
    imp = rec_ns("node-b", "Event", "ev-imp-1", {"event_type": "record_imported", "target": ref(act), "actor": "importer", "operator": "op-i",
                                                 "witnessed_at": "2026-10-31T18:00:00+00:00", "details": {"bundle_sha256": "a" * 64}}, created="2026-10-31T18:00:00+00:00")
    for local in (None, {act["version"]: "imported_unreviewed"}):                  # the web path passes no local states; both must agree
        (row,) = ledger.action_ledger([c, act], [{"sequence": 1, "envelope": imp}], NOW, None, local)
        assert row["state"] == "imported_no_local_lifecycle" and row["imported"] is True and row["outcome"]["final_state"] is None
        assert row["outcome"]["terminal"] is False and row["lifecycle_basis"] == "record_imported event"
        assert [i["status"] for i in row["inputs_resolution"]] == ["exact_version_present", "not_in_this_snapshot"]
        assert row["proposal"] == {"kind": "plan"} and row["plans"] == [{"step": 1}]                      # passed through verbatim, unvalidated
    # local state alone is enough (no record_imported event in the exported slice)
    (row,) = ledger.action_ledger([c, act], [], NOW, None, {act["version"]: "imported_unreviewed"})
    assert row["imported"] is True and row["state"] == "imported_no_local_lifecycle" and row["lifecycle_basis"] == "local_status only"
    # an imported version that later gets real lifecycle events reports THOSE, not the import placeholder
    ready = event("action_ready", act, actor="coord", operator="op-c", at="2026-10-31T18:30:00+00:00")
    (row,) = ledger.action_ledger([c, act], [{"sequence": 1, "envelope": imp}, {"sequence": 2, "envelope": ready}], NOW)
    assert row["state"] == "ready" and row["outcome"]["final_state"] == "ready"
    # a local Action with a lifecycle is not marked imported
    local_act = action_ns("node-b", "loc-1", c)
    evs = [{"sequence": 1, "envelope": event("action_ready", local_act)}]
    (row,) = ledger.action_ledger([c, local_act], evs, NOW)
    assert row["imported"] is False and row["state"] == "ready"


# ------------------------------------------------------------------ the scope statement
def test_snapshot_states_its_scope_and_what_it_did_not_read():
    c, pa = claim_rec("th-a"), prob_with("PA", ["th-a"])
    read = fake_read(pa, c)
    read["meta"]["scope"] = {"mode": "listed_namespaces", "namespaces_requested": ["node-a"], "namespaces_read": ["node-a"],
                             "excluded_by_scope": [{"namespace": "node-b", "kind": "Claim", "record_versions": 880}], "other_exclusions": []}
    s = snapshot.build_snapshot(read, [], NOW)
    assert "scoped to namespaces ['node-a']" in s["scope_statement"] and "NOT READ: node-b/Claim x880" in s["scope_statement"]
    assert "Nothing here is a statement about the whole database unless mode is all_namespaces" in s["scope_statement"]
    assert s["n_actions"] == 0 and s["n_claims_all"] == 1


# ------------------------------------------------------------------ PostgreSQL: two namespaces in one database, as in the live store
@pytest.fixture
def two_node_db(request):
    if not os.environ.get("FRONTIER_TEST_DSN"):
        pytest.skip("run through scripts/test_postgres.sh")
    stores = request.getfixturevalue("stores")
    a, b = stores("node-a"), stores("node-b")
    return a, b


def test_pg_scope_census_and_exclusions_with_imported_records(two_node_db):
    from conftest import TOKENS, claim
    a, b = two_node_db
    rc = a.submit(TOKENS["alice"], "c1", claim(a, "th-a"))["record"]
    bundle = a.export_bundle([ref(rc)])
    b.import_bundle(TOKENS["alice"], "imp1", bundle)                           # node-b now holds a node-a record, as in the live database
    mine = b.submit(TOKENS["alice"], "c2", claim(b, "th-b"))["record"]
    scoped = pg.read_store(b.dsn, b.namespace, schema=b.schema)
    assert {r["namespace"] for r in scoped["records"]} == {"node-b"} and rc["version"] not in {r["version"] for r in scoped["records"]}
    sc = scoped["meta"]["scope"]
    assert sc["mode"] == "listed_namespaces" and sc["namespaces_read"] == ["node-b"]
    assert sc["excluded_by_scope"] == [{"namespace": "node-a", "kind": "Claim", "record_versions": 1}]
    # the import event belongs to node-b but TARGETS the node-a record: it is read, and it is not evidence of an Action
    assert any(e["envelope"]["payload"]["event_type"] == "record_imported" and e["envelope"]["payload"]["target"]["namespace"] == "node-a" for e in scoped["events"])
    full = pg.read_store(b.dsn, None, schema=b.schema)
    assert full["meta"]["scope"]["mode"] == "all_namespaces" and full["meta"]["scope"]["excluded_by_scope"] == []
    assert {r["namespace"] for r in full["records"]} == {"node-a", "node-b"} and full["local_status"][rc["version"]] == "imported_unreviewed"
    assert full["local_status"][mine["version"]] == "proposed"
    cen = pg.census(b.dsn, b.schema)
    assert cen["namespaces"] == ["node-a", "node-b"] and cen["total_record_versions"] == len(full["records"])
    assert {(e["event_namespace"], e["event_type"], e["target_namespace"]) for e in cen["events_by_namespace_and_target"]} >= {("node-b", "record_imported", "node-a"), ("node-b", "record_proposed", "node-b")}
    s = snapshot.build_snapshot(scoped, [], NOW)
    assert "node-a/Claim x1" in s["scope_statement"]
