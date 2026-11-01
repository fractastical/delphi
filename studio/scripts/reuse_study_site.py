"""Publisher adapter for reuse-study visuals: verify a manifest's input and output hashes, then offer only verified media.

    build(ins, out, root, manifest_path=MANIFEST, expected_sha256=None) -> {"visuals": [card, ...], "manifest_href": str}

`ins` is build_site's Inputs (read(rel) -> bytes, remembered with its sha256); `out` is its output mapping ("@<site path>" keys);
`root` is the checkout. Nothing is scanned, run or fetched. A visual is offered only when EVERY source, renderer and media file
named by the manifest exists inside the allowlist and matches its declared sha256 and size; one mismatch raises and nothing is
added to `out`. The adapter never invents a result: it publishes what the manifest declares, and a study with no manifest entry
shows nothing. It accepts a future formal (for example oxygen-diffusion) artifact the same way: add its source prefix below.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path, PurePosixPath

MANIFEST = "artifacts/reuse-study-visuals/manifest.json"
MEDIA_PREFIX = "artifacts/reuse-study-visuals/"
MEDIA_PREFIXES = (MEDIA_PREFIX, "artifacts/epithelial/media/")
SOURCE_PREFIXES = ("artifacts/voxel-actuation/", "artifacts/oxygen-diffusion-rule/", "artifacts/epithelial/", "docs/epithelial-repair-card.md")   # exact committed producer outputs only
RENDERER_PREFIXES = ("engineering/reuse_visuals/", "engineering/epithelial/")
DOWNLOAD_SUFFIXES = (".json", ".md", ".txt")                    # strict text: no csv, tarball or binary is offered as a source download
MAX_DOWNLOAD_BYTES = 2_000_000
SITE_SOURCE_PREFIX = MEDIA_PREFIX + "sources/"                    # where a download whose producer path the static handler would not serve is remapped
MEDIA_SUFFIXES = (".mp4", ".gif", ".png", ".json", ".md")
MAX_MEDIA_BYTES = 20_000_000
REQUIRED = ("id", "study", "title", "evidence_kind", "labels", "caveats", "media", "sources", "renderer")


def _safe(rel: str, prefixes: tuple[str, ...], root: Path) -> str:
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or str(p) != rel or not rel.startswith(prefixes):
        raise ValueError(f"path outside the allowlist: {rel}")
    if not (root / rel).resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes the checkout: {rel}")
    return rel


def _verify(ins, item: dict, prefixes: tuple[str, ...], root: Path) -> bytes:
    rel = _safe(item["path"], prefixes, root)
    blob = ins.read(rel)
    if sha256(blob).hexdigest() != item["sha256"] or len(blob) != item["bytes"]:
        raise ValueError(f"digest or size mismatch: {rel}")
    return blob


def build(ins, out: dict, root, manifest_path: str = MANIFEST, expected_sha256: str | None = None) -> dict:
    root = Path(root)
    raw = ins.read(_safe(manifest_path, (MEDIA_PREFIX,), root))
    if expected_sha256 and sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("manifest digest changed")
    m = json.loads(raw)
    if m.get("schema") != "frontier.reuse-study-visuals/1" or not m.get("visuals"):
        raise ValueError("not a reuse-study-visuals/1 manifest")
    studies = {p["id"] for p in ins.json("site/content/projects.json")["projects"] if p.get("template") == "reuse-study"}
    staged, cards, total = {"@" + manifest_path: raw}, [], 0
    for v in m["visuals"]:
        missing = [k for k in REQUIRED if k not in v]
        if missing or v["study"] not in studies:
            raise ValueError(f"visual {v.get('id')!r}: missing {missing} or unknown study {v.get('study')!r}")
        if not v["labels"].get("model_only") and "formal" not in v["evidence_kind"].lower():
            raise ValueError("a visual must declare itself model-only or a formal artifact")
        downloads = []
        for item in v["sources"]:
            blob = _verify(ins, item, SOURCE_PREFIXES, root)
            if item.get("download"):
                if not item["path"].endswith(DOWNLOAD_SUFFIXES) or len(blob) > MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"download not allowed: {item['path']}")
                site = item.get("site_path", item["path"])
                if site != item["path"] and (not site.startswith(SITE_SOURCE_PREFIX) or not site.endswith(DOWNLOAD_SUFFIXES) or _safe(site, (SITE_SOURCE_PREFIX,), root) != site):
                    raise ValueError(f"site path not allowed: {site}")
                if item.get("errata_required") and "errata" not in v["media"]:
                    raise ValueError(f"{item['path']} is offered only beside its errata note")
                staged["@" + site] = blob
                total += len(blob)
                downloads.append({"label": PurePosixPath(site).name, "href": site, "sha256": item["sha256"], "bytes": item["bytes"], "errata_required": bool(item.get("errata_required")), "source_path": item["path"]})
        for item in v["renderer"]:
            _verify(ins, item, RENDERER_PREFIXES, root)
        hrefs = {}
        for kind, item in v["media"].items():
            if not item["path"].endswith(MEDIA_SUFFIXES):
                raise ValueError(f"media type not allowed: {item['path']}")
            blob = _verify(ins, item, MEDIA_PREFIXES, root)
            total += len(blob)
            staged["@" + item["path"]] = blob
            hrefs[kind + "_href"] = item["path"]
        cards.append({"video_href": None, "poster_href": None, "figure_href": None, "summary": v.get("summary"), "downloads": downloads, "source_hrefs": [d["href"] for d in downloads],
                      "id": v["id"], "study": v["study"], "title": v["title"], "evidence_kind": v["evidence_kind"], "labels": v["labels"], "caveats": v["caveats"],
                      "records_kept": v.get("records_kept", []), "engine_benchmark": v.get("engine_benchmark"), "biological_carrier": v.get("biological_carrier"),
                      "posthoc_denominators": v.get("posthoc_denominators"), "sim_time_s": v.get("sim_time_s"), "media": v["media"],
                      "sources_verified": len(v["sources"]), "renderer_verified": len(v["renderer"])} | hrefs)
    if total > MAX_MEDIA_BYTES:
        raise ValueError("media exceed the byte bound")
    out.update(staged)
    return {"visuals": cards, "manifest_href": manifest_path, "manifest_sha256": sha256(raw).hexdigest()}
