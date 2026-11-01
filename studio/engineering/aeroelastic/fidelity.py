"""Predeclared VLM-lattice resolution ladder for the strongest returned static-feedback effects.

Every arm is engineering.aeroelastic.run.solve_arm, unchanged, under the original protocol.json physics; only
the lattice varies, through solve_arm's existing grid_override. Selection, diagnostics and decision rules are
frozen in artifacts/aeroelastic/fidelity-v1/protocol.json before any ladder result exists.

    python -m engineering.aeroelastic.fidelity run --out output        # the packet's entry point
    python -m engineering.aeroelastic.fidelity preflight --out DIR     # controls + one reproduced arm
    python -m engineering.aeroelastic.fidelity analyze --out output    # re-derive summary from saved arms
    python -m engineering.aeroelastic.fidelity pack                    # build the source-hashed packet
"""

import argparse
import gzip
import io
import json
import math
import multiprocessing
import platform
import subprocess
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path

import numpy as np
import scipy

from engineering.cfd3d import vlm

from .controls import run as original_controls
from .model import (
    ART,
    ROOT,
    Response,
    check_inputs,
    deform,
    dump,
    protocol,
    setup,
    transfer,
)
from .run import solve_arm

FID = ART / "fidelity-v1"
ROUNDOFF = {"absolute": 1e-10, "relative": 1e-9}


def fprotocol():
    return json.loads((FID / "protocol.json").read_text())


def grid(fp, mesh):
    item = fp["lattices"][mesh]
    return item["span"], item["chord"]


def override(fp, mesh):
    """main/fine take the original production path; ladder lattices go through grid_override."""
    if fp["lattices"][mesh]["path"].startswith("original"):
        return None
    span, chord = grid(fp, mesh)
    return {"span": span, "chord": chord}


def arm_id(compliance, speed, mesh, arm):
    return f"chi{compliance}-u{speed:g}-{mesh}-{arm}"


def check_references(fp):
    for item in fp["references"]:
        raw = (ROOT / item["path"]).read_bytes()
        if len(raw) != item["bytes"] or sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"Packed reference changed: {item['path']}")
    pin = fp["physics_unchanged"]["original_protocol"]
    if sha256((ROOT / pin["path"]).read_bytes()).hexdigest() != pin["sha256"]:
        raise ValueError("Original protocol changed")


# ---------------------------------------------------------------- independent transfer checks
def reference_axis(source):
    plane = source["fin_plane"]
    eu, ew = np.asarray(plane["e_u"], float), np.asarray(plane["e_w"], float)
    n = np.cross(ew, eu)
    n /= np.linalg.norm(n)
    return n if n[2] >= 0 else -n


def independent_transfer(fin, force, EI):
    """Checks that do not reuse the quantity they check (unlike the transfer ledger identities)."""
    lat, geo = fin["lattice"], fin["geometry"]
    strip = np.array([s[0] for s in lat["strip"]])
    s_ind = 0.5 * (lat["ue"][strip] + lat["ue"][strip + 1]) - fin["lower"]
    n_ref = reference_axis(fin["source"])
    N_ref = force @ n_ref
    normal, _ = transfer(fin, lat, force)
    x = np.array([0.25, 0.5]) * min(s_ind.min(), fin["response"].stations.min())
    w, _ = fin["response"].evaluate(x, normal, EI)
    # unloaded root segment: EI w = M0 x^2/2 - V0 x^3/6
    M0, V0 = np.linalg.solve(np.c_[x**2 / 2, -(x**3) / 6], EI * w)
    M_ref, V_ref = float(s_ind @ N_ref), float(N_ref.sum())
    station_error = float(np.max(abs(s_ind - fin["response"].stations)))
    axis_error = float(np.linalg.norm(geo["n_up"] - n_ref))
    return {
        "station_error_m": station_error,
        "axis_error": axis_error,
        "axis_dot_e_u": float(abs(n_ref @ geo["eu"])),
        "min_lattice_normal_dot_n_up": float((lat["N"] @ n_ref).min()),
        "root_moment_relative_error": abs(M0 - M_ref) / max(abs(M_ref), 1e-30),
        "root_shear_relative_error": abs(V0 - V_ref) / max(abs(V_ref), 1e-30),
        "normal_force_N": float(abs(N_ref.sum())),
        "checks": {
            "stations": station_error <= 1e-12,
            "axis": axis_error <= 1e-12
            and abs(n_ref @ geo["eu"]) <= 1e-12
            and float((lat["N"] @ n_ref).min()) > 0,
            "beam_equilibrium": abs(M0 - M_ref) <= 1e-8 * abs(M_ref)
            and abs(V0 - V_ref) <= 1e-8 * abs(V_ref),
        },
    }


def fixed_area_CL(fins, lattices, speed):
    """CL on the fixed source area from the unit (rho=1, V=1) VLM solve, plus the physical panel forces."""
    p = protocol()
    alpha = np.deg2rad(p["parameters"]["alpha_deg"])
    rho = p["parameters"]["rho_kg_m3"]
    _, unit, _, _ = vlm.solve(vlm.combine(lattices), p["parameters"]["alpha_deg"])
    area = sum(f["source"]["area_flat_m2"] for f in fins.values())
    lift = np.array([-np.sin(alpha), 0, np.cos(alpha)])
    return float(unit.sum(axis=0) @ lift / area / 0.5), unit * rho * speed**2


def scale_checks(fins, force, speed):
    """Cross-artifact force scale against the upstream 48x16 vlm.json, and the thin-airfoil CL bound."""
    p = protocol()
    alpha = np.deg2rad(p["parameters"]["alpha_deg"])
    q = 0.5 * p["parameters"]["rho_kg_m3"] * speed**2
    area = sum(f["source"]["area_flat_m2"] for f in fins.values())
    lift = np.array([-np.sin(alpha), 0, np.cos(alpha)])
    CL = float(force.sum(axis=0) @ lift / (q * area))
    offset, ratios = 0, {}
    for name, fin in fins.items():
        size = len(fin["lattice"]["area"])
        normal = abs(
            float(
                force[offset : offset + size].sum(axis=0)
                @ reference_axis(fin["source"])
            )
        )
        offset += size
        reference = (
            p["parameters"]["EI_inputs"][name]["reference_normal_force_N"]
            * (speed / 20.0) ** 2
        )
        ratios[name] = normal / reference - 1
    return {
        "CL": CL,
        "CL_per_rad": CL / alpha,
        "normal_force_relative_to_upstream_48x16": ratios,
        "checks": {
            "upstream_force": all(abs(r) <= 0.03 for r in ratios.values()),
            "thin_airfoil_bound": 0 < CL / alpha <= 2 * math.pi,
        },
    }


def lattice_controls(payload):
    """Zero/stiff limits, ledger identities, independent transfer checks and their mutations on one lattice."""
    mesh, span, chord, out = payload
    p = protocol()
    g = p["gates"]
    speed = p["parameters"]["reference_speed_m_s"]
    started = time.monotonic()
    fins = setup(span, chord)
    lattices = {n: f["lattice"] for n, f in fins.items()}
    rigid_CL, force = fixed_area_CL(fins, lattices, speed)
    EI = {
        n: p["parameters"]["EI_inputs"][n]["EI_Nm2_by_compliance"]["0.8"] for n in fins
    }
    checks, fins_out = {}, {}
    zeros, stiff = {}, {}
    offset = 0
    for name, fin in fins.items():
        size = len(fin["lattice"]["area"])
        f = force[offset : offset + size]
        offset += size
        normal, ledger = transfer(fin, fin["lattice"], f)
        dropped = normal.copy()
        dropped[int(abs(dropped).argmax())] = 0
        independent = independent_transfer(fin, f, EI[name])
        shifted = dict(
            fin, response=Response(fin["length"], 0.8 * fin["response"].stations)
        )
        swapped = dict(fin, geometry=dict(fin["geometry"], n_up=fin["geometry"]["ew"]))
        m_station = independent_transfer(shifted, f, EI[name])["checks"]
        m_axis = independent_transfer(swapped, f, EI[name])["checks"]
        zeros[name] = deform(fin, np.zeros_like(normal), 1.0)
        stiff[name] = deform(fin, normal, EI[name] * g["stiff_limit_EI_multiplier"])
        tiny, _ = fin["response"].evaluate(
            np.linspace(0, fin["length"], 501),
            normal,
            EI[name] * g["stiff_limit_EI_multiplier"],
        )
        fins_out[name] = {"ledger": ledger, "independent": independent}
        checks[f"ledger_identities_{name}"] = ledger["passed"]
        checks[f"ledger_mutation_rejected_{name}"] = not transfer(
            fin, fin["lattice"], f, dropped
        )[1]["passed"]
        for key, value in independent["checks"].items():
            checks[f"{key}_{name}"] = value
        checks[f"station_mutation_rejected_{name}"] = not (
            m_station["stations"] or m_station["beam_equilibrium"]
        )
        checks[f"axis_mutation_rejected_{name}"] = not (
            m_axis["axis"] or m_axis["beam_equilibrium"]
        )
        checks[f"stiff_limit_tip_{name}"] = (
            float(max(abs(tiny))) / fin["length"] <= g["stiff_limit_tip_over_span_max"]
        )
    zero_CL, _ = fixed_area_CL(fins, zeros, speed)
    stiff_CL, _ = fixed_area_CL(fins, stiff, speed)
    checks["zero_load_geometry_exact"] = all(
        np.array_equal(lattices[n][k], zeros[n][k])
        for n in fins
        for k in ["A", "B", "C", "N"]
    )
    checks["zero_load_CL"] = (
        abs(zero_CL - rigid_CL) <= g["zero_load_CL_absolute_difference_max"]
    )
    checks["stiff_limit_CL"] = (
        abs(stiff_CL - rigid_CL) <= g["stiff_limit_CL_absolute_difference_max"]
    )
    scale = scale_checks(fins, force, speed)
    checks.update(scale["checks"])
    unit_scale = scale_checks(
        fins, force / (p["parameters"]["rho_kg_m3"] * speed**2), speed
    )["checks"]
    double_scale = scale_checks(fins, 2 * force, speed)["checks"]
    checks["unit_force_mutation_rejected"] = not unit_scale["upstream_force"]
    checks["doubled_force_mutation_rejected"] = not (
        double_scale["thin_airfoil_bound"] or double_scale["upstream_force"]
    )
    result = {
        "schema": "frontier.aeroelastic.fidelity-lattice-controls/1",
        "mesh": mesh,
        "lattice": {
            "span": span,
            "chord": chord,
            "panels": int(sum(len(x["area"]) for x in lattices.values())),
        },
        "speed_m_s": speed,
        "rigid_CL": rigid_CL,
        "zero_load_CL": zero_CL,
        "stiff_limit_CL": stiff_CL,
        "scale": scale,
        "fins": fins_out,
        "checks": checks,
        "passed": all(checks.values()),
        "wall_seconds": time.monotonic() - started,
        "scope": "Numerical consistency at this lattice; ledger identities are bookkeeping, independent checks and mutations are listed separately",
    }
    dump(Path(out) / "lattice-controls" / f"{mesh}.json", result)
    return result


# ---------------------------------------------------------------- arms
def arm_group(payload):
    """The three paired arms of one context on one lattice; failures are saved, never dropped."""
    compliance, speed, mesh, grid_override, out, deadline = payload
    rows = []
    for arm in protocol()["parameters"]["arms"]:
        name = arm_id(compliance, speed, mesh, arm)
        started = time.monotonic()
        if started > deadline:
            result = {
                "status": "not-started: deadline",
                "valid_for_declared_transfer": False,
            }
        else:
            try:
                result = solve_arm(
                    compliance,
                    speed,
                    mesh,
                    arm,
                    Path(out) / "arms" / name,
                    deadline,
                    grid_override,
                )
            except Exception as exc:
                result = {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "valid_for_declared_transfer": False,
                }
                dump(Path(out) / "arms" / name / "failure.json", result)
        result.update(
            id=name,
            compliance=compliance,
            speed_m_s=speed,
            mesh=mesh,
            arm=arm,
            wall_seconds=time.monotonic() - started,
        )
        rows.append(result)
    dump(Path(out) / "progress" / f"chi{compliance}-u{speed:g}-{mesh}.json", rows)
    return rows


def panels(fp, mesh):
    span, chord = grid(fp, mesh)
    return span * chord


def tasks(fp, out, deadline):
    """Heaviest lattice first so the critical path starts at once."""
    meshes = sorted(fp["lattices"], key=lambda m: -panels(fp, m))
    work = []
    for mesh in meshes:
        span, chord = grid(fp, mesh)
        work += [
            (
                arm_group,
                (
                    c["compliance"],
                    c["speed_m_s"],
                    mesh,
                    override(fp, mesh),
                    str(out),
                    deadline,
                ),
            )
            for c in fp["selected_contexts"]
        ]
        work.append((lattice_controls, (mesh, span, chord, str(out))))
    return work


# ---------------------------------------------------------------- analysis (frozen rules)
def final(arm, key):
    return arm["iterations"][-1][key]


def fixed_point_bound(arm):
    """A-posteriori bound for a two-way arm from its own residual history; 0 for rigid/one-way."""
    if arm["arm"] != "two-way-static-feedback":
        return {"CL": 0.0, "shape_over_span": 0.0, "rho": None}
    history = [x["shape_residual_over_span"] for x in arm["iterations"]]
    ratios = [b / a for a, b in zip(history[-4:-1], history[-3:]) if a > 0]
    rho = max(ratios) if ratios else math.inf
    if not rho < 1:
        return {"CL": math.inf, "shape_over_span": math.inf, "rho": rho}
    return {
        "CL": abs(arm["iterations"][-1]["CL_change"]) * rho / (1 - rho),
        "shape_over_span": history[-1] * rho / (1 - rho),
        "rho": rho,
    }


def dt_floor(arm):
    return abs(arm["flight"]["main"]["range_m"] - arm["flight"]["half"]["range_m"])


def effects(arms):
    """Paired effects on one lattice for one context; arms maps arm name -> result."""
    two = arms["two-way-static-feedback"]
    CL = {a: final(x, "CL_on_fixed_source_area") for a, x in arms.items()}
    rng = {a: x["flight"]["main"]["range_m"] for a, x in arms.items()}
    fp = {a: fixed_point_bound(x) for a, x in arms.items()}
    cl_floor = {a: fp[a]["CL"] for a in arms}
    range_floor = {
        a: dt_floor(x) + abs(rng[a]) * fp[a]["CL"] / abs(CL[a]) for a, x in arms.items()
    }
    pairs = {
        "one_way_minus_rigid": ("rigid", "one-way-frozen-load"),
        "two_way_minus_one_way": ("one-way-frozen-load", "two-way-static-feedback"),
        "two_way_minus_rigid": ("rigid", "two-way-static-feedback"),
    }
    out = {}
    for label, (a, b) in pairs.items():
        out[f"dCL_{label}"] = {
            "value": CL[b] - CL[a],
            "floor": cl_floor[a] + cl_floor[b],
        }
        out[f"dRange_{label}_m"] = {
            "value": rng[b] - rng[a],
            "floor": range_floor[a] + range_floor[b],
        }
    shape = two["iterations"][-1]["shape_validity"]
    for part, fin in [("pectoral", "pectoral_L"), ("pelvic", "pelvic_L")]:
        out[f"tip_over_L_two_way_{part}"] = {
            "value": shape[fin]["tip_over_L"],
            "floor": fp["two-way-static-feedback"]["shape_over_span"],
        }
    out["CL_rigid"] = {"value": CL["rigid"], "floor": 0.0}
    return out


def triple(values, ratio):
    """Three-grid behaviour of one quantity, coarse -> fine (frozen formulas)."""
    coarse, medium, fine = values
    e21, e32 = medium - coarse, fine - medium
    small = ROUNDOFF["absolute"] + ROUNDOFF["relative"] * max(abs(fine), abs(medium))
    row = {"values": list(values), "e21": e21, "e32": e32}
    if abs(e21) <= small and abs(e32) <= small:
        return row | {
            "behaviour": "roundoff_insensitive",
            "p": None,
            "extrapolated": fine,
            "GCI_abs": small,
            "GCI_rel": small / max(abs(fine), 1e-300),
        }
    R = e32 / e21 if e21 != 0 else math.inf
    row["R"] = R
    if not 0 < R < 1:
        return row | {
            "behaviour": "oscillatory" if -1 < R < 0 else "divergent",
            "p": None,
        }
    p = math.log(1 / R) / math.log(ratio)
    denominator = ratio**p - 1
    gci = 1.25 * abs(e32) / denominator
    return row | {
        "behaviour": "monotone",
        "p": p,
        "extrapolated": fine + e32 / denominator,
        "GCI_abs": gci,
        "GCI_rel": gci / max(abs(fine), 1e-300),
    }


def classify(series, floor, fp):
    """Apply the frozen resolved / sign_resolved / not_resolved rule to one effect's five-lattice series."""
    tri = {
        k: triple([series[m] for m in t["lattices"]], t["ratio"])
        for k, t in fp["triples"].items()
    }
    finest, previous = series["l64x16"], series["l32x8"]
    signs = {np.sign(v) for v in series.values()}
    same_sign = len(signs) == 1 and 0 not in signs
    above_floor = abs(finest) >= 10 * floor
    reasons = []
    good = {"monotone", "roundoff_insensitive"}
    if not all(t["behaviour"] in good for t in tri.values()):
        reasons.append(
            "triple not monotone: "
            + ", ".join(f"{k} {t['behaviour']}" for k, t in tri.items())
        )
    else:
        for k, t in tri.items():
            if t["p"] is not None and not 0.5 <= t["p"] <= 4:
                reasons.append(f"{k} observed order {t['p']:.3g} outside [0.5, 4]")
        if tri["T2"]["GCI_rel"] > 0.10:
            reasons.append(f"T2 GCI_rel {tri['T2']['GCI_rel']:.3g} > 0.10")
        if (
            abs(tri["T2"]["extrapolated"] - tri["T1.5"]["extrapolated"])
            > tri["T2"]["GCI_abs"] + tri["T1.5"]["GCI_abs"]
        ):
            reasons.append(
                "T2 and T1.5 extrapolations disagree beyond their summed GCI"
            )
    if not same_sign:
        reasons.append("sign changes across lattices")
    if not above_floor:
        reasons.append("finest value below 10x numerical floor")
    if not reasons:
        status = "resolved"
    elif same_sign and above_floor and abs(finest) >= 3 * abs(finest - previous):
        status = "sign_resolved"
    else:
        status = "not_resolved"
    return {
        "status": status,
        "reasons": reasons,
        "series": series,
        "floor_at_finest": floor,
        "triples": tri,
    }


def decide(context_effects):
    """Frozen decision convention; never a fish-performance statement."""
    bending, feedback, rigid = (
        context_effects[k]
        for k in ["dCL_one_way_minus_rigid", "dCL_two_way_minus_one_way", "CL_rigid"]
    )
    out = {}
    if bending["status"] == "resolved":
        T2 = rigid["triples"]["T2"]
        reference = (
            T2["extrapolated"]
            if T2["behaviour"] in ("monotone", "roundoff_insensitive")
            else rigid["series"]["l64x16"]
        )
        relative = abs(bending["triples"]["T2"]["extrapolated"]) / abs(reference)
        out["bending"] = {
            "decision": "retain_bending" if relative >= 0.01 else "reject_bending",
            "relative": relative,
            "rigid_CL_reference": reference,
        }
    else:
        out["bending"] = {"decision": "undetermined", "why": bending["reasons"]}
    if out["bending"]["decision"] == "undetermined":
        out["feedback"] = {
            "decision": "undetermined",
            "why": ["one-way effect not resolved"],
        }
        return out
    scale = abs(bending["triples"]["T2"]["extrapolated"])
    if feedback["status"] == "resolved":
        size = abs(feedback["triples"]["T2"]["extrapolated"])
        out["feedback"] = {
            "decision": "two_way_needed"
            if size >= 0.10 * scale
            else "one_way_sufficient",
            "ratio_to_one_way": size / scale,
        }
    elif feedback["status"] == "sign_resolved":
        finest, previous = feedback["series"]["l64x16"], feedback["series"]["l32x8"]
        bound = abs(finest) + abs(finest - previous)
        out["feedback"] = {
            "decision": "one_way_sufficient"
            if bound < 0.10 * scale
            else "undetermined",
            "ratio_bound_to_one_way": bound / scale,
        }
    else:
        out["feedback"] = {"decision": "undetermined", "why": feedback["reasons"]}
    return out


def reproduction(fp, arms):
    """Recomputed main/fine arms against the packed a54f478 references."""
    rows = []
    for item in fp["references"]:
        ref = json.loads((ROOT / item["path"]).read_text())
        name = Path(item["path"]).parent.name
        new = arms.get(name)
        row = {
            "id": name,
            "reference_sha256": item["sha256"],
            "present": new is not None,
        }
        if new is None or "iterations" not in new:
            rows.append(
                row
                | {
                    "exact": False,
                    "within_roundoff": False,
                    "status": None if new is None else new["status"],
                }
            )
            continue
        pairs = [
            (a["CL_on_fixed_source_area"], b["CL_on_fixed_source_area"])
            for a, b in zip(ref["iterations"], new["iterations"])
        ]
        for fin in ref["iterations"][-1]["shape_validity"]:
            pairs.append(
                (
                    ref["iterations"][-1]["shape_validity"][fin]["tip_over_L"],
                    new["iterations"][-1]["shape_validity"][fin]["tip_over_L"],
                )
            )
        if ref["flight"] and new["flight"]:
            pairs += [
                (ref["flight"][d]["range_m"], new["flight"][d]["range_m"])
                for d in ["main", "half"]
            ]
        same = (
            ref["status"] == new["status"]
            and len(ref["iterations"]) == len(new["iterations"])
            and (ref["flight"] is None) == (new["flight"] is None)
        )
        diff = max(
            (
                abs(a - b) - ROUNDOFF["absolute"] - ROUNDOFF["relative"] * abs(a)
                for a, b in pairs
            ),
            default=0.0,
        )
        rows.append(
            row
            | {
                "status_and_counts_equal": same,
                "exact": same and all(a == b for a, b in pairs),
                "within_roundoff": same and diff <= 0,
                "compared_values": len(pairs),
            }
        )
    return rows


def load(out):
    """Saved arm rows and lattice controls of one output directory."""
    arms = {}
    for path in sorted((out / "progress").glob("*.json")):
        for row in json.loads(path.read_text()):
            arms[row["id"]] = row
    controls = {
        p.stem: json.loads(p.read_text())
        for p in sorted((out / "lattice-controls").glob("*.json"))
    }
    return arms, controls


def analyze(out):
    out = Path(out)
    fp = fprotocol()
    arms, controls = load(out)
    contexts = []
    for c in fp["selected_contexts"]:
        compliance, speed = c["compliance"], c["speed_m_s"]
        rows = {
            m: {
                a: arms.get(arm_id(compliance, speed, m, a))
                for a in protocol()["parameters"]["arms"]
            }
            for m in fp["lattices"]
        }
        statuses = {
            arm_id(compliance, speed, m, a): (x or {"status": "missing"})["status"]
            for m, group in rows.items()
            for a, x in group.items()
        }
        valid = {
            m: all(
                x is not None and x["valid_for_declared_transfer"]
                for x in group.values()
            )
            for m, group in rows.items()
        }
        per_mesh = {m: effects(group) for m, group in rows.items() if valid[m]}
        entry = {
            "compliance": compliance,
            "speed_m_s": speed,
            "statuses": statuses,
            "descriptive_series": {
                k: {m: per_mesh[m][k]["value"] for m in per_mesh} for k in fp["effects"]
            }
            if per_mesh
            else {},
        }
        if all(valid.values()):
            classified = {
                k: classify(
                    {m: per_mesh[m][k]["value"] for m in fp["lattices"]},
                    per_mesh["l64x16"][k]["floor"],
                    fp,
                )
                for k in fp["effects"]
            }
            entry |= {
                "assessable": True,
                "effects": classified,
                "decision": decide(classified),
            }
        else:
            entry |= {
                "assessable": False,
                "decision": {
                    "bending": {"decision": "undetermined", "why": ["not_assessable"]},
                    "feedback": {"decision": "undetermined", "why": ["not_assessable"]},
                },
            }
        contexts.append(entry)
    declared = len(fp["selected_contexts"]) * len(fp["lattices"]) * 3
    summary = {
        "schema": "frontier.aeroelastic.fidelity-results/1",
        "protocol_sha256": sha256((FID / "protocol.json").read_bytes()).hexdigest(),
        "declared_arms": declared,
        "returned_arms": len(arms),
        "valid_arms": sum(
            bool(x.get("valid_for_declared_transfer")) for x in arms.values()
        ),
        "status_counts": {
            s: sum(x["status"] == s for x in arms.values())
            for s in sorted({x["status"] for x in arms.values()})
        },
        "lattice_controls_passed": {m: c["passed"] for m, c in controls.items()},
        "reproduction_of_a54f478": reproduction(fp, arms),
        "contexts": contexts,
        "scope": fp["decision"]["scope"],
        "biological_success_probability": None,
    }
    dump(out / "summary.json", summary)
    return summary


# ---------------------------------------------------------------- execution, receipt, packet
def environment_check():
    if np.__version__ != "2.5.4" or scipy.__version__ != "1.17.1":
        raise ValueError("Exact frozen NumPy/SciPy pins required")


def receipt(out, started, failure, fp):
    files = [p for p in out.rglob("*") if p.is_file() and p.name != "receipt.json"]
    sources = [ROOT / "engineering/aeroelastic" / n for n in PACKAGE] + [
        ROOT / x for x in SHARED_SOURCES
    ]
    result = {
        "schema": "frontier.aeroelastic.fidelity-receipt/1",
        "fidelity_protocol_sha256": sha256(
            (FID / "protocol.json").read_bytes()
        ).hexdigest(),
        "original_protocol_sha256": sha256(
            (ART / "protocol.json").read_bytes()
        ).hexdigest(),
        "sources": {
            str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "device": "CPU",
        },
        "wall_seconds": time.monotonic() - started,
        "failure": failure,
        "files": [
            {
                "path": str(p.relative_to(out)),
                "sha256": sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }
            for p in files
        ],
        "dollars": None,
    }
    result["output_bytes"] = sum(x["bytes"] for x in result["files"])
    result["output_cap_exceeded"] = (
        result["output_bytes"] > fp["resources"]["output_cap_bytes"]
    )
    dump(out / "receipt.json", result)
    return result


def run(out, preflight=False):
    if out.exists():
        raise ValueError("Fresh output directory required")
    out = out.resolve()
    out.mkdir(parents=True)
    fp = fprotocol()
    started = time.monotonic()
    failure = None
    try:
        environment_check()
        check_inputs()
        check_references(fp)
        if not original_controls(out / "controls-original.json")["passed"]:
            raise RuntimeError("Original numerical controls failed")
        deadline = started + fp["resources"]["soft_no_new_work_seconds"]
        work = tasks(fp, out, deadline)
        if preflight:  # local: main-lattice controls and one reproduced arm group only
            work = [
                w
                for w in work
                if w[1][0] == "main"
                or (
                    w[0] is arm_group
                    and w[1][2] == "main"
                    and w[1][0] == fp["selected_contexts"][0]["compliance"]
                    and w[1][1] == fp["selected_contexts"][0]["speed_m_s"]
                )
            ]
        crashed = []
        with ProcessPoolExecutor(
            max_workers=1 if preflight else fp["resources"]["workers"],
            mp_context=multiprocessing.get_context("spawn"),
        ) as pool:
            futures = {
                pool.submit(fn, payload): (fn.__name__, payload[:4])
                for fn, payload in work
            }
            for item in as_completed(futures):
                try:
                    item.result()
                except (
                    Exception
                ) as exc:  # a crashed task is recorded; the others still return
                    crashed.append(
                        {
                            "task": futures[item][0],
                            "payload": [str(x) for x in futures[item][1]],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    dump(out / "task-failures.json", crashed)
        if preflight:
            arms, controls = load(out)
            rows = [r for r in reproduction(fp, arms) if r["present"]]
            dump(
                out / "preflight.json",
                {
                    "scope": "local preflight: original controls, main-lattice controls, one reproduced arm group; not the ladder",
                    "lattice_controls_passed": {
                        m: c["passed"] for m, c in controls.items()
                    },
                    "reproduction_of_a54f478": rows,
                },
            )
            if (
                crashed
                or not all(c["passed"] for c in controls.values())
                or not all(r["within_roundoff"] for r in rows)
            ):
                failure = "preflight check failed (results kept)"
        else:
            summary = analyze(out)
            problems = []
            if crashed:
                problems.append(f"{len(crashed)} task(s) crashed")
            if not all(summary["lattice_controls_passed"].values()) or len(
                summary["lattice_controls_passed"]
            ) != len(fp["lattices"]):
                problems.append("lattice controls failed or missing")
            if summary["returned_arms"] != summary["declared_arms"] or any(
                s.startswith(("not-started", "partial"))
                for s in summary["status_counts"]
            ):
                problems.append("incomplete arms")
            failure = "; ".join(problems) + " (all results kept)" if problems else None
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        dump(out / "failure.json", {"error": failure})
    r = receipt(out, started, failure, fp)
    print(
        {
            "failure": failure,
            "bytes": r["output_bytes"],
            "wall_seconds": r["wall_seconds"],
        },
        flush=True,
    )
    return 1 if failure or r["output_cap_exceeded"] else 0


SHARED_SOURCES = [
    "engineering/fin_mechanics/__init__.py",
    "engineering/fin_mechanics/beam.py",
    "engineering/cfd3d/vlm.py",
    "engineering/cfd3d/gates_vlm.json",
    "engineering/simulation/__init__.py",
    "engineering/simulation/glide.py",
    "engineering/simulation/schema.py",
]
PACKAGE = [
    "__init__.py",
    "model.py",
    "flight.py",
    "controls.py",
    "run.py",
    "fidelity.py",
    "requirements.txt",
]


def pack(measured):
    fp = fprotocol()
    source = [ROOT / "engineering/aeroelastic" / n for n in PACKAGE] + [
        ROOT / x for x in SHARED_SOURCES
    ]
    source += [ROOT / x["path"] for x in protocol()["inputs"]]
    source += [ART / "protocol.json", FID / "protocol.json"] + [
        ROOT / x["path"] for x in fp["references"]
    ]
    payload, files = io.BytesIO(), []
    with (
        gzip.GzipFile(fileobj=payload, mode="wb", filename="", mtime=0) as zipped,
        tarfile.open(fileobj=zipped, mode="w") as archive,
    ):
        for path in sorted(source):
            raw = path.read_bytes()
            info = tarfile.TarInfo(str(path.relative_to(ROOT)))
            info.size, info.mode = len(raw), 0o644
            archive.addfile(info, io.BytesIO(raw))
            files.append(
                {
                    "path": info.name,
                    "sha256": sha256(raw).hexdigest(),
                    "bytes": len(raw),
                }
            )
    archive_path = FID / "fidelity-cpu-packet.tar.gz"
    archive_path.write_bytes(payload.getvalue())
    manifest = {
        "schema": "frontier.aeroelastic.fidelity-cpu-packet/1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "archive_path": str(archive_path.relative_to(ROOT)),
        "archive_sha256": sha256(archive_path.read_bytes()).hexdigest(),
        "archive_bytes": archive_path.stat().st_size,
        "entry_argv": [
            "python",
            "-m",
            "engineering.aeroelastic.fidelity",
            "run",
            "--out",
            "output",
        ],
        "requirements": "engineering/aeroelastic/requirements.txt",
        "environment": {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
        "resources": fp["resources"],
        "measured_runtime_control": json.loads(Path(measured).read_text()),
        "files": files,
        "outputs": [
            "output/controls-original.json",
            "output/lattice-controls/<5 lattices>.json",
            "output/arms/<45 arms>/{result.json,static-states.npz,glide-main.npz,glide-half.npz,failure.json} as applicable",
            "output/progress/*.json",
            "output/summary.json",
            "output/receipt.json",
            "output/failure.json if any",
        ],
        "input_network_required": False,
        "no_credentials_or_model_inference": True,
    }
    dump(FID / "packet.json", manifest)
    print(
        {k: manifest[k] for k in ["source_commit", "archive_sha256", "archive_bytes"]}
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "preflight", "analyze", "pack"])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--measured", type=Path, help="runtime-control JSON for pack")
    args = parser.parse_args()
    if args.command == "pack":
        pack(args.measured)
    elif args.command == "analyze":
        analyze(args.out)
    else:
        raise SystemExit(run(args.out, preflight=args.command == "preflight"))
