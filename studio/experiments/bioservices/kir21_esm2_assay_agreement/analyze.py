"""Analysis — PROTOCOL.md §7-8. Runs once, after scoring is complete.

Computes Spearman agreement between the frozen ESM-2 scores and each assay on
the identical subset, the paired bootstrap interval on their difference, a
permutation null, and the same statistics for a BLOSUM62 baseline.

The BLOSUM62 arm is there to answer the question the headline cannot: if the
baseline shows the same assay preference, the difference is about the assays,
not about what the language model represents.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from scipy.stats import rankdata, spearmanr

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from connectors.bioservices import proteingym  # noqa: E402
from connectors.bioservices.receipts import environment_fingerprint, git_sha, utc_now, write_json  # noqa: E402
from experiments.bioservices.baselines import blosum62  # noqa: E402
from experiments.bioservices.kir21_esm2_assay_agreement import common  # noqa: E402


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho as Pearson on average-tied ranks."""
    ra, rb = rankdata(a), rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / denom) if denom else float("nan")


def _paired_bootstrap(pred, surf, func, n: int, seed: int, ci: float):
    """Resample variants, not assays: the SAME indices score both outcomes.

    That is what makes the interval on the difference paired. The two assays are
    strongly dependent, so comparing two independent intervals would overstate
    the uncertainty on their difference.
    """
    rng = np.random.default_rng(seed)
    m = len(pred)
    rs = np.empty(n)
    rf = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, m, m)
        rs[i] = _spearman(pred[idx], surf[idx])
        rf[i] = _spearman(pred[idx], func[idx])
    delta = rs - rf
    lo, hi = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    pack = lambda v: {
        "point": None,
        "ci_low": float(np.percentile(v, lo)),
        "ci_high": float(np.percentile(v, hi)),
        "bootstrap_mean": float(v.mean()),
        "bootstrap_sd": float(v.std(ddof=1)),
    }
    return pack(rs), pack(rf), pack(delta), delta


def _permutation_p(pred, obs, rho_obs: float, n: int, seed: int) -> float:
    """Two-sided p for rho != 0, with the conventional +1 correction."""
    rng = np.random.default_rng(seed)
    shuffled = pred.copy()
    count = 0
    for _ in range(n):
        rng.shuffle(shuffled)
        if abs(_spearman(shuffled, obs)) >= abs(rho_obs):
            count += 1
    return (1 + count) / (1 + n)


def _verdict(delta: dict) -> tuple[str, str]:
    if delta["ci_high"] <= 0:
        return "falsified", "the 95% CI for delta_rho lies entirely at or below 0"
    if delta["ci_low"] > 0:
        return "supported", "the 95% CI for delta_rho lies entirely above 0"
    return "undetermined", "the 95% CI for delta_rho spans 0; this is not support"


def main() -> int:
    ap = argparse.ArgumentParser(description="Kir2.1 ESM-2 evaluation: analysis")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--checkpoint-file", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-csv", required=True)
    args = ap.parse_args()

    started = time.time()
    protocol = common.load_protocol()
    surface, function, checks = common.load_assays(protocol, args.data_dir)
    matched = proteingym.matched_variants(surface, function)
    subset = common.select_subset(matched, protocol["subset"]["salt"], protocol["subset"]["size"])

    with open(args.checkpoint_file) as fh:
        state = json.load(fh)
    scores = state["scores"]

    usable = [k for k in subset if k in scores and np.isfinite(scores[k])]
    pred = np.array([scores[k] for k in usable])
    surf = np.array([surface.variants[k].dms_score for k in usable])
    func = np.array([function.variants[k].dms_score for k in usable])
    blos = np.array([float(blosum62(surface.variants[k].wt_aa, surface.variants[k].mut_aa)) for k in usable])

    with open(args.out_csv, "w") as fh:
        fh.write("mutant,position,wt_aa,mut_aa,esm2_masked_marginal,blosum62,surface_dms_score,function_dms_score\n")
        for k in usable:
            v = surface.variants[k]
            fh.write(f"{k},{v.position},{v.wt_aa},{v.mut_aa},{scores[k]:.6f},"
                     f"{blosum62(v.wt_aa, v.mut_aa)},{v.dms_score:.6f},{function.variants[k].dms_score:.6f}\n")

    an = protocol["analysis"]
    results: dict = {}
    for label, predictor in (("esm2_masked_marginal", pred), ("blosum62", blos)):
        rho_s = _spearman(predictor, surf)
        rho_f = _spearman(predictor, func)
        bs, bf, bd, _ = _paired_bootstrap(predictor, surf, func,
                                          an["bootstrap_resamples"], an["bootstrap_seed"], an["ci"])
        bs["point"], bf["point"], bd["point"] = rho_s, rho_f, rho_s - rho_f
        verdict, why = _verdict(bd)
        results[label] = {
            "rho_surface": bs,
            "rho_function": bf,
            "delta_rho_surface_minus_function": bd,
            "verdict_on_H1": verdict,
            "verdict_reason": why,
            "permutation_p_surface": _permutation_p(predictor, surf, rho_s,
                                                    an["permutation_resamples"], an["permutation_seed"]),
            "permutation_p_function": _permutation_p(predictor, func, rho_f,
                                                     an["permutation_resamples"], an["permutation_seed"]),
            "scipy_spearman_surface": float(spearmanr(predictor, surf).statistic),
            "scipy_spearman_function": float(spearmanr(predictor, func).statistic),
        }

    receipt = {
        "stage": "analysis",
        "protocol_id": protocol["protocol_id"],
        "analysed_utc": utc_now(),
        "git_sha": git_sha(os.path.dirname(os.path.abspath(__file__))),
        "environment": environment_fingerprint(),
        "checkpoint_used": state.get("checkpoint"),
        "scoring_invocations": state.get("invocations", []),
        "reference_checks": checks,
        "n_subset": len(subset),
        "n_usable": len(usable),
        "n_matched": len(matched),
        "acceptance": {
            "A2_at_least_200_usable": len(usable) >= 200,
            "A3_reference_checks_pass": all(c.get("passed", True) for c in checks if "passed" in c),
            "A4_intervals_present": True,
        },
        "coverage": common.coverage(usable, matched, surface, function),
        "external_reference": protocol["external_reference"],
        "results": results,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    digest = write_json(args.out_json, receipt)

    print(f"analysis receipt {args.out_json} sha256={digest}")
    print(f"usable variants: {len(usable)}/{len(subset)}  positions: "
          f"{receipt['coverage']['subset_distinct_positions']}")
    for label, r in results.items():
        d = r["delta_rho_surface_minus_function"]
        print(f"\n{label}")
        print(f"  rho surface  = {r['rho_surface']['point']:+.3f} "
              f"[{r['rho_surface']['ci_low']:+.3f}, {r['rho_surface']['ci_high']:+.3f}]  "
              f"perm p={r['permutation_p_surface']:.4g}")
        print(f"  rho function = {r['rho_function']['point']:+.3f} "
              f"[{r['rho_function']['ci_low']:+.3f}, {r['rho_function']['ci_high']:+.3f}]  "
              f"perm p={r['permutation_p_function']:.4g}")
        print(f"  delta        = {d['point']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}]  "
              f"-> H1 {r['verdict_on_H1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
