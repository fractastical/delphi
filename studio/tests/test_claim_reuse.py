"""Input causality/integrity and capability redaction; no candidate FEM is run here."""

import copy
from fractions import Fraction
import json

import pytest
from pydantic import ValidationError

from engineering.claim_reuse.compute import (
    ART,
    bind_inputs,
    candidate_stiffness,
    compute,
    parsed_critical,
)
from engineering.claim_reuse.workflow import Client


def inputs():
    claim = json.loads((ART / "claim-read.json").read_text())["record"]
    protocol = json.loads((ART / "protocol.json").read_text())
    return claim, protocol, protocol["cases"][0]


def test_exact_claim_value_causally_constructs_candidate_parameter():
    claim, protocol, case = inputs()
    result = bind_inputs(claim, protocol, case)
    critical = parsed_critical(claim)
    assert Fraction(result["solver_EI_Nm2_exact"]) == critical * Fraction(
        case["margin_exact"]
    )
    assert candidate_stiffness(2 * critical, case["margin_exact"]) == 2 * Fraction(
        result["solver_EI_Nm2_exact"]
    )
    assert result["claim_ref"] == protocol["claim_ref"]


def test_altered_claim_is_refused_before_solver(tmp_path, monkeypatch):
    claim, protocol, case = inputs()
    changed = copy.deepcopy(claim)
    changed["payload"]["statement"] += " altered law"
    monkeypatch.setattr(
        "engineering.claim_reuse.compute.beam.solve_checked",
        lambda *a, **k: pytest.fail("mutated Claim reached solver"),
    )
    with pytest.raises(ValidationError, match="digest mismatch"):
        compute(changed, protocol, case, tmp_path)


def test_historical_scope_mismatch_is_refused():
    claim, protocol, case = inputs()
    protocol["source_result_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source scope"):
        bind_inputs(claim, protocol, case)


def test_exact_ref_cannot_silently_use_a_new_head():
    claim, protocol, case = inputs()
    protocol["claim_ref"]["version"] = "0" * 64
    with pytest.raises(ValueError, match="Exact Claim reference"):
        bind_inputs(claim, protocol, case)


def test_transcripts_never_include_credentials_or_lease_capabilities(tmp_path):
    client = Client(None, "secret-fixture-token-value", tmp_path / "transcript.json")
    client.secrets.append("secret-fixture-lease-value")
    safe = client.safe(
        {
            "lease_id": "secret-fixture-lease-value",
            "nested": [
                "Bearer secret-fixture-token-value",
                {"note": "prefix secret-fixture-lease-value suffix"},
            ],
        }
    )
    encoded = json.dumps(safe)
    assert "secret-fixture-token-value" not in encoded
    assert "secret-fixture-lease-value" not in encoded
    assert "[redacted bearer capability]" in encoded


def test_action_cache_pins_numerics_and_code_revision():
    from engineering.claim_reuse.workflow import action_draft

    _, protocol, case = inputs()
    plan = {"code_commit": "1" * 40, "code_files": {"fixture.py": "2" * 64}}
    a = action_draft(protocol, case, plan)["payload"]["cache_key"]
    modified = copy.deepcopy(protocol)
    modified["numerics"]["elements"] = [8, 16, 32]
    b = action_draft(modified, case, plan)["payload"]["cache_key"]
    assert a["parameters"] != b["parameters"]
    other = {**plan, "code_commit": "3" * 40}
    assert (
        action_draft(protocol, case, other)["payload"]["cache_key"]["code"] != a["code"]
    )
