"""Audit actual contribution receipts and plot saved states, without changing solver inputs."""

from datetime import datetime
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from frontier.models import Record, ref
from .compute import ART, ROOT, dump, sha


def report():
    protocol = json.loads((ART / "protocol.json").read_text())
    plan = json.loads((ART / "execution-plan.json").read_text())
    reuse = json.loads((ART / "reuse-verification.json").read_text())
    assert not reuse["truncated"]
    assert (
        len({(e["source"]["namespace"], e["source"]["id"]) for e in reuse["edges"]})
        == 2
    )
    assert {e["source"]["version"] for e in reuse["edges"]} == {
        r["version"] for r in plan["actions"].values()
    }
    assert all(
        e["relation"] == "uses" and e["target"] == protocol["claim_ref"]
        for e in reuse["edges"]
    )
    for name, digest in plan["code_files"].items():
        assert sha(ROOT / name) == digest, name
    assert sha(ART / "protocol.json") == plan["protocol_sha256"]
    file_index = {sha(p): p for p in ART.rglob("*") if p.is_file()}
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), dpi=130)
    for case in protocol["cases"]:
        folder = ART / case["id"]
        result = json.loads((folder / "result.json").read_text())
        params = json.loads((folder / "effective-inputs.json").read_text())
        claim = json.loads((folder / "claim-read-before-run.json").read_text())
        evidence = json.loads((folder / "evidence-receipt.json").read_text())
        action = json.loads((folder / "action-readback.json").read_text())
        for record in (claim["record"], evidence["record"], action["record"]):
            Record.model_validate(record)
        assert ref(claim["record"]) == protocol["claim_ref"]
        assert (
            ref(action["record"]) == plan["actions"][case["id"]] and action["is_head"]
        )
        assert action["record"]["payload"]["inputs"] == [protocol["claim_ref"]]
        assert evidence["record"]["payload"]["produced_by"] == ref(action["record"])
        assert evidence["record"]["payload"]["target"] == protocol["claim_ref"]
        assert (
            action["action"]["state"] == "submitted"
            and evidence["local_status"] == "proposed"
        )
        for artifact in evidence["record"]["payload"]["artifacts"]:
            assert artifact["sha256"] in file_index
            assert (
                file_index[artifact["sha256"]].stat().st_size == artifact["byte_size"]
            )
        for name, digest in result["files"].items():
            assert sha(folder / name) == digest
        transcript = json.loads((ART / ("mcp-run-" + case["id"] + ".json")).read_text())
        tools = [r["tool"] for r in transcript]
        lease = tools.index("frontier_lease")
        transitions = [
            (i, r["arguments"]["state"])
            for i, r in enumerate(transcript)
            if r["tool"] == "frontier_transition"
        ]
        running = next(i for i, s in transitions if s == "running")
        submitted = next(i for i, s in transitions if s == "submitted")
        read = next(
            i
            for i, r in enumerate(transcript)
            if r["tool"] == "frontier_get"
            and r["arguments"]["target"] == protocol["claim_ref"]
        )
        propose = tools.index("frontier_propose")
        assert lease < running < read < propose < submitted
        assert (
            datetime.fromisoformat(transcript[read]["finished_at_utc"])
            <= datetime.fromisoformat(params["bound_before_solver_at_utc"])
            <= datetime.fromisoformat(result["started_at_utc"])
            <= datetime.fromisoformat(result["finished_at_utc"])
            <= datetime.fromisoformat(transcript[propose]["started_at_utc"])
        )
        assert (
            result["numerical_checks_passed"]
            and result["declared_domain_predicate_matches"]
        )
        values = np.genfromtxt(folder / "profile.csv", delimiter=",", names=True)
        color = "#a83d35" if not result["model_domain_valid"] else "#227d69"
        label = (
            case["margin_exact"]
            + " × EIcrit; "
            + ("outside" if not result["model_domain_valid"] else "inside")
            + " declared domain"
        )
        axes[0].plot(
            values["x_m"] * 1000, values["w64_m"] * 1000, label=label, color=color
        )
        axes[0].plot(
            values["x_m"] * 1000,
            values["analytic_w_m"] * 1000,
            color=color,
            ls=":",
            lw=1,
        )
        rows.append(
            {
                "case": case["id"],
                "action_ref": ref(action["record"]),
                "evidence_ref": ref(evidence["record"]),
                "actual_Claim_consumed_before_solver": True,
                "parsed_EIcrit_Nm2_exact": params["claim_critical_EI_exact"],
                "solver_EI_Nm2_exact": params["solver_EI_Nm2_exact"],
                "tip_over_L": result["validity"]["tip_over_L"],
                "tip_over_L_limit": result["validity"]["tip_over_L_limit"],
                "max_slope_rad": result["validity"]["max_slope_rad"],
                "model_domain_valid": result["model_domain_valid"],
                "numerical_checks_passed": result["numerical_checks_passed"],
                "result_sha256": sha(folder / "result.json"),
                "profile_sha256": sha(folder / "profile.csv"),
                "action_state_at_readback": action["action"]["state"],
                "evidence_status_at_submission": evidence["local_status"],
                "wall_seconds": result["wall_seconds"],
            }
        )
    axes[0].set(
        xlabel="Ray coordinate (mm)",
        ylabel="Linear-model deflection (mm)",
        title="Actual FEM states; dotted: same-model analytic curve",
    )
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.2)
    axes[1].bar(
        [r["case"] for r in rows],
        [r["tip_over_L"] for r in rows],
        color=["#a83d35" if not r["model_domain_valid"] else "#227d69" for r in rows],
    )
    limit = rows[0]["tip_over_L_limit"]
    assert all(r["tip_over_L_limit"] == limit for r in rows)
    axes[1].axhline(
        limit, color="black", ls="--", label=f"Frozen declared tip/L limit {limit:g}"
    )
    axes[1].set(
        ylabel="Computed tip deflection / span",
        title="Counterexample retained; no biological success claim",
    )
    axes[1].legend(fontsize=8)
    fig.suptitle("One exact Claim consumed by two distinct leased computations")
    fig.text(
        0.03,
        0.015,
        "Declared illustration only. Shared source/model; empirical validity, time saved and collective benefit are unknown.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(ART / "candidate-profiles.png")
    plt.close(fig)
    summary = {
        "schema": "frontier.claim-reuse.audit/1",
        "claim_ref": protocol["claim_ref"],
        "distinct_current_action_ids_with_recorded_input_use": len(rows),
        "distinct_shared_claim_versions": 1,
        "causal_read_and_input_binding_before_each_solver": True,
        "cases": rows,
        "review_scope": "Producer submission only; independent review is separate and may occur later than these captured readbacks",
        "original_proposals": "Ready but never leased/run, superseded before compute for cache identity strengthening; excluded from executed reuse count",
        "time_or_cost_saved": None,
        "collective_benefit": None,
        "biological_success_probability": None,
        "empirical_validation": "unknown",
        "scope": protocol["scope"],
    }
    dump(ART / "audit.json", summary)
    dump(
        ART / "report-provenance.json",
        {
            "postprocessing_code_sha256": sha(__file__),
            "inputs": {
                "protocol": sha(ART / "protocol.json"),
                "reuse_edges": sha(ART / "reuse-verification.json"),
                "results": {r["case"]: r["result_sha256"] for r in rows},
                "profiles": {r["case"]: r["profile_sha256"] for r in rows},
            },
            "outputs": {
                "audit.json": sha(ART / "audit.json"),
                "candidate-profiles.png": sha(ART / "candidate-profiles.png"),
            },
        },
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    report()
