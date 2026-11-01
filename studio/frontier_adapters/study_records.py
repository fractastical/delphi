"""Prepare a finite record bundle for the reusable oxygen rule and the two secondary studies.

Reads exact bytes from pinned Git commits (never the working tree), hashes them, and builds typed records with the
existing `frontier.models` contracts. It makes no network or model call and writes nothing to a store. Imports stay with
root. Three things are kept apart on purpose:

* a Claim about a conditional steady-diffusion formula, and the Evidence (Lean compilation, numerical checks, source
  reading) that bears on it. D, a and C0 are unknown; nothing here predicts viability of any tissue;
* generic voxel numerical mechanics as simulated Evidence at its actual toy scale, with the frozen E miss and the
  unresolved spatial discrepancy stated, never a living microcarrier;
* two recorded (not actionable) Problems, one per secondary project, each an unresolved bridge named in the sources.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

from frontier.models import Draft, Member, Project, make_record

from .import_cli import ref_of

NAMESPACE, ISSUER = "delphi-frontier", "codex-03"
REPO_URL = "https://github.com/kganjam/delphi-frontier/blob/"
OXY, OXY_DIR = "3b9d215", "artifacts/oxygen-diffusion-rule/"
VOX_SUMMARY, VOX_AUDIT = "a896380", "130b3f4"
EPI, EPI_REVIEW = "66f2b95", "6298621"
LIVE_PROJECTS = "projects/reuse-studies/live-projects.json"


class Pinned:
    """Exact bytes at one commit; the digest and size are computed here, not copied from a summary."""

    def __init__(self, root, commit):
        self.root, self.commit = Path(root), commit

    def read(self, path):
        out = subprocess.run(["git", "-C", str(self.root), "show", f"{self.commit}:{path}"], capture_output=True, check=True, timeout=30)
        return out.stdout

    def source(self, path, locator, access):
        data = self.read(path)
        return {"uri": f"{REPO_URL}{self.commit}/{path}", "locator": locator, "source_version": self.commit,
                "content_sha256": sha256(data).hexdigest(), "content_available": False, "access": access, "license": None}

    def artifact(self, path, role, media, title=None):
        data = self.read(path)
        digest = sha256(data).hexdigest()
        return {"title": title or Path(path).name, "uri": "urn:sha256:" + digest, "sha256": digest, "byte_size": len(data),
                "media_type": media, "role": role, "availability": "referenced", "license": None}


def _rec(kind, ident, payload, created_at):
    draft = Draft(namespace=NAMESPACE, issuer=ISSUER, kind=kind, id=ident, source_uri="urn:frontier:study-record:" + ident,
                  visibility="public", payload=payload)
    return make_record(draft, created_at=created_at)


def _evidence(claim, kind, relation, source, method, context, assumptions, provenance, group, uncertainty, limitations, artifacts, created_at):
    return {"target": ref_of(claim), "evidence_kind": kind, "source": source,
            "created_time": {"value": created_at, "basis": "witnessed"}, "retrieved_time": {"value": created_at, "basis": "witnessed"},
            "method": method, "context": context, "assumptions": assumptions, "provenance": provenance,
            "source_dependence": {"group": group, "note": "records sharing this group read one receipt; they are not independent checks"},
            "uncertainty": uncertainty, "limitations": limitations, "relation": relation, "produced_by": None, "artifacts": artifacts}


OXYGEN_NOT_ESTABLISHED = ["D, a and C0 for any tissue, cell type or material: all unknown", "cell viability, survival or any oxygen threshold",
                          "actual oxygen supply to a microcarrier or repair patch", "transfer from tumour spheroids or any other context"]

GEOMETRIES = {
    "sphere": {"formula": "C_center = C0 - a R^2 / (6 D); non-negative iff a R^2 <= 6 D C0",
               "setting": "spherical domain, outer boundary C(R) = C0, symmetry at the centre",
               "origin": "derived", "attribution": "Sphere relation follows Grimes et al. 2014 Eq. 2.2 and Eq. 2.6 (read from the published equation images); the centre profile is the repository's application of that equation.",
               "theorem": "sphere_center_oxygen_bound"},
    "slab": {"formula": "C_center = C0 - a L^2 / (2 D); non-negative iff a L^2 <= 2 D C0",
             "setting": "one half of a symmetric slab: no-flux centre at x=0 and supplied face C(L) = C0 (total thickness 2L)",
             "origin": "derived", "attribution": "No slab expression is attributed to Grimes et al.; the coefficient 2 is derived here from D C'' = a with a no-flux centre.",
             "theorem": "slab_center_oxygen_bound"},
}


def oxygen_records(root, created_at):
    pin = Pinned(root, OXY)
    manifest = json.loads(pin.read(OXY_DIR + "artifact-manifest.json"))
    manifest_sha = {f["path"]: f["sha256"] for f in manifest["files"]}
    rule_path, lean_path, mutant_path = OXY_DIR + "rule-contract.json", "engineering/formalize/lean/OxygenDiffusionBound.lean", "engineering/formalize/lean/OxygenDiffusionBound_negative_corrupt_law.lean"
    receipt_path, numeric_path, prov_path = OXY_DIR + "lean-receipt.json", OXY_DIR + "numerical-checks.json", OXY_DIR + "source-provenance.json"
    receipt, numeric, prov = (json.loads(pin.read(p)) for p in (receipt_path, numeric_path, prov_path))
    records, bindings = [], []
    for path in (rule_path, lean_path, mutant_path, receipt_path, numeric_path, prov_path):
        if path in manifest_sha:  # the manifest lists every file except itself
            bindings.append({"path": path, "commit": OXY, "manifest_sha256": manifest_sha[path], "computed_sha256": sha256(pin.read(path)).hexdigest()})
    for name, g in GEOMETRIES.items():
        claim = _rec("Claim", f"claim:oxygen-{name}-center-bound", {
            "title": f"Conditional steady diffusion bound, {name}",
            "statement": (f"Under steady diffusion with spatially constant positive consumption a > 0, constant isotropic D > 0 and boundary content C0 >= 0, "
                          f"in a {g['setting']}: {g['formula']}. Ccenter < 0 marks the constant-consumption model's domain limit, not a physical negative concentration."),
            "context": "Ideal-geometry algebraic rule with unknown parameters. It carries no biological context: D, a and C0 are context-specific unknowns.",
            "assumptions": ["steady state", "diffusion only; no perfusion or advection", "constant positive consumption a > 0 (the Lean equivalence premise 0 < a) and constant diffusion coefficient", "ideal geometry with the stated boundary conditions"],
            "limitations": ["Not established: " + "; ".join(OXYGEN_NOT_ESTABLISHED), "The formally supported claim is restricted to a > 0; a zero-consumption extension is not claimed and is not covered by the Lean statements", g["attribution"]],
            "source": pin.source(rule_path, f"/geometries/{name}", "Repository rule contract at the pinned commit; parameters unknown"),
            "source_record_version": manifest_sha.get(rule_path), "origin": g["origin"],
            "prior_review": {"status": "none; formal check and numerical check are Evidence, not review"}}, created_at)
        lean = _evidence(claim, "formal", "supports", pin.source(receipt_path, f"/positive and /corrupted_coefficients ({g['theorem']})", "Lean receipt at the pinned commit"),
                         "Lean 4 compiled the theorem and its two corrupted-coefficient twins; the twins failed with 4 diagnostics, as expected.",
                         "Algebraic implication only, for a > 0, after the source-to-equation interpretation.",
                         ["Lean checks the implication under the stated premises", "translation from source to equation is a separate, unchecked step"],
                         {"lean_version": receipt["lean_version"], "mathlib_revision": receipt["mathlib"]["revision"], "corrupted_failure_diagnostics": receipt["corrupted_coefficients"]["actual_failure_diagnostics"],
                          "theorem": g["theorem"], "execution_performed": False,
                          "producer_exception": "Receipt copied from the owner's pinned run; this adapter reran nothing"},
                         "lean-receipt:" + sha256(pin.read(receipt_path)).hexdigest(),
                         "Exact over the stated reals; no statistical uncertainty. The premises are idealisations.",
                         receipt["limitations"] + ["Compilation is not tissue validation and says nothing about any parameter value"],
                         [pin.artifact(lean_path, "code", "text/plain"), pin.artifact(mutant_path, "code", "text/plain", "negative control (corrupted law)"),
                          pin.artifact(receipt_path, "certificate", "application/json")], created_at)
        num = _evidence(claim, "simulated", "supports", pin.source(numeric_path, f"/checks ({g['theorem']} twins)", "Numerical-check receipt at the pinned commit"),
                        f"{numeric['check_count']} deterministic checks of the repository's profile helpers against the stated centre equation and limit.",
                        "Computational implementation check of a closed form on a fixture; not a simulation of tissue.",
                        ["Fixture values are arbitrary test numbers, not biological parameters"],
                        {"check_count": numeric["check_count"], "statuses": sorted({c["status"] for c in numeric["checks"]}), "execution_performed": False,
                         "producer_exception": "Receipt copied from the owner's pinned run; this adapter reran nothing"},
                        "numerical-checks:" + sha256(pin.read(numeric_path)).hexdigest(),
                        "Tolerance 1e-12 on rational fixtures; says nothing about D, a or C0.",
                        ["Agreement of an implementation with its own equation is not empirical validation", "Both geometries share one receipt"],
                        [pin.artifact(numeric_path, "output", "application/json")], created_at)
        records += [claim, _rec("Evidence", f"evidence:oxygen-{name}-lean", lean, created_at), _rec("Evidence", f"evidence:oxygen-{name}-numerical", num, created_at)]
    sphere_claim = records[0]
    src = _evidence(sphere_claim, "source_assessment", "context_only", pin.source(prov_path, "/primary_source and /equations_read_from_published_equation_images", "Provenance receipt at the pinned commit; no article bytes are carried"),
                    "Records which equations of the primary source were read, with image and full-text digests, and the license as stated.",
                    "Grimes et al. 2014 (PMC3899881) supplies the spherical Laplacian and diffusion-limit expression; it is a spheroid study.",
                    ["Equation images were read as published figures", "No slab expression is attributed to the source"],
                    {"source_receipt": OXY_DIR + "source-provenance.json", "citation": prov["primary_source"]["citation"], "doi": prov["primary_source"]["doi"],
                     "execution_performed": False, "producer_exception": "Documentary source assessment; no executed Action is invented"},
                    "grimes2014-pmc3899881", "Spheroid parameters in the source are not transferred.",
                    ["No full article text is carried or mirrored; only URL, digests and locators", "The source's spheroid consumption and diffusion values are context, not parameters here"],
                    [pin.artifact(prov_path, "input", "application/json")], created_at)
    records.append(_rec("Evidence", "evidence:oxygen-source-assessment", src, created_at))
    return records, bindings


def voxel_records(root, created_at):
    summary_pin, audit_pin = Pinned(root, VOX_SUMMARY), Pinned(root, VOX_AUDIT)
    spath, apath, rpath, dpath = "artifacts/voxel-actuation/summary.json", "artifacts/audits/xenobot/corrected-1be6dcb/audit.json", "artifacts/audits/xenobot/replay-receipt.json", "docs/audits/voxelyze-review-2026-10-31.md"
    summary = json.loads(summary_pin.read(spath))
    e_ctl, g_sp = summary["controls"]["E_zero_gravity"], summary["arm_G_spatial"]
    assert e_ctl["met"] is False and g_sp["G-coarse"]["body_lengths"] != g_sp["G-fine"]["body_lengths"]
    claim = _rec("Claim", "claim:voxelyze-toy-numerical-mechanics", {
        "title": "Generic Voxelyze soft-voxel numerics at toy scale",
        "statement": ("In the saved CPU runs of Voxelyze 4287e365 on a 45 g generic soft-voxel ground-contact benchmark with prescribed thermal-expansion actuation, "
                      "displacement depends on the prescribed pattern. The frozen zero-gravity control E missed its bound, and displacement differs between coarse and fine voxel grids without spatial convergence."),
        "context": "Numerical mechanics of a toy model. The actuation is prescribed thermal expansion, not measured cellular contractility; the scale is a 45 g centimetre-scale benchmark, not a Xenopus-scale construct, tissue or microcarrier.",
        "assumptions": ["generic example material values", "prescribed thermal-expansion drive stands in for an actuation parameter"],
        "limitations": ["Control E failed its frozen bound: 0.017479 center-span units against 0.01", "Spatial discrepancy is unresolved: coarse 0.15318 BL against fine 0.01878 BL in arm G",
                        "No tissue calibration, living microcarrier or biological transfer is established", "No force or energy history was saved, so no efficiency or mechanism fraction exists"],
        "source": summary_pin.source(spath, "/controls/E_zero_gravity and /arm_G_spatial", "Repository summary at the pinned commit"),
        "origin": "derived", "prior_review": {"independent_review": "docs/audits/voxelyze-review-2026-10-31.md at 130b3f4 reports no numerical-data blocker and required scale qualifications"}}, created_at)
    sim = _evidence(claim, "simulated", "qualifies", summary_pin.source(spath, "/controls/E_zero_gravity, /arm_G_spatial, /arm_A_verdict", "Repository summary at the pinned commit"),
                    "Voxelyze 0.9 CPU runs frozen at 7b9bd5d, deterministic with no RNG, so there are no stochastic replicates.",
                    "Generic 45 g toy ground-contact benchmark; not a tissue or microcarrier.",
                    ["generic example material values", "prescribed thermal expansion, not measured contractility"],
                    {"engine_commit": summary["engine"]["commit"], "protocol_frozen_commit": summary["protocol_frozen_commit"], "determinism": summary["determinism"],
                     "control_E": e_ctl, "arm_G": g_sp, "arm_A_observed": summary["arm_A_verdict"]["observed"], "execution_performed": False,
                     "producer_exception": "Outputs copied from the owner's pinned run; this adapter reran nothing"},
                    "voxel-summary:" + sha256(summary_pin.read(spath)).hexdigest(),
                    "Deterministic code with no replicates; spatial discrepancy between grids is unresolved and no uncertainty interval exists.",
                    ["E missed its frozen bound and is retained as a miss", "Spatial nonconvergence is retained, not resolved", "Normalised comparisons use changing denominators; the raw SI difference is 15.5739% relative to coarse for the post-hoc travelling pattern, which is not a convergence test"],
                    [summary_pin.artifact(spath, "output", "application/json"), audit_pin.artifact(apath, "output", "application/json", "corrected audit output")], created_at)
    replay = _evidence(claim, "simulated", "reproduces", audit_pin.source(rpath, "/runs", "Independent replay receipt at the pinned commit"),
                       "Independent reviewer rebuilt upstream Voxelyze and reran seven declared records; all matched the originals exactly.",
                       "Replay of the same numerical benchmark; the same model, so a shared-model check rather than independent biological replication.",
                       ["same engine and same inputs"],
                       {"replay_receipt": rpath, "review_doc": dpath, "records_reran": ["P1", "P2", "M1", "M2", "M3", "D", "E"], "E_still_fails_frozen_bound": True, "execution_performed": False,
                        "producer_exception": "Receipt copied from the reviewer's pinned run; this adapter reran nothing"},
                    "voxel-replay:" + sha256(audit_pin.read(rpath)).hexdigest(),
                    "Replay is exact; it cannot show that the model is right.",
                    ["Replay does not address spatial convergence", "E remains a failed control after replay"],
                    [audit_pin.artifact(rpath, "log", "application/json"), audit_pin.artifact(dpath, "output", "text/markdown")], created_at)
    return [claim, _rec("Evidence", "evidence:voxelyze-summary", sim, created_at), _rec("Evidence", "evidence:voxelyze-replay", replay, created_at)]


def live_project_refs(root):
    data = json.loads((Path(root) / LIVE_PROJECTS).read_text())
    refs = {p["project"]: p for p in data["projects"]}
    return {k: (v["target"], v["record"]["payload"]) for k, v in refs.items()}


def problem_records(root, created_at, claim_ref, voxel_evidence_ref):
    projects = live_project_refs(root)
    f002 = next(q["problem"] for q in projects["epithelial-repair"][1]["open_questions"] if q.get("problem"))
    audit_pin, epi_pin = Pinned(root, VOX_AUDIT), Pinned(root, EPI)
    tissue = _rec("Problem", "problem:tissue-contractility-to-actuation", {
        "title": "Measured cell contractility to prescribed voxel actuation",
        "known_state": "The voxel model prescribes thermal expansion on a 45 g toy; the review states that this is not measured cellular contractility. No construct measurement exists in this repository and no calibration links the model's actuation parameter to any cell or tissue.",
        "question": "What measured contractility of one named cell construct would bound the prescribed actuation parameter of a generic voxel model, and with what stated context?",
        "problem_kind": "project_gap", "novelty_status": "not assessed", "data_access": "No construct measurement is available here.",
        "completeness": "recorded", "required_capabilities": ["measurement of construct contractility or strain against force", "documented mapping to the model's actuation parameter"],
        "downstream_uses": ["project-tissue-microcarrier actuation-to-motion bridge"], "dependencies": [claim_ref, voxel_evidence_ref],
        "source": audit_pin.source("docs/audits/voxelyze-review-2026-10-31.md", "paragraph beginning 'Material values come from a generic example'", "Independent review at the pinned commit"),
        "approach": "measurement", "scales": ["cellular", "tissue"], "context_tags": ["voxel-actuation", "unresolved-bridge"]}, created_at)
    epi = _rec("Problem", "problem:epithelial-gap-closure-to-physical-time", {
        "title": "Observed gap closure to calibrated physical time and mechanism",
        "known_state": ("The Cellular Potts mechanism testbed runs in model units: the card states none of its parameters is a force, a stress or a time in minutes, and nothing is calibrated to a cell line or measured tissue. "
                        "In one both-drives-off control at k=4 the gap shrank by 551 of 2500 nodes (22.04%); that is a condition-specific run, consistent with passive volume relaxation but with no mechanism contribution isolated, and it is not a universal subtraction. "
                        "Final strict tally at 66f2b95 with independent review 6298621: 7 pass, 3 fail, G6 descriptive, G1b incomplete, G8 unevaluable; physical-time calibration remains open."),
        "question": "What measurement of gap closure in one named cell line would calibrate the model's time unit and distinguish the contributing mechanisms?",
        "problem_kind": "project_gap", "novelty_status": "not assessed", "data_access": "No cell-line closure measurement is available here.",
        "completeness": "recorded", "required_capabilities": ["time-resolved gap closure measurement in a named cell line", "a stated mapping from model time units to physical time"],
        "downstream_uses": ["project-epithelial-repair closure-to-time bridge"], "dependencies": [f002],
        "source": epi_pin.source("docs/epithelial-repair-card.md", "section 2 (scale mapping), section 4 (passive control) and the strict tally", "Final corrected card at the pinned commit; independent review at 6298621 (docs/audits/epithelial-repair-review-2026-10-31.md)"),
        "approach": "measurement", "scales": ["cellular", "tissue"], "context_tags": ["epithelial-repair", "unresolved-bridge", "independently-reviewed"]}, created_at)
    return tissue, epi


def attachments(root, tissue, epi, vox_claim, vox_sim):
    """Proposed Project members; the Projects themselves are not edited. Each is validated against Member/Project."""
    projects = live_project_refs(root)
    out = []
    plan = {"tissue-microcarrier": [
                (ref_of(vox_claim), "design", "context_for", "Voxel numerical mechanics reused as a generic tool only; not a tissue or microcarrier result."),
                (ref_of(vox_sim), "evidence", "context_for", "Simulated toy-scale evidence with a missed control E and unresolved spatial convergence."),
                (ref_of(tissue), "gap", "depends_on", "Open bridge; recorded, not actionable, no priority or probability.")],
            "epithelial-repair": [(ref_of(epi), "gap", "depends_on", "Open bridge; recorded, not actionable; independent card review pending.")]}
    for name, items in plan.items():
        target, payload = projects[name]
        members = [Member(ref=r, role=role, subsystem="study-records", scale="cellular" if role == "gap" else "tissue", relationship=rel,
                          applicability="Declared scope only; no causal bridge is inferred.", causal_bridge="none_declared", rationale=why).model_dump()
                   for r, role, rel, why in items]
        proposed_payload = {**payload, "members": payload["members"] + members}
        Project.model_validate(proposed_payload)
        row = {"project": target, "proposed_members": members, "payload_validates_if_appended": True,
               "note": "Attachment proposal for root review; the Project record is not modified here."}
        if name == "tissue-microcarrier":
            row["proposed_open_question_link"] = {"question_index": 1, "text": payload["open_questions"][1]["text"], "problem": ref_of(tissue)}
        out.append(row)
    return out


def build(root, *, created_at):
    root = Path(root)
    oxygen, bindings = oxygen_records(root, created_at)
    voxel = voxel_records(root, created_at)
    tissue, epi = problem_records(root, created_at, ref_of(voxel[0]), ref_of(voxel[1]))
    records = [*oxygen, *voxel, tissue, epi]
    return records, attachments(root, tissue, epi, voxel[0], voxel[1]), bindings


def validate(root, records, bindings):
    """Focused validity and source-binding checks; returns a list of problems (empty means consistent, nothing more)."""
    probs = []
    by_ref = {(r["kind"], r["id"], r["version"]) for r in records}
    for b in bindings:
        if b["manifest_sha256"] != b["computed_sha256"]:
            probs.append(f"binding mismatch {b['path']}")
    for r in records:
        Draft(namespace=r["namespace"], kind=r["kind"], id=r["id"], issuer=r["issuer"], source_uri=r["source_uri"], payload=r["payload"])
        p = r["payload"]
        for art in p.get("artifacts", []):
            if art["uri"] != "urn:sha256:" + art["sha256"]:
                probs.append(f"{r['id']}: artifact uri/digest mismatch")
        if r["kind"] == "Problem":
            if p["completeness"] != "recorded" or any(p.get(k) for k in ("acceptance_criteria", "falsifiers", "next_action", "cost_stop_bounds")):
                probs.append(f"{r['id']}: a recorded Problem must not carry invented acceptance, falsifiers, action or bounds")
            if any(k in p for k in ("priority", "probability")):
                probs.append(f"{r['id']}: priority or probability field")
            for d in p["dependencies"]:
                if (d["kind"], d["id"], d["version"]) not in by_ref and d["id"] != "F002":
                    probs.append(f"{r['id']}: dependency {d['id']} not in bundle or live project")
        if r["kind"] == "Claim" and r["id"].startswith("claim:voxelyze"):
            text = p["statement"] + " ".join(p["limitations"])
            if "missed" not in text or "without spatial convergence" not in text or "45 g" not in text:
                probs.append(f"{r['id']}: E miss, nonconvergence and toy scale must be stated")
        if r["kind"] == "Claim" and r["id"].startswith("claim:oxygen"):
            if "unknown" not in (p["context"] + " ".join(p["limitations"])):
                probs.append(f"{r['id']}: unknown parameters not stated")
            if "a > 0" not in p["statement"] or "non-negative consumption" in p["statement"] or "a >= 0" in p["statement"]:
                probs.append(f"{r['id']}: formally supported claim must be restricted to a > 0")
        if r["id"] == "problem:epithelial-gap-closure-to-physical-time":
            if p["source"]["source_version"] != EPI or "22.04%" not in p["known_state"] or "not a universal subtraction" not in p["known_state"] or "arithmetic floor" in p["known_state"]:
                probs.append(f"{r['id']}: stale epithelial source or floor attribution")
        if r["kind"] == "Evidence" and p["target"]["kind"] == "Claim" and (p["target"]["kind"], p["target"]["id"], p["target"]["version"]) not in by_ref:
            probs.append(f"{r['id']}: target not in bundle")
        if r["kind"] == "Evidence" and r["id"].startswith("evidence:voxelyze") and p["evidence_kind"] != "simulated":
            probs.append(f"{r['id']}: voxel numerics must be simulated evidence")
    return probs


def main(argv=None):
    import argparse
    from datetime import datetime, timezone
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="projects/reuse-studies/study-records")
    p.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    a = p.parse_args(argv)
    records, att, bindings = build(a.root, created_at=a.created_at)
    problems = validate(a.root, records, bindings)
    if problems:
        raise SystemExit("validation failed: " + "; ".join(problems))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "records.json").write_text(json.dumps(records, indent=1, sort_keys=True) + "\n")
    (out / "project-attachments.json").write_text(json.dumps(att, indent=1, sort_keys=True) + "\n")
    (out / "source-bindings.json").write_text(json.dumps(bindings, indent=1, sort_keys=True) + "\n")
    (out / "validity.json").write_text(json.dumps({"schema": "frontier.study-records.validity/1", "problems": problems, "records": len(records),
                                                    "scope": "schema validity, pinned-byte binding and scope statements; not scientific acceptance"}, indent=1) + "\n")
    print(json.dumps({"records": len(records), "attachments": len(att), "source_bindings": len(bindings)}))


if __name__ == "__main__":
    main()
