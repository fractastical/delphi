"""The register import, and the line it draws between recording a problem and acting on one.

The register is morphoswarm's curated open-problems file: 250 sourced biology questions, each
with a PMC id, a locator and a verbatim quote. It states what is unknown and why it matters. It
does not state what would settle the question, what would refute an answer, what to do next or
when to stop -- and those four fields are exactly what an Action needs. These tests pin that the
importer never invents them, and that the store refuses to execute against a problem that lacks
them.
"""
import json
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

    # Provenance, measured rather than assumed. The first draft of this test asserted that
    # "the overwhelming majority" carry a source URI, generalised from the first record read.
    # It is false: most of the register is unsourced, and the test exists to keep that visible.
    provenance = report["provenance"]
    with_uri = sum(1 for d in drafts if d["payload"]["source"]["uri"])
    assert with_uri == provenance["any_source"]
    assert provenance["with_locator_and_quote"] + provenance["topic_reference_only"] \
        + provenance["no_source_at_all"] == report["importable"]
    # The unsourced majority must be labelled as such, never as a sourced open problem.
    unsourced = [d for d in drafts if d["payload"]["original"]["provenance_path"] == "none"]
    assert len(unsourced) == provenance["no_source_at_all"] > 0
    for d in unsourced:
        assert d["payload"]["source"]["uri"] is None
        assert "NO source" in d["payload"]["source"]["access"]
    # And the weak path must not be presented as supporting a specific statement.
    for d in drafts:
        if d["payload"]["original"]["provenance_path"] == "references":
            assert d["payload"]["source"]["locator"] is None
            assert "WEAKER" in d["payload"]["source"]["access"]

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


def test_export_refuses_held_content_under_an_unstated_licence(store):
    """A commons built on export/import must not launder redistribution rights.

    An independent review of the Paperclip Evidence API found zero occurrences of licence,
    copyright, terms-of-use or redistribution in its entire OpenAPI, while its `include_context`
    option returns article passages. An adapter written against it would set
    `content_available=true` with `license=None` and ship passages of unknown licence onward
    inside a bundle that advertises integrity.
    """
    from frontier.models import ref
    from frontier.store import Forbidden

    offending = _claim_with_source(store, "unlicensed", content_available=True, license=None)
    saved = store.submit(TOKENS["alice"], "unlicensed", offending)["record"]
    with pytest.raises(Forbidden, match="unstated licence"):
        store.export_bundle([ref(saved)])

    # Control 1: the SAME record exports once a licence is stated, so the refusal is caused by
    # the missing licence and not by the record or by export being broken.
    licensed = _claim_with_source(store, "licensed", content_available=True, license="CC-BY-4.0")
    ok = store.submit(TOKENS["alice"], "licensed", licensed)["record"]
    assert store.export_bundle([ref(ok)])["records"]

    # Control 2: a reference whose bytes we do NOT claim to hold exports with no licence at all.
    # Sharing the digest of something you may not redistribute is exactly what is allowed.
    reference = _claim_with_source(store, "reference-only", content_available=False, license=None)
    pointer = store.submit(TOKENS["alice"], "reference-only", reference)["record"]
    assert store.export_bundle([ref(pointer)])["records"]

    # And the refusal names the offender, so a caller can fix it rather than guess.
    with pytest.raises(Forbidden, match=r"Claim/unlicensed"):
        store.export_bundle([ref(ok), ref(saved)])


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
