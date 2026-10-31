"""Segment every image in inputs/sources.json with Cellpose (CPSAM v2) on Nebius.

Writes results/<image-id>/{mask.png, overlay.png, cellpose.json}. Images that
already have a mask are skipped, so the script is safe to re-run.

    python3 claim-sources/cell-geometry/segment.py [image-id ...]
"""
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "plugins" / "nebius"))
from nebius_mcp import Client  # noqa: E402

MODEL = "cellpose-cpsam-v2"


def download(client, artifact_id, dest):
    handle = client.call("download_scientific_artifact", {"artifact_id": artifact_id})
    url = handle.get("url") or (handle.get("handle") or {}).get("url") or handle.get("download_url")
    dest.write_bytes(urllib.request.urlopen(url, timeout=300).read())


def segment(client, image_id, meta):
    out = HERE / "results" / image_id
    if (out / "mask.png").exists():
        print(f"{image_id}: already segmented")
        return
    out.mkdir(parents=True, exist_ok=True)
    ref = client.upload(MODEL, HERE / "inputs" / meta["image"], "image/png")
    diameter = meta.get("cellpose_diameter")
    sub = client.call("segment_cells_native", {
        "image_base64": ref,
        "media_type": "image/png",
        "research_only": True,
        "diameter": diameter,
        "idempotency_key": f"cell-geometry-{ref['sha256'][:32]}-d{diameter or 'auto'}",
        "output_prefix": f"claim-sources/cell-geometry/{image_id}",
        "wait_seconds": 30,
    })
    # A retryable error after admission still carries the operation ID to poll.
    op_id = (sub.get("operation") or {}).get("id") or sub.get("operation_id") or (sub.get("error") or {}).get("operation_id")
    if not op_id:
        raise RuntimeError(f"unexpected submit response: {json.dumps(sub)[:1500]}")
    print(f"{image_id}: submitted {op_id}")
    res = client.wait(op_id, every=10)
    r = res["result"]
    download(client, r["mask_artifact"]["artifact_id"], out / "mask.png")
    download(client, r["overlay_artifact"]["artifact_id"], out / "overlay.png")
    record = {
        "image_id": image_id,
        "operation_id": op_id,
        "platform": "Nebius Scientific AI Platform",
        "tool": "segment_cells_native",
        "model_id": r["model_id"],
        "model_sha256": r["model_sha256"],
        "diameter": diameter,
        "cellpose_version": r["cellpose_version"],
        "input_sha256": r["input_sha256"],
        "mask_sha256": r["mask_artifact"]["sha256"],
        "object_count": r["object_count"],
        "image_shape": r["image_shape"],
        "timings": res.get("response", {}).get("timings"),
        "object_areas_px": r["object_areas_px"],
    }
    (out / "cellpose.json").write_text(json.dumps(record, indent=1))
    print(f"{image_id}: {r['object_count']} cells")


def main():
    sources = json.loads((HERE / "inputs" / "sources.json").read_text())
    wanted = sys.argv[1:] or list(sources)
    client = Client()
    for image_id in wanted:
        try:
            segment(client, image_id, sources[image_id])
        except Exception as e:  # keep going; one bad image shouldn't stop the batch
            print(f"{image_id}: FAILED {e}")


if __name__ == "__main__":
    main()
