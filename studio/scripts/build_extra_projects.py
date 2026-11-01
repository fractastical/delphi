#!/usr/bin/env python3
"""Build the two reuse-study proposals as validated Project drafts, plus one import bundle.

Authoritative text lives in site/content/projects.json (entries with template "reuse-study"); this script derives the Project
payloads from it, so the page and the draft cannot drift. Member refs are copied verbatim from site/data/catalog.json and the
script fails closed if one is absent. No source or evidence ref is invented: the papers behind each study have no record in the
catalog, so they appear as the page's sources and in `source`, not as members.

    python3 scripts/build_extra_projects.py [--created-at ISO8601]

Writes projects/<id>.draft.json for each study and projects/extra-projects.bundle.json (frontier-bundle-0.1, Project records
only, namespace "snapshot"; re-pin with build_flying_fish_project.repin before submitting to a live node). The bundle is
PREPARED ONLY: nothing here imports, reviews or accepts it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from build_flying_fish_project import CATALOG  # noqa: E402
from frontier.models import Draft, digest, make_record  # noqa: E402

PROJECTS = ROOT / "site/content/projects.json"
OUT = ROOT / "projects"
ISSUER = "additional-projects"   # placeholder: the importing operator re-issues under their authenticated actor

# (catalog id, role, subsystem, scale, relationship, applicability, rationale); the catalog is authoritative for every ref.
SHARED = [
    ("doc-model-coupling", "design", "coupling contract", None, "constrains",
     "Declared: defines composable, scenario and refused couplings. Any coupling in this project is labelled scenario until a calibration exists.",
     "The one exact record both studies, and the flying-fish project, intend to reuse."),
    ("doc-SPEC-017-self-validation", "context", "how results may be claimed", None, "constrains",
     "Declared: the self-validation rules that limit what a result from this project may be called.",
     "Pinned so the project states the governing rules for its own claims."),
    ("doc-SPEC-013-adaptive-experimentation", "design", "experiment planning", None, "informs",
     "Declared: how experiments are planned within and across scales. This project proposes endpoints; it plans no run.",
     "Context for the proposed endpoints and instruments."),
]
EXTRA_MEMBERS = {
    "epithelial-repair": [("F002", "gap", "lower-scale evidence for tissue behaviour", "tissue", "depends_on",
                           "Declared: the registered open question about what evidence connects lower-scale predictions to tissue behaviour. Related in shape only; its subject is a different system.",
                           "Links this study to the same registered gap rather than restating it.")],
}
# scale -> (status, note). 'implemented_model' would mean a runnable model for THIS project; none exists for either study.
COVERAGE = {
    "tissue-microcarrier": [("cellular", "source_only", "Two abstracts report cell constructs; no parameter or model is attached."),
                            ("tissue", "unimplemented", "No contractile-tissue model exists in this node."),
                            ("organ", "unimplemented", "The proposed soft-voxel runner is not delivered; no shape or motion result exists.")],
    "epithelial-repair": [("subcellular", "unimplemented", "Protrusion and contractility are inputs of the published models; none is modelled here."),
                          ("cellular", "source_only", "Two abstracts describe cell mechanics and adhesion; no parameter is sourced here."),
                          ("tissue", "source_only", "Two published models of closure are known at abstract level; none has been run here."),
                          ("organ", "unimplemented", "No barrier-geometry readout exists.")],
}


def studies() -> list[dict]:
    return [p for p in json.loads(PROJECTS.read_text())["projects"] if p.get("template") == "reuse-study"]


def build(created_at: str | None = None) -> dict[str, dict]:
    refs = {r["ref"]["id"]: r["ref"] for r in json.loads(CATALOG.read_text())["records"]}
    sha = hashlib.sha256(PROJECTS.read_bytes()).hexdigest()
    out = {}
    for p in studies():
        members = []
        for cid, role, sub, scale, rel, appl, why in SHARED + EXTRA_MEMBERS.get(p["id"], []):
            if cid not in refs:
                raise SystemExit(f"catalog has no record {cid!r}; refusing to invent a ref")
            m = dict(ref=refs[cid], role=role, subsystem=sub, relationship=rel, applicability=appl, causal_bridge="none_declared", rationale=why)
            if scale:
                m["scale"] = scale
            members.append(m)
        questions = [dict(text=q, blocks=[]) for q in p["open_questions"]]
        if p.get("related_problem"):
            rid = p["related_problem"]["id"]
            if rid not in refs or refs[rid]["version"] != p["related_problem"]["version"]:
                raise SystemExit(f"related_problem {rid!r} is not the catalog's exact ref")
            questions[0]["problem"] = refs[rid]
        reqs = [dict(id="req-" + e["id"], kind="validation", text=f"{e['text']} Falsified if: {e['falsifier']}", stage="proposed") for e in p["endpoints"]]
        reqs.append(dict(id="req-non-goals", kind="non_goal", text="This project is not " + "; not ".join(x[0].lower() + x[1:] for x in p["context"]["not_this"]) + ".", stage="declared"))
        payload = {
            "title": p["title"],
            "mission": p["goal"] + " " + p["summary"],
            "source": {"uri": "https://github.com/kganjam/delphi-frontier", "locator": f"site/content/projects.json#{p['id']}", "source_version": sha[:12],
                       "content_sha256": sha, "content_available": False, "access": "public repository file; member refs are snapshot-catalog refs", "license": None},
            "limitations": ["Every member ref is a snapshot-catalog ref (namespace 'snapshot'), not a live-store version: re-pin before submitting.",
                            "The cited papers have no record in the catalog, so they are not members. They appear as sources on the page, read at abstract level only.",
                            "No calibration bridges any pair of scales; every coupling is absent or scenario-level.",
                            "No runner exists for this project; every instrument is proposed. Nothing here is a simulation or an observation."],
            "scale_coverage": [dict(scale=s, status=st, note=n) for s, st, n in COVERAGE[p["id"]]],
            "members": members, "requirements": reqs, "open_questions": questions}
        draft = {"namespace": "snapshot", "kind": "Project", "id": "project-" + p["id"], "issuer": ISSUER,
                 "source_uri": f"urn:frontier:project-draft:{p['id']}", "visibility": "public", "payload": payload}
        Draft.model_validate(draft)
        out[p["id"]] = {"draft": draft, "grounding": {
            "refs_source": "site/data/catalog.json (snapshot namespace), copied verbatim",
            "projects_json_sha256": sha,
            "member_refs_sha256": hashlib.sha256(json.dumps([m["ref"] for m in members], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "members_grounded": len(members), "members_in_catalog": sum(m["ref"]["id"] in refs for m in members),
            "issuer_note": "issuer is a placeholder; the importing operator re-issues under their authenticated actor",
            "status": "PREPARED ONLY; not imported, reviewed or accepted",
            "not_established": ["that any proposed endpoint holds", "that any tool's result transfers to this biology", "that these refs exist as versions in a live node"]}}
    return out


def bundle(drafts: dict[str, dict], created_at: str) -> dict:
    records = [make_record(Draft.model_validate(d["draft"]), created_at) for d in drafts.values()]
    body = {"schema_version": "frontier-bundle-0.1", "exporting_node": "snapshot", "records": records, "review_claims": [], "policy_version": "prepared-not-reviewed",
            "trust": "Digest proves integrity only; reviews require receiving-node policy."}
    return {**body, "bundle_sha256": digest(body)}


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--created-at", required=True, help="ISO 8601 UTC time recorded on the bundle's records; pass it from `date -u`")
    a = ap.parse_args()
    d = build()
    for k, v in d.items():
        dump(OUT / f"{k}.draft.json", v)
    dump(OUT / "extra-projects.bundle.json", bundle(d, a.created_at))
    print("wrote", [f"{k}.draft.json" for k in d], "extra-projects.bundle.json")
