"""Source numbers the printable forms are derived from, each with its locator and read level.

Everything here is a transcription or a labelled choice.  A value with `kind="source"` was read from the
cited document; `kind="figure_read"` was read off a published figure by eye (low precision);
`kind="design_assumption"` and `kind="aesthetic"` are ours and carry no biological authority.

Fish 1990 was retrieved by this worker on 2026-10-31 from the author's university page; its sha256
matches the copy dx-guilds read (`engineering/constraints.py` SOURCES, branch work/guilds-engineering
@ 6612af6 and 948c2e1).  Table I and Table IV were read from `pdftotext -layout` output.  The OCR drops decimal
points ("0460" for 0.460); restored values are cross-checked in `table_cross_check()` against Table II,
an independent r.m.a. fit to the same specimens.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DAANE_SUMMARY = REPO / "artifacts/print/sources/daane2021-S1A-summary.json"

FISH1990 = {
    "id": "fish1990",
    "citation": "Fish, F. E. (1990). Wing design and scaling of flying fish with regard to flight performance. "
                "J. Zool., Lond. 221: 391-403.",
    "url": "https://health-sciences.wcupa.edu/sciences-mathematics/biology/fFish/documents/1990JZWing%20design.pdf",
    "sha256": "1efed334ed4aa48ec8e23801ff0b420d1d5c21430100a6d86d0b3e569421f8ea",
    "bytes": 368219,
    "read_level": "full-text",
    "retrieved": "2026-10-31 (print worker; HTTP 200)",
    "specimens": "199 preserved specimens, 33 species, 6 genera, 0.003-0.53 kg (p.393)",
}

# Table I (p.394): r.m.a. fits  Y = a * M^b, M in kg; lengths in m, areas in m^2 (units inferred: the fits give
# 0.20 m standard length and 0.0089 m^2 wing area at 0.1 kg, consistent with Table II wing loadings).
# Wing area = pectoral + pelvic fins + the rectangles of body between them (Methods, p.392-393).
# Wing span = 2 * (fin base to tip) + body width (Methods).
TABLE_I = {
    "Cypselurus": {"n": 113, "length": (0.460, 0.355), "span": (0.651, 0.375), "area": (0.039, 0.642),
                   "hypocaudal_area": (0.003, 0.650)},
    "Exocoetus": {"n": 26, "length": (0.462, 0.347), "span": (0.774, 0.380), "area": (0.046, 0.741),
                  "hypocaudal_area": (0.004, 0.729)},
}
# Table II (p.395): wing loading WL = a * M^b (N/m^2) -- used only as an independent cross-check.
TABLE_II = {"Cypselurus": (285.015, 0.400, (16.1, 205.5)), "Exocoetus": (300.101, 0.360, (40.3, 139.2))}
# Table III (p.396): aspect ratio of individual pectoral fins, AR = a * M^b (Exocoetus r not significant).
TABLE_III = {"Cypselurus": (12.717, 0.163, (3.0, 12.2)), "Exocoetus": (23.410, 0.195, (8.9, 19.9))}
# Table IV (p.397): mean % of wing area that is pectoral fin; % of caudal fin that is hypocaudal lobe.
TABLE_IV = {"Cypselurus": {"pectoral_pct": 75.99, "hypocaudal_pct": 62.63},
            "Exocoetus": {"pectoral_pct": 91.83, "hypocaudal_pct": 63.89}}

COMPARISON_MASS = {
    "value_kg": 0.1,
    "kind": "source",
    "locator": "Fish 1990 p.399: 'Compared to a 0.1 kg bird ..., Cypselurus and Exocoetus of equivalent mass'",
    "why": "one mass for all forms, inside both genera's measured wing-loading ranges, so differences between "
           "the forms come from proportions rather than size",
}

# Fin placement along the body, read by eye from Fish 1990 Fig. 4 (composite planform tracing, p.398) and
# Fig. 1 (Breder 1930 redrawn, p.393).  Precision about +/-0.05 SL.  Not a measurement.
FIGURE_READ = {
    "Cypselurus": {"pectoral_x_sl": 0.27, "pelvic_x_sl": 0.55, "kind": "figure_read",
                   "locator": "Fish 1990 Fig. 4 left and Fig. 1a"},
    "Exocoetus": {"pectoral_x_sl": 0.28, "pelvic_x_sl": 0.42, "kind": "figure_read",
                  "locator": "Fish 1990 Fig. 4 right"},
}

BODY_DENSITY = {
    "value_kg_m3": 1025.0,
    "kind": "design_assumption",
    "basis": "Fish 1990 p.399 states body density 'should be close to that of water for buoyancy stability'; "
             "1025 kg/m^3 is a typical seawater density chosen by us, not a measured exocoetid density",
}

# dx-nca's controlled glide comparison (file-only handoff messages/nca-to-print.md, 2026-10-31T19:21Z).  The three
# geometries are the Fish Cypselurus fit at 0.05 kg with wing area x fS and whole-wing AR x fAR.  The build reads
# the committed CSV from this commit and checks its sha256; a sink rate or range quoted in a design JSON is
# NCA's simulated output, not an observation.
NCA_CONTROLLED = {
    "repo": "kganjam/delphi-frontier", "branch": "work/nca-glide",
    "commit": "87e72f9fbc29bf97452af249fe1ba7bf48ae9dcc",
    "comparison_csv": "engineering/simulation/results_controlled/comparison.csv",
    "comparison_csv_sha256": "6c434c4a7b09e5897c3ad043f706d1a8b2e5f41b52b62d2650b4dcfd45f0343d",
    "protocol": "engineering/simulation/PROTOCOL_CONTROLLED.md",
    "protocol_sha256": "0099463326f19aa301130844a9c94d92d7bd8bf8f5ea7e2df1d9e6e385a4f6d0",
    "evidence_kind": "simulated",
    "model_version": "glide-pointmass/1",
    "caveats": ["polars are assumptions (P1 CD0 0.06 e 0.8 CL_max 1.2; P2 CD0 0.25 CL_max 1.03), not calibrated",
                "point mass: no pitch, stability or flapping; a printed model's Reynolds number differs",
                "0 robust winners of 144 variants; only equilibrium sink falling with S and AR is robust",
                "a comparison set for a geometry-effect test, not an optimum"],
}

FORMLABS = {
    "design_specs": {
        "url": "https://support.formlabs.com/s/article/Design-Specs",
        "read": "2026-10-31 via r.jina.ai (direct page is client-rendered)",
        "read_level": "full-text",
        "basis_stated_by_source": "Formlabs Clear Resin at 100 microns on the Form 2; other resins/printers vary",
        "min_supported_wall_mm": 0.4, "min_unsupported_wall_mm": 0.4, "min_drain_hole_mm": 3.5,
        "min_hole_mm": 0.8, "min_clearance_mm": 0.5,
        "wire_1p5mm_max_height_mm": 30,
    },
    "printability_guide": {
        "url": "https://formlabs.com/support/Design-Models-for-Printability/",
        "read": "2026-10-31 direct, HTTP 200", "read_level": "full-text",
        "smallest_listed_build_volume_mm": [125, 125, 165],
        "note": "build volumes listed only for Form 1+, 2, 3, 3B, 3L, 3BL, Fuse 1; no Form 4 / Form Studio "
                "figure on that page",
    },
    "preform_api": {
        "urls": ["https://developer.formlabs.com/core-concepts/validate/",
                 "https://developer.formlabs.com/examples/printability-report/"],
        "read": "2026-10-31 direct, HTTP 200", "read_level": "full-text",
        "checks": ["validate_manifoldness", "validate_thin_features(threshold_mm)", "validate_cups",
                   "validate_minima", "validate_supportedness", "validate_in_bounds", "validate_interferences"],
        "example_thin_threshold_mm": 0.5,
    },
}


def fit(genus: str, quantity: str, mass_kg: float) -> float:
    a, b = TABLE_I[genus][quantity]
    return a * mass_kg ** b


def table_cross_check(genus: str, mass_kg: float) -> dict:
    """Wing loading from the Table I area fit against the independent Table II fit at the same mass."""
    g = 9.80665
    wl_from_area = mass_kg * g / fit(genus, "area", mass_kg)
    a, b, _rng = TABLE_II[genus]
    wl_table_ii = a * mass_kg ** b
    return {"genus": genus, "mass_kg": mass_kg, "wl_table_I_area_N_m2": wl_from_area,
            "wl_table_II_N_m2": wl_table_ii, "relative_difference": abs(wl_from_area - wl_table_ii) / wl_table_ii}


@functools.lru_cache(maxsize=1)
def daane_summary() -> dict:
    """Fin/SL ratios recomputed from Daane et al. 2021 Data S1A by `engineering.geometry.daane_s1`."""
    if not DAANE_SUMMARY.exists():
        raise FileNotFoundError(f"{DAANE_SUMMARY} not found: engineering.geometry runs from a repository checkout "
                                "(the summary lives in artifacts/print/sources/), not from an installed wheel; "
                                "install with `pip install -e '.[geometry]'` and run from the repo root")
    return json.loads(DAANE_SUMMARY.read_text())
