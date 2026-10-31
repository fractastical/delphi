"""The register import, and the line it draws between recording a problem and acting on one.

The register is morphoswarm's curated open-problems file: 250 sourced biology questions, each
with a PMC id, a locator and a verbatim quote. It states what is unknown and why it matters. It
does not state what would settle the question, what would refute an answer, what to do next or
when to stop -- and those four fields are exactly what an Action needs. These tests pin that the
importer never invents them, and that the store refuses to execute against a problem that lacks
them.
"""
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from frontier.models import ACTIONABILITY, Draft, Problem, ref
from frontier.store import Conflict
from conftest import TOKENS, action

REPO = Path(__file__).resolve().parent.parent
REGISTER = Path("/home/ubuntu/git/morphoswarm/data/problems/register.yaml")


def a_recorded_problem(store, id="recorded-problem"):
    return {"namespace": store.namespace, "kind": "Problem", "id": id, "issuer": "alice",
            "source_uri": "urn:frontier:protocol-test",
            "payload": {"title": "A sourced question with no stated way to settle it",
                        "known_state": "A fixture standing in for a curated register entry.",
                        "question": "What would settle this?",
                        "problem_kind": "sourced_field_open_problem",
                        "novelty_status": "Curated elsewhere; not re-checked here.",
                        "data_access": "No data requirement stated.",
                        "completeness": "recorded",
                        "required_capabilities": [], "downstream_uses": [],
                        "source": {"uri": "https://example.org/paper", "locator": "INTRODUCTION",
                                   "source_version": None, "content_sha256": None,
                                   "content_available": False, "access": "Public reference; bytes not retrieved.",
                                   "license": None}}}


def test_recorded_problem_may_omit_every_actionability_field():
    payload = a_recorded_problem.__wrapped__ if hasattr(a_recorded_problem, "__wrapped__") else None
    draft = a_recorded_problem(type("S", (), {"namespace": "node-a"})())
    problem = Problem.model_validate(draft["payload"])
    assert problem.completeness == "recorded"
    assert [f for f in ACTIONABILITY if not getattr(problem, f)] == list(ACTIONABILITY)


def test_actionable_problem_must_carry_all_four_and_names_the_missing_ones():
    payload = dict(a_recorded_problem(type("S", (), {"namespace": "node-a"})())["payload"])
    payload["completeness"] = "actionable"
    with pytest.raises(ValueError) as caught:
        Problem.model_validate(payload)
    message = str(caught.value)
    for field in ACTIONABILITY:
        assert field in message, f"{field} should be named in the refusal"


def test_store_refuses_an_action_against_a_recorded_problem(store):
    recorded = store.submit(TOKENS["alice"], "recorded", a_recorded_problem(store))["record"]
    with pytest.raises(Conflict, match="recorded, not actionable"):
        store.submit(TOKENS["alice"], "act-on-recorded", action(store, ref(recorded)))

    # Control: the SAME action succeeds once the four fields exist, so the refusal is caused by
    # actionability and not by the problem being a Problem.
    promoted = a_recorded_problem(store, "promoted-problem")
    promoted["payload"] |= {"completeness": "actionable",
                            "acceptance_criteria": ["An independent reviewer confirms the stated bound."],
                            "falsifiers": ["A counterexample within the stated scope."],
                            "next_action": "State the projection and freeze the target.",
                            "cost_stop_bounds": "At most 600 seconds of local compute; stop on a counterexample."}
    actionable = store.submit(TOKENS["alice"], "promoted", promoted)["record"]
    assert store.submit(TOKENS["alice"], "act-on-actionable", action(store, ref(actionable)))["record"]


@pytest.mark.skipif(not REGISTER.exists(), reason="morphoswarm register not present on this host")
def test_whole_register_imports_and_none_of_it_is_actionable(store, tmp_path):
    out = tmp_path / "drafts.jsonl"
    done = subprocess.run([sys.executable, str(REPO / "scripts" / "import_register.py"), str(REGISTER),
                           "--out", str(out)], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["rejected"] == 0
    assert report["importable"] == report["problems_in_register"] >= 250
    # The finding, pinned: every problem comes in, and not one of them can be acted on.
    assert report["actionable"] == 0
    assert report["recorded_not_actionable"] == report["importable"]

    drafts = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(drafts) == report["importable"]
    for draft in drafts:
        Draft.model_validate(draft)
        problem = Problem.model_validate(draft["payload"])
        assert problem.completeness == "recorded"
        # Nothing was invented to make them import.
        assert [f for f in ACTIONABILITY if not getattr(problem, f)] == list(ACTIONABILITY)
        # Provenance survives the mapping.
        assert problem.source.content_available is False, "the importer must not claim it holds the bytes"
        assert draft["payload"]["original"].get("register_record") or \
               draft["payload"]["original"].get("register_record_sha256")

    # Provenance, measured rather than assumed. The register carries THREE provenance fields; they are counted separately.
    fields = report["source_fields_in_register"]
    chosen = report["source_chosen_for_the_draft"]
    with_uri = sum(1 for d in drafts if d["payload"]["source"]["uri"])
    assert with_uri == chosen["any_source"]
    assert chosen["why_source"] + chosen["attestation_open_with_locator_and_quote"] + chosen["references_topic_only"] \
        + chosen["no_resolvable_source"] == report["importable"]
    assert fields["attestations"]["entries"] == sum(len(d["payload"]["original"]["register_provenance"]["attestations"]) for d in drafts)
    assert fields["references"]["entries"] == sum(len(d["payload"]["original"]["register_provenance"]["references"]) for d in drafts)
    # The earlier 148 "no source at all" was the previous importer ignoring `attestations`; it is reproduced, not hidden.
    prev = report["previous_mapping"]
    assert prev["why_source"] + prev["references"] + prev["none"] == report["importable"]
    assert chosen["no_resolvable_source"] <= prev["none"]
    if report["register_sha256"].startswith("a0155552"):
        assert (prev["why_source"], prev["references"], prev["none"]) == (34, 68, 148)
        assert (fields["attestations"]["problems"], fields["attestations"]["entries"], fields["attestations"]["entries_with_pmcid"],
                fields["attestations"]["entries_with_url_only"]) == (250, 465, 462, 3)
        assert fields["attestations"]["by_stance"] == {"open": 416, "settled": 49}
        assert fields["attestations"]["problems_with_a_settled_facet"] == 37
        assert fields["references"]["problems"] == 74 and fields["references"]["entries"] == 108
        assert fields["why_source"]["problems"] == 34
        assert chosen["no_resolvable_source"] == 0 and chosen["attestation_open_with_locator_and_quote"] == 216
    # A curator's question is never labelled as a primary-literature open problem, and nothing was promoted.
    assert report["problem_kind_used"] == ["project_gap"]
    assert all(d["payload"]["problem_kind"] == "project_gap" and d["payload"]["completeness"] == "recorded" for d in drafts)
    # Citations only: every quote, locator and identifier in a draft is exactly one the register carries.
    import yaml
    register = {p["slug"]: p for p in yaml.safe_load(REGISTER.read_text())["problems"]}
    for d in drafts:
        rec = register[d["id"]]
        prov = d["payload"]["original"]["register_provenance"]
        assert [(x["pmcid"], x["url"], x["locator"], x["quote"], x["stance"], x["kind"]) for x in prov["attestations"]] == \
               [(x.get("pmcid"), x.get("url"), x.get("locator"), x.get("quote"), x.get("stance"), x.get("kind")) for x in rec["attestations"]]
        assert prov["references"] == (rec.get("references") or []) and prov["why_source"] == (rec.get("why_source") or None)
        assert all(x["quote_checked_against_source"] is False for x in prov["attestations"])
    # The path that fed `source` must say what it is, and nothing stronger than it is.
    for d in drafts:
        path = d["payload"]["original"]["provenance_path"]
        src = d["payload"]["source"]
        if path == "none":
            assert src["uri"] is None and "NO resolvable source" in src["access"]
        elif path == "references":
            assert src["locator"] is None and "WEAKER" in src["access"]
        elif path == "attestation":
            assert src["locator"] and "curator's transcription" in src["access"]
            assert "not that the question as phrased is a primary-literature open problem" in src["access"]

    # A real one goes into the store and is still refused an action.
    first = drafts[0] | {"issuer": "alice"}
    saved = store.submit(TOKENS["alice"], "register-0", first)["record"]
    with pytest.raises(Conflict, match="recorded, not actionable"):
        store.submit(TOKENS["alice"], "act-register-0", action(store, ref(saved)))


def _claim_with_source(store, id, **source_changes):
    from conftest import claim
    draft = claim(store, id)
    draft["payload"]["source"] = {**draft["payload"]["source"], **source_changes}
    return draft


def test_unlicensed_held_content_is_refused_at_every_boundary(store, stores):
    """A commons built on export/import must not launder redistribution rights.

    The FIRST version of this gate guarded only `export_bundle`, and an independent reviewer
    found the hole within the hour: `store.get` returns the full record envelope, so the same
    record was refused on export and served on read, while the export test went on passing.
    That is the shape this repo keeps meeting -- a gate that is off looks exactly like a gate
    that passed -- so the rule is now enforced at the door and on the way out, and this test
    checks every boundary rather than the one that was convenient to write.
    """
    from frontier.models import ref
    from frontier.store import Forbidden

    offending = _claim_with_source(store, "unlicensed", content_available=True, license=None)

    # 1. The door. Nothing unlicensed is stored in the first place.
    with pytest.raises(Forbidden, match="unstated licence"):
        store.submit(TOKENS["alice"], "unlicensed", offending)

    # 2. The read path -- the exit the first version missed. Exercised directly on the helper,
    #    since submit now refuses to create such a record for us to read back.
    from frontier.store import _unlicensed_available_content
    synthetic = {"kind": "Claim", "id": "smuggled",
                 "payload": {"source": {"content_available": True, "license": None}}}
    assert _unlicensed_available_content([synthetic]) == ["Claim/smuggled"]
    assert _unlicensed_available_content([{"kind": "Claim", "id": "ok", "payload": {
        "source": {"content_available": True, "license": "CC-BY-4.0"}}}]) == []

    # 3. Import. A peer asserting it holds content does not give us the right to hold it.
    licensed = _claim_with_source(store, "licensed", content_available=True, license="CC-BY-4.0")
    ok = store.submit(TOKENS["alice"], "licensed", licensed)["record"]
    bundle = store.export_bundle([ref(ok)])
    tampered = deepcopy(bundle)
    tampered["records"][0]["payload"]["source"]["license"] = None
    from frontier.models import digest as _digest
    tampered["records"][0]["version"] = _digest(
        {k: v for k, v in tampered["records"][0].items() if k != "version"})
    body = {k: v for k, v in tampered.items() if k != "bundle_sha256"}
    tampered["bundle_sha256"] = _digest(body)
    other = stores("node-b")
    with pytest.raises(Forbidden, match="unstated licence"):
        other.import_bundle(TOKENS["bob"], "imp-unlicensed", tampered)

    # Control 1: a stated licence passes the door AND exports.
    assert store.export_bundle([ref(ok)])["records"]
    assert store.get(ref(ok), TOKENS["alice"])["record"]

    # Control 2: a reference whose bytes we do NOT claim to hold needs no licence at all.
    # Sharing the digest of something you may not redistribute is exactly what is allowed.
    reference = _claim_with_source(store, "reference-only", content_available=False, license=None)
    pointer = store.submit(TOKENS["alice"], "reference-only", reference)["record"]
    assert store.export_bundle([ref(pointer)])["records"]
    assert store.get(ref(pointer), TOKENS["alice"])["record"]

    # Control 3: the refusal names the offender rather than failing anonymously.
    with pytest.raises(Forbidden, match=r"Claim/unlicensed"):
        store.submit(TOKENS["alice"], "unlicensed-again", offending)


PROPOSALS = Path("/data/artifacts/delphi-evolve-rethink/messages/sourced-problems-proposal.json")


@pytest.mark.skipif(not PROPOSALS.exists(), reason="sourced proposals not present on this host")
def test_sourced_problems_are_actionable_and_close_the_loop(store, tmp_path):
    """Curation discipline is the difference, and it is measurable.

    The curated register gives 250 problems, 0 actionable, 40.8% carrying any source. Problems
    sourced to a retrieved identifier with a locator and a substring-checked quote give 15 of 17
    actionable and 100% with a resolvable URI. Same schema, same importer contract, opposite
    result -- so `0 of 250` is a statement about how the register was built, not about the bar.
    """
    from frontier.models import ref

    out = tmp_path / "sourced.jsonl"
    done = subprocess.run([sys.executable, str(REPO / "scripts" / "import_sourced_problems.py"),
                           str(PROPOSALS), "--out", str(out)], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["rejected"] == 0
    assert report["actionable"] >= 1
    assert report["with_resolvable_source_uri"] == report["importable"]
    # Nothing claims to hold bytes, so none of these can trip the export licence gate.
    drafts = [json.loads(line) for line in out.read_text().splitlines()]
    for d in drafts:
        assert d["payload"]["source"]["content_available"] is False

    actionable = next(d for d in drafts if d["payload"]["completeness"] == "actionable")
    saved = store.submit(TOKENS["alice"], "sourced-actionable", actionable | {"issuer": "alice"})["record"]

    # THE LOOP: a sourced problem that states what would settle it can carry an Action, be made
    # ready, and be leased by a worker. This is what `recorded` problems cannot do.
    act = store.submit(TOKENS["alice"], "act-sourced", action(store, ref(saved)))["record"]
    store.transition(TOKENS["alice"], "ready-sourced", ref(act), "ready")
    lease = store.lease(TOKENS["carol"], "lease-sourced", ref(act))
    assert lease["state"] == "leased" and lease["lease_id"]

    # And it exports, because it carries a resolvable source and claims no content bytes.
    bundle = store.export_bundle([ref(saved)])
    assert bundle["records"] and bundle["bundle_sha256"]

    # Control: the recorded ones still cannot be acted on, so the gate did not simply go away.
    rec = [d for d in drafts if d["payload"]["completeness"] == "recorded"]
    if rec:
        r = store.submit(TOKENS["alice"], "sourced-recorded", rec[0] | {"issuer": "alice"})["record"]
        # A distinct record id: conftest.action() always uses "action", and this test already
        # submitted one, so reusing it fails on a stale predecessor and would mask the real gate.
        blocked = action(store, ref(r)) | {"id": "action-against-recorded"}
        with pytest.raises(Conflict, match="recorded, not actionable"):
            store.submit(TOKENS["alice"], "act-sourced-recorded", blocked)


# ---------------------------------------------------------------------------------------------------------------------
# Synthetic registers: the attestation salvage, without depending on the host's register file.
# ---------------------------------------------------------------------------------------------------------------------
sys.path.insert(0, str(REPO / "scripts"))
import import_register as ir  # noqa: E402


def entry(slug="q", **changes):
    p = {"slug": slug, "statement": "Does X cause Y?", "why_it_matters": "Because Z.", "tags": [], "attestations": []}
    p.update(changes)
    return p


def att(pmcid="PMC1", locator="Results", quote="  A quote, exactly as transcribed — with “marks” and  double  spaces. ", stance="open", kind="research", **extra):
    return {"pmcid": pmcid, "locator": locator, "quote": quote, "stance": stance, "kind": kind, **extra}


def valid(draft):
    Draft.model_validate(draft)
    return Problem.model_validate(draft["payload"])


def test_attestation_is_salvaged_verbatim_without_promotion_or_a_primary_field_label():
    q = att()
    d = ir.to_draft(entry(attestations=[q]))
    problem = valid(d)
    assert problem.completeness == "recorded" and not problem.next_action and not problem.falsifiers
    assert problem.problem_kind == "project_gap" and problem.problem_kind != "sourced_field_open_problem"
    assert problem.source.uri == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1/" and problem.source.locator == "Results"
    assert problem.source.content_available is False and problem.source.content_sha256 is None
    assert "not checked against the source" in problem.source.access and "primary-literature" in problem.source.access
    kept = d["payload"]["original"]["register_provenance"]["attestations"][0]
    assert kept["quote"] == q["quote"], "the quote is copied unmodified: no strip, no normalisation, no truncation"
    assert kept["quote_checked_against_source"] is False and kept["uri"] == problem.source.uri
    assert d["payload"]["original"]["provenance_path"] == "attestation"


def test_why_source_still_wins_and_references_stay_a_weaker_separate_path():
    ws = {"pmcid": "PMC9", "locator": "Intro", "quote": "From why_source."}
    d = ir.to_draft(entry(why_source=ws, attestations=[att()], references=[{"pmcid": "PMC5", "role": "background", "note": "n"}]))
    assert d["payload"]["original"]["provenance_path"] == "why_source" and d["payload"]["source"]["uri"].endswith("PMC9/")
    prov = d["payload"]["original"]["register_provenance"]
    assert prov["why_source"] == ws and len(prov["attestations"]) == 1 and len(prov["references"]) == 1, "the three fields stay separate"
    d = ir.to_draft(entry(attestations=[], references=[{"pmcid": "PMC5", "role": "background", "note": "n"}]))
    assert d["payload"]["original"]["provenance_path"] == "references" and d["payload"]["source"]["locator"] is None
    assert "WEAKER" in d["payload"]["source"]["access"]


def test_a_settled_attestation_never_stands_as_the_source_of_openness_but_is_kept_and_counted():
    d = ir.to_draft(entry(attestations=[att(pmcid="PMC1", stance="settled", quote="settled one"), att(pmcid="PMC2", quote="open one")]))
    assert d["payload"]["source"]["uri"].endswith("PMC2/") and "entry 1 of 2" in d["payload"]["source"]["access"]
    assert "1 of 2 attestations have stance settled" in d["payload"]["source"]["access"]
    only_settled = ir.to_draft(entry(attestations=[att(stance="settled", quote="settled only")]))
    assert only_settled["payload"]["original"]["provenance_path"] == "none" and only_settled["payload"]["source"]["uri"] is None
    assert "NO resolvable source" in only_settled["payload"]["source"]["access"]
    assert only_settled["payload"]["original"]["register_provenance"]["attestations"][0]["quote"] == "settled only"
    assert "1 settled" in only_settled["payload"]["novelty_status"]


def test_url_only_attestation_resolves_and_an_unresolvable_one_is_kept_not_used():
    d = ir.to_draft(entry(attestations=[{"url": "https://example.org/prize", "locator": "page", "quote": "q", "stance": "open", "kind": "challenge-list"}]))
    assert d["payload"]["source"]["uri"] == "https://example.org/prize" and d["payload"]["original"]["provenance_path"] == "attestation"
    nothing = ir.to_draft(entry(attestations=[{"locator": "x", "quote": "q", "stance": "open", "kind": "research"}]))
    assert nothing["payload"]["original"]["provenance_path"] == "none"
    assert len(nothing["payload"]["original"]["register_provenance"]["attestations"]) == 1
    odd = ir.to_draft(entry(attestations=["not a mapping", att()]))
    assert odd["payload"]["original"]["register_provenance"]["attestations"][0]["raw"] == "not a mapping"
    assert odd["payload"]["source"]["uri"].endswith("PMC1/"), "an odd entry does not hide a usable one"


def test_oversize_record_drops_the_whole_copy_first_then_digests_quotes_but_never_truncates_them():
    many = [att(pmcid=f"PMC{i}", quote=("q%02d " % i) * 700) for i in range(30)]      # ~2,800 characters each
    big = entry(attestations=many, tags=["pad"], curator_note="x" * 20000)
    d = ir.to_draft(big)
    from frontier.models import canonical
    assert len(canonical(d).encode()) <= 65536
    o = d["payload"]["original"]
    assert "register_record" not in o and o["register_record_omitted"] and len(o["register_record_sha256"]) == 64
    atts = o["register_provenance"]["attestations"]
    assert len(atts) == 30 and [x["pmcid"] for x in atts] == [f"PMC{i}" for i in range(30)], "no item disappears"
    for x, original in zip(atts, many):
        if x["quote"] is None:
            assert x["quote_omitted_for_size"] and len(x["quote_sha256"]) == 64
        else:
            assert x["quote"] == original["quote"], "a kept quote is whole; a shortened quote would be a fabricated passage"
    assert any(x["quote"] is None for x in atts)


def test_report_counts_the_three_fields_separately():
    problems = [entry("a", attestations=[att("PMC1"), att("PMC1", stance="settled", quote="s")]),
                entry("b", attestations=[att("PMC1")], references=[{"pmcid": "PMC7", "role": "r", "note": "n"}, {"role": "no id"}]),
                entry("c", why_source={"pmcid": "PMC3", "locator": "l", "quote": "q"}),
                entry("d", attestations=[], references=[{"pmcid": "PMC8", "role": "r", "note": "n"}]),
                entry("e")]
    f = ir.register_field_counts(problems)
    assert f["why_source"] == {"problems": 1, "with_pmcid_locator_quote": 1}
    assert f["references"]["problems"] == 2 and f["references"]["entries"] == 3 and f["references"]["resolvable_entries"] == 2
    assert f["references"]["problems_with_a_resolvable_entry"] == 2 and f["references"]["carry_locator_or_quote"] == 0
    a = f["attestations"]
    assert (a["problems"], a["entries"], a["distinct_sources"], a["max_problems_sharing_one_source"]) == (2, 3, 1, 2)
    assert a["by_stance"] == {"open": 2, "settled": 1} and a["problems_with_a_settled_facet"] == 1 and a["problems_with_every_attestation_settled"] == 0
    assert a["problems_resting_on_exactly_one_distinct_source"] == 2
    assert f["problems_with_none_of_the_three"] == 1
    assert [ir.legacy_provenance_path(p) for p in problems] == ["none", "references", "why_source", "references", "none"]
