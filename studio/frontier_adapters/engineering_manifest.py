"""Engineering / formal producer receipts -> PROPOSED Problem, Claim, Action and Evidence drafts, frozen as an importable bundle.

First slice (<= 16 records): one fin-mechanics chain (simulation and render kept as SEPARATE Actions) and one Lean-certificate chain.

What this module is, and is not
  * It READS immutable git blobs (`git cat-file`) at a pinned `source_commit`; it never reads the working tree, never writes to a store,
    never contacts a service and never executes producer code. Producing a bundle is not importing it: corpus owns imports.
  * Every hash the producer's receipt states is RECOMPUTED from the blob and compared; a mismatch refuses the whole chain, and the
    reason names the file. A digest in a record is still not a byte verification by the store (the store never fetches).
  * Imported Actions record what the producer REPORTS it ran. Nothing here says Frontier executed it, and nothing here is reviewed:
    every record is single-reader, not Codex-reviewed, not independently reviewed.
  * Artifacts use the shared `frontier_adapters.artifacts` pointers and the store's own `ArtifactRef` (urn:sha256, availability
    `referenced`). No URL is claimed; no licence is asserted. Bytes are not embedded.
  * Sim and render are different Actions with different code and different output hashes. The producer did not record when each output
    was created (both files arrive in one commit), so the bundle says that instead of inventing an order; the render Action's `inputs`
    pin the simulation Evidence, which declares dependence and is not a record of execution order.
  * Not in this slice: the glide fixed-launch / RD video manifests and the print manifest. Printer slicing is UNKNOWN in the producer's
    material and nothing here may say otherwise.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

from .artifacts import entry, find_abs_paths, scrub_paths, to_artifact_ref, git_blob
from .common import canon, sha_bytes, sha_obj, validate_draft

ADAPTER_ID = "frontier_adapters.engineering_manifest"
ADAPTER_VERSION = "0.1.0"
REPO_LABEL = "delphi-frontier"
MAX_RECORDS = 16
STATUS = "PROPOSED. Not submitted, accepted or published. Single-reader (market worker), not Codex-reviewed, not independently reviewed."
IMPORT_NOTE = ("Imported record of what the producer's receipt reports. Frontier did not execute this and no one has re-run it; "
               "the producer's own code produced both the claim and the result, so it is not independent evidence.")
SOURCE_ACCESS = ("Public repository file at an immutable commit (git locator in the title/locator). Only digests are carried; bytes are not "
                 "embedded and no licence for the content is stated by this record.")


class Refused(ValueError):
    """The producer's receipt cannot be turned into records. The message names the check that failed."""


# --------------------------------------------------------------------------------------------------------------------------
# reading immutable blobs and recording every check
# --------------------------------------------------------------------------------------------------------------------------
class Chain:
    """Collects PROPOSED records in dependency order (each version digest depends on what it points to) and the checks behind them."""

    def __init__(self, repo: str, source_commit: str, namespace: str, issuer: str, created_at: str, name: str):
        self.repo, self.commit, self.ns, self.issuer, self.created_at, self.name = repo, source_commit, namespace, issuer, created_at, name
        self.records: list[dict] = []
        self.checks: list[dict] = []

    # ---- blobs
    def blob(self, path: str) -> bytes:
        try:
            return git_blob(self.repo, self.commit, path)
        except FileNotFoundError as e:
            raise Refused(f"[{self.name}] required producer file is not in the pinned commit: {e}") from None

    def jblob(self, path: str) -> dict:
        try:
            return json.loads(self.blob(path))
        except json.JSONDecodeError as e:
            raise Refused(f"[{self.name}] {path} is not valid JSON: {e}") from None

    def check(self, cid: str, ok: bool, detail: str, *, refuse: bool = True):
        self.checks.append({"id": cid, "ok": bool(ok), "detail": detail})
        if refuse and not ok:
            raise Refused(f"[{self.name}] check failed: {cid}: {detail}")

    def same_hash(self, cid: str, path: str, stated: str) -> bytes:
        data = self.blob(path)
        got = sha_bytes(data)
        self.check(cid, got == stated, f"{path}: producer states sha256 {stated[:16]}..., blob at {self.commit[:12]} hashes to {got[:16]}...")
        return data

    # ---- artifacts (shared pointers + the store's typed ArtifactRef)
    def artifact(self, role: str, path: str, data: bytes | None = None, note: str | None = None) -> dict:
        data = self.blob(path) if data is None else data
        return to_artifact_ref(entry(role, data, path=path, repo_label=REPO_LABEL, commit=self.commit, note=note))

    # ---- sequential validated records
    def add(self, draft: dict) -> dict:
        if len(self.records) >= MAX_RECORDS:
            raise Refused(f"[{self.name}] more than {MAX_RECORDS} records")
        bad = find_abs_paths(draft)
        if bad:
            raise Refused(f"[{self.name}] absolute local path in a draft at {bad}")
        v = validate_draft(draft, self.created_at)
        if v["licence_gate_offenders"]:
            raise Refused(f"[{self.name}] store licence gate would refuse: {v['licence_gate_offenders']}")
        self.records.append(v["record"])
        return {k: v["record"][k] for k in ("namespace", "kind", "id", "version")}

    def draft(self, kind: str, id_: str, payload: dict, source_uri: str) -> dict:
        return {"namespace": self.ns, "kind": kind, "id": id_, "issuer": self.issuer, "source_uri": source_uri, "visibility": "public",
                "predecessor": None, "payload": payload}


def _source(chain: Chain, path: str, data: bytes, what: str) -> dict:
    return {"uri": None, "locator": f"git:{REPO_LABEL}@{chain.commit}:{path}", "source_version": f"git:{REPO_LABEL}@{chain.commit}",
            "content_sha256": sha_bytes(data), "content_available": False, "access": SOURCE_ACCESS + " " + what, "license": None}


def _cache_key(target_version: str, **dims) -> dict:
    from frontier.models import POLICY
    ck = {"target": target_version, **dims, "acceptance_policy": POLICY}
    return {k: (v if len(v) <= 1000 else v[:997] + "...") for k, v in ck.items()}


def _time(chain: Chain) -> tuple[dict, dict]:
    # The producers record no run time. created_time is therefore UNKNOWN; the commit that carries the file is only an upper bound.
    return ({"value": None, "basis": "unknown"}, {"value": chain.created_at, "basis": "declared"})


def _commit_utc(repo: str, commit: str) -> str:
    out = subprocess.run(["git", "-C", repo, "show", "-s", "--format=%cI", commit], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise Refused(f"cannot read commit {commit[:12]}: {out.stderr.strip()[:100]}")
    return datetime.fromisoformat(out.stdout.strip()).astimezone(timezone.utc).isoformat()


def resolve_commit(repo: str, rev: str) -> str:
    out = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", rev + "^{commit}"], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise Refused(f"cannot resolve {rev!r}: {out.stderr.strip()[:100]}")
    return out.stdout.strip()


# --------------------------------------------------------------------------------------------------------------------------
# chain 1: fin mechanics (simulation Action and render Action are separate)
# --------------------------------------------------------------------------------------------------------------------------
FIN_DIR = "engineering/fin_mechanics"


def fin_mechanics_chain(repo: str, source_commit: str, *, namespace: str = "node-a", issuer: str = "importer", created_at: str | None = None) -> Chain:
    """Claim (derived critical stiffness) -> Action(sim) -> Evidence(sim) -> Action(render, inputs=[Evidence(sim)]) -> Evidence(render) -> Problem."""
    created_at = created_at or _commit_utc(repo, source_commit)
    c = Chain(repo, source_commit, namespace, issuer, created_at, "fin_mechanics")
    art = f"{FIN_DIR}/artifacts"
    man = c.jblob(f"{art}/manifest.json")
    c.check("manifest.schema", man.get("schema") == "frontier.finmech.manifest/1", f"schema {man.get('schema')!r}")
    c.check("manifest.evidence_kind", man.get("evidence_kind") == "simulated", f"producer declares evidence_kind {man.get('evidence_kind')!r}")
    # outputs: every output file's blob must hash to what the manifest states
    outs = man["outputs"]
    result_bytes = c.same_hash("output.result_json", f"{art}/result.json", outs["result.json"]["sha256"])
    mp4 = c.same_hash("output.mp4", f"{art}/fin_mechanics.mp4", outs["fin_mechanics.mp4"]["sha256"])
    poster = c.same_hash("output.poster", f"{art}/poster.png", outs["poster.png"]["sha256"])
    for name, data in (("result.json", result_bytes), ("fin_mechanics.mp4", mp4), ("poster.png", poster)):
        c.check(f"output.size.{name}", len(data) == outs[name]["bytes"], f"{name}: manifest {outs[name]['bytes']} bytes, blob {len(data)}")
    # code: each file hash, then the combined code identity the producer prints (sha256 of the canonical JSON of the per-file hashes)
    code_bytes = {}
    for fn, stated in man["code_files_sha256"].items():
        code_bytes[fn] = c.same_hash(f"code.{fn}", f"{FIN_DIR}/{fn}", stated)
    c.check("code.combined", sha_obj(man["code_files_sha256"]) == man["code_sha256"], "sha256(canonical JSON of per-file hashes) equals manifest code_sha256")
    # input request: file hash and the canonical hash the result echoes
    req_bytes = c.same_hash("input.request_file", f"{FIN_DIR}/{man['request_file']['path']}", man["request_file"]["sha256"])
    result = json.loads(result_bytes)
    c.check("result.schema", result.get("schema") == "frontier.finmech.result/1" and result.get("verdict") == "ok", f"schema {result.get('schema')!r} verdict {result.get('verdict')!r}")
    c.check("result.inputs_sha256", result["inputs_sha256"] == man["request_file"]["canonical_sha256"], "result.inputs_sha256 equals manifest request canonical_sha256")
    c.check("result.code_sha256", result["code_sha256"] == man["code_sha256"], "result.code_sha256 equals manifest code_sha256")
    c.check("result.evidence_kind", result.get("evidence_kind") == "simulated", f"result evidence_kind {result.get('evidence_kind')!r}")
    crit = result["critical_stiffness"]
    from fractions import Fraction
    try:
        exact_ok = abs(float(Fraction(crit["EI_crit_Nm2_exact"])) - crit["EI_crit_Nm2_float"]) < 1e-15 * max(1.0, abs(crit["EI_crit_Nm2_float"]))
    except (ValueError, ZeroDivisionError, KeyError):
        exact_ok = False
    c.check("result.critical_stiffness", exact_ok, f"EI_crit exact {crit.get('EI_crit_Nm2_exact')!r} parses as a rational equal to the float {crit.get('EI_crit_Nm2_float')!r}")
    vid = man["video"]
    c.check("video.counts", vid["n_frames"] == round(vid["duration_s"] * vid["fps"]) and 0 <= vid["n_frames_invalid"] <= vid["n_frames"],
            f"{vid['n_frames']} frames = {vid['duration_s']} s x {vid['fps']} fps; {vid['n_frames_invalid']} flagged invalid")
    request = json.loads(req_bytes)
    c.check("request.declared_illustration", "DECLARED ILLUSTRATION" in str(request.get("label", "")), f"request label: {str(request.get('label'))[:90]!r}", refuse=False)

    # ---------- records
    not_est = list(result["not_established"])
    assumptions = list(result["assumptions"])
    src_uri = "urn:frontier:adapter:engineering-manifest:fin-mechanics"
    exact = crit["EI_crit_Nm2_exact"]
    limitations_common = [
        IMPORT_NOTE,
        "The request is labelled by its producer: " + str(request.get("label")) + ". Its numbers are test values, not a design claim.",
        "EI is an ASSUMED log-spaced range (" + result["EI_assumed_range"]["min_Nm2"] + " to " + result["EI_assumed_range"]["max_Nm2"] + " N m^2), not a measurement of any fin ray.",
    ] + [f"Producer states it does not establish: {x}" for x in not_est]
    claim_ref = c.add(c.draft("Claim", "eng-finmech-claim-ei-crit", {
        "title": "Declared-load critical bending stiffness of a single clamped-free ray (linear small-deformation surrogate)",
        "statement": (f"For the producer's declared request (canonical sha256 {result['inputs_sha256'][:16]}...), in a linear static Euler-Bernoulli cantilever with a uniform line load from a "
                      f"declared lift-pressure proxy, the bending stiffness below which the declared small-deformation limits are exceeded is EI_crit = {exact} N m^2 "
                      f"(binding limit: {crit.get('binding_limit')})."),
        "context": ("Producer-derived number from exact rational arithmetic on DECLARED inputs (rho, V, CL, tributary width, ray length, validity thresholds). "
                    "It is a threshold of the surrogate, not a property of any fish. Decision rule stated by the producer: " + result["measurement_question"]["decision_rule"]),
        "assumptions": assumptions, "limitations": limitations_common,
        "source": _source(c, f"{art}/result.json", result_bytes, "Claim statement is the producer's critical_stiffness field."),
        "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src_uri))

    sim_code = {k: v for k, v in man["code_files_sha256"].items() if k != "render.py"}
    action_sim_ref = c.add(c.draft("Action", "eng-finmech-action-sim", {
        "target": claim_ref,
        "title": "Imported record of a producer-reported run (NOT executed by Frontier): fin-mechanics EI sweep and critical-stiffness computation",
        "acceptance_criteria": ["A clean re-execution from the pinned code and the pinned request file reproduces result.json byte-for-byte, and the producer's controls pass.",
                                "An independent reviewer checks the surrogate's assumptions against the claim before it is used for anything."],
        "required_capabilities": ["python3 with numpy (versions NOT recorded by the producer)"],
        "cost_stop_bounds": "Wall time and resources of the producer's run are NOT recorded in its manifest. No budget or stop bound was declared.",
        "cache_key": _cache_key(claim_ref["version"],
                                input=f"request {man['request_file']['sha256']}; canonical {man['request_file']['canonical_sha256']}",
                                code=f"git:{REPO_LABEL}@{source_commit}; code_sha256 {man['code_sha256']}; files " + ", ".join(f"{k}:{v[:12]}" for k, v in sorted(sim_code.items())),
                                model=f"{result['model_version']} (deterministic surrogate, no language model)",
                                environment="NOT RECORDED by the producer (interpreter, package versions, hardware)",
                                parameters="request file as pinned; EI sweep 61 log-spaced points over the assumed range; 64 elements",
                                scope="simulated surrogate on declared inputs; not a measurement and not a design claim"),
        "inputs": []}, src_uri))
    ev_sim_ref = c.add(c.draft("Evidence", "eng-finmech-evidence-sim", {
        "target": claim_ref, "evidence_kind": "simulated",
        "source": _source(c, f"{art}/result.json", result_bytes, "Primary result file."),
        "created_time": _time(c)[0], "retrieved_time": _time(c)[1],
        "method": "Producer's deterministic surrogate: " + result["model_version"] + ". Controls reported by the producer: FEM vs analytic max relative difference "
                  f"{result['controls']['fem_vs_analytic_max_rel_diff_over_sweep']:.3g}; analytic residuals vs independent quadrature <= {result['controls']['max_rel_residual']:.3g}.",
        "context": "Applicability: the surrogate's own critical stiffness for a declared illustration request. " + IMPORT_NOTE,
        "assumptions": assumptions,
        "provenance": {"system": "engineering/fin_mechanics (producer code in this repository)", "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION},
                       "source_commit": source_commit, "code_sha256": man["code_sha256"], "inputs_sha256": result["inputs_sha256"],
                       "validity": result["validity"], "checks_performed_by_adapter": [k["id"] for k in c.checks if k["ok"]],
                       "execution": "reported by the producer; not executed or replayed by this adapter"},
        "source_dependence": {"declared": True, "group": "same producer and same code produced the claim and this result", "independent_of_claim": False},
        "uncertainty": "Not quantified by the producer beyond numerical controls; the input range is an assumption.",
        "limitations": limitations_common + [f"{result['validity']['fraction_of_assumed_range_valid_uniform']:.3f} of the assumed EI range is inside the small-deformation limit; the rest is flagged invalid, not hidden."],
        "local_id": None, "provider_assessment": None, "relation": "unspecified", "produced_by": action_sim_ref,
        "artifacts": [c.artifact("output", f"{art}/result.json", result_bytes, "primary simulation result"),
                      c.artifact("input", f"{FIN_DIR}/{man['request_file']['path']}", req_bytes, "pinned request (a declared illustration)")]
                     + [c.artifact("code", f"{FIN_DIR}/{fn}", code_bytes[fn]) for fn in sorted(sim_code)]}, src_uri))

    action_render_ref = c.add(c.draft("Action", "eng-finmech-action-render", {
        "target": claim_ref,
        "title": "Imported record of a producer-reported render (NOT executed by Frontier): video and poster from the computed frames",
        "acceptance_criteria": ["Re-rendering from the pinned code and the simulation result reproduces the numeric frames (frames_data_sha256); mp4 bytes may differ across ffmpeg builds.",
                                "The video is read as a picture of the computed frames, not as additional evidence."],
        "required_capabilities": ["python3 with numpy and matplotlib; ffmpeg (versions NOT recorded by the producer)"],
        "cost_stop_bounds": "Wall time and resources of the producer's render are NOT recorded. No budget or stop bound was declared.",
        "cache_key": _cache_key(claim_ref["version"],
                                input=f"simulation evidence version {ev_sim_ref['version']}; result.json sha256 {outs['result.json']['sha256']}",
                                code=f"git:{REPO_LABEL}@{source_commit}; render.py sha256 {man['code_files_sha256']['render.py']}; code_sha256 {man['code_sha256']}",
                                model="none: deterministic rendering of computed frames",
                                environment="NOT RECORDED by the producer (ffmpeg build, matplotlib, fonts)",
                                parameters=f"{vid['n_frames']} frames, {vid['fps']} fps, {vid['duration_s']} s, {vid['size_px'][0]}x{vid['size_px'][1]}",
                                scope="visualisation of a simulated surrogate; creation time and order relative to the simulation are NOT recorded"),
        "inputs": [ev_sim_ref]}, src_uri))
    c.add(c.draft("Evidence", "eng-finmech-evidence-render", {
        "target": claim_ref, "evidence_kind": "simulated",
        "source": _source(c, f"{art}/manifest.json", c.blob(f"{art}/manifest.json"), "Render manifest."),
        "created_time": _time(c)[0], "retrieved_time": _time(c)[1],
        "method": f"Producer's renderer draws {vid['n_frames']} frames from {vid['frames_from']}.",
        "context": "A picture of the computed frames, linked to the simulation Evidence it consumed. It adds no new support for the Claim. " + IMPORT_NOTE,
        "assumptions": assumptions,
        "provenance": {"system": "engineering/fin_mechanics render.py", "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION}, "source_commit": source_commit,
                       "frames_data_sha256": vid["frames_data_sha256"], "frames_valid": vid["n_frames"] - vid["n_frames_invalid"], "frames_invalid": vid["n_frames_invalid"],
                       "ordering_note": "The producer records no creation time for either output; both files arrive in one commit. Separation of the two Actions follows different code and different outputs, not a recorded sequence.",
                       "execution": "reported by the producer; not executed or replayed by this adapter"},
        "source_dependence": {"declared": True, "group": "same producer and same computed frames as the simulation Evidence", "independent_of_claim": False},
        "uncertainty": "Not applicable to a rendering; the numeric frames are the reproducible quantity (" + vid["frames_data_sha256"][:16] + "...).",
        "limitations": [IMPORT_NOTE, f"{vid['n_frames_invalid']} of {vid['n_frames']} frames are flagged by the producer as outside the small-deformation limit.",
                        man["note"], "mp4 and png are views for people; they are not an artifact of the measurement and not a validation of anything."],
        "local_id": None, "provider_assessment": None, "relation": "context_only", "produced_by": action_render_ref,
        "artifacts": [c.artifact("output", f"{art}/fin_mechanics.mp4", mp4, "video of the computed frames; bytes can vary with the ffmpeg build"),
                      c.artifact("output", f"{art}/poster.png", poster, "poster image"),
                      c.artifact("code", f"{FIN_DIR}/render.py", code_bytes["render.py"]),
                      c.artifact("receipt", f"{art}/manifest.json", c.blob(f"{art}/manifest.json"), "producer manifest with output and code hashes")]}, src_uri))

    mq = result["measurement_question"]
    c.add(c.draft("Problem", "eng-finmech-problem-ei-measurement", {
        "title": "Is the real effective bending stiffness of the target fin ray above or below the declared critical stiffness?",
        "known_state": f"The surrogate's critical stiffness for the declared illustration request is EI_crit = {exact} N m^2; the EI of any real ray is not known to this repository (assumed range only).",
        "question": mq["question"], "problem_kind": "project_gap",
        "novelty_status": "Not searched by this adapter; the producer cites a different species and boundary condition as context only.",
        "data_access": "No measurement of any real ray exists in this repository; EI appears only as an assumed range (status " + result["EI_assumed_range"]["status"] + ").",
        "completeness": "recorded", "acceptance_criteria": [], "falsifiers": [], "next_action": None, "required_capabilities": [mq["apparatus"]],
        "cost_stop_bounds": None, "downstream_uses": [x for x in (mq["decision_rule"], mq.get("turns")) if x],
        "dependencies": [claim_ref],
        "source": _source(c, f"{art}/result.json", result_bytes, "Problem text is the producer's measurement_question field, copied."),
        "original": {"producer_field": "measurement_question", "adapter": ADAPTER_ID},
        "approach": "measurement", "scales": [], "context_tags": ["engineering-surrogate", "declared-illustration"]}, src_uri))
    return c


# --------------------------------------------------------------------------------------------------------------------------
# chain 2: Lean certificate (z3 search that produced it is recorded in provenance, not as separate evidence)
# --------------------------------------------------------------------------------------------------------------------------
FORMAL_DIR = "engineering/formal"
STANDARD_AXIOMS = {"Classical.choice", "Quot.sound", "propext"}


def formal_certificate_chain(repo: str, source_commit: str, *, namespace: str = "node-a", issuer: str = "importer", created_at: str | None = None) -> Chain:
    """Claim (conflict among declared constraints) -> Action(Lean kernel check, reported) -> Evidence(formal)."""
    created_at = created_at or _commit_utc(repo, source_commit)
    c = Chain(repo, source_commit, namespace, issuer, created_at, "formal_certificate")
    rb = c.blob(f"{FORMAL_DIR}/RECEIPT.json")
    rec = json.loads(rb)
    sr, lc = rec["solver_result"], rec["lean_checks"]
    c.check("solver.unsat", sr["status"] == "unsat", f"solver status {sr['status']!r}")
    c.check("solver.core_minimal", sr.get("core_minimal") is True, f"core_minimal {sr.get('core_minimal')!r}")
    c.check("lean.ran", lc.get("lean") == "ran" and lc.get("all_ok") is True, f"lean {lc.get('lean')!r} all_ok {lc.get('all_ok')!r}")
    pos, neg = lc["positive"], lc["negative"]
    c.check("lean.positive.exit0", pos["exit"] == 0, f"positive exit {pos['exit']}")
    c.check("lean.positive.axioms", pos["only_standard_axioms"] is True and set(pos["axioms_used"]) <= STANDARD_AXIOMS and not pos["non_axiom_output"],
            f"axioms {sorted(pos['axioms_used'])}; non-axiom output {pos['non_axiom_output']}")
    rejected = neg["each_block_rejected"]
    c.check("lean.negative.all_rejected", bool(rejected) and all(rejected.values()) and not neg["errors_outside_blocks"],
            f"negative controls rejected: {sorted(k for k, v in rejected.items() if v)} of {sorted(rejected)}")
    cert = rec["lean_certificate_text"]
    c.check("certificate.text_hash", sha_bytes(cert.encode()) == lc["provenance"]["assembled_sources_sha256"]["certificate_text"], "sha256(lean_certificate_text) equals the receipt's certificate_text hash")
    # the Lean theory files and constraints.py the receipt hashed
    file_bytes = {}
    for name, stated in lc["provenance"]["files"].items():
        if name == "lean_checks.py" or name.endswith(".lean") or name == "../constraints.py":
            path = f"{FORMAL_DIR}/{name}" if not name.startswith("..") else "engineering/" + name[3:]
            file_bytes[path] = c.same_hash(f"file.{name}", path, stated)
    c.check("theory.hash", sha_bytes(file_bytes[f"{FORMAL_DIR}/GeometricSimilarity.lean"]) == lc["theory_sha256"], "theory_sha256 equals GeometricSimilarity.lean blob hash")

    src_uri = "urn:frontier:adapter:engineering-manifest:formal-certificate"
    scope, reason = sr["scope"], sr["reason"]
    used = sr["used_constraints"]
    conflict = sr["conflict"]
    prov = sr["provenance"]
    params = {k: v["value"] for k, v in prov["level_lift_proxy"]["parameters"].items()}
    lean_ver = lc["lean_version"].split("(")[1].split(",")[0].replace("version ", "").strip()
    lib_note = f"Lean {lean_ver} with Mathlib rev {lc['provenance']['mathlib_rev'][:12]}; project path withheld"
    limitations = [
        IMPORT_NOTE,
        "Scope stated by the producer: " + scope,
        "The z3 search that found the conflict is reported as: " + reason + ". The formal evidence is the Lean kernel check of the certificate, not the z3 verdict.",
        "Whether the plain-language statement is a faithful reading of the Lean theorem has not been reviewed.",
        f"rho and CL are design assumptions set by the caller (rho={params.get('rho')}, CL={params.get('CL')}); they come from no source in the repository.",
        "No independent proof object exists for the z3 step; the Lean check covers only the stated certificate theorem under its stated hypotheses.",
    ]
    claim_ref = c.add(c.draft("Claim", "eng-formal-claim-declared-constraints-conflict", {
        "title": "Three declared flying-fish design constraints have no common solution (level-lift proxy, minimum wing loading, maximum speed)",
        "statement": ("There are no real m, g, S, V with S > 0, V >= 0, wing loading at least 150, V at most 10 and the level-flight lift proxy "
                      "2*m*g <= V^2*(49/40)*S*1 jointly satisfied. Lean theorem as produced by the receipt:\n" + cert.strip()),
        "context": "Derived by the producer's constraint solver and certified by a Lean kernel check. " + scope,
        "assumptions": [f"{k} = {v} ({prov['level_lift_proxy']['parameters'][k]['kind']})" for k, v in params.items()] + ["constraints used: " + ", ".join(used) + "; minimal conflict core: " + ", ".join(conflict)],
        "limitations": limitations,
        "source": _source(c, f"{FORMAL_DIR}/RECEIPT.json", rb, "Claim is the receipt's conflict_instance theorem and conflict core."),
        "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src_uri))
    action_ref = c.add(c.draft("Action", "eng-formal-action-lean-check", {
        "target": claim_ref,
        "title": "Imported record of a producer-reported Lean kernel check (NOT executed by Frontier): conflict certificate plus negative controls",
        "acceptance_criteria": ["A clean re-run of the pinned Lean sources reproduces exit 0 with only standard axioms for the positive block.",
                                "Each of the four negative blocks (including the corrupted certificate) is rejected by the kernel on re-run."],
        "required_capabilities": [f"Lean {lean_ver} toolchain", "Mathlib at the recorded revision"],
        "cost_stop_bounds": f"Reported wall time: positive {pos['seconds']} s, negative {neg['seconds']} s (producer's clock, single run). No budget or stop bound was declared.",
        "cache_key": _cache_key(claim_ref["version"],
                                input=f"certificate_text sha256 {lc['provenance']['assembled_sources_sha256']['certificate_text']}; positive source {lc['provenance']['assembled_sources_sha256']['positive']}; "
                                      f"negative source {lc['provenance']['assembled_sources_sha256']['negative']}",
                                code=f"git:{REPO_LABEL}@{source_commit}; theory_sha256 {lc['theory_sha256']}; lean_checks.py {lc['provenance']['files']['lean_checks.py']}",
                                model="none: Lean kernel check; the certificate was found by a z3-based solver, no language model recorded",
                                environment=f"{lib_note}; lake manifest {lc['provenance']['lake_manifest_sha256'][:16]}...; OS/hardware NOT recorded",
                                parameters="positive block, then four negative blocks (wl_k2, mass_exponent, stall_k2, corrupted_certificate)",
                                scope="formal check of one theorem under stated hypotheses; not organism feasibility"),
        "inputs": []}, src_uri))
    c.add(c.draft("Evidence", "eng-formal-evidence-lean-check", {
        "target": claim_ref, "evidence_kind": "formal",
        "source": _source(c, f"{FORMAL_DIR}/RECEIPT.json", rb, "Receipt of the formal check."),
        "created_time": _time(c)[0], "retrieved_time": _time(c)[1],
        "method": f"Lean kernel check, {lib_note}; positive block exit {pos['exit']} in {pos['seconds']} s with axioms {sorted(pos['axioms_used'])}; "
                  f"negative controls rejected: {sorted(rejected)}. The certificate came from a z3 conflict search (status {sr['status']}, solver {sr['solver']}, z3 {sr['z3_version']}).",
        "context": "Formal check of the Lean theorem quoted in the Claim. 'supports' is a declaration by the adapter that this check bears on the Claim's statement; it is not a review of statement fidelity.",
        "assumptions": ["The Lean hypotheses are the Claim's stated constraints with the stated rho and CL.", "Mathlib and the Lean kernel are trusted as installed."],
        "provenance": {"system": "engineering/formal/lean_checks.py", "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION}, "source_commit": source_commit,
                       "lean_version": lc["lean_version"], "mathlib_rev": lc["provenance"]["mathlib_rev"], "toolchain_file": lc["provenance"]["lean_toolchain_file"],
                       "solver": {"name": sr["solver"], "z3_version": sr["z3_version"], "status": sr["status"], "core_minimal": sr["core_minimal"],
                                  "used_constraints": used, "conflict_core": conflict, "verdict_checked_by": "z3 only (producer's own words); no independent proof object"},
                       "positive": {"exit": pos["exit"], "seconds": pos["seconds"], "axioms_used": sorted(pos["axioms_used"])},
                       "negative": {"exit": neg["exit"], "seconds": neg["seconds"], "each_block_rejected": rejected},
                       "checks_performed_by_adapter": [k["id"] for k in c.checks if k["ok"]],
                       "execution": "reported by the producer; not executed or replayed by this adapter"},
        "source_dependence": {"declared": True, "group": "same producer built the constraints, found the certificate and wrote the checks", "independent_of_claim": False},
        "uncertainty": "Not applicable to a kernel check beyond trust in the toolchain; statement fidelity is separate and unreviewed.",
        "limitations": limitations,
        "local_id": None, "provider_assessment": None, "relation": "supports", "produced_by": action_ref,
        "artifacts": [c.artifact("certificate", f"{FORMAL_DIR}/RECEIPT.json", rb, "receipt containing the certificate text and the Lean results")]
                     + [c.artifact("code", p, file_bytes[p]) for p in sorted(file_bytes)]}, src_uri))
    return c


# --------------------------------------------------------------------------------------------------------------------------
# assembly: link checks, a frozen frontier-bundle-0.1, and a chain/manifest report
# --------------------------------------------------------------------------------------------------------------------------
def _refs_in(record: dict) -> list[tuple[str, dict]]:
    p, out = record["payload"], []
    if "target" in p:
        out.append(("target", p["target"]))
    if p.get("produced_by"):
        out.append(("produced_by", p["produced_by"]))
    out += [("inputs", r) for r in p.get("inputs", [])] + [("dependencies", r) for r in p.get("dependencies", [])]
    return out


def link_checks(records: list[dict]) -> list[dict]:
    """Every pointer resolves to a record IN the bundle at that exact version, and Evidence/Action agree on their target."""
    by = {(r["namespace"], r["kind"], r["id"], r["version"]): r for r in records}
    checks = []
    for r in records:
        for field, ref in _refs_in(r):
            key = (ref["namespace"], ref["kind"], ref["id"], ref["version"])
            checks.append({"id": f"{r['id']}.{field}", "ok": key in by, "detail": f"{field} -> {ref['kind']}/{ref['id']}@{ref['version'][:12]}"})
        if r["kind"] == "Evidence" and r["payload"].get("produced_by"):
            act = by.get(tuple(r["payload"]["produced_by"][k] for k in ("namespace", "kind", "id", "version")))
            ok = bool(act) and act["payload"]["target"]["version"] == r["payload"]["target"]["version"]
            checks.append({"id": f"{r['id']}.produced_by_same_target", "ok": ok, "detail": "Evidence and the Action that produced it target the same exact Claim version"})
        for a in r["payload"].get("artifacts", []):
            ok = a["availability"] == "referenced" and a["uri"] == "urn:sha256:" + a["sha256"] and a.get("license") is None
            checks.append({"id": f"{r['id']}.artifact.{a['sha256'][:10]}", "ok": ok, "detail": f"{a['role']} availability={a['availability']} license={a.get('license')}"})
    return checks


def build_bundle(chains: list[Chain], *, exporting_node: str | None = None, limit: int | None = None) -> dict:
    """A frozen, importable `frontier-bundle-0.1` (same body construction as Store.export_bundle). Nothing is written to any store."""
    from frontier.models import MAX_BUNDLE_BYTES, MAX_BUNDLE_RECORDS, POLICY, Record, digest
    records = [r for ch in chains for r in ch.records]
    limit = MAX_RECORDS if limit is None else limit            # read at call time: tests (and callers) may patch MAX_RECORDS
    if len(records) > limit:
        raise Refused(f"{len(records)} records exceeds the {'first-slice' if limit == MAX_RECORDS else 'slice'} limit of {limit}")
    if len(records) > MAX_BUNDLE_RECORDS:
        raise Refused("exceeds the store's bundle record limit")
    for r in records:
        Record.model_validate(r)
    if len({(r["namespace"], r["kind"], r["id"]) for r in records}) != len(records):
        raise Refused("duplicate record ids in the bundle")
    bad = [c for c in link_checks(records) if not c["ok"]]
    if bad:
        raise Refused(f"link checks failed: {bad[:3]}")
    namespaces = {r["namespace"] for r in records}
    body = {"schema_version": "frontier-bundle-0.1", "exporting_node": exporting_node or sorted(namespaces)[0], "records": records, "review_claims": [],
            "policy_version": POLICY, "trust": "Digest proves integrity only; reviews require receiving-node policy."}
    bundle = {**body, "bundle_sha256": digest(body)}
    if len(canon(bundle).encode()) > MAX_BUNDLE_BYTES:
        raise Refused("bundle exceeds the store's byte limit")
    return bundle


def chain_report(chains: list[Chain], bundle: dict) -> dict:
    records = bundle["records"]
    return {
        "status": STATUS, "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION},
        "source": {"repo_label": REPO_LABEL, "commit": chains[0].commit, "read": "immutable git blobs only; working tree not read"},
        "counts": {"records": len(records), **{k: sum(1 for r in records if r["kind"] == k) for k in ("Problem", "Claim", "Action", "Evidence")}, "limit": MAX_RECORDS},
        "execution_statement": "Every Action is an IMPORTED RECORD of what the producer reports. None was executed by Frontier or by this adapter, none was replayed, none was reviewed.",
        "chains": [{"name": ch.name, "records": [{"kind": r["kind"], "id": r["id"], "version": r["version"]} for r in ch.records],
                    "checks": ch.checks} for ch in chains],
        "link_checks": link_checks(records),
        "artifact_policy": "All artifacts are ArtifactRef with availability 'referenced' and a urn:sha256 pointer; no URL is claimed, no licence asserted, bytes not embedded.",
        "not_in_this_slice": ["glide fixed-launch and RD video manifests", "print manifest (printer slicing is UNKNOWN in the producer's material)"],
        "bundle_sha256": bundle["bundle_sha256"],
        "record_payload_sha256": {r["id"]: sha_obj(r["payload"]) for r in records},
    }


def write_frozen(out_dir: str, chains: list[Chain]) -> dict:
    bundle = build_bundle(chains)
    report = chain_report(chains, bundle)
    os.makedirs(out_dir, exist_ok=True)
    files = {"bundle.frontier-bundle-0.1.json": json.dumps(bundle, indent=1, sort_keys=True) + "\n",
             "chain.json": json.dumps(report, indent=1, sort_keys=True) + "\n"}
    bad = find_abs_paths(bundle) + find_abs_paths(report)
    if bad:
        raise Refused(f"absolute local paths in output at {bad}")
    for n, t in files.items():
        with open(os.path.join(out_dir, n), "w") as fh:
            fh.write(t)
    manifest = {"status": STATUS, "bundle_sha256": bundle["bundle_sha256"], "file_sha256": {n: sha_bytes(t.encode()) for n, t in files.items()},
                "records": [{"kind": r["kind"], "id": r["id"], "namespace": r["namespace"], "version": r["version"]} for r in bundle["records"]],
                "publication": "none. Not written to any store; corpus owns imports."}
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        fh.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return {"bundle": bundle, "report": report, "manifest": manifest}


def build_first_slice(repo: str, source_commit: str, *, namespace: str = "node-a", issuer: str = "importer", created_at: str | None = None) -> list[Chain]:
    commit = resolve_commit(repo, source_commit)
    return [fin_mechanics_chain(repo, commit, namespace=namespace, issuer=issuer, created_at=created_at),
            formal_certificate_chain(repo, commit, namespace=namespace, issuer=issuer, created_at=created_at)]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m frontier_adapters.engineering_manifest",
                                 description="Freeze the first-slice engineering/formal bundle from immutable git blobs. Writes files only; never touches a store.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--source-commit", required=True, help="commit (or rev) holding the producer receipts; recorded in every locator")
    ap.add_argument("--out", required=True)
    ap.add_argument("--namespace", default="node-a")
    ap.add_argument("--issuer", default="importer")
    ap.add_argument("--created-at", default=None, help="ISO time pinned into every record; default: the source commit's committer time (UTC)")
    a = ap.parse_args(argv)
    chains = build_first_slice(a.repo, a.source_commit, namespace=a.namespace, issuer=a.issuer, created_at=a.created_at)
    out = write_frozen(a.out, chains)
    print(json.dumps({"records": len(out["bundle"]["records"]), "bundle_sha256": out["bundle"]["bundle_sha256"], "out": a.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
