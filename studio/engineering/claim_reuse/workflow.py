"""Official MCP contribution client; credentials/lease capabilities never enter artifacts."""

import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import numpy as np
import scipy

from frontier.models import Draft, POLICY, Record, ref
from .compute import ART, CODE_FILES, ROOT, compute, dump, sha, utc

ENDPOINT = "https://frontier.morphoswarm.ai/mcp"
ACTOR = "fin-reuse-worker"
NAMESPACE = "delphi-frontier"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def action_draft(protocol, case, plan):
    return Draft(
        namespace=NAMESPACE,
        kind="Action",
        id="agent-fin-reuse-" + case["id"] + "-v1",
        issuer=ACTOR,
        source_uri="urn:frontier:claim-reuse:" + protocol["id"],
        payload={
            "target": protocol["claim_ref"],
            "inputs": [protocol["claim_ref"]],
            "title": "Exact-Claim consumed before calculation: "
            + case["id"]
            + " illustrative ray stiffness candidate",
            "acceptance_criteria": [
                "Exact source Claim and historical request pins verified before compute",
                "Fixed quadrature/null/mutant/FEM controls pass or failures retained",
                "Actual derived stiffness and invalid/valid model-domain outcome preserved",
                "Output hashes and exact Action producer recorded; independent review required",
            ],
            "required_capabilities": [
                "bounded local CPU",
                "Python with NumPy and SciPy",
                "official MCP contributor client",
            ],
            "cost_stop_bounds": "One CPU/thread,4GiB,128tasks,600s whole process; no cloud/GPU/network solver. Stop on pin mismatch or numerical-control failure; invalid candidate remains visible.",
            "cache_key": {
                "target": protocol["claim_ref"]["version"],
                "input": digest(
                    {
                        "claim": protocol["claim_ref"],
                        "request": protocol["source_request_sha256"],
                    }
                ),
                "code": digest(plan["code_files"]),
                "model": "existing static Euler-Bernoulli beam and declared load bridge",
                "environment": sha(ART / "environment.json"),
                "parameters": digest(case),
                "scope": protocol["scope"],
                "acceptance_policy": POLICY,
            },
            "proposal": {
                "intent": "simulation",
                "method": protocol["input_binding"] + " Reuse installed beam adapter.",
                "assumptions": [
                    "Original declared illustration context only; critical stiffness Claim remains unreviewed",
                    "Selected EI is an assumed design parameter, not measured ray stiffness",
                ],
                "alternatives": [
                    {
                        "label": "lower-load",
                        "description": "Reduce the fixed load rather than increase EI",
                        "tradeoff": "Changes original Claim context and requires another protocol",
                    }
                ],
                "expected_information": case["question"],
                "decision_context": "Keep or reject a stiffness candidate within the stated linear-model domain; no fish feasibility decision",
                "expected_outputs": [
                    "Effective input binding, beam profile, result/control and provenance receipts"
                ],
                "controls": protocol["controls"],
                "analysis_plan": "Compare16/32/64element profiles with existing analytic solution; preserve every model-domain flag and fixed control outcome.",
                "outcomes": [
                    {
                        "label": "inside-domain",
                        "criterion": "Declared validity thresholds satisfied",
                        "decision_consequence": "Retain as illustrative linear-model candidate only",
                    },
                    {
                        "label": "outside-domain",
                        "criterion": "Declared validity threshold exceeded",
                        "decision_consequence": "Reject this linear-model candidate; do not interpret invalid deformation biologically",
                    },
                    {
                        "label": "unknown",
                        "criterion": "Pin or numerical check fails",
                        "decision_consequence": "Keep blocker; no acceptance claim",
                    },
                ],
                "selection_basis": "manual",
                "selection_rationale": "Two predeclared stiffness margins from the same consumed exact Claim; no utility/agency comparison",
                "limitations": [
                    protocol["scope"],
                    "Shared source/model/conditions; no biological calibration or independent samples",
                ],
            },
        },
    ).model_dump()


def artifact(path, role):
    p = Path(path)
    media = "text/csv" if p.suffix == ".csv" else "application/json"
    return {
        "title": p.name,
        "uri": "urn:sha256:" + sha(p),
        "sha256": sha(p),
        "byte_size": p.stat().st_size,
        "media_type": media,
        "role": role,
        "availability": "referenced",
        "license": None,
    }


def evidence_draft(protocol, case, target_action, result, plan, folder):
    output = folder / "result.json"
    return Draft(
        namespace=NAMESPACE,
        kind="Evidence",
        id="agent-fin-reuse-evidence-" + case["id"] + "-v1",
        issuer=ACTOR,
        source_uri="urn:frontier:claim-reuse:" + protocol["id"],
        payload={
            "target": protocol["claim_ref"],
            "produced_by": target_action,
            "evidence_kind": "simulated",
            "relation": "qualifies",
            "source": {
                "uri": "urn:sha256:" + sha(output),
                "locator": "result.json at code revision " + plan["code_commit"],
                "source_version": plan["code_commit"],
                "content_sha256": sha(output),
                "content_available": False,
                "access": "Reference metadata only; actual generated bytes retained in the committed artifact directory; publication/availability projection is separate",
                "license": None,
            },
            "created_time": {"value": result["finished_at_utc"], "basis": "witnessed"},
            "retrieved_time": {"value": utc(), "basis": "witnessed"},
            "method": "Exact Claim read and validated BEFORE deriving solver EI; actual installed load bridge and beam FEM/analytic/null/mutant/grid checks executed, not imported or retroactively linked",
            "context": protocol["scope"],
            "assumptions": [
                "All original source Claim assumptions retained",
                "Stiffness selected by predeclared rational margin, not measured",
            ],
            "provenance": {
                "protocol_sha256": sha(ART / "protocol.json"),
                "protocol_commit": plan["protocol_commit"],
                "code_commit": plan["code_commit"],
                "code_files": plan["code_files"],
                "before_run_claim_read_sha256": sha(
                    folder / "claim-read-before-run.json"
                ),
                "effective_inputs_sha256": sha(folder / "effective-inputs.json"),
                "result_sha256": sha(output),
                "numerical_checks_passed": result["numerical_checks_passed"],
                "model_domain_valid": result["model_domain_valid"],
            },
            "source_dependence": {
                "group": protocol["id"],
                "independence": "Shared exact Claim, historical request and solver; two stiffness scenarios, not independent biological samples",
            },
            "uncertainty": "Deterministic numerical approximation under declared inputs; biological calibration/parameter uncertainty unknown; no success probability",
            "limitations": list(result["limitations"])
            + ["No acceptance by producing actor; separate operator review required"],
            "artifacts": [
                artifact(ART / "protocol.json", "protocol"),
                artifact(ART / "source-request.json", "input"),
                artifact(ART / "source-result.json", "input"),
                artifact(ART / "code-pin.json", "code"),
                artifact(ART / "environment.json", "environment"),
                artifact(folder / "claim-read-before-run.json", "input"),
                artifact(folder / "effective-inputs.json", "input"),
                artifact(output, "output"),
                artifact(folder / "profile.csv", "output"),
            ],
        },
    ).model_dump()


class Client:
    def __init__(self, session, token, transcript):
        self.session, self.secrets, self.path = session, [token], transcript
        self.entries = []

    def safe(self, value):
        if isinstance(value, dict):
            return {
                k: ("[redacted bearer capability]" if k == "lease_id" else self.safe(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.safe(v) for v in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[redacted bearer capability]")
        return value

    async def call(self, name, arguments):
        started = utc()
        response = await self.session.call_tool(name, arguments)
        if response.isError:
            self.entries.append(
                {
                    "tool": name,
                    "started_at_utc": started,
                    "finished_at_utc": utc(),
                    "error": True,
                    "arguments": self.safe(arguments),
                }
            )
            dump(self.path, self.entries)
            raise RuntimeError("MCP tool failed; inspect safe transcript: " + name)
        value = json.loads(response.content[0].text)
        if name == "frontier_lease":
            self.secrets.append(value["lease_id"])
        self.entries.append(
            {
                "tool": name,
                "started_at_utc": started,
                "finished_at_utc": utc(),
                "arguments": self.safe(arguments),
                "response": self.safe(value),
            }
        )
        dump(self.path, self.entries)
        return value


async def workflow(args):
    protocol = json.loads((ART / "protocol.json").read_text())
    token = Path(args.credential_file).read_text().strip()
    if not 24 <= len(token) <= 512:
        raise ValueError("Invalid credential file")
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=False, headers={"Authorization": "Bearer " + token}
    ) as http:
        async with streamable_http_client(ENDPOINT, http_client=http) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                client = Client(
                    session,
                    token,
                    ART
                    / (
                        "mcp-"
                        + args.phase
                        + ("-" + args.case if args.case else "")
                        + ".json"
                    ),
                )
                caps = await client.call("frontier_capabilities", {})
                if caps["principal"]["actor"] != ACTOR or caps["principal"][
                    "roles"
                ] != ["contributor"]:
                    raise ValueError("Wrong worker principal or roles")
                if args.phase == "propose":
                    env = {
                        "python": platform.python_version(),
                        "numpy": np.__version__,
                        "scipy": scipy.__version__,
                        "mcp": version("mcp"),
                        "httpx": httpx.__version__,
                        "machine": platform.machine(),
                        "threads": 1,
                        "thread_environment": {
                            k: os.environ.get(k)
                            for k in (
                                "OMP_NUM_THREADS",
                                "OPENBLAS_NUM_THREADS",
                                "MKL_NUM_THREADS",
                            )
                        },
                        "scope": "Actual local CPU interpreter, no GPU execution",
                    }
                    dump(ART / "environment.json", env)
                    plan = {
                        "protocol_commit": subprocess.check_output(
                            [
                                "git",
                                "log",
                                "-1",
                                "--format=%H",
                                "--",
                                "artifacts/claim-reuse/protocol.json",
                            ],
                            cwd=ROOT,
                            text=True,
                        ).strip(),
                        "code_commit": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                        ).strip(),
                        "code_files": {p: sha(ROOT / p) for p in CODE_FILES},
                        "actions": {},
                    }
                    dump(
                        ART / "code-pin.json",
                        {
                            k: plan[k]
                            for k in ("protocol_commit", "code_commit", "code_files")
                        },
                    )
                    claim = await client.call(
                        "frontier_get", {"target": protocol["claim_ref"]}
                    )
                    Record.model_validate(claim["record"])
                    if ref(claim["record"]) != protocol["claim_ref"]:
                        raise ValueError(
                            "Exact Claim retrieval returned another record"
                        )
                    for case in protocol["cases"]:
                        draft = action_draft(protocol, case, plan)
                        dump(ART / ("action-draft-" + case["id"] + ".json"), draft)
                        proposed = await client.call(
                            "frontier_propose",
                            {
                                "draft": draft,
                                "idempotency_key": protocol["id"]
                                + "-propose-"
                                + case["id"],
                            },
                        )
                        Record.model_validate(proposed["record"])
                        plan["actions"][case["id"]] = ref(proposed["record"])
                        dump(ART / "execution-plan.json", plan)
                    print(
                        json.dumps(
                            {
                                "phase": "proposed",
                                "actions": plan["actions"],
                                "execution": False,
                            },
                            indent=2,
                        )
                    )
                elif args.phase == "run":
                    case = next(c for c in protocol["cases"] if c["id"] == args.case)
                    plan = json.loads((ART / "execution-plan.json").read_text())
                    target = plan["actions"][case["id"]]
                    if any(sha(ROOT / p) != h for p, h in plan["code_files"].items()):
                        raise ValueError("Frozen execution code changed")
                    folder = ART / case["id"]
                    if (folder / "execution-attempt.json").exists():
                        raise ValueError(
                            "Execution attempt exists; reconcile rather than duplicate the run"
                        )
                    current = await client.call("frontier_get", {"target": target})
                    if current["action"]["state"] != "ready" or current["record"][
                        "payload"
                    ]["inputs"] != [protocol["claim_ref"]]:
                        raise ValueError(
                            "Coordinator readiness or exact Claim input missing"
                        )
                    folder.mkdir(exist_ok=True)
                    dump(
                        folder / "execution-attempt.json",
                        {
                            "started_at_utc": utc(),
                            "action": target,
                            "note": "No lease bearer is persisted; retries require reconciliation",
                        },
                    )
                    leased = await client.call(
                        "frontier_lease",
                        {
                            "target": target,
                            "seconds": protocol["resources"]["lease_seconds"],
                            "idempotency_key": protocol["id"] + "-lease-" + case["id"],
                        },
                    )
                    capability = leased["lease_id"]
                    await client.call(
                        "frontier_transition",
                        {
                            "target": target,
                            "state": "running",
                            "lease_id": capability,
                            "idempotency_key": protocol["id"]
                            + "-running-"
                            + case["id"],
                        },
                    )
                    claim = await client.call(
                        "frontier_get", {"target": protocol["claim_ref"]}
                    )
                    dump(folder / "claim-read-before-run.json", claim)
                    result = compute(claim["record"], protocol, case, folder)
                    draft = evidence_draft(protocol, case, target, result, plan, folder)
                    dump(folder / "evidence-draft.json", draft)
                    evidence = await client.call(
                        "frontier_propose",
                        {
                            "draft": draft,
                            "idempotency_key": protocol["id"]
                            + "-evidence-"
                            + case["id"],
                        },
                    )
                    dump(folder / "evidence-receipt.json", evidence)
                    final_state = (
                        "submitted" if result["numerical_checks_passed"] else "failed"
                    )
                    await client.call(
                        "frontier_transition",
                        {
                            "target": target,
                            "state": final_state,
                            "lease_id": capability,
                            "idempotency_key": protocol["id"]
                            + "-"
                            + final_state
                            + "-"
                            + case["id"],
                        },
                    )
                    final = await client.call("frontier_get", {"target": target})
                    dump(folder / "action-readback.json", final)
                    print(
                        json.dumps(
                            {
                                "phase": final_state,
                                "case": case["id"],
                                "action": target,
                                "evidence": ref(evidence["record"]),
                                "model_domain_valid": result["model_domain_valid"],
                                "numerical_checks_passed": result[
                                    "numerical_checks_passed"
                                ],
                                "local_status": evidence["local_status"],
                                "biological_success_probability": None,
                            },
                            indent=2,
                        )
                    )
                else:
                    plan = json.loads((ART / "execution-plan.json").read_text())
                    graph = await client.call(
                        "frontier_neighborhood",
                        {"target": protocol["claim_ref"], "limit": 50},
                    )
                    dump(ART / "claim-neighborhood.json", graph)
                    uses = [
                        e
                        for e in graph["edges"]
                        if e["relation"] == "uses"
                        and e["target"] == protocol["claim_ref"]
                        and e["source"] in plan["actions"].values()
                    ]
                    result = {
                        "claim_ref": protocol["claim_ref"],
                        "distinct_recorded_action_uses": len(
                            {e["source"]["version"] for e in uses}
                        ),
                        "edges": uses,
                        "truncated": graph.get("truncated"),
                        "scope": "Actual typed input reuse, not independent confirmation or measured time/cost/agency benefit",
                    }
                    dump(ART / "reuse-verification.json", result)
                    print(json.dumps(result, indent=2))
                # Only scan this task's bounded artifacts; never emit the secrets.
                for path in ART.rglob("*"):
                    if path.is_file() and any(
                        s.encode() in path.read_bytes() for s in client.secrets
                    ):
                        raise RuntimeError("Secret material detected in task artifacts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["propose", "run", "verify"])
    parser.add_argument("--case", choices=["below-threshold", "above-threshold"])
    parser.add_argument("--credential-file", required=True)
    args = parser.parse_args()
    if args.phase == "run" and not args.case:
        parser.error("--case required for run")
    asyncio.run(workflow(args))
