import hashlib
import json

import pytest

from engineering.experimental_design.cantilever_demo import (
    BEAM_SOURCE,
    BEAM_SOURCE_SHA256,
    build_cantilever_protocol,
    freeze_protocol,
    run_demo,
)
from engineering.experimental_design.planner import plan_experiments


def test_frozen_cantilever_contract_is_source_pinned_and_rank_controlled(tmp_path):
    protocol = build_cantilever_protocol()
    assert BEAM_SOURCE.is_file()
    assert hashlib.sha256(BEAM_SOURCE.read_bytes()).hexdigest() == BEAM_SOURCE_SHA256
    assert protocol["equation"]["source_sha256"] == BEAM_SOURCE_SHA256
    assert protocol["source_claims"] == []
    assert protocol["input_datasets"] == []

    path = tmp_path / "protocol.json"
    protocol_hash = freeze_protocol(path)
    assert json.loads(path.read_text()) == protocol
    assert freeze_protocol(path) == protocol_hash

    result = plan_experiments(protocol)
    designs = {row["id"]: row for row in result["designs"]}
    assert designs["deflection_only"]["identifiability"]["rank"] == 1
    assert designs["mixed_load_deflection"]["identifiability"]["rank"] == 2
    assert result["selected_design_id"] == "mixed_load_deflection"
    assert result["measurement_rows"] == []
    assert result["action_artifact"]["state"] == "proposal_unlinked"


def test_run_requires_protocol_to_be_committed(tmp_path):
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(build_cantilever_protocol()))
    with pytest.raises(RuntimeError, match="committed file"):
        run_demo(path, tmp_path / "out")
