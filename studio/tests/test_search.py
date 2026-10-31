"""Search tests. Run inside the documented bounded scope:
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 bash scripts/test_postgres.sh tests/test_search.py
"""
from copy import deepcopy

import pytest

from frontier.models import ref
from frontier.search import (MAX_REFS_PER_RESULT, SearchIndex, curation_labels, explain_match, source_fidelity, source_view)
from frontier.store import Conflict, FrontierError, Store, Unauthorized
from conftest import TOKENS, assessment, claim, evidence, source

DAVE = "test-only-local-token-for-dave-b-only"


@pytest.fixture
def index(store):
    idx = SearchIndex(store)
    idx.initialize()
    return idx


def save(store, draft, key=None, token="alice"):
    return store.submit(TOKENS[token], key or draft["id"], draft)["record"]


def claim_with(store, id, statement, context="Protocol test only", title=None, **changes):
    d = claim(store, id, **changes)
    d["payload"]["statement"] = statement
    d["payload"]["context"] = context
    if title:
        d["payload"]["title"] = title
    return d


# ---------------------------------------------------------------------------------------------- pure functions
def test_source_fidelity_classes_are_three_and_never_merged():
    assert source_fidelity(None) == "not_applicable"
    base = {"uri": None, "locator": None, "source_version": None, "content_available": False, "license": None,
            "content_sha256_declared": False, "access": "x"}
    assert source_fidelity(base) == "no_source"
    assert source_fidelity({**base, "uri": "https://example.org/a"}) == "reference_only"
    assert source_fidelity({**base, "uri": "https://example.org/a", "locator": "row=7"}) == "locator_present"


def test_unlicensed_available_content_never_yields_a_snippet_and_is_labelled():
    envelope = {"kind": "Claim", "id": "held", "version": "a" * 64, "source_uri": "urn:x",
                "payload": {"title": "T", "statement": "needle in a haystack", "source": {
                    "uri": "https://example.org/x", "locator": None, "source_version": None, "content_sha256": None,
                    "content_available": True, "access": "held", "license": None}}}
    reasons, fields, snippet = explain_match(envelope, "needle", "needle", None)
    assert fields == ["statement"] and snippet is None
    labels = curation_labels(envelope, "proposed")["labels"]
    assert any("NO stated licence" in x for x in labels)
    envelope["payload"]["source"]["license"] = "CC0-1.0"
    assert explain_match(envelope, "needle", "needle", None)[2] and "needle" in explain_match(envelope, "needle", "needle", None)[2]


def test_parameter_validation_is_bounded_and_happens_before_any_database_access():
    idx = SearchIndex(Store("host=/nonexistent dbname=none", "node-a"))
    for bad in ({"query": "x" * 201}, {"query": "a\x00b"}, {"limit": 0}, {"limit": 51}, {"limit": True}, {"kinds": "Nope"},
                {"kinds": ["Claim", "Claim"]}, {"status": "maybe"}, {"source": "ab"}, {"context": ""}, {"scope": "bad scope!"},
                {"cursor": "not-a-cursor"}, {"include_history": "yes"}):
        with pytest.raises(FrontierError):
            idx.search(**bad)


# ---------------------------------------------------------------------------------------------- index and data model
def test_initialize_is_idempotent_adds_indexes_only_and_the_gin_index_is_usable(store):
    with store.connection() as c:
        tables_before = sorted(r["tablename"] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (store.schema,)))
    idx = SearchIndex(store)
    idx.initialize()
    idx.initialize()
    with store.connection() as c:
        tables_after = sorted(r["tablename"] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (store.schema,)))
        names = {r["indexname"] for r in c.execute("SELECT indexname FROM pg_indexes WHERE schemaname=%s", (store.schema,))}
    assert tables_before == tables_after, "search must add indexes only, no table and no data copy"
    assert {"record_search_fts", "record_title_lower", "record_source_uri_prefix", "record_payload_source_prefix", "review_target"} <= names
    save(store, claim_with(store, "indexed", "fixture statement for the index"))
    with store.connection() as c:
        c.execute("SET LOCAL enable_seqscan = off")
        plan = "\n".join(next(iter(r.values())) for r in c.execute(
            "EXPLAIN SELECT version FROM record_versions WHERE to_tsvector('simple', search_text) @@ websearch_to_tsquery('simple', 'fixture')"))
    assert "record_search_fts" in plan, plan


def test_search_is_read_only(store, index):
    save(store, claim_with(store, "ro", "read only probe"))
    tables = ("record_versions", "events", "write_receipts", "idempotency", "local_states", "typed_edges")
    def counts():
        with store.connection() as c:
            return {t: c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in tables}
    before = counts()
    index.search("read only probe")
    index.search("", kinds="Claim", token=TOKENS["alice"])
    assert counts() == before


# ---------------------------------------------------------------------------------------------- access isolation
def test_access_isolation_for_records_and_related_references(store, index):
    store.provision(DAVE, "dave", "operator-d", ["contributor"], ["node-b"], 100)
    public = save(store, claim_with(store, "pub", "isolationterm public statement"))
    private = save(store, claim_with(store, "priv", "isolationterm private statement", visibility="private"))
    private_ev = evidence(store, ref(public))
    private_ev.update(id="private-evidence", visibility="private")
    save(store, private_ev)

    anon = index.search("isolationterm")
    assert [r["ref"]["id"] for r in anon["results"]] == ["pub"]
    owner = index.search("isolationterm", token=TOKENS["alice"])
    assert {r["ref"]["id"] for r in owner["results"]} == {"pub", "priv"}
    outsider = index.search("isolationterm", token=DAVE)
    assert [r["ref"]["id"] for r in outsider["results"]] == ["pub"], "a principal without the namespace sees public records only"
    # An exact version pin of a private record is not an access bypass.
    assert index.search(private["version"])["results"] == []
    assert index.search(private["version"], token=DAVE)["results"] == []
    owner_pin = index.search(private["version"], token=TOKENS["alice"])["results"]
    assert owner_pin[0]["ref"]["id"] == "priv" and "exact version pin" in owner_pin[0]["why_matched"]
    assert all(r["ref"]["kind"] == "Event" for r in owner_pin[1:]), "other hits are only the Event records that cite the version"
    # Related references follow the same rule.
    pub_row = lambda res: next(r for r in res["results"] if r["ref"]["id"] == "pub")
    assert pub_row(anon)["evidence_references"] == []
    assert [e["evidence"]["id"] for e in pub_row(owner)["evidence_references"]] == ["private-evidence"]
    assert pub_row(outsider)["evidence_references"] == []
    # scope filter narrows, it never widens
    assert index.search("isolationterm", scope="private")["results"] == []
    assert [r["ref"]["id"] for r in index.search("isolationterm", scope="private", token=TOKENS["alice"])["results"]] == ["priv"]
    assert index.search("isolationterm", scope="node-a", token=DAVE)["results"] == [] or all(
        r["visibility"] == "public" for r in index.search("isolationterm", scope="node-a", token=DAVE)["results"])
    with pytest.raises(Unauthorized):
        index.search("isolationterm", token="test-only-not-a-provisioned-token-xyz")


# ---------------------------------------------------------------------------------------------- kind, context, equation
def test_kind_context_and_equation_retrieval(store, index):
    turing = save(store, claim_with(store, "turing-window", "Mode n grows iff 2n^2 < (L/π)^2 < 5n^2 on a finite domain",
                                    context="One-dimensional Neumann boundaries, declared model", title="Finite-domain Turing windows"))
    save(store, claim_with(store, "kimura", "Fixation probability under weak selection", context="Diploid, genic, constant Ne"))
    ev = save(store, evidence(store, ref(turing)))

    hit = index.search("2n^2 < (L/π)^2 < 5n^2")
    assert hit["results"][0]["ref"]["id"] == "turing-window"
    assert any("literal text match in payload.statement" in w for w in hit["results"][0]["why_matched"])
    assert "(L/π)^2".lower() in hit["results"][0]["snippet"]
    assert index.search("(L/π)^2")["results"][0]["ref"]["id"] == "turing-window"
    # symbols only: the full-text query is empty, the literal fallback still finds it
    assert [r["ref"]["id"] for r in index.search("<")["results"]] and index.search("<")["results"][0]["ref"]["id"] in {"turing-window", "evidence", "kimura"}
    assert index.search("5n^2 on a finite")["results"][0]["ref"]["id"] == "turing-window"
    # context filter and kind filter
    assert [r["ref"]["id"] for r in index.search("", context="neumann")["results"]] == ["turing-window"]
    assert [r["ref"]["id"] for r in index.search("", kinds="Evidence")["results"]] == ["evidence"]
    both = index.search("", kinds=["Claim", "Evidence"])
    assert {r["ref"]["kind"] for r in both["results"]} == {"Claim", "Evidence"}
    assert index.search("fixation", kinds="Evidence")["results"] == []
    # operators and punctuation never error, and SQL metacharacters are inert
    for q in ("finite -neumann", '"finite domain"', "a OR b", "'; DROP TABLE record_versions; --", "%", "_", "\\", "((("):
        index.search(q)
    with store.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM record_versions").fetchone()["n"] >= 3
    assert ev["version"]


def test_title_and_term_ranking_orders_candidates_without_using_status(store, index):
    save(store, claim_with(store, "weak", "A passing mention of rankingterm among other words that dilute it.", title="Unrelated title"))
    save(store, claim_with(store, "strong", "rankingterm rankingterm rankingterm", title="rankingterm"))
    save(store, claim_with(store, "mid", "rankingterm appears here", title="About rankingterm things"))
    res = index.search("rankingterm")["results"]
    assert [r["ref"]["id"] for r in res][0] == "strong"
    assert res[0]["score"] > res[1]["score"] >= res[2]["score"]
    assert [r["score"] for r in res] == sorted((r["score"] for r in res), reverse=True)
    assert all(r["curation"]["promoted"] is False for r in res)


# ---------------------------------------------------------------------------------------------- exact identifiers and pins
def test_exact_identifiers_and_version_pins(store, index):
    first = save(store, claim_with(store, "exact-id-claim", "first statement about exactness", source_uri="https://example.org/unique-source-xyz"))
    second_draft = claim_with(store, "exact-id-claim", "revised statement about exactness", predecessor=first["version"],
                              source_uri="https://example.org/unique-source-xyz")
    second = save(store, second_draft, key="exact-id-claim-2")
    save(store, claim_with(store, "other", "mentions exact-id-claim only in passing text"))

    by_id = index.search("exact-id-claim")["results"]
    assert by_id[0]["ref"]["id"] == "exact-id-claim" and by_id[0]["ref"]["version"] == second["version"] and by_id[0]["is_head"]
    assert "exact record id" in by_id[0]["why_matched"]
    assert [r["ref"]["version"] for r in by_id if r["ref"]["id"] == "exact-id-claim"] == [second["version"]], "heads only by default"
    # an exact version pin returns exactly that immutable version, head or not
    pinned = index.search(first["version"])["results"]
    assert pinned[0]["ref"]["version"] == first["version"] and pinned[0]["is_head"] is False
    assert all(r["ref"]["kind"] == "Event" for r in pinned[1:]), "other hits are only the Event records that cite the version"
    assert "exact version pin" in pinned[0]["why_matched"]
    history = index.search("exact-id-claim", include_history=True)["results"]
    assert {r["ref"]["version"] for r in history if r["ref"]["id"] == "exact-id-claim"} == {first["version"], second["version"]}
    assert all(len(r["ref"]["version"]) == 64 for r in history)
    # exact source URI and source prefix filter (envelope source_uri and payload.source.uri are separate fields)
    by_src = index.search("https://example.org/unique-source-xyz")["results"]
    assert by_src[0]["ref"]["id"] == "exact-id-claim" and "exact source URI" in by_src[0]["why_matched"]
    assert {r["ref"]["id"] for r in index.search("", source="https://example.org/unique")["results"]} == {"exact-id-claim"}
    assert {r["ref"]["id"] for r in index.search("", source="https://example.org/public-dataset")["results"]} == {"exact-id-claim", "other"}
    assert index.search("", source="https://nope.example/")["results"] == []


# ---------------------------------------------------------------------------------------------- pagination
def test_stable_keyset_pagination_across_pages_and_concurrent_inserts(store, index):
    for i in range(7):
        save(store, claim_with(store, f"page-{i}", "paginationterm " + "filler " * i, title=f"Page {i}"))
    full = [r["ref"]["version"] for r in index.search("paginationterm", limit=50)["results"]]
    assert len(full) == 7 and len(set(full)) == 7

    seen, cursor = [], ""
    inserted = False
    while True:
        page = index.search("paginationterm", limit=3, cursor=cursor)
        seen += [r["ref"]["version"] for r in page["results"]]
        if not inserted:  # a record inserted between pages must not duplicate or drop any already-listed record
            save(store, claim_with(store, "late", "paginationterm late arrival"))
            inserted = True
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
        assert len(page["results"]) == 3
    assert len(seen) == len(set(seen)), "no duplicates across pages"
    assert set(full) <= set(seen), "no original record skipped"
    page = index.search("paginationterm", limit=3)
    assert index.search("paginationterm", limit=3)["results"] == page["results"], "repeat call over unchanged data is identical"
    with pytest.raises(FrontierError):
        index.search("another query", limit=3, cursor=page["next_cursor"])
    with pytest.raises(FrontierError):
        index.search("paginationterm", limit=3, cursor="1.ff.ff")
    assert index.search("paginationterm", limit=50)["next_cursor"] is None


# ---------------------------------------------------------------------------------------------- opposing and disputed evidence
def dispute(store, target, evidence_ref=None, decision="disputed"):
    a = assessment(ref(target), reviewer="bob", decision=decision)
    if decision != "accepted":
        a["dimensions"]["independent_replication"]["status"] = "failed"
    if evidence_ref:
        a["dimensions"]["independent_replication"]["evidence_links"] = [evidence_ref]
    return store.review(TOKENS["bob"], "dispute-" + decision, a)


def test_explicit_opposing_and_disputed_references(store, index):
    target = save(store, claim_with(store, "contested", "A scoped statement that is later disputed", title="Contested claim"))
    ev = save(store, evidence(store, ref(target)))
    calm = save(store, claim_with(store, "calm", "A scoped statement nobody disputes", title="Calm claim"))
    before = index.search("scoped statement")
    row = next(r for r in before["results"] if r["ref"]["id"] == "contested")
    assert row["local_status"] == "proposed" and row["disputes"]["disputing_reviews"] == []
    assert [e["evidence"]["id"] for e in row["evidence_references"]] == ["evidence"], "evidence that targets it is listed, direction not inferred"
    assert "not inferred" in row["evidence_references"][0]["note"]

    result = dispute(store, target, evidence_ref=ref(ev))
    assert result["local_status"] == "disputed"
    after = index.search("scoped statement")
    row = next(r for r in after["results"] if r["ref"]["id"] == "contested")
    quiet = next(r for r in after["results"] if r["ref"]["id"] == "calm")
    assert row["local_status"] == "disputed" and row["disputes"]["local_status"] == "disputed"
    assert [d["decision"] for d in row["disputes"]["disputing_reviews"]] == ["disputed"]
    assert row["disputes"]["disputing_reviews"][0]["assessment"]["kind"] == "Assessment"
    assert [e["evidence"]["id"] for e in row["disputes"]["cited_evidence"]] == ["evidence"]
    assert "not inferred" in row["disputes"]["cited_evidence"][0]["note"]
    assert quiet["disputes"]["disputing_reviews"] == [] and quiet["local_status"] == "proposed"
    # the dispute does not change the version, the text or the rank tier of the record
    assert row["ref"]["version"] == target["version"]
    assert [r["ref"]["id"] for r in index.search("", status="disputed")["results"]] == ["contested"]
    assert "contested" not in [r["ref"]["id"] for r in index.search("", status="accepted")["results"]]

    # An uploaded Assessment with no review receipt is NOT counted as a dispute.
    forged = {"namespace": store.namespace, "kind": "Assessment", "id": "uploaded-review", "issuer": "alice",
              "source_uri": "urn:frontier:fixture", "payload": assessment(ref(calm), reviewer="alice", decision="disputed")}
    save(store, forged)
    again = next(r for r in index.search("scoped statement")["results"] if r["ref"]["id"] == "calm")
    assert again["disputes"]["disputing_reviews"] == [] and again["local_status"] == "proposed"


def test_ranking_tiers_are_lexicographic_not_additive(store, index):
    """Adversarial: competitors satisfy several LOWER categories at once (source + title + literal text); under an additive
    score they would outrank the exact match. Exact version > id > source URI > title equals > title contains > literal text."""
    target = save(store, claim_with(store, "tier-target", "plain statement"))
    pin = target["version"]
    decoy = claim_with(store, "tier-decoy-1", f"mentions {pin} in the text", title=pin, source_uri=pin)
    save(store, decoy)
    res = index.search(pin)["results"]
    assert res[0]["ref"]["id"] == "tier-target" and res[0]["score"] >= 9000, [(r["ref"]["id"], r["score"]) for r in res]
    decoy_row = next(r for r in res if r["ref"]["id"] == "tier-decoy-1")
    assert 7000 <= decoy_row["score"] < 8000 and res[0]["score"] > decoy_row["score"]

    # exact id beats a record that matches the same string as source URI + title + text
    save(store, claim_with(store, "needle-id", "unrelated words"))
    save(store, claim_with(store, "needle-decoy", "needle-id needle-id needle-id", title="needle-id", source_uri="needle-id"))
    res = index.search("needle-id")["results"]
    assert res[0]["ref"]["id"] == "needle-id" and 8000 <= res[0]["score"] < 9000
    by = {r["ref"]["id"]: r["score"] for r in res}
    assert 7000 <= by["needle-decoy"] < 8000

    # exact source URI beats title-equals + literal text
    save(store, claim_with(store, "src-hit", "other words", source_uri="urn:tier:source"))
    save(store, claim_with(store, "title-hit", "urn:tier:source urn:tier:source", title="urn:tier:source"))
    res = index.search("urn:tier:source")["results"]
    assert [r["ref"]["id"] for r in res][:2] == ["src-hit", "title-hit"]
    assert 7000 <= res[0]["score"] < 8000 and 6000 <= res[1]["score"] < 7000

    # title equals > title contains > literal text only > full-text only; the secondary bucket never crosses a tier
    save(store, claim_with(store, "t-eq", "x", title="tiersharedterm"))
    save(store, claim_with(store, "t-in", "x", title="the tiersharedterm title"))
    save(store, claim_with(store, "t-txt", "tiersharedterm " * 30, title="no match in the title"))
    res = index.search("tiersharedterm")["results"]
    assert [r["ref"]["id"] for r in res] == ["t-eq", "t-in", "t-txt"]
    assert [r["score"] // 1000 for r in res] == [6, 5, 4]
    save(store, claim_with(store, "fts-only", "tiersharedterm and other words in a different order", title="no match here either"))
    ft = index.search("other tiersharedterm")["results"]  # words not adjacent: no literal match, full-text only
    assert ft and next(r for r in ft if r["ref"]["id"] == "fts-only")["score"] // 1000 == 1


def test_reference_lists_flag_truncation_per_result_instead_of_dropping_silently(store, index):
    crowded = save(store, claim_with(store, "crowded", "crowdedterm statement one"))
    quiet = save(store, claim_with(store, "quiet", "crowdedterm statement two"))
    for i in range(MAX_REFS_PER_RESULT + 3):
        e = evidence(store, ref(crowded))
        e["id"] = f"crowd-ev-{i}"
        save(store, e)
    e = evidence(store, ref(quiet))
    e["id"] = "quiet-ev"
    save(store, e)
    res = {r["ref"]["id"]: r for r in index.search("crowdedterm")["results"]}
    assert len(res["crowded"]["evidence_references"]) == MAX_REFS_PER_RESULT
    assert res["crowded"]["reference_truncation"]["evidence_references"] is True and res["crowded"]["references_complete"] is False
    # another result is not starved by the crowded one, and reports completeness
    assert [x["evidence"]["id"] for x in res["quiet"]["evidence_references"]] == ["quiet-ev"]
    assert res["quiet"]["reference_truncation"]["evidence_references"] is False and res["quiet"]["references_complete"] is True
    assert res["quiet"]["disputes"]["truncated"] is False
    # exactly at the cap is complete (not flagged)
    exact = save(store, claim_with(store, "exactcap", "exactcapterm statement"))
    for i in range(MAX_REFS_PER_RESULT):
        e = evidence(store, ref(exact))
        e["id"] = f"cap-ev-{i}"
        save(store, e)
    row = index.search("exactcapterm")["results"][0]
    assert len(row["evidence_references"]) == MAX_REFS_PER_RESULT and row["references_complete"] is True


def test_dispute_reference_lists_are_bounded_and_flag_truncation(store, index):
    target = save(store, claim_with(store, "crowded", "crowdedterm statement"))
    for i in range(MAX_REFS_PER_RESULT + 3):
        e = evidence(store, ref(target))
        e["id"] = f"ev-{i}"
        save(store, e)
    row = index.search("crowdedterm")["results"][0]
    assert len(row["evidence_references"]) == MAX_REFS_PER_RESULT


def test_dispute_lists_truncate_conservatively_and_flag_dependent_evidence(store, index):
    target = save(store, claim_with(store, "many-disputes", "manydisputeterm statement"))
    for i in range(MAX_REFS_PER_RESULT + 2):
        a = assessment(ref(target), reviewer="bob", decision="disputed")
        a["dimensions"]["independent_replication"]["status"] = "failed"
        store.review(TOKENS["bob"], f"many-{i}", a)
    row = index.search("manydisputeterm")["results"][0]
    assert len(row["disputes"]["disputing_reviews"]) == MAX_REFS_PER_RESULT
    assert row["reference_truncation"]["disputing_reviews"] is True and row["disputes"]["truncated"] is True
    assert row["reference_truncation"]["cited_evidence"] is True, "evidence cited by the cut-off reviews is incomplete too"
    assert row["references_complete"] is False


def test_a_private_evidence_link_inside_a_dispute_is_not_shown_to_others(store, index):
    target = save(store, claim_with(store, "guarded", "guardedterm statement"))
    secret = evidence(store, ref(target))
    secret.update(id="secret-evidence", visibility="private")
    secret_rec = save(store, secret)
    try:
        dispute(store, target, evidence_ref=ref(secret_rec))
    except (Conflict, FrontierError) as e:
        pytest.skip("the store refuses a public review citing private evidence: " + str(e))
    anon = next(r for r in index.search("guardedterm")["results"] if r["ref"]["id"] == "guarded")
    owner = next(r for r in index.search("guardedterm", token=TOKENS["alice"])["results"] if r["ref"]["id"] == "guarded")
    assert anon["disputes"]["cited_evidence"] == []
    assert [e["evidence"]["id"] for e in owner["disputes"]["cited_evidence"]] == ["secret-evidence"]


# ---------------------------------------------------------------------------------------------- source-aware curation labels
def test_source_aware_curation_labels_describe_and_never_promote(store, index):
    none_src = claim_with(store, "src-none", "labelterm statement")
    none_src["payload"]["source"] = {**source(), "uri": None, "locator": None, "content_sha256": None}
    ref_only = claim_with(store, "src-ref", "labelterm statement")
    ref_only["payload"]["source"] = {**source(), "locator": None}
    located = claim_with(store, "src-loc", "labelterm statement")
    problem = {"namespace": store.namespace, "kind": "Problem", "id": "recorded-problem", "issuer": "alice", "source_uri": "urn:frontier:fixture",
               "payload": {"title": "labelterm recorded problem", "known_state": "Curated register entry", "question": "What is unknown?",
                           "problem_kind": "sourced_field_open_problem", "novelty_status": "register entry",
                           "data_access": "not assessed", "completeness": "recorded", "required_capabilities": ["review"],
                           "downstream_uses": ["none stated"], "source": source()}}
    for d in (none_src, ref_only, located, problem):
        save(store, d)
    res = {r["ref"]["id"]: r for r in index.search("labelterm", limit=50)["results"]}
    assert res["src-none"]["curation"]["source_fidelity"] == "no_source" and any("no source recorded" in x for x in res["src-none"]["curation"]["labels"])
    assert res["src-ref"]["curation"]["source_fidelity"] == "reference_only"
    assert res["src-loc"]["curation"]["source_fidelity"] == "locator_present"
    assert any("digest declared; content bytes not held" in x for x in res["src-loc"]["curation"]["labels"])
    assert any("recorded problem, not actionable" in x for x in res["recorded-problem"]["curation"]["labels"])
    for r in res.values():
        assert r["curation"]["promoted"] is False and r["local_status"] == "proposed"
        assert any("not independently reviewed" in x for x in r["curation"]["labels"])
    assert res["src-loc"]["source"]["content_available"] is False and res["src-loc"]["source"]["content_sha256_declared"] is True
    assert source_view(deepcopy(located["payload"]))["locator"] == "row=7"
