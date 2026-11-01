"""Binding/refusal tests only; Lean compilation is a separate explicit bounded job."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "artifacts/epithelial/interval-certificate/validate.py"
spec = importlib.util.spec_from_file_location("epithelial_interval_validate", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_exact_nonempty_binding():
    document = validator.witness_document()
    validator.check_witnesses(document)
    assert len(document["cells"]) == 4
    assert len({a["id"] for c in document["cells"] for a in c["arms"]}) == 8


@pytest.mark.parametrize(
    "mutation", ["empty", "wrong_endpoint", "wrong_context", "wrong_hash"]
)
def test_changed_witness_refused(mutation):
    document = deepcopy(validator.witness_document())
    if mutation == "empty":
        document["cells"] = []
    elif mutation == "wrong_endpoint":
        document["cells"][0]["scaled_ratio_interval"][0] = "1/1000000"
    elif mutation == "wrong_context":
        document["source_ensemble"]["stop_time_model_units"] = 2000
    else:
        document["cells"][0]["arms"][0]["logger_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pinned nonempty audit"):
        validator.check_witnesses(document)


def test_changed_raw_logger_refused(tmp_path):
    document = validator.witness_document()
    arm = document["cells"][0]["arms"][0]
    d = tmp_path / arm["id"]
    d.mkdir()
    (d / "logger.csv").write_text(
        "fabricated replacement, not the pinned native output"
    )
    with pytest.raises(ValueError, match="Native raw logger changed"):
        validator.check_witnesses(document, tmp_path)


@pytest.mark.parametrize("mutation", ["endpoint", "tolerance", "nonempty_interval"])
def test_changed_lean_binding_refused(mutation):
    text = (ROOT / validator.SOURCE).read_text()
    if mutation == "endpoint":
        text = text.replace("(2 : ℝ) / 175 ≤ x", "(3 : ℝ) / 175 ≤ x", 1)
    elif mutation == "tolerance":
        text = text.replace(": ¬ x ≤ 2 * y", ": ¬ x ≤ 3 * y", 1)
    else:
        text = text.replace("x ≤ (4 : ℝ) / 175", "x ≤ (5 : ℝ) / 175", 1)
    with pytest.raises(ValueError, match="Lean"):
        validator.check_lean_binding(validator.witness_document(), text)
