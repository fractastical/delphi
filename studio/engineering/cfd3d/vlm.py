"""Thin-surface vortex-lattice method (VLM) for the fish3d-v3 paired fins, with analytic controls.

    python engineering/cfd3d/vlm.py controls OUT.json
    python engineering/cfd3d/vlm.py fish PANELS.json COMPONENTS.json OUTDIR

Why VLM: the v3 fin membrane is 0.10 mm and its rays 0.60 mm, below any 3-D grid here (0.06-0.11 cells at
L 128-256), so a Navier-Stokes grid cannot resolve them. VLM treats each fin as a zero-thickness lifting surface:
that is the approximation, stated, not a resolution of the membrane. Inviscid, attached flow, small angle of
attack; Reynolds-number independent. Gates: gates_vlm.json (frozen before this file existed).

Method (Katz & Plotkin, Low-Speed Aerodynamics, ch. 12; recalled): one horseshoe vortex per panel, bound segment
on the panel's 1/4-chord line, collocation at 3/4 chord, trailing legs along +x to a far plane, camber through
the boundary-condition normal, Kutta-Joukowski force per bound segment. Units: rho = 1, |V| = 1; dCp is
dimensionless and becomes Pa only through an explicitly chosen medium and speed.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

FAR = 1e3          # trailing-leg length, in multiples of the largest lattice dimension
EPS = 1e-10


def seg_vel(P: np.ndarray, A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Velocity at points P (N,3) induced by unit vortex segments A->B (M,3): returns (N,M,3)."""
    r1 = P[:, None, :] - A[None, :, :]
    r2 = P[:, None, :] - B[None, :, :]
    r0 = (B - A)[None, :, :]
    c = np.cross(r1, r2)
    c2 = np.einsum("nmk,nmk->nm", c, c)
    n1, n2 = np.linalg.norm(r1, axis=2), np.linalg.norm(r2, axis=2)
    k = np.einsum("nmk,nmk->nm", r0, r1 / np.maximum(n1, EPS)[..., None] - r2 / np.maximum(n2, EPS)[..., None])
    scale = np.where(c2 > EPS * EPS, k / (4 * math.pi * np.maximum(c2, EPS * EPS)), 0.0)
    return c * scale[..., None]


def chord_at(poly_uw: np.ndarray, u: float) -> tuple[float, float] | None:
    """(w_min, w_max) where the line u = const crosses the closed polygon, or None."""
    ws = []
    p, q = poly_uw, np.roll(poly_uw, -1, axis=0)
    for (u1, w1), (u2, w2) in zip(p, q):
        if (u1 - u) * (u2 - u) <= 0 and u1 != u2:
            ws.append(w1 + (u - u1) / (u2 - u1) * (w2 - w1))
    return (min(ws), max(ws)) if len(ws) >= 2 else None


def lattice(poly_uw, origin, e_u, e_w, n_up, ns=20, nc=6, normal_fn=None, colloc=0.75):
    """Panels on a planar planform (u spanwise, w chordwise = flow direction), cosine-spaced in span."""
    u_lo, u_hi = poly_uw[:, 0].min(), poly_uw[:, 0].max()
    t = 0.5 * (1 - np.cos(np.linspace(0, math.pi, ns + 1)))
    ue = u_lo + (u_hi - u_lo) * np.clip(t, 1e-6, 1 - 1e-6)
    to3 = lambda u, w: origin + u * e_u + w * e_w  # noqa: E731
    A, B, C, N, area, strip, uw = [], [], [], [], [], [], []
    for i in range(ns):
        c0, c1, cm = chord_at(poly_uw, ue[i]), chord_at(poly_uw, ue[i + 1]), chord_at(poly_uw, 0.5 * (ue[i] + ue[i + 1]))
        if c0 is None or c1 is None or cm is None:
            continue
        for j in range(nc):
            f0, f1 = j / nc, (j + 1) / nc
            w = lambda c, f: c[0] + f * (c[1] - c[0])  # noqa: E731
            fq = f0 + 0.25 * (f1 - f0)
            A.append(to3(ue[i], w(c0, fq)))
            B.append(to3(ue[i + 1], w(c1, fq)))
            um = 0.5 * (ue[i] + ue[i + 1])
            wc = w(cm, f0 + colloc * (f1 - f0))
            C.append(to3(um, wc))
            N.append(normal_fn(um, wc, (f0 + colloc * (f1 - f0))) if normal_fn else n_up)
            # trapezoid area in the plane: chord segment at both edges times span width
            area.append(0.5 * ((w(c0, f1) - w(c0, f0)) + (w(c1, f1) - w(c1, f0))) * (ue[i + 1] - ue[i]))
            strip.append((i, j))
            uw.append([(ue[i], w(c0, f0)), (ue[i + 1], w(c1, f0)), (ue[i + 1], w(c1, f1)), (ue[i], w(c0, f1))])
    return {"A": np.array(A), "B": np.array(B), "C": np.array(C), "N": np.array(N), "area": np.array(area),
            "strip": strip, "ue": ue, "uw": np.array(uw)}


def solve(lat, alpha_deg: float, beta_deg: float = 0.0):
    """Unit free stream, rho = 1. Returns gamma, panel forces (KJ), dCp along each panel's normal."""
    a, b = math.radians(alpha_deg), math.radians(beta_deg)
    V = np.array([math.cos(a) * math.cos(b), -math.sin(b), math.sin(a) * math.cos(b)])
    A, B, C, N = lat["A"], lat["B"], lat["C"], lat["N"]
    span = max(np.ptp(np.vstack([A, B]), axis=0).max(), 1e-9)
    xhat = np.array([1.0, 0.0, 0.0])
    Af, Bf = A + FAR * span * xhat, B + FAR * span * xhat
    M = np.empty((len(C), len(A)))
    for i in range(0, len(C), 256):                                       # chunked: memory O(256 x M)
        sl = slice(i, i + 256)
        v = seg_vel(C[sl], Af, A) + seg_vel(C[sl], A, B) + seg_vel(C[sl], B, Bf)
        M[sl] = np.einsum("nmk,nk->nm", v, N[sl])
    g = np.linalg.solve(M, -N @ V)
    F = g[:, None] * np.cross(V, B - A)                                   # Kutta-Joukowski, rho = 1
    q = 0.5
    dcp = np.einsum("nk,nk->n", F, N) / (q * lat["area"])
    return g, F, dcp, V


def combine(lats: dict) -> dict:
    keys = ["A", "B", "C", "N", "area"]
    out = {k: np.vstack([lats[f][k] for f in lats]) if k != "area" else np.concatenate([lats[f][k] for f in lats])
           for k in keys}
    out["owner"] = [f for f in lats for _ in range(len(lats[f]["area"]))]
    return out


# ---------------------------------------------------------------- analytic controls
def elliptic(ar: float, ns=40, nc=12, colloc=0.75):
    b, c0 = 1.0, 4.0 / (math.pi * ar)          # S = pi b c0 / 4 = b^2 / AR
    y = np.linspace(-b / 2, b / 2, 401)
    c = c0 * np.sqrt(np.clip(1 - (2 * y / b) ** 2, 0, 1))
    poly = np.vstack([np.c_[y, -c / 4], np.c_[y[::-1], 3 * c[::-1] / 4]])   # straight 1/4-chord line
    return lattice(poly, np.zeros(3), np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), ns, nc,
                   colloc=colloc), b * b / ar


def cl_of(lat, S, alpha):
    _, F, _, V = solve(lat, alpha)
    a = math.radians(alpha)
    lift_dir = np.array([-math.sin(a), 0, math.cos(a)])
    return float(F.sum(axis=0) @ lift_dir / (0.5 * S)), F


def controls() -> dict:
    g = json.loads((Path(__file__).parent / "gates_vlm.json").read_text())["controls"]
    r = {}
    helm = lambda A: 2 * math.pi * A / (2 + math.sqrt(A * A + 4))  # noqa: E731
    ll = lambda A: 2 * math.pi * A / (A + 2)  # noqa: E731
    lat6, S6 = elliptic(6)
    cla6 = cl_of(lat6, S6, 4)[0] / math.radians(4)
    r["V1_elliptic_AR6"] = {"CL_alpha": cla6, "reference": helm(6), "rel_err": abs(cla6 / helm(6) - 1)}
    r["V1_elliptic_AR6"]["pass"] = r["V1_elliptic_AR6"]["rel_err"] <= g["V1_elliptic_AR6"]["pass"]["rel_err_max"]
    lat20, S20 = elliptic(20)
    cla20 = cl_of(lat20, S20, 4)[0] / math.radians(4)
    r["V2_elliptic_AR20"] = {"CL_alpha": cla20, "reference": ll(20), "rel_err": abs(cla20 / ll(20) - 1)}
    r["V2_elliptic_AR20"]["pass"] = r["V2_elliptic_AR20"]["rel_err"] <= g["V2_elliptic_AR20"]["pass"]["rel_err_max"]
    latf, Sf = elliptic(6, ns=80, nc=24)
    claf = cl_of(latf, Sf, 4)[0] / math.radians(4)
    r["V3_refinement"] = {"CL_alpha_fine": claf, "rel_change": abs(claf / cla6 - 1)}
    r["V3_refinement"]["pass"] = r["V3_refinement"]["rel_change"] <= g["V3_refinement"]["pass"]["rel_change_max"]
    m, AR = 0.04, 20.0
    poly = np.array([[-AR / 2, 0.0], [AR / 2, 0.0], [AR / 2, 1.0], [-AR / 2, 1.0]])
    nfn = lambda u, w, f: (lambda s: np.array([-s, 0, 1.0]) / math.hypot(s, 1))(4 * m * (1 - 2 * w))  # noqa: E731
    latc = lattice(poly, np.zeros(3), np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), 40, 12,
                   normal_fn=nfn)
    latr = lattice(poly, np.zeros(3), np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), 40, 12)
    cla_r = cl_of(latr, AR, 4)[0] / math.radians(4)
    cl0 = cl_of(latc, AR, 0)[0]
    r["V4_camber"] = {"CL0": cl0, "reference": cla_r * 2 * m, "rel_err": abs(cl0 / (cla_r * 2 * m) - 1)}
    r["V4_camber"]["pass"] = r["V4_camber"]["rel_err"] <= g["V4_camber"]["pass"]["rel_err_max"]
    latm, Sm = elliptic(6, colloc=0.25)
    clam = cl_of(latm, Sm, 4)[0] / math.radians(4)
    r["V5_mutant_collocation_quarter_chord"] = {"CL_alpha": clam, "rel_err": abs(clam / helm(6) - 1)}
    r["V5_mutant_collocation_quarter_chord"]["pass"] = r["V5_mutant_collocation_quarter_chord"]["rel_err"] > \
        g["V1_elliptic_AR6"]["pass"]["rel_err_max"]
    # V6: two half-elliptic wings with +-20 deg dihedral, the right one the mirror of the left; at zero
    # sideslip the summed side force must vanish (a planar wing gives zero side force trivially, so dihedral)
    d = math.radians(20)
    half = lambda sgn: lattice(  # noqa: E731
        np.vstack([np.c_[np.linspace(0, .5, 201), -np.sqrt(np.clip(1 - (np.linspace(0, .5, 201) / .5) ** 2, 0, 1)) * .053],
                   np.c_[np.linspace(.5, 0, 201), 3 * np.sqrt(np.clip(1 - (np.linspace(.5, 0, 201) / .5) ** 2, 0, 1)) * .053]]),
        np.zeros(3), np.array([0, sgn * math.cos(d), math.sin(d)]), np.array([1.0, 0, 0]),
        np.array([0, -sgn * math.sin(d), math.cos(d)]), 20, 12)
    pair = combine({"L": half(1), "R": half(-1)})
    _, Fp, _, _ = solve(pair, 4)
    a4 = math.radians(4)
    lift = float(Fp.sum(axis=0) @ np.array([-math.sin(a4), 0, math.cos(a4)]))
    r["V6_symmetry"] = {"side_force_over_lift": float(abs(Fp.sum(axis=0)[1]) / abs(lift)), "lift_rho1_V1": lift}
    r["V6_symmetry"]["pass"] = r["V6_symmetry"]["side_force_over_lift"] <= g["V6_symmetry"]["pass"]["abs_side_force_over_lift_max"]
    r["all_pass"] = all(v["pass"] for v in r.values() if isinstance(v, dict))
    return r


# ---------------------------------------------------------------- fish
PAIRED = ("pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R")
MEDIA = {"air_20C": {"rho": 1.204, "nu": 1.516e-5}, "water_20C": {"rho": 998.2, "nu": 1.004e-6}}   # recalled
SPEEDS = {"air_20C": {"values_m_s": [10.0, 16.0, 20.0],
                      "status": "16-20 m/s take-off speed relayed by claude-05 from Fish 1990 (not read here); 10 assumed"},
          "water_20C": {"values_m_s": [5.0, 10.0], "status": "assumed, unsourced"}}


def quad_normal(q: np.ndarray) -> np.ndarray:
    n = np.cross(q[2] - q[0], q[3] - q[1])
    return n / np.linalg.norm(n)


def fin_setup(fin: dict, ns: int, nc: int):
    pl = fin["fin_plane"]
    O, eu, ew = (np.array(pl[k], float) for k in ("origin_m", "e_u", "e_w"))
    n_up = np.cross(ew, eu)
    n_up = n_up if n_up[2] >= 0 else -n_up
    out = np.array(fin["outline_m"], float)
    poly = np.c_[(out - O) @ eu, (out - O) @ ew]
    quads = np.array(fin["quads_m"], float)
    qc = quads.mean(axis=1)
    qn = np.array([quad_normal(q) for q in quads])
    qn = qn * np.sign(qn @ n_up)[:, None]
    quv = np.c_[(qc - O) @ eu, (qc - O) @ ew]
    quads_uw = np.stack([np.c_[(q - O) @ eu, (q - O) @ ew] for q in quads])

    def nfn(u, w, f):
        """Normal of the source mid-surface itself at (u, w): invert the containing quad's bilinear map."""
        k = int(in_quads(np.array([[u, w]]), quads_uw)[0])
        k = k if k >= 0 else int(np.argmin(((quv - [u, w]) ** 2).sum(axis=1)))
        c, X = quads_uw[k], quads[k]
        st = np.array([0.5, 0.5])
        for _ in range(20):
            s_, t_ = st
            P = (1 - s_) * (1 - t_) * c[0] + s_ * (1 - t_) * c[1] + s_ * t_ * c[2] + (1 - s_) * t_ * c[3]
            J = np.c_[(1 - t_) * (c[1] - c[0]) + t_ * (c[2] - c[3]), (1 - s_) * (c[3] - c[0]) + s_ * (c[2] - c[1])]
            st = st - np.linalg.solve(J, P - [u, w])
        s_, t_ = np.clip(st, 0, 1)
        Xs = (1 - t_) * (X[1] - X[0]) + t_ * (X[2] - X[3])
        Xt = (1 - s_) * (X[3] - X[0]) + s_ * (X[2] - X[1])
        n = np.cross(Xs, Xt)
        n /= np.linalg.norm(n)
        return n if n @ n_up >= 0 else -n
    lat = lattice(poly, O, eu, ew, n_up, ns, nc, normal_fn=nfn)
    return lat, {"O": O, "eu": eu, "ew": ew, "n_up": n_up, "poly": poly, "quads": quads, "qc": qc, "qn": qn,
                 "quv": quv, "qarea": np.array([0.5 * np.linalg.norm(np.cross(q[2] - q[0], q[3] - q[1])) for q in quads])}


def in_quads(pts: np.ndarray, quads_uw: np.ndarray) -> np.ndarray:
    """Index of the first quad (Q,4,2) containing each point (P,2) by crossing number, -1 if none."""
    x, y = pts[:, None, 0], pts[:, None, 1]
    inside = np.zeros((len(pts), len(quads_uw)), bool)
    for k in range(4):
        a, b = quads_uw[None, :, k], quads_uw[None, :, (k + 1) % 4]
        cross = (a[..., 1] > y) != (b[..., 1] > y)
        xi = a[..., 0] + (y - a[..., 1]) * (b[..., 0] - a[..., 0]) / np.where(b[..., 1] == a[..., 1], 1e-30,
                                                                             b[..., 1] - a[..., 1])
        inside ^= cross & (x < xi)
    return np.where(inside.any(axis=1), inside.argmax(axis=1), -1)


def transfer(lat, geo, F_fin: np.ndarray, m: int = 8):
    """Conservative panel->quad transfer: each VLM panel's force is split over the quads by overlap area.

    Overlap is sampled with m x m bilinear points per panel (Jacobian-weighted); a sample inside no quad goes to
    the nearest quad centroid and is counted in `uncovered_area_frac`. Sum over quads == sum over panels exactly.
    """
    quads_uw = np.stack([np.c_[(q - geo["O"]) @ geo["eu"], (q - geo["O"]) @ geo["ew"]] for q in geo["quads"]])
    s = (np.arange(m) + 0.5) / m
    S, T = np.meshgrid(s, s, indexing="ij")
    S, T = S.ravel(), T.ravel()
    W = np.zeros((len(F_fin), len(geo["quads"])))
    unc = 0.0
    for k, c in enumerate(lat["uw"]):
        pts = ((1 - S) * (1 - T))[:, None] * c[0] + (S * (1 - T))[:, None] * c[1] + (S * T)[:, None] * c[2] + \
              ((1 - S) * T)[:, None] * c[3]
        du = (1 - T)[:, None] * (c[1] - c[0]) + T[:, None] * (c[2] - c[3])
        dv = (1 - S)[:, None] * (c[3] - c[0]) + S[:, None] * (c[2] - c[1])
        jac = np.abs(du[:, 0] * dv[:, 1] - du[:, 1] * dv[:, 0])
        wts = jac / jac.sum()
        qi = in_quads(pts, quads_uw)
        miss = qi < 0
        if miss.any():
            qi[miss] = np.argmin(((pts[miss, None, :] - geo["quv"][None]) ** 2).sum(axis=2), axis=1)
            unc += float(wts[miss].sum() * lat["area"][k])
        np.add.at(W[k], qi, wts)
    Fq = W.T @ F_fin
    return Fq, unc / float(lat["area"].sum())


def fish(panels_path: Path, comps_path: Path, outdir: Path, source: str = "", ns=48, nc=16) -> dict:
    panels, comps = json.loads(panels_path.read_text()), json.loads(comps_path.read_text())
    if panels["candidate_sha256"] != comps["candidate_sha256"]:
        raise SystemExit("REFUSED: panels.json and components.json name different candidates")
    cand = panels["candidate_sha256"]
    bb = comps["components"]["body"]["check"]["bbox_mm"]
    L_body = (bb[1][0] - bb[0][0]) / 1000.0          # body x-extent, metres (snout to caudal peduncle region)
    lats, geos = {}, {}
    for f in PAIRED:
        lats[f], geos[f] = fin_setup(panels["fins"][f], ns, nc)
    allp = combine(lats)
    S = float(sum(lats[f]["area"].sum() for f in PAIRED))
    res = {"schema": "cfd3d-vlm-fish-0.1", "candidate_sha256": cand, "candidate_id": comps.get("candidate_id"),
           "panels_sha256": hashlib.sha256(panels_path.read_bytes()).hexdigest(),
           "components_sha256": hashlib.sha256(comps_path.read_bytes()).hexdigest(), "source": source,
           "method": "horseshoe VLM, rho=1 |V|=1; gates_vlm.json; isolated paired fins, no body, no median fins",
           "lattice": {"spanwise": ns, "chordwise": nc, "panels": int(len(allp["area"])), "S_lattice_m2": S,
                       "S_fin_flat_m2": {f: panels["fins"][f]["area_flat_m2"] for f in PAIRED}},
           "membrane": {f: _thk(comps, f) for f in PAIRED},
           "resolution_note": ("membrane and rays are not resolved by any grid here; VLM models each fin as a "
                               "zero-thickness surface (the approximation), so no thickness or ray stiffness enters"),
           "regimes": _regimes(L_body), "speeds": SPEEDS, "media": MEDIA, "cases": {}}
    for alpha in json.loads((Path(__file__).parent / "gates_vlm.json").read_text())["fish_rules"]["angle_of_attack_deg"]:
        g, F, dcp, V = solve(allp, alpha)
        a = math.radians(alpha)
        lift_dir = np.array([-math.sin(a), 0, math.cos(a)])
        case = {"alpha_deg": alpha, "CL_paired_fins_on_S_lattice": float(F.sum(axis=0) @ lift_dir / (0.5 * S)),
                "side_force_over_lift": float(abs(F.sum(axis=0)[1]) / max(abs(F.sum(axis=0) @ lift_dir), 1e-30)),
                "fins": {}}
        o = np.array(allp["owner"])
        for f in PAIRED:
            m = o == f
            Fq, unc = transfer(lats[f], geos[f], F[m])
            qd = np.einsum("qk,qk->q", Fq, geos[f]["qn"]) / (0.5 * geos[f]["qarea"])     # dCp along quad upper normal
            Fn = (qd * 0.5 * geos[f]["qarea"])[:, None] * geos[f]["qn"]                     # what an adapter applies
            Fv = F[m].sum(axis=0)
            gross = float(np.linalg.norm(F[m], axis=1).sum())
            case["fins"][f] = {
                "CL_fin_on_own_lattice_area": float(Fv @ lift_dir / (0.5 * lats[f]["area"].sum())),
                "force_coeff_vec_rho1_V1": Fv.tolist(),
                "quad_dCp": qd.tolist(),
                "quad_upper_normal": geos[f]["qn"].tolist(),
                "quad_area_m2": geos[f]["qarea"].tolist(),
                "uncovered_area_frac": unc,
                "transfer_vector_residual_over_gross": float(np.linalg.norm(Fq.sum(axis=0) - Fv) / gross),
                "normal_pressure_residual_over_gross": float(np.linalg.norm(Fn.sum(axis=0) - Fv) / gross),
                "normal_pressure_lift_ratio": float((Fn.sum(axis=0) @ lift_dir) / (Fv @ lift_dir))
                if abs(Fv @ lift_dir) > 1e-3 * gross else None,
                "quad_area_sum_m2": float(geos[f]["qarea"].sum()), "lattice_area_m2": float(lats[f]["area"].sum())}
        res["cases"][str(alpha)] = case
        case["paired_fin_lift_N"] = {m: {str(u): case["CL_paired_fins_on_S_lattice"] * 0.5 * MEDIA[m]["rho"] * u * u * S
                                         for u in SPEEDS[m]["values_m_s"]} for m in MEDIA}
    res["dynamic_pressure_Pa"] = {m: {str(u): 0.5 * MEDIA[m]["rho"] * u * u for u in SPEEDS[m]["values_m_s"]}
                                  for m in MEDIA}
    res["pa_rule"] = "delta_p_Pa = quad_dCp * dynamic_pressure_Pa[medium][speed]; pushes the fin along +quad_upper_normal"
    res["refinement"] = _refine(panels, ns, nc, res["cases"]["4"])
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "vlm.json").write_text(json.dumps(res, indent=1))
    return res


def _refine(panels, ns, nc, base, alpha=4, k=1.5):
    """Same fins at k x the lattice in each direction: change in CL and in the transferred quad dCp."""
    n2, c2 = int(round(ns * k)), int(round(nc * k))
    lats, geos = {}, {}
    for f in PAIRED:
        lats[f], geos[f] = fin_setup(panels["fins"][f], n2, c2)
    allp = combine(lats)
    _, F, _, _ = solve(allp, alpha)
    a = math.radians(alpha)
    S = float(sum(lats[f]["area"].sum() for f in PAIRED))
    cl = float(F.sum(axis=0) @ np.array([-math.sin(a), 0, math.cos(a)]) / (0.5 * S))
    o, out = np.array(allp["owner"]), {"alpha_deg": alpha, "lattice": [n2, c2],
                                       "CL_rel_change": abs(cl / base["CL_paired_fins_on_S_lattice"] - 1)}
    for f in PAIRED:
        Fq, _ = transfer(lats[f], geos[f], F[o == f])
        qd = np.einsum("qk,qk->q", Fq, geos[f]["qn"]) / (0.5 * geos[f]["qarea"])
        q0 = np.array(base["fins"][f]["quad_dCp"])
        out[f] = {"quad_dCp_rms_change_over_rms": float(np.sqrt(np.mean((qd - q0) ** 2)) / np.sqrt(np.mean(q0 ** 2))),
                  "quad_dCp_max_abs_change": float(np.abs(qd - q0).max())}
    return out


def _thk(comps, f):
    t = comps["components"][f]["params"]["thickness_mm"]
    return {"thickness_mm": t, "modelled_as": "zero-thickness surface (unresolved, not resolved)"}


def _regimes(L):
    return {"note": "VLM is inviscid and Re-independent; validity needs attached flow (thin boundary layers, "
                    "small alpha). The listed Re only say which real regime a dCp would be converted for.",
            "L_body_m": L, "L_body_basis": "body bbox x-extent (for v3a/b/c it equals candidate biology.standard_length_m)",
            "Re_L": {m: [u * L / MEDIA[m]["nu"] for u in SPEEDS[m]["values_m_s"]] for m in MEDIA}}


if __name__ == "__main__":
    if sys.argv[1] == "controls":
        r = controls()
        Path(sys.argv[2]).write_text(json.dumps(r, indent=1))
        print(json.dumps({k: (v["pass"] if isinstance(v, dict) else v) for k, v in r.items()}))
    else:
        r = fish(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else "")
        print(json.dumps({a: {"CL": c["CL_paired_fins_on_S_lattice"], "side/lift": c["side_force_over_lift"],
                              "unc": {f: round(v["uncovered_area_frac"], 4) for f, v in c["fins"].items()},
                              "res_n": {f: round(v["normal_pressure_residual_over_gross"], 4) for f, v in c["fins"].items()},
                              "Lratio": {f: v["normal_pressure_lift_ratio"] and round(v["normal_pressure_lift_ratio"], 4)
                                         for f, v in c["fins"].items()}}
                          for a, c in r["cases"].items()}))
