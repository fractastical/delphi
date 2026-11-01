#!/usr/bin/env python3
"""Standing card for the repo, as one video.

Reads docs/claims.json (the claim graph) and test-data/organisms/merged/taxa.json.
Claim figures are that graph's build. The pre-registered count is result.json files
whose status is "preregistered", the same walk as scripts/site/build-claim-graph.mjs.

Writes assets/delphi-where-it-stands.mp4 and a poster still beside it.

    python3 scripts/site/build-summary-video.py
    python3 scripts/site/build-summary-video.py --preview
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CLAIMS_PATH = ROOT / "docs" / "claims.json"
TAXA_PATH = ROOT / "test-data" / "organisms" / "merged" / "taxa.json"
TESTS = ROOT / "test-data" / "claim-tests"
LOGO = ROOT / "assets" / "logo.svg"
OUT_MP4 = ROOT / "assets" / "delphi-where-it-stands.mp4"
OUT_PNG = ROOT / "assets" / "delphi-where-it-stands.png"

W, H = 1920, 1080
FPS = 24
DURATION = 26.0

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F_BLACK, F_BOLD, F_REG, F_MED = 9, 1, 0, 10

INK = (17, 17, 17)
MUTED = (138, 144, 154)
FAINT = (186, 190, 198)
RULE = (226, 228, 232)
BLUE = (47, 111, 237)
GOLD = (184, 132, 10)
GREEN = (30, 140, 72)
WHITE = (255, 255, 255)

# Bar segments, drawn left to right. A claim is one segment: a proof takes the
# pixel when there is one, otherwise the data verdict, otherwise untested.
SEGMENTS = [
    ("lean", (212, 154, 20), "Lean-checked"),
    ("lit", (236, 208, 130), "proved in literature"),
    ("partial", (214, 186, 110), "partly proved"),
    ("supports", (46, 158, 84), "data supports"),
    ("mixed", (150, 206, 168), "data mixed"),
    ("refutes", (214, 112, 128), "data refutes"),
    ("inconclusive", (196, 202, 212), "inconclusive"),
    ("refuted", (176, 48, 48), "refuted by proof"),
    ("untested", (232, 234, 238), "untested"),
]
SEG_COLOR = {k: c for k, c, _ in SEGMENTS}
SEG_LABEL = {k: lab for k, _, lab in SEGMENTS}

NAMED = [
    ("Aristotle", {"Aristotle"}),
    ("Darwin", {"Charles Darwin"}),
    ("Thompson", {"D'Arcy Wentworth Thompson"}),
    ("Math biology", None),
    ("Wolfram", {"Stephen Wolfram"}),
    ("Levin", {"Michael Levin"}),
]


def font(size, face):
    return ImageFont.truetype(HN, size, index=face)


def ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def appear(t, start, dur=0.45):
    return ease((t - start) / dur)


def counted(t, start, dur, target):
    p = appear(t, start, dur)
    if p >= 1:
        return target
    return int(target * p)


def comma(n):
    return f"{n:,}"


def year_span(years):
    years = [y for y in years if isinstance(y, int)]
    if not years:
        return ""
    def fmt(y):
        return f"{-y} BC" if y < 0 else str(y)
    lo, hi = min(years), max(years)
    if lo == hi:
        return f"c. {fmt(lo)}" if lo < 0 else fmt(lo)
    return f"{fmt(lo)}–{fmt(hi)}"


def segment_of(c):
    if c.get("theorem") and c.get("proof") == "lean":
        return "lean"
    if c.get("theorem") and c.get("proof") == "literature":
        return "lit"
    ev = c.get("evidence")
    if ev in ("supports", "mixed", "refutes", "inconclusive"):
        return ev
    if c.get("verification") == "refuted" or c.get("status") == "refuted":
        return "refuted"
    if c.get("verification") == "partial" or c.get("status") == "partial":
        return "partial"
    return "untested"


def load():
    doc = json.loads(CLAIMS_PATH.read_text())
    claims = doc["claims"]
    named = {name for name, thinkers in NAMED if thinkers}
    named_thinkers = set().union(*(s for _, s in NAMED if s))
    groups = []
    for name, thinkers in NAMED:
        if thinkers is None:
            cs = [c for c in claims if c["thinker"] not in named_thinkers]
        else:
            cs = [c for c in claims if c["thinker"] in thinkers]
        segs = Counter(segment_of(c) for c in cs)
        tested = [c for c in cs if c.get("evidence")]
        groups.append({
            "name": name,
            "claims": cs,
            "n": len(cs),
            "segs": segs,
            "theorems": sum(1 for c in cs if c.get("theorem")),
            "tested": len(tested),
            "live": sum(1 for c in cs if c.get("registry") == "production" and not c.get("draft")),
            "works": Counter(c.get("work") or "" for c in cs),
            "thinkers": Counter(c["thinker"] for c in cs),
            "years": [c.get("year") for c in cs],
        })
    if sum(g["n"] for g in groups) != len(claims):
        raise SystemExit("source rows do not add up to the claim graph")
    for g in groups:
        if sum(g["segs"].values()) != g["n"]:
            raise SystemExit(f"bar for {g['name']} does not partition its claims")

    tested = [c for c in claims if c.get("evidence")]
    verdicts = Counter(c["evidence"] for c in tested)
    faith = []
    for c in tested:
        dt = c.get("data_test") or {}
        f = dt.get("faithfulness") if isinstance(dt, dict) else None
        if f:
            faith.append(f)
    pending = 0
    for dirpath, _, filenames in os.walk(TESTS):
        if "result.json" not in filenames:
            continue
        try:
            rec = json.loads(Path(dirpath, "result.json").read_text())
        except json.JSONDecodeError:
            continue
        if rec.get("status") == "preregistered":
            pending += 1
    taxa = json.loads(TAXA_PATH.read_text())
    stats = {
        "built": doc.get("built") or "",
        "claims": len(claims),
        "thinkers": len({c["thinker"] for c in claims}),
        "years": year_span([c.get("year") for c in claims]),
        "live": sum(1 for c in claims if c.get("registry") == "production" and not c.get("draft")),
        "theorems": sum(1 for c in claims if c.get("theorem")),
        "lean": sum(1 for c in claims if c.get("theorem") and c.get("proof") == "lean"),
        "lit": sum(1 for c in claims if c.get("theorem") and c.get("proof") == "literature"),
        "tested": len(tested),
        "supports": verdicts.get("supports", 0),
        "mixed": verdicts.get("mixed", 0),
        "refutes": verdicts.get("refutes", 0),
        "inconclusive": verdicts.get("inconclusive", 0),
        "organisms": sum(1 for c in tested if c.get("evidence_kind") == "biological"),
        "faith": len(faith),
        "not_rep": sum(1 for f in faith if f.get("status") == "agreed" and f.get("verdict") == "not-representative"),
        "contested": sum(1 for f in faith if f.get("status") == "contested"),
        "pending": pending,
        "neither": sum(1 for c in claims if c.get("verification") == "untested" and not c.get("evidence")),
        "taxa": len(taxa),
        "groups": groups,
    }
    if stats["supports"] + stats["mixed"] + stats["refutes"] + stats["inconclusive"] != stats["tested"]:
        raise SystemExit("verdicts do not add up to tested claims")
    if stats["lean"] + stats["lit"] != stats["theorems"]:
        raise SystemExit("Lean and literature proofs do not add up to theorems")
    return stats


def subtitle(g):
    span = year_span(g["years"])
    if g["name"] == "Math biology":
        return f"{len(g['thinkers'])} thinkers, {span}"
    works = [w for w, _ in g["works"].most_common() if w]
    if len(works) == 1:
        short = {
            "On the Origin of Species": "Origin of Species",
            "On Growth and Form": "On Growth and Form",
            "A New Kind of Science": "A New Kind of Science",
        }.get(works[0], works[0])
        return f"{short}, {span}"
    if g["name"] == "Levin":
        return f"{len(works)} papers, {span}"
    # Aristotle's three treatises share a shape: "The History of Animals".
    bits = []
    for w in works:
        bit = w.replace("The ", "").replace("On the ", "").replace(" of Animals", "")
        bits.append(bit)
    label = ", ".join(bits)
    if len(label) > 36:
        label = f"{len(works)} works"
    return f"{label}, {span}"


def load_seal(size):
    png = Path(tempfile.gettempdir()) / "delphi-seal.png"
    subprocess.run(
        ["qlmanage", "-t", "-s", "1024", "-o", str(png.parent), str(LOGO)],
        check=True, capture_output=True,
    )
    produced = png.parent / "logo.svg.png"
    im = Image.open(produced).convert("RGBA")
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 20 and not (r > 248 and g > 248 and b > 248):
                xs.append(x)
                ys.append(y)
    im = im.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    return im


def text_width(fnt, s):
    return fnt.getlength(s)


def draw_tracked(draw, xy, s, fnt, fill, tracking):
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += fnt.getlength(ch) + tracking
    return x


def rounded_bar(base, box, segments, total, progress):
    x, y, w, h = (int(v) for v in box)
    if progress <= 0 or w <= 0 or total <= 0:
        return
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=max(1, h // 2), fill=255)
    color = Image.new("RGBA", (w, h), (238, 240, 243, 255))
    d = ImageDraw.Draw(color)
    items = [(k, n) for k, n in segments if n]
    # A segment of one claim would vanish in a bar of hundreds. Keep three pixels,
    # then give the rest out in proportion and let the last segment close the width.
    floor = 3
    reserved = floor * len(items)
    extra = max(0, w - reserved)
    widths = [floor + int(extra * n / total) for _, n in items]
    widths[-1] += w - sum(widths)
    pw = w * progress
    cursor = 0
    for (k, _), sw in zip(items, widths):
        vis = int(min(max(0, sw), max(0, pw - cursor)))
        if vis > 0:
            d.rectangle((cursor, 0, cursor + vis, h), fill=SEG_COLOR[k] + (255,))
        cursor += sw
    color.putalpha(mask)
    base.alpha_composite(color, (x, y))


def paint_title(t, seal):
    im = Image.new("RGBA", (W, H), WHITE + (255,))
    d = ImageDraw.Draw(im)
    a = appear(t, 0.15, 0.6)
    if a <= 0:
        return im
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    seal_s = seal.resize((210, 210), Image.Resampling.LANCZOS)
    layer.alpha_composite(seal_s, ((W - 210) // 2, 248))
    kicker = font(22, F_MED)
    title = font(84, F_BOLD)
    sub = font(30, F_REG)
    small = font(22, F_REG)
    draw_tracked(ld, ((W - text_width(kicker, "DELPHI") - 6 * 5) // 2, 490), "DELPHI", kicker, INK, 6)
    s = "Where it stands"
    ld.text(((W - text_width(title, s)) / 2, 536), s, font=title, fill=INK)
    s = "November 1, 2026"
    ld.text(((W - text_width(sub, s)) / 2, 650), s, font=sub, fill=MUTED)
    s = "Candidate laws of biology"
    ld.text(((W - text_width(sub, s)) / 2, 748), s, font=sub, fill=INK)
    s = "Proof for the math. Tests against open data for the rest."
    ld.text(((W - text_width(small, s)) / 2, 802), s, font=small, fill=MUTED)
    s = "delphibio.org"
    ld.text(((W - text_width(small, s)) / 2, 848), s, font=small, fill=INK)
    fade_layer(im, layer, a)
    return im


def fade_layer(base, layer, alpha):
    if alpha >= 1:
        base.alpha_composite(layer)
        return
    if alpha <= 0:
        return
    r, g, b, a = layer.split()
    a = a.point(lambda p: int(p * alpha))
    base.alpha_composite(Image.merge("RGBA", (r, g, b, a)))


def paint_card(t, stats, seal):
    im = Image.new("RGBA", (W, H), WHITE + (255,))
    d = ImageDraw.Draw(im)
    # Header
    head = font(18, F_MED)
    draw_tracked(d, (72, 46), "DELPHI  ·  WHERE IT STANDS", head, INK, 1.4)
    date = "NOV 1, 2026"
    df = font(18, F_MED)
    d.text((W - 72 - text_width(df, date), 46), date, font=df, fill=MUTED)
    d.line((72, 84, W - 72, 84), fill=RULE, width=2)
    seal_s = seal.resize((118, 118), Image.Resampling.LANCZOS)
    im.alpha_composite(seal_s, (W - 72 - 118, 108))

    title = font(52, F_BOLD)
    d.text((72, 108), "Candidate laws of biology", font=title, fill=INK)
    sub = font(22, F_REG)
    line = f"{comma(stats['claims'])} claims from {stats['thinkers']} thinkers, {stats['years']}. Each one a nanopublication,"
    d.text((72, 178), line, font=sub, fill=MUTED)
    d.text((72, 208), "checked two ways: proof for the math, tests against open data for the rest.", font=sub, fill=MUTED)

    # Left column
    stats_y = [
        (5.4, "claims", stats["claims"], INK, "claims",
         f"{stats['thinkers']} thinkers, {stats['years']}",
         f"{comma(stats['neither'])} neither proved nor tested"),
        (6.5, "live", stats["live"], BLUE, "live as nanopubs",
         "Darwin, Thompson, Wolfram, math biology",
         "signed and on the production registry"),
        (7.6, "theorems", stats["theorems"], GOLD, "theorems",
         f"{stats['lean']} Lean-checked  ·  {stats['lit']} literature",
         "a proof is not a test"),
        (8.7, "tested", stats["tested"], GREEN, "tested against data",
         f"{stats['supports']} supports  ·  {stats['mixed']} mixed  ·  {stats['refutes']} refutes  ·  {stats['inconclusive']} inconclusive",
         f"{stats['organisms']} of them on organisms  ·  {stats['pending']} awaiting data"),
        (9.8, "taxa", stats["taxa"], (90, 96, 108), "animal taxa resolved",
         "merged inventory of what the sources name",
         ""),
    ]
    num_f = font(64, F_BLACK)
    lab_f = font(22, F_BOLD)
    det_f = font(16, F_REG)
    y = 278
    for start, _key, target, color, label, detail, detail2 in stats_y:
        a = appear(t, start, 0.4)
        if a <= 0:
            y += 132
            continue
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        n = counted(t, start, 0.85, target)
        ld.text((72, y), comma(n), font=num_f, fill=color)
        ld.text((300, y + 14), label, font=lab_f, fill=INK)
        ld.text((300, y + 44), detail, font=det_f, fill=MUTED)
        if detail2:
            ld.text((300, y + 68), detail2, font=det_f, fill=MUTED)
        fade_layer(im, layer, a)
        y += 132

    # Right table. Columns are right-aligned so the headers sit on the figures.
    rows_start = 11.0
    col_right = {"CLAIMS": 1396, "THEOREMS": 1544, "TESTED": 1672, "LIVE": 1808}
    if t >= rows_start - 0.15:
        rule_a = appear(t, rows_start, 0.35)
        rule = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(rule).line((748, 268, 748, 868), fill=RULE + (255,), width=2)
        fade_layer(im, rule, rule_a)
        col_f = font(13, F_MED)
        ha = appear(t, rows_start, 0.35)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.text((780, 276), "SOURCE", font=col_f, fill=MUTED)
        ld.text((1064, 276), "STANDING", font=col_f, fill=MUTED)
        for label, right in col_right.items():
            ld.text((right - text_width(col_f, label), 276), label, font=col_f, fill=MUTED)
        fade_layer(im, layer, ha)

    name_f = font(24, F_BOLD)
    sub_f = font(15, F_REG)
    val_f = font(24, F_BOLD)
    row_h = 96
    for i, g in enumerate(stats["groups"]):
        start = rows_start + 0.4 + i * 0.65
        a = appear(t, start, 0.4)
        if a <= 0:
            continue
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        y = 314 + i * row_h
        ld.text((780, y), g["name"], font=name_f, fill=INK)
        ld.text((780, y + 32), subtitle(g), font=sub_f, fill=MUTED)

        def cell(n, right, color):
            s = "·" if n == 0 else comma(n)
            col = FAINT if n == 0 else color
            ld.text((right - text_width(val_f, s), y + 2), s, font=val_f, fill=col)

        cell(g["n"], col_right["CLAIMS"], INK)
        cell(g["theorems"], col_right["THEOREMS"], GOLD)
        cell(g["tested"], col_right["TESTED"], GREEN)
        cell(g["live"], col_right["LIVE"], BLUE)
        fade_layer(im, layer, a)
        bar_p = appear(t, start + 0.12, 0.85)
        segs = [(k, g["segs"].get(k, 0)) for k, _, _ in SEGMENTS]
        rounded_bar(im, (1064, y + 10, 188, 18), segs, g["n"], bar_p * a)

    # Legend and the faithfulness line, under the rows.
    leg_a = appear(t, 16.0, 0.45)
    if leg_a > 0:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        note_f = font(14, F_REG)
        ld.text((780, 886), "The bar shows a proof when the claim has one, and the data verdict otherwise.", font=note_f, fill=MUTED)
        note = (f"Faithfulness gate: {stats['faith']} of {stats['tested']} checked, "
                f"{stats['not_rep']} not representative, {stats['contested']} contested")
        ld.text((780, 910), note, font=note_f, fill=MUTED)
        present = {k for g in stats["groups"] for k in g["segs"] if g["segs"][k]}
        rows = (
            ["lean", "lit", "partial", "refuted"],
            ["supports", "mixed", "refutes", "inconclusive", "untested"],
        )
        for row_i, keys in enumerate(rows):
            x, y = 780, 944 + row_i * 24
            for k in keys:
                if k not in present:
                    continue
                color, lab = SEG_COLOR[k], SEG_LABEL[k]
                ld.rounded_rectangle((x, y + 3, x + 14, y + 15), radius=3, fill=color)
                ld.text((x + 20, y), lab, font=note_f, fill=MUTED)
                x += 20 + text_width(note_f, lab) + 16
        fade_layer(im, layer, leg_a)

    # Footer
    foot = font(14, F_MED)
    d.line((72, 1004, W - 72, 1004), fill=RULE, width=2)
    d.text((72, 1022), "GITHUB.COM/FRACTASTICAL/DELPHI", font=foot, fill=MUTED)
    note = "A PROOF IS NOT EVIDENCE THAT ORGANISMS SATISFY IT;  A DATA TEST IS NOT A PROOF"
    d.text((W - 72 - text_width(foot, note), 1022), note, font=foot, fill=MUTED)
    return im


def blend(a, b, p):
    if p <= 0:
        return a
    if p >= 1:
        return b
    return Image.blend(a, b, p)


def frame_at(t, stats, seal):
    title = paint_title(t, seal)
    if t < 4.2:
        return title
    card = paint_card(t, stats, seal)
    if t < 5.3:
        return blend(title, card, appear(t, 4.2, 1.1))
    return card


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="write four stills and stop")
    args = ap.parse_args()
    stats = load()
    print(
        f"built {stats['built']}  claims {stats['claims']}  live {stats['live']}  "
        f"theorems {stats['theorems']} ({stats['lean']} lean, {stats['lit']} lit)  "
        f"tested {stats['tested']} ({stats['supports']}/{stats['mixed']}/{stats['refutes']}/{stats['inconclusive']})  "
        f"on organisms {stats['organisms']}  pending {stats['pending']}  "
        f"faith {stats['faith']} ({stats['not_rep']} not representative, {stats['contested']} contested)  "
        f"taxa {stats['taxa']}"
    )
    for g in stats["groups"]:
        print(f"  {g['name']:16} {g['n']:5} thm {g['theorems']:3} tested {g['tested']:3} live {g['live']:4}  {subtitle(g)}")
        print("    " + "  ".join(f"{k} {g['segs'].get(k, 0)}" for k, _, _ in SEGMENTS if g["segs"].get(k, 0)))

    seal = load_seal(512)
    if args.preview:
        out = Path(tempfile.gettempdir()) / "delphi-video-preview"
        out.mkdir(exist_ok=True)
        for t in (2.0, 9.0, 15.0, 24.0):
            im = frame_at(t, stats, seal).convert("RGB")
            im.save(out / f"t{t:.0f}.png")
            print("preview", out / f"t{t:.0f}.png")
        return

    tmp = Path(tempfile.mkdtemp(prefix="delphi-video-"))
    n = int(DURATION * FPS)
    print(f"rendering {n} frames at {FPS} fps")
    final = None
    for i in range(n):
        t = i / FPS
        im = frame_at(t, stats, seal).convert("RGB")
        im.save(tmp / f"f{i:04d}.png", optimize=False)
        final = im
        if i % 48 == 0:
            print(f"  {i}/{n}")
    final.save(OUT_PNG, optimize=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(FPS), "-i", str(tmp / "f%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17",
            "-movflags", "+faststart", str(OUT_MP4),
        ],
        check=True,
    )
    shutil.rmtree(tmp)
    print(OUT_MP4, OUT_MP4.stat().st_size)
    print(OUT_PNG, OUT_PNG.stat().st_size)


if __name__ == "__main__":
    main()
