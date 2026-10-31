"""Builds data/fish-lifecycle/*.json from verified quotes. Every quote must be a verbatim substring of the source text (whitespace-normalised);
a quote that is not found stops the build. Full text of sources without an open licence stays outside the repo; their hashes are recorded.

  PYTHONPATH=. python3 -m engineering.lifecycle.build --noredist <dir with PMC3030279_efetch.xml and PMC7109522_fulltext.xml>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import diffusion as df

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "fish-lifecycle"
ART = OUT / "artifacts"
RETRIEVED = "2026-10-31"

# id -> (pmcid, openly_licensed_text_in_repo)
SRC = {"parichy2009": ("PMC3030279", False), "aman2018": ("PMC6072442", True), "daane2018": ("PMC6039437", True), "mateus2020": ("PMC7109522", False),
       "stackley2011": ("PMC3183059", True), "grimes2014": ("PMC3899881", True), "mukasheva2024": ("PMC11588461", True), "konadu2023": ("PMC10534073", True)}
norm = lambda s: re.sub(r"\s+", " ", s).strip()


def texts(noredist: Path) -> dict[str, dict]:
    out = {}
    for sid, (pmc, inrepo) in SRC.items():
        p = (ART / f"{pmc}_fulltext.xml") if inrepo else (noredist / ("PMC3030279_efetch.xml" if pmc == "PMC3030279" else f"{pmc}_fulltext.xml"))
        raw = p.read_bytes()
        root = ET.fromstring(raw)
        cells = [norm("".join(c.itertext())) for c in root.iter() if c.tag in ("td", "th")]
        out[sid] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "text": norm("".join(root.itertext())), "cells": cells, "pmc": pmc, "root": root}
    return out


def q(T, sid, quote, locator, where="text"):
    """A verified quote: must occur verbatim in the source (text, or a table cell), and be at most 25 words."""
    n = norm(quote)
    hay = T[sid]["text"] if where == "text" else None
    ok = (n in hay) if where == "text" else any(n in c for c in T[sid]["cells"])
    if not ok:
        raise SystemExit(f"QUOTE NOT FOUND in {sid} ({where}): {n!r}")
    if len(n.split()) > 25:
        raise SystemExit(f"quote over 25 words in {sid}: {n!r}")
    return {"source": sid, "quote": n, "locator": locator, "verified_verbatim": True}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--noredist", type=Path, required=True)
    T = texts(ap.parse_args().noredist)
    Q = lambda *a, **k: q(T, *a, **k)
    meta = {sid: json.loads((ART / f"europepmc_{pmc}.json").read_text())["resultList"]["result"][0] for sid, (pmc, inrepo) in SRC.items() if inrepo}
    cards = [
        {"id": "parichy2009", "citation": "Parichy DM, Elizondo MR, Mills MG, Gordon TN, Engeszer RE. Normal table of postembryonic zebrafish development: staging by externally visible anatomy of the living fish. Dev Dyn 238:2975-3015 (2009). doi:10.1002/dvdy.22113",
         "pmcid": "PMC3030279", "species": "Danio rerio", "evidence_class": "measured_in_fish", "license": None, "license_note": "Europe PMC: not open access; full text came from NCBI PMC efetch (NIH author manuscript); no licence stated, so the text is NOT stored here",
         "read_level": "full-text (author manuscript via efetch)", "full_text_sha256": T["parichy2009"]["sha256"], "full_text_bytes": T["parichy2009"]["bytes"], "text_in_repo": False, "retrieved": RETRIEVED,
         "limits": ["Table 4 values are means of laboratory cohorts at the stated temperatures; strain and rearing differences are discussed in the paper", "SL and SSL are different measures: the text gives squamation beginning at ~8.1 mm SL while Table 4 lists SP at 9.6 SSL"]},
        {"id": "aman2018", "citation": "Aman AJ, Fulbright AN, Parichy DM. Wnt/beta-catenin regulates an ancient signaling network during zebrafish scale development. eLife 7:e37001 (2018). doi:10.7554/eLife.37001", "pmcid": "PMC6072442",
         "species": "Danio rerio", "evidence_class": "observed_qualitative", "license": "CC BY (Europe PMC)", "license_note": "from Europe PMC metadata", "read_level": "full-text", "text_in_repo": True, "retrieved": RETRIEVED,
         "limits": ["live imaging of individual fish: sequence and staging, no growth equation"]},
        {"id": "daane2018", "citation": "Daane JM, Lanni J, Rothenberg I, Seebohm G, Higdon CW, Johnson SL, Harris MP. Bioelectric-calcineurin signaling module regulates allometric growth and size of the zebrafish fin. Sci Rep 8:10391 (2018). doi:10.1038/s41598-018-28450-6", "pmcid": "PMC6039437",
         "species": "Danio rerio", "evidence_class": "observed_qualitative", "license": "CC BY (Europe PMC)", "license_note": "from Europe PMC metadata", "read_level": "full-text", "text_in_repo": True, "retrieved": RETRIEVED,
         "limits": ["pharmacology and mutants on fin regeneration; no allometric coefficient or growth law was found in the text read"]},
        {"id": "mateus2020", "citation": "Mateus R, Holtzer L, Seum C, Hadjivasiliou Z, Dubois M, Julicher F, Gonzalez-Gaitan M. BMP signaling gradient scaling in the zebrafish pectoral fin. Cell Rep 30:4292-4302.e7 (2020). doi:10.1016/j.celrep.2020.03.024", "pmcid": "PMC7109522",
         "species": "Danio rerio", "evidence_class": "modelled_and_fit_to_fish_data", "license": "CC BY-NC-ND (Europe PMC)", "license_note": "no-derivatives and non-commercial: full text NOT stored here; short quotes and a hash only", "read_level": "full-text (not stored)",
         "full_text_sha256": T["mateus2020"]["sha256"], "full_text_bytes": T["mateus2020"]["bytes"], "text_in_repo": False, "retrieved": RETRIEVED, "limits": ["pectoral fin bud, 48-78 hpf only; the exponential fit fails after 78 hpf by the authors' account", "theory section and STAR Methods equations not extracted here"]},
        {"id": "stackley2011", "citation": "Stackley KD, Beeson CC, Rahn JJ, Chan SSL. Bioenergetic profiling of zebrafish embryonic development. PLoS One 6:e25652 (2011). doi:10.1371/journal.pone.0025652", "pmcid": "PMC3183059", "species": "Danio rerio",
         "evidence_class": "measured_in_fish", "license": "CC BY (Europe PMC)", "license_note": "from Europe PMC metadata", "read_level": "full-text (text only: per-stage values are in figures that were not read)", "text_in_repo": True, "retrieved": RETRIEVED,
         "limits": ["per-stage pmol/min/embryo values are plotted, not stated in the text, so none are recorded here"]},
        {"id": "grimes2014", "citation": "Grimes DR, Kelly C, Bloch K, Partridge M. A method for estimating the oxygen consumption rate in multicellular tumour spheroids. J R Soc Interface 11:20131124 (2014). doi:10.1098/rsif.2013.1124", "pmcid": "PMC3899881",
         "species": "Homo sapiens (DLD1 colorectal carcinoma spheroids)", "evidence_class": "borrowed_nonfish", "license": "CC BY (Europe PMC)", "license_note": "from Europe PMC metadata", "read_level": "full-text (typeset equations are images: text not read)", "text_in_repo": True, "retrieved": RETRIEVED,
         "limits": ["tumour spheroids, not fish tissue and not a bioink", "D is assumed close to water, not measured in these spheroids", "constant consumption assumed; Michaelis-Menten variant mentioned and found negligibly different"]},
        {"id": "mukasheva2024", "citation": "Mukasheva F, Adilova L, Dyussenbinov A, Yernaimanova B, Abilev M, Akilbekova D. Optimizing scaffold pore size for tissue engineering: insights across various tissue types. Front Bioeng Biotechnol 12:1444986 (2024). doi:10.3389/fbioe.2024.1444986", "pmcid": "PMC11588461",
         "species": "multiple (review; not fish)", "evidence_class": "borrowed_nonfish", "license": "CC BY (Europe PMC)", "license_note": "from Europe PMC metadata", "read_level": "full-text", "text_in_repo": True, "retrieved": RETRIEVED,
         "limits": ["a review: ranges come from other studies and disagree; no fish tissue", "stiffness and degradation kinetics were not extracted"]},
        {"id": "konadu2023", "citation": "Konadu B, Hosler JP, Gibert Y, et al. Analysis of oxygen consumption rates in zebrafish reveals differences based on sex, age and strain. Front Physiol 14:1272366 (2023). doi:10.3389/fphys.2023.1272366", "pmcid": "PMC10534073", "species": "Danio rerio",
         "evidence_class": "measured_in_fish", "license": "CC BY (Europe PMC)", "license_note": "from Europe PMC metadata", "read_level": "full-text", "text_in_repo": True, "retrieved": RETRIEVED,
         "limits": ["pooled animals per chamber (60 embryos, 5 larvae, 1 adult)", "the adult value looks unit- or normalisation-suspect; see assurance map"]}]
    for c in cards:
        if c["text_in_repo"]:
            m = meta[c["id"]]
            assert m["pmcid"] == c["pmcid"], c["id"]
            c["europepmc_title"], c["europepmc_license"] = m["title"], m.get("license")
            c["full_text_sha256"], c["full_text_bytes"] = T[c["id"]]["sha256"], T[c["id"]]["bytes"]
            c["full_text_path"] = f"data/fish-lifecycle/artifacts/{c['pmcid']}_fulltext.xml"
    eq = [
        {"id": "eq-exp-gradient", "name": "Exponential morphogen gradient", "form": "C(s) = C0 * exp(-s / lambda)", "variables": {"C": "BMP-signalling reporter (BRE) signal, arbitrary units", "s": "position along the gradient", "lambda": "length scale", "C0": "amplitude at the proximal side"},
         "units": {"s": "length (cell diameters or micrometres; the paper uses both)", "lambda": "length", "C": "arbitrary (reporter intensity)"}, "context": "zebrafish pectoral fin bud, BRE reporter, 48-78 hpf, anterior and posterior gradients",
         "parameters": [{"name": "lambda", "value": "about 5 cell diameters (around 28 um) at 60 hpf, both gradients", "kind": "fitted to reporter data"}], "status": "modelled_and_fit_to_fish_data",
         "quotes": [Q("mateus2020", "C(s)=C0e−s/λ", "Results: Two BMP Signaling Gradients during Pectoral Fin Development"), Q("mateus2020", "length scale of about 5 cell diameters (around 28 μm)", "Results: Two BMP Signaling Gradients during Pectoral Fin Development"),
                    Q("mateus2020", "after 78 hpf, the profile does not fit an exponential curve", "Results: Two BMP Signaling Gradients during Pectoral Fin Development")],
         "claimed_by_source": "the gradients scale in two dimensions with the fin's size; scaling by an expansion-repression mechanism with expander Smoc1", "not_established_here": "the quantitative lambda(fin size) relation was not extracted; the equation is not validated beyond 48-78 hpf or beyond the pectoral fin"},
        {"id": "eq-diffusion-consumption", "name": "Steady-state diffusion with constant consumption (spherical)", "form": "D * Laplacian(C) = a   (spherical Laplacian)", "variables": {"D": "oxygen diffusion constant of the tissue", "C": "oxygen per unit mass (volume of O2 per kg)", "a": "oxygen consumption rate per unit mass"},
         "units": {"D": "m^2 s^-1", "a": "m^3 kg^-1 s^-1 (volume of oxygen gas per kg of tissue per second)", "C": "m^3 kg^-1"}, "context": "DLD1 human colorectal tumour spheroids in culture; constant a; time-independent",
         "parameters": [{"name": "D", "value": "2e-9 m^2 s^-1", "kind": "assumed close to water, not measured"}, {"name": "a", "value": "7.29 +/- 1.4 e-7 m^3 kg^-1 s^-1 (= 1.82 +/- 0.35 e-3 mol kg^-1 min^-1)", "kind": "fitted to spheroid hypoxia staining"},
                        {"name": "r_l", "value": "233 +/- 22 um", "kind": "fitted"}], "status": "borrowed_nonfish",
         "quotes": [Q("grimes2014", "At the edge of the spheroid, a radius of ro, the volume of oxygen per unit mass is Co", "Methods: Model derivation"), Q("grimes2014", "we have assumed the oxygen diffusion constant D is close to that of water", "Results: Hypoxic and oxic interface"),
                    Q("grimes2014", "a = 7.29 ± 1.4 × 10−7 m3 kg−1 s−1", "Discussion"), Q("grimes2014", "rl had a relatively constantly value of 233 ± 22 μm", "Discussion"), Q("grimes2014", "The model is time independent", "Discussion"),
                    Q("grimes2014", "oxygen diffusion limits are typically 100–200 μm", "Introduction")],
         "typeset_equation_note": "equations 2.1-2.10 are images in the open-access XML; their text was not read. The setup is taken from the paper's words; closed forms in engineering/lifecycle/diffusion.py are derived here.", "not_established_here": "any value of D, C0 or a for fish tissue or a bioink"},
        {"id": "eq-diffusion-limit", "name": "Diffusion limit (sphere) and the slab analogue", "form": "sphere: r_l = sqrt(6 D C0 / a);  slab, one-sided supply: L = sqrt(2 D C0 / a);  slab supplied from both faces: total thickness 2L", "variables": {"C0": "oxygen amount per unit volume at the supplied boundary", "a": "consumption per unit volume"},
         "units": {"r_l": "m", "L": "m", "C0/a": "s"}, "context": "derived here from the paper's stated boundary conditions, then verified by substitution; the sphere form is the paper's 'diffusion limit' defined as the radius at which the centre pressure just reaches zero",
         "parameters": [], "status": "derived_here_from_stated_setup", "quotes": [Q("grimes2014", "which is the greatest radius the spheroid can obtain and still be entirely viable", "Methods: Model derivation")],
         "not_established_here": "this is a sizing aid for an assumed uniform consumption; it says nothing about vascularised tissue"},
        {"id": "rel-size-over-age", "name": "Size predicts developmental progress better than age", "form": "logistic regression of trait presence on SL or HAA (all R^2 > 0.5); temperature and density add R^2 < 0.05 after size", "variables": {"SL": "standard length", "HAA": "height at anterior of anal fin (linear for HAA > 0.5 mm)"},
         "units": {"SL": "mm", "HAA": "mm"}, "context": "laboratory zebrafish, three temperatures (24, 28.5, 33 C) and three densities, N = 782", "parameters": [], "status": "measured_in_fish",
         "quotes": [Q("parichy2009", "size (measured as SL or HAA) had the highest correlation with developmental progress for all traits examined", "Growth and environmental effects"), Q("parichy2009", "temperature, density, and their interactions with size explained very little additional variance", "Growth and environmental effects")]},
        {"id": "reg-sl-haa", "name": "SL from HAA", "form": "SL = 3.56 * HAA + 4.40", "variables": {"SL": "standard length", "HAA": "height at anterior of anal fin"}, "units": {"SL": "mm", "HAA": "mm"}, "context": "Parichy 2009 Table 3, R^2 = 0.98; valid for HAA > 0.5 mm", "parameters": [{"name": "slope", "value": 3.56}, {"name": "intercept", "value": "4.40 mm"}],
         "status": "measured_in_fish", "quotes": [Q("parichy2009", "SL = (3.56 × HAA) + 4.40", "Table 3", where="cell")]},
        {"id": "param-growth-rate", "name": "Post-embryonic growth rate in SL", "form": "dSL/dt (measured mean, not a fitted law)", "variables": {"dSL/dt": "growth rate"}, "units": {"dSL/dt": "mm per day"}, "context": "larvae reared at 24 C and at 33 C; the 28.5 C value is not stated in this sentence",
         "parameters": [{"name": "24 C", "value": "0.45 +/- 0.009 mm/day (mean +/- SE)"}, {"name": "33 C", "value": "0.54 +/- 0.011 mm/day (mean +/- SE)"}], "status": "measured_in_fish",
         "quotes": [Q("parichy2009", "fish reared at 24 °C grew more slowly than fish reared at 33 °C (SL mm per day, mean±SE: 0.45±0.009, 0.54±0.011, respectively", "Growth and environmental effects")], "not_established_here": "no growth law (von Bertalanffy, Gompertz or other) was found in the text read; none is asserted"},
        {"id": "param-o2-consumption", "name": "Oxygen consumption per animal", "form": "measured rates (no equation)", "variables": {"OCR": "oxygen consumption rate"}, "units": {"OCR": "pmol O2 per minute per animal (pooled animals per chamber)"}, "context": "zebrafish at 28.5 C, Oroboros chamber (Konadu) and Seahorse XF24 (Stackley)",
         "parameters": [{"name": "5 dpf 'embryos'", "value": "126 +/- 4.6 pmol/min/embryo (Konadu; n = 60 pooled per experiment)"}, {"name": "larvae 0.6-0.9 cm", "value": "94.4 +/- 8.3 pmol/min/larva (Konadu; 5 pooled)"},
                        {"name": "adult 3 mo and 12 mo male", "value": "160 pmol/min (Konadu; unit or normalisation suspect)"}, {"name": "3-48 hpf", "value": "basal respiration increases linearly (Stackley; values in figures not read)"}], "status": "measured_in_fish",
         "quotes": [Q("konadu2023", "embryos consume 126 ± 4.6 pmol O2 per minute per embryo", "Results 3.1"), Q("konadu2023", "Basal oxygen consumption rate was determined to be 94.4 ± 8.3 pmol O2 per minute per larvae", "Results 3.1"),
                    Q("konadu2023", "the average oxygen consumption in a 3-month-old and a 12-month male is the same (160 pmol O2/min)", "Discussion"), Q("konadu2023", "Zebrafish embryos that were 5 dpf were used", "Methods 2.1"),
                    Q("stackley2011", "Total basal respiration increased linearly from 3 to 48 hpf", "Results: Metabolic respiration increased linearly")]},
        {"id": "seq-squamation", "name": "Scale formation sequence and staging", "form": "invariant sequence of row and column addition (no equation)", "variables": {}, "units": {}, "context": "zebrafish juveniles, live imaging of individual fish; Fgf signalling necessary for scale initiation and outgrowth", "parameters": [], "status": "observed_qualitative",
         "quotes": [Q("aman2018", "zebrafish squamation proceeds through an invariant sequence of row and column addition", "Discussion"), Q("aman2018", "Within one day, two complete rows of scales formed", "Results: sp7+ osteoblast like cells generate scales"),
                    Q("aman2018", "complete arrest of squamation and scale growth without affecting overall somatic growth", "Results: Fgf-dependent differentiation of scale")]},
        {"id": "obs-fin-calcineurin", "name": "Fin regeneration growth and calcineurin", "form": "qualitative: dose-dependent coordinated overgrowth (no equation)", "variables": {}, "units": {}, "context": "adult fin regeneration; kcnk5b/alf mutants", "parameters": [], "status": "observed_qualitative",
         "quotes": [Q("daane2018", "dose-dependent coordinated overgrowth of fin regenerates", "Results: Skeletal phenotypes of fins treated with FK506"), Q("daane2018", "act to maintain heightened rate of growth during regeneration of the fin", "Introduction")], "not_established_here": "no allometric coefficient or growth law was found"},
        {"id": "win-scaffold-pore", "name": "Scaffold pore-size windows (design context, not a law)", "form": "ranges by tissue; sources disagree", "variables": {"pore size": "diameter"}, "units": {"pore size": "micrometres"}, "context": "review of tissue-engineering scaffolds (bone, skin, others); not fish tissue", "parameters": [], "status": "borrowed_nonfish",
         "quotes": [Q("mukasheva2024", "Scaffolds with a 50–700 µm pore size range are commonly used in bone tissue engineering", "Section 2"), Q("mukasheva2024", "Other sources, however, identify an optimal pore size range of 100–600 µm", "Section 4.2"),
                    Q("mukasheva2024", "Moderate pore sizes, around 2–12 μm, are more suited to the dermal layer", "Section 3.3")], "disagreement": "bone windows differ across the cited works (50-700, 100-600, 200-600 um) and the review notes very large pores can impair stability and cell attachment"}]
    (OUT / "equations.json").write_text(json.dumps({"schema": "fish-lifecycle-equations-0.1 (connector-local)", "retrieved": RETRIEVED, "equations": eq}, indent=1, sort_keys=True))
    (OUT / "sources.json").write_text(json.dumps({"schema": "fish-lifecycle-sources-0.1 (connector-local)", "cards": cards, "not_used": [{"citation": "Loh QL, Choong C. Three-dimensional scaffolds for tissue engineering applications: role of porosity and pore size. Tissue Eng Part B Rev 19:485-502 (2013)", "reason": "not open access; the PMC record states the publisher does not allow the full text to be downloaded; abstract-level only, so nothing was taken from it"}]}, indent=1, sort_keys=True))
    chk = build_rest(T, Q)
    print(len(cards), "cards;", len(eq), "equation/parameter entries;", sum(len(e["quotes"]) for e in eq), "verified quotes; slab two-sided limit um", round(chk["derived"]["slab_two_sided_total_thickness_um"], 1))
    return 0


def table4(T):
    """Parichy 2009 Table 4 rows, parsed from the source table (not retyped)."""
    for tw in T["parichy2009"]["root"].iter("table-wrap"):
        if norm("".join(tw.find("label").itertext())) == "Table 4":
            rows = [[norm("".join(c.itertext())) for c in tr] for tr in tw.iter("tr")]
            out = []
            for r in rows[2:]:
                if len(r) >= 10 and re.fullmatch(r"[A-Za-z]{1,4}", r[0]):
                    v = lambda x: None if x.startswith("—") or x in ("n.d. 5", "n.d.", "") else x      # a dash or n.d. is a missing value, never zero
                    desc = r[1] + (" (P = pelvic fin: Parichy's section heading for PB reads 'pelvic fin bud appearance')" if r[1].startswith("P fin") else "")
                    out.append({"milestone": r[0], "description": desc, "figure": r[2], "ssl_mm": float(r[3]), "sl_pre_mm": v(r[4]), "sl_post_mm": v(r[5]), "haa_pre_mm": v(r[6]), "haa_post_mm": v(r[7]), "sl_p50_mm": v(r[8]), "haa_p50_mm": v(r[9])})
            return out
    raise SystemExit("Table 4 not found")


def build_rest(T, Q):
    t4 = table4(T)
    assert [m["milestone"] for m in t4][0] == "pSB" and [m["milestone"] for m in t4][-1] == "J" and len(t4) == 14, [m["milestone"] for m in t4]
    larva = [m for m in t4 if m["milestone"] != "J"]
    stages = {
        "schema": "fish-lifecycle-stages-0.1 (connector-local; no root schema changed)", "organism": "Danio rerio (zebrafish) only: a model organism, NOT a flying fish", "temperature_reference_c": 28.5, "retrieved": RETRIEVED,
        "note": "stage boundaries are Parichy 2009's laboratory conventions; any other species needs its own boundaries (unknown)",
        "stages": [
            {"id": "embryo", "name": "Embryo", "definition": Q("parichy2009", "the attainment of the protruding mouth stage (~72 hpf at 28.5 °C)", "Life history stage definitions"), "time": {"start_hpf": 0, "end_hpf": 72, "temperature_c": 28.5},
             "size": {"status": "unknown", "note": "no size series for embryos was read (Kimmel 1995 is not open access and was not read)"}, "growth": {"status": "unknown"},
             "metabolism": {"status": "measured_in_fish", "items": [{"quantity": "basal respiration trend", "value": "increases linearly from 3 to 48 hpf", "unit": "pmol O2/min/embryo", "per_stage_values": None, "source": "stackley2011", "note": "values are in figures that were not read"}]},
             "fins_and_scales": {"status": "modelled_and_fit_to_fish_data", "items": [{"quantity": "BMP gradient length scale in the pectoral fin bud", "value": "about 28 um at 60 hpf", "window_hpf": [48, 78], "source": "mateus2020"}]}, "locomotion": {"status": "unknown", "note": "no source read"}},
            {"id": "larva", "name": "Larva", "definition": Q("parichy2009", "Larva: An individual that is no longer an embryo but has yet to become a juvenile", "Life history stage definitions"),
             "time": {"start_hpf": 72, "end": "complete squamation and loss of the larval fin fold (about 4 weeks post-fertilization in the authors' laboratory)", "temperature_c": 28.5}, "size": {"unit": "mm", "measure": "SL (standard length); SSL = standardized standard length", "milestones": larva, "source": "parichy2009 Table 4"},
             "growth": {"status": "measured_in_fish", "items": [{"quantity": "SL growth rate", "unit": "mm/day", "values": {"24 C": "0.45 +/- 0.009 (mean +/- SE)", "33 C": "0.54 +/- 0.011 (mean +/- SE)"}, "source": "parichy2009", "note": "two temperature means only; no growth law"}]},
             "metabolism": {"status": "measured_in_fish", "items": [{"quantity": "oxygen consumption, larvae 0.6-0.9 cm", "value": "94.4 +/- 8.3", "unit": "pmol O2/min/larva (5 pooled)", "source": "konadu2023"}, {"quantity": "oxygen consumption, 5 dpf", "value": "126 +/- 4.6", "unit": "pmol O2/min/embryo (60 pooled)", "source": "konadu2023",
                       "disagreement": "Konadu calls 5 dpf fish 'embryos'; by Parichy's definition (embryo ends ~72 hpf) they are larvae. Both kept."}]},
             "fins_and_scales": {"status": "observed_qualitative", "items": [{"quantity": "median and pelvic fin ray appearance and squamation onset by size", "source": "parichy2009 Table 4", "see": "size.milestones"}]}, "locomotion": {"status": "unknown", "note": "no source read"}},
            {"id": "juvenile", "name": "Juvenile", "definition": Q("parichy2009", "Here defined by the attainment of a complete pattern of scales (squamation) and complete loss of the larval fin fold.", "Life history stage definitions"),
             "time": {"duration": Q("parichy2009", "the juvenile period lasts from ~4 weeks post-fertilization to 6–12 weeks post-fertilization depending on strain and rearing conditions", "Life history stage definitions")["quote"]},
             "size": {"unit": "mm", "entry": [m for m in t4 if m["milestone"] == "J"][0], "source": "parichy2009 Table 4"}, "growth": {"status": "unknown", "note": "no juvenile growth series was extracted"}, "metabolism": {"status": "unknown", "note": "no juvenile oxygen consumption value was read"},
             "fins_and_scales": {"status": "observed_qualitative", "items": [{"quantity": "scale row and column addition sequence; Fgf needed for initiation and outgrowth", "source": "aman2018"}]}, "locomotion": {"status": "unknown", "note": "no source read"}},
            {"id": "adult", "name": "Adult", "definition": Q("parichy2009", "Adult: Defined by the production of viable gametes and the appearance of secondary sexual characteristics in fish that are in breeding condition.", "Life history stage definitions"),
             "size": {"unit": "mm SL", "sexual_maturity_apparent_as_early_as": {"male": "17.5 +/- 0.6", "female": "18.3 +/- 0.7"}, "source": "parichy2009"},
             "growth": {"status": "unknown"}, "metabolism": {"status": "measured_in_fish", "items": [{"quantity": "oxygen consumption, 3-month and 12-month male", "value": "160", "unit": "pmol O2/min/animal", "source": "konadu2023", "flag": "unit or normalisation suspect: an adult is far heavier than a 5 dpf fish yet the per-animal value is close to the 5 dpf value (126); not used for sizing and not resolved here"}]},
             "fins_and_scales": {"status": "observed_qualitative", "items": [{"quantity": "fin regeneration growth rate maintained under calcineurin inhibition", "source": "daane2018", "note": "qualitative"}]}, "locomotion": {"status": "unknown", "note": "no source read"}}],
        "interfaces": [
            {"id": "size_sl", "unit": "mm", "role": "master developmental variable", "evidence": "measured_in_fish", "source": "parichy2009", "usable_for": "indexing stage by size", "not_for": "other species, or ages beyond the measured cohorts",
             "support": Q("parichy2009", "size (measured as SL or HAA) had the highest correlation with developmental progress for all traits examined", "Growth and environmental effects")},
            {"id": "sl_from_haa", "unit": "mm", "form": "SL = 3.56 * HAA + 4.40 (R^2 0.98; HAA > 0.5 mm)", "evidence": "measured_in_fish", "source": "parichy2009 Table 3"},
            {"id": "temperature", "unit": "C", "reference": 28.5, "effect": "SL growth 0.45 mm/day at 24 C and 0.54 mm/day at 33 C", "evidence": "measured_in_fish", "source": "parichy2009"},
            {"id": "o2_per_animal", "unit": "pmol O2/min/animal", "evidence": "measured_in_fish", "source": "konadu2023; stackley2011", "usable_for": "order of magnitude per animal at stated ages", "not_for": "volumetric consumption (animal volume and tissue mass were not obtained)"},
            {"id": "fin_gradient_lambda", "unit": "um", "value": "about 28 at 60 hpf", "evidence": "modelled_and_fit_to_fish_data", "source": "mateus2020", "not_for": "fins after 78 hpf, other fins, other species"},
            {"id": "diffusion_limit_borrowed", "unit": "um", "value": "r_l 233 +/- 22 (sphere, DLD1)", "evidence": "borrowed_nonfish", "source": "grimes2014", "not_for": "fish tissue or any bioink"},
            {"id": "scaffold_pore_windows", "unit": "um", "evidence": "borrowed_nonfish", "source": "mukasheva2024", "note": "ranges disagree across the cited works"}]}
    (OUT / "stages.json").write_text(json.dumps(stages, indent=1, sort_keys=True))
    # ---- bounded sizing check, borrowed parameters, geometry stated
    D, rl, sd = 2e-9, 233e-6, 22e-6
    c = df.c0_over_a_from_sphere_limit(D, rl)
    lo, hi = df.c0_over_a_from_sphere_limit(D, rl - sd), df.c0_over_a_from_sphere_limit(D, rl + sd)
    two = df.slab_max_total_thickness(D, c)
    comp = []
    for m in t4:
        if m["haa_pre_mm"] is not None:
            try:
                h = float(m["haa_pre_mm"].split("±")[0])
            except ValueError:
                continue
            comp.append({"milestone": m["milestone"], "haa_mm": h, "ratio_haa_to_two_sided_slab_limit": round(h * 1e-3 / two, 2)})
    check = {"schema": "fish-lifecycle-diffusion-check-0.1", "status": "SIZING AID UNDER BORROWED PARAMETERS. Not a feasibility statement and not a fish-tissue result.",
             "geometry_assumptions": ["uniform oxygen consumption, steady state, diffusion only, no perfusion", "sphere form is the paper's diffusion limit; the slab forms are derived here for a flat solid supplied from one or two faces"],
             "inputs": {"D_m2_per_s": {"value": D, "source": "grimes2014", "kind": "assumed close to water, not measured"}, "r_l_m": {"value": rl, "sd": sd, "source": "grimes2014", "kind": "fitted to DLD1 spheroids"},
                        "typical_diffusion_limit_um": {"value": "100-200", "source": "grimes2014 Introduction (citing others)"}},
             "derived": {"c0_over_a_s": c, "c0_over_a_s_range": [lo, hi], "slab_one_sided_limit_um": df.slab_limit_thickness(D, c) * 1e6, "slab_two_sided_total_thickness_um": two * 1e6,
                         "slab_two_sided_range_um": [df.slab_max_total_thickness(D, lo) * 1e6, df.slab_max_total_thickness(D, hi) * 1e6], "sphere_check_um": df.sphere_limit_radius(D, c) * 1e6},
             "comparison_with_fish_body_height": {"quantity": "HAA from Parichy 2009 Table 4 (before-milestone means, mm)", "rows": comp, "reading": "a perfusion-free solid block as tall as the fish at these stages would exceed the borrowed two-sided limit by the stated ratio; real fish tissue is vascularised and its consumption differs, so this exposes the scale of the constraint and nothing more"},
             "not_known": ["volumetric oxygen consumption of any zebrafish tissue", "C0 at a printed construct's surface", "D in a bioink or scaffold", "whether consumption stays constant as cells mature or proliferate", "any viability threshold for fish cells"],
             "claims_not_made": ["a living whole-fish bioprint is feasible", "a living whole-fish bioprint is infeasible", "the check applies to fish cells"]}
    (OUT / "nutrient_diffusion_check.json").write_text(json.dumps(check, indent=1, sort_keys=True))
    # ---- region assurance map
    S = {"measured_in_fish", "modelled_and_fit_to_fish_data", "observed_qualitative", "borrowed_nonfish", "unknown"}
    def cell(st, src="", note=""):
        assert st in S
        return {"status": st, "sources": src, "note": note}
    U = lambda note="no source read": cell("unknown", "", note)
    amap = {"schema": "fish-lifecycle-assurance-0.1 (connector-local)", "statuses": sorted(S), "organism": "Danio rerio", "stages": ["embryo", "larva", "juvenile", "adult"],
            "processes": {
                "staging_by_size": {"embryo": U("Kimmel 1995 not open access; not read"), "larva": cell("measured_in_fish", "parichy2009", "Table 4 milestones in SL, SSL and HAA"), "juvenile": cell("measured_in_fish", "parichy2009", "entry at 11.0 SSL"), "adult": cell("measured_in_fish", "parichy2009", "sexual maturity 17.5-18.3 mm SL")},
                "growth_rate": {"embryo": U(), "larva": cell("measured_in_fish", "parichy2009", "two temperature means; no growth law"), "juvenile": U("no series extracted"), "adult": U()},
                "fin_outgrowth_law": {"embryo": cell("modelled_and_fit_to_fish_data", "mateus2020", "exponential BMP gradient, lambda about 28 um at 60 hpf, 48-78 hpf only"), "larva": U("no quantitative fin growth law read"), "juvenile": U(), "adult": cell("observed_qualitative", "daane2018", "regeneration overgrowth under calcineurin inhibition; no equation")},
                "scale_formation": {"embryo": cell("unknown", "", "not applicable before squamation"), "larva": cell("observed_qualitative", "parichy2009; aman2018", "onset sizes (Table 4) and invariant row/column sequence; no equation"), "juvenile": cell("observed_qualitative", "aman2018", "Fgf needed for initiation and outgrowth"), "adult": U()},
                "oxygen_consumption": {"embryo": cell("measured_in_fish", "stackley2011", "linear increase 3-48 hpf; per-stage values not read"), "larva": cell("measured_in_fish", "konadu2023", "94.4 pmol/min/larva; 5 dpf 126 pmol/min/embryo (stage naming disagrees with Parichy)"), "juvenile": U(), "adult": cell("measured_in_fish", "konadu2023", "160 pmol/min/animal; unit or normalisation suspect")},
                "nutrient_diffusion_constraint": {s: cell("borrowed_nonfish", "grimes2014", "DLD1 spheroids, D assumed water-like; no fish tissue or bioink value") for s in ("embryo", "larva", "juvenile", "adult")},
                "cell_viability_in_printing": {s: U("not read (open-access bioprinting viability papers were found but not fetched)") for s in ("embryo", "larva", "juvenile", "adult")},
                "scaffold_mechanics_and_maturation": {s: cell("borrowed_nonfish", "mukasheva2024", "pore-size windows only; stiffness, degradation and maturation kinetics not extracted; ranges disagree") for s in ("embryo", "larva", "juvenile", "adult")},
                "locomotion": {s: U() for s in ("embryo", "larva", "juvenile", "adult")},
                "whole_organism_bioprint": {s: cell("unknown", "", "not claimed feasible or infeasible; no source supports either") for s in ("embryo", "larva", "juvenile", "adult")}},
            "claims_not_made": ["a living whole-fish bioprint is feasible", "any of these zebrafish values holds for a flying fish", "locomotion or maintenance cost models exist here"],
            "gaps_first": ["locomotion at every stage", "juvenile and adult growth series", "volumetric oxygen consumption of fish tissue", "viability thresholds for fish cells in a bioink", "scaffold stiffness, degradation and maturation kinetics", "quantitative fin-growth and scale-growth laws", "flying-fish stage boundaries and sizes"]}
    (OUT / "assurance.json").write_text(json.dumps(amap, indent=1, sort_keys=True))
    return check


if __name__ == "__main__":
    raise SystemExit(main())
