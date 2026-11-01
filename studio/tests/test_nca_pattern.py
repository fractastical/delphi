import numpy as np
import torch

from engineering.nca_pattern.model import ART, NCA, seed, target


def test_frozen_design_is_nonempty_and_source_goal_not_observation():
    import json
    import hashlib

    meta = json.loads((ART / "target-manifest.json").read_text())
    assert meta["foreground_pixels"] == 653 and meta["all_zero_baseline_MSE"] > 0.02
    assert (
        hashlib.sha256((ART / "target.npz").read_bytes()).hexdigest()
        == meta["target_sha256"]
    )
    assert "design goal" in meta["status"]


def test_zero_updater_cannot_copy_target_and_bias_cannot_create_empty_pattern():
    goal, xy, _ = target()
    model = NCA()
    state = seed(64, xy)
    mask = torch.ones(1, 1, 64, 64, dtype=torch.bool)
    assert torch.equal(model(state, fire_mask=mask), state)
    with torch.no_grad():
        model.output.bias.fill_(0.2)
    assert torch.count_nonzero(model(torch.zeros_like(state), fire_mask=mask)) == 0
    assert np.count_nonzero(goal[:, 3].numpy()) > 500


def test_checkpoint_model_state_is_safe_weights_only_loadable(tmp_path):
    from engineering.nca_pattern.train import checkpoint

    model = NCA()
    opt = torch.optim.Adam(model.parameters())
    fire = torch.Generator().manual_seed(1)
    path = tmp_path / "state.pt"
    checkpoint(
        path, model, opt, 0, fire, np.random.default_rng(2), np.random.default_rng(3)
    )
    saved = torch.load(path, weights_only=True, map_location="cpu")
    assert saved["step"] == 0 and not saved["pool_state_saved"]
    assert sum(x.numel() for k, x in saved["model"].items() if k != "kernels") == 8336
