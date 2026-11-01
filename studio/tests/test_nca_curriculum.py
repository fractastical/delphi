import numpy as np
import pytest
import torch

from engineering.nca_curriculum.policy import damage_masks, install_read_guard
from engineering.nca_curriculum.analyze import (
    expected_identities,
    paired_effects,
    predicate,
)
from engineering.nca_pattern.analyze import load
from engineering.nca_pattern.model import ROOT

SCHEDULE = [
    {"iterations_inclusive": [0, 499], "cutoff_inclusive": [16, 20]},
    {"iterations_inclusive": [500, 999], "cutoff_inclusive": [20, 24]},
    {"iterations_inclusive": [1000, 1999], "cutoff_inclusive": [24, 28]},
]


def test_policy_preserves_two_matched_circles_and_consumes_paired_rng():
    circles = torch.ones(3, 1, 64, 64, dtype=torch.bool)
    circles[:, :, 30:40, 30:40] = False
    baseline = np.random.default_rng(1)
    mixed = np.random.default_rng(1)
    for step in [0, 499, 500, 999, 1000, 1999]:
        a, cut_a = damage_masks("damage-pool", step, circles, baseline, SCHEDULE)
        b, cut_b = damage_masks("curriculum-pool", step, circles, mixed, SCHEDULE)
        assert (
            cut_a == cut_b
            and torch.equal(a, circles)
            and torch.equal(b[1:], circles[1:])
        )
        assert not b[0, :, :, 7].any() and b[0, :, :, cut_b:].all()
    assert baseline.bit_generator.state == mixed.bit_generator.state


def test_read_guard_blocks_payload_until_barrier_release(tmp_path):
    path = tmp_path / "masks.npz"
    path.write_bytes(b"not read before barrier")
    guard = install_read_guard(path)
    with pytest.raises(RuntimeError, match="before checkpoint"):
        path.read_bytes()
    assert (
        guard["blocked_early_attempts"] == 1 and guard["mask_reads_after_release"] == 0
    )
    guard["released_after_checkpoint_barrier"] = True
    assert path.read_bytes() == b"not read before barrier"
    assert guard["mask_reads_after_release"] >= 1


def test_frozen_probe_counts_and_pair_dependence_are_not_pooled():
    cfg = load(ROOT / "artifacts/nca-curriculum/runtime-protocol.json")
    cases = expected_identities(cfg)
    assert len(cases) == 200
    assert sum(x[1] != "all-erased-negative" for x in cases) == 192
    records = [
        {"model_id": model, "kind": kind, "recomputed_passed": True}
        for model, kind, _ in cases if kind != "all-erased-negative"
    ]
    effects = paired_effects(cfg, records)
    assert len([x for x in effects if x["group"] == "all_design"]) == 4
    assert all(x["curriculum_minus_baseline_fraction"] == 0 for x in effects)
    removed = records.pop()
    missing = paired_effects(cfg, records)
    row = next(
        x for x in missing if x["group"] == "all_design"
        and str(x["initialization_seed"]) == removed["model_id"].split("-s")[-1]
    )
    assert not row["both_evaluation_sets_executed"]
    assert row["curriculum_minus_baseline_fraction"] is None


def test_recovery_requires_predamage_and_persistence_all_saved_checkpoints():
    good = {"rgba_MSE": .01, "silhouette_IoU": .8}
    bad = {"rgba_MSE": .03, "silhouette_IoU": .8}
    item = {"kind": "new-left-prefix-34", "status": "complete", "predamage": bad}
    assert not predicate(item, good, np.ones((4, 64, 64)))
    item["predamage"] = good
    assert predicate(item, good, np.ones((4, 64, 64)))
    item.update(kind="persistence", metrics=[
        {"update_step": 256, **good}, {"update_step": 2048, **bad},
    ])
    assert not predicate(item, good, np.ones((4, 64, 64)))
    item["metrics"][-1].update(good)
    assert predicate(item, good, np.ones((4, 64, 64)))
