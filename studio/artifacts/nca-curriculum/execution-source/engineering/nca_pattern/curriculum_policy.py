"""Explicit training-mask policy and source-order guard for independent evaluation."""

import os
import sys

import torch


def damage_masks(regime, iteration, circle_keep, generator, schedule):
    interval = next(
        x["cutoff_inclusive"]
        for x in schedule
        if x["iterations_inclusive"][0] <= iteration <= x["iterations_inclusive"][1]
    )
    cutoff = int(generator.integers(interval[0], interval[1] + 1))
    keep = circle_keep.clone()
    if regime == "curriculum-pool":
        # First of the three lowest-loss states is the third-lowest-loss state.
        keep[0] = (
            torch.arange(keep.shape[-1], device=keep.device)[None, None, :] >= cutoff
        )
    elif regime != "damage-pool":
        raise ValueError("Unknown frozen regime")
    return keep, cutoff


def install_read_guard(mask_path):
    expected = os.path.abspath(os.fspath(mask_path))
    state = {
        "released_after_checkpoint_barrier": False,
        "blocked_early_attempts": 0,
        "mask_reads_after_release": 0,
    }

    def guard(event, args):
        if (
            event != "open"
            or not args
            or not isinstance(args[0], (str, bytes, os.PathLike))
        ):
            return
        if os.path.abspath(os.fsdecode(args[0])) != expected:
            return
        if not state["released_after_checkpoint_barrier"]:
            state["blocked_early_attempts"] += 1
            raise RuntimeError("Evaluation mask read before checkpoint barrier")
        state["mask_reads_after_release"] += 1

    sys.addaudithook(guard)
    return state


def validate_manifest(path, cfg):
    from hashlib import sha256
    import json

    manifest = json.loads(path.read_text())
    if (
        sha256(path.read_bytes()).hexdigest()
        != cfg["independent_evaluation_manifest_sha256"]
    ):
        raise ValueError("Independent evaluation manifest changed")
    if (
        manifest["protocol_sha256"] != cfg["curriculum_plan_sha256"]
        or manifest["target_sha256"] != cfg["target"]["sha256"]
    ):
        raise ValueError("Evaluation plan/target identity changed")
    if (
        manifest["update_seeds"] != cfg["evaluation"]["update_seeds"]
        or manifest["mask_file_sha256"] != cfg["target"]["heldout_masks_sha256"]
    ):
        raise ValueError("Independent evaluation seed/mask identity changed")
    if [x["id"] for x in manifest["masks"]] != cfg["evaluation"]["damage"]["masks"]:
        raise ValueError("Evaluation mask identities changed")
