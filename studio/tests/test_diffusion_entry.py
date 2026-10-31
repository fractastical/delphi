import json

import pytest

from frontier_compute.diffusion_entry import PACKET_SHA, require_gate


def test_training_refuses_missing_same_job_gate(tmp_path):
    with pytest.raises(RuntimeError, match="missing"):
        require_gate(tmp_path / "absent.json")


@pytest.mark.parametrize("gate", [{"ok": False, "packet_sha256": PACKET_SHA}, {"ok": True, "packet_sha256": "other"}])
def test_training_refuses_failed_or_other_packet_gate(tmp_path, gate):
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(gate))
    with pytest.raises(RuntimeError, match="failed or belongs"):
        require_gate(path)
