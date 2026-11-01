#!/usr/bin/env python3
"""The twelve-laws slide as a looping animation (MP4 and GIF).

Same page as laws-tile.png (build-laws-tile.py supplies the page, captions, photos and the drawn
tiles), with every square tile moving:
  photos           slow push-in and drift on the specimen
  Errera's law     the shortest wall grows across the cell, then the daughters part
  twelve pentagons the truncated icosahedron turns once
  hollow tubes     a rod's material spreads into a tube; the stiffness readout is 2(R/r)^2 - 1, computed
  square-cube      cubes of side 1, 2, 3 grow; the unit grids show weight x L^3 and area x L^2
  Kleiber's law    the slopes draw out from a common origin (schematic, no data)

    uv run --with pillow --with numpy --with matplotlib python3 assets/deck/build-laws-anim.py \
        [--frames 80] [--fps 20] [--morpho ~/Documents/GitHub/infinitemorphospace]

Needs ffmpeg on PATH. Writes laws-tile.mp4 (1920x1080, 20 fps), laws-tile.gif (1024 px wide, 12 fps, to keep
it small) and laws-tile-midframe.png (a still from the full-grown part of the loop) next to this file.
"""
import argparse
import importlib.util
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("laws_tile", HERE / "build-laws-tile.py")
tl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tl)


def photo_tile(src, kw, n, w, h, u):
    """Slow push-in and drift on a specimen photo; each tile has its own phase."""
    uu = u + 0.07 * n
    z = kw.get("zoom", 1.0) * (1 + 0.14 * tl.ease(uu))
    cx = kw.get("cx", 0.5) + 0.012 * math.cos(2 * math.pi * uu)
    cy = kw.get("cy", 0.5) + 0.010 * math.sin(2 * math.pi * uu)
    return tl.cover(src, w, h, cx=cx, cy=cy, zoom=z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--morpho", type=Path, default=Path.home() / "Documents/GitHub/infinitemorphospace")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache/delphisci-laws-tile")
    ap.add_argument("--frames", type=int, default=80)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--gif-width", type=int, default=1024)
    ap.add_argument("--gif-fps", type=int, default=12)
    ap.add_argument("--out", type=Path, default=HERE)
    a = ap.parse_args()

    laws = tl.laws(a.morpho, a.cache)
    page = tl.chrome()
    P, side = tl.P, tl.P(tl.TILE)
    mask = tl.tile_mask((side, side))
    caps = [tl.caption(law) for law in laws]
    srcs = {}
    for n, law in enumerate(laws):                      # photo sources, shrunk once so each frame is fast
        ph = getattr(law["art"], "photo", None)
        if ph:
            im = (ph[0] if isinstance(ph[0], Image.Image) else Image.open(ph[0])).convert("RGB")
            im.thumbnail((2000, 2000), Image.LANCZOS)
            srcs[n] = (im, ph[1])

    tmp = Path(tempfile.mkdtemp(prefix="laws-anim-"))
    try:
        for f in range(a.frames):
            u = f / a.frames
            fr = page.copy()
            for n, law in enumerate(laws):
                if n in srcs:
                    art = photo_tile(srcs[n][0], srcs[n][1], n, side, side, u)
                else:
                    art = law["art"].drawn(side, side, e=tl.ease(u), u=u)
                tile = art.convert("RGBA")
                tile.alpha_composite(caps[n])
                x, y = tl.tile_xy(n)
                fr.paste(tile.convert("RGB"), (P(x), P(y)), mask)
            fr.resize((tl.W, tl.H), Image.LANCZOS).save(tmp / f"f{f:03d}.png")
            print(f"\rframe {f + 1}/{a.frames}", end="", flush=True)
        print()
        a.out.mkdir(parents=True, exist_ok=True)
        inp = ["-framerate", str(a.fps), "-i", str(tmp / "f%03d.png")]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-vf", "format=yuv420p", "-c:v", "libx264",
                        "-crf", "17", "-movflags", "+faststart", str(a.out / "laws-tile.mp4")], check=True)
        vf = (f"fps={a.gif_fps},scale={a.gif_width}:-1:flags=lanczos,split[s0][s1];"
              "[s0]palettegen=max_colors=128:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-vf", vf, "-loop", "0", str(a.out / "laws-tile.gif")], check=True)
        shutil.copy(tmp / f"f{a.frames // 2:03d}.png", a.out / "laws-tile-midframe.png")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name in ("laws-tile.mp4", "laws-tile.gif"):
        print(name, f"{(a.out / name).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
