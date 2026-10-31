"""Full 6,789-variant scoring — PREREGISTRATION-full.md.

Computes the masked log-probability vector at every one of the 391 matched
positions, persists those vectors, and derives a score for every matched
variant. Resumable across capped scopes, like the 256-variant run.

Two things it does that the 256 run did not:

- It **saves the per-position vectors**, with a sha256 of the exact masked input
  row. The earlier run saved only per-variant scores, which cannot be inverted
  back into a position's distribution, so extending it cost a full recomputation.
  After this, extending to any variant at these positions is free.
- It **re-derives the 256 original scores and requires them to match bit-for-bit.**
  A mismatch means the scoring path is not deterministic across processes, which
  would weaken the earlier result too, so it halts the run rather than warning.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from connectors.bioservices import proteingym  # noqa: E402
from connectors.bioservices.esm2 import Esm2MaskedMarginalScorer, ScoringConfig  # noqa: E402
from connectors.bioservices.receipts import environment_fingerprint, git_sha, utc_now, write_json  # noqa: E402
from experiments.bioservices.kir21_esm2_assay_agreement import common  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Kir2.1 ESM-2: full matched-set scoring")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--checkpoint-file", required=True)
    ap.add_argument("--original-scores", required=True,
                    help="the committed 256-variant checkpoint, for the reproduction control")
    ap.add_argument("--budget-seconds", type=float, default=470.0)
    args = ap.parse_args()

    started = time.time()
    protocol = common.load_protocol()
    surface, function, _checks = common.load_assays(protocol, args.data_dir)
    reference = surface.reference_sequence
    matched = proteingym.matched_variants(surface, function)
    positions = sorted({surface.variants[k].position for k in matched})

    state = {"vectors": {}, "invocations": [], "checkpoint": protocol["model"]["target_checkpoint"]}
    if os.path.exists(args.checkpoint_file):
        with open(args.checkpoint_file) as fh:
            state = json.load(fh)

    remaining = [p for p in positions if str(p) not in state["vectors"]]
    if remaining:
        cfg = ScoringConfig(
            checkpoint=state["checkpoint"],
            threads=protocol["model"]["threads"],
            batch_positions=protocol["model"]["batch_positions"],
        )
        t0 = time.time()
        scorer = Esm2MaskedMarginalScorer(reference, cfg, cache_dir=args.cache_dir)
        load_seconds = time.time() - t0

        bp = cfg.batch_positions
        work_started = time.time()
        done = 0
        for start in range(0, len(remaining), bp):
            if time.time() - work_started > args.budget_seconds:
                break
            chunk = remaining[start : start + bp]
            for pos, rec in scorer.position_log_probs(chunk).items():
                state["vectors"][str(pos)] = rec
            done += len(chunk)
        state["invocations"].append({
            "utc": utc_now(), "model_load_seconds": round(load_seconds, 2),
            "work_seconds": round(time.time() - work_started, 1),
            "positions_this_run": done, "positions_total": len(state["vectors"]),
            "git_sha": git_sha(os.path.dirname(os.path.abspath(__file__))),
            "environment": environment_fingerprint(),
        })
        write_json(args.checkpoint_file, state)
        left = len([p for p in positions if str(p) not in state["vectors"]])
        status = "COMPLETE" if left == 0 else "PARTIAL"
        print(f"{status} positions={len(state['vectors'])}/{len(positions)} "
              f"this_run={done} remaining={left} elapsed={time.time() - started:.1f}s")
        if left:
            return 0

    # Every position is present: derive scores for all matched variants.
    scores = {}
    for key in matched:
        v = surface.variants[key]
        rec = state["vectors"][str(v.position)]
        if rec["wt_aa"] != v.wt_aa:
            raise SystemExit(
                f"{key}: stored vector at position {v.position} is for {rec['wt_aa']}, not {v.wt_aa}"
            )
        scores[key] = rec["log_probs"][v.mut_aa] - rec["log_probs"][v.wt_aa]

    # Reproduction control against the committed 256.
    with open(args.original_scores) as fh:
        original = json.load(fh)["scores"]
    mismatches = []
    for key, old in original.items():
        new = scores.get(key)
        if new is None:
            mismatches.append({"mutant": key, "reason": "absent from the full matched set"})
        elif new != old:
            mismatches.append({"mutant": key, "original": old, "recomputed": new,
                               "abs_diff": abs(new - old)})
    control = {
        "n_original": len(original),
        "n_mismatched": len(mismatches),
        "bit_for_bit": not mismatches,
        "mismatches": mismatches[:20],
    }
    out = {
        "stage": "full_matched_scoring",
        "completed_utc": utc_now(),
        "checkpoint": state["checkpoint"],
        "n_positions": len(state["vectors"]),
        "n_variants": len(scores),
        "scores": scores,
        "reproduction_control": control,
        "invocations": state["invocations"],
    }
    path = args.checkpoint_file.replace(".json", "_scores.json")
    write_json(path, out)
    print(f"COMPLETE positions={len(state['vectors'])} variants={len(scores)}")
    print(f"reproduction control: {control['n_original']} original, "
          f"{control['n_mismatched']} mismatched, bit_for_bit={control['bit_for_bit']}")
    if mismatches:
        print("HALTING: the scoring path is not reproducible across processes.")
        for m in mismatches[:5]:
            print("   ", m)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
