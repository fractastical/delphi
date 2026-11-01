#!/usr/bin/env python3
"""The project in sixty seconds, as one growing knowledge graph.

The idea is the "growth over time" replay on pkg.scienceoracle.com: every record is a node, nodes
arrive in order, and the colour of a node is what the record says about it. Here the nodes are the
claims in docs/claims.json. They arrive by source year (Aristotle to Levin), then the layers of
checking are drawn over them in the order the pipeline applies them:

    sources -> assessors -> proofs -> data tests -> publication -> closing card

Every number on screen is computed here from repo files: docs/claims.json (built by
scripts/site/build-claim-graph.mjs), test-data/claim-tests/**/result.json (dataset sources and
pre-registered tests), test-data/organisms/merged/taxa.json, the Lean registry through
lib/lean-source.mjs, and the swarm snapshot table in chats/SWARM_COORDINATION.md.

Writes assets/delphi-in-sixty-seconds.mp4 and a poster still beside it.

    python3 scripts/site/build-graph-video.py              # full render, 1920x1080, 24 fps, 60 s
    python3 scripts/site/build-graph-video.py --preview    # a handful of stills in /tmp, no video
    python3 scripts/site/build-graph-video.py --fast       # 12 fps, no supersampling, for iteration

Needs ffmpeg on PATH and Pillow. Renders frames in parallel with multiprocessing.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CLAIMS_PATH = ROOT / "docs" / "claims.json"
TAXA_PATH = ROOT / "test-data" / "organisms" / "merged" / "taxa.json"
TESTS = ROOT / "test-data" / "claim-tests"
SWARM_MD = ROOT / "chats" / "SWARM_COORDINATION.md"
LOGO = ROOT / "assets" / "logo.svg"
OUT_MP4 = ROOT / "assets" / "delphi-in-sixty-seconds.mp4"
OUT_PNG = ROOT / "assets" / "delphi-in-sixty-seconds.png"

W, H = 1920, 1080
FPS = 24
DURATION = 60.0
SS = 2  # supersampling factor; set by --fast

# Fonts. Georgia and Menlo ship with macOS; Inter is vendored beside the deck.
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia.ttf"
GEORGIA_B = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
GEORGIA_I = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
MENLO = "/System/Library/Fonts/Menlo.ttc"
INTER = ROOT / "assets" / "deck" / "fonts" / "Inter-Regular.ttf"
INTER_M = ROOT / "assets" / "deck" / "fonts" / "Inter-Medium.ttf"

# Palette: warm paper and ink, the PKG viewer's teal for edges, the claim-graph verdict colours.
PAPER = (246, 243, 236)
PAPER2 = (252, 250, 246)
INK = (29, 36, 51)
INK2 = (83, 101, 130)
INK3 = (140, 150, 168)
GRID = (222, 217, 205)
RULE = (214, 208, 195)
NODE = (198, 193, 182)        # a claim nobody has scored, proved or tested
EDGE = (74, 138, 122)         # teal, source edges
GOLD = (201, 150, 38)
BLUE = (47, 111, 237)
SUP = (46, 158, 84)
MIX = (222, 170, 60)
REF = (196, 72, 88)
INC = (132, 144, 164)
TRUTH = [  # assessor p(true): elicited opinions, binned like the viewer's legend
    (0.9, (31, 122, 77), "≥ 0.9"),
    (0.7, (111, 170, 108), "0.7 – 0.9"),
    (0.4, (222, 170, 60), "0.4 – 0.7"),
    (-1.0, (196, 72, 88), "< 0.4"),
]
VERDICT = {"supports": SUP, "mixed": MIX, "refutes": REF, "inconclusive": INC}

GOLDEN = 2.399963229728653

# Timeline (seconds).
T_TITLE_OUT = 3.6
T_GROW0, T_GROW1 = 4.6, 17.2
T_ASSESS, T_SWEEP0, T_SWEEP1 = 18.0, 18.6, 24.6
T_PROOF, T_MATH0, T_MATH1, T_THM0, T_THM1 = 27.0, 27.6, 29.2, 29.6, 32.4
T_DATA, T_DS0, T_DS1, T_TEST0, T_TEST1 = 36.0, 36.4, 38.0, 37.6, 44.6
T_PUB, T_WAVE0, T_WAVE1, T_SWARM = 47.0, 47.6, 52.0, 51.0
T_CLOSE = 54.6

# Source hubs: name, thinkers (None = every thinker not named elsewhere), centre in 1x pixels.
HUBS = [
    ("Aristotle", {"Aristotle"}, (350, 600)),
    ("Mathematical biology", None, (560, 250)),
    ("D'Arcy Thompson", {"D'Arcy Wentworth Thompson"}, (850, 330)),
    ("Darwin", {"Charles Darwin"}, (820, 860)),
    ("Wolfram", {"Stephen Wolfram"}, (1190, 370)),
    ("Levin", {"Michael Levin"}, (1190, 800)),
]
SPACING = 8.0
CENTER = (800, 590)
ASSESSOR_POS = [(700, 540), (905, 540)]
LEAN_POS = (800, 612)
GRAPH_RIGHT = 1500
COL_X = 1544
LABEL_W = 165  # width reserved for a dataset label, 1x px

# Dataset families: keyword rules over the `source`/`name` of each dataset in a result.json.
FAMILIES = [
    ("GBIF", r"\bGBIF\b"),
    ("NCBI GenBank", r"GenBank|\bNCBI\b|RefSeq|SRA\b"),
    ("Paleobiology Database", r"Paleobiology Database|\bPBDB\b"),
    ("Open Tree of Life", r"Open Tree of Life"),
    ("NHANES", r"NHANES"),
    ("ICES DATRAS", r"\bICES\b|DATRAS"),
    ("Kew WCVP", r"WCVP|Vascular Plants|Kew\b"),
    ("Wikimedia micrographs", r"Wikimedia"),
    ("AVONET", r"AVONET"),
    ("Gene Ontology", r"Gene Ontology|GO annotations|go-basic"),
    ("OEIS", r"\bOEIS\b"),
    ("Dryad", r"Dryad|^Data from:|Data associated with"),
    ("Simulations & code", r"simulation|cellular automa|\bcode\b|SPM12?\b|spm_|\.m\b|totalistic|runs of|Cook, M"),
]
MAX_FAMILIES = 12


# ----------------------------------------------------------------------------- helpers

def ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_io(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def appear(t, start, dur=0.45):
    return ease((t - start) / dur)


def counted(t, start, dur, target):
    p = appear(t, start, dur)
    return target if p >= 1 else int(target * p)


def comma(n):
    return f"{n:,}"


def year_label(y):
    y = int(round(y))
    return f"c. {-y} BC" if y < 0 else str(y)


def year_span(years):
    years = [y for y in years if isinstance(y, int)]
    lo, hi = min(years), max(years)
    return year_label(lo) if lo == hi else f"{year_label(lo)}–{year_label(hi)}"


def mix(a, b, p):
    p = max(0.0, min(1.0, p))
    return tuple(int(round(a[i] + (b[i] - a[i]) * p)) for i in range(3))


def truth_color(p):
    if p is None:
        return NODE
    for lo, col, _ in TRUTH:
        if p >= lo:
            return col
    return NODE


_FONTS = {}


def font(path, size):
    key = (str(path), int(size * SS))
    f = _FONTS.get(key)
    if f is None:
        f = ImageFont.truetype(str(path), int(size * SS))
        _FONTS[key] = f
    return f


def P(v):
    return v * SS


# ----------------------------------------------------------------------------- data

def family_of(text, data_kind):
    for name, rx in FAMILIES:
        if re.search(rx, text, re.I):
            return name
    if data_kind == "computational":
        return "Simulations & code"
    return "Other open data"


def dataset_family(claim):
    dt = claim.get("data_test") or {}
    path = dt.get("path")
    rec = None
    if path and (ROOT / path).exists():
        try:
            rec = json.loads((ROOT / path).read_text())
        except json.JSONDecodeError:
            rec = None
    kind = dt.get("data_kind") or claim.get("evidence_kind")
    if rec:
        ds = rec.get("datasets") or rec.get("planned_datasets") or []
        if isinstance(ds, dict):
            ds = [ds]
        for d in ds:
            if not isinstance(d, dict):
                continue
            text = " ".join(str(d.get(k) or "") for k in ("source", "provider", "name", "title", "id", "url"))
            fam = family_of(text, kind)
            if fam not in ("Other open data",):
                return fam
    return "Simulations & code" if kind == "computational" else "Other open data"


def lean_registry():
    js = ("import(process.argv[1]).then(m=>{const l=m.listLaws().laws;"
          "console.log(JSON.stringify({n:l.length,accepted:l.filter(x=>x.status==='accepted').length}))})")
    out = subprocess.run(["node", "-e", js, str(ROOT / "lib" / "lean-source.mjs")], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def swarm_snapshot():
    md = SWARM_MD.read_text()
    def row(label):
        m = re.search(rf"^\| {re.escape(label)}[^|]*\| *([\d,]+)", md, re.M)
        if not m:
            raise SystemExit(f"SWARM_COORDINATION.md: no snapshot row starting {label!r}")
        return int(m.group(1).replace(",", ""))
    head = re.search(r"^### Snapshot: (\S+)", md, re.M)
    return {
        "chats": row("Local Cursor chats"),
        "subagents": row("Subagents launched"),
        "cloud": row("Cloud agents launched"),
        "date": head.group(1) if head else "undated",
    }


def load():
    doc = json.loads(CLAIMS_PATH.read_text())
    claims = doc["claims"]
    named = set().union(*(s for _, s, _ in HUBS if s))

    nodes = []
    hubs = []
    for hi, (name, thinkers, (cx, cy)) in enumerate(HUBS):
        cs = [c for c in claims if (c["thinker"] not in named if thinkers is None else c["thinker"] in thinkers)]
        cs.sort(key=lambda c: (c.get("year") or 0, c["id"]))
        phase = hi * 1.7
        for i, c in enumerate(cs):
            r = SPACING * math.sqrt(i + 0.6)
            th = i * GOLDEN + phase
            nodes.append({
                "id": c["id"], "hub": hi, "year": c.get("year"),
                "x": cx + r * math.cos(th), "y": cy + r * math.sin(th),
                "truth": c.get("truth"), "math": bool(c.get("math")), "theorem": bool(c.get("theorem")),
                "proof": c.get("proof"), "evidence": c.get("evidence"),
                "live": c.get("registry") == "production" and not c.get("draft"),
                "family": dataset_family(c) if c.get("evidence") else None,
            })
        hubs.append({
            "name": name, "cx": cx, "cy": cy, "n": len(cs),
            "radius": SPACING * math.sqrt(len(cs) + 0.6),
            "span": year_span([c.get("year") for c in cs]),
            "thinkers": len({c["thinker"] for c in cs}),
            "works": len({c.get("work") for c in cs}),
        })
    if len(nodes) != len(claims):
        raise SystemExit("hubs do not partition the claims")

    # Arrival order: by source year, then hub, then position in the disc (so discs grow outward).
    order = sorted(range(len(nodes)), key=lambda k: (nodes[k]["year"] or 0, nodes[k]["hub"], k))
    N = len(nodes)
    for rank, k in enumerate(order):
        nodes[k]["t_in"] = T_GROW0 + (T_GROW1 - T_GROW0) * rank / N
        nodes[k]["rank"] = rank
    assessed = [k for k in order if nodes[k]["truth"] is not None]
    for j, k in enumerate(assessed):
        nodes[k]["a_rank"] = j
    maths = [k for k in order if nodes[k]["math"]]
    for j, k in enumerate(maths):
        nodes[k]["t_math"] = T_MATH0 + (T_MATH1 - T_MATH0) * j / max(1, len(maths))
    thms = [k for k in order if nodes[k]["theorem"]]
    for j, k in enumerate(thms):
        nodes[k]["t_thm"] = T_THM0 + (T_THM1 - T_THM0) * j / max(1, len(thms))
    tested = [k for k in order if nodes[k]["evidence"]]
    for j, k in enumerate(tested):
        nodes[k]["t_test"] = T_TEST0 + (T_TEST1 - T_TEST0) * j / max(1, len(tested))
    for n in nodes:
        n["d_center"] = math.hypot(n["x"] - CENTER[0], n["y"] - CENTER[1])

    # Dataset families on a ring around the graph, most used first, folded to MAX_FAMILIES.
    fam_count = Counter(nodes[k]["family"] for k in tested)
    keep = [f for f, _ in fam_count.most_common() if f != "Other open data"][:MAX_FAMILIES - 1]
    for k in tested:
        if nodes[k]["family"] not in keep:
            nodes[k]["family"] = "Other open data"
    fam_count = Counter(nodes[k]["family"] for k in tested)
    fams = [f for f, _ in fam_count.most_common()]
    families = place_families(fams, fam_count, hubs)
    fam_index = {f["name"]: i for i, f in enumerate(families)}
    for k in tested:
        nodes[k]["fam_i"] = fam_index[nodes[k]["family"]]
    for j, k in enumerate(tested):
        families[nodes[k]["fam_i"]].setdefault("t_in", T_DS0 + (T_DS1 - T_DS0) * nodes[k]["fam_i"] / len(families))

    verdicts = Counter(nodes[k]["evidence"] for k in tested)
    assessors = sorted({a["assessor"] for c in claims for a in (c.get("truth_by") or [])})
    if len(assessors) != 2:
        raise SystemExit(f"expected two truth assessors, found {assessors}")

    pending = 0
    for dirpath, _, filenames in os.walk(TESTS):
        if "result.json" in filenames:
            try:
                if json.loads(Path(dirpath, "result.json").read_text()).get("status") == "preregistered":
                    pending += 1
            except json.JSONDecodeError:
                pass

    reg = lean_registry()
    stats = {
        "built": doc.get("built") or "",
        "claims": N, "thinkers": len({c["thinker"] for c in claims}), "works": len({c.get("work") for c in claims}),
        "span": year_span([c.get("year") for c in claims]),
        "assessed": len(assessed), "assessors": assessors,
        "math": len(maths), "theorems": len(thms),
        "lean": sum(1 for k in thms if nodes[k]["proof"] == "lean"),
        "lit": sum(1 for k in thms if nodes[k]["proof"] == "literature"),
        "laws": reg["n"], "laws_accepted": reg["accepted"],
        "tested": len(tested), **{v: verdicts.get(v, 0) for v in VERDICT},
        "organisms": sum(1 for c in claims if c.get("evidence") and c.get("evidence_kind") == "biological"),
        "pending": pending,
        "live": sum(1 for n in nodes if n["live"]),
        "test_registry": sum(1 for c in claims if c.get("registry") == "test" and not c.get("draft")),
        "neither": sum(1 for c in claims if c.get("verification") == "untested" and not c.get("evidence")),
        "taxa": len(json.loads(TAXA_PATH.read_text())),
        "swarm": swarm_snapshot(),
    }
    if stats["tested"] != sum(stats[v] for v in VERDICT):
        raise SystemExit("verdicts do not add up to tested claims")
    if stats["lean"] + stats["lit"] != stats["theorems"]:
        raise SystemExit("Lean and literature proofs do not add up to theorems")
    return stats, nodes, hubs, families


def hub_label_box(h):
    return (h["cx"] - 115, h["cy"] - h["radius"] - 52, h["cx"] + 115, h["cy"] - h["radius"] - 6)


def boxes_overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def family_label_box(x, y):
    if x > CENTER[0]:
        return (x + 10, y - 9, x + 10 + LABEL_W, y + 9)
    return (x - 10 - LABEL_W, y - 9, x - 10, y + 9)


def place_families(names, counts, hubs):
    """Dataset nodes on an ellipse around the graph. Each is nudged in angle, then outward, until its
    node and its label are clear of every hub disc, every hub label and every dataset already placed."""
    out = []
    n = len(names)
    cx, cy = 780, 590
    hub_boxes = [hub_label_box(h) for h in hubs] + [(36, 920, 380, 1060)]  # last box: the legend
    for i, name in enumerate(names):
        th0 = -math.pi / 2 + 2 * math.pi * (i + 0.5) / n
        best = None
        for step in range(40):
            rx, ry = 540 + 9 * step, 395 + 7 * step
            for da in (0, 0.06, -0.06, 0.12, -0.12, 0.18, -0.18, 0.25, -0.25, 0.33, -0.33):
                th = th0 + da
                x, y = cx + rx * math.cos(th), cy + ry * math.sin(th)
                lb = family_label_box(x, y)
                if not (lb[0] > 30 and lb[2] < GRAPH_RIGHT - 20 and 118 < y < H - 30):
                    continue
                if any(math.hypot(x - h["cx"], y - h["cy"]) < h["radius"] + 34 for h in hubs):
                    continue
                if any(boxes_overlap(lb, hb) for hb in hub_boxes):
                    continue
                # The label must not lie across a disc either.
                if any(math.hypot(px - h["cx"], y - h["cy"]) < h["radius"] + 12 for h in hubs for px in (lb[0], (lb[0] + lb[2]) / 2, lb[2])):
                    continue
                if any(boxes_overlap(lb, family_label_box(o["x"], o["y"])) or math.hypot(x - o["x"], y - o["y"]) < 40 for o in out):
                    continue
                best = (x, y)
                break
            if best:
                break
        if not best:
            best = (cx + 540 * math.cos(th0), cy + 395 * math.sin(th0))
        out.append({"name": name, "x": best[0], "y": best[1], "n": counts[name]})
    return out


# ----------------------------------------------------------------------------- seal

def load_seal(size):
    png_dir = Path(tempfile.gettempdir())
    subprocess.run(["qlmanage", "-t", "-s", "1024", "-o", str(png_dir), str(LOGO)], check=True, capture_output=True)
    im = Image.open(png_dir / "logo.svg.png").convert("RGBA")
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if a > 20 and not (r > 248 and g > 248 and b > 248):
                xs.append(x)
                ys.append(y)
    im = im.crop((min(xs), min(ys), max(xs) + 2, max(ys) + 2))
    # qlmanage paints the SVG's transparent background white; knock it out so the seal sits on paper.
    import numpy as np
    arr = np.array(im)
    white = (arr[..., :3] > 236).all(axis=-1)
    arr[white, 3] = 0
    im = Image.fromarray(arr)
    return im.resize((size, size), Image.Resampling.LANCZOS)


# ----------------------------------------------------------------------------- scene state

class Scene:
    def __init__(self, stats, nodes, hubs, families, seal, year_track):
        self.stats, self.nodes, self.hubs, self.families, self.seal = stats, nodes, hubs, families, seal
        self.year_track = year_track

    # Camera: a slow push during growth, then a slow drift out. Positions are in graph space.
    def cam(self, t):
        if t < T_GROW1:
            k = 1.10 - 0.10 * ease_io((t - T_GROW0 + 1.0) / (T_GROW1 - T_GROW0 + 1.0))
        else:
            k = 1.0 + 0.035 * ease_io((t - T_GROW1) / (T_CLOSE - T_GROW1))
        return k

    def xy(self, x, y, k):
        return (P(CENTER[0] + (x - CENTER[0]) * k), P(CENTER[1] + (y - CENTER[1]) * k))


def node_fill(n, t):
    """Fill colour: a proof takes the node when it has one, then a data verdict, then the assessor score."""
    if n["theorem"] and t >= n.get("t_thm", 1e9):
        return GOLD
    if n["evidence"] and t >= n.get("t_test", 1e9):
        return VERDICT[n["evidence"]]
    if n["truth"] is not None and "a_rank" in n:
        s = sweep_index(t, None)
        if s is not None and s >= n["a_rank"]:
            return truth_color(n["truth"])
    return NODE


_SWEEP_N = None


def sweep_index(t, n_assessed):
    global _SWEEP_N
    if n_assessed is not None:
        _SWEEP_N = n_assessed
    if t < T_SWEEP0:
        return None
    return _SWEEP_N * ease_io((t - T_SWEEP0) / (T_SWEEP1 - T_SWEEP0))


# ----------------------------------------------------------------------------- painting

def paint_paper(im):
    d = ImageDraw.Draw(im)
    step = 44
    for y in range(100, H, step):
        for x in range(28, GRAPH_RIGHT, step):
            d.ellipse((P(x) - SS * 0.6, P(y) - SS * 0.6, P(x) + SS * 0.6, P(y) + SS * 0.6), fill=GRID)
    d.line((P(GRAPH_RIGHT + 18), P(100), P(GRAPH_RIGHT + 18), P(H - 40)), fill=RULE, width=SS)


def paint_header(d, t, sc):
    mono = font(MENLO, 13)
    d.text((P(48), P(40)), "DELPHI  ·  CANDIDATE LAWS OF BIOLOGY", font=mono, fill=INK2)
    s = f"GRAPH BUILT {sc.stats['built']}  ·  DELPHIBIO.ORG"
    d.text((P(W - 48), P(40)), s, font=mono, fill=INK3, anchor="ra")
    d.line((P(48), P(70), P(W - 48), P(70)), fill=RULE, width=SS)
    # Chapter title, left.
    chapters = [
        (T_GROW0 - 0.4, "Sources", "one node per claim, arriving by the year it was written"),
        (T_ASSESS, "Assessment", "two assessors from different providers score every claim"),
        (T_PROOF, "Proof", "the mathematical claims, and the ones that are proved"),
        (T_DATA, "Data", "pre-registered tests against open datasets"),
        (T_PUB, "Publication", "every claim, assessment and test as a signed nanopublication"),
    ]
    cur = None
    for i, (start, title, sub) in enumerate(chapters):
        nxt = chapters[i + 1][0] if i + 1 < len(chapters) else T_CLOSE
        if start <= t < nxt:
            cur = (start, title, sub, nxt)
    if cur:
        start, title, sub, nxt = cur
        a = appear(t, start, 0.5) * (1 - appear(t, nxt - 0.35, 0.35))
        col = mix(PAPER, INK, a)
        col2 = mix(PAPER, INK2, a)
        d.text((P(48), P(86)), title, font=font(GEORGIA, 40), fill=col)
        d.text((P(48 + 8 + font(GEORGIA, 40).getlength(title) / SS), P(104)), sub, font=font(GEORGIA_I, 19), fill=col2)
    # Year ticker during growth, right of the graph region.
    if T_GROW0 - 0.6 < t < T_GROW1 + 1.6:
        a = appear(t, T_GROW0 - 0.6, 0.6) * (1 - appear(t, T_GROW1 + 0.8, 0.8))
        y = sc.year_track(t)
        d.text((P(GRAPH_RIGHT - 12), P(84)), year_label(y), font=font(GEORGIA, 54), fill=mix(PAPER, INK, a), anchor="ra")


def paint_graph(im, d, t, sc):
    k = sc.cam(t)
    nodes = sc.nodes
    rad = P(3.1)
    # Source edges: claim -> hub centre, teal ink, faint.
    for n in nodes:
        a = appear(t, n["t_in"], 0.5)
        if a <= 0:
            continue
        h = sc.hubs[n["hub"]]
        x1, y1 = sc.xy(n["x"], n["y"], k)
        x0, y0 = sc.xy(h["cx"], h["cy"], k)
        d.line((x0, y0, x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), fill=mix(PAPER, EDGE, 0.22 * a), width=SS)
    # Assessor edges: the sweep lights each assessed claim's two edges, then they settle faint.
    s = sweep_index(t, None)
    if s is not None:
        apos = [sc.xy(*p, k) for p in ASSESSOR_POS]
        for n in nodes:
            j = n.get("a_rank")
            if j is None or j > s:
                continue
            glow = math.exp(-(s - j) / 70.0)
            a = 0.035 + 0.55 * glow
            x1, y1 = sc.xy(n["x"], n["y"], k)
            col = mix(PAPER, mix(INK2, truth_color(n["truth"]), glow), a)
            for ax, ay in apos:
                d.line((ax, ay, x1, y1), fill=col, width=SS)
    # Lean edges: proved-in-Lean claims to the Lean node, gold.
    if t >= T_THM0:
        lx, ly = sc.xy(*LEAN_POS, k)
        for n in nodes:
            if n["proof"] != "lean":
                continue
            a = appear(t, n["t_thm"], 0.6)
            if a <= 0:
                continue
            x1, y1 = sc.xy(n["x"], n["y"], k)
            d.line((lx, ly, lx + (x1 - lx) * a, ly + (y1 - ly) * a), fill=mix(PAPER, GOLD, 0.55), width=SS)
    # Dataset edges: tested claim -> its dataset family, coloured by verdict.
    if t >= T_TEST0:
        fpos = [sc.xy(f["x"], f["y"], k) for f in sc.families]
        for n in nodes:
            if not n["evidence"]:
                continue
            a = appear(t, n["t_test"], 0.6)
            if a <= 0:
                continue
            fx, fy = fpos[n["fam_i"]]
            x1, y1 = sc.xy(n["x"], n["y"], k)
            d.line((fx, fy, fx + (x1 - fx) * a, fy + (y1 - fy) * a), fill=mix(PAPER, VERDICT[n["evidence"]], 0.5), width=SS)
    # Publication wave.
    wave_r = None
    if T_WAVE0 <= t:
        wave_r = 1000 * ease((t - T_WAVE0) / (T_WAVE1 - T_WAVE0))
        if t < T_WAVE1 + 0.4:
            cx, cy = sc.xy(*CENTER, k)
            rr = P(wave_r * k)
            a = 1 - appear(t, T_WAVE1 - 0.2, 0.6)
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=mix(PAPER, INK, 0.35 * a), width=SS)
    # Nodes.
    for n in nodes:
        a = appear(t, n["t_in"], 0.5)
        if a <= 0:
            continue
        x, y = sc.xy(n["x"], n["y"], k)
        r = rad * (0.2 + 0.8 * a) * (1 + 0.9 * (1 - a))
        fill = node_fill(n, t)
        outline = None
        width = SS
        if n["math"] and t >= n.get("t_math", 1e9):
            outline = BLUE
            r2 = rad * 1.45 * appear(t, n["t_math"], 0.5)
            d.ellipse((x - r2, y - r2, x + r2, y + r2), outline=mix(PAPER, BLUE, 0.9), width=SS)
        if wave_r is not None and n["live"] and n["d_center"] <= wave_r:
            outline = INK
        if n["theorem"] and t >= n.get("t_thm", 1e9):
            pulse = 1 - appear(t, n["t_thm"], 0.8)
            r = r * (1 + 0.8 * pulse)
        if n["evidence"] and t >= n.get("t_test", 1e9):
            pulse = 1 - appear(t, n["t_test"], 0.8)
            r = r * (1 + 0.8 * pulse)
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=width)
    # Hub centres and labels.
    name_f, sub_f = font(GEORGIA, 21), font(MENLO, 11)
    for h in sc.hubs:
        first = min(n["t_in"] for n in nodes if sc.hubs[n["hub"]] is h)
        a = appear(t, first, 0.6)
        if a <= 0:
            continue
        x, y = sc.xy(h["cx"], h["cy"], k)
        r = P(4.5)
        d.ellipse((x - r, y - r, x + r, y + r), fill=PAPER2, outline=mix(PAPER, INK, a), width=SS)
        ly = sc.xy(h["cx"], h["cy"] - h["radius"] - 50, k)[1]
        d.text((x, ly), h["name"], font=name_f, fill=mix(PAPER, INK, a), anchor="ma")
        n_now = sum(1 for n in nodes if sc.hubs[n["hub"]] is h and t >= n["t_in"])
        extra = f"  ·  {h['thinkers']} thinkers" if h["thinkers"] > 1 else ""
        d.text((x, ly + P(26)), f"{h['span']}  ·  {n_now} claims{extra}", font=sub_f, fill=mix(PAPER, INK2, a), anchor="ma")
    # Assessor nodes.
    if t >= T_ASSESS:
        a = appear(t, T_ASSESS + 0.2, 0.6)
        for (px, py), name in zip(ASSESSOR_POS, sc.stats["assessors"]):
            x, y = sc.xy(px, py, k)
            r = P(9) * a
            d.ellipse((x - r, y - r, x + r, y + r), fill=mix(PAPER, INK, a))
            d.text((x, y + P(16)), name, font=font(MENLO, 12), fill=mix(PAPER, INK, a), anchor="ma")
            d.text((x, y + P(32)), "assessor", font=font(MENLO, 10), fill=mix(PAPER, INK3, a), anchor="ma")
    # Lean node.
    if t >= T_THM0 - 0.4:
        a = appear(t, T_THM0 - 0.4, 0.6)
        x, y = sc.xy(*LEAN_POS, k)
        r = P(10) * a
        d.ellipse((x - r, y - r, x + r, y + r), fill=mix(PAPER, GOLD, a), outline=mix(PAPER, INK, a), width=SS)
        d.text((x, y + P(17)), "Lean 4 + Mathlib", font=font(MENLO, 12), fill=mix(PAPER, INK, a), anchor="ma")
        n_lean = sum(1 for n in nodes if n["proof"] == "lean" and t >= n["t_thm"])
        d.text((x, y + P(33)), f"{n_lean} claims machine-checked", font=font(MENLO, 10), fill=mix(PAPER, INK3, a), anchor="ma")
    # Dataset family nodes (squares).
    if t >= T_DS0:
        for f in sc.families:
            a = appear(t, f["t_in"], 0.6)
            if a <= 0:
                continue
            x, y = sc.xy(f["x"], f["y"], k)
            r = P(6) * a
            d.rounded_rectangle((x - r, y - r, x + r, y + r), radius=P(1.5), fill=PAPER2, outline=mix(PAPER, INK, a), width=SS)
            n_now = sum(1 for n in nodes if n["evidence"] and n.get("fam_i") == sc.families.index(f) and t >= n["t_test"])
            label = f["name"] if n_now == 0 else f"{f['name']}  ·  {n_now}"
            anchor = "la" if f["x"] > CENTER[0] else "ra"
            dx = P(12) if f["x"] > CENTER[0] else -P(12)
            d.text((x + dx, y - P(7)), label, font=font(MENLO, 11), fill=mix(PAPER, INK, a), anchor=anchor)


def ledger_rows(t, sc):
    """The right-hand column: a row per chapter, each number counted up when its chapter starts."""
    st, nodes = sc.stats, sc.nodes
    rows = []
    n_in = sum(1 for n in nodes if t >= n["t_in"])
    rows.append((T_GROW0 - 0.2, "SOURCES", n_in, INK, "claims",
                 [f"{st['thinkers']} thinkers  ·  {st['works']} works", st["span"],
                  f"{comma(st['neither'])} neither proved nor tested"]))
    if t >= T_ASSESS:
        s = sweep_index(t, None)
        n_a = 0 if s is None else min(st["assessed"], int(s) + 1)
        rows.append((T_ASSESS, "ASSESSED", n_a, INK2, "claims scored",
                     ["  ·  ".join(a for a in st["assessors"]), "p(true) is an elicited opinion, not a verdict",
                      "assessor is never builder"]))
    if t >= T_PROOF:
        n_m = sum(1 for n in nodes if n["math"] and t >= n.get("t_math", 1e9))
        n_t = sum(1 for n in nodes if n["theorem"] and t >= n.get("t_thm", 1e9))
        n_l = sum(1 for n in nodes if n["proof"] == "lean" and t >= n.get("t_thm", 1e9))
        rows.append((T_PROOF, "PROVED", n_t, GOLD, "theorems",
                     [f"of {n_m} mathematical claims", f"{n_l} Lean-checked  ·  {n_t - n_l} in the literature",
                      f"{st['laws']} Lean laws registered, {st['laws_accepted']} accepted"]))
    if t >= T_DATA:
        tested_now = [n for n in nodes if n["evidence"] and t >= n.get("t_test", 1e9)]
        v = Counter(n["evidence"] for n in tested_now)
        rows.append((T_DATA, "TESTED", len(tested_now), SUP, "against data",
                     [f"{v['supports']} supports  ·  {v['mixed']} mixed  ·  {v['refutes']} refutes",
                      f"{v['inconclusive']} inconclusive  ·  {st['organisms']} on organism data",
                      f"{st['pending']} pre-registered, awaiting data"]))
    if t >= T_PUB:
        wave_r = 1000 * ease((t - T_WAVE0) / (T_WAVE1 - T_WAVE0)) if t >= T_WAVE0 else 0
        n_live = sum(1 for n in nodes if n["live"] and n["d_center"] <= wave_r)
        rows.append((T_PUB, "PUBLISHED", n_live, BLUE, "live nanopublications",
                     [f"{comma(st['test_registry'])} more on the test registry",
                      f"{comma(st['taxa'])} animal taxa resolved to external IDs",
                      "signed, citable, never deleted"]))
    if t >= T_SWARM:
        sw = st["swarm"]
        rows.append((T_SWARM, "BUILT BY", sw["chats"], INK2, "agent sessions",
                     [f"{sw['subagents']} subagents  ·  {sw['cloud']} cloud agents",
                      f"snapshot {sw['date']} (SWARM_COORDINATION.md)",
                      "coordinated through files, not chat"]))
    return rows


def paint_column(d, t, sc):
    x = P(COL_X)
    y = 96
    lab_f, num_f, unit_f, det_f = font(MENLO, 11), font(GEORGIA, 38), font(GEORGIA_I, 16), font(INTER, 12.5)
    for start, label, num, color, unit, details in ledger_rows(t, sc):
        a = appear(t, start, 0.5)
        if a <= 0:
            continue
        d.text((x, P(y)), label, font=lab_f, fill=mix(PAPER, INK3, a))
        s = comma(num)
        d.text((x, P(y + 15)), s, font=num_f, fill=mix(PAPER, color, a))
        d.text((x + num_f.getlength(s) + P(9), P(y + 35)), unit, font=unit_f, fill=mix(PAPER, INK2, a))
        yy = y + 64
        for line in details:
            d.text((x, P(yy)), line, font=det_f, fill=mix(PAPER, INK2, a))
            yy += 18
        y = yy + 20
    # Legend for the node colours, bottom-left of the graph, once there is something to explain.
    if t >= T_SWEEP0 + 0.5:
        a = appear(t, T_SWEEP0 + 0.5, 0.6)
        x = P(48)
        ly = H - 52 - 18 * 5
        d.text((x, P(ly)), "NODE COLOUR", font=lab_f, fill=mix(PAPER, INK3, a))
        items = [(GOLD, "proved (theorem)"), (SUP, "data supports"), (MIX, "data mixed"), (REF, "data refutes"),
                 (INC, "data inconclusive")]
        shown = []
        if t >= T_THM0:
            shown.append(items[0])
        if t >= T_TEST0:
            shown.extend(items[1:])
        shown += [(c, f"assessor p(true) {lab}") for _, c, lab in TRUTH]
        shown.append((NODE, "not yet scored"))
        rows_y = ly + 20
        # Two columns so everything fits.
        half = (len(shown) + 1) // 2
        for i, (col, lab) in enumerate(shown):
            cx = x + (0 if i < half else P(190))
            cy = P(rows_y + 18 * (i if i < half else i - half))
            d.ellipse((cx, cy + P(3), cx + P(9), cy + P(12)), fill=mix(PAPER, col, a))
            d.text((cx + P(14), cy), lab, font=font(INTER, 11), fill=mix(PAPER, INK2, a))


def paint_title(t, sc):
    im = Image.new("RGB", (P(W), P(H)), PAPER)
    d = ImageDraw.Draw(im)
    a = appear(t, 0.2, 0.8)
    if a <= 0:
        return im
    seal = sc.seal.resize((P(170), P(170)), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    layer.alpha_composite(seal, ((P(W) - P(170)) // 2, P(290)))
    r, g, b, al = layer.split()
    im.paste(Image.merge("RGB", (r, g, b)), (0, 0), al.point(lambda p: int(p * a)))
    d.text((P(W / 2), P(500)), "DELPHI", font=font(MENLO, 16), fill=mix(PAPER, INK2, a), anchor="ma")
    d.text((P(W / 2), P(540)), "Candidate laws of biology", font=font(GEORGIA, 72), fill=mix(PAPER, INK, a), anchor="ma")
    a2 = appear(t, 1.0, 0.8)
    d.text((P(W / 2), P(650)), "Everything we did, as one growing graph. Sixty seconds.", font=font(GEORGIA_I, 28), fill=mix(PAPER, INK2, a2), anchor="ma")
    a3 = appear(t, 1.8, 0.8)
    d.text((P(W / 2), P(730)), f"Every number is computed from the repository, graph built {sc.stats['built']}.",
           font=font(INTER, 17), fill=mix(PAPER, INK3, a3), anchor="ma")
    return im


def paint_closing(t, sc):
    st = sc.stats
    im = Image.new("RGB", (P(W), P(H)), PAPER)
    d = ImageDraw.Draw(im)
    a = appear(t, T_CLOSE + 0.3, 0.8)
    seal = sc.seal.resize((P(120), P(120)), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    layer.alpha_composite(seal, ((P(W) - P(120)) // 2, P(190)))
    r, g, b, al = layer.split()
    im.paste(Image.merge("RGB", (r, g, b)), (0, 0), al.point(lambda p: int(p * a)))
    d.text((P(W / 2), P(350)), "Candidate laws of biology", font=font(GEORGIA, 60), fill=mix(PAPER, INK, a), anchor="ma")
    d.text((P(W / 2), P(440)), "Proof for the math. Tests against open data for the rest.", font=font(GEORGIA_I, 26), fill=mix(PAPER, INK2, a), anchor="ma")
    # Four figures.
    a2 = appear(t, T_CLOSE + 1.0, 0.8)
    figs = [(st["claims"], "claims", INK), (st["theorems"], "theorems", GOLD), (st["tested"], "tested against data", SUP), (st["live"], "live nanopublications", BLUE)]
    xs = [P(W / 2 + (i - 1.5) * 330) for i in range(4)]
    for (n, lab, col), x in zip(figs, xs):
        d.text((x, P(540)), comma(counted(t, T_CLOSE + 1.0, 1.2, n)), font=font(GEORGIA, 64), fill=mix(PAPER, col, a2), anchor="ma")
        d.text((x, P(625)), lab, font=font(INTER_M, 16), fill=mix(PAPER, INK2, a2), anchor="ma")
    a3 = appear(t, T_CLOSE + 2.0, 0.8)
    d.text((P(W / 2), P(740)), "A proof is not evidence that organisms satisfy it.  A data test is not a proof.",
           font=font(GEORGIA_I, 24), fill=mix(PAPER, INK, a3), anchor="ma")
    d.text((P(W / 2), P(790)), "Refuted and inconclusive results are published too.", font=font(GEORGIA_I, 24), fill=mix(PAPER, INK2, a3), anchor="ma")
    a4 = appear(t, T_CLOSE + 2.8, 0.8)
    d.text((P(W / 2), P(900)), "delphibio.org   ·   github.com/fractastical/delphi", font=font(MENLO, 16), fill=mix(PAPER, INK, a4), anchor="ma")
    return im


def paint_graph_frame(t, sc):
    im = Image.new("RGB", (P(W), P(H)), PAPER)
    paint_paper(im)
    d = ImageDraw.Draw(im)
    paint_header(d, t, sc)
    paint_graph(im, d, t, sc)
    paint_column(d, t, sc)
    return im


def frame_at(t, sc):
    if t < T_TITLE_OUT:
        return paint_title(t, sc)
    if t < T_TITLE_OUT + 1.0:
        return Image.blend(paint_title(t, sc), paint_graph_frame(t, sc), appear(t, T_TITLE_OUT, 1.0))
    if t < T_CLOSE:
        return paint_graph_frame(t, sc)
    if t < T_CLOSE + 1.0:
        return Image.blend(paint_graph_frame(t, sc), paint_closing(t, sc), appear(t, T_CLOSE, 1.0))
    return paint_closing(t, sc)


def finish(im):
    if SS == 1:
        return im
    return im.resize((W, H), Image.Resampling.LANCZOS)


# ----------------------------------------------------------------------------- year ticker

def make_year_track(nodes, fps):
    """A smoothed year for the ticker: the current claim's year, approached with a short time constant,
    precomputed per frame so workers agree."""
    order = sorted(nodes, key=lambda n: n["t_in"])
    years = [n["year"] or 0 for n in order]
    t_ins = [n["t_in"] for n in order]
    n_frames = int(DURATION * fps) + 2
    track = []
    y = float(years[0])
    import bisect
    for i in range(n_frames):
        t = i / fps
        j = bisect.bisect_right(t_ins, t) - 1
        target = years[max(0, min(j, len(years) - 1))]
        y += (target - y) * (1 - math.exp(-(1 / fps) / 0.22))
        track.append(y)
    def at(t):
        i = max(0, min(len(track) - 1, int(round(t * fps))))
        return track[i]
    return at


# ----------------------------------------------------------------------------- render

_SCENE = None


def _init(stats, nodes, hubs, families, seal_bytes, fps, ss):
    global _SCENE, SS
    SS = ss
    seal = Image.open(seal_bytes).convert("RGBA") if not isinstance(seal_bytes, Image.Image) else seal_bytes
    sweep_index(0, stats["assessed"])
    _SCENE = Scene(stats, nodes, hubs, families, seal, make_year_track(nodes, fps))


def _render(args):
    i, t, path = args
    finish(frame_at(t, _SCENE)).save(path, optimize=False)
    return i


def main():
    global SS, FPS
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="write stills to /tmp and stop")
    ap.add_argument("--fast", action="store_true", help="12 fps, no supersampling")
    ap.add_argument("--times", default="2,8,13,20,24,30,40,49,53,58", help="preview times, seconds")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    if args.fast:
        SS, FPS = 1, 12

    stats, nodes, hubs, families = load()
    print(f"built {stats['built']}  claims {stats['claims']}  thinkers {stats['thinkers']}  works {stats['works']}  "
          f"assessed {stats['assessed']} by {stats['assessors']}  math {stats['math']}  theorems {stats['theorems']} "
          f"({stats['lean']} lean, {stats['lit']} lit)  laws {stats['laws']}/{stats['laws_accepted']}  "
          f"tested {stats['tested']} ({stats['supports']}/{stats['mixed']}/{stats['refutes']}/{stats['inconclusive']})  "
          f"pending {stats['pending']}  live {stats['live']}  test-registry {stats['test_registry']}  taxa {stats['taxa']}  "
          f"swarm {stats['swarm']}")
    for h in hubs:
        print(f"  {h['name']:22} {h['n']:4}  {h['span']}  r={h['radius']:.0f}")
    print("  datasets:", ", ".join(f"{f['name']} {f['n']}" for f in families))

    seal = load_seal(512)
    tmp = Path(tempfile.mkdtemp(prefix="delphi-graph-video-"))
    if args.preview:
        _init(stats, nodes, hubs, families, seal, FPS, SS)
        for t in (float(x) for x in args.times.split(",")):
            p = tmp / f"t{t:05.1f}.png"
            finish(frame_at(t, _SCENE)).save(p)
            print("preview", p)
        return

    n = int(DURATION * FPS)
    jobs = [(i, i / FPS, str(tmp / f"f{i:04d}.png")) for i in range(n)]
    print(f"rendering {n} frames at {FPS} fps, {SS}x supersampled, {args.jobs} workers")
    with Pool(args.jobs, initializer=_init, initargs=(stats, nodes, hubs, families, seal, FPS, SS)) as pool:
        done = 0
        for _ in pool.imap_unordered(_render, jobs, chunksize=8):
            done += 1
            if done % (FPS * 5) == 0:
                print(f"  {done}/{n}")
    # Poster: the full graph, just before the closing card.
    shutil.copy(tmp / f"f{int((T_CLOSE - 0.6) * FPS):04d}.png", OUT_PNG)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "f%04d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(OUT_MP4)],
        check=True,
    )
    shutil.rmtree(tmp)
    print(OUT_MP4, OUT_MP4.stat().st_size)
    print(OUT_PNG, OUT_PNG.stat().st_size)


if __name__ == "__main__":
    main()
