#!/usr/bin/env python3
"""Build docs/team.html: the team composite with its five morphology wedges made interactive.
Hovering a wedge shows the delphisci claims about that pattern and the species on which the
morpho lab's 12-step loop has tested the pattern's model.

Claims come from docs/claims.json (run build-claim-graph.mjs first). Species come from the
MorphoEval bundles in infinitemorphospace/morphoeval/kg/<bundle>/ (REPORT.md for score, verdict
and assessor; published.json for the claim nanopub and registry). Retracted bundles are refused.
Without the morpho repo the last docs/team/species.json is reused.

    python3 scripts/site/build-team-page.py [--morpho ~/Documents/GitHub/infinitemorphospace]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
OUT = DOCS / "team"
ORG_IMAGES = REPO / "test-data/organisms/images"

PANELS = [
    {
        "key": "phyllotaxis",
        "title": "Phyllotaxis",
        "model": "Vogel 1979",
        "formula": "r_n = c\\sqrt{n},\\; \\theta_n = n \\cdot 137.508^\\circ",
        "blurb": "Florets placed one golden angle apart pack into interlocking Fibonacci spirals.",
        "claims": ["thompson1917-ch14-07", "thompson1917-ch14-08", "thompson1917-ch14-01",
                   "thompson1917-ch14-04", "thompson1917-ch14-06"],
        "species": [
            {"bundle": "2026-10-18-phyllotaxis-audit-v2", "name": "Helianthus annuus", "common": "Sunflower",
             "image": "datasets/phyllotaxis/helianthus_annuus_capitulum_specimen.jpg",
             "crop": (0.5, 0.5, 0.92),
             "credit": "File:Sunflower Spiral.jpg, Wikimedia Commons, CC BY-SA 2.0",
             "finding": "621 florets segmented on a real seed head; cell circularity 0.79 against 0.85 for the "
                        "golden-angle model, with parastichy counts checked against Swinton et al. 2016."},
        ],
    },
    {
        "key": "branching",
        "title": "Branching",
        "model": "Murray 1926",
        "formula": "r_0^3 = r_1^3 + r_2^3",
        "blurb": "Each junction conserves the cube of the radius, which minimises the cost of moving fluid.",
        "claims": ["thompson1917-ch15-15", "thompson1917-ch15-10", "thompson1917-ch15-14",
                   "thompson1917-ch15-13", "wolfram2002-ch08-19"],
        "species": [
            {"bundle": "2026-10-18-venation-audit-v2", "name": "Ginkgo biloba", "common": "Ginkgo leaf venation",
             "image": "datasets/venation/ginkgo_open_venation_specimen.jpg",
             "crop": (0.5, 0.3, 0.55),
             "credit": "File:Ginkgo biloba 01 SR 87-36-02 A.jpg, Wikimedia Commons, CC BY-SA 3.0",
             "finding": "Runions space-colonisation veins with Murray's law at the junctions, measured on a real leaf; "
                        "Ginkgo's open dichotomous veins form no loops, a reticulate leaf supplies the looped case."},
        ],
    },
    {
        "key": "wing",
        "title": "Wing venation",
        "model": "Hoffmann et al. 2018",
        "formula": "\\text{cells} = \\text{Voronoi}(\\text{inhibitory centres})",
        "blurb": "Veins form where inhibitory centres meet, so cell size is set by one inhibition length.",
        "claims": ["thompson1917-ch07-04", "thompson1917-ch07-09", "thompson1917-ch07-08", "thompson1917-ch07-10"],
        "claims_note": "Thompson's cell-packing laws: the venation model's cells are the same 120° partitions.",
        "species": [
            {"bundle": "2026-10-14-odonata-audit", "name": "Odonata", "common": "Dragonflies, 69 fossil and 394 living wings",
             "org_image": "odonata", "crop": (0.38, 0.42, 0.62),
             "finding": "Median wing-cell length stays at 0.78–0.99 mm across 150 million years and a sixfold range "
                        "of wing length: the inhibition length is approximately, not strictly, conserved."},
        ],
    },
    {
        "key": "turing",
        "title": "Turing patterns",
        "model": "Turing 1952 · Gray–Scott",
        "formula": "\\partial_t u = D_u \\nabla^2 u - uv^2 + F(1-u)",
        "blurb": "A short-range activator and a long-range inhibitor turn a uniform field into spots and stripes.",
        "claims": ["turing-wavelength", "turing-ddi", "turing-morphogen-hypothesis",
                   "wolfram2002-ch08-28", "wolfram2002-ch08-26"],
        "species": [
            {"bundle": "2026-10-19-turing-audit-v2", "name": "Pomacanthus imperator", "common": "Emperor angelfish",
             "image": "datasets/turing/pomacanthus_imperator_stripes_specimen.jpg",
             "crop": (0.64, 0.47, 0.55),
             "credit": "Diego Delso, Wikimedia Commons, CC BY-SA 4.0",
             "finding": "Stripe spacing measured on a real flank (CV 0.15, 22 Y-junctions) against a Turing labyrinth "
                        "and an equal-diffusion control that makes no pattern."},
            {"bundle": "2026-10-19-palate-ruguga-turing-audit-v3", "name": "Equus caballus", "common": "Horse palate rugae",
             "image": "datasets/palate_ruguga_turing/palate_rugae_specimen.jpg",
             "crop": (0.5, 0.52, 0.95),
             "credit": "File:Palatum horse.JPG, Wikimedia Commons, CC BY-SA 3.0",
             "finding": "An FGF/SHH Turing sheet raises 9 ridges on the Shh stripes; their duty cycle (0.42) is "
                        "close to the segmented rugae (0.44–0.49), and the ridges vanish with equal diffusion."},
            {"bundle": "2026-10-26-bos-taurus-turing-wavelength-audit-v7", "name": "Bos taurus", "common": "Holstein coat",
             "image": "datasets/bos_taurus_turing_wavelength/bos_taurus_specimen.jpg",
             "crop": (0.45, 0.52, 0.85),
             "credit": "Province of Ontario Picture Bureau, c.1920, Wikimedia Commons, public domain",
             "negative": True,
             "finding": "Tested negative. On 10 cows a single-wavelength Turing pattern is rejected (it predicts ~125 "
                        "uniform spots, the cows carry a few body-scale patches)."},
        ],
    },
    {
        "key": "spiral",
        "title": "Equiangular spiral",
        "model": "Thompson 1917",
        "formula": "r = a\\,e^{\\theta \\cot\\alpha}",
        "blurb": "Growth at a constant ratio on opposite sides winds a logarithmic spiral of constant angle.",
        "claims": ["thompson1917-ch11-03", "thompson1917-ch13-03", "thompson1917-ch13-13",
                   "thompson1917-ch11-10", "thompson1917-ch13-05"],
        "species": [
            {"bundle": "2026-10-28-t1917-027-the-logarithmic-spiral-audit-v2", "name": "Nautilus pompilius",
             "common": "Chambered nautilus", "image": "datasets/thompson_1917/t1917-027/nautilus_pompilius_specimen.jpg",
             "crop": (0.42, 0.45, 0.72),
             "credit": "File:Pu - Nautilus pompilius - 10.jpg, Wikimedia Commons, CC BY-SA 4.0",
             "finding": "The shell outline fits a logarithmic spiral (log-polar r ≈ 0.96), with synthetic-recovery "
                        "and shuffle controls."},
            {"bundle": "2026-10-28-t1917-031-the-shapes-of-horns-and-of-tee-audit-v2", "name": "Ovis ammon",
             "common": "Argali horn", "image": "datasets/thompson_1917/t1917-031/ovis_ammon_argali_skull_horns_specimen.jpg",
             "crop": (0.72, 0.4, 0.55),
             "credit": "Ksuryawanshi, Wikimedia Commons, CC BY-SA 4.0",
             "finding": "A real horn gives a spiral angle of 74.7° (73.6–75.6), matching Thompson's 75°, but the "
                        "angle moves to 87° when the tip arc is dropped. Verdict mixed."},
            {"bundle": "2026-10-28-t1917-029-the-spiral-shells-of-the-foram-audit-v2", "name": "Fusulinida",
             "common": "Fusulinid foraminifera", "image": "datasets/thompson_1917/t1917-029/fusulinid_axial_thin_section_commons_NEON.jpg",
             "crop": (0.5, 0.5, 0.95),
             "credit": "ja:User:NEON, Wikimedia Commons, CC BY-SA 2.5",
             "finding": "A thin section gives a whorl ratio of 1.49 ± 0.10, matching Thompson's 1.5 and Triticites' "
                        "1.53; the late-whorl drift fails in some genera. Verdict mixed."},
        ],
    },
]
# The composite draws PATTERNS in wedge order: phyllotaxis, tree, wing, turing, spiral net.
WEDGE = {"phyllotaxis": 0, "branching": 1, "wing": 2, "turing": 3, "spiral": 4}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def retracted(morpho):
    text = ""
    for f in ["tier_b_retraction_queue.json", "tier_b_retraction_queue_deleted_bundles.json",
              "tier_b_deletion_manifest.json"]:
        p = morpho / "morphoeval/runs" / f
        if p.exists():
            text += p.read_text()
    return text


def bundle_record(morpho, bundle, gone):
    kg = morpho / "morphoeval/kg" / bundle
    if re.search(rf'"{re.escape(bundle)}"', gone):
        sys.exit(f"{bundle} is retracted or deleted; pick another bundle")
    report = (kg / "REPORT.md").read_text()
    m = re.search(r"overall ([\d.]+) \(([^)]+)\)", report)
    assessors = re.findall(r"assessor `pkr:model/([^`]+)`", report)
    pub = json.loads((kg / "published.json").read_text())
    claim = next(((k, v) for k, v in pub.items() if k.endswith("-claim.trig") and v.get("nanopub")), None)
    return {
        "bundle": bundle,
        "score": float(m.group(1)) if m else None,
        "verdict": m.group(2) if m else None,
        "assessors": sorted(set(assessors)),
        "nanopub": claim[1]["nanopub"] if claim else None,
        "registry": {"prod": "production", "test": "test"}.get(claim[1].get("published")) if claim else None,
        "report": f"https://github.com/fractastical/morpholib/blob/main/morphoeval/kg/{bundle}/REPORT.md",
    }


def thumb(src, name, size=240, crop=(0.5, 0.5, 1.0)):
    """Square crop around the part of the photo that shows the pattern: (centre x, centre y, side),
    the first two as fractions of width and height, the side as a fraction of the shorter edge."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    fx, fy, k = crop
    s = int(min(w, h) * k)
    x0 = min(max(int(fx * w - s / 2), 0), w - s)
    y0 = min(max(int(fy * h - s / 2), 0), h - s)
    im = im.crop((x0, y0, x0 + s, y0 + s)).resize((size, size), Image.LANCZOS)
    dst = OUT / "species" / f"{name}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=84, optimize=True)
    return f"team/species/{name}.jpg"


def species_records(morpho):
    gone = retracted(morpho)
    org = {x["slug"]: x for x in json.loads((ORG_IMAGES / "manifest.json").read_text())["images"]}
    out = {}
    for p in PANELS:
        rows = []
        for s in p["species"]:
            r = {k: v for k, v in s.items() if k not in ("image", "org_image", "crop")}
            r.update(bundle_record(morpho, s["bundle"], gone))
            if "org_image" in s:
                o = org[s["org_image"]]
                r["img"] = thumb(REPO / o["thumb_path"], slug(s["name"]), size=160, crop=s["crop"])
                r["credit"] = f"{o['commons_file']}, {o['author']}, Wikimedia Commons, {o['license']}"
            else:
                r["img"] = thumb(morpho / s["image"], slug(s["name"]), crop=s.get("crop", (0.5, 0.5, 1.0)))
            rows.append(r)
        out[p["key"]] = rows
    return out


def claim_records(ids):
    claims = {c["id"]: c for c in json.loads((DOCS / "claims.json").read_text())["claims"]}
    rows = []
    for i in ids:
        c = claims.get(i)
        if not c:
            sys.exit(f"claim {i} not in docs/claims.json")
        r = {k: c[k] for k in ("id", "label", "thinker", "year", "status", "proof", "theorem",
                               "truth", "nanopub", "registry", "kind", "math", "statement", "truth_by",
                               "assessor_confidence", "evidence", "lean_theorems")}
        # The graph view needs the evidence that hangs off each claim: who scored it and how sure
        # they were, the data test and its verdict, the Lean proof, and the MorphoEval audits.
        t = c.get("data_test") or None
        r["data_test"] = {k: t.get(k) for k in ("verdict", "confidence", "preregistered", "data_kind")} if t else None
        r["morpholib"] = [{k: m.get(k) for k in ("id", "relation", "organism", "verdict", "score", "nanopub", "registry")}
                          for m in (c.get("morpholib") or [])]
        rows.append(r)
    return rows


def geometry():
    """The composite's layout constants, read from team-composite.py so the hit areas match the image."""
    env = {}
    src = Path(__file__).with_name("team-composite.py").read_text()
    for name, expr in re.findall(r"^([A-Z_]+(?:, [A-Z_]+)*) = ([-\d., */()A-Z_]+?)\s*(?:#.*)?$", src, re.M):
        values = eval(expr, {"__builtins__": {}}, env)
        names = name.split(", ")
        env.update(zip(names, values) if len(names) > 1 else [(name, values)])
    return {k: env[k] for k in ("W", "H", "CX", "CY", "R_PENT", "P_RAD", "LOGO_RAD", "GAP", "LINE_W")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--morpho", type=Path, default=Path.home() / "Documents/GitHub/infinitemorphospace")
    ap.add_argument("--composite", type=Path, default=REPO / "assets/team-halloween-2026.png")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "species.json"
    if (args.morpho / "morphoeval/kg").is_dir():
        species = species_records(args.morpho)
        cache.write_text(json.dumps(species, indent=1, ensure_ascii=False) + "\n")
    else:
        print(f"{args.morpho} not found; reusing {cache.relative_to(REPO)}")
        species = json.loads(cache.read_text())

    Image.open(args.composite).convert("RGB").save(OUT / "composite.jpg", quality=88, optimize=True)
    panels = []
    for p in PANELS:
        panels.append({
            "key": p["key"], "wedge": WEDGE[p["key"]], "title": p["title"], "model": p["model"],
            "formula": p["formula"], "blurb": p["blurb"], "claims_note": p.get("claims_note"),
            "claims": claim_records(p["claims"]), "species": species[p["key"]],
        })
    data = {"geometry": geometry(), "panels": panels,
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
    seal = (REPO / "assets/logo.svg").read_text().strip()
    inline = re.sub(r"<svg[^>]*>", lambda t: re.sub(r'\s(width|height)="\d+"', "", t.group(0)), seal, count=1)
    inline = inline.replace("<svg ", '<svg role="img" aria-label="DELPHI seal" ', 1)
    page = (DOCS / "team.template.html").read_text()
    mono = inline.replace("#14213d", "#000").replace("#e5c07b", "#fff")
    page = (page.replace("<!--__SEAL__-->", inline)
                .replace("<!--__SEAL_MONO__-->", mono)
                .replace("/*__SEAL_URI__*/", quote(seal, safe="-_.!~*'()"))
                .replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")))
    (DOCS / "team.html").write_text(page)
    n = sum(len(p["species"]) for p in panels)
    print(f"docs/team.html: {len(page) // 1024} KB, {len(panels)} panels, "
          f"{sum(len(p['claims']) for p in panels)} claims, {n} species")


if __name__ == "__main__":
    main()
