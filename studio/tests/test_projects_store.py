"""Project / Annotation through the real store (ephemeral Postgres): write rules, pins, discussion, review, migration."""
from copy import deepcopy
from pathlib import Path

import psycopg
import pytest

from conftest import TOKENS, assessment, claim, evidence, source
from frontier.models import ref
from frontier.store import Conflict, Forbidden, Missing, Store, Unauthorized

SCALES = [{"scale": "organism", "status": "implemented_model", "note": "glide simulation exists"},
          {"scale": "tissue", "status": "unimplemented", "note": "no fin tissue model"}]


def sub(store, who, key, draft):
    return store.submit(TOKENS[who], key, draft)["record"]


def member(pin, **kw):
    m = {"ref": pin, "role": "subsystem", "subsystem": "wing", "scale": "organism", "relationship": "supports",
         "applicability": "Declared: applies to the stated geometry only.", "rationale": "Pinned for the design."}
    m.update(kw)
    return m


def project(store, members, id="proj", visibility="public", **over):
    p = {"title": "Design studio project", "mission": "A design goal.", "source": source(), "limitations": ["Not validated."],
         "scale_coverage": SCALES, "members": members, "requirements": [], "open_questions": []}
    p.update(over)
    return {"namespace": store.namespace, "kind": "Project", "id": id, "issuer": "alice", "source_uri": "urn:frontier:project",
            "visibility": visibility, "payload": p}


def annotation(store, anchor, id="ann", who="carol", visibility="public", **over):
    p = {"kind": "comment", "body": "A comment.", "anchor": anchor}
    p.update(over)
    return {"namespace": store.namespace, "kind": "Annotation", "id": id, "issuer": who, "source_uri": "urn:frontier:annotation",
            "visibility": visibility, "payload": p}


def evidence_with_artifact(store, target, digest="d" * 64, id="evidence"):
    d = evidence(store, target)
    d["id"] = id
    d["payload"]["artifacts"] = [{"title": "mesh", "uri": "urn:sha256:" + digest, "sha256": digest, "byte_size": 10,
                                  "media_type": "model/stl", "role": "geometry", "availability": "referenced"}]
    return d


@pytest.fixture
def world(store):
    c = sub(store, "alice", "c1", claim(store))
    e = sub(store, "alice", "e1", evidence_with_artifact(store, ref(c)))
    return store, c, e


# ------------------------------------------------------------------------------------------- Project
def test_project_round_trip_search_edges_and_reuse(world):
    store, c, e = world
    p1 = sub(store, "alice", "p1", project(store, [member(ref(c)), member(ref(e), role="evidence", subsystem="geometry",
             artifact={"evidence": ref(e), "sha256": "d" * 64})], id="proj-1"))
    p2 = sub(store, "alice", "p2", project(store, [member(ref(c), subsystem="other")], id="proj-2"))   # SAME pinned claim, second project
    assert store.get(ref(p1))["record"] == p1 and store.get(ref(p1))["local_review"]["status"] == "proposed"
    assert {r["ref"]["id"] for r in store.search(kind="Project")["results"]} == {"proj-1", "proj-2"}
    assert {r["ref"]["id"] for r in store.search("design studio")["results"]} == {"proj-1", "proj-2"}
    rels = {(x["relation"], x["target"]["id"]) for x in store.neighborhood(ref(p1))["edges"] if x["source"]["id"] == "proj-1"}
    assert {("project_member", "claim"), ("project_member", "evidence"), ("project_member_artifact", "evidence")} <= rels
    got = store.projects_for(ref(c))
    assert {x["ref"]["id"] for x in got["projects"]} == {"proj-1", "proj-2"}
    assert store.projects_for(ref(e))["projects"][0]["ref"]["id"] == "proj-1"
    assert "does not establish" in got["limit"]


def test_writes_use_the_existing_authenticated_path_only(world):
    store, c, _ = world
    d = project(store, [member(ref(c))])
    with pytest.raises(Unauthorized):
        store.submit(None, "k1", d)
    with pytest.raises(Unauthorized):
        store.submit("not-a-real-token-not-a-real-token", "k2", d)
    with pytest.raises(Forbidden):                                    # issuer must be the authenticated actor
        store.submit(TOKENS["carol"], "k3", d)
    store.provision("reviewer-only-token-reviewer-only", "rev", "operator-r", ["reviewer"], [store.namespace], 10)
    with pytest.raises(Forbidden):                                    # a non-contributor cannot write
        store.submit("reviewer-only-token-reviewer-only", "k4", {**d, "issuer": "rev"})
    first = store.submit(TOKENS["alice"], "same-key", d)
    assert store.submit(TOKENS["alice"], "same-key", d) == first      # idempotent
    with pytest.raises(Conflict):
        store.submit(TOKENS["alice"], "same-key", project(store, [member(ref(c))], id="different"))
    ev = store.events(limit=50)["events"]
    assert any(x["envelope"]["payload"]["event_type"] == "record_proposed" and x["envelope"]["payload"]["target"]["kind"] == "Project" for x in ev)


def test_a_project_is_revised_only_through_the_predecessor_rule(world):
    store, c, _ = world
    p = sub(store, "alice", "p1", project(store, [member(ref(c))]))
    with pytest.raises(Conflict):                                     # no predecessor
        store.submit(TOKENS["alice"], "p2", project(store, [member(ref(c))], title="Retitled"))
    d = project(store, [member(ref(c))], title="Retitled")
    d["predecessor"] = p["version"]
    p2 = store.submit(TOKENS["alice"], "p3", d)["record"]
    assert store.get(ref(p))["is_head"] is False and store.get(ref(p2))["is_head"] is True
    assert store.get(ref(p))["record"] == p                           # the old version is preserved exactly


def test_pins_must_exist_but_may_be_superseded_versions(world):
    store, c, _ = world
    d = claim(store)
    d["predecessor"] = c["version"]
    d["payload"]["title"] = "Revised claim"
    c2 = store.submit(TOKENS["alice"], "claim-v2", d)["record"]
    assert store.get(ref(c))["is_head"] is False
    stale = sub(store, "alice", "p1", project(store, [member(ref(c))], id="pins-old"))          # a Project may pin the old version
    fresh = sub(store, "alice", "p2", project(store, [member(ref(c2))], id="pins-new"))
    pm = {m["index"]: m for m in store.project_members(ref(stale))["members"]}[0]
    assert pm["is_current"] is False and pm["current_version"] == c2["version"] and pm["available"] is True
    assert store.project_members(ref(fresh))["members"][0]["is_current"] is True
    assert {x["ref"]["id"] for x in store.projects_for(ref(c))["projects"]} == {"pins-old"}      # exact version
    assert {x["ref"]["id"] for x in store.projects_for(ref(c), all_versions=True)["projects"]} == {"pins-old", "pins-new"}
    ghost = {**ref(c), "version": "9" * 64}
    with pytest.raises(Missing):
        store.submit(TOKENS["alice"], "ghost", project(store, [member(ghost)], id="ghost"))


def test_a_public_record_cannot_reference_a_private_one(store):
    priv = sub(store, "alice", "pc", {**claim(store, id="private-claim"), "visibility": "private"})
    with pytest.raises(Conflict, match="public"):
        store.submit(TOKENS["alice"], "pp", project(store, [member(ref(priv))], id="leaks"))
    ok = sub(store, "alice", "pp2", project(store, [member(ref(priv))], id="private-project", visibility="private"))
    assert store.get(ref(ok), TOKENS["alice"])["record"] == ok
    with pytest.raises(Conflict, match="public"):
        store.submit(TOKENS["alice"], "pa", annotation(store, {"record": ref(priv)}, who="alice"))
    with pytest.raises(Missing):                                      # and an anonymous reader cannot see the private pin
        store.projects_for(ref(priv))


def test_artifact_digests_must_be_listed_by_the_pinned_evidence(world):
    store, c, e = world
    good = {"evidence": ref(e), "sha256": "d" * 64}
    wrong = {"evidence": ref(e), "sha256": "e" * 64}
    sub(store, "alice", "ok", project(store, [member(ref(e), artifact=good)], id="good-artifact"))
    with pytest.raises(Conflict, match="not listed"):
        store.submit(TOKENS["alice"], "bad", project(store, [member(ref(e), artifact=wrong)], id="bad-artifact"))
    sub(store, "carol", "an-ok", annotation(store, {"record": ref(e), "artifact": good,
        "region": {"type": "mesh_part", "part_id": "ray_3", "artifact_sha256": "d" * 64}}, id="ann-ok"))
    with pytest.raises(Conflict, match="not listed"):
        store.submit(TOKENS["carol"], "an-bad", annotation(store, {"record": ref(e), "artifact": wrong}, id="ann-bad"))


# ------------------------------------------------------------------------------------------- Annotation
def test_annotation_is_authored_by_the_authenticated_actor_and_changes_nothing_it_points_at(world):
    store, c, _ = world
    before = store.get(ref(c))
    a = sub(store, "carol", "a1", annotation(store, {"record": ref(c), "region": {"type": "named_subsystem", "name": "wing"}},
                                             kind="challenge", body="I doubt this applies."))
    assert a["issuer"] == "carol"
    with pytest.raises(Forbidden):
        store.submit(TOKENS["alice"], "impersonate", annotation(store, {"record": ref(c)}, id="imp", who="carol"))
    after = store.get(ref(c))
    assert after["record"] == before["record"] and after["local_review"] == before["local_review"] and after["is_head"]
    assert store.get(ref(a))["local_review"]["status"] == "proposed"      # an annotation is never self-accepting
    got = store.annotations_for(ref(c))
    assert [x["ref"]["id"] for x in got["annotations"]] == ["ann"] and got["annotations"][0]["issuer"] == "carol"


def test_replies_must_stay_on_the_same_record_and_edits_are_new_versions(world):
    store, c, e = world
    a = sub(store, "carol", "a1", annotation(store, {"record": ref(c)}, kind="question", body="Why?"))
    r1 = sub(store, "alice", "r1", annotation(store, {"record": ref(c)}, id="reply", who="alice", body="Because.", reply_to=ref(a)))
    with pytest.raises(Conflict, match="same record"):
        store.submit(TOKENS["alice"], "r2", annotation(store, {"record": ref(e)}, id="wrong-thread", who="alice", reply_to=ref(a)))
    d = annotation(store, {"record": ref(c)}, kind="question", body="Why, precisely?")
    d["predecessor"] = a["version"]
    a2 = store.submit(TOKENS["carol"], "a2", d)["record"]
    with pytest.raises(Conflict, match="predecessor"):
        store.submit(TOKENS["carol"], "a3", {**d, "predecessor": a["version"]})
    got = store.annotations_for(ref(c))["annotations"]
    # heads, each listed by its OWN creation time (an edited annotation sorts by its newest version; threading is display's job)
    assert {(x["ref"]["id"], x["ref"]["version"]) for x in got} == {("ann", a2["version"]), ("reply", r1["version"])}
    assert [x["record"]["created_at"] for x in got] == sorted(x["record"]["created_at"] for x in got)
    assert store.get(ref(a))["record"] == a                              # the superseded text is preserved exactly
    reply = next(x for x in got if x["ref"]["id"] == "reply")
    assert reply["record"]["payload"]["reply_to"] == ref(a)              # the reply keeps the exact version it answered


def test_discussion_may_concern_a_superseded_version(world):
    store, c, _ = world
    d = claim(store)
    d["predecessor"] = c["version"]
    d["payload"]["title"] = "Revised"
    c2 = store.submit(TOKENS["alice"], "v2", d)["record"]
    sub(store, "carol", "a1", annotation(store, {"record": ref(c)}, id="on-old"))
    sub(store, "carol", "a2", annotation(store, {"record": ref(c2)}, id="on-new"))
    assert [x["ref"]["id"] for x in store.annotations_for(ref(c))["annotations"]] == ["on-old"]
    assert [x["ref"]["id"] for x in store.annotations_for(ref(c2))["annotations"]] == ["on-new"]
    assert {x["ref"]["id"] for x in store.annotations_for(ref(c2), all_versions=True)["annotations"]} == {"on-old", "on-new"}


def test_a_proposed_edit_is_a_proposal_and_leaves_the_record_alone(world):
    store, c, _ = world
    edit = {"target_path": "limitations[0]", "proposed": "A stricter limitation.", "rationale": "More honest."}
    a = sub(store, "carol", "e1", annotation(store, {"record": ref(c)}, kind="proposed_edit", body="Suggest.", proposed_edit=edit))
    assert a["payload"]["proposed_edit"] == edit
    assert store.get(ref(c))["record"]["payload"]["limitations"] == ["Not measured evidence"] and store.get(ref(c))["is_head"]
    with pytest.raises(Conflict, match="top-level"):
        store.submit(TOKENS["carol"], "e2", annotation(store, {"record": ref(c)}, id="e2", kind="proposed_edit", body="x",
                     proposed_edit={**edit, "target_path": "nonexistent_field.x"}))


def test_annotations_can_be_anchored_on_a_project_and_on_an_annotation_target_stays_exact(world):
    store, c, _ = world
    p = sub(store, "alice", "p1", project(store, [member(ref(c))]))
    sub(store, "carol", "a1", annotation(store, {"record": ref(p), "region": {"type": "parameter_path", "path": "members[0].scale"}},
                                         kind="challenge", body="This scale label is wrong."))
    assert store.annotations_for(ref(p))["annotations"][0]["record"]["payload"]["anchor"]["region"]["path"] == "members[0].scale"
    with pytest.raises(Missing):
        store.annotations_for({**ref(p), "version": "9" * 64})


# ------------------------------------------------------------------------------------------- review, bundles
def test_acceptance_stays_with_independent_review_and_discussion_does_not_change_it(world):
    store, c, _ = world
    p = sub(store, "alice", "p1", project(store, [member(ref(c))]))
    sub(store, "carol", "a1", annotation(store, {"record": ref(p)}, kind="challenge", body="Disagree."))
    with pytest.raises(Forbidden):                                    # the submitting operator cannot review
        store.review(TOKENS["alias"], "self", assessment(ref(p), reviewer="alias"))
    assert store.get(ref(p))["local_review"]["status"] == "proposed"
    store.review(TOKENS["bob"], "rev", assessment(ref(p)))
    assert store.get(ref(p))["local_review"]["status"] == "accepted"   # exactly the existing review semantics
    assert store.get(ref(c))["local_review"]["status"] == "proposed"   # membership did not accept the member


def test_bundle_round_trip_carries_projects_and_annotations_without_trust(stores):
    a, b = stores("node-a"), stores("node-b")
    c = sub(a, "alice", "c", claim(a))
    p = sub(a, "alice", "p", project(a, [member(ref(c))]))
    n = sub(a, "carol", "n", annotation(a, {"record": ref(p)}))
    bundle = a.export_bundle([ref(c), ref(p), ref(n)])
    receipt = b.import_bundle(TOKENS["alice"], "import", bundle)
    assert receipt["imported_reviews_are_local_authority"] is False
    for rec in (c, p, n):
        got = b.get(ref(rec))
        assert got["record"] == rec and got["local_review"]["status"] == "imported_unreviewed"


# ------------------------------------------------------------------------------------------- migration
OLD_SCHEMA = Path(__file__).with_name("fixtures") / "schema_pre_projects.sql"


def test_an_old_store_is_migrated_additively_and_old_records_are_unchanged(store_factory=None):
    import os
    from uuid import uuid4
    dsn = os.environ["FRONTIER_TEST_DSN"]
    s = Store(dsn, "node-a", "old_" + uuid4().hex[:20])
    with s.connection() as c:                                         # initialise EXACTLY as the pre-change code did
        from psycopg import sql
        c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(s.schema)))
        c.execute(OLD_SCHEMA.read_text())
        c.execute("INSERT INTO node_config VALUES (1,%s,1)", (s.namespace,))
    for actor, roles, op in (("alice", ["contributor", "coordinator"], "operator-a"), ("bob", ["reviewer", "contributor"], "operator-b"),
                             ("carol", ["contributor"], "operator-c")):
        s.provision(TOKENS[actor], actor, op, roles, [s.namespace], 1000)
    with s.connection() as c:                                         # the old constraint really rejects the new kind
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("""INSERT INTO record_versions VALUES (%s,'node-a','Project','x','alice','urn:x','public',NULL,
                         CURRENT_TIMESTAMP,'{}'::jsonb,'x')""", ("1" * 64,))
    c1 = sub(s, "alice", "c1", claim(s))
    e1 = sub(s, "alice", "e1", evidence(s, ref(c1)))
    s.review(TOKENS["bob"], "r1", assessment(ref(e1)))

    def snapshot():
        with s.connection() as c:
            return {t: c.execute(f"SELECT * FROM {t} ORDER BY 1,2").fetchall()
                    for t in ("record_versions", "heads", "typed_edges", "local_states", "reviews", "events")}
    before = snapshot()
    s.initialize()                                                    # the migration
    assert snapshot() == before                                       # old records, hashes, edges, states: identical
    s.initialize()                                                    # idempotent
    assert snapshot() == before
    p = sub(s, "alice", "p1", project(s, [member(ref(c1))]))          # new kinds now work on the migrated store
    sub(s, "carol", "a1", annotation(s, {"record": ref(p)}))
    assert s.get(ref(c1))["record"] == c1 and s.get(ref(p))["record"] == p
    with s.connection() as c:
        assert [r["id"] for r in c.execute("SELECT id FROM schema_migrations").fetchall()] == ["projects-annotations-1"]
        with pytest.raises(psycopg.errors.CheckViolation):            # a bogus kind is still rejected
            c.execute("""INSERT INTO record_versions VALUES (%s,'node-a','Bogus','x','alice','urn:x','public',NULL,
                         CURRENT_TIMESTAMP,'{}'::jsonb,'x')""", ("2" * 64,))
    with s.connection() as c:
        with pytest.raises(psycopg.errors.RaiseException):            # the migration ledger is append-only
            c.execute("UPDATE schema_migrations SET description='x'")


def test_a_fresh_store_has_the_new_kinds_and_one_migration_row(store):
    with store.connection() as c:
        assert [r["id"] for r in c.execute("SELECT id FROM schema_migrations").fetchall()] == ["projects-annotations-1"]
        ck = c.execute("""SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint WHERE conrelid=to_regclass('record_versions')
                          AND contype='c'""").fetchall()
    assert any("'Project'" in r["d"] and "'Annotation'" in r["d"] for r in ck)
