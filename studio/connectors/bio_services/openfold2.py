"""Request construction and receipt checks for hosted OpenFold2 inference.

This module does not authenticate or make network calls. A caller supplies an
already-authorized MCP client, which keeps credential handling with the
configured service client and makes tests deterministic.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

OPENFOLD2_MAX_RESIDUES = 1024
STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def sequence_sha256(sequence: str) -> str:
    """Return SHA-256 over the unwrapped uppercase amino-acid sequence."""
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def validate_protein_sequence(sequence: str, *, max_residues: int = OPENFOLD2_MAX_RESIDUES) -> str:
    """Validate a single unmodified sequence accepted by the OpenFold2 tool."""
    if not isinstance(sequence, str):
        raise TypeError("sequence must be text")
    if not sequence or sequence != sequence.strip() or re.search(r"\s", sequence):
        raise ValueError("sequence must be nonempty, unwrapped, and contain no whitespace")
    if sequence != sequence.upper():
        raise ValueError("sequence must use uppercase one-letter amino-acid codes")
    invalid = sorted(set(sequence) - STANDARD_AA)
    if invalid:
        raise ValueError(f"sequence contains unsupported or noncanonical residue codes: {''.join(invalid)}")
    if len(sequence) > max_residues:
        raise ValueError(f"sequence has {len(sequence)} residues; maximum is {max_residues}")
    return sequence


def build_openfold2_request(
    sequence: str,
    *,
    input_id: str,
    idempotency_key: str,
    output_prefix: str,
    wait_seconds: int = 30,
) -> dict[str, Any]:
    """Build the pinned, single-model OpenFold2 request used by this connector.

    The server tool's accepted shape is recorded by the live catalog. One
    selected model and disabled relaxation avoid turning this into a sweep.
    ``output_prefix`` is caller-chosen and must be unique to its work item.
    """
    validate_protein_sequence(sequence)
    if not input_id or len(input_id) > 128:
        raise ValueError("input_id must be 1..128 characters")
    if len(idempotency_key) < 8:
        raise ValueError("idempotency_key must contain at least 8 characters")
    if not output_prefix.startswith("frontier/") or ".." in output_prefix.split("/"):
        raise ValueError("output_prefix must be under the caller's frontier/ namespace")
    if not 0 <= wait_seconds <= 30:
        raise ValueError("wait_seconds must be between 0 and 30")
    return {
        "input_id": input_id,
        "sequence": sequence,
        "selected_models": [1],
        "relax_prediction": False,
        "idempotency_key": idempotency_key,
        "wait_seconds": wait_seconds,
        "output_prefix": output_prefix,
    }


def validate_openfold2_receipt(receipt: dict[str, Any], *, expected_sequence: str) -> None:
    """Check that a persisted operation receipt belongs to the pinned request."""
    validate_protein_sequence(expected_sequence)
    if receipt.get("tool") != "infer_openfold2_native":
        raise ValueError("receipt does not identify infer_openfold2_native")
    if receipt.get("model_id") != "openfold2":
        raise ValueError("receipt does not identify OpenFold2")
    if receipt.get("sequence_length_aa") != len(expected_sequence):
        raise ValueError("receipt sequence length does not match the pinned input")
    if receipt.get("sequence_sha256") != sequence_sha256(expected_sequence):
        raise ValueError("receipt sequence hash does not match the pinned input")
    if not receipt.get("operation_id"):
        raise ValueError("receipt has no provider operation ID")
    if receipt.get("final_status") not in {"SUCCEEDED", "FAILED", "CANCELLED", "ERROR", "EXPIRED", None}:
        raise ValueError("receipt contains an unknown terminal state")
