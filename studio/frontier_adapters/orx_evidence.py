"""OpenResearch (`orx`) run -> Frontier Evidence draft.

Read-only. This adapter NEVER executes anything from a run; replay is a separate, explicit script
(`orx_replay.py`) that needs a flag and is meant for code you wrote.

A run is accepted as the subject of an Evidence record only if ALL of these hold (each is a control with
a failing test):
  * status is "done" AND the run directory's exit_code file is 0   (the DB exit_code column is NULL for a
    successful local run in orx 0.2.23, so the file is the only witness)
  * the source tarball's sha256 equals the digest orx recorded       (code identity is checked, not trusted)
  * the named result file exists in the run directory                 (we hash it ourselves)
  * the evidence kind is "simulated" or "predicted"                   (a computational run is never "observed";
    "formal" needs a proof checker and "source_assessment" is not a run)

Every Evidence field carries its ORIGIN in provenance.field_origin: "orx" (read from the run record),
"adapter" (computed here), "author" (declared by whoever ran it), or "absent" (nobody can fill it).
What OpenResearch cannot supply is therefore visible in the record, not implied.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tarfile
import urllib.request

from .artifacts import find_abs_paths, scrub_paths
from .common import iso_utc, sha_bytes, sha_obj

ADAPTER_ID = "frontier_adapters.orx_evidence"
ADAPTER_VERSION = "0.1.0"
ALLOWED_KINDS = ("simulated", "predicted")
OPENRESEARCH_PIN = "alphaXiv/OpenResearch@703fd4bba66311625cf7e0b0776a0f949d3f4c73"  # source read for this adapter

# Always-true limitations of an orx run record (read from the pinned source and observed on orx 0.2.23).
MECHANICAL_LIMITATIONS = [
    "OpenResearch does not record the execution environment (interpreter, OS, packages, hardware); local runs use "
    "the host's own environment and container images are mutable tags, so the record alone does not say how to "
    "reproduce the environment.",
    "Inputs outside the committed git snapshot and any random seeds are not recorded; only the command string and "
    "the committed code are.",
    "OpenResearch does not hash or register run outputs; the content digest in this record was computed by the "
    "adapter from a mutable local run directory at retrieval time.",
    "Run, experiment and project ids are random UUIDs local to one machine's store: there is no shared registry, "
    "and the run can be deleted by its owner (`orx exp delete`).",
    "A run reaching status 'done' means the process exited 0. It says nothing about scientific validity and has "
    "not been reviewed.",
    "The database exit_code was NULL for this local run; the exit code was read from the run directory's exit_code "
    "file instead.",
]


EXTERNAL_IO_LIMITATIONS = [
    "This run read its inputs from, and wrote its outputs to, a directory OUTSIDE the OpenResearch snapshot and run directory. "
    "OpenResearch stores neither: the input and output digests here were computed by the adapter from immutable git blobs, "
    "and the run itself only links to them through hashes its own script printed.",
    "OpenResearch does not list a run's inputs. Replaying with one of two input files missing produced a different report "
    "without any error (measured during this import), so a replayer cannot learn the full input set from the record.",
]


class Refused(ValueError):
    """The run cannot be the subject of an Evidence record. The message names the control that failed."""


def _rb(path):
    with open(path, "rb") as fh:
        return fh.read()


def _jl(path):
    with open(path) as fh:
        return json.load(fh)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def read_run(*, run_id: str, api: str | None = None, export_dir: str | None = None, result_file: str) -> dict:
    """Collect and VERIFY the facts about one run, from a live `orx up/serve` API or an export directory."""
    if bool(api) == bool(export_dir):
        raise ValueError("give exactly one of api= or export_dir=")
    if api:
        run = _get(f"{api}/api/runs/{run_id}")["run"]
        health = _get(f"{api}/api/health")
        base = run["backend"].get("jobId")            # local path; read, never emitted
        tar_path = run["backend"].get("sourcePath")
    else:
        run = _jl(os.path.join(export_dir, "run.json"))["run"]
        health = _jl(os.path.join(export_dir, "health.json"))
        base, tar_path = export_dir, os.path.join(export_dir, "source.tar")
    be = run["backend"]
    if run["status"] != "done":
        raise Refused(f"run status is {run['status']!r}, not 'done': a run that did not complete is not evidence")
    def read(name, sub=""):
        p = os.path.join(base, sub, name) if sub else os.path.join(base, name)
        return _rb(p) if os.path.isfile(p) else None
    exit_raw = read("exit_code")
    if exit_raw is None or exit_raw.strip() != b"0":
        raise Refused(f"exit_code file is {exit_raw!r}: only an exit code of 0 is accepted")
    if not tar_path or not os.path.isfile(tar_path):
        raise Refused("source tarball is not available, so code identity cannot be checked")
    tar_bytes = _rb(tar_path)
    if sha_bytes(tar_bytes) != be.get("sourceDigest"):
        raise Refused("source tarball sha256 does not match the digest orx recorded: the snapshot was altered")
    with tarfile.open(tar_path) as tf:
        tracked = sorted(m.name for m in tf.getmembers() if m.isfile())
    out_sub = "outputs" if export_dir else "repo"
    result = read(result_file, out_sub)
    if result is None:
        raise Refused(f"result file {result_file!r} not found in the run directory")
    outputs = []
    if export_dir:
        names = sorted(os.listdir(os.path.join(base, "outputs")))
    else:
        names = sorted(os.listdir(os.path.join(base, "repo")))
    for n in names:
        if n not in tracked:                                           # produced by the run, not in the snapshot
            b = read(n, out_sub)
            outputs.append({"path": n, "sha256": sha_bytes(b), "bytes": len(b)})
    log = read("log") or b""
    return {
        "run_id": run["id"], "experiment_id": run["experimentId"], "project_id": run["projectId"],
        "status": run["status"], "command": run["command"], "commit_sha": run.get("commitSha"),
        "created_ms": run["createdAt"], "ended_ms": run.get("endedAt"),
        "backend_kind": be.get("kind"), "source_tar_sha256": be["sourceDigest"], "source_tar_bytes": be.get("sourceSize"),
        "source_files": tracked, "exit_code_file": 0, "db_exit_code": run.get("exitCode"),
        "orx_version": health.get("version"), "result_file": result_file, "result_sha256": sha_bytes(result),
        "outputs": outputs, "log_sha256": sha_bytes(log), "log_bytes": len(log),
    }


def export_run(*, api: str, run_id: str, out_dir: str) -> str:
    """Write a portable, path-scrubbed export (run.json, health.json, exit_code, log, outputs/, source.tar)."""
    run = _get(f"{api}/api/runs/{run_id}")
    health = _get(f"{api}/api/health")
    be = run["run"]["backend"]
    os.makedirs(os.path.join(out_dir, "outputs"), exist_ok=True)
    src = be["jobId"]
    with tarfile.open(be["sourcePath"]) as tf:
        tracked = {m.name for m in tf.getmembers() if m.isfile()}
    for name in ("exit_code", "log"):
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(_rb(os.path.join(src, name)))
    for n in os.listdir(os.path.join(src, "repo")):
        p = os.path.join(src, "repo", n)
        if n not in tracked and os.path.isfile(p):
            with open(os.path.join(out_dir, "outputs", n), "wb") as fh:
                fh.write(_rb(p))
    with open(os.path.join(out_dir, "source.tar"), "wb") as fh:
        fh.write(_rb(be["sourcePath"]))
    for k in ("jobId", "sourcePath"):                                   # local absolute paths do not travel
        be[k] = "<local path withheld>"
    for name, obj in (("run.json", run), ("health.json", health)):
        with open(os.path.join(out_dir, name), "w") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
    return out_dir



def read_store_run(*, store_dir: str, run_id: str) -> dict:
    """Read one run from a live OpenResearch STORE (read-only sqlite + run directory + snapshot tarball).

    Verifies: status done, run-directory exit_code == 0, snapshot tarball sha256 == recorded digest. Reports the
    snapshot's file digests and the run log's digest and its ORX_RESULT_JSON line. Local absolute paths are read,
    used and never returned.
    """
    db = sqlite3.connect(f"file:{os.path.join(store_dir, 'orx.db')}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    row = db.execute("select * from runs where id=?", (run_id,)).fetchone()
    if row is None:
        raise Refused(f"run {run_id!r} is not in this store")
    be = json.loads(row["backend_json"])
    exp = db.execute("select title, description, branch_name, parent_experiment_id from local_experiments where id=?",
                     (row["experiment_id"],)).fetchone()
    if row["status"] != "done":
        raise Refused(f"run status is {row['status']!r}, not 'done'")
    rd = os.path.join(store_dir, "local-runs", run_id)
    exit_raw = _rb(os.path.join(rd, "exit_code")) if os.path.isfile(os.path.join(rd, "exit_code")) else None
    if exit_raw is None or exit_raw.strip() != b"0":
        raise Refused(f"exit_code file is {exit_raw!r}: only 0 is accepted")
    digest = be.get("sourceDigest")
    tar_path = os.path.join(store_dir, "source-snapshots", f"{digest}.tar")      # located by digest, not by the recorded path
    if not os.path.isfile(tar_path) or sha_bytes(_rb(tar_path)) != digest:
        raise Refused("source tarball missing or its sha256 differs from the digest orx recorded")
    snapshot_files = {}
    with tarfile.open(tar_path) as tf:
        for m in tf.getmembers():
            if m.isfile():
                snapshot_files[m.name] = sha_bytes(tf.extractfile(m).read())
    log = _rb(os.path.join(rd, "log"))
    m = re.search(rb"^ORX_RESULT_JSON (\{.*\})$", log, re.M)
    cmd, scrubbed = scrub_paths(row["command"])
    return {
        "run_id": row["id"], "experiment_id": row["experiment_id"], "project_id": row["project_id"], "status": row["status"],
        "command": cmd, "command_scrubbed": scrubbed, "command_verbatim_sha256": sha_bytes(row["command"].encode()),
        "commit_sha": row["commit_sha"], "created_ms": row["created_at"], "ended_ms": row["ended_at"],
        "backend_kind": be.get("kind"), "source_tar_sha256": digest, "source_tar_bytes": be.get("sourceSize"),
        "snapshot_files": snapshot_files, "exit_code_file": 0, "db_exit_code": row["exit_code"],
        "experiment_title": exp["title"] if exp else None, "experiment_description": exp["description"] if exp else None,
        "orx_version": None, "orx_version_note": "not stored in the run record; take it from the producer's own receipt",
        "log_sha256": sha_bytes(log), "log_bytes": len(log),
        "log_result_json": json.loads(m.group(1)) if m else None,
        "outputs": [], "result_file": None, "result_sha256": None,
    }


def to_evidence_draft(facts: dict, *, target: dict, author: dict, namespace: str = "node-a",
                      issuer: str = "importer", kind: str = "simulated", replay: dict | None = None,
                      evidence_id: str | None = None, visibility: str = "public", artifacts: list | None = None,
                      link_checks: list | None = None, primary: dict | None = None, relation: str = "unspecified",
                      produced_by: dict | None = None) -> dict:
    """Build a PROPOSED Evidence draft. `target` is an exact Ref {namespace, kind, id, version}.

    `author` is the run author's own declaration: {assumptions, limitations, uncertainty, source_dependence,
    method, context}. Whatever the author leaves out is recorded as absent, never filled in.
    """
    if kind not in ALLOWED_KINDS:
        raise Refused(f"evidence_kind {kind!r} refused: a computational run may be 'simulated' or 'predicted' only")
    if set(target) != {"namespace", "kind", "id", "version"} or not re.fullmatch(r"[0-9a-f]{64}", target["version"]):
        raise Refused("target must be an exact Ref with a 64-hex version digest")
    f = facts
    if primary is None:                                   # default: the primary result is a file in the run directory
        primary = {"locator": f"orx-run:{f['run_id']}/{f['result_file']}", "sha256": f["result_sha256"]}
    command = f["command"]
    origin = {}
    def put(field, value, who):
        origin[field] = who
        return value

    method = author.get("method") or (
        f"Local OpenResearch run (backend {f['backend_kind']}) of the command `{command}` on the code snapshot "
        f"git:{f['commit_sha']} (source tar sha256 {f['source_tar_sha256']}). The method description is the run's own command, not an "
        "author-written protocol.")
    context = author.get("context") or "No context was declared by the run author; OpenResearch stores only a title and description."
    undeclared = "Not declared by the run author; OpenResearch records no uncertainty."
    payload = {
        "target": put("target", target, "author"),
        "evidence_kind": put("evidence_kind", kind, "author"),
        "source": put("source", {
            "uri": None,                                                           # nothing resolvable by others
            "locator": primary["locator"],
            "source_version": f"git:{f['commit_sha']}; source-tar-sha256:{f['source_tar_sha256']}",
            "content_sha256": primary["sha256"], "content_available": False,       # no licence stated => digest only
            "access": ("Local-only: held in the producing machine's OpenResearch store; not published or served. "
                       "Only the digest of the result file is carried. OpenResearch (MIT) licenses its software, not "
                       "the content of a user's runs, so no licence for this content is stated."),
            "license": None}, "adapter+orx"),
        "created_time": put("created_time", {"value": iso_utc(f["ended_ms"]), "basis": "witnessed"}, "orx"),
        "retrieved_time": put("retrieved_time", {"value": iso_utc(), "basis": "witnessed"}, "adapter"),
        "method": put("method", method, "author" if author.get("method") else "orx"),
        "context": put("context", context, "author" if author.get("context") else "absent"),
        "assumptions": put("assumptions", list(author.get("assumptions") or []), "author" if author.get("assumptions") else "absent"),
        "provenance": put("provenance", {
            "system": "alphaXiv/OpenResearch orx", "orx_version": f["orx_version"], "openresearch_source_read": OPENRESEARCH_PIN,
            "run_id": f["run_id"], "experiment_id": f["experiment_id"], "project_id": f["project_id"],
            "commit_sha": f["commit_sha"], "source_tar_sha256": f["source_tar_sha256"], "command": command,
            "command_scrubbed": f.get("command_scrubbed", False), "command_verbatim_sha256": f.get("command_verbatim_sha256"),
            "artifacts": artifacts or [], "link_checks": link_checks or [],
            "backend_kind": f["backend_kind"], "status": f["status"], "exit_code_file": f["exit_code_file"],
            "db_exit_code": f["db_exit_code"], "outputs": f["outputs"], "log_sha256": f["log_sha256"],
            "time_witness": "ended_at is the local orx supervisor's clock on the producing machine; uncorroborated",
            "replay": replay or {"performed": False},
            "field_origin": origin,
            "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION}}, "adapter+orx"),
        "source_dependence": put("source_dependence", author.get("source_dependence") or {"declared": False}, "author" if author.get("source_dependence") else "absent"),
        "uncertainty": put("uncertainty", author.get("uncertainty") or undeclared, "author" if author.get("uncertainty") else "absent"),
        "limitations": put("limitations", MECHANICAL_LIMITATIONS + (EXTERNAL_IO_LIMITATIONS if artifacts else [])
                           + list(author.get("limitations") or []), "adapter+author"),
        "local_id": put("local_id", f["run_id"], "orx"),
        "provider_assessment": put("provider_assessment", None, "absent"),
    }
    payload["provenance"]["field_origin"] = origin
    # Typed core fields (frontier-core 1b329cc). Omitted when default so a plain import keeps the original payload bytes.
    if relation != "unspecified":
        payload["relation"] = put("relation", relation, "author")
    if produced_by is not None:
        payload["produced_by"] = put("produced_by", produced_by, "author")
    if artifacts:
        from .artifacts import to_artifact_ref
        payload["artifacts"] = put("artifacts", [to_artifact_ref(a) for a in artifacts], "adapter")
    bad = find_abs_paths(payload)
    if bad:
        raise Refused(f"evidence payload would contain absolute local paths at {bad}")
    eid = evidence_id or f"orx-run-{f['run_id']}"
    return {"namespace": namespace, "kind": "Evidence", "id": eid, "issuer": issuer,
            "source_uri": "urn:frontier:adapter:openresearch-local-run",   # import-path label, not an identifier of the run
            "visibility": visibility, "predecessor": None, "payload": payload}


def to_action_draft(facts: dict, *, target: dict, inputs: list[dict], input_digests: dict, namespace: str = "node-a",
                    issuer: str = "importer", action_id: str | None = None, acceptance_criteria: list | None = None,
                    environment_note: str | None = None, visibility: str = "public") -> dict:
    """A PROPOSED Action record describing an analysis that an OpenResearch run reports as completed.

    It is a record of what was run, with `inputs` pinning the exact Claim versions it used (`uses` edges). It does not
    prove the action ran: the run receipt and the output artifacts, joined by the Evidence that points back here, do.
    `cache_key` carries the eight required dimensions; `environment` states plainly that OpenResearch did not record it.
    """
    from frontier.models import POLICY
    f = facts
    ck = {
        "target": target["version"],
        "input": "; ".join(f"{k} sha256:{v}" for k, v in sorted(input_digests.items()))[:1000],
        "code": f"git:{f['commit_sha']}; orx snapshot sha256:{f['source_tar_sha256']}",
        "model": "none: deterministic analysis, no language model used",
        "environment": environment_note or "NOT RECORDED by OpenResearch (interpreter, package versions, hardware unrecorded)",
        "parameters": f["command"][:1000],
        "scope": "analysis step of a finished sweep, as run on the OpenResearch local backend (not hosted compute, no GPU)",
        "acceptance_policy": POLICY,
    }
    payload = {
        "target": target,
        "title": f"Executed analysis (supervisor-reported done): {f.get('experiment_title') or f['run_id']}"[:3000],
        "acceptance_criteria": acceptance_criteria or [
            "A clean re-execution from the recorded code and the digest-pinned inputs reproduces the recorded output byte-for-byte.",
            "Every link check between the run log, its inputs and its outputs passes, with a mutation control that changes the output."],
        "required_capabilities": ["python3 with the packages the analysis imports (versions NOT recorded by OpenResearch)"],
        "cost_stop_bounds": f"Actual: {max(0, (f['ended_ms'] - f['created_ms']) // 1000)} s wall on one local CPU host; no GPU, no paid model calls. "
                            "Stop bound: the run's own completion; there was no separate budget.",
        "cache_key": ck,
        "inputs": inputs,
    }
    bad = find_abs_paths(payload)
    if bad:
        raise Refused(f"action payload would contain absolute local paths at {bad}")
    return {"namespace": namespace, "kind": "Action", "id": action_id or f"orx-run-{f['run_id']}-action", "issuer": issuer,
            "source_uri": "urn:frontier:adapter:openresearch-local-run", "visibility": visibility, "predecessor": None, "payload": payload}
