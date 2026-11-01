#!/usr/bin/env python3
"""Pattern atlas: the five-wedge pentagon of docs/team.html as one large still image, without
the portraits, with every species the morpho lab tested each model on fanned out around its
wedge, the way the page shows them on hover.

The wedges are the same generated morphologies as team-composite.py (phyllotaxis, Murray tree,
wing venation, Turing labyrinth, equiangular net), rendered on a larger pentagon. Species,
crops and findings come from build-team-page.py's PANELS, scores and verdicts from
docs/team/species.json; the photos are read from the morpho repo (or fetched from Wikimedia
Commons for organism-manifest images). Formulas are typeset with matplotlib's mathtext.

    uv run --with numpy --with scipy --with pillow --with matplotlib \\
        python3 scripts/site/pattern-atlas.py [--morpho ~/Documents/GitHub/infinitemorphospace]
"""

import argparse
import importlib.util
import io
import json
import math
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tc = load('team-composite')          # wedge patterns and geometry
tp = load('build-team-page')         # PANELS: claims, species, crops, findings

NAVY, GOLD = tc.NAVY, tc.GOLD
WHITE = (240, 236, 226)
GREY = (190, 196, 214)
RED = (255, 110, 116)

# ---- geometry: a bigger pentagon, no portraits, species on a ring outside -----------------
W, H = 4400, 3600
CX, CY = 2200, 1700
R_PENT = 760
LOGO = 720
SP_RING = 1380          # species circle centres
SP_R = 160              # species circle radius
SP_GAP = 14             # between circles in a fan
LABEL_R = SP_RING + SP_R + 34   # species labels start here, radially outward
TITLE_R = 890           # wedge title block centre, on the bisector
FONT = '/System/Library/Fonts/HelveticaNeue.ttc'   # 0 regular, 1 bold, 7 light
SERIF_I = '/System/Library/Fonts/Supplemental/Georgia Italic.ttf'

# team-composite's pattern functions read the layout from module globals; no portraits here.
for k, v in dict(W=W, H=H, CX=CX, CY=CY, R_PENT=R_PENT, LOGO=LOGO,
                 LOGO_RAD=LOGO * 250 / 512, P_RAD=0).items():
    setattr(tc, k, v)


def xy(r, deg):
    a = math.radians(deg)
    return CX + r * math.cos(a), CY - r * math.sin(a)


def bisector(key):
    return (90 - 72 * tp.WEDGE[key] - 36 + 180) % 360 - 180      # in (-180, 180]


def font(size, style=0, serif=False):
    return ImageFont.truetype(SERIF_I, size) if serif else ImageFont.truetype(FONT, size, index=style)


# ---- wedges and seal ----------------------------------------------------------------------

def draw_wedges(bg):
    gold = np.zeros((H, W, 4), np.uint8); gold[..., :3] = GOLD
    for i, fn in enumerate(tc.PATTERNS):
        mask = tc.wedge_mask(i)
        tc.ndi_dilated[i] = ndi.binary_dilation(mask, iterations=6)
        alpha = fn(i, mask)
        soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)),
                          dtype=float) / 255.0
        layer = gold.copy(); layer[..., 3] = (np.clip(alpha, 0, 1) * soft * 235).astype(np.uint8)
        bg = Image.alpha_composite(bg, Image.fromarray(layer, 'RGBA'))
        print(f'wedge {i}: {fn.__name__}', flush=True)
    verts = [xy(R_PENT, 90 - 72 * i) for i in range(5)]
    sc = 2
    over = Image.new('RGBA', (W * sc, H * sc), (0, 0, 0, 0)); od = ImageDraw.Draw(over)
    pts = [(x * sc, y * sc) for x, y in verts]
    od.line(pts + [pts[0]], fill=GOLD + (230,), width=tc.LINE_W * sc, joint='curve')
    for p in pts:
        od.line(((CX * sc, CY * sc), p), fill=GOLD + (230,), width=tc.LINE_W * sc)
    for p in pts:                                   # a small knot where the portraits used to sit
        r = 16 * sc; od.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=GOLD + (255,))
        r = 7 * sc; od.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=NAVY + (255,))
    return Image.alpha_composite(bg, over.resize((W, H), Image.LANCZOS))


def soft_shadow(bg, box, blur, alpha):
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box, fill=(0, 0, 0, alpha))
    return Image.alpha_composite(bg, sh.filter(ImageFilter.GaussianBlur(blur)))


def draw_seal(bg):
    with tempfile.TemporaryDirectory() as tmp:
        logo = tc.render_logo(tmp)
    h = LOGO // 2
    bg = soft_shadow(bg, (CX - h - 12, CY - h + 16, CX + h + 12, CY + h + 40), 28, 150)
    bg.alpha_composite(logo, (CX - h, CY - h))
    return bg


# ---- text ---------------------------------------------------------------------------------

def mathtext(tex, px, color):
    """Typeset a formula with matplotlib and return it as an RGBA image in `color`."""
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import mathtext as mt
    from matplotlib.font_manager import FontProperties
    buf = io.BytesIO()
    mt.math_to_image(f'${tex}$', buf, prop=FontProperties(size=px * 0.72), dpi=100, format='png', color='black')
    buf.seek(0)
    arr = np.asarray(Image.open(buf).convert('RGBA'))
    a = arr[..., 3] if arr[..., 3].min() < 255 else 255 - arr[..., :3].mean(axis=2).astype(np.uint8)
    out = np.zeros(a.shape + (4,), np.uint8); out[..., :3] = color; out[..., 3] = a
    im = Image.fromarray(out, 'RGBA')
    return im.crop(im.getbbox()) if im.getbbox() else im


def text_block(lines, align='left'):
    """lines: [(text or RGBA image, font, colour, gap after)] -> one RGBA image."""
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    sizes = []
    for t, f, _, _ in lines:
        if isinstance(t, Image.Image):
            sizes.append((t.width, t.height))
        else:
            _, _, r, b = probe.textbbox((0, 0), t, font=f)
            sizes.append((r, b + 4))
    w = max(s[0] for s in sizes) + 4
    h = sum(s[1] + g for s, (_, _, _, g) in zip(sizes, lines))
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    y = 0
    for (t, f, c, g), (tw, th) in zip(lines, sizes):
        x = 0 if align == 'left' else (w - tw) if align == 'right' else (w - tw) // 2
        if isinstance(t, Image.Image):
            im.alpha_composite(t, (x, y))
        else:
            d.text((x, y), t, font=f, fill=c + (255,))
        y += th + g
    return im


def place(bg, block, x, y, anchor):
    """anchor 'l': x is the left edge; 'r': the right edge; 'c': the centre. y is the vertical centre."""
    px = x if anchor == 'l' else x - block.width if anchor == 'r' else x - block.width / 2
    bg.alpha_composite(block, (int(px), int(y - block.height / 2)))


def wrap(text, f, width):
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    lines, cur = [], ''
    for wd in text.split():
        t = (cur + ' ' + wd).strip()
        if probe.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = wd
    if cur:
        lines.append(cur)
    return lines


# ---- species ------------------------------------------------------------------------------

def fetch_original(url, cache):
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / url.rsplit('/', 1)[-1]
    if not dst.exists():
        req = urllib.request.Request(url, headers={
            'User-Agent': 'delphisci-pattern-atlas/1.0 (https://github.com/fractastical/delphi)'})
        with urllib.request.urlopen(req, timeout=60) as r:
            dst.write_bytes(r.read())
    return dst


def species_photo(s, morpho, cache):
    if 'org_image' in s:
        man = json.loads((REPO / 'test-data/organisms/images/manifest.json').read_text())['images']
        o = next(x for x in man if x['slug'] == s['org_image'])
        try:
            return Image.open(fetch_original(o['original_url'], cache))
        except Exception as e:                               # offline: the 160 px manifest thumb
            print(f'  {s["name"]}: {e}; using the manifest thumbnail', file=sys.stderr)
            return Image.open(REPO / o['thumb_path'])
    p = morpho / s['image']
    if p.exists():
        return Image.open(p)
    print(f'  {s["name"]}: {p} missing; using the docs/team/species thumbnail', file=sys.stderr)
    return Image.open(REPO.parent / 'docs/team/species' / f'{tp.slug(s["name"])}.jpg')


def circle_photo(im, crop, size, ring, color):
    """Square crop (centre x, centre y, side) as in build-team-page.thumb, in a ringed disc."""
    im = im.convert('RGB')
    w, h = im.size
    fx, fy, k = crop
    s = int(min(w, h) * k)
    x0 = min(max(int(fx * w - s / 2), 0), w - s)
    y0 = min(max(int(fy * h - s / 2), 0), h - s)
    im = im.crop((x0, y0, x0 + s, y0 + s)).resize((size, size), Image.LANCZOS).convert('RGBA')
    sc = 4; big = size * sc
    m = Image.new('L', (big, big), 0)
    ImageDraw.Draw(m).ellipse((ring * sc, ring * sc, big - ring * sc, big - ring * sc), fill=255)
    m = m.resize((size, size), Image.LANCZOS)
    r = Image.new('RGBA', (big, big), (0, 0, 0, 0)); rd = ImageDraw.Draw(r)
    rd.ellipse((0, 0, big - 1, big - 1), fill=color + (255,))
    k2 = int(ring * sc * 0.5); rd.ellipse((k2, k2, big - k2, big - k2), fill=NAVY + (255,))
    out = r.resize((size, size), Image.LANCZOS); out.paste(im, (0, 0), m)
    return out


def draw_species(bg, morpho, cache):
    scored = json.loads((REPO.parent / 'docs/team/species.json').read_text())
    apothem = R_PENT * math.cos(math.radians(36))
    step = math.degrees(2 * math.asin((SP_R + SP_GAP) / SP_RING))
    f_name, f_common, f_find, f_score = font(40, 0, serif=True), font(27, 7), font(23, 7), font(22, 1)
    spokes = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(spokes)
    discs = []
    for p in tp.PANELS:
        bis = bisector(p['key'])
        n = len(p['species'])
        recs = {r['name']: r for r in scored.get(p['key'], [])}
        # The page centres each fan on the bisector. Here the two upper wedges would then push a
        # fan of three into the title, so those fans are swung away from the top vertex instead.
        swing = 0 if n == 1 or not 0 < bis < 180 else (n - 1) / 2 * step * (1 if bis > 90 else -1)
        for i, s in enumerate(p['species']):
            ang = bis + swing - (i - (n - 1) / 2) * step
            # dotted spoke from the pentagon edge to the disc, as on the page
            edge = apothem / math.cos(math.radians(ang - bis))
            (x0, y0), (x1, y1) = xy(edge + 10, ang), xy(SP_RING - SP_R - 12, ang)
            nd = max(1, int(math.hypot(x1 - x0, y1 - y0) / 14))
            for k in range(nd + 1):
                t = k / nd; px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                if any(bx0 <= px <= bx1 and by0 <= py <= by1 for bx0, by0, bx1, by1 in TITLE_BOXES):
                    continue                                 # do not run through the wedge title
                sd.ellipse((px - 2.2, py - 2.2, px + 2.2, py + 2.2), fill=WHITE + (110,))
            cx, cy = xy(SP_RING, ang)
            col = RED if s.get('negative') else WHITE
            discs.append((cx, cy, circle_photo(species_photo(s, morpho, cache), s['crop'], 2 * SP_R, 9, col)))
            # label, outward along the spoke so fans of three do not collide
            r = recs.get(s['name'], {})
            score = f"{r['score']:.1f} / 100 · {r['verdict']}" if r.get('score') is not None else ''
            if s.get('negative'):
                score = 'tested negative' + (f" · {r['score']:.1f} / 100" if r.get('score') is not None else '')
            c = math.cos(math.radians(ang))
            align = 'left' if c > 0.3 else 'right' if c < -0.3 else 'center'
            lines = [(s['name'], f_name, col, 2), (s['common'], f_common, WHITE, 10)]
            for ln in wrap(s['finding'], f_find, 540 if align != 'center' else 680):
                lines.append((ln, f_find, GREY, 0))
            if score:
                lines[-1] = lines[-1][:3] + (8,)
                lines.append((score, f_score, RED if s.get('negative') else GOLD, 0))
            block = text_block(lines, align)
            # Side labels sit beside their own disc, at the height of the spoke's continuation,
            # so a fan of three reads disc / label / disc / label down the side.
            ly = cy - (LABEL_R - SP_RING) * math.sin(math.radians(ang))
            if align == 'center':
                place(bg, block, cx, cy + SP_R + 30 + block.height / 2, 'c')
            elif align == 'left':
                place(bg, block, cx + SP_R + 34, ly, 'l')
            else:
                place(bg, block, cx - SP_R - 34, ly, 'r')
            print(f'  {p["key"]}: {s["name"]}', flush=True)
    bg = Image.alpha_composite(bg, spokes)
    for cx, cy, disc in discs:
        bg = soft_shadow(bg, (cx - SP_R, cy - SP_R + 14, cx + SP_R, cy + SP_R + 14), 16, 130)
        bg.alpha_composite(disc, (int(cx - SP_R), int(cy - SP_R)))
    return bg


def draw_titles(bg):
    f_title, f_model = font(46, 1), font(27, 7)
    for p in tp.PANELS:
        formula = mathtext(p['formula'], 40, GOLD)
        block = text_block([(p['title'].upper(), f_title, GOLD, 4), (p['model'], f_model, WHITE, 14),
                            (formula, None, None, 0)], 'center')
        x, y = xy(TITLE_R, bisector(p['key']))
        place(bg, block, x, y, 'c')
        TITLE_BOXES.append((x - block.width / 2 - 18, y - block.height / 2 - 18,
                            x + block.width / 2 + 18, y + block.height / 2 + 18))
    return bg


TITLE_BOXES = []        # filled by draw_titles; the species spokes skip these


def draw_header(bg):
    d = ImageDraw.Draw(bg)
    d.text((W / 2, 110), 'Fundamental laws of nature', font=font(96, 1), fill=GOLD + (255,), anchor='mm')
    d.text((W / 2, 192), 'Five patterns of life, each drawn from its equations, and the species their models were tested on',
           font=font(36, 7), fill=WHITE + (255,), anchor='mm')
    f_foot = font(24, 7)
    foot = ('Wedges computed from Vogel 1979, Murray 1926, Hoffmann et al. 2018, Turing 1952 (Gray–Scott) and '
            'Thompson 1917, with no hand drawing. Scores are MorphoEval audit rubrics out of 100 from AI assessors '
            'other than the builder, not expert validation; a red ring marks a model that tested negative. '
            'delphisci · github.com/fractastical/delphi')
    y = H - 64
    for ln in wrap(foot, f_foot, W - 500)[::-1]:
        d.text((W / 2, y), ln, font=f_foot, fill=(160, 168, 190, 255), anchor='mm'); y -= 34
    return bg


def background():
    bg = Image.new('RGB', (W, H), NAVY)
    glow = Image.new('L', (W, H), 0); gd = ImageDraw.Draw(glow)
    for r in range(1500, 0, -10):
        gd.ellipse((CX - r, CY - r, CX + r, CY + r), fill=int(60 * (1 - r / 1500)))
    return Image.composite(Image.new('RGB', (W, H), (48, 62, 104)), bg, glow).convert('RGBA')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--morpho', type=Path, default=Path.home() / 'Documents/GitHub/infinitemorphospace')
    ap.add_argument('--cache', type=Path, default=Path.home() / '.cache/delphisci-images',
                    help='where Commons originals are kept between runs')
    ap.add_argument('--png', type=Path, default=REPO / 'assets/pattern-atlas.png')
    ap.add_argument('--jpg', type=Path, default=REPO.parent / 'docs/team/pattern-atlas.jpg')
    args = ap.parse_args()

    bg = background()
    bg = draw_wedges(bg)
    bg = draw_seal(bg)
    bg = draw_titles(bg)
    bg = draw_species(bg, args.morpho, args.cache)
    bg = draw_header(bg)
    out = bg.convert('RGB')
    for path in (args.png, args.jpg):
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(path, optimize=True, **({'quality': 90} if path.suffix == '.jpg' else {}))
    print(f'saved {args.png} and {args.jpg} ({W}x{H})')


if __name__ == '__main__':
    main()
