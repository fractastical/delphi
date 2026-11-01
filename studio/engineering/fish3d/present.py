"""Caption, encode and record the Blender renders of a fish3d candidate.

    python -m engineering.fish3d.present --renders DIR [--out artifacts/fish3d/<id>/render] [--verify]

DIR holds still/ and turntable/ from blender_render.py.  Writes still.png, poster.png, turntable.mp4, turntable.gif
and render.json, which maps candidate_sha256 + fish.glb sha256 -> Blender version and settings -> output sha256s.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engineering.geometry.turntable import encode_gif, encode_mp4, probe

ROOT = Path(__file__).resolve().parents[2]
CAND_DIR = ROOT / "artifacts/fish3d/fish3d-N1-cypselurus-baseline"
VIDEO = {"fps": 16, "mp4": {"codec": "libx264", "preset": "slow", "crf": 22, "pix_fmt": "yuv420p", "threads": 1},
         "gif": {"width_px": 640, "height_px": 360, "frame_step": 2, "colors": 128}}
BACKDROP = {"top": (176, 198, 216), "bottom": (226, 233, 238)}
LIMITS = {"still_max_bytes": 6_000_000, "mp4_max_bytes": 4_000_000, "gif_max_bytes": 8_000_000}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for f in ("present.py", "blender_render.py"):
        h.update((Path(__file__).parent / f).read_bytes())
    return h.hexdigest()


def caption(cand_sha: str, glb_sha: str, blender: str, comp: dict) -> list[str]:
    body = comp["components"]["body"]["params"]
    sl = body["standard_length_mm"]["value"]
    span = 2 * (comp["components"]["pectoral_L"]["check"]["bbox_mm"][1][1])
    return [
        f"Candidate fish3d-N1 (sha256 {cand_sha[:12]}), path-traced in Blender {blender} Cycles from fish.glb "
        f"(sha256 {glb_sha[:12]}). SL {sl:.0f} mm, span {span:.0f} mm.",
        "Body, paired fins and caudal sized from Fish 1990 fits, Daane 2021 S1A and the NCA comparison set (derived); "
        "fin thickness, eyes, gill covers assumed.",
        "Scales: an assumed lattice (50 along the body), not a grown or measured pattern. Engineered form, not an "
        "organism. Not an aerodynamic result.",
    ]


def backdrop(w: int, h: int) -> Image.Image:
    t = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array(BACKDROP["top"], float), np.array(BACKDROP["bottom"], float)
    arr = (top * (1 - t) + bot * t).repeat(w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def compose(png: Path, lines: list[str]) -> np.ndarray:
    im = Image.open(png).convert("RGBA")
    w, h = im.size
    band = int(0.13 * h)
    canvas = Image.new("RGBA", (w, h + band), (250, 250, 250, 255))
    canvas.paste(Image.alpha_composite(backdrop(w, h), im), (0, 0))
    d = ImageDraw.Draw(canvas)
    size = max(11, int(h / 52))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size)
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        font = bold = ImageFont.load_default()
    for i, line in enumerate(lines):
        f = bold if i == 0 else font
        d.text((int(0.012 * w), h + int(0.12 * band) + i * int(1.45 * size)), line, fill=(20, 20, 20, 255), font=f)
        if d.textlength(line, font=f) > 0.985 * w:
            raise ValueError(f"caption line {i} does not fit at {w}px")
    rgb = np.asarray(canvas.convert("RGB"))
    return rgb[: rgb.shape[0] // 2 * 2, : rgb.shape[1] // 2 * 2].copy()  # even sizes for yuv420p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", required=True)
    ap.add_argument("--out", default=str(CAND_DIR / "render"))
    a = ap.parse_args(argv)
    rd, out = Path(a.renders), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    build = json.loads((CAND_DIR / "build.json").read_text())
    comp = json.loads((CAND_DIR / "components.json").read_text())
    reps = {k: json.loads((rd / k / "blender_report.json").read_text()) for k in ("still", "turntable")}
    for k, r in reps.items():
        if r["glb_sha256"] != build["files"]["fish.glb"] or r["candidate_sha256"] != build["candidate_sha256"]:
            raise SystemExit(f"{k}: render was made from a different mesh or candidate than build.json")
    lines = caption(build["candidate_sha256"], build["files"]["fish.glb"], reps["still"]["blender"], comp)
    still = compose(rd / "still" / "frame_000.png", lines)
    Image.fromarray(still).save(out / "still.png", optimize=False)
    frames = [compose(p, lines) for p in sorted((rd / "turntable").glob("frame_*.png"))]
    encode_mp4(frames, out / "turntable.mp4", VIDEO)
    encode_gif(frames, out / "turntable.gif", VIDEO)
    Image.fromarray(frames[0]).save(out / "poster.png", optimize=False)
    pr = probe(out / "turntable.mp4")
    files = {p.name: {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
             for p in sorted(out.iterdir()) if p.suffix in (".png", ".mp4", ".gif")}
    rec = {
        "schema": "frontier.fish3d.render/1",
        "evidence_kind": "path-traced rendering of the candidate mesh (not a measurement, not aerodynamics)",
        "candidate_sha256": build["candidate_sha256"], "glb": "fish.glb", "glb_sha256": build["files"]["fish.glb"],
        "build_code_sha256": build["code_sha256"], "present_code_sha256": code_hash(),
        "blender": {k: {kk: r[kk] for kk in ("blender", "mode", "samples", "resolution", "frames", "settings",
                                             "framing", "imported")} for k, r in reps.items()},
        "video": {"file": "turntable.mp4", "sha256": files["turntable.mp4"]["sha256"],
                  "bytes": files["turntable.mp4"]["bytes"], "codec": pr["codec_name"], "width": pr["width"],
                  "height": pr["height"], "fps": VIDEO["fps"], "n_frames": int(pr["nb_read_frames"]), "loop": True},
        "gif": {"file": "turntable.gif", "sha256": files["turntable.gif"]["sha256"], "bytes": files["turntable.gif"]["bytes"]},
        "poster": "poster.png", "poster_sha256": files["poster.png"]["sha256"],
        "still": {"file": "still.png", "sha256": files["still.png"]["sha256"], "bytes": files["still.png"]["bytes"]},
        "caption": lines, "backdrop": BACKDROP, "video_settings": VIDEO, "limits": LIMITS,
        "checks": {"frames_match": int(pr["nb_read_frames"]) == len(frames),
                   "within_limits": files["still.png"]["bytes"] <= LIMITS["still_max_bytes"]
                   and files["turntable.mp4"]["bytes"] <= LIMITS["mp4_max_bytes"]
                   and files["turntable.gif"]["bytes"] <= LIMITS["gif_max_bytes"]},
        "not_claimed": ["aerodynamic performance or validity", "an organism or ancestor", "a grown scale pattern",
                        "biological fin thickness, camber or ray structure", "any physical print"],
    }
    (out / "render.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"checks": rec["checks"], "files": {k: v["bytes"] for k, v in files.items()}}, indent=1))
    return 0 if all(rec["checks"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
