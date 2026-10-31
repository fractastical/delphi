"""Bounded hydration keeps individual-read semantics without per-record connections."""
from contextlib import contextmanager
from copy import deepcopy

import pytest

from conftest import TOKENS, action, assessment, claim
from frontier.models import Draft, make_record, ref
from frontier.search import SearchIndex
from frontier.store import Forbidden, FrontierError, Missing, Store, Unauthorized


def save(store, draft, key=None):
    return store.submit(TOKENS["alice"], key or draft["id"], draft)["record"]


def test_batch_parity_order_duplicates_history_and_current_review(store):
    first = save(store, claim(store, "history"))
    revision = claim(store, "history", predecessor=first["version"])
    revision["payload"]["statement"] += " Revised fixture."
    second = save(store, revision, "revision")
    store.review(TOKENS["bob"], "review", assessment(ref(second)))
    pins = [ref(second), ref(first), ref(second)]
    index = SearchIndex(store)
    assert index.get_many(pins) == [store.get(pin) for pin in pins]
    assert [row["is_head"] for row in index.get_many(pins)] == [True, False, True]
    store.review(TOKENS["bob"], "dispute", assessment(ref(second), decision="disputed"))
    assert index.get_many([ref(second)])[0]["local_review"]["status"] == "disputed"


def test_batch_parity_action_lease_and_null_action(store):
    target = save(store, claim(store))
    record = save(store, action(store, ref(target)))
    index = SearchIndex(store)
    pins = [ref(target), ref(record)]
    assert index.get_many(pins) == [store.get(pin) for pin in pins]
    store.transition(TOKENS["alice"], "ready", ref(record), "ready")
    store.lease(TOKENS["carol"], "lease", ref(record))
    rows = index.get_many(pins)
    assert rows == [store.get(pin) for pin in pins]
    assert rows[0]["action"] is None
    assert isinstance(rows[1]["action"]["lease_until"], str)


def test_batch_visibility_auth_and_all_pin_fields(store):
    public = save(store, claim(store, "public"))
    private = save(store, claim(store, "private", visibility="private"))
    outsider = "test-only-local-token-for-dave-b-only"
    store.provision(outsider, "dave", "operator-d", ["contributor"], ["node-b"], 100)
    index = SearchIndex(store)
    for token in (None, outsider):
        with pytest.raises(Missing, match="Exact record version unavailable"):
            index.get_many([ref(public), ref(private)], token)
    assert index.get_many([ref(private)], TOKENS["alice"]) == [store.get(ref(private), TOKENS["alice"])]
    with pytest.raises(Unauthorized):
        index.get_many([ref(public)], "invalid-token")
    for field, value in (("namespace", "node-b"), ("kind", "Evidence"), ("id", "another"), ("version", "f" * 64)):
        pin = {**ref(public), field: value}
        with pytest.raises(Missing):
            index.get_many([pin])


def test_batch_retains_legacy_unlicensed_content_gate(store):
    # An operator may encounter legacy rows imported before the write-time gate.
    draft = claim(store, "legacy")
    draft["payload"]["source"].update(content_available=True, license=None)
    record = make_record(Draft.model_validate(draft))
    with store.connection() as c:
        store._insert(c, record, store._auth(c, TOKENS["alice"]))
    for read in (lambda: store.get(ref(record)), lambda: SearchIndex(store).get_many([ref(record)])):
        with pytest.raises(Forbidden):
            read()


def test_batch_bounds_before_database_access():
    index = SearchIndex(Store("host=/nonexistent dbname=none", "node-a"))
    assert index.get_many([]) == []
    for targets in ([{}] * 51, "bad", {}, iter([])):
        with pytest.raises(FrontierError):
            index.get_many(targets)
    with pytest.raises(ValueError):
        index.get_many([{}])


def test_full_page_uses_one_connection_one_select_and_is_read_only(store, monkeypatch):
    records = [save(store, claim(store, "record-" + str(i))) for i in range(50)]
    pins = [ref(record) for record in reversed(records)]
    expected = [store.get(pin) for pin in pins]
    original = store.connection
    calls = {"connections": 0, "queries": []}

    class Connection:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def execute(self, query, *args, **kwargs):
            calls["queries"].append(query)
            return self.wrapped.execute(query, *args, **kwargs)

    @contextmanager
    def traced():
        calls["connections"] += 1
        with original() as c:
            c.execute("SET TRANSACTION READ ONLY")
            yield Connection(c)

    monkeypatch.setattr(store, "connection", traced)
    assert SearchIndex(store).get_many(deepcopy(pins)) == expected
    assert calls["connections"] == 1
    assert len(calls["queries"]) == 1
    assert calls["queries"][0].lstrip().startswith("SELECT")
