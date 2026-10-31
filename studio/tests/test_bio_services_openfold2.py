import pytest

from connectors.bio_services.openfold2 import (
    build_openfold2_request,
    sequence_sha256,
    validate_openfold2_receipt,
    validate_protein_sequence,
)


def test_openfold2_request_is_single_model_and_bound_to_sequence():
    sequence = "ACDEFGHIKLMNPQRSTVWY"
    request = build_openfold2_request(
        sequence,
        input_id="fish-kcnj13",
        idempotency_key="stable-key-123",
        output_prefix="frontier/kcnj13-openfold2/run-1",
    )
    assert request["sequence"] == sequence
    assert request["selected_models"] == [1]
    assert request["relax_prediction"] is False
    assert request["wait_seconds"] == 30
    assert sequence_sha256(sequence) == "5a52efc76a4a4ceb3c992ff17426b3545634646080bb6acec132c47c278c9846"


@pytest.mark.parametrize("sequence", ["", " ACDE", "AC DE", "acde", "ACDX", "BZX"])
def test_rejects_unwrapped_noncanonical_or_ambiguous_sequences(sequence):
    with pytest.raises((TypeError, ValueError)):
        validate_protein_sequence(sequence)


def test_rejects_too_long_sequence_and_unscoped_prefix():
    with pytest.raises(ValueError, match="maximum"):
        validate_protein_sequence("A" * 1025)
    with pytest.raises(ValueError, match="frontier/"):
        build_openfold2_request(
            "ACDE", input_id="x", idempotency_key="stable-key", output_prefix="runs/x"
        )


def test_receipt_must_match_exact_input_and_provider_operation():
    sequence = "ACDE"
    receipt = {
        "tool": "infer_openfold2_native",
        "model_id": "openfold2",
        "sequence_length_aa": len(sequence),
        "sequence_sha256": sequence_sha256(sequence),
        "operation_id": "op-example",
        "final_status": "SUCCEEDED",
    }
    validate_openfold2_receipt(receipt, expected_sequence=sequence)
    with pytest.raises(ValueError, match="hash"):
        validate_openfold2_receipt(receipt, expected_sequence="ACDF")
