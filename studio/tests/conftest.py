import os
from uuid import uuid4

import pytest

from frontier.store import Store

TOKENS = {x: "test-only-local-token-for-" + x for x in ("alice", "bob", "carol", "alias")}


@pytest.fixture
def stores():
    dsn = os.environ.get("FRONTIER_TEST_DSN")
    if not dsn:
        pytest.fail("Use scripts/test_postgres.sh within the documented systemd scope")
    def create(namespace="node-a"):
        store = Store(dsn, namespace, "test_" + uuid4().hex)
        store.initialize()
        for actor, roles, operator in [("alice", ["contributor", "coordinator"], "operator-a"),
                                       ("bob", ["reviewer", "contributor"], "operator-b"),
                                       ("carol", ["contributor"], "operator-c"),
                                       ("alias", ["reviewer", "contributor"], "operator-a")]:
            store.provision(TOKENS[actor], actor, operator, roles, [namespace, "node-a", "node-b"], 1000)
        return store
    return create


@pytest.fixture
def store(stores):
    return stores()


def source():
    return {"uri": "https://example.org/public-dataset.csv", "locator": "row=7", "source_version": "source-release-v3",
            "content_sha256": "a" * 64, "content_available": False, "access": "public reference, unavailable bytes", "license": "CC0-1.0"}


def claim(store, id="claim", issuer="alice", **changes):
    draft = {"namespace": store.namespace, "kind": "Claim", "id": id, "issuer": issuer,
             "source_uri": "https://example.org/test-protocol", "payload": {"title": "Protocol fixture, not scientific data",
                "statement": "A software fixture asserts a scoped statement.", "context": "Protocol test only",
                "assumptions": ["Fixture"], "limitations": ["Not measured evidence"], "source": source()}}
    draft.update(changes)
    return draft


def evidence(store, target):
    return {"namespace": store.namespace, "kind": "Evidence", "id": "evidence", "issuer": "alice",
            "source_uri": "https://example.org/test-protocol", "payload": {"target": target,
               "evidence_kind": "source_assessment", "source": source(),
               "created_time": {"value": None, "basis": "unknown"},
               "retrieved_time": {"value": "2026-10-31T15:00:00+00:00", "basis": "declared"},
               "method": "Software protocol fixture", "context": "No empirical claim",
               "assumptions": ["A fixture"], "provenance": {"provider": "fixture"},
               "source_dependence": {"group": "single-fixture-source", "independence": "unknown"},
               "uncertainty": "Unknown", "limitations": ["Unavailable source bytes; digest is declared only."]}}


def assessment(target, reviewer="bob", decision="accepted"):
    from frontier.models import DIMENSIONS
    return {"target": target, "decision": decision,
            "dimensions": {d: {"status": "passed", "reviewer": reviewer,
                                "rationale": "Software acceptance-control fixture; not a scientific review.",
                                "evidence_links": []} for d in DIMENSIONS},
            "independence_rationale": "Separate configured operator fixture",
            "limitations": ["This exercises workflow only, not scientific correctness."]}


def action(store, target):
    from frontier.models import POLICY
    return {"namespace": store.namespace, "kind": "Action", "id": "action", "issuer": "alice",
            "source_uri": "urn:frontier:protocol-test", "payload": {"target": target, "title": "Software fixture action",
            "acceptance_criteria": ["Test protocol invariants"], "required_capabilities": ["review"],
            "cost_stop_bounds": "No runner; lease test only, at most 600 seconds",
            "cache_key": {"target": target["version"], "input": "fixture-v1", "code": "test-v1", "model": "none",
                          "environment": "postgres16", "parameters": "fixture", "scope": "protocol-only", "acceptance_policy": POLICY}}}
