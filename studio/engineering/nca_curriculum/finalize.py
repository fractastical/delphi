"""Package audited curriculum outcomes; never train, rescore or select a model."""

from engineering.nca_pattern.analyze import digest, load
from engineering.nca_pattern.model import ROOT, dump

ART = ROOT / "artifacts/nca-curriculum"


def run():
    audit = load(ART / "returned-analysis/audit.json")
    summary = load(ART / "run/summary.json")
    receipt = load(ART / "run/job-receipt.json")
    cfg = load(ART / "runtime-protocol.json")
    if digest(ART / "run/job-receipt.json") != audit["job_receipt_sha256"]:
        raise ValueError("Audited native receipt changed")
    records = audit["records"]
    kinds = ["persistence", *cfg["evaluation"]["damage"]["masks"]]
    by_kind = []
    for kind in kinds:
        groups = {}
        for regime in cfg["training"]["regimes"]:
            rows = [x for x in records if x["kind"] == kind and x["model_id"].startswith(regime + "-")]
            groups[regime] = {"passed": sum(x["recomputed_passed"] for x in rows), "executed": len(rows), "declared": 12}
        by_kind.append({"kind": kind, "regimes": groups})
    regimes = []
    for regime in cfg["training"]["regimes"]:
        rows = [x for x in records if x["kind"] != "all-erased-negative" and x["model_id"].startswith(regime + "-")]
        regimes.append({"regime": regime, "passed": sum(x["recomputed_passed"] for x in rows), "tested": len(rows), "declared": 96})
    paired = [x for x in audit["per_pair_effects"] if x["group"] == "all_design"]
    table = "\n".join(
        f"| {x['kind']} | {x['regimes']['damage-pool']['passed']}/12 | {x['regimes']['curriculum-pool']['passed']}/12 |"
        for x in by_kind
    )
    text = f"""# Question outcome: targeted repair and persistence trade off

The declared comparison completed: eight final 2000-step models, four matched initialization pairs, all 192 design probes and eight separate erased controls. **Baseline {regimes[0]['passed']}/96 versus curriculum {regimes[1]['passed']}/96: no aggregate benefit in these declared probes.** Overall {audit['counts']['design_passed']}/192 design predicates passed; all failed predicates remain in the raw records.

| Endpoint family | Three-circle baseline | Prefix curriculum |
| --- | --- | --- |
{table}

Targeted prefix30/34 repair improved while persistence declined. This is a computational pattern tradeoff, not tissue regeneration. Each row's twelve probes share four learned models per regime and are dependent. The replicate units are the four paired initializations. Their all-design curriculum-minus-baseline fractions are {[x['curriculum_minus_baseline_fraction'] for x in paired]}; mean {(regimes[1]['passed'] - regimes[0]['passed']) / 96:.6g}. These are descriptive comparisons, not a biological success probability or a population effect estimate. The full predeclared per-pair endpoint breakdown is in audit.json; no best model is substituted for the ensemble.

The eight erased-state controls are excluded from 192 and establish only the rule's absorbing-zero behavior. All cases use independently committed fresh update seeds and damage masks, but the same fixed design target. Old 0/48 and 32/48 experiments remain unchanged and have different evaluation sets; those rates are not directly compared as a new benchmark improvement.

The frozen auditor checked {audit['files_checked']} native file digests, all 200 identities, eight checkpoint pins, four matched initialization/update budgets, guard order and selected all-channel damage states. {audit['nonexact_metric_count']} metric reductions differ bit-for-bit, maximum {audit['max_metric_absolute_difference']:.17g}; exact reproduction is {audit['exact_metric_reproduction']}. The separately frozen fixed-roundoff diagnostic is {audit['fixed_roundoff_metric_reproduction']}. No threshold or outcome was changed. Intermediate unsaved whole-state assertions still rely on source-pinned saved metrics; there was no independent training rerun.

The movie contains 26 actual saved frames for each of the eight preselected prefix34 trajectories, including before/after erasure at update256. It does not show long-horizon persistence, so read the persistence table alongside the movie. Display clipping does not affect metrics. Pixels, updates and twelve hidden channels have no measured biological interpretation.

Next open question: can a separately preregistered local-rule or training-policy comparison retain the observed repair gains without losing persistence, using new evaluation cases? No new job is proposed before this result is reviewed. Material mechanics, genetic implementation, nervous systems and organism feasibility remain unsupported bridges.
"""
    (ART / "QUESTION-OUTCOME.md").write_text(text)
    names = {
        "protocol": "protocol.json", "runtime_protocol": "runtime-protocol.json",
        "audit": "returned-analysis/audit.json", "report": "returned-analysis/RESULTS.md",
        "question_outcome": "QUESTION-OUTCOME.md", "receipt": "run/job-receipt.json",
        "checkpoint_barrier": "run/checkpoint-before-holdout.json",
        "read_guard": "run/evaluation-read-guard.json", "raw_manifest": "raw-manifest.json",
        "video": "returned-analysis/curriculum-trajectories.mp4",
        "poster": "returned-analysis/poster.png", "training_plot": "returned-analysis/training-and-evaluation.png",
        "render_provenance": "returned-analysis/render-provenance.json",
    }
    refs = {name: {"path": str((ART / path).relative_to(ROOT)), "sha256": digest(ART / path), "bytes": (ART / path).stat().st_size} for name, path in names.items()}
    dump(ART / "index.json", {
        "schema": "frontier.nca.curriculum.model-card/1", "id": "nca-curriculum",
        "execution_status": summary["status"], "inverse_objective_status": "Targeted repair gains with persistence cost; no aggregate benefit in declared probes",
        "counts": audit["counts"], "regime_counts": regimes, "by_kind": by_kind,
        "paired_effects": audit["per_pair_effects"], "replicate_unit": "four paired training initializations; probes within model dependent",
        "empirical_validation": "unknown", "biological_success_probability": None,
        "evaluation_status": "Fresh independently committed cases/seeds; one previously fitted design target, not new-target generalization",
        "artifacts": refs, "question": load(ART / "protocol.json")["question"],
        "native_job_id": "aijob-e00wmj8t8ndzvcpfja", "environment": receipt["environment"], "device": receipt["device"],
        "native_science_wall_seconds": receipt["wall_seconds"], "dollars": None,
        "limits": [
            "Computational local-rule pattern, not observed tissue, DNA, a cell program or nervous-system implementation.",
            "Prefix30/34 repair improves while persistence falls; no aggregate benefit and no general biological probability.",
            "Four initialization pairs; shared weights, target and assumptions make update/mask probes dependent.",
            "Movie shows selected prefix34 recovery, not the separate 2048-update persistence endpoint.",
            "Exact floating reductions differ; separately named fixed-roundoff diagnostic is retained, not substituted.",
            "No exact training resume: pool not serialized. No independent training/hidden-trajectory replication.",
        ],
    })
    files = [x for x in ART.rglob("*") if x.is_file() and x.name != "artifact-manifest.json"]
    dump(ART / "artifact-manifest.json", {"schema": "frontier.nca.curriculum.artifacts/1", "files": [
        {"path": str(path.relative_to(ART)), "sha256": digest(path), "bytes": path.stat().st_size}
        for path in sorted(files)
    ]})


if __name__ == "__main__":
    run()
