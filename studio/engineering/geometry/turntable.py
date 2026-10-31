"""Turntable MP4 / GIF / poster for each printable form, rendered from the committed STL triangles.

    python -m engineering.geometry.turntable [--out artifacts/print] [--only <form-id>] [--frames 48]
    python -m engineering.geometry.turntable --verify      # re-check committed media; exit 1 on any mismatch

Input is the STL each form's design JSON names; its sha256 must equal the build manifest's entry, and the canonical
mesh hash of the re-read STL is recorded, so every video names the exact mesh it shows.  The frames are drawn with
the same flat-shaded polygons as `render.py` (matplotlib, orthographic camera orbiting the prop) and encoded with
ffmpeg (libx264, one thread, bit-exact flags) and Pillow (GIF, one shared palette, no dithering), so a re-run with
the same libraries writes the same bytes.  Each frame carries its own caveats: the display scale, a scale bar in
prop and biological millimetres, the fin plate thickness, and that nothing has been printed.

Writes media/<form-id>/{turntable.mp4, turntable.gif, poster.png, render.json} and media/index.json.  The build
manifest (manifest.json) does not list media/; media/index.json is the authority for these files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from . import render  # noqa: E402
from . import validate as VAL  # noqa: E402

HERE = Path(__file__).resolve().parent
SETTINGS = {
    "width_px": 640, "height_px": 360, "dpi": 100, "frames": 48, "fps": 16, "elevation_deg": 22.0,
    "start_azimuth_deg": -58.0, "projection": "ortho", "mesh_color_rgb": [0.32, 0.55, 0.78],
    "background": "#ffffff", "scale_bar_prop_mm": 20.0, "zoom": 2.3, "caption_band": 0.25,
    "mp4": {"codec": "libx264", "preset": "slow", "crf": 23, "pix_fmt": "yuv420p", "threads": 1},
    "gif": {"width_px": 480, "height_px": 270, "frame_step": 2, "colors": 64, "dither": "none"},
    "poster_frame": 0,
    "framing": "one orbit radius per set (largest prop in the set), so sizes compare within a set",
}
LIMITS = {"mp4_max_bytes": 1_500_000, "gif_max_bytes": 2_500_000, "poster_max_bytes": 300_000}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for name in ("turntable.py", "render.py"):
        h.update(name.encode() + b"\0" + (HERE / name).read_bytes())
    return h.hexdigest()


def tool_versions() -> dict:
    import importlib.metadata as md
    ff = subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    return {"matplotlib": md.version("matplotlib"), "numpy": md.version("numpy"), "pillow": md.version("pillow"),
            "ffmpeg": ff}


def caption(design: dict, size_mm: list[float]) -> list[str]:
    k = 1000 * design["prop_mm"]["display_scale"]
    plate = design["print_parameters"]["fin_thickness_mm"]["value"]
    num, den = _ratio(design["prop_mm"]["display_scale"])
    return [f"{design['short']}: {design['title']}",
            f"Display scale {num}:{den}: 1 m of fish = {k:.0f} mm of prop. Prop {size_mm[0]:.1f} × {size_mm[1]:.1f}"
            f" × {size_mm[2]:.1f} mm.",
            f"Fins are {plate:g} mm print plates ({plate / design['prop_mm']['display_scale']:.1f} mm at fish scale), "
            "not biological thickness.",
            "Rendered from the exported STL. Engineered illustrative form, not an organism. "
            "Not printed; printer and resin unknown."]


def _ratio(x: float) -> tuple[int, int]:
    from fractions import Fraction
    f = Fraction(x).limit_denominator(100)
    return f.numerator, f.denominator


def frames(V: np.ndarray, T: np.ndarray, radius: float, lines: list[str], scale: float,
           st=SETTINGS) -> tuple[list[np.ndarray], dict]:
    """RGB frames of one orbit, plus framing checks.  The mesh is centred on its bounding-box centre; the axes
    span +-radius.  Checks: every caption line lies inside the frame, and no drawn pixel touches the edge of the
    picture band on any frame (nothing is cropped)."""
    c = 0.5 * (V.min(axis=0) + V.max(axis=0))
    Vc = V - c
    fig = plt.figure(figsize=(st["width_px"] / st["dpi"], st["height_px"] / st["dpi"]), dpi=st["dpi"],
                     facecolor=st["background"])
    band = st["caption_band"]
    ax = fig.add_axes((0.0, band, 1.0, 1.0 - band), projection="3d", proj_type=st["projection"])
    ax.set_facecolor(st["background"])
    render.add_mesh(ax, [(Vc, T, tuple(st["mesh_color_rgb"]))])
    bar = st["scale_bar_prop_mm"]
    z0 = Vc[:, 2].min() - 0.08 * radius
    x0 = -bar / 2
    ax.plot([x0, x0 + bar], [-0.85 * radius, -0.85 * radius], [z0, z0], color="#222222", lw=2.2)
    ax.text(x0 + bar / 2, -0.85 * radius, z0 - 0.06 * radius,
            f"{bar:g} mm prop = {bar / scale:.0f} mm fish", fontsize=6.5, ha="center", va="top", color="#222222")
    ax.set_xlim(-radius, radius); ax.set_ylim(-radius, radius); ax.set_zlim(-radius, radius)
    ax.set_box_aspect((1, 1, 1), zoom=st["zoom"])
    ax.set_axis_off()
    texts = [fig.text(0.012, band - 0.045 - 0.052 * i, line, fontsize=7.4 if i == 0 else 6.6,
                      weight="bold" if i == 0 else "normal", color="#15232b", ha="left", va="center")
             for i, line in enumerate(lines)]
    out, edge_hits = [], 0
    H = st["height_px"]
    top_band = int(round(H * (1 - band)))  # rows [0, top_band) hold the picture
    bg = np.array(matplotlib.colors.to_rgb(st["background"])) * 255
    for i in range(st["frames"]):
        ax.view_init(elev=st["elevation_deg"], azim=st["start_azimuth_deg"] + 360.0 * i / st["frames"])
        fig.canvas.draw()
        f = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        pic = f[:top_band - 1]
        rim = np.concatenate([pic[0], pic[-1], pic[:, 0], pic[:, -1]])
        edge_hits += int((np.abs(rim.astype(float) - bg).max(axis=1) > 8).sum())
        out.append(f)
    r = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(r) for t in texts]
    W = st["width_px"]
    caption_fits = all(b.x0 >= 0 and b.x1 <= W and b.y0 >= 0 and b.y1 <= H * band for b in boxes)
    plt.close(fig)
    return out, {"caption_inside_frame": caption_fits, "caption_right_edge_px": round(float(max(b.x1 for b in boxes)), 1),
                 "picture_edge_pixels_touched": edge_hits, "not_cropped": edge_hits == 0}


def encode_mp4(fr: list[np.ndarray], path: Path, st=SETTINGS) -> None:
    m = st["mp4"]
    h, w = fr[0].shape[:2]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(st["fps"]), "-i", "-", "-an", "-c:v", m["codec"], "-preset", m["preset"],
           "-crf", str(m["crf"]), "-pix_fmt", m["pix_fmt"], "-threads", str(m["threads"]),
           "-movflags", "+faststart", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
           str(path)]
    subprocess.run(cmd, input=b"".join(f.tobytes() for f in fr), check=True)


def encode_gif(fr: list[np.ndarray], path: Path, st=SETTINGS) -> None:
    g = st["gif"]
    imgs = [Image.fromarray(f).resize((g["width_px"], g["height_px"]), Image.Resampling.LANCZOS)
            for f in fr[::g["frame_step"]]]
    sheet = Image.new("RGB", (g["width_px"], g["height_px"] * len(imgs)))
    for i, im in enumerate(imgs):
        sheet.paste(im, (0, i * g["height_px"]))
    pal = sheet.quantize(colors=g["colors"], method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    q[0].save(path, save_all=True, append_images=q[1:], loop=0, optimize=False, disposal=1,
              duration=int(round(1000 * g["frame_step"] / st["fps"])))


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                          "stream=codec_name,width,height,nb_read_frames,r_frame_rate,pix_fmt", "-of", "json",
                          str(path)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)["streams"][0]


def verify(out: Path) -> list[str]:
    """Re-check committed media against the meshes they claim to show.  Returns problems (empty = consistent):
    every form in the build manifest has media; each file's bytes match its render.json and the index; each
    render names the STL and mesh hash the build manifest holds now; the renderer code hash is current."""
    man = json.loads((out / "manifest.json").read_text())
    idx = json.loads((out / "media" / "index.json").read_text())
    problems = []
    if idx["renderer_code_sha256"] != code_hash():
        problems.append("renderer code changed since the media were rendered")
    if set(idx["forms"]) != set(man["forms"]):
        problems.append(f"index forms {sorted(idx['forms'])} != manifest forms {sorted(man['forms'])}")
    for fid, row in idx["forms"].items():
        md = out / "media" / fid
        rj = (md / "render.json").read_bytes()
        if sha(rj) != row["render_sha256"]:
            problems.append(f"{fid}: render.json bytes differ from the index")
        rec = json.loads(rj)
        for name, want in (("turntable.mp4", rec["video"]["sha256"]), ("turntable.gif", rec["gif"]["sha256"]),
                           ("poster.png", rec["poster_sha256"])):
            if not (md / name).is_file() or sha((md / name).read_bytes()) != want:
                problems.append(f"{fid}: {name} missing or not the bytes render.json declares")
        if man["files"].get(rec["input"]["stl"]) != rec["input"]["stl_sha256"]:
            problems.append(f"{fid}: rendered from an STL the build manifest no longer holds")
        if man["forms"].get(fid, {}).get("mesh_sha256") != rec["input"]["mesh_sha256_design"]:
            problems.append(f"{fid}: design mesh hash changed since rendering")
        if not all(rec["checks"][k] for k in ("mp4_frames_match", "within_size_limits", "caption_inside_frame",
                                              "not_cropped")):
            problems.append(f"{fid}: a render check failed: {rec['checks']}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/print")
    ap.add_argument("--verify", action="store_true", help="check committed media; render nothing")
    ap.add_argument("--only", default=None, help="render one form (a preview); index.json is not rewritten")
    ap.add_argument("--frames", type=int, default=SETTINGS["frames"])
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if a.verify:
        problems = verify(out)
        print("\n".join(problems) if problems else "media consistent with meshes and renderer")
        return 1 if problems else 0
    st = {**SETTINGS, "frames": a.frames}
    man = json.loads((out / "manifest.json").read_text())
    code, tools = code_hash(), tool_versions()
    designs = {fid: json.loads((out / f["design"]).read_text()) for fid, f in man["forms"].items()}
    meshes, radius = {}, {}
    for fid, d in designs.items():
        rel = d["files"]["stl"]["path"]
        data = (out / rel).read_bytes()
        if sha(data) != man["files"][rel]:
            raise ValueError(f"{rel} does not match the build manifest; rebuild before rendering")
        V, T = VAL.read_stl(data)
        meshes[fid] = (rel, data, V, T)
        r = 0.5 * float(np.linalg.norm(V.max(axis=0) - V.min(axis=0)))
        radius[d["set"]["id"]] = max(radius.get(d["set"]["id"], 0.0), r)
    index = {"schema": "frontier.print.media_index/1", "renderer_code_sha256": code, "tools": tools,
             "settings": st, "limits": LIMITS, "forms": {}}
    bad = []
    for fid, d in designs.items():
        if a.only and fid != a.only:
            continue
        rel, data, V, T = meshes[fid]
        size = (V.max(axis=0) - V.min(axis=0)).tolist()
        lines = caption(d, size)
        fr, framing = frames(V, T, radius[d["set"]["id"]] * 1.02, lines, d["prop_mm"]["display_scale"], st)
        md = out / "media" / fid
        md.mkdir(parents=True, exist_ok=True)
        encode_mp4(fr, md / "turntable.mp4", st)
        encode_gif(fr, md / "turntable.gif", st)
        Image.fromarray(fr[st["poster_frame"]]).save(md / "poster.png", optimize=False)
        files = {n: (md / n).read_bytes() for n in ("turntable.mp4", "turntable.gif", "poster.png")}
        pr = probe(md / "turntable.mp4")
        sizes_ok = (len(files["turntable.mp4"]) <= LIMITS["mp4_max_bytes"]
                    and len(files["turntable.gif"]) <= LIMITS["gif_max_bytes"]
                    and len(files["poster.png"]) <= LIMITS["poster_max_bytes"])
        frames_ok = int(pr["nb_read_frames"]) == st["frames"]
        if not (sizes_ok and frames_ok and framing["caption_inside_frame"] and framing["not_cropped"]):
            bad.append(fid)
        rec = {
            "schema": "frontier.print.render/1", "id": fid, "title": d["title"], "short": d["short"],
            "set": d["set"]["id"], "label": d["label"],
            "evidence_kind": "rendering of an engineered print mesh (not an observation, not a simulation)",
            "input": {"stl": rel, "stl_sha256": sha(data), "mesh_sha256_reread_stl": VAL.mesh_hash(V, T),
                      "mesh_sha256_design": d["validation"]["mesh_sha256"],
                      "design": f"design/{fid}.json", "design_sha256": man["files"][f"design/{fid}.json"],
                      "build_code_sha256": man["run"]["code_sha256"]},
            "renderer": {"module": "engineering/geometry/turntable.py (+ render.py add_mesh)",
                         "code_sha256": code, "tools": tools, "settings": st},
            "video": {"file": "turntable.mp4", "sha256": sha(files["turntable.mp4"]),
                      "bytes": len(files["turntable.mp4"]), "codec": pr["codec_name"], "width": pr["width"],
                      "height": pr["height"], "fps": st["fps"], "n_frames": int(pr["nb_read_frames"]),
                      "duration_s": st["frames"] / st["fps"], "loop": True},
            "gif": {"file": "turntable.gif", "sha256": sha(files["turntable.gif"]), "bytes": len(files["turntable.gif"]),
                    "width": st["gif"]["width_px"], "height": st["gif"]["height_px"],
                    "n_frames": len(range(0, st["frames"], st["gif"]["frame_step"]))},
            "poster": "poster.png", "poster_sha256": sha(files["poster.png"]), "poster_bytes": len(files["poster.png"]),
            "caveats": {"display_scale": d["prop_mm"]["display_scale"],
                        "display_scale_meaning": d["prop_mm"]["display_scale_meaning"],
                        "fin_plate_mm": d["print_parameters"]["fin_thickness_mm"]["value"],
                        "fin_plate_note": "fins are thickened print plates, not biological thickness",
                        "printer_resin": d["printer_resin"],
                        "on_frame_text": lines,
                        "not_claimed": ["physical print", "aerodynamic fidelity", "organism", "ancestor",
                                        "evolutionary reachability"]},
            "checks": {"mp4_frames_match": frames_ok, "within_size_limits": sizes_ok, "limits": LIMITS, **framing},
        }
        (md / "render.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        index["forms"][fid] = {"render": f"media/{fid}/render.json",
                               "render_sha256": sha((md / "render.json").read_bytes()),
                               "stl_sha256": rec["input"]["stl_sha256"], "video_sha256": rec["video"]["sha256"],
                               "gif_sha256": rec["gif"]["sha256"], "poster_sha256": rec["poster_sha256"]}
        print(fid, rec["video"]["bytes"], rec["gif"]["bytes"], rec["poster_bytes"], framing,
              "ok" if fid not in bad else "FAIL")
    if not a.only:
        (out / "media" / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
