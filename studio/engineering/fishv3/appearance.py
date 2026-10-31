"""Pigmentation as a separate appearance layer: per-vertex colours on the candidate's exact meshes.

Appearance never enters candidate.json, so a colour change never changes the geometry hash that CFD, the fin-ray
adapter and print use.  Each option records which pattern elements are sourced (FAO WCA, Cheilopogon furcatus
sheet and family page) and which are design choices.  All RGB values are design choices; no pattern here comes
from a validated pigment-pattern model.
"""
from __future__ import annotations

import math

import numpy as np

FAO = "fao_wca_exocoetidae"
OPTIONS = {
    "adult-fao": {
        "title": "Adult C. furcatus pattern as described by FAO WCA (colours are ours)",
        "elements": [
            {"element": "body dark above, pale below; dark colours usually iridescent blue or green in life",
             "status": "sourced (family and C. furcatus sheet)", "source": FAO},
            {"element": "dorsal and caudal fins greyish; anal fin transparent", "status": "sourced (C. furcatus)",
             "source": FAO},
            {"element": "pectoral fins almost black to grey (deep blue in life) with an unpigmented oblique crossband "
                        "reaching or nearly reaching the upper margin, and a very broad unpigmented rear margin",
             "status": "sourced (C. furcatus); band position and width on the fin are ours", "source": FAO},
            {"element": "pelvic fins pale", "status": "assumed (adult pelvic colour not stated for C. furcatus)"},
            {"element": "countershading boundary height, all RGB values, scale-edge tint", "status": "design choice"},
        ],
        "bars": 0},
    "juvenile-bars-design": {
        "title": "Adult pattern plus 6 transverse body bars (DESIGN CHOICE on an adult-size body)",
        "elements": [
            {"element": "everything in adult-fao", "status": "as adult-fao"},
            {"element": "6 transverse vertical bars on the body", "status": "sourced for JUVENILES of 50-100 mm SL only "
             "(C. furcatus); this candidate is 159 mm SL, so applying them is a design choice", "source": FAO},
            {"element": "bar positions and widths", "status": "design choice"},
        ],
        "bars": 6},
}
DEFAULT = "adult-fao"
DARK, PALE = np.array([0.05, 0.13, 0.32]), np.array([0.84, 0.86, 0.89])
FIN_DARK, FIN_PALE = np.array([0.10, 0.12, 0.20]), np.array([0.86, 0.88, 0.92])
GREY, CLEAR = np.array([0.46, 0.48, 0.52]), np.array([0.90, 0.91, 0.93])
EYE, OPERC = np.array([0.03, 0.03, 0.04]), np.array([0.62, 0.68, 0.76])


def _body(V, body, bars, head_end_s, tail_s=0.95):
    s = V[:, 0] / body.sl
    hz = np.maximum(body.W * body.hw * body.f(np.clip(s, 0, 1)), 1e-6)
    t = np.clip((V[:, 2] / hz + 0.15) / 0.5, 0, 1)  # dark above roughly z > 0.1 h, design boundary
    t = t * t * (3 - 2 * t)
    c = PALE[None] * (1 - t[:, None]) + DARK[None] * t[:, None]
    if bars:
        centres = np.linspace(head_end_s + 0.06, tail_s - 0.04, bars)
        half = 0.022
        on = np.zeros(len(V), bool)
        for cs in centres:
            on |= np.abs(s - cs) < half
        c[on] = c[on] * 0.35 + DARK * 0.65 * 0.6
    return c


def _fin_coords(V, fan, frame, side):
    origin, e_u, e_w, e_n = frame
    P = V * np.array([1.0, side, 1.0])
    R = np.column_stack([e_u, e_w, e_n])
    L = (P - origin) @ R  # (u, w, n)
    o = fan.roots.mean(axis=0)
    a0, a1 = math.radians(fan.alpha_deg[0]), math.radians(fan.alpha_deg[-1])
    xi = np.clip((np.arctan2(L[:, 1] - o[1], L[:, 0] - o[0]) - a0) / (a1 - a0), 0, 1)
    r = np.hypot(L[:, 0] - o[0], L[:, 1] - o[1])
    Lx = np.interp(xi, np.linspace(0, 1, len(fan.lengths)), fan.lengths)
    return xi, r / np.maximum(Lx, 1e-9)


def vertex_colors(cid: str, V: np.ndarray, fans: dict, body, option: str, head_end_s: float) -> np.ndarray:
    opt = OPTIONS[option]
    if cid in ("body", "scales"):
        c = _body(V, body, opt["bars"], head_end_s)
        if cid == "scales":
            c = np.clip(c * 1.12 + 0.03, 0, 1)
    elif cid.startswith("eye"):
        c = np.tile(EYE, (len(V), 1))
    elif cid.startswith("operculum"):
        c = np.tile(OPERC, (len(V), 1))
    elif cid.startswith("pectoral"):
        xi, rf = _fin_coords(V, *fans[cid])
        band = np.abs(rf - (0.50 + 0.18 * (0.5 - xi))) < 0.07  # oblique, reaches the leading (upper) margin
        rear = xi > 0.72                                         # very broad unpigmented rear margin
        c = np.where((band | rear)[:, None], FIN_PALE[None], FIN_DARK[None])
    elif cid in ("dorsal", "caudal"):
        c = np.tile(GREY, (len(V), 1))
    else:  # anal (transparent), pelvic (assumed pale)
        c = np.tile(CLEAR, (len(V), 1))
    rgba = np.concatenate([np.clip(c, 0, 1), np.ones((len(V), 1))], axis=1)
    return (rgba * 255).round().astype(np.uint8)


def record(option: str, csha: str) -> dict:
    return {"schema": "frontier.fish3d.appearance/1", "candidate_sha256": csha, "option": option,
            **OPTIONS[option], "rgb_design_values": {"dark": DARK.tolist(), "pale": PALE.tolist(),
                                                     "fin_dark": FIN_DARK.tolist(), "fin_pale": FIN_PALE.tolist(),
                                                     "grey": GREY.tolist(), "clear": CLEAR.tolist()},
            "label": "Appearance only. Not a validated pigment-pattern map; geometry is identical across options."}
