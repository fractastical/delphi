#!/usr/bin/env python3
"""Draw a timeline card for every organism and two summary figures.

    python3 organisms/timeline.py            # all taxa -> organisms/images/timelines/<slug>.png
    python3 organisms/timeline.py columba-livia nautilus   # just these slugs
    python3 organisms/timeline.py --summary-only

Inputs: organisms/merged/timeline.json and organisms/images/manifest.json (both written by
`node organisms/images.mjs`). Each card shows the representative image, the Paleobiology
Database first/last-appearance range on a Phanerozoic axis with ICS period colours, and a
historical axis (1735-2030) with the year of formal description, the Darwin (1859) and
Thompson (1917) mentions, and the release years of the genome assemblies we hold.

Summary figures (organisms/images/):
  timeline-summary.png  fossil ranges of all ranged taxa grouped by class, with the most
                        mentioned taxa pictured at their first appearance, plus the historical
                        panel (descriptions and genome releases per decade).
  mosaic.jpg            every thumbnail, ordered by first appearance, with a period-colour stripe.

Needs matplotlib and Pillow only.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Rectangle
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MERGED = ROOT / "organisms" / "merged"
IMAGES = ROOT / "organisms" / "images"
CARDS = IMAGES / "timelines"

# ICS International Chronostratigraphic Chart periods (Ma) and colours.
PERIODS = [
    ("Cambrian", 538.8, 485.4, "#7FA056"), ("Ordovician", 485.4, 443.8, "#009270"),
    ("Silurian", 443.8, 419.2, "#B3E1B6"), ("Devonian", 419.2, 358.9, "#CB8C37"),
    ("Carboniferous", 358.9, 298.9, "#67A599"), ("Permian", 298.9, 251.9, "#F04028"),
    ("Triassic", 251.9, 201.4, "#812B92"), ("Jurassic", 201.4, 145.0, "#34B2C9"),
    ("Cretaceous", 145.0, 66.0, "#7FC64E"), ("Paleogene", 66.0, 23.03, "#FD9A52"),
    ("Neogene", 23.03, 2.58, "#FFE619"), ("Quaternary", 2.58, 0.0, "#F9F97F"),
]
PRECAMBRIAN = "#F74370"
GEO_MAX = 560.0   # left edge of the geological axis; older first appearances are clipped with a marker
HIST = (1735, 2030)
BOOKS = {"darwin-origin": ("Darwin, Origin", 1859, "#8B1A1A"), "thompson-growth-form": ("Thompson, Growth & Form", 1917, "#1F4E79")}
C_DESC, C_GENOME, C_RANGE, C_EXTINCT = "#444444", "#2A9D8F", "#3A3A3A", "#B22222"


def load():
    tl = json.loads((MERGED / "timeline.json").read_text())["taxa"]
    man = json.loads((IMAGES / "manifest.json").read_text())["images"]
    img = {m["slug"]: m for m in man if m.get("thumb_path")}
    return tl, img


def period_of(ma):
    if ma is None:
        return None
    for name, a, b, col in PERIODS:
        if b <= ma <= a:
            return name, col
    return ("Precambrian", PRECAMBRIAN) if ma > PERIODS[0][1] else ("Quaternary", PERIODS[-1][3])


def thumb(slug, img, size):
    """Square, letterboxed thumbnail as an RGB PIL image, or a grey placeholder."""
    m = img.get(slug)
    if m:
        try:
            im = Image.open(ROOT / m["thumb_path"])
            if im.mode in ("RGBA", "LA", "P"):   # flatten transparency onto white, not black
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.split()[3])
                im = bg
            return ImageOps.pad(im.convert("RGB"), (size, size), color=(245, 245, 245))
        except Exception:
            pass
    ph = Image.new("RGB", (size, size), (235, 235, 235))
    d = ImageDraw.Draw(ph)
    d.text((size // 2 - 20, size // 2 - 6), "no image", fill=(150, 150, 150))
    return ph


def draw_geo_axis(ax, ymin=0, ymax=1, labels=True, fontsize=7):
    ax.set_xlim(GEO_MAX, 0)
    for name, a, b, col in PERIODS:
        ax.add_patch(Rectangle((min(a, GEO_MAX), ymin), -(min(a, GEO_MAX) - b), ymax - ymin, color=col, alpha=0.35, lw=0))
        if labels and a - b > 20:
            ax.text((min(a, GEO_MAX) + b) / 2, ymax, name[:3] if a - b < 45 else name, ha="center", va="bottom", fontsize=fontsize, color="#333")
    ax.add_patch(Rectangle((GEO_MAX, ymin), -(GEO_MAX - PERIODS[0][1]), ymax - ymin, color=PRECAMBRIAN, alpha=0.35, lw=0))
    ax.set_ylim(ymin, ymax)
    ax.set_yticks([])
    for s in ("left", "right", "top"):
        ax.spines[s].set_visible(False)


def range_bar(ax, f, y, h, lw=0):
    """Draw first/last appearance range for one taxon at height y. Returns x of first appearance."""
    fa_max, fa_min = f["firstapp_max_ma"], f.get("firstapp_min_ma") or f["firstapp_max_ma"]
    la_max, la_min = f.get("lastapp_max_ma") or 0, f.get("lastapp_min_ma") or 0
    extant = f.get("is_extant") == "extant"
    end = 0 if extant else la_min
    col = C_RANGE if extant else C_EXTINCT
    x0 = min(fa_max, GEO_MAX)
    ax.add_patch(Rectangle((x0, y - h / 2), -(x0 - end), h, color=col, alpha=0.85, lw=lw))
    # Uncertainty in first and last appearance as lighter extensions.
    if fa_max > fa_min:
        ax.add_patch(Rectangle((x0, y - h / 2), -(x0 - fa_min), h, color="white", alpha=0.45, lw=0))
    if not extant and la_max > la_min:
        ax.add_patch(Rectangle((la_max, y - h / 2), -(la_max - la_min), h, color="white", alpha=0.45, lw=0))
    if fa_max > GEO_MAX:
        ax.plot([GEO_MAX], [y], marker="<", color=col, ms=5, clip_on=False)
    return x0


def card(t, img, out):
    f = t.get("fossil") or {}
    has_range = f.get("firstapp_max_ma") is not None
    fig = plt.figure(figsize=(12, 4.4), dpi=100)
    gs = GridSpec(2, 2, width_ratios=[1, 3.3], height_ratios=[1, 1], wspace=0.08, hspace=0.75, left=0.02, right=0.98, top=0.86, bottom=0.11)

    # --- image + name
    ax = fig.add_subplot(gs[:, 0])
    ax.imshow(thumb(t["slug"], img, 300))
    ax.axis("off")
    m = img.get(t["slug"])
    if m:
        credit = f"{m.get('author') or ''} · {m.get('license') or ''}".strip(" ·")
        ax.set_title(credit[:70], fontsize=6, color="#777", loc="left", pad=2)
    name = t["accepted_name"] + (f"  ({t['vernacular']})" if t.get("vernacular") else "")
    sub = " · ".join(x for x in [t.get("rank"), t.get("class"), f"{t['mention_count']} mention{'s' if t['mention_count'] != 1 else ''}"] if x)
    fig.suptitle(name, x=0.02, y=0.975, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.02, 0.905, sub, fontsize=8.5, color="#555")

    # --- geological axis
    ax = fig.add_subplot(gs[0, 1])
    draw_geo_axis(ax, 0, 1)
    if has_range:
        range_bar(ax, f, 0.5, 0.3)
        lab = f"{f.get('early_interval') or '?'} ({f['firstapp_max_ma']:g} Ma) → " + ("extant" if f.get("is_extant") == "extant" else f"{f.get('late_interval') or '?'} ({f.get('lastapp_min_ma', 0):g} Ma)")
        lab += f" · {f.get('n_occs', 0)} PBDB occurrences" + (f" · PBDB {f['pbdb_rank']} {f['pbdb_name']}" if f.get("pbdb_name") != t["accepted_name"] or f.get("pbdb_rank") != t.get("rank") else "")
        ax.text(GEO_MAX, -0.35, lab, fontsize=7, color="#333", va="top", ha="left", clip_on=False)
    else:
        ax.text(GEO_MAX / 2, 0.5, "no Paleobiology Database range for this name", ha="center", va="center", fontsize=8, color="#777")
    ax.set_xlabel("million years ago", fontsize=7, labelpad=1)
    ax.tick_params(labelsize=7, length=2)

    # --- historical axis
    ax = fig.add_subplot(gs[1, 1])
    ax.set_xlim(*HIST)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    for s in ("left", "right", "top"):
        ax.spines[s].set_visible(False)
    Y = 0.62
    ax.axhline(Y, color="#bbb", lw=1, zorder=0)
    for key, (label, yr, col) in BOOKS.items():
        hit = any(mn["project"] == key for mn in t.get("mentioned", []))
        ax.axvline(yr, color=col, lw=1.2 if hit else 0.6, ls="-" if hit else ":", alpha=1 if hit else 0.5)
        ax.text(yr, 1.0, label, rotation=0, ha="center", va="bottom", fontsize=6.5, color=col if hit else "#999")
        if hit:
            ax.plot(yr, Y, "o", color=col, ms=7, zorder=3)
    d = t.get("described") or {}
    if d.get("year"):
        ax.plot(d["year"], Y, marker="*", color=C_DESC, ms=11, zorder=3)
        ax.annotate(f"described {d['year']}\n{d.get('authorship') or ''}", (d["year"], Y), xytext=(0, -9), textcoords="offset points", ha="center", va="top", fontsize=6.5, color=C_DESC)
    gen_years = [g["year"] for g in t.get("genomes", [])]
    for g in t.get("genomes", []):
        ax.plot(g["year"], Y, marker="^", color=C_GENOME, ms=8, zorder=3)
    if gen_years:
        lv = sorted({(g["level"] or "assembly") for g in t["genomes"]})
        ax.annotate(f"genome{'s' if len(gen_years) > 1 else ''} {min(gen_years)}" + (f"–{max(gen_years)}" if len(set(gen_years)) > 1 else "") + f"\n{', '.join(lv)}", (min(gen_years), Y), xytext=(0, -9), textcoords="offset points", ha="center", va="top", fontsize=6.5, color=C_GENOME)
    ax.set_xticks(range(1750, 2030, 25))
    ax.tick_params(labelsize=7, length=2)
    ax.set_xlabel("year", fontsize=7, labelpad=1)

    fig.savefig(out)
    plt.close(fig)


def summary(tl, img, out):
    ranged = [t for t in tl if (t.get("fossil") or {}).get("firstapp_max_ma") is not None]
    by_class = {}
    for t in ranged:
        by_class.setdefault(t.get("class") or "unplaced", []).append(t)
    # Lanes: classes with >= 3 ranged taxa; the rest pooled.
    lanes = {k: v for k, v in by_class.items() if len(v) >= 3}
    other = [t for k, v in by_class.items() if len(v) < 3 for t in v]
    if other:
        lanes["other classes"] = other
    # Oldest first appearance at the top of the panel (row index n-1).
    order = sorted(lanes, key=lambda k: max(min(t["fossil"]["firstapp_max_ma"], GEO_MAX) for t in lanes[k]))

    n = len(order)
    fig = plt.figure(figsize=(16, 0.55 * n + 7), dpi=100)
    gs = GridSpec(2, 1, height_ratios=[0.55 * n, 4.2], hspace=0.18, left=0.11, right=0.985, top=0.95, bottom=0.08)

    # --- A: fossil ranges by class
    ax = fig.add_subplot(gs[0])
    draw_geo_axis(ax, -0.5, n - 0.5, fontsize=8)
    ax.set_xlim(GEO_MAX, -22)   # room for pictures of extant taxa at 0 Ma
    ax.set_xticks(range(0, int(GEO_MAX), 50))
    for yi, cls in enumerate(order):
        taxa = sorted(lanes[cls], key=lambda t: -t["fossil"]["firstapp_max_ma"])
        k = len(taxa)
        for j, t in enumerate(taxa):
            yy = yi - 0.38 + 0.76 * (j + 0.5) / k
            range_bar(ax, t["fossil"], yy, max(0.76 / k * 0.9, 0.02))
        # Pictures for the most-mentioned taxa in the lane, at first appearance.
        pics = [t for t in sorted(taxa, key=lambda t: -t["mention_count"]) if t["slug"] in img][:3]
        used = []
        for t in pics:
            x = min(t["fossil"]["firstapp_max_ma"], GEO_MAX)
            if any(abs(x - u) < 28 for u in used):
                continue
            used.append(x)
            ab = AnnotationBbox(OffsetImage(thumb(t["slug"], img, 64), zoom=0.62), (x, yi), frameon=True, pad=0.1, bboxprops=dict(edgecolor="white", lw=1), zorder=5)
            ax.add_artist(ab)
            ax.text(x, yi + 0.33, t["accepted_name"], fontsize=5.5, ha="center", va="bottom", color="#222", zorder=6, bbox=dict(facecolor="white", alpha=0.7, lw=0, pad=0.5))
        ax.text(GEO_MAX * 1.005, yi, f"{cls} ({k})", ha="right", va="center", fontsize=8)
    ax.set_yticks([])
    ax.set_xlabel("million years ago — Paleobiology Database first/last appearance per taxon (grey = extant, red = extinct; pictures mark the most-mentioned taxa in each class)", fontsize=8)
    ax.tick_params(labelsize=8)
    ax.set_title(f"Organisms Darwin (1859) and Thompson (1917) wrote about: {len(ranged)} of {len(tl)} taxa with a fossil range", fontsize=12, loc="left", pad=16)

    # --- B: historical panel
    ax = fig.add_subplot(gs[1])
    decades = list(range(HIST[0], HIST[1], 10))
    desc = [t["described"]["year"] for t in tl if (t.get("described") or {}).get("year")]
    gen = [g["year"] for t in tl for g in t.get("genomes", [])]
    ax.hist(desc, bins=decades + [HIST[1]], color=C_DESC, alpha=0.75, label=f"formal description of the taxon (GBIF authorship; {len(desc)} taxa)")
    ax.hist(gen, bins=decades + [HIST[1]], color=C_GENOME, alpha=0.85, label=f"NCBI genome assembly released ({len(gen)} assemblies)")
    for key, (label, yr, col) in BOOKS.items():
        nm = sum(1 for t in tl if any(mn["project"] == key for mn in t.get("mentioned", [])))
        ax.axvline(yr, color=col, lw=1.5)
        ax.text(yr, ax.get_ylim()[1] * 0.97, f"{label} {yr}\n{nm} taxa mentioned", ha="right" if key == "darwin-origin" else "left", va="top", fontsize=8, color=col)
    ax.set_xlim(*HIST)
    ax.set_xlabel("year", fontsize=8)
    ax.set_ylabel("taxa / assemblies per decade", fontsize=8)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
    ax.tick_params(labelsize=8)
    for s in ("right", "top"):
        ax.spines[s].set_visible(False)
    fig.savefig(out)
    plt.close(fig)


def mosaic(tl, img, out, cell=48, cols=40):
    have = [t for t in tl if t["slug"] in img]
    key = lambda t: -((t.get("fossil") or {}).get("firstapp_max_ma") or -1)
    have.sort(key=key)
    rows = -(-len(have) // cols)
    stripe = 6
    sheet = Image.new("RGB", (cols * cell, rows * (cell + stripe)), (255, 255, 255))
    for i, t in enumerate(have):
        x, y = (i % cols) * cell, (i // cols) * (cell + stripe)
        sheet.paste(thumb(t["slug"], img, cell), (x, y))
        p = period_of((t.get("fossil") or {}).get("firstapp_max_ma"))
        ImageDraw.Draw(sheet).rectangle([x, y + cell, x + cell - 1, y + cell + stripe - 1], fill=p[1] if p else (220, 220, 220))
    sheet.save(out, quality=82, optimize=True)
    return len(have), rows


def main(argv):
    tl, img = load()
    args = [a for a in argv if not a.startswith("--")]
    CARDS.mkdir(parents=True, exist_ok=True)
    if "--summary-only" not in argv:
        todo = [t for t in tl if not args or t["slug"] in args]
        for i, t in enumerate(todo):
            card(t, img, CARDS / f"{t['slug']}.png")
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(todo)} cards")
        print(f"cards: {len(todo)} -> {CARDS.relative_to(ROOT)}/")
    if not args:
        summary(tl, img, IMAGES / "timeline-summary.png")
        n, rows = mosaic(tl, img, IMAGES / "mosaic.jpg")
        print(f"summary: {IMAGES.relative_to(ROOT)}/timeline-summary.png; mosaic of {n} thumbnails in {rows} rows -> mosaic.jpg")


if __name__ == "__main__":
    main(sys.argv[1:])
