"""Analytic reference load on the leading-edge ray: thin-airfoil theory per chordwise section.

Classical results, recalled and not re-read here; each is checked numerically in the tests:
  flat plate, small alpha, inviscid, attached:  dCp(xi) = 4 alpha sqrt((1 - xi)/xi),  xi = x/c
  section lift coefficient                       Cl = int_0^1 dCp dxi = 2 pi alpha
  leading-edge strip [0, xi1]                    int_0^xi1 dCp dxi = 4 alpha G(xi1),
                                                 G(xi) = sqrt(xi (1 - xi)) + asin(sqrt(xi)),  G(1) = pi/2
  finite-span correction (Prandtl lifting line, elliptic loading)  alpha_eff = alpha / (1 + 2/AR)

The fan fin is not elliptic and its aspect ratio is low, so alpha_eff is an ASSUMED correction and
the uncorrected 2D value is reported beside it as the upper bracket. The leading-edge suction peak is
an integrable singularity: the strip load is finite even though dCp at xi = 0 is not.

Per unit length of ray 0 (swept by lambda, at the leading edge), with the section at span u(s):
    q_true(s) = q_dyn * c(s) * 4 alpha_eff * G(xi1(s)) * cos(lambda)       [N/m]
because a strip of chordwise width w_c over du = cos(lambda) ds carries dA = w_c cos(lambda) ds.
"""
from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from . import SCHEMA_PRESSURE, SCHEMA_PRESSURE_V2
from . import fin_geometry as fg


def G(xi: float) -> float:
    if not 0.0 <= xi <= 1.0:
        raise ValueError(f"xi={xi} outside [0, 1]")
    return math.sqrt(xi * (1.0 - xi)) + math.asin(math.sqrt(xi))


def dcp(xi, alpha):
    xi = np.asarray(xi, dtype=float)
    return 4.0 * alpha * np.sqrt((1.0 - xi) / xi)


def aspect_ratio(g: dict) -> dict:
    fp = fg.fin_plane(g)
    us = [fg.to_plane(fp, p)[0] for p in g["panels"]["outline_m"]]
    b = max(us) - min(us)
    S = g["panels"]["area_flat_m2"]
    return {"span_m": b, "area_m2": S, "AR": b * b / S,
            "note": "span = extent of the outline along e_u; S = panels.json area_flat_m2 (derived)"}


DEFAULT_FLOW = {  # every entry is a declared assumption, none measured
    "rho_kg_m3": {"value": 1.225, "status": "assumed", "source": "fin_mechanics example_request rho (design_assumption)"},
    "U_m_s": {"value": 5.0, "status": "assumed", "source": "fin_mechanics example_request witness V (declared illustration); unsourced"},
    "alpha_deg": {"value": 5.0, "status": "assumed",
                  "source": "declared; v3a pose has the fin plane containing the stream, so its own alpha is 0"},
}
S_OVER_L = (0.0, 0.25, 0.5, 0.75, 1.0)


def reference(g: dict | None = None, flow: dict | None = None, s_over_L=S_OVER_L, lifting_line: bool = True) -> dict:
    g = g or fg.load()
    flow = flow or DEFAULT_FLOW
    rho, U = flow["rho_kg_m3"]["value"], flow["U_m_s"]["value"]
    alpha = math.radians(flow["alpha_deg"]["value"])
    ar = aspect_ratio(g)
    a_eff = alpha / (1.0 + 2.0 / ar["AR"]) if lifting_line else alpha
    q_dyn = 0.5 * rho * U * U
    r0 = fg.ray0(g)
    lam = r0["sweep_rad"]
    rows = []
    for f in s_over_L:
        sec = fg.section(g, f)
        Gs = G(sec["xi_strip"])
        strip_per_span = q_dyn * sec["chord_m"] * 4 * a_eff * Gs        # N per m of span u
        w_c = sec["strip_chordwise_m"]                                  # LE to strip boundary, chordwise
        rows.append({**sec, "G": Gs, "strip_fraction_of_section_lift": Gs / (math.pi / 2),
                     "q_true_N_per_m": strip_per_span * math.cos(lam),
                     "dp_strip_mean_Pa": strip_per_span / w_c})
    return {"alpha_rad": alpha, "alpha_eff_rad": a_eff, "lifting_line": lifting_line, "aspect": ar,
            "q_dyn_Pa": q_dyn, "sweep_rad": lam, "flow": flow, "stations": rows,
            "L_exact": r0["L_exact"], "tributary_width_declared_m": r0["tributary_width_m"]}


def record(ref: dict, g: dict | None = None, version: int = 2) -> dict:
    """The analytic reference as a member-pressure record.

    Each station's jump is the strip-mean dCp*q_dyn over ray 0's local tributary strip.
    version 2 (current): each station carries its own width, the strip's dA/ds from the pinned
      geometry (fin_geometry.tributary_v2), so q = jump * width reproduces q_true at every station.
    version 1 (SUPERSEDED, kept to reproduce the retained v1 artifacts): one width per member,
      rays.json tributary_width_m (a fan mean). On a fan that is knowingly wrong: it moves force
      toward the root (F +15.5%, root moment -8.6% against the strip; fin_patch.fan_width_gap)."""
    g = g or fg.load()
    m = fg.member_json(g)
    L = ref["L_exact"]
    s_m = [str(Fraction(st["s_over_L"]).limit_denominator(1000) * L) for st in ref["stations"]]
    stations = [{"s_m": s, "p_pos_Pa": "0", "p_neg_Pa": repr(float(st["dp_strip_mean_Pa"]))}
                for s, st in zip(s_m, ref["stations"])]
    if version == 2:
        trib = fg.tributary_v2(g, [(s, st["s_over_L"]) for s, st in zip(s_m, ref["stations"])])
    elif version == 1:
        trib = {"width_m": repr(ref["tributary_width_declared_m"]), "status": "from_geometry",
                "source": f"rays.json ray 0 tributary_width_m (sha256 {g['sha256']['rays.json'][:16]}); "
                          "a mean over a fan whose local width varies"}
    else:
        raise ValueError(f"version {version}")
    rec = {"schema": SCHEMA_PRESSURE_V2 if version == 2 else SCHEMA_PRESSURE,
           "source": {"producer": "analytic: thin-airfoil strip on the v3a pectoral_L leading-edge ray",
                      "evidence_kind": "analytic", "receipt_sha256": None, "fields_sha256": None,
                      "geometry_sha256": None, "candidate_sha256": m["candidate_sha256"],
                      "member_sha256": m["member_sha256"], "frame_sha256": m["frame_sha256"],
                      "geometry_files_sha256": g["sha256"],
                      "units": "Pa jump, m frame; q_dyn = 0.5 rho U^2 from declared rho, U"},
           "dimensionality": "analytic",
           "frame": {"id": m["frame_id"], "length_unit": "m"},
           "member": {"id": m["member_id"], "root_m": m["root_m"], "tip_m": m["tip_m"], "normal": ["0", "0", "1"]},
           "pressure": {"unit": "Pa", "kind": "dimensional",
                        "reference": "jump p_ventral - p_dorsal, thin-airfoil strip mean over ray 0's local "
                                     "tributary strip; inviscid, attached, flat plate"},
           "stations": stations,
           "tributary": trib,
           "time": {"kind": "static", "window_s": None},
           "resolution": {"cells_across_member_thickness": None, "cells_along_member": None}}
    if version == 1:
        rec["superseded"] = "constant-width fan loading; current method is member-pressure/2 (per-station widths)"
    rec["source"]["pressure_sha256"] = fg.canonical_sha(rec["stations"])
    rec["source"]["receipt_sha256"] = fg.canonical_sha({k: v for k, v in rec.items() if k != "source"})
    return rec
