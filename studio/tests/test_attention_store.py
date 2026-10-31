"""Store adapter, source-field links, actual snapshot and demo annotations.
Fixtures are test-only inventions. PG tests use the ephemeral cluster from scripts/test_postgres.sh and skip when it is not set."""
import inspect
import os
import re
from pathlib import Path

import psycopg
import pytest

from attention import annotation as A, demo, links, pg, snapshot, vocab
from frontier.models import Draft, make_record, ref
from test_attention_view import NS, SRC, T, action, annot, assessment, event, problem, rec

NOW = "2026-10-31T19:00:00+00:00"


def claim_rec(id, **kw):
    return rec("Claim", id, {"title": id, "statement": "s", "context": "c", "assumptions": ["a"], "limitations": ["l"], "source": SRC,
                             "prior_review": {"category": "checked", "finding": "f"}, **kw})


def prob_with(id, claim_ids=(), depends=(), unlocks=(), **kw):
    p = problem(id, **kw)
    p["payload"].setdefault("original", {})
    p["payload"]["original"].update(claim_ids=list(claim_ids), depends_on=[d["id"] for d in depends], unlocks=list(unlocks))
    p["payload"]["dependencies"] = list(depends)
    return p


def heads_of(*recs):
    from attention.records import heads
    h = heads(list(recs))
    return ({(k[0], k[2]): v["head"] for k, v in h.items() if k[1] == "Problem"}, {(k[0], k[2]): v["head"] for k, v in h.items() if k[1] == "Claim"})


# ------------------------------------------------------------------ links from source fields only
def test_links_come_from_source_fields_and_roles_are_not_inferred():
    c1, c2 = claim_rec("th-a"), claim_rec("th-b")
    pa = prob_with("PA", ["th-a", "th-b"], unlocks=["prose use"])
    pb = prob_with("PB", ["th-a"], depends=[ref(pa)])
    P, C = heads_of(pa, pb, c1, c2)
    out = links.coupled_links(P, C)
    kinds = sorted((l["link_kind"], l["from"]["id"], (l["to"] or {}).get("id")) for l in out["links"])
    assert kinds == [("concerns_claim", "PA", "th-a"), ("concerns_claim", "PA", "th-b"), ("concerns_claim", "PB", "th-a"),
                     ("declared_downstream", "PA", None), ("depends_on", "PB", "PA")]
    assert out["couplings"] == [{"claim": ref(c1), "problems": [f"{NS}/Problem/PA", f"{NS}/Problem/PB"], "via": "shared payload.original.claim_ids"}]
    assert all(l["role"]["value"] is None and "not inferred" in l["role"]["source"] for l in out["links"])
    dl = next(l for l in out["links"] if l["link_kind"] == "declared_downstream")
    assert dl["typed"] is False and dl["to"] is None and dl["text"] == "prose use"
    dep = next(l for l in out["links"] if l["link_kind"] == "depends_on")
    assert dep["pinned_to_current_head"] is True


def test_claim_ids_resolve_only_within_the_problems_own_namespace():
    from test_attention_view import rec_ns, problem_ns
    claim_b = rec_ns("node-b", "Claim", "th-x", {"title": "t", "statement": "s", "context": "c", "assumptions": ["a"], "limitations": ["l"], "source": SRC})
    pa = problem_ns("node-a", "PA", original={"claim_ids": ["th-x"], "depends_on": [], "unlocks": []})
    P, C = heads_of(pa, claim_b)
    out = links.coupled_links(P, C)
    assert out["links"] == [] and "th-x" in out["issues"][0]["issue"]                  # same id exists on node-b, but that is a different record
    pb = problem_ns("node-b", "PB", original={"claim_ids": ["th-x"], "depends_on": [], "unlocks": []})
    P, C = heads_of(pb, claim_b)
    assert [(l["from"]["namespace"], l["to"]["namespace"]) for l in links.coupled_links(P, C)["links"]] == [("node-b", "node-b")]


def test_role_is_taken_from_a_store_approach_field_only_when_it_says_so():
    c1 = claim_rec("th-a")
    for approach, expect in (("theory_fit", "theory_fit"), ("design_goal", "design_goal"), ("top_down", None)):
        p = prob_with("PA", ["th-a"]); p["payload"]["approach"] = approach
        P, C = heads_of(p, c1)
        assert links.coupled_links(P, C)["links"][0]["role"]["value"] == expect


def test_unresolved_claim_ids_and_dependency_mismatches_are_reported_not_dropped():
    pa = prob_with("PA")
    pb = prob_with("PB", ["ghost"], depends=[ref(pa)])
    pb["payload"]["original"]["depends_on"] = []                       # source says none; the store-typed list says PA
    P, C = heads_of(pa, pb)
    out = links.coupled_links(P, C)
    msgs = " | ".join(i["issue"] for i in out["issues"])
    assert "ghost" in msgs and "differ from original.depends_on" in msgs
    stale = prob_with("PB", depends=[ref(problem("PA", title="older version"))])
    P, C = heads_of(pa, stale)
    assert next(l for l in links.coupled_links(P, C)["links"] if l["link_kind"] == "depends_on")["pinned_to_current_head"] is False


# ------------------------------------------------------------------ snapshot over a fake read
def fake_read(*records, events=(), status=None):
    status = status or {r["version"]: "proposed" for r in records}
    return {"records": list(records), "events": list(events), "local_status": status, "typed_edges": [], "heads": {},
            "meta": {"source": {"namespace": NS}, "read_at_utc": NOW, "read_only": True, "records": len(records), "events": len(events),
                     "excluded_private": 0, "integrity_failures": [], "content_sha256": "0" * 64}}


def test_actual_snapshot_rates_nothing_and_says_what_is_missing():
    c1 = claim_rec("th-a")
    pa = prob_with("PA", ["th-a"], unlocks=["prose"])
    pb = prob_with("PB", ["th-a"], depends=[ref(pa)])
    s = snapshot.build_snapshot(fake_read(pa, pb, c1), [], NOW)
    assert s["snapshot_kind"] == "actual" and s["local_status_counts"] == {"proposed": 3}
    row = next(r for r in s["problems"] if r["ref"]["id"] == "PA")
    assert row["local_status"] == {"vocabulary": "frontier-store", "field": "local_status", "value": "proposed", "recognized": True}
    fields = {m["field"] for m in row["missing_priorities"]}
    # recorded Problem: all four actionability fields absent except none given -> falsifiers, acceptance, next_action, cost bounds are empty in this fixture
    assert {"store.Problem.acceptance_criteria", "store.Problem.falsifiers", "store.Problem.next_action", "store.Problem.cost_stop_bounds"} <= fields
    assert "annotation (pinned to this Problem version)" in fields and "store.Problem.approach (theory_fit | design_goal)" in fields
    assert row["utility"]["status"] == "unknown" and s["rankings"]["declared_evpi"]["tiers"] == [] and len(s["rankings"]["declared_evpi"]["unplaced"]) == 2
    # the only ordering with inputs: store-typed dependencies, inverted. PA has 1 dependent, PB 0.
    assert [t["ids"] for t in s["rankings"]["derived_dependents"]["tiers"]] == [[f"{NS}/Problem/PA"], [f"{NS}/Problem/PB"]]
    claim_row = s["claims"][0]
    assert claim_row["concerned_by_problems"] == [f"{NS}/Problem/PA", f"{NS}/Problem/PB"] and claim_row["assessment"]["latest_assertion"] is None
    assert claim_row["source_review_verbatim"]["category"] == "checked" and "viable or true" in s["does_not_imply"]
    assert s["missing_priorities_summary"]["by_field"]["annotation (pinned to this Problem version)"] == 2


def test_assessment_changes_the_assertion_column_but_no_ranking():
    c1, pa = claim_rec("th-a"), prob_with("PA", ["th-a"])
    base = snapshot.build_snapshot(fake_read(pa, c1), [], NOW)
    asm = assessment(c1, "accepted")
    with_asm = snapshot.build_snapshot(fake_read(pa, c1, asm), [], NOW)
    assert base["rankings"] == with_asm["rankings"]
    a = with_asm["claims"][0]["assessment"]
    assert a["latest_assertion"]["decision"]["value"] == "accepted" and base["claims"][0]["assessment"]["latest_assertion"] is None
    # local_status in fake_read marks every record 'proposed': the assertion is shown, but the target is NOT locally accepted
    assert a["local_acceptance"]["provided"] is True and a["local_acceptance"]["target_local_status"] == "proposed" and a["local_acceptance"]["is_local_review_outcome"] is False


def test_claim_assessment_on_an_older_version_is_not_shown_as_current():
    c_old, pa = claim_rec("th-a"), prob_with("PA", ["th-a"])
    c_new = claim_rec("th-a", statement="changed")                      # different payload -> different version, same id
    older = assessment(c_old, "accepted")
    s = snapshot.build_snapshot(fake_read(pa, c_new, older), [], NOW)
    a = s["claims"][0]["assessment"]
    assert a["latest_assertion"] is None and a["assessments_on_older_versions"] == 1


def test_local_status_vocabulary_matches_schema_sql():
    sql = (Path(__file__).resolve().parent.parent / "frontier" / "schema.sql").read_text()
    m = re.search(r"status TEXT NOT NULL CHECK \(status IN \(([^)]*)\)\)", sql)
    assert tuple(x.strip().strip("'") for x in m.group(1).split(",")) == vocab.STORE["local_status"]


# ------------------------------------------------------------------ demo annotations (authored, separate, deterministic)
def test_demo_annotations_are_deterministic_pinned_and_invent_no_numbers():
    c1 = claim_rec("turing-ddi")
    f3 = prob_with("F003", ["turing-ddi"], unlocks=["An honest simulation explorer"])
    f1 = prob_with("F001", [], unlocks=["Scoped reuse of the Price derivation"])
    c2 = claim_rec("fisher-ftns")
    recs = [f3, f1, c1, c2]
    assert demo.DEMO_CREATED == "2026-10-31T00:00:00+00:00"                                       # a fixed instant, not "now"
    a1, a2 = demo.demo_annotations(recs), demo.demo_annotations(list(reversed(recs)))
    assert [d["annotation_sha256"] for d in a1] == [d["annotation_sha256"] for d in a2] and len(a1) == 2
    for d in a1:
        assert d["annotator_operator"] == demo.DEMO_OPERATOR and "DEMO" in d["limitations"][0]
        assert all(e["kind"] == "proposed_connection" for e in d["unlocks"])                         # suggestions only
        assert all(m["utility_status"] == "unknown" and m["prior"] is None and m["utilities"] is None for m in d["decisions"].values())
        assert d["next_action"] is None
    s = snapshot.build_snapshot(fake_read(*recs), a1, NOW, "with_demo_annotations")
    r3 = next(r for r in s["problems"] if r["ref"]["id"] == "F003")
    assert r3["annotation"]["status"] == "applied" and {u["relation"] for u in r3["unlock_reasons"]} == {"design_requirement", "theory_challenge"}
    assert s["whiteboard_facets"]["both"] == [f"{NS}/Problem/F003"] and s["whiteboard_facets"]["design_requirement"] == [f"{NS}/Problem/F001"]
    assert s["rankings"]["declared_evpi"]["tiers"] == []                                             # authored demo moves no value ranking
    # the actual snapshot of the same store has none of it
    act = snapshot.build_snapshot(fake_read(*recs), [], NOW)
    assert act["whiteboard_facets"]["both"] == [] and all(r["annotation"]["status"] == "none" for r in act["problems"])
    # change a Problem -> the pinned demo annotation goes stale, it is not silently re-applied
    f3b = prob_with("F003", ["turing-ddi"], unlocks=["An honest simulation explorer"], title="changed")
    s2 = snapshot.build_snapshot(fake_read(f3b, f1, c1, c2), a1, NOW, "with_demo_annotations")
    assert next(r for r in s2["problems"] if r["ref"]["id"] == "F003")["annotation"]["status"] == "stale"


# ------------------------------------------------------------------ the PostgreSQL adapter
def test_adapter_reads_only_the_allowed_tables():
    src = inspect.getsource(pg.read_store) + inspect.getsource(pg.connect_readonly)
    for forbidden in ("principals", "idempotency", "write_receipts", "INSERT", "UPDATE", "DELETE", "token"):
        assert forbidden not in src, forbidden
    assert pg._describe("host=/x port=1 dbname=d user=u password=SECRET") == {"host": "/x", "port": "1", "dbname": "d"}


@pytest.fixture
def pgstore(request):
    if not os.environ.get("FRONTIER_TEST_DSN"):
        pytest.skip("run through scripts/test_postgres.sh")
    return request.getfixturevalue("store")


def test_pg_roundtrip_is_read_only_exact_and_excludes_private(pgstore):
    from conftest import TOKENS, claim
    c = pgstore.submit(TOKENS["alice"], "c1", claim(pgstore, "th-a"))["record"]
    pd = Draft(namespace=pgstore.namespace, kind="Problem", id="P1", issuer="alice", source_uri="urn:test", payload={
        **problem("P1")["payload"], "original": {"claim_ids": ["th-a"], "depends_on": [], "unlocks": ["prose"]}}).model_dump()
    p = pgstore.submit(TOKENS["alice"], "p1", pd)["record"]
    priv = claim(pgstore, "hidden", visibility="private")
    pgstore.submit(TOKENS["alice"], "c2", priv)
    read = pg.read_store(pgstore.dsn, pgstore.namespace, schema=pgstore.schema)
    ids = {(r["kind"], r["id"]) for r in read["records"]}
    assert ("Claim", "th-a") in ids and ("Problem", "P1") in ids and ("Claim", "hidden") not in ids and read["meta"]["excluded_private"] >= 1
    assert read["meta"]["integrity_failures"] == [] and read["meta"]["read_only"] is True and set(read["local_status"].values()) == {"proposed"}
    s = snapshot.build_snapshot(read, [], NOW)
    lk = next(l for l in s["links"] if l["link_kind"] == "concerns_claim")
    assert lk["to"]["version"] == c["version"] and lk["from"]["version"] == p["version"]                 # exact refs, not ids
    assert any(e["envelope"]["payload"]["event_type"] == "record_proposed" for e in read["events"])
    with pg.connect_readonly(pgstore.dsn, pgstore.schema) as conn:
        assert conn.execute("SHOW default_transaction_read_only").fetchone()["default_transaction_read_only"] == "on"      # the server-side default, not only the driver flag
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("INSERT INTO node_config VALUES (2, 'x', 1)")
    # tamper with a stored envelope (owned ephemeral cluster, writer connection): the adapter must report it, not trust it
    with psycopg.connect(pgstore.dsn) as w:
        w.execute(f"SET search_path TO {pgstore.schema}")
        w.execute("SET session_replication_role = replica")                        # the store's append-only trigger would refuse; this is the throwaway test cluster
        w.execute("UPDATE record_versions SET envelope = jsonb_set(envelope, '{payload,title}', '\"tampered\"') WHERE version = %s", (c["version"],))
    bad = pg.read_store(pgstore.dsn, pgstore.namespace, schema=pgstore.schema)["meta"]["integrity_failures"]
    assert [f["version"] for f in bad] == [c["version"]]


# ------------------------------------------------------------------ the real service, if reachable (invariants only; counts may change)
LIVE = "dbname=frontier user=frontier_app host=/data/services/delphi-frontier/run port=5471"


def test_live_service_snapshot_invariants():
    try:
        read = pg.read_store(LIVE, "delphi-frontier")
    except Exception:
        pytest.skip("live service not reachable")
    assert read["meta"]["integrity_failures"] == [] and read["meta"]["read_only"] is True            # digests must hold; schema skew (newer store) is reported, not failed
    assert "schema_skew" in read["meta"] and set(read["local_status"].values()) <= set(vocab.STORE["local_status"])
    s = snapshot.build_snapshot(read, [], NOW)
    assert s["snapshot_kind"] == "actual" and all(r["annotation"]["status"] == "none" for r in s["problems"])
    assert all(r["missing_priorities"] for r in s["problems"]) and all(r["utility"]["status"] == "unknown" for r in s["problems"])
    assert s["link_issues"] == [] or all("issue" in i for i in s["link_issues"])


# ------------------------------------------------------------------ a newer store than this checkout: skew is not corruption, and unknown words are carried, not crashed on
def skewed(rec_, **changes):
    from frontier.models import digest
    env = {k: v for k, v in rec_.items() if k != "version"}
    env["payload"] = {**env["payload"], **changes}
    return {**env, "version": digest(env)}


def test_envelope_check_separates_corruption_from_schema_skew():
    good = problem("PA")
    assert pg.check_envelope(good) == ("ok", "")
    tampered = {**good, "payload": {**good["payload"], "title": "changed"}}                            # version no longer matches the bytes
    assert pg.check_envelope(tampered)[0] == "digest"
    newer = skewed(good, problem_kind="curated_question")                                               # valid digest, unknown word
    verdict, detail = pg.check_envelope(newer)
    assert verdict == "schema" and "problem_kind" in detail


def test_unknown_store_vocabulary_is_carried_verbatim_not_mapped_or_fatal():
    newer = skewed(problem("PA"), problem_kind="curated_question")
    s = snapshot.build_snapshot(fake_read(newer), [], NOW)
    kind = s["problems"][0]["store"]["problem_kind"]
    assert kind == {"vocabulary": "frontier-store", "field": "problem_kind", "value": "curated_question", "recognized": False}
    known = snapshot.build_snapshot(fake_read(problem("PB")), [], NOW)["problems"][0]["store"]["problem_kind"]
    assert known["recognized"] is True and known["value"] == "sourced_field_open_problem"
    assert vocab.tag_lenient("frontier-store", "local_status", "archived")["recognized"] is False
