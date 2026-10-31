"""Scoring batch — PROTOCOL.md §5. Resumable across capped scopes.

The protocol fixes ``RuntimeMaxSec=600`` for every step, and the pilot projected
about 21 minutes of scoring. So this script does bounded work per invocation,
checkpoints what it finished, and exits; a driver re-invokes it until it reports
complete. Each invocation makes progress, which is what distinguishes resumption
from the retry storm the brief forbids.

It writes scores only. No correlation is computed here, so the scoring step
cannot be influenced by seeing an outcome.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from connectors.bioservices import proteingym  # noqa: E402
from connectors.bioservices.esm2 import Esm2MaskedMarginalScorer, ScoringConfig  # noqa: E402
from connectors.bioservices.receipts import environment_fingerprint, git_sha, utc_now, write_json  # noqa: E402
from experiments.bioservices.kir21_esm2_assay_agreement import common  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Kir2.1 ESM-2 evaluation: scoring batch")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--checkpoint-file", required=True, help="resumable partial scores")
    ap.add_argument("--budget-seconds", type=float, default=480.0,
                    help="scoring work per invocation, excluding model load")
    args = ap.parse_args()

    started = time.time()
    protocol = common.load_protocol()
    surface, function, _checks = common.load_assays(protocol, args.data_dir)
    reference = surface.reference_sequence
    matched = proteingym.matched_variants(surface, function)
    subset = common.select_subset(matched, protocol["subset"]["salt"], protocol["subset"]["size"])

    state = {"scores": {}, "invocations": [], "checkpoint": protocol["model"]["target_checkpoint"]}
    if os.path.exists(args.checkpoint_file):
        with open(args.checkpoint_file) as fh:
            state = json.load(fh)

    remaining = [k for k in subset if k not in state["scores"]]
    if not remaining:
        print(f"COMPLETE scored={len(state['scores'])}/{len(subset)}")
        return 0

    cfg = ScoringConfig(
        checkpoint=state["checkpoint"],
        threads=protocol["model"]["threads"],
        batch_positions=protocol["model"]["batch_positions"],
    )
    load_t = time.time()
    scorer = Esm2MaskedMarginalScorer(reference, cfg, cache_dir=args.cache_dir)
    load_seconds = time.time() - load_t

    # Group the remaining variants by position so one forward pass serves all
    # variants at that position, then spend the budget position-group by group.
    by_position: dict[int, list] = {}
    for key in remaining:
        by_position.setdefault(surface.variants[key].position, []).append(surface.variants[key])
    positions = sorted(by_position)

    bp = cfg.batch_positions
    work_started = time.time()
    done_positions = 0
    for start in range(0, len(positions), bp):
        if time.time() - work_started > args.budget_seconds:
            break
        chunk = positions[start : start + bp]
        variants = [v for p in chunk for v in by_position[p]]
        scores = scorer.score_many(variants)
        for mutant, value in scores.items():
            state["scores"][mutant] = value
        done_positions += len(chunk)

    state["invocations"].append({
        "utc": utc_now(),
        "model_load_seconds": round(load_seconds, 2),
        "work_seconds": round(time.time() - work_started, 1),
        "positions_scored": done_positions,
        "forward_passes": scorer.forward_passes,
        "scored_total": len(state["scores"]),
        "git_sha": git_sha(os.path.dirname(os.path.abspath(__file__))),
        "environment": environment_fingerprint(),
    })
    write_json(args.checkpoint_file, state)

    left = len([k for k in subset if k not in state["scores"]])
    status = "COMPLETE" if left == 0 else "PARTIAL"
    print(f"{status} scored={len(state['scores'])}/{len(subset)} "
          f"positions_this_run={done_positions} remaining_variants={left} "
          f"elapsed={time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
