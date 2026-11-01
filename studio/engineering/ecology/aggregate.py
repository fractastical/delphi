"""Join disjoint returned arms without changing either immutable source receipt."""

from hashlib import sha256
import json
from pathlib import Path

from .model import ART, dump
from .sensitivity_plot import render


def combine(initial, continuation, protocol):
    """Refuse changed, repeated or newly invented scientific arms."""
    original = {x["id"]: x for x in initial["results"]}
    completed = {k: v for k, v in original.items() if v["status"] == "computed"}
    missing = {
        k
        for k, v in original.items()
        if v["status"] == "not-started: soft deadline reached"
    }
    additions = continuation["results"]
    ids = [x["id"] for x in additions]
    if len(ids) != len(set(ids)) or set(ids) != missing or set(ids) & set(completed):
        raise ValueError(
            "Aggregate would duplicate, replace or invent a scientific arm"
        )
    expected = {
        f"{setting['id']}-s{seed}-{'neighbors' if mode else 'ablated'}": {
            "id": f"{setting['id']}-s{seed}-{'neighbors' if mode else 'ablated'}",
            "setting": setting["id"],
            "overrides": setting["overrides"],
            "seed": seed,
            "neighbors": mode,
        }
        for setting in protocol["settings"]
        for seed in protocol["seeds"]
        for mode in protocol["neighbor_modes"]
    }
    for item in additions:
        if item["task"] != expected[item["id"]]:
            raise ValueError("Continuation changed frozen task recipe")
    joined = {**completed, **{x["id"]: x for x in additions}}
    if set(joined) != set(expected):
        raise ValueError("Aggregate does not cover exact declared identities")
    paired = []
    for setting in protocol["settings"]:
        for seed in protocol["seeds"]:
            values = [
                joined[f"{setting['id']}-s{seed}-{name}"]
                for name in ("neighbors", "ablated")
            ]
            eligible = all(
                x["status"] == "computed"
                and x["numeric_gate_passed"]
                and all(x["actuator_gates"].values())
                and x["endpoint"]["available"]
                for x in values
            )
            row = {"setting": setting["id"], "seed": seed, "eligible": eligible}
            for name, field in [
                ("response_count_difference", "response_count"),
                ("positive_work_difference_J", "positive_work_J"),
                ("lateral_displacement_difference_m", "mean_lateral_displacement_m"),
            ]:
                row[name] = (
                    values[0]["endpoint"][field] - values[1]["endpoint"][field]
                    if eligible
                    else None
                )
            paired.append(row)
    return {
        "schema": "frontier.ecology.aggregate-results/1",
        "status": "all declared arms computed"
        if all(x["status"] == "computed" for x in joined.values())
        else "partial or failed",
        "scenario_count": len(expected),
        "computed_count": sum(x["status"] == "computed" for x in joined.values()),
        "initial_native_status_unchanged": initial["status"],
        "continuation_native_status": continuation["status"],
        "results": [joined[k] for k in expected],
        "paired_comparisons": paired,
        "scope": "Exact disjoint union of original26 and separately executed2 missing arms; source partial receipts remain immutable. Shared-model axial scenarios, not biological success probabilities.",
    }


def run():
    paths = [
        ART / "uncertainty-initial/summary.json",
        ART / "uncertainty-continuation/raw-science/summary.json",
    ]
    initial, continuation = [json.loads(p.read_text()) for p in paths]
    audits = [
        ART / "uncertainty-initial/audit.json",
        ART / "uncertainty-continuation/audit.json",
    ]
    if (
        continuation["original_summary_sha256"]
        != sha256(paths[0].read_bytes()).hexdigest()
    ):
        raise ValueError("Continuation parent summary changed")
    for path, source in zip(audits, paths, strict=True):
        audit = json.loads(path.read_text())
        if (
            audit["raw_source_summary_sha256"]
            != sha256(source.read_bytes()).hexdigest()
        ):
            raise ValueError("Audited source summary changed")
        if not (
            audit["source_identity_passed"]
            and audit["exact_metric_reproduction"]
            and audit["fixed_roundoff_force_pose_replay"]
        ):
            raise ValueError("Source audit failed; aggregate not published as checked")
    result = combine(
        initial,
        continuation,
        json.loads((ART / "uncertainty-protocol.json").read_text()),
    )
    result["parents"] = [
        {"path": str(p.relative_to(ART)), "sha256": sha256(p.read_bytes()).hexdigest()}
        for p in paths + audits
    ]
    result["analysis_code_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    out = ART / "uncertainty-aggregate/summary.json"
    dump(out, result)
    render(out, out.with_name("paired-sensitivity.png"))
    print({"status": result["status"], "computed": result["computed_count"]})


if __name__ == "__main__":
    run()
