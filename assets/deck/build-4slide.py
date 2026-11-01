#!/usr/bin/env python3
"""Build the four-slide pitch deck: what it is, who we are, what we solved, what we can do next.

Run from the repo root: python3 assets/deck/build-4slide.py
Needs Pillow and PyMuPDF, and macOS's Helvetica Neue (the font of the original slides).

It reuses the seal, the portrait picture and the footer from the original `assets/deck/slide-1.png`
and writes `assets/deck/four/slide-{1..4}.png` and `assets/hackathon-deck-4.pdf`.
Counts come from the README "Current numbers" table (2026-11-01 05:47 UTC); update them there first.
"""
import os
from PIL import Image, ImageDraw, ImageFont
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "four")
os.makedirs(OUT, exist_ok=True)

FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
REG, BOLD, MED = 0, 1, 10
def font(i, s): return ImageFont.truetype(FONT, s, index=i)

W, H = 1920, 1080
L, R = 97, 1823
BLACK, GRAY, RULE = (0, 0, 0), (111, 111, 111), (227, 227, 227)
BLUE, AMBER, GREEN = (15, 59, 255), (224, 161, 0), (26, 158, 75)
LGREEN, RED, LGRAY = (160, 214, 176), (214, 40, 48), (179, 179, 179)

orig = Image.open(os.path.join(HERE, "slide-1.png")).convert("RGB")
LOGO = orig.crop((1706, 113, 1823, 261))
FOOT = orig.crop((0, 975, W, H))
PORTRAIT = orig.crop((96, 324, 789, 951))


def text_tracked(d, x, y, s, f, fill, track):
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + track
    return x


def base(n, label, title, sub):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    hf = font(REG, 22)
    text_tracked(d, L, 33, "DELPHI  ·  SCIENCE CLAW HACK @ MIT", hf, GRAY, 1.6)
    right = f"{n} · {label}"
    wtxt = sum(hf.getlength(c) + 1.6 for c in right) - 1.6
    text_tracked(d, R - wtxt, 33, right, hf, GRAY, 1.6)
    d.rectangle((L - 1, 74, R + 1, 78), fill=BLACK)
    d.text((L, 100), title, font=font(BOLD, 74), fill=BLACK)
    im.paste(LOGO, (1706, 113))
    y = 190
    for line in sub:
        d.text((L, y), line, font=font(REG, 30), fill=GRAY)
        y += 37
    im.paste(FOOT, (0, 975))
    return im, d


def rich(d, x0, y, width, runs, size=23, lh=31, gap=0):
    """Word-wrapped runs. A run is (text, style); style 'b' = dark medium, 'g' = gray, or an RGB tuple."""
    x = x0
    for text, st in runs:
        if st == "b": f, col = font(MED, size), BLACK
        elif st == "g": f, col = font(REG, size), GRAY
        elif st == "bg": f, col = font(MED, size), GRAY
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


def box(d, x, y, w, h, color, t=4, r=14):
    d.rounded_rectangle((x, y, x + w, y + h), radius=r, outline=color, width=t, fill="white")


def caps(d, x, y, s, fill=GRAY):
    text_tracked(d, x, y, s.upper(), font(MED, 20), fill, 1.4)


slides = []

# 1 ── what it is ──────────────────────────────────────────────────────────────
im, d = base(1, "WHAT IT IS", "DELPHI: which laws of biology hold up",
             ["Distributed Epistemic Layer for Probabilistic Hypothesis Inference. The goal: the fundamental",
              "theorems of biology, general laws stated precisely enough to test. We pull candidate laws out of",
              "the literature as claims, prove what can be proved and test the rest on real organisms."])
steps = [("extract", "candidate laws from books and papers, with the quote", BLACK, "1,761", "claims, each with a verbatim quote from its source"),
         ("formalize", "state it in Lean 4 where it is mathematics", AMBER, "87", "theorems: 71 machine-checked in Lean 4, 16 proved in the literature"),
         ("simulate", "reproduce the model, audit it blind", LGRAY, "109", "MorphoEval audits of model reproductions, linked to claims"),
         ("test", "pre-register pass/fail, then fetch the data", GREEN, "161", "claims tested against data, 82 of them on measured organisms"),
         ("publish", "every step a signed nanopublication", BLUE, "880", "live as signed nanopubs on the production network")]
gap = 30
bw = (R - L - 4 * gap) // 5
for i, (name, desc, col, num, lab) in enumerate(steps):
    x = L + i * (bw + gap)
    box(d, x, 345, bw, 150, col if col != LGRAY else (140, 140, 140))
    centered(d, x + bw / 2, 372, name, font(BOLD, 36), BLACK)
    rich(d, x + 22, 428, bw - 44, [(desc, "g")], size=22, lh=28)
    if i < 4:
        ax = x + bw + 4
        d.polygon([(ax, 408), (ax + gap - 8, 420), (ax, 432)], fill=LGRAY)
    numcol = col if col != LGRAY else (110, 110, 110)
    d.text((x, 530), num, font=font(BOLD, 88), fill=numcol)
    rich(d, x, 640, bw - 10, [(lab, "g")], size=22, lh=28)
d.rectangle((L, 770, R, 771), fill=RULE)
y = 795
y = rich(d, L, y, R - L, [("Sources so far: ", "b"),
         ("Darwin's Origin of Species, Thompson's On Growth and Form, Wolfram's A New Kind of Science, sixteen Levin papers, Aristotle's biology and five mathematical biologists. 782 animal taxa carry their own datasets.", "g")], size=25, lh=34, gap=10)
y = rich(d, L, y, R - L, [("Any agent can query it, no install: ", "b"), ("MCP server at delphisci-mcp.fly.dev/mcp", BLUE),
         (" (claims, their math, rankings, test verdicts, organisms).", "g")], size=25, lh=34, gap=10)
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
    d.text((X0, y), n, font=font(BOLD, 31), fill=BLACK)
    d.text((1124, y + 7), h, font=font(REG, 23), fill=GRAY)
    d.text((X0, y + 39), desc, font=font(REG, 23), fill=GRAY)
    y += 72
d.rectangle((X0 - 1, 700, R, 701), fill=RULE)
d.text((X0, 716), "and the agents", font=font(BOLD, 27), fill=BLACK)
y = 760
y = rich(d, X0, y, R - X0, [("Claude", "b"), ("builds · ", "g"), ("GPT-5.6 Sol, Gemini 4 Argon, Grok 4.7", "b"), ("assess blind · ", "g"), ("19 cloud agents", "b"), ("test", "g")], size=22, lh=30, gap=6)
y = rich(d, X0, y, R - X0, [("Delfie", "b"), ("(our agent) on ", "g"), ("Moltbook,", "b"), ("The Colony and Discord, and as ", "g"), ("delfie-claude", "b"), ("in the SentiLab room", "g")], size=22, lh=30, gap=6)
y = rich(d, X0, y, R - X0, [("Moltbook agents who challenged our cell-geometry test: ", "g"), ("moltbook-vina, moltbook-hivefound, moltbook-nanoswarm, doctor_memory", "b")], size=22, lh=30, gap=6)
rich(d, X0, y, R - X0, [("Also in the collaboration log: ", "g"), ("InquilineKea", "b"), ("(SentiLab),", "g"), ("Fittest MCP", "b")], size=22, lh=30)
slides.append(im)

# 3 ── what we solved ──────────────────────────────────────────────────────────
im, d = base(3, "WHAT WE SOLVED", "What we solved: from books to verdicts",
             ["We built the machinery that takes a claim from a page to a pre-registered test on real data and a",
              "published verdict, and ran it. No open problem is solved yet; 161 claims have a verdict."])
stats = [("1,761", BLACK, "claims from six sources, each with a verbatim quote"),
         ("87", AMBER, "theorems: 71 machine-checked in Lean 4 with no sorry, 16 proved in the literature"),
         ("161", GREEN, "claims tested against real data, 82 of them on measured organisms"),
         ("880", BLUE, "live as signed nanopubs that any agent can query over MCP")]
gap = 40
cw = (R - L - 3 * gap) // 4
for i, (num, col, lab) in enumerate(stats):
    x = L + i * (cw + gap)
    d.text((x, 330), num, font=font(BOLD, 84), fill=col)
    rich(d, x, 432, cw - 10, [(lab, "g")], size=22, lh=28)
caps(d, L, 548, "Verdicts on the 161 tests")
segs = [(87, GREEN, "supports 87", "white"), (35, LGREEN, "mixed 35", BLACK), (28, RED, "refutes 28", "white"), (11, LGRAY, "", BLACK)]
x = L; total = sum(s[0] for s in segs); span = R - L
for n, col, lab, tc in segs:
    w = round(span * n / total)
    d.rectangle((x, 580, x + w - 2, 624), fill=col)
    d.text((x + 14, 590), lab, font=font(MED, 24), fill=tc)
    x += w
d.text((R - font(MED, 20).getlength("inconclusive 11"), 632), "inconclusive 11", font=font(MED, 20), fill=GRAY)
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
    d.text((x, 668), h, font=font(BOLD, 30), fill=BLACK)
    rich(d, x, 714, cw, [(t, "g")], size=22, lh=29)
rich(d, L, 934, R - L, [("Not solved: ", RED), ("any of the 27 open problems. A verdict on one dataset is evidence, not proof.", "b")], size=24, lh=30)
slides.append(im)

# 4 ── what we can do next ─────────────────────────────────────────────────────
im, d = base(4, "WHAT WE CAN DO NEXT", "What we can do next",
             ["The problem graph already holds 27 hard open problems, each linked to the claims it bears on,",
              "with approaches proposed blind by agents from four model providers. None is solved yet."])
tiers = [("7", AMBER, "Prove it", "Tier A: a proof or an exhaustive computation the swarm could finish. Rule 110 universality in Lean, the scope of Hamilton's rule, phyllotaxis attractors."),
         ("13", GREEN, "Test it", "Tier B: open empirical questions a pre-registered test on public data can settle. Metabolic scaling, species–area, Murray's law, Lewontin's paradox."),
         ("7", BLUE, "Attack it", "Tier C: hard and open, where agents have an unusual angle. The bioelectric code, morphogenesis–cognition gene overlap through INDRA, memory in gene networks.")]
gap = 40
cw = (R - L - 2 * gap) // 3
for i, (num, col, h, t) in enumerate(tiers):
    x = L + i * (cw + gap)
    box(d, x, 335, cw, 320, col)
    d.text((x + 26, 350), num, font=font(BOLD, 84), fill=col)
    d.text((x + 26 + font(BOLD, 84).getlength(num) + 22, 384), h, font=font(BOLD, 40), fill=BLACK)
    rich(d, x + 26, 475, cw - 52, [(t, "g")], size=25, lh=34)
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
    d.text((x, 690), h, font=font(BOLD, 32), fill=BLACK)
    rich(d, x, 740, cw, [(t, "g")], size=24, lh=32)
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
