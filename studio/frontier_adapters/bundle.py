"""Assemble a PROPOSED Claim + Evidence pair and its unsigned nanopub drafts. Nothing is submitted or published."""
from __future__ import annotations

import json
import os
import subprocess

from . import nanopub_draft as nd
from .artifacts import find_abs_paths
from .common import iso_utc, sha_bytes, sha_obj, validate_draft


def _frontier_commit() -> str | None:
    p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the repository this package lives in
    try:
        return subprocess.run(["git", "-C", p, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def assemble(claim_draft: dict, evidence_from_target, *, out_dir: str, created_at: str | None = None) -> dict:
    """`evidence_from_target(target_ref) -> evidence draft`. The Evidence is pinned to the Claim's exact version."""
    created_at = created_at or iso_utc()
    claim = validate_draft(claim_draft, created_at)
    c = claim["record"]
    target = {k: c[k] for k in ("namespace", "kind", "id", "version")}
    ev_draft = evidence_from_target(target)
    ev = validate_draft(ev_draft, created_at)
    e = ev["record"]
    if claim["licence_gate_offenders"] or ev["licence_gate_offenders"]:
        raise nd.ExportRefused(f"store licence gate would refuse: {claim['licence_gate_offenders'] + ev['licence_gate_offenders']}")
    claim_trig = nd.record_to_trig(c)
    ev_trig = nd.record_to_trig(e, target_claim=c)
    checks = {"claim": nd.validate_trig(claim_trig), "evidence": nd.validate_trig(ev_trig)}
    if not all(v["four_graphs"] and v["balanced"] and not v["blank_node_labels"] for v in checks.values()):
        raise nd.ExportRefused(f"structural check failed: {checks}")
    os.makedirs(out_dir, exist_ok=True)
    files = {"records.json": json.dumps([c, e], indent=2, sort_keys=True) + "\n",
             "claim.draft.trig": claim_trig, "evidence.draft.trig": ev_trig}
    for n, t in files.items():
        with open(os.path.join(out_dir, n), "w") as fh:
            fh.write(t)
    manifest = {
        "status": "PROPOSED. Not submitted to any store, not accepted, not published. single-reader, not Codex-reviewed.",
        "created_at": created_at,
        "records": [{"kind": r["kind"], "id": r["id"], "namespace": r["namespace"], "version": r["version"],
                     "payload_sha256": sha_obj(r["payload"])} for r in (c, e)],
        "evidence_targets_exact_claim_version": e["payload"]["target"]["version"] == c["version"],
        "original_delphi": {"claim_iri": c["source_uri"], "nanopub_uri": c["payload"]["source_record_version"],
                            "registry": c["payload"]["prior_review"]["delphi_original"]["registry"]},
        "validated_with": {"frontier_models": "frontier.models.Draft/make_record + store._unlicensed_available_content",
                           "frontier_commit_read": _frontier_commit(), "licence_gate_offenders": []},
        "trig_structure": checks,
        "file_sha256": {n: sha_bytes(t.encode()) for n, t in files.items()},
        "publication": "none. nanopub_draft has no publish function; drafts carry de:signatureStatus UNSIGNED DRAFT.",
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        fh.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def assemble_many(claim_drafts: dict, evidence_plans: list, *, out_dir: str, created_at: str | None = None, action_builder=None) -> dict:
    """Claims -> (optional) Action per evidence -> Evidence, all pinned by exact version. Nothing is submitted.

    `evidence_plans`: [(claim_id, builder)] where `builder(target_ref, action_ref_or_None) -> evidence draft`.
    `action_builder(target_ref, claim_refs) -> action draft` (omit for no Action).
    Order matters: each version digest depends on the records it points to, so Claims are made first, then Actions,
    then Evidence. `chain.json` is the claim -> action -> evidence -> artifact graph with every link check.
    """
    created_at = created_at or iso_utc()
    os.makedirs(out_dir, exist_ok=True)
    records, trig, offenders = {}, {}, []
    for cid, d in claim_drafts.items():
        v = validate_draft(d, created_at)
        records[("Claim", cid)] = v["record"]
        offenders += v["licence_gate_offenders"]
    claim_ref = lambda cid: {k: records[("Claim", cid)][k] for k in ("namespace", "kind", "id", "version")}
    chain_ev = []
    for cid, builder in evidence_plans:
        target = claim_ref(cid)
        action_ref = None
        if action_builder:
            ad = action_builder(target, [claim_ref(cid)])
            av = validate_draft(ad, created_at)
            records[("Action", ad["id"])] = av["record"]
            action_ref = {k: av["record"][k] for k in ("namespace", "kind", "id", "version")}
        ed = builder(target, action_ref)
        ev = validate_draft(ed, created_at)
        records[("Evidence", ed["id"])] = ev["record"]
        offenders += ev["licence_gate_offenders"]
        chain_ev.append((cid, ev["record"], action_ref))
    if offenders:
        raise nd.ExportRefused(f"store licence gate would refuse: {offenders}")
    checks = {}
    for (kind, rid), rec in records.items():
        tc = records[("Claim", rec["payload"]["target"]["id"])] if kind == "Evidence" else None
        t = nd.record_to_trig(rec, target_claim=tc)
        trig[f"{kind.lower()}--{rid}.draft.trig"] = t
        checks[f"{kind}/{rid}"] = nd.validate_trig(t)
    if not all(v["four_graphs"] and v["balanced"] and not v["blank_node_labels"] for v in checks.values()):
        raise nd.ExportRefused(f"structural check failed: {checks}")
    allrecs = [r for r in records.values()]
    bad = find_abs_paths(allrecs) + [x for t in trig.values() for x in find_abs_paths(t)]
    if bad:
        raise nd.ExportRefused(f"absolute local paths in output at {bad}")
    files = {"records.json": json.dumps(allrecs, indent=2, sort_keys=True) + "\n", **trig}
    for n, t in files.items():
        with open(os.path.join(out_dir, n), "w") as fh:
            fh.write(t)
    ev_recs = [e for _, e, _ in chain_ev]
    runs = {e["payload"]["provenance"]["run_id"] for e in ev_recs}
    chain = {
        "status": "PROPOSED. Not submitted, accepted or published. single-reader, not Codex-reviewed.",
        "counts": {"claims": len(claim_drafts), "actions_declared": sum(1 for k in records if k[0] == "Action"),
                   "evidence_records": len(ev_recs), "distinct_runs_behind_the_evidence": len(runs)},
        "reuse_counts": {
            "imported_records": len(allrecs),
            "declared_reuse": f"{sum(1 for k in records if k[0] == 'Action')} Action records pin Claim versions as inputs (declaration only: it does not show anything ran)",
            "executed_reuse": f"{len(runs)} run(s) joined to the Actions by receipt and hashed output artifacts; supervisor-reported completion plus an exit_code file of 0; "
                              "benefit not measured (no controlled comparison)",
            "independently_reviewed_reuse": 0},
        "claims": [{"id": c["id"], "version": c["version"], "delphi_iri": c["source_uri"],
                    "delphi_nanopub": c["payload"]["source_record_version"],
                    "registry": c["payload"]["prior_review"]["delphi_original"]["registry"],
                    "origin": c["payload"].get("origin", "unknown")} for (k, _), c in records.items() if k == "Claim"],
        "evidence": [{"id": e["id"], "version": e["version"], "target": e["payload"]["target"], "kind": e["payload"]["evidence_kind"],
                      "relation": e["payload"].get("relation", "unspecified"), "produced_by": e["payload"].get("produced_by"),
                      "run_id": e["payload"]["provenance"]["run_id"], "artifacts": e["payload"].get("artifacts", []),
                      "link_checks": e["payload"]["provenance"].get("link_checks", []),
                      "replay": e["payload"]["provenance"].get("replay"), "limitations_count": len(e["payload"]["limitations"])}
                     for e in ev_recs],
    }
    files["chain.json"] = json.dumps(chain, indent=2, sort_keys=True) + "\n"
    with open(os.path.join(out_dir, "chain.json"), "w") as fh:
        fh.write(files["chain.json"])
    manifest = {
        "status": chain["status"], "created_at": created_at,
        "records": [{"kind": r["kind"], "id": r["id"], "namespace": r["namespace"], "version": r["version"],
                     "payload_sha256": sha_obj(r["payload"])} for r in allrecs],
        "validated_with": {"frontier_models": "frontier.models.Draft/make_record + store._unlicensed_available_content",
                           "licence_gate_offenders": []},
        "trig_structure": checks, "file_sha256": {n: sha_bytes(t.encode()) for n, t in files.items()},
        "publication": "none. nanopub_draft has no publish function; drafts carry de:signatureStatus UNSIGNED DRAFT.",
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        fh.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"summary": {"records": len(allrecs), **chain["counts"]}, "manifest": manifest, "chain": chain}
