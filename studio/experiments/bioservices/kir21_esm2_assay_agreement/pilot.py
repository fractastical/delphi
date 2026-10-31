"""Validation pilot — PROTOCOL.md §9. Run before the scoring batch.

Two positive controls and two negative controls. The negatives must raise: a
pilot whose refusal cases pass quietly has tested nothing, so a non-raising
negative fails the pilot and the run stops.

The pilot also measures batched-forward latency, which drives the checkpoint
step-down rule in §5. That rule reads a wall clock and never a measured value.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from connectors.bioservices import proteingym  # noqa: E402
from connectors.bioservices.esm2 import Esm2MaskedMarginalScorer, ScoringConfig  # noqa: E402
from connectors.bioservices.receipts import environment_fingerprint, git_sha, utc_now, write_json  # noqa: E402
from experiments.bioservices.kir21_esm2_assay_agreement import common  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Kir2.1 ESM-2 evaluation: validation pilot")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--latency-batches", type=int, default=3)
    args = ap.parse_args()

    started = time.time()
    protocol = common.load_protocol()
    surface, function, checks = common.load_assays(protocol, args.data_dir)
    reference = surface.reference_sequence
    matched = proteingym.matched_variants(surface, function)
    subset = common.select_subset(matched, protocol["subset"]["salt"], protocol["subset"]["size"])

    archive = os.path.join(args.data_dir, "DMS_ProteinGym_substitutions.zip")
    orientations = [common.orientation_check(surface, archive), common.orientation_check(function, archive)]

    cfg = ScoringConfig(
        checkpoint=protocol["model"]["target_checkpoint"],
        threads=protocol["model"]["threads"],
        batch_positions=protocol["model"]["batch_positions"],
    )
    load_t = time.time()
    scorer = Esm2MaskedMarginalScorer(reference, cfg, cache_dir=args.cache_dir)
    load_seconds = time.time() - load_t

    controls: list[dict] = []

    # P1 — a wild-type "substitution" is the same log-probability minus itself.
    pos = surface.variants[subset[0]].position
    wt = reference[pos - 1]
    wt_variant = proteingym.Variant(f"{wt}{pos}{wt}", wt, pos, wt, float("nan"))
    p1 = scorer.score_many([wt_variant])[wt_variant.mutant]
    controls.append({
        "id": "P1", "case": f"wild-type substitution {wt_variant.mutant}",
        "expected": "score exactly 0.0", "observed": p1, "passed": p1 == 0.0,
    })

    # P2 — a real matched variant scores finitely, and rebuilding its sequence
    # from the reference reproduces the CSV's own mutated_sequence.
    v = surface.variants[subset[0]]
    p2_score = scorer.score_many([v])[v.mutant]
    rebuilt = reference[: v.position - 1] + v.mut_aa + reference[v.position:]
    import csv, io, zipfile
    with zipfile.ZipFile(archive) as zf:
        member = proteingym._member_name(archive, surface.assay_id)
        csv_seq = next(
            r["mutated_sequence"]
            for r in csv.DictReader(io.StringIO(zf.read(member).decode("utf-8")))
            if r["mutant"] == v.mutant
        )
    controls.append({
        "id": "P2", "case": f"real matched variant {v.mutant}",
        "expected": "finite score and rebuilt sequence equals the CSV mutated_sequence",
        "observed": {"score": p2_score, "sequence_matches_csv": rebuilt == csv_seq},
        "passed": math.isfinite(p2_score) and rebuilt == csv_seq,
    })

    # N1 — declared wild-type residue wrong for the position. Must refuse.
    wrong = next(a for a in proteingym.AA if a != reference[pos - 1])
    controls.append(_expect_refusal(
        "N1", f"declared wild-type {wrong} at position {pos}, reference holds {reference[pos - 1]}",
        lambda: proteingym.check_variant_against_reference(f"{wrong}{pos}A", reference)))

    # N2 — position outside the reference. Must refuse.
    bad = len(reference) + 1
    controls.append(_expect_refusal(
        "N2", f"position {bad} outside 1..{len(reference)}",
        lambda: proteingym.check_variant_against_reference(f"A{bad}G", reference)))

    # Latency, for the step-down rule. Positions not already cached by P1/P2.
    seen = {v.position for v in (wt_variant, v)}
    probe = [p for p in sorted({surface.variants[k].position for k in subset}) if p not in seen]
    per_batch: list[float] = []
    bp = cfg.batch_positions
    for i in range(args.latency_batches):
        chunk = probe[i * bp : (i + 1) * bp]
        if len(chunk) < bp:
            break
        t0 = time.time()
        scorer._masked_log_probs(chunk)
        per_batch.append(time.time() - t0)

    subset_positions = len({surface.variants[k].position for k in subset})
    median_batch = statistics.median(per_batch) if per_batch else float("nan")
    projected = median_batch * math.ceil(subset_positions / bp)
    limit = 25 * 60
    step_down = bool(per_batch) and projected > limit

    all_checks_pass = all(c.get("passed", True) for c in checks if "passed" in c)
    orientations_pass = all(o["passed"] for o in orientations)
    controls_pass = all(c["passed"] for c in controls)

    receipt = {
        "stage": "pilot",
        "protocol_id": protocol["protocol_id"],
        "started_utc": utc_now(),
        "git_sha": git_sha(os.path.dirname(os.path.abspath(__file__))),
        "environment": environment_fingerprint(),
        "reference_checks": checks,
        "orientation_checks": orientations,
        "controls": controls,
        "matched_variants": len(matched),
        "subset_size": len(subset),
        "subset_distinct_positions": subset_positions,
        "latency": {
            "checkpoint": cfg.checkpoint,
            "model_load_seconds": round(load_seconds, 2),
            "batch_positions": bp,
            "per_batch_seconds": [round(x, 3) for x in per_batch],
            "median_batch_seconds": round(median_batch, 3) if per_batch else None,
            "projected_scoring_seconds": round(projected, 1) if per_batch else None,
            "limit_seconds": limit,
            "step_down_triggered": step_down,
            "checkpoint_for_batch": protocol["model"]["step_down_checkpoint"] if step_down else cfg.checkpoint,
        },
        "passed": bool(all_checks_pass and orientations_pass and controls_pass and per_batch),
        "elapsed_seconds": round(time.time() - started, 1),
    }
    digest = write_json(args.out, receipt)
    print(f"pilot receipt {args.out} sha256={digest}")
    for c in controls:
        print(f"  {c['id']} {'PASS' if c['passed'] else 'FAIL'}  {c['case']}")
    print(f"  reference checks: {'PASS' if all_checks_pass else 'FAIL'}; "
          f"orientation: {'PASS' if orientations_pass else 'FAIL'}")
    print(f"  median batch {median_batch:.2f}s over {bp} positions; "
          f"{subset_positions} positions projected {projected / 60:.1f} min; step_down={step_down}")
    print("PILOT:", "PASS" if receipt["passed"] else "FAIL")
    return 0 if receipt["passed"] else 1


def _expect_refusal(cid: str, case: str, fn) -> dict:
    """A negative control passes only by raising ReferenceMismatch."""
    try:
        result = fn()
    except proteingym.ReferenceMismatch as exc:
        return {"id": cid, "case": case, "expected": "ReferenceMismatch",
                "observed": f"ReferenceMismatch: {exc}", "passed": True}
    except Exception as exc:  # a different error is not the refusal we asked for
        return {"id": cid, "case": case, "expected": "ReferenceMismatch",
                "observed": f"{type(exc).__name__}: {exc}", "passed": False}
    return {"id": cid, "case": case, "expected": "ReferenceMismatch",
            "observed": f"no refusal; returned {result}", "passed": False}


if __name__ == "__main__":
    raise SystemExit(main())
