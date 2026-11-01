"""End to end: Delphi claims -> OpenResearch run f81c0b68 (NCA analysis, LOCAL backend) -> hashed artifacts.

Builds PROPOSED records only (nothing is submitted, accepted or published):
  Claim turing-ddi, Claim turing-wavelength  (live from Delphi, original ids/nanopub URIs/registry kept)
  Evidence (simulated) for each, pinned to the exact Claim version, produced by the real orx run f81c0b68
  chain.json  claim -> evidence -> artifact graph with every link check and the replay result
  artifact-manifest.json  the manifest root asked for (digest + locator, no bytes, no absolute paths)

Environment (read, never embedded):  ORX_STORE   the producing host's OpenResearch data dir
                                     NCA_REPO    a git checkout of kganjam/delphi-evolve containing commit COMMIT
Run (bounded):  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 \
  env PYTHONPATH=. ORX_STORE=... NCA_REPO=... python3 -m frontier_adapters.examples.make_nca_chain
"""
import json
import os
import re
import subprocess
import sys

from frontier_adapters import artifacts as art, bundle, delphi_claim as dc, orx_evidence as oe, orx_replay
from frontier_adapters.common import iso_utc, sha_bytes
from frontier_adapters.delphi_mcp import Delphi

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "nca_chain")
REPO_LABEL = "kganjam/delphi-evolve"
COMMIT = "1067cdb7b49dcfd77102d6d9a3242cfe8cd20268"       # work/rethink-nca, verified on the remote
PREREG_COMMIT = "cb27cf24521b7eb77f784bc266d2f3f584f049ff"
RUN_ID = "f81c0b68-ad0c-4ebe-b809-96977ad1c0f3"
RES = "scopedesk/oracles/results/nonlinear_sweep"
PREREG = "scopedesk/oracles/nonlinear_sweep/PREREG.md"
ANALYZER = "scopedesk/oracles/nonlinear_sweep/analyze.py"


def section(md: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    return m.group(1) if m else ""


def bullets(md: str, heading: str, startswith: str | None = None) -> list[str]:
    out = [l[2:].strip() for l in section(md, heading).split("\n") if l.startswith(("* ", "- "))]
    return [b for b in out if not startswith or b.startswith(startswith)]


def table_rows(md: str, starts: tuple) -> list[str]:
    return [l.strip() for l in md.split("\n") if l.startswith("| ") and l[2:].startswith(starts)]


def clean(s: str) -> str:
    return art.scrub_paths(s)[0]


def main():
    repo, store = os.environ["NCA_REPO"], os.environ["ORX_STORE"]
    blob = lambda p: art.git_blob(repo, COMMIT, p)
    rows, status, report = blob(f"{RES}/rows.jsonl"), blob(f"{RES}/run_status.json"), blob(f"{RES}/report.json")
    report_md, receipt_b = blob(f"{RES}/REPORT.md"), blob(f"{RES}/orx_receipt.json")
    prereg_b, analyzer_b = art.git_blob(repo, PREREG_COMMIT, PREREG), blob(ANALYZER)
    rep, receipt = json.loads(report), json.loads(receipt_b)
    md, pre = report_md.decode(), prereg_b.decode()

    facts = oe.read_store_run(store_dir=store, run_id=RUN_ID)
    facts["orx_version"] = receipt["tool"].split(",")[0].replace("orx ", "").split(" ")[0] + " (per the producer's receipt; not stored in the run record)"
    tar = open(os.path.join(store, "source-snapshots", facts["source_tar_sha256"] + ".tar"), "rb").read()

    # ---- artifact pointers (digest + locator; no bytes) ----
    A = [
        art.entry("input", rows, path=f"{RES}/rows.jsonl", repo_label=REPO_LABEL, commit=COMMIT,
                  note="read by the run from a directory outside its snapshot; produced by the 2.8 h sweep, which has no orx record"),
        art.entry("input", status, path=f"{RES}/run_status.json", repo_label=REPO_LABEL, commit=COMMIT,
                  note="a SECOND input, also outside the snapshot; omitting it changes the output (measured)"),
        art.entry("output", report, path=f"{RES}/report.json", repo_label=REPO_LABEL, commit=COMMIT,
                  note="written by the run into the input directory, not into the run directory"),
        art.entry("report", report_md, path=f"{RES}/REPORT.md", repo_label=REPO_LABEL, commit=COMMIT),
        art.entry("protocol", prereg_b, path=PREREG, repo_label=REPO_LABEL, commit=PREREG_COMMIT,
                  note="committed before any scored row (author-asserted commit time)"),
        art.entry("receipt", receipt_b, path=f"{RES}/orx_receipt.json", repo_label=REPO_LABEL, commit=COMMIT,
                  note="the producer's own account of the run"),
        art.entry("code", analyzer_b, path=ANALYZER, repo_label=REPO_LABEL, commit=COMMIT),
        {"role": "code_snapshot", "path": "source.tar", "sha256": facts["source_tar_sha256"], "git_blob": None,
         "bytes": facts["source_tar_bytes"], "content_available": False, "license": None,
         "locator": f"orx-run:{RUN_ID}/source-snapshot", "git_commit": facts["commit_sha"],
         "note": "git archive of the orx experiment commit; located in the producing host's store only"},
        {"role": "log", "path": "log", "sha256": facts["log_sha256"], "git_blob": None, "bytes": facts["log_bytes"],
         "content_available": False, "license": None, "locator": f"orx-run:{RUN_ID}/log",
         "note": "run stdout; mutable local file; contains the ORX_RESULT_JSON line used in the link checks"},
    ]
    sha = {a["role"] + ":" + a["path"].split("/")[-1]: a["sha256"] for a in A}

    # ---- link checks (each computed; each has a failing counter-test) ----
    lrj = facts["log_result_json"] or {}
    snap_an = facts["snapshot_files"].get("analyze_sweep.py")
    anc = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", PREREG_COMMIT, COMMIT], capture_output=True).returncode == 0
    checks = [
        {"name": "logged_input_sha256_equals_input_artifact", "passed": lrj.get("rows_sha256") == sha["input:rows.jsonl"],
         "a": lrj.get("rows_sha256"), "b": sha["input:rows.jsonl"]},
        {"name": "report_embeds_the_same_input_sha256", "passed": rep["rows_sha256"] == sha["input:rows.jsonl"],
         "a": rep["rows_sha256"], "b": sha["input:rows.jsonl"]},
        {"name": "logged_overall_equals_report_overall", "passed": lrj.get("overall") == rep["overall"]},
        {"name": "snapshot_analyzer_equals_committed_analyzer", "passed": snap_an == sha["code:analyze.py"], "a": snap_an, "b": sha["code:analyze.py"]},
        {"name": "receipt_agrees_with_store_record", "passed": receipt["run_id"] == facts["run_id"] and receipt["orx_experiment_commit"] == facts["commit_sha"]
         and receipt["rows_sha256"] == sha["input:rows.jsonl"] and receipt["status"] == facts["status"]},
        {"name": "protocol_commit_is_ancestor_of_results_commit", "passed": anc,
         "note": "git ancestry; commit times are author-asserted, not witnessed"},
    ]

    # ---- replay: the analysis only, on immutable blobs, clean env, declared deviation, mutation control ----
    mut_rows = rows.decode().split("\n")
    for i, l in enumerate(mut_rows):
        if l and (r := json.loads(l)).get("linear") == "out_of_scope" and r.get("category") == "no_pattern":
            r["category"] = "pattern"; mut_rows[i] = json.dumps(r); break
    kw = dict(tar_bytes=tar, command=facts["command"], interpreter=sys.executable, config_key="rows_dir",
              output_name="report.json", expected_output_sha256=sha["output:report.json"],
              expected_stdout_sha256=facts["log_sha256"], trust_code=True,
              env_extra={"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"})
    kw["command"] = "OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -I run_experiment.py"   # recorded command with the absolute interpreter token neutralised
    inputs = {"rows.jsonl": rows, "run_status.json": status}
    full = orx_replay.replay_external(inputs=inputs, **kw)
    one_missing = orx_replay.replay_external(inputs={"rows.jsonl": rows}, **kw)
    control = orx_replay.replay_external(inputs=inputs, mutate_input=("rows.jsonl", "\n".join(mut_rows).encode()), **kw)
    replay = {"performed": True, "scope": "the ANALYSIS step only; the 2,520-cell sweep was not re-run",
              "results": {"full_inputs": {"matches_recorded": bool(full["output_matches_expected"]), **full},
                          }, "mutation_control": control["output_matches_expected"] is False,
              "control_results": {"one_row_changed": control}, "missing_input_probe": one_missing}
    checks.append({"name": "replay_output_byte_identical_to_recorded_report", "passed": bool(full["output_matches_expected"]),
                   "a": full["output_sha256"], "b": sha["output:report.json"]})
    checks.append({"name": "replay_stdout_byte_identical_to_orx_log", "passed": bool(full["stdout_matches_recorded_log"])})
    checks.append({"name": "mutation_control_changes_the_output", "passed": control["output_matches_expected"] is False})
    checks.append({"name": "missing_run_status_input_changes_the_output_silently", "passed": one_missing["output_matches_expected"] is False and one_missing["exit"] == 0,
                   "note": "a finding about the orx record (it does not list inputs), not a pass/fail of the evidence"})

    # ---- the author's own words, verbatim from the committed REPORT/PREREG ----
    cautions = [clean(b) for b in bullets(md, "Cautions")]
    ensemble = [clean(b) for b in bullets(pre, "Ensemble (named; no claim that it is \"realistic\")")]
    quantities = {q: [clean(b) for b in bullets(pre, "Quantities reported (definitions fixed now)", q)] for q in ("R1", "R2", "R3")}
    head = {q: clean(next(iter(table_rows(md, (q + ":",))), "")) for q in ("R1", "R2", "R3")}
    dep = {
        "shares_criterion_with_target": True,
        "note": ("The sweep DEFINES its onset ratio d_c from the turing-ddi continuum inequality and lambda_c from the turing-wavelength "
                 "record notation (PREREG, Ensemble). It tests their consequences in the nonlinear regime; it is not independent of their formulas."),
        "producer": "delphi-rethink-nca (Claude Sonnet 5.5)", "ensemble_designed_by_producer": True,
        "solvers_independent": False, "solvers_note": "both solvers are by the same author and share the equations (REPORT, Cautions)",
        "preregistered": {"protocol_commit": PREREG_COMMIT, "author_asserted_time": "2026-10-31T08:34:46-07:00", "witnessed": False},
        "shares_run_with": [],
    }
    common_author = {
        "assumptions": ensemble,
        "limitations": cautions + ["The orx run covers only the analysis step; the sweep itself ran outside OpenResearch under systemd-run and is not recorded there.",
                                   "Replay reproduces the analysis from the recorded report inputs; it does not re-run or independently check the 2,520-cell sweep (a separate GPU/CPU replay by the producer is planned, not done)."],
        "uncertainty": next((c for c in cautions if "intervals are exact" in c.lower() or "not independent" in c.lower()),
                            "Intervals treat cells as independent and are too narrow (REPORT)."),
        "method": ("Preregistered analysis (PREREG.md, committed before any scored row) of the finished 2,520-cell nonlinear sweep, executed as "
                   f"`{facts['command']}` through the OpenResearch local backend, on the code snapshot git:{facts['commit_sha']}. "
                   "Cells are NOT independent. The sweep itself (10,055 s, 2 workers, CPU) is outside this run."),
    }

    def ev_builder(target_id, qs, relation_note):
        def build(target, action_ref):
            a = dict(common_author)
            a["context"] = ("Applicability / scope evidence for Delphi claim " + target_id + " from a named ensemble of two kinetics models (1-D, zero-flux). "
                            "Quantities (PREREG definitions, verbatim): " + " | ".join(sum((quantities[q] for q in qs), [])) +
                            " Results (REPORT, verbatim): " + " | ".join(head[q] for q in qs) +
                            " This is a sweep over the producer's own ensemble, not a statement about tissue. Declared relation 'qualifies': "
                            + relation_note + " (a declaration by the importing adapter, not a review and not the producer's own label).")
            a["source_dependence"] = dict(dep)
            primary = {"locator": f"orx-run:{RUN_ID}; git:{REPO_LABEL}@{COMMIT[:12]}:{RES}/report.json", "sha256": sha["output:report.json"]}
            d = oe.to_evidence_draft(facts, target=target, author=a, kind="simulated", replay=replay, artifacts=A, link_checks=checks,
                                     primary=primary, evidence_id=f"orx-run-{RUN_ID}--{target_id}", relation="qualifies",
                                     produced_by=action_ref)
            d["payload"]["source"]["access"] = (
                "Run: held in the producing host's local OpenResearch store only. Artifacts: pinned by git commit in " + REPO_LABEL +
                "; only digests and locators are carried, no bytes. No licence is stated for this content (the OpenResearch MIT licence covers the "
                "software, not run content, and is not used as one). An artifact manifest is proposed for the site's /artifacts/ tree and is not yet hosted.")
            return d
        return build

    mcp = Delphi(min_interval=1.0, max_requests=60)
    claims = {}
    for cid in ("turing-ddi", "turing-wavelength"):
        snap, tr = dc.collect(mcp, cid)
        claims[cid] = dc.to_claim_draft(snap, verification=dc.verify_source(snap, tr))
    created = iso_utc()
    in_digests = {"rows.jsonl": sha["input:rows.jsonl"], "run_status.json": sha["input:run_status.json"]}
    note_ddi = ("it qualifies the scope of the claim's linear criterion in this ensemble: cells the criterion calls stable can pattern at finite "
                "amplitude (R1), while every linearly unstable cell patterned by the horizon (R2)")
    note_wl = ("in this ensemble the nonlinear dominant mode differs from the fastest linear mode in a third of linearly unstable cells (R3), "
               "which qualifies reading the onset wavelength as the observed spacing")
    out = bundle.assemble_many(
        claims, [("turing-ddi", ev_builder("turing-ddi", ("R1", "R2"), note_ddi)),
                 ("turing-wavelength", ev_builder("turing-wavelength", ("R3",), note_wl))],
        out_dir=OUT, created_at=created,
        action_builder=lambda target, refs: oe.to_action_draft(
            facts, target=target, inputs=refs, input_digests=in_digests, action_id=f"orx-run-{RUN_ID}-action--{target['id']}"))
    amf = art.manifest({"run_id": RUN_ID, "backend": "local (not hosted OpenResearch compute, no GPU)", "commit": facts["commit_sha"]}, A,
                       proposed_site_path=f"/artifacts/orx-run-{RUN_ID}/manifest.json")
    for name, obj in (("artifact-manifest.json", amf), ("replay_report.json", replay), ("link_checks.json", checks)):
        bad = art.find_abs_paths(obj)
        assert not bad, f"{name}: absolute paths at {bad}"
        with open(os.path.join(OUT, name), "w") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True); fh.write("\n")
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
