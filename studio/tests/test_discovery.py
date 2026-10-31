"""Hybrid lexical + vector discovery. A deterministic TEST DOUBLE embedder stands in for the hosted provider so the plumbing (pins, hashes,
privacy, fusion, cache, bounds, fallback) is tested offline; its vectors are never presented as semantic search and it lives only in this file.
Run bounded: systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash scripts/test_postgres.sh tests/test_discovery.py
"""
import json
import re
import time
import urllib.error
from hashlib import sha256
from math import sqrt

import pytest

from conftest import TOKENS, claim, evidence
from frontier.discovery import (DIMENSIONS, RECIPE, Discovery, GeminiEmbedder, Unavailable, artifact_doc, input_hash, record_doc, search, vec_literal)
from frontier.models import ref
from frontier.store import FrontierError

# Synonym groups give the double "semantic" neighbours that share no word: pure test scaffolding.
GROUPS = [{"car", "automobile", "vehicle"}, {"heart", "cardiac", "cardiomyocyte"}, {"fish", "zebrafish", "teleost"}, {"gene", "allele", "locus"}]


class Double:
    provider, model, dimensions = "test-double", "double-1", DIMENSIONS

    def __init__(self, fail_on=None, delay=0.0, fail_all=False):
        self.calls = {"docs": 0, "queries": 0, "batches": 0}
        self.fail_on, self.delay, self.fail_all = fail_on, delay, fail_all

    def _vec(self, text):
        v = [0.0] * DIMENSIONS
        for w in re.findall(r"[a-z]+", text.lower()):
            g = next((i for i, grp in enumerate(GROUPS) if w in grp), None)
            slot = (g * 7 + 1) if g is not None else (int(sha256(w.encode()).hexdigest(), 16) % (DIMENSIONS - 40)) + 40
            v[slot] += 1.0
        n = sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        self.calls["batches"] += 1
        if self.fail_all:
            raise Unavailable("provider down")
        if self.fail_on and any(self.fail_on in t for t in texts):
            raise Unavailable("embedding provider answered HTTP 400")
        self.calls["docs"] += len(texts)
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        self.calls["queries"] += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail_all:
            raise Unavailable("provider down")
        return self._vec(text)


def put(store, id, title, statement, visibility="public", token="alice", **extra):
    d = claim(store, id, visibility=visibility)
    d["payload"]["title"], d["payload"]["statement"] = title, statement
    return store.submit(TOKENS[token], "k-" + id, d)["record"]


@pytest.fixture
def seeded(store):
    recs = {
        "car": put(store, "car-claim", "Automobile braking distances", "Vehicle stopping distance grows with speed."),
        "heart": put(store, "heart-claim", "Cardiomyocyte proliferation after injury", "Cardiac regeneration depends on cell cycle re-entry."),
        "private": put(store, "private-claim", "Secret cardiac note", "A private automobile heart observation.", visibility="private"),
        "other": put(store, "other-claim", "Lattice gauge notes", "Unrelated numerical remarks."),
    }
    d = Discovery(store, Double())
    d.initialize()
    return store, d, recs


def index(d, **kw):
    return d.index(**kw)


# ---- schema and recipe ------------------------------------------------------------------------------------------------
def test_initialize_is_idempotent_and_adds_only_discovery_tables(store):
    d = Discovery(store, Double())
    with store.connection() as c:
        before = {r["tablename"] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (store.schema,))}
    d.initialize()
    d.initialize()
    with store.connection() as c:
        after = {r["tablename"] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (store.schema,))}
        idx = {r["indexname"] for r in c.execute("SELECT indexname FROM pg_indexes WHERE schemaname=%s", (store.schema,))}
    assert after - before == {"discovery_documents", "discovery_failures", "discovery_runs", "discovery_query_cache"}
    assert "discovery_documents_hnsw" in idx


def test_text_recipe_is_deterministic_bounded_and_skips_missing_fields():
    env = {"kind": "Claim", "id": "x", "payload": {"title": "T", "statement": "S", "context": "C", "assumptions": ["a", "b"], "limitations": []}}
    a, b = record_doc(env), record_doc(env)
    assert a == b and a["text"].splitlines()[0] == "Claim: T" and "assumptions: a; b" in a["text"] and "limitations" not in a["text"]
    big = {"kind": "Claim", "id": "x", "payload": {"title": "T", "statement": "z" * 20000}}
    d = record_doc(big)
    assert d["truncated"] is True and len(d["text"]) == 6000 and input_hash(d["text"]) == sha256(d["text"].encode()).hexdigest()
    art = artifact_doc({"id": "e1", "payload": {"context": "ctx", "method": "m"}}, {"title": "A", "role": "input", "media_type": "application/json", "availability": "referenced", "sha256": "a" * 64})
    assert "Artifact (input): A" in art["text"] and "declared by Evidence e1" in art["text"] and "bytes" not in art["text"]


# ---- indexing: pins, hashes, privacy, resumability, failures ---------------------------------------------------------------
def test_index_pins_versions_hashes_inputs_and_never_embeds_private_records(seeded):
    store, d, recs = seeded
    ev = evidence(store, ref(recs["car"]))
    ev["payload"]["artifacts"] = [{"title": "Snapshot", "uri": "urn:sha256:" + "b" * 64, "sha256": "b" * 64, "byte_size": 5, "media_type": "application/json",
                                   "role": "input", "availability": "referenced", "license": None}]
    ev_rec = store.submit(TOKENS["alice"], "ev", ev)["record"]
    r = index(d)
    assert r["failed"] == 0 and r["embedded"] == r["planned"] and r["model"] == "double-1" and r["dimensions"] == 768
    with store.connection() as c:
        rows = c.execute("SELECT * FROM discovery_documents").fetchall()
    ids = {x["doc_id"] for x in rows}
    assert "record:" + recs["private"]["version"] not in ids, "private records are never embedded"
    assert not any("secret" in x["input_text"].lower() or "private" in x["input_text"].lower() for x in rows)
    assert "record:" + recs["car"]["version"] in ids and f"artifact:{ev_rec['version']}:{'b' * 64}:input" in ids
    assert any(x["doc_type"] == "record" and x["kind"] == "Event" for x in rows), "all public kinds are indexed, Event included"
    for x in rows:
        assert x["input_sha256"] == sha256(x["input_text"].encode()).hexdigest() and x["text_recipe"] == RECIPE and x["dimensions"] == 768
        assert x["provider"] == "test-double" and x["task_type"] == "RETRIEVAL_DOCUMENT"
        with store.connection() as c:
            assert c.execute("SELECT 1 FROM record_versions WHERE version=%s AND visibility='public'", (x["version"],)).fetchone(), "every vector is pinned to a public version"
    art = next(x for x in rows if x["doc_type"] == "artifact")
    assert art["artifact_sha256"] == "b" * 64 and art["artifact_role"] == "input" and art["version"] == ev_rec["version"]
    assert r["coverage"]["documents_indexed"] == r["coverage"]["documents_planned"] and r["manifest_sha256"]


def test_reindex_is_incremental_and_a_new_version_supersedes_in_results(seeded):
    store, d, recs = seeded
    index(d)
    n = d.embedder.calls["docs"]
    again = index(d)
    assert again["to_embed"] == 0 and again["requests"] == 0 and d.embedder.calls["docs"] == n
    rev = claim(store, "heart-claim", predecessor=recs["heart"]["version"])
    rev["payload"]["title"], rev["payload"]["statement"] = "Cardiomyocyte proliferation revised", "Revised statement about cardiac cells."
    new = store.submit(TOKENS["alice"], "heart-2", rev)["record"]
    third = index(d)
    assert third["embedded"] >= 1 and third["already_current"] > 0
    res = d.search("cardiac cells", mode="vector")
    versions = [i["ref"]["version"] for i in res["items"]]
    assert new["version"] in versions and recs["heart"]["version"] not in versions, "only the current head is returned; the old version stays pinned in the table"


def test_a_poisoned_document_is_isolated_recorded_and_coverage_stays_honest(store):
    put(store, "ok-1", "Fine record one", "fine words")
    put(store, "bad-1", "Poison record", "POISONTOKEN here")
    put(store, "ok-2", "Fine record two", "more fine words")
    d = Discovery(store, Double(fail_on="POISONTOKEN"))
    d.initialize()
    r = index(d)
    assert r["failed"] == 1 and r["failures"][0]["error_class"] == "unavailable" and "bad-1" not in r["failures"][0]["message"]
    cov = r["coverage"]
    assert cov["documents_indexed"] == cov["documents_planned"] - 1
    with store.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM discovery_failures").fetchone()["n"] == 1
        assert c.execute("SELECT count(*) AS n FROM discovery_runs").fetchone()["n"] == 1


def test_request_budget_is_enforced_and_unembedded_documents_are_reported(store):
    for i in range(6):
        put(store, f"budget-{i}", f"Record {i}", "text")
    d = Discovery(store, Double())
    d.initialize()
    r = index(d, max_requests=1, batch=3)
    assert r["requests"] == 1 and r["embedded"] == 3 and r["failed"] == r["to_embed"] - 3 and r["failure_classes"] == {"request_budget": r["failed"]}
    done = index(d, max_requests=10, batch=50)
    assert done["failed"] == 0 and done["coverage"]["documents_indexed"] == done["coverage"]["documents_planned"], "resumes where it stopped"


def test_dry_run_writes_nothing(seeded):
    store, d, _ = seeded
    r = index(d, dry_run=True)
    assert r["dry_run"] is True and r["to_embed"] > 0 and d.embedder.calls["batches"] == 0
    with store.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM discovery_documents").fetchone()["n"] == 0


# ---- search -----------------------------------------------------------------------------------------------------------
def test_contract_shape_hybrid_fusion_and_semantic_only_match(seeded):
    store, d, recs = seeded
    index(d)
    res = d.search("automobile stopping")
    assert set(res) >= {"query", "mode", "items", "index", "relevance_note"} and res["mode"] == "hybrid" and "unavailable_reason" not in res
    assert res["index"]["model"] == "double-1" and res["index"]["dimensions"] == 768 and res["index"]["documents"] > 0 and res["index"]["updated_at"]
    assert "not truth" in res["relevance_note"] or "not truth, quality" in res["relevance_note"]
    top = res["items"][0]
    assert top["ref"] == ref(recs["car"]) and top["type"] == "record" and top["kind"] == "Claim" and top["local_status"] == "proposed"
    assert {"title", "snippet", "score", "score_kind", "why_matched"} <= set(top) and top["score_kind"].startswith("rrf")
    assert any(w.startswith("semantic: cosine") for w in top["why_matched"]) and any(w.startswith("lexical rank") for w in top["why_matched"])
    # a synonym-only query (no shared word) is found by vector and hybrid, not by lexical
    syn = "vehicle"
    assert not [i for i in d.search("vehicle", mode="lexical")["items"] if i["ref"]["id"] == "car-claim" and i["why_matched"] and "semantic" in " ".join(i["why_matched"])]
    assert recs["car"]["version"] in [i["ref"]["version"] for i in d.search(syn, mode="vector")["items"]]
    assert all(i["score_kind"] == "cosine_similarity" for i in d.search(syn, mode="vector")["items"])
    assert all(i["score_kind"] == "lexical_rank_reciprocal" for i in d.search("automobile", mode="lexical")["items"])


def test_an_exact_identifier_is_kept_at_the_top_by_the_lexical_side_of_the_fusion(seeded):
    store, d, recs = seeded
    index(d)
    res = d.search("other-claim", mode="hybrid")
    assert res["items"][0]["ref"]["id"] == "other-claim" and any(w.startswith("lexical rank 1") for w in res["items"][0]["why_matched"])
    pinned = d.search(recs["heart"]["version"], mode="hybrid")
    assert pinned["items"][0]["ref"]["version"] == recs["heart"]["version"], "an exact version pin is found whatever the vector side says"


def test_private_records_are_never_returned_by_any_mode(seeded):
    store, d, recs = seeded
    index(d)
    for mode in ("lexical", "vector", "hybrid"):
        for q in ("automobile heart", "private cardiac note", "Secret"):
            assert all(i["ref"]["id"] != "private-claim" for i in d.search(q, mode=mode)["items"])


def test_artifacts_are_returned_as_artifact_items_with_their_pins(seeded):
    store, d, recs = seeded
    ev = evidence(store, ref(recs["car"]))
    ev["payload"]["artifacts"] = [{"title": "Braking snapshot", "uri": "urn:sha256:" + "c" * 64, "sha256": "c" * 64, "byte_size": 9, "media_type": "application/json",
                                   "role": "output", "availability": "referenced", "license": None}]
    ev_rec = store.submit(TOKENS["alice"], "ev", ev)["record"]
    index(d)
    items = d.search("braking snapshot", mode="hybrid")["items"]
    art = next(i for i in items if i["type"] == "artifact")
    assert art["artifact_sha256"] == "c" * 64 and art["ref"] == ref(ev_rec) and art["kind"] == "Evidence"


def test_kind_filter_and_event_default_exclusion(seeded):
    store, d, recs = seeded
    index(d)
    assert all(i["kind"] == "Claim" for i in d.search("automobile", kind="Claim", mode="hybrid")["items"])
    assert not any(i["kind"] == "Event" for i in d.search("record proposed", mode="hybrid")["items"])
    assert any(i["kind"] == "Event" for i in d.search("record_proposed", kind="Event", mode="vector")["items"])


def test_fallback_is_lexical_and_labelled_when_vectors_or_provider_are_unavailable(seeded):
    store, d, recs = seeded
    # empty index
    r = d.search("automobile", mode="hybrid")
    assert r["mode"] == "lexical" and r["requested_mode"] == "hybrid" and "index is empty" in r["unavailable_reason"]
    assert any(i["ref"]["id"] == "car-claim" for i in r["items"]), "lexical results still come back"
    index(d)
    for embedder, q in ((None, "automobile"), (Double(fail_all=True), "automobile braking never embedded before")):  # a cached query would (rightly) still be served
        r = Discovery(store, embedder).search(q, mode="hybrid")
        assert r["mode"] == "lexical" and r["unavailable_reason"] and r["requested_mode"] == "hybrid"
        assert q != "automobile" or any(i["ref"]["id"] == "car-claim" for i in r["items"])
    assert Discovery(store, None).search("automobile", mode="lexical")["mode"] == "lexical" and "unavailable_reason" not in Discovery(store, None).search("automobile", mode="lexical")


def test_query_cache_rate_limit_timeout_and_cache_only(seeded):
    store, d, recs = seeded
    index(d)
    emb = d.embedder
    d.search("automobile", mode="vector")
    d.search("  AUTOMOBILE ", mode="vector")
    assert emb.calls["queries"] == 1, "normalised repeat served from the in-process cache"
    fresh = Discovery(store, emb)  # a new process: the persisted cache table answers
    fresh.search("automobile", mode="vector")
    assert emb.calls["queries"] == 1
    with store.connection() as c:
        assert c.execute("SELECT hits FROM discovery_query_cache").fetchone()["hits"] >= 1
    # autocomplete path: never calls the provider
    miss = fresh.search("brand new words", mode="hybrid", cache_only=True)
    assert miss["mode"] == "lexical" and "autocomplete never calls the provider" in miss["unavailable_reason"] and emb.calls["queries"] == 1
    # rate limit on live provider calls
    lim = Discovery(store, Double(), live_query_limit=2)
    lim.search("alpha", mode="vector"); lim.search("beta", mode="vector")
    third = lim.search("gamma", mode="hybrid")
    assert third["mode"] == "lexical" and "rate limit" in third["unavailable_reason"] and lim.embedder.calls["queries"] == 2
    # timeout bound
    slow = Discovery(store, Double(delay=1.5), query_timeout=0.2)
    t0 = time.monotonic()
    r = slow.search("delta", mode="hybrid")
    assert time.monotonic() - t0 < 1.0 and r["mode"] == "lexical" and "exceeded" in r["unavailable_reason"]


def test_validation_and_module_level_wrapper(seeded):
    store, d, _ = seeded
    for bad in ({"query": ""}, {"query": "x" * 201}, {"query": "ok", "kind": "Nope"}, {"query": "ok", "limit": 0}, {"query": "ok", "limit": 51}, {"query": "ok", "mode": "magic"}, {"query": 5}):
        with pytest.raises(FrontierError):
            d.search(**bad)
    index(d)
    r = search(store, "automobile", limit=3, mode="hybrid", embedder=d.embedder)
    assert r["mode"] == "hybrid" and len(r["items"]) <= 3


# ---- the hosted provider adapter, offline -----------------------------------------------------------------------------------
class FakeResp:
    def __init__(self, body): self.body = json.dumps(body).encode()
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_gemini_adapter_request_shape_normalisation_and_error_hygiene(monkeypatch, tmp_path):
    seen = {}
    secret = "test-only-not-a-real-embedding-key"
    env = tmp_path / "g.env"
    env.write_text(f"OTHER=1\nGEMINI_API_KEY={secret}\n")

    def fake(req, timeout=None):
        seen["url"], seen["headers"], seen["body"], seen["timeout"] = req.full_url, dict(req.header_items()), json.loads(req.data), timeout
        n = len(seen["body"].get("requests", [1]))
        v = [3.0, 4.0] + [0.0] * (DIMENSIONS - 2)
        return FakeResp({"embeddings": [{"values": v}] * n} if "requests" in seen["body"] else {"embedding": {"values": v}})
    monkeypatch.setattr("urllib.request.urlopen", fake)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    g = GeminiEmbedder(env_file=str(env), timeout=5)
    out = g.embed_documents(["a", "b"])
    assert seen["url"].endswith("/models/gemini-embedding-001:batchEmbedContents") and seen["headers"]["X-goog-api-key"] == secret and seen["timeout"] == 5
    assert all(r["taskType"] == "RETRIEVAL_DOCUMENT" and r["outputDimensionality"] == 768 for r in seen["body"]["requests"])
    assert abs(sqrt(sum(x * x for x in out[0])) - 1.0) < 1e-9 and secret not in json.dumps(seen["body"]) and secret not in seen["url"]
    q = g.embed_query("hello")
    assert seen["url"].endswith(":embedContent") and seen["body"]["taskType"] == "RETRIEVAL_QUERY" and abs(q[0] - 0.6) < 1e-9
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(Unavailable) as e:
        g.embed_query("x")
    assert "HTTP 429" in str(e.value) and secret not in str(e.value)
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeResp({"embedding": {"values": [1.0, 2.0]}}))
    with pytest.raises(Unavailable, match="unexpected shape"):
        g.embed_query("x")
    with pytest.raises(Unavailable, match="no embedding credential"):
        GeminiEmbedder(env_file=str(tmp_path / "missing.env")).embed_query("x")


def test_vec_literal_round_trips_through_pgvector(store):
    d = Discovery(store, Double())
    d.initialize()
    v = [0.0] * DIMENSIONS
    v[3] = 1.0
    with store.connection() as c:
        pass
    got = d._with_conn(lambda c: c.execute("SELECT (%s::vector <=> %s::vector) AS dist", (vec_literal(v), vec_literal(v))).fetchone()["dist"])
    assert abs(got) < 1e-9
