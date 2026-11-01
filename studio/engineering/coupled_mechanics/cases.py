"""Analytic member-pressure records and the declared member target used by the checks and the run.

Analytic pressure exercises the adapter only. It is not a flow result, and nothing here is a
measured coefficient: rho, V, CL, tributary width and ray length come from the existing
fin_mechanics DECLARED ILLUSTRATION request, and the EI interval is Alben, Madden & Lauder 2007
Section 3.4's bluegill order-of-magnitude composite figure, used as context only.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from engineering.fin_mechanics import load_bridge, sweep

from . import SCHEMA_PRESSURE, SCHEMA_TARGET

FIN_REQUEST = Path(load_bridge.__file__).resolve().parent / "example_request.json"
FRAME = "coupled-mechanics/declared-ray-frame/1"
MEMBER = "declared-pectoral-ray-1"


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def illustration_bridge() -> dict:
    """The existing exact load bridge over the existing declared request (the one-way baseline)."""
    return load_bridge.bridge(json.loads(FIN_REQUEST.read_text()))


def target(n_elements: int = 64, claim: str = "member_scenario", section=None) -> dict:
    b = illustration_bridge()
    L = Fraction(b["exact"]["L_ray_m"])
    lo, hi = sweep.CONTEXT_EI_BLUEGILL_NM2
    t = {"schema": SCHEMA_TARGET, "member_id": MEMBER, "frame_id": FRAME, "frame_length_unit": "m",
         "root_m": ["0", "0", "0"], "tip_m": [str(L), "0", "0"],
         "EI": {"lo_Nm2": repr(lo), "hi_Nm2": repr(hi), "status": "context_only",
                "source": "Alben, Madden & Lauder 2007 J R Soc Interface 4:243, Sec. 3.4: composite E x mean I, "
                          "bluegill sunfish, order of magnitude; not a flying-fish or per-ray measurement"},
         "claim": claim, "n_elements": n_elements}
    if section is not None:
        t["section"] = section
    return t


def analytic_record(profile: str = "uniform", n_stations: int = 9) -> dict:
    """Pressure jump p(s) on the declared ray, from the bridge's mean lift-pressure proxy p_bar.

    uniform:      p(s) = p_bar
    root_heavy:   p(s) = 2 p_bar (1 - s/L)  (same total force as uniform, centroid at L/3)
    tip_heavy:    p(s) = 2 p_bar s/L        (same total force, centroid at 2L/3)
    """
    b = illustration_bridge()
    p_bar = Fraction(b["exact"]["p_Pa"])
    w = Fraction(b["exact"]["w_t_m"])
    L = Fraction(b["exact"]["L_ray_m"])
    shape = {"uniform": lambda u: p_bar, "root_heavy": lambda u: 2 * p_bar * (1 - u),
             "tip_heavy": lambda u: 2 * p_bar * u}[profile]
    stations = []
    for i in range(n_stations):
        u = Fraction(i, n_stations - 1)
        stations.append({"s_m": str(u * L), "p_pos_Pa": "0", "p_neg_Pa": str(shape(u))})
    rec = {"schema": SCHEMA_PRESSURE,
           "source": {"producer": f"analytic:{profile} from fin_mechanics declared illustration",
                      "evidence_kind": "analytic", "receipt_sha256": None,
                      "fields_sha256": None, "geometry_sha256": None},
           "dimensionality": "analytic",
           "frame": {"id": FRAME, "length_unit": "m"},
           "member": {"id": MEMBER, "root_m": ["0", "0", "0"], "tip_m": [str(L), "0", "0"],
                      "normal": ["0", "0", "1"]},
           "pressure": {"unit": "Pa", "kind": "dimensional",
                        "reference": "jump p_neg - p_pos; analytic, from 0.5 rho V^2 CL (declared)"},
           "stations": stations,
           "tributary": {"width_m": str(w), "status": "declared",
                         "source": "fin_mechanics example_request.json fin.tributary_width_m (declared)"},
           "time": {"kind": "static", "window_s": None},
           "resolution": {"cells_across_member_thickness": None, "cells_along_member": None}}
    rec["source"]["receipt_sha256"] = _sha({k: v for k, v in rec.items() if k != "source"})
    return rec
