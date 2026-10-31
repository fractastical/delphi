"""Mapping with Evidence v2: the video, poster, manifest and render code linked as typed artifacts.

Wraps `frontier_mapping.build()` without touching it (it is part of the replay's code hash, which a committed
receipt carries). The simulated Evidence gets a successor whose `predecessor` is the exact v1 version; v1 is kept,
frozen, in `superseded_versions`. Every v1 artifact is preserved in v2, so the replay's model, code and CSV hashes
are unchanged. `records` holds the head set, so a loader that refuses two versions of one id sees one.

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
V2_CREATED_AT = "2026-10-31T19:25:00+00:00"   # declared when this version was written; not witnessed
EVIDENCE_ID = "orx-run-simulated-evidence"
REPO_LABEL = "kganjam/delphi-frontier"
LIMITATION = ("The video, poster and manifest were rendered from the replay CSVs by connectors/biomodels/render.py after the replay. "
              "They were not produced by the replay Action itself (produced_by still names the Action that made the CSVs), "
              "they plot two numbers per cell against model time, and they do not show cell shape, tissue or a fin.")
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


def evidence_v2(v1: dict) -> dict:
    m = fm._frontier()
    rel = "connectors/biomodels/video"
    manifest = json.loads((VIDEO_DIR / "delta_notch_replay_manifest.json").read_text())
    render_py = fm.PACKAGE / "render.py"
    if manifest["render"]["code_sha256"] != hashlib.sha256(render_py.read_bytes()).hexdigest():
        raise SystemExit("render.py changed since the video was made; re-render before building the mapping")
    for key in ("video", "poster"):
        if hashlib.sha256((VIDEO_DIR / manifest[key]["file"]).read_bytes()).hexdigest() != manifest[key]["sha256"]:
            raise SystemExit(f"{manifest[key]['file']} does not match its manifest")
    pairs = [
        _entry("output", "video/mp4", f"{rel}/{manifest['video']['file']}", "simulation video rendered from the replay CSVs; plots two numbers per cell against model time"),
        _entry("output", "image/png", f"{rel}/{manifest['poster']['file']}", "still poster, last CSV row; not a separate simulation"),
        _entry("log", "application/json", f"{rel}/delta_notch_replay_manifest.json", "video manifest: input CSV/model/code hashes, time mapping, captions"),
        _entry("code", "text/x-python", "connectors/biomodels/render.py", "the renderer that drew the video from the CSVs"),
    ]
    payload = json.loads(json.dumps(v1["payload"]))
    have = {(a["sha256"], a["role"]) for a in payload["artifacts"]}
    new_refs = [ref for _, ref in pairs if (ref["sha256"], ref["role"]) not in have]
    payload["artifacts"] = payload["artifacts"] + new_refs
    prov = payload["provenance"]
    prov["render_artifacts"] = [rich for rich, _ in pairs]
    prov["replay_hashes_preserved"] = {"model_sha256": manifest["inputs"]["model_sha256"], "replay_code_sha256": manifest["inputs"]["replay_code_sha256"],
                                       "receipt_sha256": manifest["inputs"]["receipt_sha256"], "csv": {k: v["sha256"] for k, v in manifest["inputs"]["csv"].items()}}
    prov["field_origin"]["render_artifacts"] = "author (committed files, located by git commit)"
    payload["limitations"] = payload["limitations"] + [LIMITATION]
    draft = {"namespace": v1["namespace"], "kind": "Evidence", "id": v1["id"], "issuer": v1["issuer"], "source_uri": v1["source_uri"],
             "visibility": v1["visibility"], "predecessor": v1["version"], "payload": payload}
    return m.make_record(m.Draft.model_validate(draft), created_at=V2_CREATED_AT)


def build() -> dict:
    m = fm._frontier()
    doc = fm.build()
    by_id = {r["id"]: r for r in doc["records"]}
    v1 = by_id[EVIDENCE_ID]
    v2 = evidence_v2(v1)
    by_id[EVIDENCE_ID] = v2
    doc["records"] = list(by_id.values())
    doc["superseded_versions"] = [v1]
    doc["chains"] = [{"namespace": v2["namespace"], "kind": "Evidence", "id": EVIDENCE_ID, "versions": [v1["version"], v2["version"]], "head": v2["version"],
                      "change": "v2 adds the video, poster, manifest and render.py as typed artifacts and one limitation; every v1 artifact is kept"}]
    doc["edges"] = [{"type": t, "from": r["id"], "to": ref["id"], "to_version": ref["version"]} for r in by_id.values() for t, ref in m.references(r)]
    doc["mapping_schema"] = "biomodels-frontier-mapping-0.2 (connector-local; no root schema changed)"
    doc["import_note"] = ("`records` is the head set (Evidence = v2). Importing a different version of an id that already has a head records a fork in the store, and "
                          "Store.submit advances a head only with the exact predecessor from an authenticated actor. So import `records` into an empty id, "
                          "or submit v2 on top of an already-imported v1; do not import both versions as heads. The dangling predecessor of v2 (v1) is in `superseded_versions`.")
    render_items = v2["payload"]["provenance"]["render_artifacts"]
    doc["artifacts"] = doc["artifacts"] + [{"role": "simulation-video", "path": r["path"], "sha256": r["sha256"], "in_repo": True, "evidence_kind": "simulated"} for r in render_items]
    return doc


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    out.write_text(json.dumps(doc, indent=1, sort_keys=True))
    ev = [r for r in doc["records"] if r["id"] == EVIDENCE_ID][0]
    print(f"wrote {out.name}: {len(doc['records'])} head records, {len(doc['superseded_versions'])} superseded, Evidence v2 {ev['version'][:12]} <- {ev['predecessor'][:12]}, {len(ev['payload']['artifacts'])} artifacts")
