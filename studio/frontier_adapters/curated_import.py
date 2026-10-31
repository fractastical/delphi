"""Genomics records wrapped VERBATIM into a bundle, and an additive Project v2 proposal. Writes files only; nothing is submitted to any store.

    python3 -m frontier_adapters.curated_import --repo . --source-commit 4f4ea25 --genomics-commit 8cf7008 --out frontier_adapters/examples/curated_import

The genomics worker's five records keep their own namespace, issuer and versions (they are not re-minted). The Project v2 record is a NEW version of
`project-flying-fish-mission` whose predecessor is the live version; its first 13 members are the live members, unchanged, and the four design-challenge
annotations stay anchored to the old version, which is retained.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess

from . import engineering_manifest as em
from . import run_bundles as rb

GENOMICS_PATH = "data/genomics/daane2021_supplement_records.json"
PROJECT_ID = "project-flying-fish-mission"
IMPORTED_BETSE = "imports/2026-10-31-multiscale/betse/bundle.betse.frontier-bundle-0.1.json"
NS = "delphi-frontier"


def _git(repo: str, *a: str) -> bytes:
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, check=True).stdout


def genomics_bundle(repo: str, commit: str) -> tuple[dict, dict]:
    """The five records exactly as authored (versions untouched), validated, link-checked, with the supersession scope carried in the report."""
    from frontier.models import Record
    raw = _git(repo, "show", f"{commit}:{GENOMICS_PATH}")
    src = json.loads(raw)
    recs = src["records"]
    for r in recs:
        Record.model_validate(r)
    bundle = em.build_bundle([type("C", (), {"records": recs})()], exporting_node=recs[0]["namespace"])
    kinds = [r["kind"] for r in recs]
    report = {"source": f"{GENOMICS_PATH}@{commit}", "source_sha256": hashlib.sha256(raw).hexdigest(), "records": len(recs),
              "kinds": {k: kinds.count(k) for k in sorted(set(kinds))}, "issuer": src["issuer"], "namespace": src["namespace"], "status_in_source": src["status"],
              "append_only_note": src["append_only_note"], "supersedes_in_status": src["supersedes_in_status"],
              "verbatim": True, "versions": {r["id"]: r["version"] for r in recs},
              "scope": "Versions are the genomics worker's, not recomputed by this adapter. Artifact digests inside the Evidence were not fetched or re-hashed here."}
    return bundle, report


def _ref(r: dict) -> dict:
    return {"namespace": r["namespace"], "kind": r["kind"], "id": r["id"], "version": r["version"]}


def project_v2(repo: str, commit: str, bundles: dict, genomics: list[dict], *, created_at: str | None = None) -> tuple[dict, dict]:
    old = json.loads(_git(repo, "show", f"{commit}:projects/flying-fish.live-repin.json"))["draft"]
    receipt = json.loads(_git(repo, "show", f"{commit}:projects/flying-fish.live-repin-receipt.json"))
    anns = [json.loads(x) for x in _git(repo, "show", f"{commit}:projects/flying-fish.design-challenges.jsonl").decode().splitlines() if x.strip()]
    old_version = receipt["project_ref"]["version"]
    members = old["payload"]["members"]
    assert [m["ref"] for m in members] == receipt["member_refs"], "the draft's 13 pins differ from the live receipt's"
    assert len(anns) == 4 and all(a["payload"]["anchor"]["record"]["version"] == old_version for a in anns), "annotations are not anchored to the live version"
    by_id = {r["id"]: r for b in bundles.values() for r in b["records"]}
    for r in genomics:
        by_id[r["id"]] = r
    plan = [
        ("run-betse-evidence-sim", "subsystem", "BETSE bioelectric tissue", "tissue", "context_for", "Declared: a generic tissue bioelectric simulation (five scenarios); no fin-tissue parameter maps to it and no fin calibration exists.", "Computed context only; the fin is not the simulated tissue."),
        ("run-openfold2-evidence-predicted-structure", "subsystem", "Kcnj13 predicted structure", "macromolecular", "context_for", "Declared: a single-sequence OpenFold2 monomer of zebrafish Kcnj13 with low model-internal confidence; not an experimental structure and no binding or function claim.", "A prediction, kept context-only; the two Kcnj13 sources disagree on sequence."),
        ("run-morpheus-evidence-provider-baseline", "subsystem", "Morpheus generic multicellular example", "cellular", "context_for", "Declared: only the baseline reached t=2.0 in a provider job that FAILED; the local arms were capped earlier. Generic example, not a fish.", "Partial run, reported as partial."),
        ("run-md-evidence-cuda-v2", "subsystem", "Collagen-mimetic MD, 3 x 100 ps CUDA", "macromolecular", "context_for", "Declared: three seeds of a short atomistic trajectory; the cross-scale gate refuses any conversion to tissue modulus.", "Computed, short, no transfer to the fin."),
        ("run-mdc-evidence-cuda-v3", "subsystem", "Collagen-mimetic MD, 3 conditional branches to 1000 ps", "macromolecular", "context_for", "Declared: three conditional continuations of three parents, NOT six independent samples; the predeclared drift diagnostic read False, False, True and is not a stability probability.", "Computed, conditional, descriptive."),
        ("gx-lat4a-is-slc43a2a-supported", "evidence", "lat4a to slc43a2a (Daane 2021 supplement + Ensembl)", "molecular", "informs", "Declared: the mapping is SUPPORTED by the supplement's medaka ids and one Ensembl ortholog; the authors print no zebrafish accession, so it is not author-stated. Newer than, and does not erase, the earlier 'probably' claim.", "Documentary association in zebrafish; transfer to flying fish stays open."),
        ("gx-ev-ensembl-ortholog", "evidence", "Ensembl ortholog check for lat4a", "molecular", "informs", "Declared: one Ensembl zebrafish ortholog (ENSDARG00000036848) for the medaka lat4a gene; control lat4b maps elsewhere.", "Source assessment; residue check inconclusive."),
        ("gx-ev-datas1-lat4a-rows", "evidence", "Daane 2021 Data S1 rows for lat4a/lat4b", "molecular", "informs", "Declared: the authors' own sheet rows in medaka coordinates (F326L, phyloP).", "Only the named rows were read."),
        ("gx-problem-lat4a-residues", "gap", "lat4a residue and accession question", "molecular", "depends_on", "Declared: the open question that remains after the supplement mapping (figures S2D-S2F not read; UniProt naming disagrees).", "Open Problem."),
    ]
    new = []
    for rid, role, sub, scale, rel, appl, why in plan:
        r = by_id[rid]
        new.append({"ref": _ref(r), "role": role, "subsystem": sub, "scale": scale, "relationship": rel, "applicability": appl, "causal_bridge": "none_declared", "rationale": why})
    payload = copy.deepcopy(old["payload"])
    payload["members"] = members + new
    payload["limitations"] = payload["limitations"] + ["Version 2 adds members only. The 13 earlier members, requirements, open questions and scale coverage are unchanged; no whole-fish calibration claim is made and the four authored challenges anchored to the earlier version still exist."]
    created_at = created_at or em._commit_utc(repo, commit)
    c = rb.AssetChain(repo, commit, NS, old["issuer"], created_at, "project_v2")
    draft = {"namespace": NS, "kind": "Project", "id": PROJECT_ID, "issuer": old["issuer"], "source_uri": old["source_uri"], "visibility": "public", "predecessor": old_version, "payload": payload}
    c.add(draft)
    rec = c.records[0]
    report = {"status": "PROPOSED, not submitted. Import the bundles first, then submit this record with Store.submit as its owner (predecessor = the live head).",
              "project": PROJECT_ID, "predecessor_version": old_version, "new_version": rec["version"], "old_members_preserved": 13, "old_members_identical": payload["members"][:13] == members,
              "new_members": len(new), "total_members": len(payload["members"]), "annotations_anchored_to_old_version": len(anns), "annotation_ids": [a["id"] for a in anns],
              "old_version_retained": True, "unchanged": ["requirements", "open_questions", "scale_coverage"], "unpinned_candidates": ["fish3d build", "scales sim", "behavior sim", "lifecycle"],
              "scale_coverage_change_for_owner": "None made. Molecular/macromolecular/cellular/tissue statuses may deserve a revision now that MD, OpenFold2, Morpheus and BETSE exist; that is the Project owner's decision.",
              "new_member_refs": [{**m["ref"], "role": m["role"], "relationship": m["relationship"], "scale": m["scale"]} for m in new]}
    return rec, report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--genomics-commit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--created-at")
    a = ap.parse_args()
    commit = em.resolve(a.repo, a.source_commit) if hasattr(em, "resolve") else _git(a.repo, "rev-parse", a.source_commit).decode().strip()
    gcommit = _git(a.repo, "rev-parse", a.genomics_commit).decode().strip()
    gb, grep = genomics_bundle(a.repo, gcommit)
    chains = {n: rb.ALL_CHAINS[n](a.repo, commit, namespace=NS) for n in ("openfold2", "morpheus", "md", "md_continuation")}
    bundles = {n: em.build_bundle([c], limit=rb.AssetChain.max_records) for n, c in chains.items()}
    imported = json.loads(_git(a.repo, "show", f"origin/main:{IMPORTED_BETSE}"))
    rec, prep = project_v2(a.repo, commit, {**bundles, "betse": imported}, gb["records"], created_at=a.created_at)
    os.makedirs(a.out, exist_ok=True)
    out = {f"bundle.{n}.frontier-bundle-0.1.json": b for n, b in bundles.items()}
    out["bundle.genomics-daane2021.frontier-bundle-0.1.json"] = gb
    out["genomics-report.json"] = grep
    out["project-v2.record.json"] = rec
    out["project-v2.report.json"] = {**prep, "source_commit": commit, "genomics_commit": gcommit}
    for n, o in out.items():
        text = json.dumps(o, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        bad = rb.find_secretish(text)
        if bad:
            raise SystemExit(f"secret-like text in {n}: {bad[:3]}")
        open(os.path.join(a.out, n), "w").write(text)
    print(json.dumps({"out": a.out, "files": sorted(out), "records": {n: len(c.records) for n, c in chains.items()}, "genomics": len(gb["records"]), "project": {k: prep[k] for k in ("new_version", "total_members")}}))


if __name__ == "__main__":
    main()
