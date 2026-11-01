#!/usr/bin/env python3
"""Build the pitch deck: what it is, who we are, who we worked with, what we solved, what we can do next.

Run from the repo root: python3 assets/deck/build-4slide.py
Needs Pillow and PyMuPDF. `DECK_THEME=light` builds the light variant; the default is dark, the
portal's default.

Style: the slides follow Kavita's portal stylesheet, docs/css/delphi.css (tokens, type, header,
footer). Every colour below is a token from that file, named as in the file; the type is Inter
(the first font in its `--sans` stack, vendored in assets/deck/fonts/ under the OFL) with the
weights and tracking the stylesheet gives h1, h3/.eyebrow, .stat .n and body. The header is the
portal's `.site-nav` (brand symbol + wordmark), the footer its `.site-footer`. If the tokens change
in delphi.css, change TOKENS here.

It reuses the portrait picture from the original `assets/deck/slide-1.png` and writes
`assets/deck/four/slide-{1..5}.png` and `assets/hackathon-deck-4.pdf`.
Counts come from the README "Current numbers" table (2026-11-01 05:47 UTC); update them there first.
The collaborations slide (3) is read off COLLABORATIONS.md, the `revisions` of
test-data/claim-tests/thompson-growth-form/thompson1917-ch07-04/result.json, the Moltbook threads
(plugins/agent/moltbook-drafts.json; participants re-read live 2026-11-01 15:23 UTC), the README's
sibling-repositories section, plugins/fittest/README.md and test-data/claim-tests/openresearch/README.md.
"""
import os
from PIL import Image, ImageDraw, ImageFont
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "four")
os.makedirs(OUT, exist_ok=True)

# ---- type: Inter, the first font of delphi.css `--sans` ------------------------------------
REG, MED, SEMI, BOLD = "Regular", "Medium", "SemiBold", "Bold"
FONT_DIR = os.path.join(HERE, "fonts")
_HELV = "/System/Library/Fonts/HelveticaNeue.ttc"
_HELV_INDEX = {REG: 0, MED: 10, SEMI: 1, BOLD: 1}
_cache = {}


def font(w, s):
    key = (w, s)
    if key not in _cache:
        p = os.path.join(FONT_DIR, f"Inter-{w}.ttf")
        if os.path.exists(p):
            _cache[key] = ImageFont.truetype(p, s)
        else:  # the stylesheet's own fallback is the system sans
            _cache[key] = ImageFont.truetype(_HELV, s, index=_HELV_INDEX[w])
    return _cache[key]


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """color-mix(in srgb, a (1-t), b t), the stylesheet's soft variants."""
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


# ---- tokens: the :root blocks of docs/css/delphi.css, by name -----------------------------
TOKENS = {
    "dark": dict(paper="#0c1422", paper2="#142035", grid="#2a3953", rule="#3a4c6a",
                 ink="#eef3ff", ink2="#b5c2dc", ink3="#92a4c3",
                 accent="#8cacff", accent_soft="#202f51", specimen="#f09ac6", pink_soft="#40283e",
                 ok="#9bcfbe", warn="#e9bc78", on_accent="#10203d"),
    "light": dict(paper="#f7f9ff", paper2="#ffffff", grid="#dfe6f3", rule="#cbd7ec",
                  ink="#172945", ink2="#536582", ink3="#60708d",
                  accent="#315ee7", accent_soft="#eaf0ff", specimen="#bf3b7f", pink_soft="#fdebf4",
                  ok="#28694f", warn="#956513", on_accent="#ffffff"),
}
THEME = os.environ.get("DECK_THEME", "dark")
T = {k: hexrgb(v) for k, v in TOKENS[THEME].items()}
PAPER, PAPER2, GRID, RULE = T["paper"], T["paper2"], T["grid"], T["rule"]
INK, INK2, INK3 = T["ink"], T["ink2"], T["ink3"]
ACCENT, ACCENT_SOFT, SPECIMEN, OK, WARN, ON_ACCENT = T["accent"], T["accent_soft"], T["specimen"], T["ok"], T["warn"], T["on_accent"]
OK_SOFT = mix(OK, PAPER2, 0.45)          # the "mixed" verdict: --ok softened toward the panel
ON_OK = ON_ACCENT if THEME == "dark" else T["paper2"]

W, H = 1920, 1080
L, R = 97, 1823

orig = Image.open(os.path.join(HERE, "slide-1.png")).convert("RGB")
PORTRAIT = orig.crop((96, 324, 789, 951))


def text_tracked(d, x, y, s, f, fill, track):
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + track
    return x


def tracked_width(s, f, track):
    return sum(f.getlength(c) + track for c in s) - track


def h1(d, x, y, s, size):
    """delphi.css h1: weight 500, letter-spacing -.03em."""
    return text_tracked(d, x, y, s, font(MED, size), INK, -0.03 * size)


def eyebrow(d, x, y, s, size=20, fill=None, right=False):
    """delphi.css .eyebrow / h3: uppercase, weight 600, letter-spacing .12–.14em, --ink-3."""
    f, track = font(SEMI, size), 0.13 * size
    s = s.upper()
    if right:
        x -= tracked_width(s, f, track)
    text_tracked(d, x, y, s, f, fill or INK3, track)


def brand_symbol(im, x, y, h, color):
    """The portal's `.brand-symbol` SVG (viewBox 0 0 32 40), drawn at 4x and downsampled."""
    S = 4
    k = h / 40 * S
    layer = Image.new("RGBA", (int(32 * k) + 2 * S, int(40 * k) + 2 * S), (0, 0, 0, 0))
    g = ImageDraw.Draw(layer)
    P = lambda px, py: (px * k + S, py * k + S)
    g.polygon([P(16, 2), P(30, 29), P(16, 37), P(2, 29)], outline=color + (255,), width=max(1, round(1.2 * k)))
    thin, soft = max(1, round(0.8 * k)), color + (191,)
    for pts in ([(16, 2), (16, 37)], [(2, 29), (16, 21), (30, 29)], [(5, 23), (16, 17), (27, 23)],
                [(9, 16), (16, 12), (23, 16)], [(2, 29), (16, 31), (30, 29)]):
        g.line([P(*p) for p in pts], fill=soft, width=thin)
    layer = layer.resize((layer.width // S, layer.height // S), Image.LANCZOS)
    im.paste(layer, (int(x) - 1, int(y) - 1), layer)
    return 32 * h / 40


def base(n, label, title, sub):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    # .site-nav: brand symbol + wordmark on the left, section eyebrow on the right, 1px --grid rule
    sw = brand_symbol(im, L, 22, 45, ACCENT)
    text_tracked(d, L + sw + 14, 24, "Delphi", font(MED, 38), INK, -1.8)
    d.text((L + sw + 14 + tracked_width("Delphi", font(MED, 38), -1.8) + 26, 35), "Science Claw Hack @ MIT", font=font(MED, 22), fill=INK2)
    eyebrow(d, R, 37, f"{n} · {label}", size=19, right=True)
    d.rectangle((0, 88, W, 88), fill=GRID)
    # page head: h1 + .subtitle
    h1(d, L - 3, 118, title, 72)
    y = 210
    for line in sub:
        d.text((L, y), line, font=font(REG, 29), fill=INK2)
        y += 37
    # .site-footer / .foot-legal
    d.rectangle((0, 975, W, H), fill=PAPER2)
    d.rectangle((0, 975, W, 975), fill=GRID)
    fs = brand_symbol(im, L, 1004, 36, ACCENT)
    d.text((L + fs + 12, 1013), "github.com/fractastical/delphi", font=font(MED, 22), fill=INK2)
    legal = "© 2026 Project Delphi. Free and open. Model scores are reviewer ratings, not probabilities."
    d.text((R - font(REG, 19).getlength(legal), 1016), legal, font=font(REG, 19), fill=INK3)
    return im, d


def rich(d, x0, y, width, runs, size=23, lh=31, gap=0):
    """Word-wrapped runs. A run is (text, style); style 'b' = --ink medium, 'g' = --ink-2 regular, or an RGB tuple."""
    x = x0
    for text, st in runs:
        if st == "b": f, col = font(MED, size), INK
        elif st == "g": f, col = font(REG, size), INK2
        elif st == "bg": f, col = font(MED, size), INK2
        else: f, col = font(MED, size), st
        for w in text.split(" "):
            if not w: continue
            if x + f.getlength(w) > x0 + width:
                x = x0; y += lh
            d.text((x, y), w, font=f, fill=col)
            x += f.getlength(w + " ")
    return y + lh + gap


def centered(d, cx, y, s, f, fill):
    d.text((cx - f.getlength(s) / 2, y), s, font=f, fill=fill)


def box(d, x, y, w, h, color, t=3, r=10):
    """delphi.css .card: --paper-2 surface, 10px radius; the outline carries the stage colour."""
    d.rounded_rectangle((x, y, x + w, y + h), radius=r, outline=color, width=t, fill=PAPER2)


def stat(d, x, y, num, color, size=84):
    """delphi.css .stat .n: weight 500, letter-spacing -.03em."""
    return text_tracked(d, x, y, num, font(MED, size), color, -0.03 * size)


def caps(d, x, y, s, fill=None):
    eyebrow(d, x, y, s, size=18, fill=fill)


slides = []

# 1 ── what it is ──────────────────────────────────────────────────────────────
im, d = base(1, "WHAT IT IS", "DELPHI: which laws of biology hold up",
             ["Distributed Epistemic Layer for Probabilistic Hypothesis Inference. The goal: the fundamental",
              "theorems of biology, general laws stated precisely enough to test. We pull candidate laws out of",
              "the literature as claims, prove what can be proved and test the rest on real organisms."])
steps = [("extract", "candidate laws from books and papers, with the quote", INK, "1,761", "claims, each with a verbatim quote from its source"),
         ("formalize", "state it in Lean 4 where it is mathematics", WARN, "87", "theorems: 71 machine-checked in Lean 4, 16 proved in the literature"),
         ("simulate", "reproduce the model, audit it blind", INK3, "109", "MorphoEval audits of model reproductions, linked to claims"),
         ("test", "pre-register pass/fail, then fetch the data", OK, "161", "claims tested against data, 82 of them on measured organisms"),
         ("publish", "every step a signed nanopublication", ACCENT, "880", "live as signed nanopubs on the production network")]
gap = 30
bw = (R - L - 4 * gap) // 5
for i, (name, desc, col, num, lab) in enumerate(steps):
    x = L + i * (bw + gap)
    box(d, x, 345, bw, 150, col if col != INK3 else RULE)
    centered(d, x + bw / 2, 372, name, font(MED, 36), INK)
    rich(d, x + 22, 428, bw - 44, [(desc, "g")], size=21, lh=27)
    if i < 4:
        ax = x + bw + 4
        d.polygon([(ax, 408), (ax + gap - 8, 420), (ax, 432)], fill=RULE)
    stat(d, x, 530, num, col, 88)
    rich(d, x, 640, bw - 10, [(lab, "g")], size=21, lh=27)
d.rectangle((L, 770, R, 770), fill=GRID)
y = 795
y = rich(d, L, y, R - L, [("Sources so far: ", "b"),
         ("Darwin's Origin of Species, Thompson's On Growth and Form, Wolfram's A New Kind of Science, sixteen Levin papers, Aristotle's biology and five mathematical biologists. 782 animal taxa carry their own datasets.", "g")], size=24, lh=33, gap=10)
y = rich(d, L, y, R - L, [("Any agent can query it, no install: ", "b"), ("MCP server at mcp.delphibio.org/mcp", ACCENT),
         (" (claims, their math, rankings, test verdicts, organisms).", "g")], size=24, lh=33, gap=10)
rich(d, L, y, R - L, [("A proof shows a law follows from its assumptions, not that organisms satisfy them. That is what the data tests are for.", "g")], size=22, lh=30)
slides.append(im)

# 2 ── who we are ──────────────────────────────────────────────────────────────
im, d = base(2, "WHO WE ARE", "Five people, a few hundred agents",
             ["Thirty hours at Science Claw Hack @ MIT: 101 local agent chats, 262 subagents and 19 cloud",
              "agents working with five people, plus the outside agents that challenged our tests."])
im.paste(PORTRAIT.resize((620, 561)), (L, 345))
X0 = 884
people = [("Joel Dietz", "@fractastical", "lead, integrator, publisher; signs every production nanopub"),
          ("Kris", "@kganjam", "form simulator and queryable open problems"),
          ("Kavita", "@kavitakoolkarni-bio", "presentation layer: claim graph site, demo, slides"),
          ("Ashley", "@ashleycaselli", "nanopubs; linking claims to INDRA, GBIF and Wikidata"),
          ("Amit", "@xX-its-amit-Xx", "genotype–phenotype links, MCP testing, agent comparison")]
y = 330
for n, h, desc in people:
    d.text((X0, y), n, font=font(MED, 31), fill=INK)
    d.text((1124, y + 7), h, font=font(REG, 23), fill=INK3)
    d.text((X0, y + 39), desc, font=font(REG, 23), fill=INK2)
    y += 72
d.rectangle((X0 - 1, 700, R, 700), fill=GRID)
caps(d, X0, 718, "and the agents")
y = 760
y = rich(d, X0, y, R - X0, [("Claude", "b"), ("builds · ", "g"), ("GPT-5.6 Sol, Gemini 4 Argon, Grok 4.7", "b"), ("assess blind · ", "g"), ("19 cloud agents", "b"), ("test", "g")], size=22, lh=30, gap=6)
y = rich(d, X0, y, R - X0, [("Delfie", "b"), ("(our agent) on ", "g"), ("Moltbook,", "b"), ("The Colony and Discord, and as ", "g"), ("delfie-claude", "b"), ("in the SentiLab room", "g")], size=22, lh=30, gap=6)
y = rich(d, X0, y, R - X0, [("Moltbook agents who challenged our cell-geometry test: ", "g"), ("moltbook-vina, moltbook-hivefound, moltbook-nanoswarm, doctor_memory", "b")], size=22, lh=30, gap=6)
rich(d, X0, y, R - X0, [("Also in the collaboration log: ", "g"), ("InquilineKea", "b"), ("(SentiLab),", "g"), ("Fittest MCP", "b")], size=22, lh=30)
slides.append(im)

# 3 ── one test in detail: Thompson's 120° junctions, Nebius, and the agents who corrected it ──
# Every number here is read off test-data/claim-tests/thompson-growth-form/thompson1917-ch07-04/result.json
# (measured.extra.per_tissue, revisions[0..1], test_contract), claim-sources/cell-geometry/results/segmenter-bias/summary.json
# and claim-sources/cell-geometry/nanopubs/manifest.jsonl.
import json
CG = os.path.join(ROOT, "claim-sources", "cell-geometry")
rj = json.load(open(os.path.join(ROOT, "test-data", "claim-tests", "thompson-growth-form", "thompson1917-ch07-04", "result.json")))
per = rj["measured"]["extra"]["per_tissue"]
n_junctions = sum(t["junctions_measured"] for t in per.values())
n_tissues, n_conform = len(per), len(rj["measured"]["extra"]["conforming"])
rev0, rev1 = rj["revisions"][0], rj["revisions"][1]
prompted = [p["agent"] for p in rev0["prompted_by"]]
n_np = sum(1 for _ in open(os.path.join(CG, "nanopubs", "manifest.jsonl")))
conf_path = [(rev0["from"]["confidence"]), (rev0["to"]["confidence"]), (rev1["to"]["confidence"])]

im, d = base(3, "ONE TEST, IN DETAIL", "One test, end to end: do cell walls meet at 120°?",
             [f"Thompson, On Growth and Form ch. 7: tissue cell walls meet three at a time at 120°, regardless of cell size. Five tissues,",
              f"one GPU platform, {len(prompted)} outside agents, two revisions, and a verdict that is still “mixed”, now for a better reason."])


def overlay(path, box_w, box_h):
    """Centre-crop a Cellpose overlay to the panel's aspect and fit it."""
    o = Image.open(path).convert("RGB")
    ar = box_w / box_h
    w, h = o.size
    if w / h > ar: nw = int(h * ar); o = o.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else: nh = int(w / ar); o = o.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return o.resize((box_w, box_h), Image.LANCZOS)


# left: the evidence, two tissues from the five
PW, PH = 540, 212
cornea, grass = per["human-corneal-endothelium"], per["festuca-leaf-epidermis"]
panels = [("human-corneal-endothelium", "Homo sapiens, corneal endothelium", OK,
           f"{cornea['junctions_measured']} junctions · angle SD {cornea['angle_sd']}° · {cornea['frac_T_like']*100:.0f}% T-junctions · conforms"),
          ("festuca-leaf-epidermis", "Festuca arundinacea, leaf epidermis", SPECIMEN,
           f"{grass['junctions_measured']} junctions · angle SD {grass['angle_sd']}° · {grass['frac_T_like']*100:.0f}% T-junctions · does not")]
y = 300
for key, name, col, line in panels:
    d.rounded_rectangle((L - 1, y - 1, L + PW + 1, y + PH + 1), radius=10, outline=GRID, width=1, fill=PAPER2)
    im.paste(overlay(os.path.join(CG, "results", key, "overlay.png"), PW, PH), (L, y))
    d.text((L, y + PH + 10), name, font=font(MED, 20), fill=INK)
    rich(d, L, y + PH + 38, PW, [(line, col)], size=17, lh=22)
    y += PH + 84
# confidence track: 0.60 -> 0.35 -> 0.60
caps(d, L, y + 6, "Confidence recorded in result.json")
ty = y + 44
d.rectangle((L, ty + 34, L + PW, ty + 34), fill=GRID)
for i, (c, lab) in enumerate(zip(conf_path, ["Cellpose, 4 of 5 conform", "after the segmenter null", "on expert segmentations"])):
    cx = L + 22 + i * (PW - 44) // 2
    d.ellipse((cx - 9, ty + 25, cx + 9, ty + 43), fill=OK if c >= 0.5 else WARN)
    stat(d, cx - font(MED, 30).getlength(f"{c:.2f}") / 2, ty - 8, f"{c:.2f}", INK, 30)
    f = font(REG, 15); d.text((cx - f.getlength(lab) / 2, ty + 52), lab, font=f, fill=INK3)
rich(d, L, ty + 84, PW, [("Same number, different meaning: the first 0.60 rested on a segmenter with a bias nobody had measured; the second rests on hand-corrected tissues and a split reading.", "g")], size=16, lh=21)

# right: the chain of agents, in order
X0, CW = L + PW + 56, R - (L + PW + 56)
caps(d, X0, 300, "Who did what, in order")
d.rectangle((X0, 332, R, 332), fill=RULE)
sb = json.load(open(os.path.join(CG, "results", "segmenter-bias", "summary.json")))
steps3 = [
    ("Oct 31", "Claude, the builder", INK,
     f"pulls the claim from the Thompson corpus, picks {n_tissues} public micrographs (cornea, Drosophila eye, moss, grass, Aloe) and writes the hypothesis and fail criterion. Exploratory, not pre-registered, and the record says so."),
    ("", "Nebius Scientific AI", ACCENT,
     f"Cellpose-SAM segments all five; each run's operation ID, model checksum and input SHA-256 go in cellpose.json. analyze.py measures {n_junctions:,} junctions against a hexagonal lattice and a random-Voronoi control: {n_conform} of {n_tissues} conform. Verdict mixed, confidence {conf_path[0]:.2f}."),
    ("", "Delfie posts it on Moltbook", INK,
     "and three agents answer. vina: run a null, segment synthetic tilings whose packing you already know. nanoswarm: blur alone bends wall ridges toward Y, fit lines in an annulus away from the vertex. hivefound: state the expected and the disconfirming observation, admissible data and the method as four separate fields."),
    ("", "Nebius again, the null vina asked for", WARN,
     f"{len(sb['truth'])} tilings × {len(sb['snr_levels'])} noise levels through the same checkpoint. A brick wall with 100% T-junctions comes out at 3–16%; a cell-file tiling at 48–59%; random Voronoi gains near-120° junctions. Cell counts were exact, so the bias is in boundary shape. Confidence {conf_path[0]:.2f} → {conf_path[1]:.2f}."),
    ("Nov 1", "Independent data, no Cellpose", OK,
     f"eight TissueMiner Drosophila epithelia, segmented and hand-corrected by their authors. Three-way vertices 98.4–99.7%: “by threes” holds. Near-120° junctions only 16–21% while cells divide (random: 14%), rising to 42–49% once division stops. Mixed, {conf_path[2]:.2f}, now split by reading."),
    ("", "The record", INK,
     f"revisions[] names each agent, venue and comment URL; hivefound's four fields are now the test contract in every result.json; {n_np} dataset and evidence records sit on the nanopub test registry, none signed for production. Next: ridge-based angles with nanoswarm's annulus sweep, then a pre-registered replication."),
]
y = 346
for when, who, col, text in steps3:
    d.ellipse((X0 + 2, y + 7, X0 + 14, y + 19), fill=col)
    if when: eyebrow(d, X0 + 30, y + 4, when, size=14)
    d.text((X0 + 30 + (74 if when else 0), y), who, font=font(MED, 22), fill=INK)
    y = rich(d, X0 + 30, y + 30, CW - 30, [(text, "g")], size=17, lh=22, gap=10)
    if y < 920: d.rectangle((X0 + 8, y - 8, X0 + 8, y - 6), fill=RULE)
assert y <= 960, f"slide 3 steps run to y={y}"
slides.append(im)

# 4 ── what we solved ──────────────────────────────────────────────────────────
im, d = base(4, "WHAT WE SOLVED", "What we solved: from books to verdicts",
             ["We built the machinery that takes a claim from a page to a pre-registered test on real data and a",
              "published verdict, and ran it. No open problem is solved yet; 161 claims have a verdict."])
stats = [("1,761", INK, "claims from six sources, each with a verbatim quote"),
         ("87", WARN, "theorems: 71 machine-checked in Lean 4 with no sorry, 16 proved in the literature"),
         ("161", OK, "claims tested against real data, 82 of them on measured organisms"),
         ("880", ACCENT, "live as signed nanopubs that any agent can query over MCP")]
gap = 40
cw = (R - L - 3 * gap) // 4
for i, (num, col, lab) in enumerate(stats):
    x = L + i * (cw + gap)
    stat(d, x, 330, num, col, 84)
    rich(d, x, 432, cw - 10, [(lab, "g")], size=22, lh=28)
caps(d, L, 548, "Verdicts on the 161 tests")
# .live / .ok, the softened ok, .bad / --specimen, and --rule for the undecided
segs = [(87, OK, "supports 87", ON_OK), (35, OK_SOFT, "mixed 35", INK), (28, SPECIMEN, "refutes 28", ON_OK), (11, RULE, "", INK)]
x = L; total = sum(s[0] for s in segs); span = R - L
for n, col, lab, tc in segs:
    w = round(span * n / total)
    d.rounded_rectangle((x, 580, x + w - 3, 624), radius=5, fill=col)
    d.text((x + 14, 590), lab, font=font(MED, 24), fill=tc)
    x += w
d.text((R - font(MED, 20).getlength("inconclusive 11"), 632), "inconclusive 11", font=font(MED, 20), fill=INK3)
cols = [("Real refutations",
         "Darwin's island biogeography (2 refuted, 2 mixed) and Thompson's heart and fish-shape claims were refuted on public data. Wolfram's randomness batteries and Levin's keratocyte and planarian-head claims held."),
        ("It audits itself",
         "A blind assessor from another provider checks that each test measures what its claim says: 28 of 161 checked so far, 5 judged not representative and set aside. A segmenter-bias control cut one Thompson result from 0.60 to 0.35."),
        ("The collective beats one agent",
         "Same model and budget, 20 claims, first of two experiments: one agent verified 13 datasets, isolated workers 17, a centralized swarm 19, a decentralized one 18, with no fabricated identifier in any final plan. Every multi-agent arm beat one agent in both.")]
gap = 50
cw = (R - L - 2 * gap) // 3
for i, (h, t) in enumerate(cols):
    x = L + i * (cw + gap)
    d.text((x, 668), h, font=font(MED, 30), fill=INK)
    rich(d, x, 714, cw, [(t, "g")], size=22, lh=29)
rich(d, L, 934, R - L, [("Not solved: ", SPECIMEN), ("any of the 27 open problems. A verdict on one dataset is evidence, not proof.", "b")], size=24, lh=30)
slides.append(im)

# 5 ── what we can do next ─────────────────────────────────────────────────────
im, d = base(5, "WHAT WE CAN DO NEXT", "What we can do next",
             ["The problem graph already holds 27 hard open problems, each linked to the claims it bears on,",
              "with approaches proposed blind by agents from four model providers. None is solved yet."])
tiers = [("7", WARN, "Prove it", "Tier A: a proof or an exhaustive computation the swarm could finish. Rule 110 universality in Lean, the scope of Hamilton's rule, phyllotaxis attractors."),
         ("13", OK, "Test it", "Tier B: open empirical questions a pre-registered test on public data can settle. Metabolic scaling, species–area, Murray's law, Lewontin's paradox."),
         ("7", ACCENT, "Attack it", "Tier C: hard and open, where agents have an unusual angle. The bioelectric code, morphogenesis–cognition gene overlap through INDRA, memory in gene networks.")]
gap = 40
cw = (R - L - 2 * gap) // 3
for i, (num, col, h, t) in enumerate(tiers):
    x = L + i * (cw + gap)
    box(d, x, 335, cw, 320, col)
    xe = stat(d, x + 26, 350, num, col, 84)
    d.text((xe + 22, 384), h, font=font(MED, 40), fill=INK)
    rich(d, x + 26, 475, cw - 52, [(t, "g")], size=24, lh=33)
cols = [("Close the evidence gap",
         "1,524 of 1,761 claims are neither proved nor tested. 9 pre-registered tests wait for data, and 133 of the 161 finished tests have not yet been through the faithfulness check."),
        ("Replicate across organisms",
         "A law that holds in one organism is not fundamental. 82 of 161 tests used measured organism data; 782 taxa and 1,372 dataset records are ready to run each law across species."),
        ("Open to other teams",
         "The hosted MCP server, agent forum and Frontier node (1,190 claims mirrored) already let outside agents challenge our tests, as the Moltbook agents did. Every new test lands as a nanopub.")]
gap = 50
cw = (R - L - 2 * gap) // 3
for i, (h, t) in enumerate(cols):
    x = L + i * (cw + gap)
    d.text((x, 690), h, font=font(MED, 32), fill=INK)
    rich(d, x, 740, cw, [(t, "g")], size=23, lh=31)
slides.append(im)

# write PNGs and the PDF
doc = pymupdf.open()
rect = pymupdf.Rect(0, 0, 691.2, 388.8)
for i, im in enumerate(slides, 1):
    p = os.path.join(OUT, f"slide-{i}.png")
    im.save(p)
    page = doc.new_page(width=rect.width, height=rect.height)
    page.insert_image(rect, filename=p)
pdf = os.path.join(ROOT, "assets", "hackathon-deck-4.pdf")
doc.save(pdf, garbage=4, deflate=True)
print("wrote", pdf, len(doc), "pages")
