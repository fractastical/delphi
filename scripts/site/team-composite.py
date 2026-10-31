#!/usr/bin/env python3
"""Team composite: portraits on a pentagon around the DELPHI seal, each wedge filled
with a morphology generated from its model.

    bottom     Hoffmann et al. 2018 (PNAS 115:9905) insect wing venation: primary veins
               (wedge margin + longitudinal veins), inhibitory centres seeded at a graded
               density, equilibrated by Lloyd's algorithm, secondary veins = Voronoi edges.
    top-right  Vogel 1979 phyllotaxis, r_n = c sqrt(n), theta_n = n * 137.5077...deg,
               centred on the seal (thompson1917-ch14-07/08).
    right      Murray 1926 vascular tree: r0^3 = r1^3 + r2^3 at every junction, branch
               angles cos(theta1) = (r0^4 + r1^4 - r2^4) / (2 r0^2 r1^2) (thompson1917-ch15-15).
    left       Turing pattern from the Gray-Scott system (Pearson 1993) (turing-wavelength).
    top-left   Equiangular spiral net: a square grid mapped by z -> exp((1 + i b) z), the
               threefold-per-turn spiral of horns and shells and its orthogonal family
               (thompson1917-ch13-01/03; ch17 transformations).

Same models as infinitemorphospace/models/{2018-hoffmann-wing-venation, 1979-vogel-phyllotaxis,
1959-murray-vascular-cube-law-branching, 1952-turing-morpho}.py. Needs numpy, scipy, Pillow,
and inkscape on PATH to rasterise assets/logo.svg.

    python3 scripts/site/team-composite.py --portraits ~/Pictures/halloween-anime
"""

import argparse
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
NAVY = (20, 33, 61)
GOLD = (229, 192, 123)

W, H = 1820, 1650
CX, CY = 910, 880
R_PENT = 650            # pentagon circumradius (portrait centres)
P_RAD = 180             # portrait radius
LOGO = 620
LOGO_RAD = LOGO * 250 / 512   # visible seal disc
GAP = 14
LINE_W = 6
ORDER = [1, 4, 5, 6, 2]       # portrait files, clockwise from the top
GOLDEN = math.radians(360 * (2 - (1 + 5 ** 0.5) / 2))


def xy(r, phi):
    return CX + r * np.cos(phi), CY - r * np.sin(phi)


def vertex_angles():
    return [math.radians(90 - 72 * i) for i in range(5)]


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0, 1)
    return np.hypot(px - ax - t * dx, py - ay - t * dy)


def wedge_mask(i, scale=1):
    """Free area of wedge i (between vertices i and i+1), at `scale` x canvas resolution."""
    va = vertex_angles()
    a, b = va[i], va[(i + 1) % 5]
    ys, xs = np.mgrid[0:H * scale, 0:W * scale].astype(float) / scale
    (ax, ay), (bx, by) = xy(R_PENT, a), xy(R_PENT, b)
    # inside triangle (centre, A, B)
    def side(px, py, x0, y0, x1, y1):
        return (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
    s1 = side(xs, ys, CX, CY, ax, ay); s2 = side(xs, ys, ax, ay, bx, by); s3 = side(xs, ys, bx, by, CX, CY)
    inside = ((s1 >= 0) & (s2 >= 0) & (s3 >= 0)) | ((s1 <= 0) & (s2 <= 0) & (s3 <= 0))
    m = inside & (np.hypot(xs - CX, ys - CY) > LOGO_RAD + GAP)
    m &= np.hypot(xs - ax, ys - ay) > P_RAD + GAP
    m &= np.hypot(xs - bx, ys - by) > P_RAD + GAP
    inset = LINE_W / 2 + 8
    m &= seg_dist(xs, ys, CX, CY, ax, ay) > inset
    m &= seg_dist(xs, ys, CX, CY, bx, by) > inset
    m &= seg_dist(xs, ys, ax, ay, bx, by) > inset
    return m


def bisector(i):
    va = vertex_angles()
    return va[i] - math.radians(36)


# --------------------------------------------------------------------------- patterns
# Each returns a float alpha array (H, W) in [0, 1]; it is clipped to the wedge later.

def draw_layer(scale):
    im = Image.new('L', (W * scale, H * scale), 0)
    return im, ImageDraw.Draw(im)


def to_alpha(im):
    return np.asarray(im.resize((W, H), Image.LANCZOS), dtype=float) / 255.0


def phyllotaxis(i, mask):
    S = 3; im, d = draw_layer(S)
    c = 8.2; rdot = 0.36 * c * math.sqrt(math.pi)
    n_max = int((R_PENT / c) ** 2)
    for n in range(1, n_max):
        r = c * math.sqrt(n); th = n * GOLDEN
        x, y = xy(r, th)
        xi, yi = int(x), int(y)
        if 0 <= xi < W and 0 <= yi < H and mask[yi, xi]:
            d.ellipse(((x - rdot) * S, (y - rdot) * S, (x + rdot) * S, (y + rdot) * S), fill=255)
    return to_alpha(im)


def murray_tree(i, mask):
    S = 3; im, d = draw_layer(S)
    rng = np.random.default_rng(52)
    lam = 7.0                                  # segment length / radius
    stack = []                                 # (x, y, screen heading, radius, depth, side)
    for off, r_root in ((-21, 6.0), (0, 7.5), (21, 6.0)):
        phi = bisector(i) + math.radians(off)
        x0, y0 = xy(LOGO_RAD + GAP + 2, phi)
        stack.append((x0, y0, -phi, r_root, 0, 1 if off <= 0 else -1))
    while stack:
        x, y, hd, r, depth, side = stack.pop()
        L = lam * r
        x1, y1 = x + L * math.cos(hd), y + L * math.sin(hd)
        d.line((x * S, y * S, x1 * S, y1 * S), fill=255, width=max(1, int(round(2 * r * S * 0.55))))
        rr = r * S * 0.55
        d.ellipse((x1 * S - rr, y1 * S - rr, x1 * S + rr, y1 * S + rr), fill=255)
        if depth >= 15 or r < 0.5:
            continue
        xi, yi = int(x1), int(y1)
        if not (0 <= xi < W and 0 <= yi < H) or not ndi_dilated[i][yi, xi]:
            continue
        q = rng.uniform(0.5, 0.75)             # flow split Q1 / Q0
        r1, r2 = r * q ** (1 / 3), r * (1 - q) ** (1 / 3)   # Murray: r0^3 = r1^3 + r2^3
        c1 = (r ** 4 + r1 ** 4 - r2 ** 4) / (2 * r * r * r1 * r1)
        c2 = (r ** 4 + r2 ** 4 - r1 ** 4) / (2 * r * r * r2 * r2)
        t1, t2 = math.acos(min(1, c1)), math.acos(min(1, c2))
        stack.append((x1, y1, hd + side * t1, r1, depth + 1, -side))
        stack.append((x1, y1, hd - side * t2, r2, depth + 1, side))
    return to_alpha(im)


def turing(i, mask):
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min() - 4, ys.max() + 5, xs.min() - 4, xs.max() + 5
    h, w = (y1 - y0) // 2, (x1 - x0) // 2
    rng = np.random.default_rng(1952)
    U = np.ones((h, w)); V = np.zeros((h, w))
    for _ in range(int(h * w / 250)):
        a, b = rng.integers(3, h - 3), rng.integers(3, w - 3)
        U[a - 2:a + 2, b - 2:b + 2] = 0.5; V[a - 2:a + 2, b - 2:b + 2] = 0.25
    V += 0.01 * rng.random((h, w))
    Du, Dv, F, k = 0.16, 0.08, 0.029, 0.057    # Pearson labyrinthine regime
    def lap(Z):
        Z = np.pad(Z, 1, mode='edge')          # zero-flux boundary
        return Z[:-2, 1:-1] + Z[2:, 1:-1] + Z[1:-1, :-2] + Z[1:-1, 2:] - 4 * Z[1:-1, 1:-1]
    for _ in range(14000):
        uvv = U * V * V
        U += Du * lap(U) - uvv + F * (1 - U)
        V += Dv * lap(V) + uvv - (F + k) * V
    v = Image.fromarray(V.astype(np.float32)).resize((x1 - x0, y1 - y0), Image.BICUBIC)
    v = np.asarray(v)
    out = np.zeros((H, W))
    out[y0:y1, x0:x1] = np.clip((v - 0.12) / 0.12, 0, 1)
    return out


def equiangular_net(i, mask):
    """Image of a square grid under z -> exp((1 + i b) z): the two orthogonal families
    of equiangular spirals r = e^{b phi + c} and r = e^{-phi / b + c} about the seal centre.
    b = ln 3 / 2pi is the spiral that grows threefold per turn."""
    S = 3
    my, mx = np.where(mask)
    y0, y1, x0, x1 = my.min() - 2, my.max() + 3, mx.min() - 2, mx.max() + 3
    ys, xs = np.mgrid[y0 * S:y1 * S, x0 * S:x1 * S].astype(float) / S
    rad = np.maximum(np.hypot(xs - CX, ys - CY), 1.0)
    phi = np.arctan2(-(ys - CY), xs - CX) - bisector(i)
    phi = (phi + math.pi) % (2 * math.pi) - math.pi          # continuous across the wedge
    b = math.log(3.0) / (2 * math.pi)
    u = np.log(rad) - b * phi
    v = np.log(rad) + phi / b
    cell = 26.0                                              # grid square at r = 420 px
    du = cell * math.sqrt(1 + b * b) / 420.0
    dv = du / b
    alpha = np.zeros_like(rad)
    for f, df, g, wpx in ((u, du, math.sqrt(1 + b * b), 1.9), (v, dv, math.sqrt(1 + 1 / b ** 2), 1.3)):
        t = f / df
        dist = np.abs(t - np.round(t)) / (g / rad / df) * S   # distance to nearest curve, in S-px
        alpha = np.maximum(alpha, np.clip(wpx * S - dist + 0.5, 0, 1))
    img = Image.fromarray((alpha * 255).astype(np.uint8)).resize((x1 - x0, y1 - y0), Image.LANCZOS)
    out = np.zeros((H, W))
    out[y0:y1, x0:x1] = np.asarray(img, dtype=float) / 255.0
    return out


def wing(i, mask):
    """Hoffmann et al. 2018 on the wedge outline, at 2x resolution."""
    S = 2
    m2 = wedge_mask(i, S)
    ys, xs = np.mgrid[0:H * S, 0:W * S].astype(float) / S
    rad = np.hypot(xs - CX, ys - CY)
    r_in = LOGO_RAD + GAP
    r_out = R_PENT * math.cos(math.radians(36))
    s = np.clip((rad - r_in) / (r_out - r_in), 0, 1)
    cell = (9.0 + 15.0 * s) * S                       # local domain size, leading -> trailing
    fr, fc = np.where(m2)
    wts = 1.0 / cell[fr, fc] ** 2; wts /= wts.sum()
    n_cells = int((1.0 / ((math.sqrt(3) / 2) * cell[fr, fc] ** 2)).sum())
    rng = np.random.default_rng(2018)
    idx = rng.choice(fr.size, size=n_cells, replace=False, p=wts)
    pts = np.column_stack([fc, fr]).astype(float)
    seeds = pts[idx].copy()
    for _ in range(18):                               # Lloyd equilibration (authors' step)
        _, lab = cKDTree(seeds).query(pts)
        cnt = np.bincount(lab, minlength=n_cells).astype(float)
        acc = np.zeros_like(seeds); np.add.at(acc, lab, pts)
        nz = cnt > 0; seeds[nz] = acc[nz] / cnt[nz, None]
    _, lab = cKDTree(seeds).query(pts)
    g = np.full(m2.shape, -1, np.int32); g[fr, fc] = lab
    sec = np.zeros(m2.shape, bool)
    dd = (g[:, :-1] != g[:, 1:]) & (g[:, :-1] >= 0) & (g[:, 1:] >= 0); sec[:, :-1] |= dd
    dd = (g[:-1, :] != g[1:, :]) & (g[:-1, :] >= 0) & (g[1:, :] >= 0); sec[:-1, :] |= dd
    # primary scaffold: wing margin + longitudinal veins concentric with the leading edge
    margin = m2 & ~ndi.binary_erosion(m2, iterations=3 * S)
    prim = margin.copy()
    for frac in (0.3, 0.62):
        rr = (r_in + frac * (r_out - r_in)) * S
        prim |= m2 & (np.abs(rad * S - rr) < 1.6 * S)
    a = np.where(ndi.binary_dilation(sec), 0.85, 0.0)
    a = np.maximum(a, np.where(ndi.binary_dilation(prim, iterations=S), 1.0, 0.0))
    img = Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    return np.asarray(img, dtype=float) / 255.0


PATTERNS = [phyllotaxis, murray_tree, wing, turing, equiangular_net]   # wedge 0 = top-right, clockwise


# --------------------------------------------------------------------------- composition

def portrait(path, size, ring=15):
    sc = 4; big = size * sc
    im = Image.open(path).convert('RGBA').resize((size, size), Image.LANCZOS)
    m = Image.new('L', (big, big), 0)
    ImageDraw.Draw(m).ellipse((ring * sc, ring * sc, big - ring * sc, big - ring * sc), fill=255)
    m = m.resize((size, size), Image.LANCZOS)
    r = Image.new('RGBA', (big, big), (0, 0, 0, 0)); rd = ImageDraw.Draw(r)
    rd.ellipse((0, 0, big - 1, big - 1), fill=GOLD + (255,))
    k = int(ring * sc * 0.45); rd.ellipse((k, k, big - k, big - k), fill=NAVY + (255,))
    out = r.resize((size, size), Image.LANCZOS); out.paste(im, (0, 0), m)
    return out


def shadow(bg, box, blur, alpha):
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box, fill=(0, 0, 0, alpha))
    return Image.alpha_composite(bg, sh.filter(ImageFilter.GaussianBlur(blur)))


def render_logo(tmp):
    out = Path(tmp) / 'logo.png'
    subprocess.run(['inkscape', str(REPO / 'assets/logo.svg'), '--export-type=png',
                    f'--export-filename={out}', '-w', '1400', '-h', '1400'],
                   check=True, capture_output=True)
    return Image.open(out).convert('RGBA').resize((LOGO, LOGO), Image.LANCZOS)


ndi_dilated = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--portraits', type=Path, default=Path.home() / 'Pictures/halloween-anime',
                    help='folder with anime-<n>.jpg portraits')
    ap.add_argument('-o', '--out', type=Path, default=REPO / 'assets/team-halloween-2026.png')
    args = ap.parse_args()

    bg = Image.new('RGB', (W, H), NAVY)
    glow = Image.new('L', (W, H), 0); gd = ImageDraw.Draw(glow)
    for r in range(950, 0, -10):
        gd.ellipse((CX - r, CY - r, CX + r, CY + r), fill=int(60 * (1 - r / 950)))
    bg = Image.composite(Image.new('RGB', (W, H), (48, 62, 104)), bg, glow).convert('RGBA')

    gold = np.zeros((H, W, 4), np.uint8); gold[..., :3] = GOLD
    for i, fn in enumerate(PATTERNS):
        mask = wedge_mask(i)
        ndi_dilated[i] = ndi.binary_dilation(mask, iterations=6)
        alpha = fn(i, mask)
        soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)),
                          dtype=float) / 255.0
        layer = gold.copy(); layer[..., 3] = (np.clip(alpha, 0, 1) * soft * 235).astype(np.uint8)
        bg = Image.alpha_composite(bg, Image.fromarray(layer, 'RGBA'))
        print(f'wedge {i}: {fn.__name__}')

    va = vertex_angles()
    verts = [xy(R_PENT, a) for a in va]
    sc = 3
    over = Image.new('RGBA', (W * sc, H * sc), (0, 0, 0, 0)); od = ImageDraw.Draw(over)
    pts = [(x * sc, y * sc) for x, y in verts]
    od.line(pts + [pts[0]], fill=GOLD + (230,), width=LINE_W * sc, joint='curve')
    for p in pts:
        od.line(((CX * sc, CY * sc), p), fill=GOLD + (230,), width=LINE_W * sc)
    bg = Image.alpha_composite(bg, over.resize((W, H), Image.LANCZOS))

    with tempfile.TemporaryDirectory() as tmp:
        logo = render_logo(tmp)
    h = LOGO // 2
    bg = shadow(bg, (CX - h - 10, CY - h + 14, CX + h + 10, CY + h + 34), 24, 150)
    bg.alpha_composite(logo, (CX - h, CY - h))

    size = 2 * P_RAD
    for k, (x, y) in zip(ORDER, verts):
        bg = shadow(bg, (x - P_RAD, y - P_RAD + 16, x + P_RAD, y + P_RAD + 16), 18, 140)
        bg.alpha_composite(portrait(args.portraits / f'anime-{k}.jpg', size), (int(x - P_RAD), int(y - P_RAD)))

    bg.convert('RGB').save(args.out, optimize=True)
    print(f'saved {args.out}')


if __name__ == '__main__':
    main()
