"""Replay of BIOMD0000001047 (Collier 1996 Delta-Notch lateral inhibition).

Needs the network (to fetch the pinned file) and libroadrunner, so it runs only when
`BIOMODELS_LIVE=1`. Without it these tests are *skipped*, which is not a pass: the recorded run is
`connectors/biomodels/receipts/BIOMD0000001047/receipt.json`.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.biomodels import client as cl  # noqa: E402
from connectors.biomodels.__main__ import PINNED  # noqa: E402
from connectors.biomodels.replay import EngineUnavailable, load_engine, replay_collier1996  # noqa: E402

ACC = "BIOMD0000001047"
pytestmark = pytest.mark.skipif(os.environ.get("BIOMODELS_LIVE") != "1", reason="set BIOMODELS_LIVE=1 (network + libroadrunner)")


@pytest.fixture(scope="module")
def model_bytes(tmp_path_factory):
    try:
        load_engine()
    except EngineUnavailable as exc:
        pytest.skip(f"libroadrunner unavailable: {exc}")
    got = cl.BioModelsClient().fetch(ACC, tmp_path_factory.mktemp("dl"))
    assert got.sha256 == PINNED[ACC]
    return Path(got.path).read_bytes()


@pytest.fixture(scope="module")
def receipt(model_bytes, tmp_path_factory):
    return replay_collier1996(model_bytes, PINNED[ACC], tmp_path_factory.mktemp("out"))


def test_every_control_passes(receipt):
    assert receipt["checks"] and all(receipt["checks"].values()), receipt["checks"]


def test_published_run_ends_patterned_and_baseline_does_not(receipt):
    pub, base = receipt["scenarios"]["as_published"], receipt["scenarios"]["symmetric_baseline"]
    assert pub["final_state"]["delta1"] > 0.9 > 0.1 > pub["final_state"]["delta2"]
    assert pub["final_state"]["notch2"] > 0.9 > 0.1 > pub["final_state"]["notch1"]
    assert base["max_abs_delta1_minus_delta2"] < 1e-9
    assert receipt["scenarios"]["no_notch_feedback_b0"]["max_abs_delta1_minus_delta2"] < 0.02


def test_receipt_is_marked_as_simulation_with_limits(receipt):
    assert receipt["evidence_kind"].startswith("simulation of a published model")
    assert any("Units" in s for s in receipt["limits"]) and receipt["run"]["hardware"]["gpu"] is None


def test_wrong_pin_and_tampered_bytes_are_refused(model_bytes, tmp_path):
    with pytest.raises(ValueError):
        replay_collier1996(model_bytes + b" ", PINNED[ACC], tmp_path)
    assert not list(tmp_path.iterdir())


def test_changed_law_changes_the_result_and_is_not_accepted_under_the_old_pin(model_bytes, tmp_path):
    mutated = model_bytes.replace(b'id="h" metaid="COPASI10" name="h" value="2"', b'id="h" metaid="COPASI10" name="h" value="0.5"')
    assert mutated != model_bytes
    with pytest.raises(ValueError):
        replay_collier1996(mutated, PINNED[ACC], tmp_path)
    # pinned to its own digest it runs, and the weakened feedback must not reproduce the pattern
    r = replay_collier1996(mutated, cl.sha256_bytes(mutated), tmp_path)
    assert r["scenarios"]["as_published"]["max_abs_delta1_minus_delta2"] < 0.5


def test_committed_receipt_matches_the_pin():
    path = Path(__file__).resolve().parents[1] / "connectors/biomodels/receipts" / ACC / "receipt.json"
    r = json.loads(path.read_text())
    assert r["model"]["sha256"] == PINNED[ACC] == r["source"]["sha256"] == r["source"]["declared_sha256"]


def test_control_values_not_just_flags(receipt):
    c = receipt["controls"]
    assert c["derivative_check"]["max_abs_diff"] < 1e-12
    assert c["derivative_check_mutated_h3"]["max_abs_diff"] > 1e-3, "the mutated evaluator must be visibly wrong"
    assert c["symmetric_jacobian_real_eigenvalues"][-1] > 1e-3
    assert all(3.0 < o < 5.0 for o in c["rk4_observed_orders"])
    assert c["patterned_state_max_abs_rate"] < 1e-8


def test_replay_runs_from_a_relocated_copy_and_reproduces_the_committed_hashes(tmp_path):
    """The README command must not depend on this checkout: copy the package elsewhere and run it from there."""
    import shutil
    import subprocess

    src = Path(__file__).resolve().parents[1] / "connectors" / "biomodels"
    root = tmp_path / "elsewhere"
    shutil.copytree(src, root / "connectors" / "biomodels", ignore=shutil.ignore_patterns("receipts", "orx", "mapping", "__pycache__"))
    out = tmp_path / "out"
    proc = subprocess.run([sys.executable, "-m", "connectors.biomodels", "replay", ACC, "--dest", str(tmp_path / "dl"), "--out", str(out)],
                          cwd=root, env={**os.environ, "PYTHONPATH": str(root)}, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-500:]
    new = json.loads((out / "receipt.json").read_text())
    old = json.loads((src / "receipts" / ACC / "receipt.json").read_text())
    assert new["output_sha256"] == old["output_sha256"] and new["run"]["code_sha256"] == old["run"]["code_sha256"]
    assert str(tmp_path) not in json.dumps(new), "the receipt must not embed this machine's paths"
