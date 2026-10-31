"""Reject corrupted evidence and failed prerequisites in the returned packet."""

import json
from pathlib import Path

import pytest

from frontier_compute.aoa_report import report


ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "results/infra/aoa/results/infra12-fish-aoa-grid-pairs/parts"
PROTOCOL = ROOT / "results/infra/aoa-protocol.json"


def test_actual_returned_packet():
    result = report(PARTS, PROTOCOL)
    assert len(result["cases"]) == 6
    assert result["all_frozen_bounds_passed"]


@pytest.mark.parametrize("corruption", ["parity", "field_hash", "nonfinite"])
def test_rejects_corrupted_evidence(monkeypatch, corruption):
    original = Path.read_text

    def changed(path, *args, **kwargs):
        text = original(path, *args, **kwargs)
        if corruption == "parity" and path.name == "checks.json":
            data = json.loads(text)
            data["repeat_passed"] = False
            return json.dumps(data)
        if path.name == "result.json":
            data = json.loads(text)
            if corruption == "field_hash":
                data["fields_sha256"] = "0" * 64
            if corruption == "nonfinite":
                data["mean_Cd_last20pct"] = float("nan")
            return json.dumps(data)
        return text

    monkeypatch.setattr(Path, "read_text", changed)
    with pytest.raises(ValueError):
        report(PARTS, PROTOCOL)
