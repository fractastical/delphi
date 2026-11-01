"""The three printable forms: biological design JSON (SI) -> prop solid (mm).

Every parameter carries a `kind`:
  functional        -- enters the solver point or a sourced proportion (mass, wing area, span, SL, shares)
  figure_read       -- read by eye from a published figure
  design_assumption -- our choice, with a physical meaning (body density)
  aesthetic         -- shape choices with no claimed biological authority (sweep, taper, lobe angle...)
  print             -- prop-only (plate thickness, minimum feature radius, display scale)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from fractions import Fraction

import manifold3d as mf
import numpy as np

from . import mesh as M
from . import sources as src

PRINT = {
    "fin_thickness_mm": {"value": 1.6, "kind": "print",
                         "note": "exaggerated for a durable handled prop; >= ~1 mm is our provisional choice, 4x "
                                 "Formlabs' 0.4 mm design-spec wall (Form 2, Clear, 100 um); not a certified setting"},
    "min_feature_radius_mm": {"value": 1.0, "kind": "print",
                              "note": "planforms are opened by this radius, so no in-plane sliver is under 2 mm"},
    "min_body_half_size_mm": {"value": 1.2, "kind": "print", "note": "blunts the snout/jaw tip"},
    "max_extent_mm": {"value": 118.0, "kind": "print",
                      "note": "longest of length/span after scaling; leaves margin inside a 120 mm box"},
    "min_length_mm": {"value": 90.0, "kind": "print", "note": "the brief's 90-120 mm prop length"},
}

SIMPLIFY_TOL_MM = 1e-3  # removes zero-area boolean slivers; surfaces move < 1 um

LABEL = ("Form study pending a validated candidate. Engineered illustrative form. Not an ancestor, not a viable organism, not a demonstrated evolutionary "
         "path, not flight-tested. Fins are thickened for printing.")


@dataclass
class FormSpec:
    id: str
    title: str
    role: str
    genus: str  # Fish 1990 genus whose fits supply SL, body and caudal (and, for gliders, wing area and span)
    mass_kg: float
    fins_from: str  # "fish_fit": wing area/span/share from Fish 1990; "fin_ratio": fin lengths from Daane S1A
    pelvic_ratio_key: str  # Daane 2021 S1A group or "group | species" for pelvic length / SL
    pectoral_share: float | None = None  # Fish 1990 Table IV (fish_fit forms)
    pectoral_ratio_key: str | None = None  # fin_ratio forms
    fin_shape_from: str | None = None  # fin_ratio forms borrow area/length^2 from this form's layout
    status_note: str = ""
    params: dict = field(default_factory=dict)
    set_id: str = "morphology-v1"
    short: str = ""  # tab label
    wing_factors: tuple[float, float] | None = None  # (area, whole-wing AR) factors on the Fish fit (NCA set)
    body_profile: str = "v1"  # key of PROFILES; "v1" is the frozen defect the published v1 sets were built with


PROFILES = {"v1": M.body_profile_v1, "pointwise": M.body_profile}


def profile_of(spec: FormSpec):
    return PROFILES[spec.body_profile]


def P(value, kind, note="", locator=""):
    d = {"value": value, "kind": kind}
    if note:
        d["note"] = note
    if locator:
        d["locator"] = locator
    return d


def aesthetic_defaults(**over) -> dict:
    a = {
        "body_height_over_width": P(1.15, "aesthetic"),
        "ventral_flattening": P(1.0, "aesthetic", "1 = elliptical; <1 flattens the belly"),
        "peduncle_fraction": P(0.16, "aesthetic"),
        "pectoral_base_fraction": P(0.38, "aesthetic", "fin base chord / max chord (narrow fan base)"),
        "pectoral_s_max": P(0.35, "aesthetic"),
        "pectoral_sweep_deg": P(12.0, "aesthetic"),
        "pectoral_dihedral_deg": P(5.0, "aesthetic"),
        "pectoral_root_height": P(0.35, "aesthetic", "fraction of local upper half-height"),
        "pelvic_base_fraction": P(0.45, "aesthetic"),
        "pelvic_s_max": P(0.4, "aesthetic"),
        "pelvic_sweep_deg": P(20.0, "aesthetic"),
        "pelvic_dihedral_deg": P(3.0, "aesthetic"),
        "pelvic_root_height": P(-0.55, "aesthetic"),
        "caudal_angle_deg": P(27.0, "aesthetic"),
        "caudal_notch_fraction": P(0.32, "aesthetic"),
        "dorsal_anal_fins": P(True, "aesthetic", "small vertical fins; excluded from wing area"),
        "lower_jaw_over_sl": P(0.0, "aesthetic"),
    }
    a.update(over)
    return a


_B_SHAPE = dict(body_height_over_width=P(1.2, "aesthetic", "streamlined, after Breder 1930 via Fish 1990 p.397"))
_C_SHAPE = dict(
    ventral_flattening=P(0.62, "aesthetic", "Cypselurus body is 'ventrally flattened' (Fish 1990 p.394, after "
                         "Breder 1930); the factor is ours"),
    body_height_over_width=P(1.05, "aesthetic"), pectoral_sweep_deg=P(16.0, "aesthetic"),
    pectoral_dihedral_deg=P(7.0, "aesthetic"), pelvic_sweep_deg=P(30.0, "aesthetic"),
    pelvic_dihedral_deg=P(4.0, "aesthetic"), pelvic_root_height=P(-0.35, "aesthetic"),
    pelvic_base_fraction=P(0.35, "aesthetic"), pelvic_s_max=P(0.3, "aesthetic"))
_CHEILOPOGON = ("Pelvic length / SL is from Cheilopogon furcatus (four-wing; Cypselurus is not in Daane S1A): "
                "a cross-genus substitution.")

# Sets are versioned and never overwritten: a new dimension set gets new form ids, its own display scale and its own
# candidates, and the earlier set's files stay as they were.
SETS = {
    "morphology-v1": {
        "title": "Morphology set: three body plans at 0.1 kg",
        "note": "A, B, C compare body plans at one mass (Fish 1990 p.399 comparison mass)"},
    "nca-comparison-v1": {
        "title": "Wing-geometry comparison set: Cypselurus at 0.05 kg (dx-nca controlled run)",
        "note": "N1-N3 vary only wing area and whole-wing aspect ratio on one Cypselurus body. A comparison set "
                "for a geometry-effect test (equilibrium sink falls with S and AR in NCA's simulation), not an "
                "optimum; range ordering flips with release speed",
        "source": src.NCA_CONTROLLED},
}
V2_NOTE = ("v2 corrects the body half-width used at single stations (fin roots, dorsal/anal fins, stand saddle): v1 "
           "evaluated mesh.body_profile_v1, which normalises by its input's maximum and so returned near full width "
           "at any single point.  Same sources, solver, print rules and shape parameters as v1; the v1 files stay "
           "as published.")
SETS.update({
    "morphology-v2": {"title": SETS["morphology-v1"]["title"] + " (v2, corrected body profile)",
                      "note": SETS["morphology-v1"]["note"] + ". " + V2_NOTE, "supersedes": "morphology-v1"},
    "nca-comparison-v2": {"title": SETS["nca-comparison-v1"]["title"] + " (v2, corrected body profile)",
                          "note": SETS["nca-comparison-v1"]["note"] + ". " + V2_NOTE, "source": src.NCA_CONTROLLED,
                          "supersedes": "nca-comparison-v1"},
})

FORMS = [
    FormSpec(
        id="A-precursor-short-fin",
        title="Precursor-inspired short-fin form (rejected glider candidate)", short="A · short-fin precursor-inspired",
        role="Form B's body at 0.1 kg with the paired-fin lengths measured on non-gliding halfbeaks; isolates fin "
             "length, and the solver rejects it",
        genus="Exocoetus", mass_kg=0.1, fins_from="fin_ratio",
        pectoral_ratio_key="halfbeak", pelvic_ratio_key="halfbeak", fin_shape_from="B-two-wing-glider",
        status_note="Body held equal to Form B (Exocoetus fits) on purpose: no halfbeak length-mass fit was read. "
                    "The elongate jaw is a qualitative halfbeak feature.",
        params=aesthetic_defaults(**_B_SHAPE, lower_jaw_over_sl=P(
            0.22, "aesthetic", "halfbeak-like elongate lower jaw; qualitative (flyingfishes are nested within the "
            "halfbeak grade, Lovejoy et al. 2004, abstract; Daane et al. 2021 Results)")),
    ),
    FormSpec(
        id="B-two-wing-glider",
        title="Enlarged-pectoral two-wing glider (Exocoetus-type proportions)", short="B · two-wing",
        role="monoplane design: pectorals carry 91.8% of wing area (Fish 1990 Table IV)",
        genus="Exocoetus", mass_kg=0.1, fins_from="fish_fit",
        pectoral_share=src.TABLE_IV["Exocoetus"]["pectoral_pct"] / 100,
        pelvic_ratio_key="flying fish | Exocoetus volitans",
        params=aesthetic_defaults(**_B_SHAPE),
    ),
    FormSpec(
        id="C-four-wing-glider",
        title="Enlarged pectoral + pelvic four-wing glider (Cypselurus-type proportions)", short="C · four-wing",
        role="biplane design: pectorals 76.0%, pelvics + body the rest (Fish 1990 Table IV)",
        genus="Cypselurus", mass_kg=0.1, fins_from="fish_fit",
        pectoral_share=src.TABLE_IV["Cypselurus"]["pectoral_pct"] / 100,
        pelvic_ratio_key="flying fish | Cheilopogon furcatus",
        status_note=_CHEILOPOGON,
        params=aesthetic_defaults(**_C_SHAPE),
    ),
] + [
    FormSpec(
        id=fid, title=title, short=short, set_id="nca-comparison-v1",
        role=role, genus="Cypselurus", mass_kg=0.05, fins_from="fish_fit",
        pectoral_share=src.TABLE_IV["Cypselurus"]["pectoral_pct"] / 100,
        pelvic_ratio_key="flying fish | Cheilopogon furcatus", wing_factors=wf,
        status_note=_CHEILOPOGON + " Body, fins and shape parameters as Form C; only S and b differ within the set.",
        params=aesthetic_defaults(**_C_SHAPE))
    for fid, title, short, role, wf in (
        ("N1-cypselurus-baseline", "Comparison N1: Cypselurus baseline, 0.05 kg", "N1 · baseline",
         "Fish 1990 Cypselurus wing-area and span fits at 0.05 kg (NCA baseline)", (1.0, 1.0)),
        ("N2-area-x1.3", "Comparison N2: wing area x1.3, same aspect ratio", "N2 · area ×1.3",
         "N1 with wing area x1.3 at the same whole-wing b^2/S (NCA variant fS 1.3, fAR 1.0)", (1.3, 1.0)),
        ("N3-area-x1.3-ar-x1.2", "Comparison N3: wing area x1.3, aspect ratio x1.2", "N3 · area ×1.3, AR ×1.2",
         "N1 with wing area x1.3 and whole-wing b^2/S x1.2 (NCA variant fS 1.3, fAR 1.2)", (1.3, 1.2)))
]


def _v2(spec: FormSpec) -> FormSpec:
    """The same form with the pointwise body profile, under a new id and set (v1 ids keep their v1 files)."""
    return replace(spec, id=spec.id + "-v2", set_id=spec.set_id.replace("-v1", "-v2"), short=spec.short + " · v2",
                   title=spec.title + " (v2)", body_profile="pointwise",
                   fin_shape_from=spec.fin_shape_from and spec.fin_shape_from + "-v2",
                   status_note=(spec.status_note + " " if spec.status_note else "") +
                   f"v2 of {spec.id}: body half-width at single stations corrected (see the set note).")


FORMS_V2 = [_v2(f) for f in FORMS]
EDITIONS = {"v1": FORMS, "v2": FORMS_V2}  # build.py builds one edition per output directory
FORMS_BY_ID = {f.id: f for f in FORMS + FORMS_V2}


def _v(p):
    return p["value"]


def daane_ratio(key: str, fin: str) -> dict:
    summ = src.daane_summary()
    rec = summ["groups"][key] if key in summ["groups"] else summ["species"][key]
    r = rec[f"{fin}_over_sl"]
    return P(r["median"], "functional",
             f"median of n={r['n']} specimens, range {r['min']:.3f}-{r['max']:.3f}; recomputed from raw lengths",
             f"Daane et al. 2021 Data S1A, '{key}' (xlsx sha256 {summ['xlsx_sha256'][:16]}...)")


def biological_point(spec: FormSpec) -> dict:
    """Sourced biological inputs (SI) before the fin layout is resolved."""
    m = spec.mass_kg
    sl = src.fit(spec.genus, "length", m)
    mass_loc = (src.COMPARISON_MASS["locator"] if spec.set_id.startswith("morphology-") else
                f"dx-nca comparison protocol mass (work/nca-glide @ {src.NCA_CONTROLLED['commit'][:7]}); inside Fish "
                "1990's 0.003-0.53 kg specimens")
    out = {"mass_kg": P(m, "functional", locator=mass_loc),
           "standard_length_m": P(sl, "functional", locator=f"Fish 1990 Table I, {spec.genus} length fit")}
    if spec.fins_from == "fish_fit":
        S0, b0 = src.fit(spec.genus, "area", m), src.fit(spec.genus, "span", m)
        fS, fAR = spec.wing_factors or (1.0, 1.0)
        S, b = fS * S0, math.sqrt(fAR * b0 ** 2 / S0 * fS * S0)
        tag = "" if spec.wing_factors is None else f" x area {fS:g}, whole-wing AR x{fAR:g} (NCA comparison variant)"
        out["wing_area_m2"] = P(S, "functional", locator=f"Fish 1990 Table I, {spec.genus} wing-area fit{tag}")
        out["wing_span_m"] = P(b, "functional", locator=f"Fish 1990 Table I, {spec.genus} wing-span fit{tag}")
        out["pectoral_share"] = P(spec.pectoral_share, "functional", locator=f"Fish 1990 Table IV, {spec.genus}")
    else:
        out["pectoral_length_over_sl"] = daane_ratio(spec.pectoral_ratio_key, "pectoral")
    out["pelvic_length_over_sl"] = daane_ratio(spec.pelvic_ratio_key, "pelvic")
    out["hypocaudal_area_m2"] = P(src.fit(spec.genus, "hypocaudal_area", m), "functional",
                                  locator=f"Fish 1990 Table I, {spec.genus} hypocaudal-area fit")
    out["hypocaudal_share"] = P(src.TABLE_IV[spec.genus]["hypocaudal_pct"] / 100, "functional",
                                locator=f"Fish 1990 Table IV, {spec.genus}")
    out["body_density_kg_m3"] = P(src.BODY_DENSITY["value_kg_m3"], "design_assumption", src.BODY_DENSITY["basis"])
    out["fin_x_over_sl"] = P(dict(pectoral=src.FIGURE_READ[spec.genus]["pectoral_x_sl"],
                                  pelvic=src.FIGURE_READ[spec.genus]["pelvic_x_sl"]), "figure_read",
                             locator=src.FIGURE_READ[spec.genus]["locator"])
    return out


def body_scale(sl: float, mass: float, rho: float, a: dict, profile) -> tuple[float, float]:
    """Max half-width W (m) such that the loft's volume equals mass / density.  Returns (W, volume)."""
    s = np.linspace(0, 1, 4001)
    f = profile(s, _v(a["peduncle_fraction"]))
    I = float(np.trapezoid(f * f, s))
    k = _v(a["body_height_over_width"]) * (1 + _v(a["ventral_flattening"]))
    V = mass / rho
    W = math.sqrt(V / (0.5 * math.pi * k * sl * I))
    return W, V


def _chord_integral(base_frac: float, s_max: float) -> float:
    x = np.linspace(0, 1, 2001)
    return float(np.trapezoid(M.fin_chord(x, base_frac, s_max), x))


def fin_layout(spec: FormSpec, bio: dict, shape_ref: dict | None = None, profile=None) -> dict:
    """Fin lengths, areas, chords and body rectangles in SI, before print-only opening/thickening.
    Fish 1990 wing area = 2 pectoral + 2 pelvic + the body rectangle at each fin base (base chord x body width).
    `profile` defaults to the spec's (profile_of)."""
    profile = profile or profile_of(spec)
    a = spec.params
    sl = _v(bio["standard_length_m"])
    W = _v(bio["body_half_width_max_m"])
    ped = _v(a["peduncle_fraction"])
    xf = _v(bio["fin_x_over_sl"])
    width = {k: 2 * W * float(profile(np.array([xf[k]]), ped)[0]) for k in ("pectoral", "pelvic")}
    Ip = _chord_integral(_v(a["pectoral_base_fraction"]), _v(a["pectoral_s_max"]))
    Iv = _chord_integral(_v(a["pelvic_base_fraction"]), _v(a["pelvic_s_max"]))
    L_v = _v(bio["pelvic_length_over_sl"]) * sl
    if spec.fins_from == "fish_fit":
        S, b, p = _v(bio["wing_area_m2"]), _v(bio["wing_span_m"]), _v(bio["pectoral_share"])
        A_p = p * S / 2
        L_p = (b - width["pectoral"]) / 2
        base_p = _v(a["pectoral_base_fraction"]) * A_p / (L_p * Ip)
        rect_p = base_p * width["pectoral"]
        rect_v = 0.0
        for _ in range(100):
            A_v = ((1 - p) * S - rect_p - rect_v) / 2
            if A_v <= 0:
                raise ValueError(f"{spec.id}: no wing area left for pelvic fins")
            new = _v(a["pelvic_base_fraction"]) * A_v / (L_v * Iv) * width["pelvic"]
            if abs(new - rect_v) < 1e-15:
                break
            rect_v = new
    else:
        L_p = _v(bio["pectoral_length_over_sl"]) * sl
        A_p = shape_ref["pectoral_area_over_length2"] * L_p ** 2
        A_v = shape_ref["pelvic_area_over_length2"] * L_v ** 2
        rect_p = _v(a["pectoral_base_fraction"]) * A_p / (L_p * Ip) * width["pectoral"]
        rect_v = _v(a["pelvic_base_fraction"]) * A_v / (L_v * Iv) * width["pelvic"]
        S = 2 * A_p + 2 * A_v + rect_p + rect_v
        b = 2 * L_p + width["pectoral"]
        p = 2 * A_p / S
    return {"pectoral_area_per_fin_m2": A_p, "pectoral_length_m": L_p, "pelvic_area_per_fin_m2": A_v,
            "pelvic_length_m": L_v, "body_rectangles_m2": rect_p + rect_v, "wing_area_m2": S, "wing_span_m": b,
            "pectoral_share": p, "body_width_at_fins_m": width,
            "pectoral_area_over_length2": A_p / L_p ** 2, "pelvic_area_over_length2": A_v / L_v ** 2,
            "pectoral_length_over_sl": L_p / sl, "pelvic_length_over_sl": L_v / sl}


def complete_point(spec: FormSpec, bio: dict, shape_ref: dict | None = None, profile=None) -> dict:
    """Body size from volume = mass / density, then the fin layout; fin_ratio forms get S, b, share from it.
    `profile` defaults to the spec's: the frozen v1 function for v1 forms, so the published sets rebuild unchanged
    (see mesh.py), the pointwise one for v2 forms."""
    profile = profile or profile_of(spec)
    a = spec.params
    sl = _v(bio["standard_length_m"])
    W, V = body_scale(sl, spec.mass_kg, _v(bio["body_density_kg_m3"]), a, profile)
    bio["body_half_width_max_m"] = P(W, "derived", "from body volume = mass / density and the aesthetic profile")
    bio["body_volume_m3"] = P(V, "derived", "mass / body density")
    lay = fin_layout(spec, bio, shape_ref, profile)
    if spec.fins_from == "fin_ratio":
        note = (f"derived: Daane S1A fin lengths x Form {spec.fin_shape_from} fin shape (area / length^2), "
                "plus body rectangles (Fish 1990 definition)")
        bio["wing_area_m2"] = P(lay["wing_area_m2"], "derived", note)
        bio["wing_span_m"] = P(lay["wing_span_m"], "derived", "2 * pectoral length + body width at fin base")
        bio["pectoral_share"] = P(lay["pectoral_share"], "derived", note)
        bio["fin_shape_reference"] = P({k: shape_ref[k] for k in ("pectoral_area_over_length2",
                                                                    "pelvic_area_over_length2")}, "design_assumption",
                                       f"fin planform shape borrowed from {spec.fin_shape_from}")
    bio["fin_layout_bio"] = P(lay, "derived")
    bio["aspect_ratio_conventions"] = P(aspect_ratios(spec, lay), "derived", AR_NOTE)
    return bio


AR_NOTE = ("Fish 1990 Table III reports the aspect ratio of the pectoral fin (p.395); which span and area enter it "
           "is not settled here (fable-to-print v2 flags the same open definition).  Three conventions are computed "
           "so a reader can see which one the Table III fit is near.  None of them is fed to the solver by this "
           "module; the solver's AR is whatever guilds' model computes from span and area.")


def aspect_ratios(spec: FormSpec, lay: dict) -> dict:
    L, A, S, b = lay["pectoral_length_m"], lay["pectoral_area_per_fin_m2"], lay["wing_area_m2"], lay["wing_span_m"]
    a, e, _rng = src.TABLE_III[spec.genus]
    return {"single_pectoral_length2_over_area": L ** 2 / A,
            "span2_over_both_pectorals": b ** 2 / (2 * A),
            "whole_wing_span2_over_area": b ** 2 / S,
            "fish1990_table_III_fit_at_mass": a * spec.mass_kg ** e,
            "fish1990_table_III_observed_range": list(_rng)}


def complete_all(forms=None) -> list[dict]:
    """Complete every form; fin_ratio forms after the form whose fin shape they borrow."""
    forms = forms or FORMS
    done: dict[str, dict] = {}
    for spec in sorted(forms, key=lambda f: f.fins_from == "fin_ratio"):
        ref = _v(done[spec.fin_shape_from]["fin_layout_bio"]) if spec.fin_shape_from else None
        done[spec.id] = complete_point(spec, biological_point(spec), ref)
    return [done[f.id] for f in forms]


def caudal_lengths(sl, ped_half, a, hypo_area, hypo_share):
    total = hypo_area / hypo_share
    upper_t = total - hypo_area
    x0 = sl * 0.97
    ang, notch = _v(a["caudal_angle_deg"]), _v(a["caudal_notch_fraction"])
    up = M.solve_lobe(upper_t, 0.5 * sl, "upper", x0, ped_half, ang, notch)
    for _ in range(30):  # notch depends on the upper lobe; alternate until stable
        lo = M.solve_lobe(hypo_area, up, "lower", x0, ped_half, ang, notch)
        up2 = M.solve_lobe(upper_t, lo, "upper", x0, ped_half, ang, notch)
        if abs(up2 - up) < 1e-9:
            break
        up = up2
    return x0, up, lo


def built_extents(spec: FormSpec, bio: dict, scale: float, res: M.Resolution | None = None) -> dict:
    """Length and span (prop mm) of a coarse trial build AT `scale`.  Measured at the candidate scale itself:
    print-only features (plate thickness, the 1 mm opening of fin and lobe tips) do not scale, so a trial at another
    scale misjudged lengths by ~4 % (88.5 mm predicted, 92.5 mm built, for N1 at 9/20)."""
    m, _ = build_prop(spec, bio, scale, res or M.Resolution(36, 24, 24, 16))
    bb = m.bounding_box()
    return {"length_mm": bb[3] - bb[0], "span_mm": bb[4] - bb[1]}


NICE_SCALES = (Fraction(1, 2), Fraction(9, 20), Fraction(2, 5), Fraction(3, 8), Fraction(7, 20), Fraction(1, 3),
               Fraction(3, 10), Fraction(1, 4), Fraction(1, 5))


def display_scale(members: list[tuple[FormSpec, dict]]) -> tuple[float, dict]:
    """One scale per set (so sizes within a set compare directly).  Hard rule: every length and span <=
    max_extent_mm.  Aim: every form >= min_length_mm long.  Scales are tried largest first on coarse trial builds;
    the first meeting both is used.  If none does, the largest that meets the hard rule is used and the shortfall
    is reported with the measurements, never hidden.  Final built bounds are re-checked by the build and tests."""
    top, low = PRINT["max_extent_mm"]["value"], PRINT["min_length_mm"]["value"]
    tried, fallback = [], None
    for s in NICE_SCALES:
        ext = [built_extents(spec, bio, float(s)) for spec, bio in members]
        longest = max(max(e["length_mm"], e["span_mm"]) for e in ext)
        shortest = min(e["length_mm"] for e in ext)
        tried.append({"scale": str(s), "longest_mm": round(longest, 2), "shortest_length_mm": round(shortest, 2)})
        if longest > top:
            continue
        fallback = fallback or (s, shortest, longest)
        if shortest >= low:
            return float(s), {"min_length_mm": low, "max_extent_mm": top, "met": True, "trials": tried}
    if fallback is None:
        raise ValueError(f"no listed display scale fits: {tried}")
    s, shortest, longest = fallback
    return float(s), {"min_length_mm": low, "max_extent_mm": top, "met": False, "trials": tried,
                      "reason": f"no listed scale gives every form >= {low:g} mm long with every extent <= {top:g} mm; "
                                f"at {s} the shortest is {shortest:.1f} mm"}


def build_prop(spec: FormSpec, bio: dict, scale: float, res: M.Resolution = M.Resolution()) -> tuple[mf.Manifold, dict]:
    """Prop solid in mm and a report of what was built, converted back to biological units for comparison."""
    a = spec.params
    k = 1000 * scale  # m -> prop mm
    t = PRINT["fin_thickness_mm"]["value"]
    r_open = PRINT["min_feature_radius_mm"]["value"]
    r_min = PRINT["min_body_half_size_mm"]["value"]
    sl = _v(bio["standard_length_m"]) * k
    W = _v(bio["body_half_width_max_m"]) * k
    hw, flat, ped = _v(a["body_height_over_width"]), _v(a["ventral_flattening"]), _v(a["peduncle_fraction"])
    to_bio_area = 1 / (k * k)

    def prof(s):
        return profile_of(spec)(np.asarray(s, dtype=float), ped)  # v1 forms: the frozen defect (see mesh.py)

    # --- body: cosine-clustered stations, half-sizes clamped to the print minimum near the snout
    s = 0.5 * (1 - np.cos(np.linspace(0, np.pi, res.stations)))
    f = prof(s)
    hw_x = np.maximum(W * f, r_min)
    hu_x = np.maximum(W * hw * f, r_min)
    hd_x = np.maximum(W * hw * flat * f, r_min)
    body = M.loft(s * sl, hw_x, hu_x, hd_x, np.zeros_like(s), res.ring, nose_x=-0.6 * r_min)
    parts = [body]
    built = {"body_loft_volume_mm3": body.volume()}

    def half_sizes(xf):
        ff = float(prof([xf])[0])
        return W * ff, W * hw * ff, W * hw * flat * ff

    # --- pectoral fins
    xp = _v(bio["fin_x_over_sl"])["pectoral"]
    w_p, hu_p, hd_p = half_sizes(xp)
    zf = _v(a["pectoral_root_height"])
    z_p = zf * hu_p
    y_surf_p = w_p * math.sqrt(max(1 - zf * zf, 0.05))
    lay = _v(bio["fin_layout_bio"])
    L_p = lay["pectoral_length_m"] * k  # Fish's span: 2 * fin length + body width at the fin base
    A_p = lay["pectoral_area_per_fin_m2"] * k * k
    c_p, cs_p, a_p = M.solve_cmax(A_p, L_p, _v(a["pectoral_base_fraction"]), _v(a["pectoral_s_max"]),
                                  _v(a["pectoral_sweep_deg"]), y_surf_p * 0.9, r_open, res)
    base_p = _v(a["pectoral_base_fraction"]) * c_p
    x_le_p = xp * sl - 0.3 * base_p
    for side in (1, -1):
        parts.append(M.place_fin(cs_p, t, x_le_p, y_surf_p, z_p, _v(a["pectoral_dihedral_deg"]), side))

    # --- pelvic fins: length from Daane S1A, area from the layout (Fish 1990 remainder, or borrowed shape)
    xv = _v(bio["fin_x_over_sl"])["pelvic"]
    w_v, hu_v, hd_v = half_sizes(xv)
    zv = _v(a["pelvic_root_height"])
    z_v = zv * hd_v
    y_surf_v = w_v * math.sqrt(max(1 - zv * zv, 0.05))
    L_v = lay["pelvic_length_m"] * k
    A_v = lay["pelvic_area_per_fin_m2"] * k * k
    c_v, cs_v, a_v = M.solve_cmax(A_v, L_v, _v(a["pelvic_base_fraction"]), _v(a["pelvic_s_max"]),
                                  _v(a["pelvic_sweep_deg"]), y_surf_v * 0.9, r_open, res)
    rect_p = base_p * 2 * w_p
    rect_v = _v(a["pelvic_base_fraction"]) * c_v * 2 * w_v
    base_v = _v(a["pelvic_base_fraction"]) * c_v
    x_le_v = xv * sl - 0.3 * base_v
    for side in (1, -1):
        parts.append(M.place_fin(cs_v, t, x_le_v, y_surf_v, z_v, _v(a["pelvic_dihedral_deg"]), side))

    # --- caudal fin, hypocaudal (lower) lobe larger as measured
    ped_half = W * hw * ped
    x0, up, lo = caudal_lengths(sl, ped_half, a, _v(bio["hypocaudal_area_m2"]) * k * k, _v(bio["hypocaudal_share"]))
    cpoly = M.caudal_planform(x0, ped_half, up, lo, _v(a["caudal_angle_deg"]), _v(a["caudal_notch_fraction"]) * up)
    caudal, caudal_area = M.xz_plate(cpoly, t, r_open, res.circular)
    parts.append(caudal)
    up_a, lo_a = M.lobe_areas(cpoly)

    # --- small dorsal and anal fins (aesthetic; not part of the wing area)
    if _v(a["dorsal_anal_fins"]):
        for sign, (s0, s1) in ((1, (0.66, 0.84)), (-1, (0.64, 0.80))):
            _, hu0, hd0 = half_sizes(s0)
            _, hu1, hd1 = half_sizes(s1)
            h0 = (hu0 if sign > 0 else hd0) * 0.6
            h1 = (hu1 if sign > 0 else hd1) * 0.6
            tip = 0.075 * sl
            poly = np.array([(s0 * sl, sign * h0), (s1 * sl, sign * h1), (s1 * sl + 0.02 * sl, sign * (h1 + tip * 0.45)),
                             (s0 * sl + 0.05 * sl, sign * (h0 + tip))])
            fin, _ = M.xz_plate(poly, t, r_open, res.circular)
            parts.append(fin)

    # --- elongate lower jaw (precursor form only)
    jaw = _v(a["lower_jaw_over_sl"]) * sl
    if jaw > 0:
        n = max(12, res.stations // 4)
        js = np.linspace(0, 1, n)
        xs = -jaw + js * (jaw + 0.12 * sl)
        _, _, hd_j = half_sizes(0.06)
        r0 = max(0.45 * hd_j, 2 * r_min)
        rr = np.maximum(r0 * js ** 0.7, r_min)
        z_j = -0.55 * hd_j
        parts.append(M.loft(xs, rr, rr * 0.8, rr * 0.8, np.full(n, z_j), max(16, res.ring // 2),
                            nose_x=-jaw - 0.6 * r_min))

    solid = mf.Manifold.batch_boolean(parts, mf.OpType.Add).simplify(SIMPLIFY_TOL_MM)
    if solid.status() != mf.Error.NoError:
        raise ValueError(f"{spec.id}: boolean union failed: {solid.status()}")

    bb = solid.bounding_box()
    built.update({
        "pectoral_area_per_fin_bio_m2": a_p * to_bio_area, "pectoral_area_target_bio_m2": A_p * to_bio_area,
        "pectoral_fin_length_bio_m": L_p / k, "pectoral_max_chord_bio_m": c_p / k,
        "pectoral_base_chord_bio_m": base_p / k,
        "pelvic_area_per_fin_bio_m2": a_v * to_bio_area, "pelvic_area_target_bio_m2": A_v * to_bio_area,
        "pelvic_fin_length_bio_m": L_v / k, "pelvic_max_chord_bio_m": c_v / k,
        "body_rectangles_bio_m2": (rect_p + rect_v) * to_bio_area,
        "wing_area_built_bio_m2": (2 * a_p + 2 * a_v + rect_p + rect_v) * to_bio_area,
        "wing_area_target_bio_m2": _v(bio["wing_area_m2"]),
        "span_target_bio_m": _v(bio["wing_span_m"]),
        "span_built_flat_bio_m": (2 * (y_surf_p + L_p)) / k,
        "caudal_area_opened_bio_m2": caudal_area * to_bio_area,
        "hypocaudal_share_built": lo_a / (up_a + lo_a),
        "lower_jaw_bio_m": jaw / k,
        "pectoral_prop_area_exaggeration": a_p / A_p, "pelvic_prop_area_exaggeration": a_v / A_v,
        "prop_area_exaggeration_note": "ratio of printed (opened, >= 2 mm wide) planform area to the scaled "
                                       "biological target; > 1 means the fin was widened for print only",
        "span_built_bbox_bio_m": (bb[4] - bb[1]) / k,
        "prop_bounds_mm": [list(bb[:3]), list(bb[3:])],
        "prop_volume_mm3": solid.volume(),
        "display_scale": scale,
    })
    return solid, built


def body_section_mm(spec: FormSpec, bio: dict, scale: float):
    """(half_width_at(x_mm), bottom_z_at(x_mm)) for the prop body, used to size the stand saddle."""
    a = spec.params
    k = 1000 * scale
    sl = _v(bio["standard_length_m"]) * k
    W = _v(bio["body_half_width_max_m"]) * k
    hw, flat, ped = _v(a["body_height_over_width"]), _v(a["ventral_flattening"]), _v(a["peduncle_fraction"])

    def f(x):
        return float(profile_of(spec)(np.array([min(max(x / sl, 0), 1)]), ped)[0])
    return (lambda x: W * f(x)), (lambda x: -W * hw * flat * f(x))
