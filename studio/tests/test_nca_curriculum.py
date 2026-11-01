import numpy as np
import pytest
import torch

from engineering.nca_curriculum.policy import damage_masks, install_read_guard

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
