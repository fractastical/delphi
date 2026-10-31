from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
import subprocess
from threading import Barrier

import psycopg
import pytest
from pydantic import ValidationError

from frontier.models import Draft, Ref, canonical, digest, ref
from frontier.store import Store, Conflict, Forbidden, Missing, Unauthorized
from conftest import TOKENS, action, assessment, claim, evidence


def saved_claim(store, id="claim"):
    return store.submit(TOKENS["alice"], "claim-" + id, claim(store, id))["record"]


def test_persistent_restart_and_database_restart(store):
    record = saved_claim(store)
    restarted = Store(store.dsn, store.namespace, store.schema)
    assert restarted.get(ref(record))["record"] == record
    # Actual postgres process stop/start, owned temporary cluster only.
    subprocess.run([os.environ["FRONTIER_TEST_PG_BIN"] + "/pg_ctl", "-D", os.environ["FRONTIER_TEST_PG_DATA"],
                    "-l", os.environ["FRONTIER_TEST_PG_LOG"], "-m", "fast", "-w", "restart"],
                   check=True, capture_output=True, timeout=30)
    assert Store(store.dsn, store.namespace, store.schema).get(ref(record))["record"] == record


def test_auth_idempotency_version_and_rollback(store, monkeypatch):
    with pytest.raises(Unauthorized):
        store.submit("invalid", "x", claim(store))
    draft = claim(store)
    first = store.submit(TOKENS["alice"], "same", draft)
    assert store.submit(TOKENS["alice"], "same", draft) == first
    changed = claim(store, "other")
    with pytest.raises(Conflict):
        store.submit(TOKENS["alice"], "same", changed)
    with pytest.raises(Conflict):
        store.submit(TOKENS["alice"], "wrong-head", draft)
    newer = {**draft, "predecessor": first["record"]["version"]}
    newer["payload"] = {**draft["payload"], "statement": "A revised software fixture."}
    second = store.submit(TOKENS["alice"], "next", newer)["record"]
    assert second["predecessor"] == first["record"]["version"]
    assert store.get(ref(first["record"]))["is_head"] is False
    with pytest.raises(Conflict):
        store.submit(TOKENS["alice"], "stale-evidence", evidence(store, ref(first["record"])))
    missing = ref(second) | {"version": "0" * 64}
    with pytest.raises(Missing):
        store.submit(TOKENS["alice"], "missing", evidence(store, missing))
    with pytest.raises(Forbidden):
        store.submit(TOKENS["carol"], "spoof", claim(store, "spoof", issuer="alice"))
    original = store._event
    def fail(*a, **kw):
        raise RuntimeError("Injected post-insert fault")
    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(RuntimeError):
        store.submit(TOKENS["alice"], "rollback", claim(store, "rollback"))
    monkeypatch.setattr(store, "_event", original)
    assert store.search("rollback")["results"] == []
    assert store.submit(TOKENS["alice"], "rollback", claim(store, "rollback"))["record"]["id"] == "rollback"


def test_review_is_explicit_independent_and_multidimensional(store):
    target = saved_claim(store)
    ev = store.submit(TOKENS["alice"], "evidence", evidence(store, ref(target)))["record"]
    assert store.get(ref(ev))["local_review"]["status"] == "proposed"
    assert store.search(kind="Evidence", status="accepted")["results"] == []
    with pytest.raises(Forbidden):
        store.review(TOKENS["alice"], "wrong-role", assessment(ref(ev), reviewer="alice"))
    with pytest.raises(Forbidden):
        store.review(TOKENS["alias"], "same-operator", assessment(ref(ev), reviewer="alias"))
    incomplete = assessment(ref(ev))
    incomplete["dimensions"]["independent_replication"]["status"] = "unreviewed"
    with pytest.raises(Conflict):
        store.review(TOKENS["bob"], "incomplete", incomplete)
    # Merely uploading an Assessment that says accepted does not change target.
    forged = {"namespace": store.namespace, "kind": "Assessment", "id": "uploaded-review", "issuer": "alice",
              "source_uri": "urn:frontier:fixture", "payload": assessment(ref(ev), reviewer="alice")}
    store.submit(TOKENS["alice"], "uploaded-review", forged)
    assert store.get(ref(ev))["local_review"]["status"] == "proposed"
    result = store.review(TOKENS["bob"], "review", assessment(ref(ev)))
    assert result["local_status"] == "accepted"
    assert store.get(ref(ev))["record"] == ev
    dispute = store.review(TOKENS["bob"], "dispute", assessment(ref(ev), decision="disputed"))
    assert dispute["local_status"] == "disputed"
    assert store.get(ref(ev))["record"] == ev
    events = store.events(limit=50)["events"]
    assert [e["envelope"]["payload"]["event_type"] for e in events].count("review_recorded") == 2


def test_two_worker_atomic_lease_and_lifecycle(store):
    target = saved_claim(store)
    record = store.submit(TOKENS["alice"], "action", action(store, ref(target)))["record"]
    with pytest.raises(Conflict):
        store.lease(TOKENS["carol"], "too-early", ref(record))
    store.transition(TOKENS["alice"], "ready", ref(record), "ready")
    barrier = Barrier(2)
    def compete(actor):
        barrier.wait(timeout=5)
        try:
            return actor, store.lease(TOKENS[actor], "compete-" + actor, ref(record))
        except Conflict:
            return actor, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(compete, ["alice", "carol"]))
    winners = [(actor, lease) for actor, lease in outcomes if lease]
    assert len(winners) == 1
    actor, lease = winners[0]
    with pytest.raises(Forbidden):
        store.transition(TOKENS[actor], "wrong-lease", ref(record), "running", "wrong")
    store.transition(TOKENS[actor], "running", ref(record), "running", lease["lease_id"])
    store.transition(TOKENS[actor], "submitted", ref(record), "submitted", lease["lease_id"])
    assert store.get(ref(record))["local_review"]["status"] == "proposed"
    store.review(TOKENS["bob"], "accept-action", assessment(ref(record)))
    assert store.get(ref(record))["action"]["state"] == "accepted"
    with pytest.raises(Conflict):
        store.lease(TOKENS["carol"], "terminal-lease", ref(record))


def test_expired_lease_cannot_submit_and_reclaim_fences_owner(store):
    target = saved_claim(store)
    a = store.submit(TOKENS["alice"], "action", action(store, ref(target)))["record"]
    store.transition(TOKENS["alice"], "ready", ref(a), "ready")
    lease = store.lease(TOKENS["carol"], "lease", ref(a))
    # Advance this fixture's database lease timestamp without sleeping or changing clocks.
    with store.connection() as c:
        c.execute("UPDATE action_state SET lease_until=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE version=%s", (a["version"],))
    with pytest.raises(Conflict):
        store.transition(TOKENS["carol"], "expired-run", ref(a), "running", lease["lease_id"])
    replacement = store.lease(TOKENS["alice"], "replacement", ref(a))
    assert replacement["lease_id"] != lease["lease_id"]
    with pytest.raises(Forbidden):
        store.transition(TOKENS["carol"], "fenced", ref(a), "running", lease["lease_id"])
    assert any(e["envelope"]["payload"]["event_type"] == "action_expired" for e in store.events(limit=50)["events"])


def test_two_store_bundle_preserves_digest_source_and_no_trust(stores):
    a, b = stores("node-a"), stores("node-b")
    target = saved_claim(a)
    ev = a.submit(TOKENS["alice"], "evidence", evidence(a, ref(target)))["record"]
    a.review(TOKENS["bob"], "accept", assessment(ref(ev)))
    bundle = a.export_bundle([ref(target), ref(ev)])
    receipt = b.import_bundle(TOKENS["alice"], "import", bundle)
    assert receipt["imported_reviews_are_local_authority"] is False
    imported = b.get(ref(ev))
    assert imported["record"] == ev
    assert imported["record"]["payload"]["source"] == ev["payload"]["source"]
    assert imported["local_review"]["status"] == "imported_unreviewed"
    assert b.search(status="accepted")["results"] == []
    assert b.import_bundle(TOKENS["alice"], "import", bundle) == receipt
    reexport = b.export_bundle([ref(target), ref(ev)])
    assert next(r for r in reexport["records"] if r["version"] == ev["version"]) == ev
    damaged = deepcopy(bundle)
    damaged["records"][0]["payload"]["statement"] = "Tampered"
    with pytest.raises(ValueError):
        b.import_bundle(TOKENS["alice"], "tampered", damaged)
    # A valid bundle digest cannot hide a changed record digest.
    damaged["bundle_sha256"] = digest({k:v for k,v in damaged.items() if k != "bundle_sha256"})
    with pytest.raises(ValidationError):
        b.import_bundle(TOKENS["alice"], "tampered-record", damaged)


def test_imported_conflict_is_fork_and_does_not_overwrite_head(stores):
    origin, replica = stores("node-a"), stores("node-b")
    first = saved_claim(origin)
    replica.import_bundle(TOKENS["alice"], "initial", origin.export_bundle([ref(first)]))
    change = claim(origin, predecessor=first["version"])
    change["payload"]["statement"] = "Explicit revised fixture"
    later = origin.submit(TOKENS["alice"], "revised", change)["record"]
    received = replica.import_bundle(TOKENS["alice"], "later", origin.export_bundle([ref(later)]))
    assert received["forks"] == [{"local_version": first["version"], "imported_version": later["version"]}]
    assert replica.get(ref(first))["is_head"] is True
    assert replica.get(ref(later))["is_head"] is False


def test_private_reads_bounds_and_immutability(store):
    record = store.submit(TOKENS["alice"], "private", claim(store, visibility="private"))["record"]
    with pytest.raises(Missing):
        store.get(ref(record))
    assert store.search()["results"] == []
    assert store.events()["events"] == []
    assert store.get(ref(record), TOKENS["alice"])["record"] == record
    with pytest.raises(Missing):
        store.export_bundle([ref(record)])
    with pytest.raises(ValueError):
        store.search(limit=51)
    with pytest.raises(ValueError):
        store.neighborhood(ref(record), limit=500)
    with pytest.raises(psycopg.errors.RaiseException):
        with store.connection() as c:
            c.execute("UPDATE record_versions SET issuer='intruder' WHERE version=%s", (record["version"],))
    with pytest.raises(psycopg.errors.RaiseException):
        with store.connection() as c:
            c.execute("DELETE FROM events")


def test_operator_quota_cannot_be_bypassed_by_actor_alias(store):
    token = "test-only-quota-token-with-long-value"
    store.provision(token, "limited", "operator-limited", ["contributor"], daily_write_limit=1)
    store.submit(token, "one", claim(store, "one", issuer="limited"))
    with pytest.raises(Forbidden):
        store.submit(token, "two", claim(store, "two", issuer="limited"))
    assert store.search(kind="Claim")["results"][0]["ref"]["id"] == "one"


def test_seed_snapshot_keeps_six_questions_and_resolved_correction(store):
    from frontier.seed import seed
    refs = seed(store, TOKENS["alice"], "alice")
    assert len(refs) == 28
    assert seed(store, TOKENS["alice"], "alice") == refs
    for target in refs:
        if target["kind"] == "Problem":
            problem = store.get(target)["record"]["payload"]
            assert problem["completeness"] == "recorded"
            assert problem["falsifiers"] == []
            with pytest.raises(Conflict, match="recorded, not actionable"):
                store.submit(TOKENS["alice"], "seed-action-" + target["id"], action(store, target))
    problems = store.search(kind="Problem", limit=50)["results"]
    assert len(problems) == 7
    resolved = store.get(next(x["ref"] for x in problems if x["ref"]["id"] == "F007"))
    assert resolved["record"]["payload"]["original"]["state"] == "resolved_in_review"
    assert resolved["local_review"]["status"] == "proposed"
