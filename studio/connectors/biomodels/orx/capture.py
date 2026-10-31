"""One-off capture of an OpenResearch (orx) local run of the replay as a Frontier Evidence draft.

Uses the corpus session's read-only adapter (`frontier_adapters`, delphi-frontier branch
work/corpus-adapters) and does not modify it. Not imported by the package or its tests.

  FRONTIER_PATH=<delphi-frontier checkout> PYTHONPATH=<checkout> python3 capture.py \
      --adapter-path <corpus checkout> --store-dir <orx data dir> --run-id <uuid> --out-dir <here>

Writes orx_facts.json (path-scrubbed run facts and the comparison against the committed receipt) and
evidence_draft.json (kind `simulated`, relation supports, produced_by the replay Action, typed artifacts, pinned to the exact
`biomodels-1047-model-behaviour` version) and artifact-manifest.json (digest and locator only; no bytes).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-path", required=True)
    ap.add_argument("--store-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    sys.path.insert(0, a.adapter_path)
    from frontier_adapters import artifacts as art, common, orx_evidence as o
    from connectors.biomodels import frontier_mapping as fm

    facts = o.read_store_run(store_dir=a.store_dir, run_id=a.run_id)
    run_repo = Path(a.store_dir) / "local-runs" / a.run_id / "repo"
    result = run_repo / "out" / "receipt.json"
    facts["result_file"], facts["result_sha256"] = "out/receipt.json", hashlib.sha256(result.read_bytes()).hexdigest()
    facts["outputs"] = [{"path": f"out/{p.name}", "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                        for p in sorted((run_repo / "out").iterdir())]
    facts["orx_version"] = subprocess.run([os.path.expanduser("~/.cargo/bin/orx"), "--version"], capture_output=True, text=True).stdout.strip()

    committed = json.loads((fm.RECEIPT_DIR / "receipt.json").read_text())
    got = {Path(x["path"]).name: x["sha256"] for x in facts["outputs"]}
    comparison = {name: got.get(name) == sha for name, sha in committed["output_sha256"].items()}
    mine = json.loads(result.read_text())
    comparison["receipt_code_sha256_equal"] = mine["run"]["code_sha256"] == committed["run"]["code_sha256"]
    comparison["all_checks_passed_in_orx_run"] = mine["all_checks_passed"] is True
    if not all(comparison.values()):
        raise SystemExit(f"orx run does not reproduce the committed receipt: {comparison}")

    records = {r["id"]: r for r in fm.core_records()}
    claim_b, action = records["biomodels-1047-model-behaviour"], records["biomodels-1047-replay"]
    root = Path(fm.PACKAGE).parents[1]
    repo_label = "kganjam/delphi-frontier"

    def git_entry(role, relpath, note=None):
        """An artifact whose bytes are an immutable blob at the last commit that touched it."""
        commit = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H", "--", relpath], capture_output=True, text=True, check=True).stdout.strip()
        data = art.git_blob(str(root), commit, relpath)
        if data != (root / relpath).read_bytes():
            raise SystemExit(f"{relpath}: working tree differs from {commit}; commit before capturing")
        return art.entry(role, data, path=relpath, repo_label=repo_label, commit=commit, note=note)

    rd = Path(a.store_dir) / "local-runs" / a.run_id
    tar = (Path(a.store_dir) / "source-snapshots" / f"{facts['source_tar_sha256']}.tar").read_bytes()
    rel = f"connectors/biomodels/receipts/{fm.ACCESSION}"
    entries = [
        art.entry("input", (run_repo / "download" / "delta_notch.xml").read_bytes(), path="delta_notch.xml",
                  where="BioModels BIOMD0000001047 revision 3, public download; bytes are NOT redistributed here (rights not established)",
                  note="fetched by the run over the network; size and sha256 verified against BioModels' declared values before use"),
        *[git_entry("output", f"{rel}/{n}") for n in sorted(committed["output_sha256"])],
        git_entry("receipt", f"{rel}/receipt.json", note="the committed receipt this run was compared against"),
        art.entry("receipt", result.read_bytes(), path="out/receipt.json", where=f"orx run {a.run_id} run directory (local store, unpublished)",
                  note="the run's own receipt; differs from the committed one only in run metadata"),
        git_entry("environment", "connectors/biomodels/requirements.txt"),
        art.entry("code_snapshot", tar, path="orx-source-snapshot.tar", where=f"orx source snapshot sha256 {facts['source_tar_sha256']} (local store, unpublished)"),
        art.entry("log", (rd / "log").read_bytes(), path="run.log", where=f"orx run {a.run_id} log (local store, mutable file)"),
    ]
    author = {
        "method": "Local OpenResearch run of `python3 run_replay.py`, which fetches BIOMD0000001047 from BioModels (sha256-verified), runs the "
                  "libroadrunner replay with its controls, and writes out/receipt.json and four output files. A second execution of the same code, not a "
                  "different method: its outputs were compared byte-for-byte with the receipt committed in delphi-frontier.",
        "context": "Simulation of the two-cell Delta-Notch model as encoded in BIOMD0000001047. Non-dimensional; no organism observation; "
                   "no claim about flying fish.",
        "assumptions": ["The SBML file is as published by BioModels revision 3.", "Time horizon 0..60 chosen for this replay.",
                        "Pinned environment: " + ", ".join(f"{k} {v}" for k, v in fm.PINS.items() if k != "pytest") + " (stated by the author; orx does not record it).",
                        "Parameter provenance (measured/fitted/assumed) of the model is unknown; the paper's full text was not read."],
        "limitations": ["Same author wrote the model replay and ran this capture: this is a repeat, not independent replication.",
                        "The independent evaluator in the controls reads the same SBML file.",
                        "The run fetched the SBML over the network; the digest is verified against BioModels' declared hash, but orx does not list that input.",
                        "The raw SBML is referenced by digest and BioModels URL only; it is not redistributed here because rights were not established (terms page unread).",
                        "Outputs were written inside the run's own repo directory, not outside the snapshot.",
                        "Fidelity of the file to the paper was not checked (paper full text not read).",
                        "Does not bear on any flying-fish tissue."],
        "uncertainty": "No uncertainty analysis. Numerical agreement is reported in the receipt (rtol convergence 3e-9; LSODA agreement <= 3.5e-9); parameter uncertainty was not studied.",
        "source_dependence": {"declared": True, "depends_on": ["BioModels BIOMD0000001047 file sha256 " + fm.MODEL_SHA256, "the committed receipt's code"],
                              "independent_of_author": False},
    }
    replay = {"performed": True, "kind": "second execution in an orx sandbox snapshot vs the committed receipt", "outputs_identical": comparison}
    draft = o.to_evidence_draft(facts, target=_ref(claim_b), author=author, kind="simulated", replay=replay, issuer=fm.ISSUER,
                                evidence_id="orx-run-simulated-evidence", namespace=fm.NAMESPACE,
                                relation="supports", produced_by=_ref(action))
    refs = [art.to_artifact_ref(e) for e in entries]
    for r, e in zip(refs, entries):
        if e["role"] == "input":
            r["uri"] = "https://www.biomodels.org/model/download/BIOMD0000001047?filename=delta_notch.xml"   # BioModels' own public URL
    draft["payload"]["artifacts"] = refs
    draft["payload"]["provenance"]["artifacts"] = entries
    draft["payload"]["provenance"]["field_origin"]["artifacts"] = "adapter (typed refs built from the entries above)"
    bad = art.find_abs_paths(draft["payload"])
    if bad:
        raise SystemExit(f"absolute paths at {bad}")
    created = draft["payload"]["created_time"]["value"]
    checked = common.validate_draft(draft, created_at=created)
    if checked["licence_gate_offenders"]:
        raise SystemExit(f"licence gate refused: {checked['licence_gate_offenders']}")
    manifest = art.manifest({"run_id": a.run_id, "backend": "local (not hosted OpenResearch compute, no GPU)", "commit": facts["commit_sha"]}, entries,
                            proposed_site_path=f"/artifacts/orx-run-{a.run_id}/manifest.json")
    out = Path(a.out_dir)
    facts_out = {k: v for k, v in facts.items() if k != "snapshot_files"}
    facts_out.update(snapshot_file_count=len(facts["snapshot_files"]), snapshot_files=facts["snapshot_files"],
                     replay_comparison=comparison, evidence_created_at=created,
                     validated_with="frontier.models.Draft/make_record and frontier.store._unlicensed_available_content (0 offenders)")
    (out / "orx_facts.json").write_text(json.dumps(facts_out, indent=1, sort_keys=True))
    (out / "evidence_draft.json").write_text(json.dumps(draft, indent=1, sort_keys=True))
    (out / "artifact-manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    print("captured", a.run_id, "comparison", comparison, "evidence version", checked["record"]["version"][:12])
    return 0


def _ref(rec):
    return {k: rec[k] for k in ("namespace", "kind", "id", "version")}


if __name__ == "__main__":
    raise SystemExit(main())
