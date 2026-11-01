"""Mapping with the rendering as its own Action and a context_only Evidence.

Wraps `frontier_mapping.build()` without touching it (that module is in the replay's code hash, which a committed
receipt carries). The replay Evidence is returned exactly as `build()` made it: same version, same artifacts, same
scientific content. The video is not attached to it, because it was produced later, by `render.py`, not by the replay
Action. Instead:

  render Action   targets the model-behaviour Claim; inputs = the replay Evidence (exact version) and that Claim.
  render Evidence relation context_only; produced_by the render Action; artifacts = video, poster (output),
                  manifest (log), render.py (code).

Same operator wrote and rendered everything; no independent review exists. An earlier draft chained a v2 onto the replay
Evidence; it was never imported, is withdrawn, and is recorded in `withdrawn_versions` so the disagreement stays visible.

  PYTHONPATH=. python3 -m connectors.biomodels.mapping_v2
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from . import frontier_mapping as fm

VIDEO_DIR = fm.PACKAGE / "video"
REPLAY_EVIDENCE_ID = "orx-run-simulated-evidence"
RENDER_ACTION_ID, RENDER_EVIDENCE_ID = "biomodels-1047-render", "biomodels-1047-render-evidence"
REPO_LABEL = "kganjam/delphi-frontier"
# Draft chained onto the replay Evidence (predecessor = replay Evidence), never imported; replaced by the design below.
WITHDRAWN = [{"kind": "Evidence", "id": REPLAY_EVIDENCE_ID, "version": "54c33964eb17ed52b61195ac9ffb0bbea2c9f8be9263fd635c67b9932baba586",
              "predecessor": "3be2c96d3a3eed25273ca5b9393ae883e8feae5a2984ab55c47d994e17da3442", "in_commit": "873a8ab9c32a",
              "reason": "typed lineage was wrong: it pointed the video's produced_by at the replay Action, which did not make the video; a limitation could not fix that. Not imported; do not import."}]
SAME_OPERATOR = ("The same operator (biomodels-worker, one session) wrote the model replay, ran the orx repeat, wrote the renderer and produced the video. "
                 "No independent review or replication exists.")
OUTPUT = fm.PACKAGE / "mapping" / f"{fm.ACCESSION}.mapping.json"


def _blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _entry(role: str, media: str, relpath: str, what: str) -> tuple[dict, dict]:
    """(rich entry, typed ArtifactRef) for a committed file, located by the last commit that touched it."""
    root = fm.PACKAGE.parents[1]
    data = (root / relpath).read_bytes()
    commit = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H", "--", relpath], capture_output=True, text=True, check=True).stdout.strip()
    if not commit:
        raise SystemExit(f"{relpath} is not committed; commit before building the mapping")
    blob = subprocess.run(["git", "-C", str(root), "cat-file", "blob", f"{commit}:{relpath}"], capture_output=True, check=True).stdout
    if blob != data:
        raise SystemExit(f"{relpath} differs from {commit}")
    sha = hashlib.sha256(data).hexdigest()
    locator = f"git:{REPO_LABEL}@{commit}:{relpath}"
    rich = {"role": role, "path": relpath, "sha256": sha, "git_blob": _blob_id(data), "bytes": len(data), "content_available": False, "license": None,
            "locator": locator, "git_commit": commit, "note": what}
    ref = {"title": f"{role}: {relpath} [{locator}] - {what}"[:3000], "uri": "urn:sha256:" + sha, "sha256": sha, "byte_size": len(data),
           "media_type": media, "role": role, "availability": "referenced", "license": None}
    return rich, ref


def _render_records(replay_ev: dict, claim_b: dict, manifest: dict, pairs: list) -> tuple[dict, dict]:
    m = fm._frontier()
    root = fm.PACKAGE.parents[1]
    render_sha = hashlib.sha256((fm.PACKAGE / "render.py").read_bytes()).hexdigest()
    stamp = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%cI", "--", "connectors/biomodels/video/delta_notch_replay.mp4"], capture_output=True, text=True, check=True).stdout.strip()
    ref_ev, ref_claim = m.ref(replay_ev), m.ref(claim_b)
    csv = manifest["inputs"]["csv"]
    action = {"namespace": fm.NAMESPACE, "kind": "Action", "id": RENDER_ACTION_ID, "issuer": fm.ISSUER, "source_uri": f"urn:frontier:connector:biomodels:{fm.ACCESSION}",
              "visibility": "public", "predecessor": None, "payload": {
        "target": ref_claim, "inputs": [ref_ev, ref_claim],
        "title": "Render the replay CSVs as a captioned two-cell Delta-Notch video and poster (presentation only)",
        "acceptance_criteria": [
            "Every input CSV matches the replay receipt's sha256 before any frame is drawn; a mismatch is refused.",
            "A second render gives the same raw-frame sha256 (the same MP4 bytes only on the same ffmpeg build).",
            "The video is 10-20 s and under 8 MB, its manifest passes the published schema, and every frame carries the simulation and non-dimensional captions."],
        "required_capabilities": [f"python 3.13 with matplotlib {manifest['render']['matplotlib']} and numpy {manifest['render']['numpy']}", "/usr/bin/ffmpeg (libx264) and ffprobe",
                                  "the committed replay CSVs"],
        "cost_stop_bounds": "Observed in the authoring session, not recorded in a receipt: about 90 s wall per full render, 2 ffmpeg threads, under a systemd scope "
                            "TasksMax=128 MemoryMax=4G MemorySwapMax=0 RuntimeMaxSec=600; no GPU, no paid model. Stop bound: the scope's 600 s.",
        "cache_key": {"target": claim_b["version"],
                      "input": f"replay evidence {replay_ev['version']}; model sha256:{manifest['inputs']['model_sha256']}; "
                               + "; ".join(f"{k} sha256:{v['sha256']}" for k, v in sorted(csv.items())),
                      "code": f"connectors/biomodels/render.py sha256:{render_sha}",
                      "model": "none: plotting of existing CSV rows, no simulation and no language model",
                      "environment": f"matplotlib {manifest['render']['matplotlib']}; numpy {manifest['render']['numpy']}; python {manifest['render']['python']}; {manifest['render']['ffmpeg'][:80]}; 2 threads",
                      "parameters": f"{manifest['time_mapping']['fps']} fps; {manifest['time_mapping']['motion_frames']} motion + {manifest['time_mapping']['hold_frames']} hold frames; "
                                    f"{manifest['dimensions']['width']}x{manifest['dimensions']['height']}; nearest CSV row, no interpolation",
                      "scope": "presentation of existing replay output; adds no scientific result; two numbers per cell, no cell shape, tissue or fin",
                      "acceptance_policy": m.POLICY}}}
    action_rec = m.make_record(m.Draft.model_validate(action), created_at=fm.CREATED_AT)
    evidence = {"namespace": fm.NAMESPACE, "kind": "Evidence", "id": RENDER_EVIDENCE_ID, "issuer": fm.ISSUER,
                "source_uri": f"urn:frontier:connector:biomodels:{fm.ACCESSION}", "visibility": "public", "predecessor": None, "payload": {
        "target": ref_claim, "evidence_kind": "simulated", "relation": "context_only", "produced_by": m.ref(action_rec),
        "source": {"uri": None, "locator": "connectors/biomodels/video/delta_notch_replay_manifest.json", "source_version": pairs[2][0]["locator"],
                   "content_sha256": pairs[2][0]["sha256"], "content_available": False,
                   "access": "Committed in the delphi-frontier repository (private); referenced by digest only. Not hosted by this record.", "license": None},
        "created_time": {"value": stamp, "basis": "declared"}, "retrieved_time": {"value": stamp, "basis": "declared"},
        "method": "connectors/biomodels/render.py drew the three replay CSVs (each checked against the replay receipt's sha256) with matplotlib and encoded them with ffmpeg; "
                  "the run's own record is the video manifest (hashes, time mapping, tool versions); no separate run receipt with command, exit status or timings exists.",
        "context": "Presentation of the replay output, linked to the replay Evidence by the render Action's inputs. It supplies no new scientific result, does not revise the replay Evidence, "
                   "and is not itself a simulation: nothing was computed except the drawing.",
        "assumptions": ["The replay CSVs are the replay Evidence's outputs (hashes checked).", "Time is shown linearly in model time with the nearest CSV row; non-dimensional."],
        "provenance": {"render_artifacts": [rich for rich, _ in pairs], "replay_evidence": ref_ev, "frames_sha256": manifest["render"]["frames_sha256"],
                       "video_manifest_schema": "connectors/biomodels/video/delta_notch_replay_manifest.schema.json",
                       "run_receipt": "none beyond the video manifest (no command, exit code or timing record was written for the render)"},
        "source_dependence": {"declared": True, "depends_on": [f"replay Evidence {replay_ev['version']}", f"model sha256 {manifest['inputs']['model_sha256']}"], "independent_of_author": False},
        "uncertainty": "Not applicable to a plot; the plotted values carry the replay's numerical agreement only (see the replay Evidence). Parameter uncertainty was not studied.",
        "limitations": [SAME_OPERATOR, "context_only: it adds nothing to the support for the Claim.", "It plots two numbers per cell against model time; it does not show cell shape, tissue, a fin or any flying-fish structure.",
                        "Model time and concentrations are non-dimensional; the model declares no unit it uses.", "The MP4 bytes are only reproducible on the same ffmpeg build; the raw-frame hash depends only on the drawing.",
                        "Parameter provenance of the model is unknown and flying-fish applicability is unknown and unattempted."],
        "artifacts": [ref for _, ref in pairs]}}
    return action_rec, m.make_record(m.Draft.model_validate(evidence), created_at=fm.CREATED_AT)


def build() -> dict:
    m = fm._frontier()
    doc = fm.build()
    by_id = {r["id"]: r for r in doc["records"]}
    replay_ev, claim_b = by_id[REPLAY_EVIDENCE_ID], by_id["biomodels-1047-model-behaviour"]
    rel = "connectors/biomodels/video"
    manifest = json.loads((VIDEO_DIR / "delta_notch_replay_manifest.json").read_text())
    render_py = fm.PACKAGE / "render.py"
    if manifest["render"]["code_sha256"] != hashlib.sha256(render_py.read_bytes()).hexdigest():
        raise SystemExit("render.py changed since the video was made; re-render before building the mapping")
    for key in ("video", "poster"):
        if hashlib.sha256((VIDEO_DIR / manifest[key]["file"]).read_bytes()).hexdigest() != manifest[key]["sha256"]:
            raise SystemExit(f"{manifest[key]['file']} does not match its manifest")
    if manifest["inputs"]["model_sha256"] != fm.MODEL_SHA256:
        raise SystemExit("video manifest names a different model")
    pairs = [
        _entry("output", "video/mp4", f"{rel}/{manifest['video']['file']}", "simulation video rendered from the replay CSVs; plots two numbers per cell against model time"),
        _entry("output", "image/png", f"{rel}/{manifest['poster']['file']}", "still poster, last CSV row; not a separate simulation"),
        _entry("log", "application/json", f"{rel}/delta_notch_replay_manifest.json", "video manifest: input CSV/model/code hashes, time mapping, captions"),
        _entry("code", "text/x-python", "connectors/biomodels/render.py", "the renderer that drew the video from the CSVs"),
    ]
    action_rec, evidence_rec = _render_records(replay_ev, claim_b, manifest, pairs)
    doc["records"] = doc["records"] + [action_rec, evidence_rec]
    doc["edges"] = [{"type": t, "from": r["id"], "to": ref["id"], "to_version": ref["version"]} for r in doc["records"] for t, ref in m.references(r)]
    doc["mapping_schema"] = "biomodels-frontier-mapping-0.2 (connector-local; no root schema changed)"
    doc["separation"]["rendering"] = [RENDER_ACTION_ID, RENDER_EVIDENCE_ID]
    doc["separation"]["rendering_note"] = "presentation of the replay output; context_only; adds no scientific result"
    doc["withdrawn_versions"] = WITHDRAWN
    doc["authorship"] = {"operator": fm.ISSUER, "note": SAME_OPERATOR}
    doc["import_note"] = ("9 head records, all new ids, no predecessor chain: import them together. The replay Evidence is byte-identical to the one in the previous mapping "
                          "(version 3be2c96d3a3e...), so an import plan that already holds it stays valid. Do not import `withdrawn_versions`.")
    doc["artifacts"] = doc["artifacts"] + [{"role": "simulation-video", "path": r["path"], "sha256": r["sha256"], "in_repo": True, "evidence_kind": "simulated"}
                                           for r in evidence_rec["payload"]["provenance"]["render_artifacts"]]
    return doc


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    out.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(f"wrote {out.name}: {len(doc['records'])} head records, {len(doc['edges'])} edges, withdrawn {len(doc['withdrawn_versions'])}")
