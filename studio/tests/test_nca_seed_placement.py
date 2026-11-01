from hashlib import sha256
import json
import shutil

import numpy as np
import pytest

from engineering.nca_pattern import seed_experiment as experiment


def test_seed_is_only_changed_array_and_original_solver_bytes_are_frozen():
    assert experiment.validate()
    source = np.load(experiment.ART / "target.npz")
    variant = np.load(experiment.VARIANT / "target.npz")
    assert variant["seed_xy"].tolist() == [7, 41]
    assert source["seed_xy"].tolist() == [8, 42]
    assert variant["silhouette"][41, 7]
    assert not source["silhouette"][42, 8]
    original = json.loads((experiment.ART / "packet.json").read_text())
    files = experiment.members()
    for item in original["files"]:
        if item["path"].startswith("engineering/"):
            assert (
                sha256(files[item["path"]].read_bytes()).hexdigest() == item["sha256"]
            )


def test_changing_target_instead_of_seed_is_rejected(tmp_path, monkeypatch):
    for name in ["target.npz", "protocol.json"]:
        shutil.copyfile(experiment.VARIANT / name, tmp_path / name)
    changed = dict(np.load(tmp_path / "target.npz"))
    changed["rgba"] = changed["rgba"].copy()
    changed["rgba"][0, 0, 0] = 1
    np.savez_compressed(tmp_path / "target.npz", **changed)
    monkeypatch.setattr(experiment, "VARIANT", tmp_path)
    with pytest.raises(ValueError, match="target array changed"):
        experiment.validate()


def test_original_run_cannot_be_relabelled_as_changed_seed_experiment(tmp_path):
    from engineering.nca_pattern.analyze import audit

    with pytest.raises(ValueError, match="Frozen protocol changed"):
        audit(experiment.ART / "run-original", tmp_path, experiment.VARIANT)
