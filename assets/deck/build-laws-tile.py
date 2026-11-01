#!/usr/bin/env python3
"""One slide: twelve laws of living form as a 4x3 grid of square tiles, each with its picture.

Photo tiles are the specimens our models were tested on (full-resolution files from the morpho lab
repo, the cell-geometry candidates, and Wikimedia Commons). The other tiles are renders of the law
itself (Errera's cut, the truncated icosahedron, the hollow tube, the square-cube law, Kleiber's slope).
Badges say only what the repo records: green = a Lean module for the claim compiled; blue = tested on
specimens by the morpho lab audits (docs/team/species.json).

The drawn tiles take a progress `e` (0..1) and a phase `u` so that build-laws-anim.py can animate the
same drawings; the still uses their final state (DRAWN_STILL).

Run from anywhere:
    uv run --with pillow --with numpy --with matplotlib python3 assets/deck/build-laws-tile.py \
        [--morpho ~/Documents/GitHub/infinitemorphospace]

Writes assets/deck/laws-tile.png (1920x1080, same size as the other slides) and
laws-tile@2x.png (3840x2160).
Fonts: macOS Helvetica Neue, as in build-4slide.py. Footer, seal and header come from slide-1.png.
"""
import argparse
import io
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]

S = 2                                   # render scale; design units are 1920x1080
W, H = 1920, 1080
L, R = 97, 1823
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
REG, BOLD, MED = 0, 1, 10
BLACK, GRAY = (0, 0, 0), (111, 111, 111)

NAVY = (11, 22, 51)
GOLD = (236, 190, 92)
PAPER = (240, 236, 226)
MUTED = (178, 186, 208)
DIM = (126, 138, 172)
SKY = (120, 160, 235)
GREEN = (26, 158, 75)
BLUE = (15, 59, 255)

# layout (design units): a text column on the left, 4x3 square tiles on the right
GAP = 14
TILE = 278
GRID_W = 4 * TILE + 3 * GAP
GX, GY = R - GRID_W, 100
PANEL_R = GX - 40                       # right edge of the text column


def font(i, size):
    return ImageFont.truetype(FONT, int(round(size * S)), index=i)


def P(v):
    return int(round(v * S))


def tile_xy(n):
    return GX + (n % 4) * (TILE + GAP), GY + (n // 4) * (TILE + GAP)


# ---------------------------------------------------------------- formulas (matplotlib mathtext)
def mathtext(tex, size, color):
    """Render `tex` (mathtext) to a transparent RGBA image, `size` design px font size."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    matplotlib.rcParams["mathtext.fontset"] = "stix"
    fig = Figure(figsize=(0.1, 0.1), dpi=72)
    FigureCanvasAgg(fig)
    fig.text(0, 0, f"${tex}$", fontsize=size * S * 0.98, color=tuple(v / 255 for v in color))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=72, transparent=True, bbox_inches="tight", pad_inches=0.02)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


# ---------------------------------------------------------------- photos
def fetch(url, cache):
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / url.rsplit("/", 1)[-1]
    if not dst.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "delphisci-laws-tile/1.0 (https://github.com/fractastical/delphi)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dst.write_bytes(r.read())
    return Image.open(dst)


def cover(im, w, h, cx=0.5, cy=0.5, zoom=1.0):
    """Crop `im` to the w:h aspect around (cx, cy) (fractions of the image); zoom > 1 crops tighter."""
    im = im.convert("RGB")
    iw, ih = im.size
    asp = w / h
    bw, bh = (iw, iw / asp) if iw / ih < asp else (ih * asp, ih)
    bw, bh = bw / zoom, bh / zoom
    x0 = min(max(cx * iw - bw / 2, 0), iw - bw)
    y0 = min(max(cy * ih - bh / 2, 0), ih - bh)
    return im.crop((int(x0), int(y0), int(x0 + bw), int(y0 + bh))).resize((w, h), Image.LANCZOS)


# ---------------------------------------------------------------- drawn tiles
# Each takes the tile size in pixels (w, h), a progress e (0..1) and a phase u (0..1), and draws in
# design units through D(): design px at render scale S and supersampling K. The art lives above the
# caption, which starts ~90 design px from the bottom.
K = 3


def D(v):
    return v * S * K


def ease(u):
    """0 -> 1 -> 0 over one loop."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * u)


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Tile:
    def __init__(self, w, h):
        self.w, self.h = w, h
        top, bot = np.array([16, 30, 66], float), np.array([8, 16, 40], float)
        t = np.linspace(0, 1, h)[:, None, None]
        arr = (top * (1 - t) + bot * t) * np.ones((1, w, 1))
        self.im = Image.fromarray(arr.astype("uint8"), "RGB").resize((w * K, h * K), Image.BICUBIC)
        self.d = ImageDraw.Draw(self.im)
        self.cx = w * K / 2

    def text(self, x, y, s, size, fill, idx=MED, anchor="l"):
        f = ImageFont.truetype(FONT, int(D(size)), index=idx)
        tw = self.d.textlength(s, font=f)
        x = x - tw / 2 if anchor == "m" else x - tw if anchor == "r" else x
        self.d.text((x, y), s, font=f, fill=fill)

    def dashed(self, p0, p1, col, wd, dash=None, gap=None):
        """Dashes of fixed length, so a growing line does not shimmer."""
        dash, gap = dash or D(7), gap or D(6)
        n = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if n < 1:
            return
        ux, uy = (p1[0] - p0[0]) / n, (p1[1] - p0[1]) / n
        s = 0.0
        while s < n:
            e = min(s + dash, n)
            self.d.line([(p0[0] + ux * s, p0[1] + uy * s), (p0[0] + ux * e, p0[1] + uy * e)], fill=col, width=int(wd))
            s += dash + gap

    def done(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)


def errera(w, h, e=0.6, u=0.0):
    """An elongated cell: the shortest cut (gold) grows across it; longer cuts dashed; then the daughters part."""
    t = Tile(w, h)
    d, cx, cy = t.d, t.cx, D(104)
    a, b = D(108), D(44)
    grow = smooth(e * 1.7)
    sep = smooth((e - 0.62) / 0.38) * D(9)
    fill = (26, 52, 108)
    if sep < 1:
        d.ellipse((cx - a, cy - b, cx + a, cy + b), fill=fill, outline=PAPER, width=int(D(2.2)))
        t.dashed((cx - a * 0.97, cy), (cx + a * 0.97, cy), (150, 160, 190), D(1.5))
        ang = math.radians(35)
        th = math.atan2(math.sin(ang) * a, math.cos(ang) * b)
        t.dashed((cx + a * math.cos(th), cy - b * math.sin(th)), (cx - a * math.cos(th), cy + b * math.sin(th)), (150, 160, 190), D(1.5))
        d.line([(cx, cy - b), (cx, cy - b + 2 * b * grow)], fill=GOLD, width=int(D(4.5)))
        t.text(cx - a * 0.8, cy - D(20), "longer cuts", 13, (150, 160, 190))
        if grow > 0.9:
            t.text(cx + D(8), cy + D(6), "shortest wall", 13, GOLD)
    else:
        for sgn, (s0, s1) in ((-1, (90, 270)), (1, (270, 90))):
            ox = sgn * sep
            d.pieslice((cx - a + ox, cy - b, cx + a + ox, cy + b), s0, s1, fill=fill, outline=PAPER, width=int(D(2.2)))
            d.line([(cx + ox, cy - b), (cx + ox, cy + b)], fill=GOLD, width=int(D(4.5)))
    return t.done()


def truncated_icosahedron():
    phi = (1 + 5 ** 0.5) / 2
    V = []
    for s1 in (-1, 1):
        for s2 in (-1, 1):
            V += [(0, s1, s2 * phi), (s1, s2 * phi, 0), (s2 * phi, 0, s1)]
    V = np.array(V, float)
    V /= np.linalg.norm(V[0])
    edge = min(np.linalg.norm(V[i] - V[j]) for i in range(12) for j in range(i + 1, 12))
    adj = {i: [j for j in range(12) if j != i and abs(np.linalg.norm(V[i] - V[j]) - edge) < 1e-6] for i in range(12)}
    faces = []
    for i in range(12):                                # a pentagon at each icosahedron vertex
        pts = [V[i] + (V[j] - V[i]) / 3 for j in adj[i]]
        n = V[i] / np.linalg.norm(V[i])
        u = np.cross(n, [0.3, 0.5, 0.8]); u /= np.linalg.norm(u); v = np.cross(n, u)
        c = np.mean(pts, axis=0)
        pts.sort(key=lambda p: math.atan2(np.dot(p - c, v), np.dot(p - c, u)))
        faces.append(("p", pts))
    for i in range(12):                                # a hexagon in each icosahedron face
        for j in adj[i]:
            for m in adj[i]:
                if i < j < m and m in adj[j]:
                    pts = []
                    for a_, b_ in ((i, j), (j, m), (m, i)):
                        pts += [V[a_] + (V[b_] - V[a_]) / 3, V[a_] + 2 * (V[b_] - V[a_]) / 3]
                    faces.append(("h", pts))
    return faces


FACES = truncated_icosahedron()


def twelve_pentagons(w, h, e=1.0, u=0.0):
    """Truncated icosahedron: 12 pentagons (gold) among 20 hexagons; u is the turn about the vertical axis."""
    t = Tile(w, h)
    d = t.d
    ay, ax = math.radians(24) + 2 * math.pi * u, math.radians(-20)
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Rm = Rx @ Ry
    cx, cy, rad = w * K * 0.37, D(100), D(55)
    light = np.array([-0.4, 0.5, 0.75]); light /= np.linalg.norm(light)
    vis = []
    for kind, pts in FACES:
        q = [Rm @ p for p in pts]
        c = np.mean(q, axis=0)
        n = np.cross(q[1] - q[0], q[2] - q[0]); n /= np.linalg.norm(n)
        if np.dot(n, c) < 0:
            n = -n
        if n[2] > 0:
            vis.append((c[2], kind, q, n))
    for _, kind, q, n in sorted(vis, key=lambda v: v[0]):
        sh = 0.55 + 0.45 * max(0, np.dot(n, light))
        poly = [(cx + p[0] * rad, cy - p[1] * rad) for p in q]
        base = np.array(GOLD if kind == "p" else (46, 86, 170), float)
        d.polygon(poly, fill=tuple(int(v * sh) for v in base))
        d.line(poly + [poly[0]], fill=(10, 18, 44), width=int(D(1.6)))
    lx = w * K * 0.37 + D(64)
    t.text(lx, cy - D(24), "12 pentagons", 14, GOLD, BOLD)
    t.text(lx, cy - D(5), "20 hexagons", 14, SKY, BOLD)
    t.text(lx, cy + D(14), "any size", 13, DIM, REG)
    return t.done()


def hollow_tube(w, h, e=1.0, u=0.0):
    """A rod's material spread into a tube: wall area fixed, outer radius r -> 1.5 r, stiffness 2(R/r)^2 - 1."""
    t = Tile(w, h)
    d = t.d
    r = D(24)
    R_ = r * (1 + 0.5 * e)
    ri = math.sqrt(max(R_ ** 2 - r ** 2, 0))
    stiff = 2 * (R_ / r) ** 2 - 1                       # (R^4 - ri^4) / r^4
    y = D(58)
    x1, x2 = w * K * 0.27, w * K * 0.73
    Rmax = 1.5 * r
    d.ellipse((x1 - r, y - r, x1 + r, y + r), fill=(120, 130, 160), outline=PAPER, width=int(D(2)))
    d.ellipse((x2 - R_, y - R_, x2 + R_, y + R_), fill=GOLD, outline=PAPER, width=int(D(2)))
    if ri > D(1):
        d.ellipse((x2 - ri, y - ri, x2 + ri, y + ri), fill=(12, 22, 52), outline=PAPER, width=int(D(2)))
    xa, xb = x1 + r + D(9), x2 - Rmax - D(9)
    d.line([(xa, y), (xb, y)], fill=MUTED, width=int(D(2)))
    hd = D(6)
    d.polygon([(xb + D(2), y), (xb - hd, y - hd * 0.6), (xb - hd, y + hd * 0.6)], fill=MUTED)
    t.text(x1, y + Rmax + D(6), "solid rod", 14, MUTED, anchor="m")
    t.text(x2, y + Rmax + D(6), "same material", 14, GOLD, anchor="m")
    t.text(t.cx, D(128), f"{stiff:.1f}× stiffer", 20, GOLD, BOLD, anchor="m")
    t.text(t.cx, D(152), "same wall area", 13, MUTED, REG, anchor="m")
    return t.done()


def square_cube(w, h, e=1.0, u=0.0):
    """Cubes of side 1, 2, 3 with unit grids: weight goes as L^3, strength as L^2."""
    t = Tile(w, h)
    d = t.d
    unit = D(17)
    c30, s30 = math.cos(math.radians(30)), 0.5
    base_y = D(130)
    xs = (w * K * 0.14, w * K * 0.42, w * K * 0.79)
    caps = (("W ×1", "A ×1"), ("W ×8", "A ×4"), ("W ×27", "A ×9"))
    for i, (n, x, cap) in enumerate(zip((1, 2, 3), xs, caps)):
        g = smooth((e * 1.7 - 0.35 * i) / 0.6)
        if g > 0.02:
            s = n * unit * g
            B = np.array([x, base_y])
            up = np.array([0, -s])
            Rr, Ll, Kk = B + [c30 * s, -s30 * s], B + [-c30 * s, -s30 * s], B + [0, -s]
            faces = {"top": (B + up, Rr + up, Kk + up, Ll + up, (150, 178, 236)),
                     "left": (Ll, B, B + up, Ll + up, (86, 122, 205)),
                     "right": (B, Rr, Rr + up, B + up, (46, 82, 160))}
            for p0, p1, p2, p3, col in faces.values():
                d.polygon([tuple(p0), tuple(p1), tuple(p2), tuple(p3)], fill=col)
                e1, e2 = p1 - p0, p3 - p0
                for j in range(n + 1):
                    a0, b0 = p0 + e1 * j / n, p0 + e2 * j / n
                    d.line([tuple(a0), tuple(a0 + e2)], fill=(10, 20, 50), width=int(D(1.3)))
                    d.line([tuple(b0), tuple(b0 + e1)], fill=(10, 20, 50), width=int(D(1.3)))
        t.text(x, base_y + D(8), cap[0], 13, GOLD if n > 1 else MUTED, anchor="m")
        t.text(x, base_y + D(24), cap[1], 13, MUTED, REG, anchor="m")
    return t.done()


def kleiber(w, h, e=1.0, u=0.0):
    """Schematic log-log axes: slope 3/4 (Kleiber) against 2/3 (surface) and 1 (proportional), drawn out of one origin."""
    t = Tile(w, h)
    d = t.d
    x0, x1 = w * K * 0.07, w * K * 0.55
    y0, y1 = D(140), D(38)
    d.line([(x0, y0), (x1, y0)], fill=MUTED, width=int(D(1.8)))
    d.line([(x0, y0), (x0, y1)], fill=MUTED, width=int(D(1.8)))
    xa, ya = x0 + D(7), y0 - D(7)
    span = x1 - xa - D(5)
    sc = (ya - y1 - D(4)) / span
    p = smooth(e * 1.35)

    def line(slope, col, wd, dash):
        xb, yb = xa + span * p, ya - slope * span * p * sc
        (t.dashed((xa, ya), (xb, yb), col, wd) if dash else d.line([(xa, ya), (xb, yb)], fill=col, width=int(wd)))
    line(1.0, DIM, D(1.8), True)
    line(2 / 3, SKY, D(1.8), True)
    line(0.75, GOLD, D(4.5), False)
    for frac in (0.0, p):
        xx, yy = xa + frac * span, ya - 0.75 * frac * span * sc
        d.ellipse((xx - D(4.5), yy - D(4.5), xx + D(4.5), yy + D(4.5)), fill=PAPER)
    t.text(x0 + D(2), y0 + D(5), "mouse", 12, MUTED, REG)
    t.text(x1, y0 + D(5), "elephant", 12, MUTED, REG, anchor="r")
    t.text(x0 + D(4), y1 - D(18), "metabolic rate", 12, MUTED, REG)
    lx = w * K * 0.60
    for i, (sw, lab, col, wd, dash) in enumerate((("1", "proportional", DIM, 2, True),
                                                  ("3/4", "Kleiber", GOLD, 5, False),
                                                  ("2/3", "surface area", SKY, 2, True))):
        yy = D(44) + D(32) * i
        if dash:
            t.dashed((lx, yy + D(7)), (lx + D(18), yy + D(7)), col, D(wd), dash=D(5), gap=D(4))
        else:
            d.line([(lx, yy + D(7)), (lx + D(18), yy + D(7))], fill=col, width=int(D(wd)))
        t.text(lx + D(26), yy - D(5), "M", 16, col, BOLD)
        t.text(lx + D(26) + D(14.5), yy - D(8), sw, 11, col, BOLD)      # exponent, raised
        t.text(lx + D(26), yy + D(13), lab, 12, MUTED, REG)
    return t.done()


DRAWN = {"Errera's law": errera, "Twelve pentagons": twelve_pentagons, "Hollow tubes": hollow_tube,
         "Square-cube law": square_cube, "Kleiber's law": kleiber}


# ---------------------------------------------------------------- the twelve laws
def laws(morpho, cache):
    ds = morpho / "datasets"
    cand = ENGINE / "claim-sources/cell-geometry/inputs/candidates"
    man = json.loads((ENGINE / "test-data/organisms/images/manifest.json").read_text())["images"]
    odo = next(x for x in man if x["slug"] == "odonata")
    try:
        odonata = fetch(odo["original_url"], cache)
    except Exception as e:
        print("odonata original unavailable, using the thumbnail:", e)
        odonata = Image.open(ENGINE / odo["thumb_path"])

    def ph(path, **kw):
        def art(w, h):
            return cover(path if isinstance(path, Image.Image) else Image.open(path), w, h, **kw)
        art.photo = (path, kw)                          # the animation reuses the source and crop
        return art

    def drawn(name):
        fn = DRAWN[name]
        art = lambda w, h: fn(w, h)                     # the final state
        art.drawn = fn
        return art

    return [
        dict(name="Logarithmic spiral", tex=r"r = a\,e^{\,\theta\cot\alpha}", by="Thompson 1917",
             art=ph(ds / "thompson_1917/t1917-027/nautilus_pompilius_specimen.jpg", cx=0.47, cy=0.5, zoom=1.2),
             pills=[("TESTED ON 3 SPECIES", BLUE)]),
        dict(name="Phyllotaxis", tex=r"\theta_n = n\cdot 137.508^{\circ}", by="Vogel 1979",
             art=ph(ds / "phyllotaxis/helianthus_annuus_capitulum_specimen.jpg"),
             pills=[("TESTED ON SUNFLOWER", BLUE)]),
        dict(name="Murray's law", tex=r"r_0^{3} = r_1^{3} + r_2^{3}", by="Murray 1926",
             art=ph(ds / "venation/ginkgo_open_venation_specimen.jpg", cx=0.5, cy=0.32),
             pills=[("LEAN-CHECKED", GREEN), ("TESTED ON GINKGO", BLUE)]),
        dict(name="Turing patterns", tex=r"\partial_t u = D_u\nabla^{2}u + f(u,v)", by="Turing 1952",
             art=ph(ds / "turing/pomacanthus_imperator_stripes_specimen.jpg", cx=0.62, cy=0.45),
             pills=[("TESTED ON 3 SPECIES", BLUE)]),
        dict(name="Wing venation", txt="cells = Voronoi(centres)", by="Hoffmann et al. 2018",
             art=ph(odonata, cx=0.4, cy=0.42, zoom=1.5),
             pills=[("TESTED ON 463 WINGS", BLUE)]),
        dict(name="120° cell junctions", txt="three walls meet at 120°", by="Plateau; Thompson 1917",
             art=ph(cand / "honeycomb.jpg"), pills=[("LEAN-CHECKED", GREEN)]),
        dict(name="Errera's law", txt="a new wall has least area", by="Errera 1886",
             art=drawn("Errera's law"), pills=[("LEAN-CHECKED", GREEN)]),
        dict(name="Laplace pressure", tex=r"\Delta p = 2\gamma\,/\,r", by="Laplace 1806; Thompson ch. V",
             art=ph(cand / "soap-bubbles.jpg", cx=0.5, cy=0.55, zoom=1.2), pills=[]),
        dict(name="Twelve pentagons", tex=r"V-E+F=2\;\Rightarrow\;12\ \mathrm{pentagons}", by="Euler; Thompson ch. IX",
             art=drawn("Twelve pentagons"), pills=[]),
        dict(name="Hollow tubes", tex=r"I \propto R^{4}\,(1-k^{4})", by="Thompson 1917, ch. XVI",
             art=drawn("Hollow tubes"), pills=[("LEAN-CHECKED", GREEN)]),
        dict(name="Square-cube law", tex=r"W\propto L^{3},\ \ A\propto L^{2}", by="Galileo 1638",
             art=drawn("Square-cube law"), pills=[("LEAN-CHECKED", GREEN)]),
        dict(name="Kleiber's law", tex=r"B \propto M^{3/4}", by="Kleiber 1932 · schematic",
             art=drawn("Kleiber's law"), pills=[]),
    ]


# ---------------------------------------------------------------- compose
def text_tracked(d, x, y, s, f, fill, track):
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + track * S
    return x


def wrap(text, f, width):
    lines, cur = [], ""
    for wd in text.split():
        t = f"{cur} {wd}".strip()
        if f.getlength(t) <= P(width) or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    return lines + [cur] if cur else lines


def caption(law, size=TILE):
    """The caption layer of a tile: gradient, name, formula, source and badges (RGBA, square)."""
    tw = th = size
    tile = Image.new("RGBA", (P(tw), P(th)), (0, 0, 0, 0))
    gh = P(150)
    gp = np.zeros((gh, P(tw), 4), dtype="uint8")
    gp[..., 0], gp[..., 1], gp[..., 2] = NAVY
    gp[..., 3] = (np.linspace(0, 1, gh) ** 1.1 * 242).astype("uint8")[:, None]
    tile.alpha_composite(Image.fromarray(gp, "RGBA"), (0, P(th) - gh))
    td = ImageDraw.Draw(tile)
    td.text((P(14), P(th - 88)), law["name"], font=font(BOLD, 24), fill=(255, 255, 255))
    if "tex" in law:
        f = mathtext(law["tex"], 27, GOLD)
        if f.height > P(32):
            f = f.resize((int(f.width * P(32) / f.height), P(32)), Image.LANCZOS)
        if f.width > P(tw - 28):
            f = f.resize((P(tw - 28), int(f.height * P(tw - 28) / f.width)), Image.LANCZOS)
        tile.alpha_composite(f, (P(14), P(th - 58) + (P(26) - f.height) // 2))
    else:
        td.text((P(14), P(th - 56)), law["txt"], font=font(MED, 18), fill=GOLD)
    td.text((P(14), P(th - 26)), law["by"], font=font(REG, 13.5), fill=MUTED)
    px = 12
    for label, c in law["pills"]:
        pf = font(MED, 12)
        ptw = pf.getlength(label) + P(16)
        td.rounded_rectangle((P(px), P(12), P(px) + ptw, P(32)), radius=P(10), fill=c)
        td.text((P(px) + P(8), P(14.5)), label, font=pf, fill=(255, 255, 255))
        px += ptw / S + 6
    return tile


def tile_mask(size):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=P(10), fill=255)
    return mask


def chrome():
    """The page without the tiles: header, the text column, credits and footer."""
    orig = Image.open(ENGINE / "assets/deck/slide-1.png").convert("RGB")
    logo = orig.crop((1706, 113, 1823, 261)).resize((P(58), P(73)), Image.LANCZOS)
    foot = orig.crop((0, 975, W, H)).resize((P(W), P(H - 975)), Image.LANCZOS)

    im = Image.new("RGB", (P(W), P(H)), "white")
    d = ImageDraw.Draw(im)
    hf = font(REG, 22)
    text_tracked(d, P(L), P(33), "DELPHI  ·  SCIENCE CLAW HACK @ MIT", hf, GRAY, 1.6)
    right = "THE LAWS"
    wtxt = sum(hf.getlength(c) + 1.6 * S for c in right) - 1.6 * S
    text_tracked(d, P(R) - wtxt, P(33), right, hf, GRAY, 1.6)
    d.rectangle((P(L) - S, P(74), P(R) + S, P(78)), fill=BLACK)
    im.paste(logo, (P(PANEL_R) - P(58), P(GY)))

    y = GY - 6
    for line in ("Twelve laws", "of living form"):
        d.text((P(L), P(y)), line, font=font(BOLD, 58), fill=BLACK)
        y += 66
    y += 14
    sf = font(REG, 26)
    for line in wrap("Each law beside the specimen it was tested on, or a drawing of the law itself.", sf, PANEL_R - L):
        d.text((P(L), P(y)), line, font=sf, fill=GRAY)
        y += 36

    # legend: what the badges and the drawn tiles mean
    y += 56
    lf, pf = font(REG, 21), font(MED, 13)
    for label, c, text in (("LEAN-CHECKED", GREEN, "A Lean module for the claim compiled."),
                           ("TESTED ON SPECIMENS", BLUE, "The morpho lab audits ran it on real specimens."),
                           ("DRAWN TILE", NAVY, "A render of the law, not a photograph. The Kleiber slopes are schematic, not data.")):
        ptw = pf.getlength(label) + P(18)
        d.rounded_rectangle((P(L), P(y), P(L) + ptw, P(y + 24)), radius=P(12), fill=c)
        d.text((P(L) + P(9), P(y + 4)), label, font=pf, fill=(255, 255, 255))
        y += 36
        for line in wrap(text, lf, PANEL_R - L):
            d.text((P(L), P(y)), line, font=lf, fill=GRAY)
            y += 28
        y += 26

    cf = font(REG, 12.5)
    credit = ("Photos, Wikimedia Commons: sunflower (CC BY-SA 2.0), ginkgo (CC BY-SA 3.0), nautilus (CC BY-SA 4.0), emperor angelfish, "
              "Diego Delso (CC BY-SA 4.0), dragonfly, Tim Bekaert (public domain), epithelium, Zhiguo.he (CC BY-SA 4.0), "
              "bubbles, T. Pilgrim (public domain).")
    lines = wrap(credit, cf, PANEL_R - L)
    y = GY + 3 * TILE + 2 * GAP - 16 * len(lines)
    for line in lines:
        d.text((P(L), P(y)), line, font=cf, fill=(140, 140, 140))
        y += 16
    im.paste(foot, (0, P(975)))
    return im


def build(morpho, cache, out_dir):
    im = chrome()
    for n, law in enumerate(laws(morpho, cache)):
        x, y = tile_xy(n)
        tile = law["art"](P(TILE), P(TILE)).convert("RGBA")
        tile.alpha_composite(caption(law))
        im.paste(tile.convert("RGB"), (P(x), P(y)), tile_mask(tile.size))

    out_dir.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / "laws-tile@2x.png", optimize=True)
    im.resize((W, H), Image.LANCZOS).save(out_dir / "laws-tile.png", optimize=True)
    print("wrote", out_dir / "laws-tile.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--morpho", type=Path, default=Path.home() / "Documents/GitHub/infinitemorphospace")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache/delphisci-laws-tile")
    ap.add_argument("--out", type=Path, default=HERE)
    a = ap.parse_args()
    build(a.morpho, a.cache, a.out)
