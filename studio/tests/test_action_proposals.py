from copy import deepcopy

import pytest
from pydantic import ValidationError

from conftest import TOKENS, action, claim
from frontier.models import ActionProposal, Draft, make_record, ref
from frontier.store import Conflict, Missing


def proposal():
    return {"intent": "simulation", "method": "Compare two time steps on the same declared model",
            "assumptions": ["Software fixture, not a scientific result"],
            "alternatives": [{"label": "defer", "description": "Wait for measured parameters", "tradeoff": "Avoids uncalibrated model work but delays a numerical check"}],
            "expected_information": "Whether the current numerical result depends on time step",
            "decision_context": "Choose a numerical resolution before comparing candidate designs",
            "expected_outputs": ["Convergence report and trajectory hashes"],
            "controls": ["Analytically known zero-force trajectory"], "analysis_plan": "Compare errors against a frozen tolerance",
            "outcomes": [{"label": "converged", "criterion": "Error below the preregistered threshold", "decision_consequence": "Proceed to model applicability review"},
                         {"label": "inconclusive", "criterion": "Numerical check exceeds the bound", "decision_consequence": "Refine the model before design selection"}],
            "selection_basis": "manual", "selection_rationale": "A cheap check before an expensive sweep",
            "limitations": ["Convergence does not establish biological validity"]}


def saved_action(store, identifier):
    target = store.submit(TOKENS["alice"], "c-"+identifier, claim(store, "c-"+identifier))["record"]
    d = action(store, ref(target)) | {"id": identifier}
    d["payload"]["proposal"] = proposal()
    return store.submit(TOKENS["alice"], identifier, d)["record"]


def test_proposal_is_versioned_and_transfers_without_authority(stores):
    s, other = stores(), stores("node-b")
    a = saved_action(s, "check")
    assert s.get(ref(a))["record"]["payload"]["proposal"] == proposal()
    assert s.get(ref(a))["action"]["state"] == "proposed"
    bundle = s.export_bundle([a["payload"]["target"], ref(a)])
    other.import_bundle(TOKENS["alice"], "transfer", bundle)
    got = other.get(ref(a))
    assert got["record"] == a and got["local_review"]["status"] == "imported_unreviewed"
    # New optional fields do not normalize or rehash old records.
    old = action(s, a["payload"]["target"])
    assert "proposal" not in make_record(Draft.model_validate(old))["payload"]


def test_plan_steps_are_pinned_and_plan_is_not_an_execution_shortcut(store):
    a = saved_action(store, "step")
    d = action(store, a["payload"]["target"]) | {"id": "plan"}
    d["payload"]["proposal"] = proposal() | {"intent": "plan", "plan_steps": [ref(a)]}
    bad = deepcopy(d)
    bad["payload"]["proposal"]["plan_steps"][0]["version"] = "0" * 64
    with pytest.raises(Missing):
        store.submit(TOKENS["alice"], "missing-step", bad)
    plan = store.submit(TOKENS["alice"], "plan", d)["record"]
    with store.connection() as c:
        assert c.execute("SELECT target_version FROM typed_edges WHERE source_version=%s AND relation='plans_step'", (plan["version"],)).fetchone()["target_version"] == a["version"]
    with pytest.raises(Conflict, match="individual steps"):
        store.transition(TOKENS["alice"], "ready-plan", ref(plan), "ready")
    with pytest.raises(Conflict, match="individual steps"):
        store.lease(TOKENS["alice"], "lease-plan", ref(plan))
    store.transition(TOKENS["alice"], "ready-step", ref(a), "ready")
    assert store.lease(TOKENS["carol"], "lease-step", ref(a))["state"] == "leased"


def test_plan_cannot_reuse_a_superseded_step(store):
    a = saved_action(store, "step")
    newer = action(store, a["payload"]["target"]) | {"id": "step", "predecessor": a["version"]}
    store.submit(TOKENS["alice"], "new-step", newer)
    d = action(store, a["payload"]["target"]) | {"id": "plan"}
    d["payload"]["proposal"] = proposal() | {"intent": "plan", "plan_steps": [ref(a)]}
    with pytest.raises(Conflict, match="Stale"):
        store.submit(TOKENS["alice"], "stale-plan", d)


@pytest.mark.parametrize("mutation", ["duplicates", "empty-control", "empty-plan", "wrong-step-kind"])
def test_incomplete_proposal_is_not_silently_actionable(mutation):
    p = proposal()
    if mutation == "duplicates":
        p["outcomes"].append(p["outcomes"][0])
    elif mutation == "empty-control":
        p["controls"] = []
    elif mutation == "empty-plan":
        p["intent"] = "plan"
    else:
        p.update(intent="plan", plan_steps=[{"namespace": "x", "kind": "Claim", "id": "x", "version": "0"*64}])
    with pytest.raises(ValidationError):
        ActionProposal.model_validate(p)
