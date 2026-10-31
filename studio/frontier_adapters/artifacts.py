"""Artifact pointers, a downloadable-style manifest, and the absolute-path rule.

An artifact is referenced by what lets a stranger check it: a git repo + immutable commit + path, the file's sha256
AND its `git hash-object` id (CONTRIBUTING-VERIFICATION rule 2), and its size. Bytes are never embedded here.

Absolute-path rule: no record, manifest or draft may contain a path that only exists on the producing machine
(/home, /tmp, /data, /Users, drive letters). `scrub_paths` replaces them with a marker and `find_abs_paths` is the
control that must come back empty on everything we emit.
"""
from __future__ import annotations

import hashlib
import re
import subprocess

from .common import sha_bytes

ABS = re.compile(r"(?<![A-Za-z0-9_.])(?:/(?:home|tmp|data|Users|var|opt|root|mnt|srv)/[^\s'\"`;,)\]}]*|[A-Za-z]:\\[^\s'\"`;,)\]}]*)")
MARK = "<abs-path-withheld>"


def scrub_paths(s: str) -> tuple[str, bool]:
    out = ABS.sub(MARK, s)
    return out, out != s


def find_abs_paths(obj, _path="$") -> list[str]:
    """Locations (JSON paths) of strings that still contain an absolute local path."""
    found = []
    if isinstance(obj, str):
        if ABS.search(obj):
            found.append(_path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found += find_abs_paths(k, f"{_path}.{k}<key>") + find_abs_paths(v, f"{_path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            found += find_abs_paths(v, f"{_path}[{i}]")
    return found


def git_blob(repo: str, commit: str, path: str) -> bytes:
    """Bytes of `path` at an immutable `commit`, read-only (git cat-file); the working tree is never touched."""
    r = subprocess.run(["git", "-C", repo, "cat-file", "blob", f"{commit}:{path}"], capture_output=True, timeout=60)
    if r.returncode != 0:
        raise FileNotFoundError(f"{commit}:{path} not found in {repo.split('/')[-1]}: {r.stderr.decode()[:120]}")
    return r.stdout


def git_blob_id(data: bytes) -> str:
    """`git hash-object` of a blob, computed without git: sha1('blob <n>\\0' + data)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def entry(role: str, data: bytes, *, path: str, repo_label: str | None = None, commit: str | None = None,
          note: str | None = None, where: str | None = None) -> dict:
    """One artifact pointer. `where` describes a non-git location in words (never an absolute path)."""
    e = {"role": role, "path": path, "sha256": sha_bytes(data), "git_blob": git_blob_id(data), "bytes": len(data),
         "content_available": False, "license": None}
    if repo_label and commit:
        e["locator"] = f"git:{repo_label}@{commit}:{path}"
        e["git_commit"] = commit
    elif where:
        e["locator"] = where
    if note:
        e["note"] = note
    return e


def manifest(run_ref: dict, artifacts: list[dict], *, proposed_site_path: str) -> dict:
    """The run artifact manifest root asked for. `hosted` is False until root serves it: no URL is claimed that
    does not resolve. Bytes are not included and no licence is asserted for them."""
    m = {
        "schema": "frontier-artifact-manifest-0.1",
        "run": run_ref,
        "artifacts": artifacts,
        "bytes_included": False,
        "licence_note": "No licence is stated for these artifacts' content. The OpenResearch software licence (MIT) is not "
                        "evidence of a licence for a user's run content and is not used as one. Digest and locator only.",
        "hosting": {"proposed_site_path": proposed_site_path, "hosted": False,
                    "note": "Proposed path under the site's /artifacts/ tree; set Source.uri to the served URL only after it resolves."},
    }
    bad = find_abs_paths(m)
    if bad:
        raise ValueError(f"manifest contains absolute local paths at {bad}")
    return m


_MEDIA = {"json": "application/json", "jsonl": "application/x-ndjson", "md": "text/markdown", "py": "text/x-python",
          "tar": "application/x-tar", "txt": "text/plain", "log": "text/plain",
          # media: typed so a reader or a media resolver can tell a video from a mesh; the type says nothing about whether the bytes are served
          "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
          "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml", "glb": "model/gltf-binary", "gltf": "model/gltf+json", "stl": "model/stl",
          "npz": "application/x-npz", "csv": "text/csv", "html": "text/html"}
# our roles -> the store's closed ArtifactRef.role set
_ROLE = {"input": "input", "output": "output", "report": "output", "protocol": "protocol", "receipt": "log", "log": "log",
         "code": "code", "code_snapshot": "code", "environment": "environment", "certificate": "certificate", "geometry": "geometry"}


def to_artifact_ref(e: dict) -> dict:
    """Rich entry -> the store's typed `ArtifactRef` payload.

    The pointer is `urn:sha256:<digest>` with availability `referenced`: the bytes are not at any public HTTPS URL we can
    vouch for, and a digest in a record is not a byte verification. Where the bytes live is said in the title, in words.
    Switch `uri` to the served HTTPS URL, and availability to `downloadable`, only after the site really serves the file
    and an owner has stated a licence.
    """
    ext = e["path"].rsplit(".", 1)[-1] if "." in e["path"].rsplit("/", 1)[-1] else "txt"
    where = e.get("locator") or e["path"]
    ref = {"title": f"{e['role']}: {e['path']} [{where}]"[:3000], "uri": "urn:sha256:" + e["sha256"], "sha256": e["sha256"],
           "byte_size": int(e["bytes"]), "media_type": _MEDIA.get(ext, "application/octet-stream"),
           "role": _ROLE[e["role"]], "availability": "referenced", "license": e.get("license")}
    return ref
