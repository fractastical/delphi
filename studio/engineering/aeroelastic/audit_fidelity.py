"""Independent return audit of the fidelity-ladder batch; frozen in fidelity-v1/return-audit-protocol.json.

Reads a returned output tree read-only and records findings instead of stopping at the first one, so every
numerical failure, domain exit, partial and missing arm stays visible beside the native status. Where it can,
it recomputes by a different route from the runner: closed-form cantilever Green's functions instead of the FE
response, strip-spacing stations and panels.json axes instead of the setup ones, a separate three-grid
implementation, and one fresh VLM solve on each stored final pose. It never reruns an arm.

    python -m engineering.aeroelastic.audit_fidelity --output RETURNED_OUTPUT_DIR --report REPORT.json
        [--collection TRANSPORT_MANIFEST.json]
"""

import argparse
import itertools
import json
import math
from hashlib import sha256
from pathlib import Path

import numpy as np

from engineering.cfd3d import vlm
from engineering.simulation import glide
from engineering.simulation.schema import G

from .model import ART, ROOT, deform, displaced, dump, protocol, setup

FID = ART / "fidelity-v1"


def frozen():
    return json.loads((FID / "return-audit-protocol.json").read_text())


def read(path):
    def reject(value):
        raise ValueError("Nonfinite JSON constant " + value)

    return json.loads(Path(path).read_bytes(), parse_constant=reject)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


class Ledger:
    """Findings and value comparisons; exact equality and fixed roundoff are kept apart."""

    def __init__(self, tolerance):
        self.tolerance = tolerance
        self.findings = []
        self.comparisons = []

    def find(self, kind, subject, detail):
        self.findings.append({"kind": kind, "subject": subject, "detail": detail})

    def compare(self, subject, actual, stored, scale=None):
        a, b = np.asarray(actual, float), np.asarray(stored, float)
        if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            self.find(
                "reproduction", subject, f"shape/finite mismatch {a.shape} vs {b.shape}"
            )
            return False
        reference = np.max(abs(b)) if scale is None else scale
        tol = self.tolerance["absolute"] + self.tolerance["relative"] * reference
        difference = float(np.max(abs(a - b))) if a.size else 0.0
        row = {
            "subject": subject,
            "exact": bool(np.array_equal(a, b)),
            "within_roundoff": difference <= tol,
            "max_abs_difference": difference,
        }
        self.comparisons.append(row)
        if not row["within_roundoff"]:
            self.find(
                "reproduction",
                subject,
                f"max |difference| {difference:.3g} > {tol:.3g}",
            )
        return row["within_roundoff"]


# ---------------------------------------------------------------- closed-form structure (not the FE response)
def stations(fin):
    """Panel span stations from the lattice strip spacing."""
    lat = fin["lattice"]
    strip = np.array([s[0] for s in lat["strip"]])
    return 0.5 * (lat["ue"][strip] + lat["ue"][strip + 1]) - fin["lower"]


def axis(source):
    plane = source["fin_plane"]
    eu, ew = np.asarray(plane["e_u"], float), np.asarray(plane["e_w"], float)
    n = np.cross(ew, eu)
    n /= np.linalg.norm(n)
    return n if n[2] >= 0 else -n


def green(x, s, loads, EI):
    """Euler-Bernoulli cantilever under point loads at s: closed form w(x), w'(x)."""
    x, s = np.asarray(x, float)[:, None], np.asarray(s, float)[None, :]
    inboard = x <= s
    w = np.where(inboard, x**2 * (3 * s - x) / 6, s**2 * (3 * x - s) / 6)
    slope = np.where(inboard, x * (2 * s - x) / 2, s**2 / 2)
    return w @ loads / EI, slope @ loads / EI


def shape_validity(fin, loads, EI, gates):
    x = np.unique(np.r_[np.linspace(0, fin["length"], 513), stations(fin)])
    w, slope = green(x, stations(fin), loads, EI)
    tip, steep = abs(float(w[-1])) / fin["length"], float(np.max(abs(slope)))
    deepest = float(np.max(abs(w))) / fin["length"]
    return {
        "tip_over_L": tip,
        "max_slope_rad": steep,
        "max_sampled_deflection_over_span": deepest,
        "valid": tip <= gates["small_deflection_tip_over_span_max"]
        and steep <= gates["small_slope_max_rad"]
        and deepest <= gates["small_deflection_tip_over_span_max"],
    }


# ---------------------------------------------------------------- one arm
def audit_arm(ledger, path, result, p):
    """Saved-state reproduction of one returned arm; returns a short record."""
    g = p["gates"]
    name = path.name
    grid = result["actual_lattice"]
    fins = setup(grid["span"], grid["chord"])
    record = {
        "id": name,
        "status": result["status"],
        "iterations": len(result["iterations"]),
        "valid_for_declared_transfer": result["valid_for_declared_transfer"],
    }
    state_file = path / "static-states.npz"
    if digest(state_file) != result["static_state_artifact"]["sha256"]:
        ledger.find("identity", name, "static-states.npz hash differs from result.json")
    data = np.load(state_file, allow_pickle=False)
    if any(not np.isfinite(data[k]).all() for k in data.files):
        ledger.find("reproduction", name, "nonfinite saved static field")
    count = len(result["iterations"])
    if any(len(data[f + "__shape_load_N"]) != count for f in fins):
        ledger.find(
            "reproduction", name, "saved frame count differs from iteration count"
        )
        return record
    rho, speed = p["parameters"]["rho_kg_m3"], result["speed_m_s"]
    alpha = np.deg2rad(p["parameters"]["alpha_deg"])
    lift = np.array([-np.sin(alpha), 0, np.cos(alpha)])
    area = sum(f["source"]["area_flat_m2"] for f in fins.values())
    EI = result["EI_Nm2"]
    expected_EI = {
        f: p["parameters"]["EI_inputs"][f]["EI_Nm2_by_compliance"][
            str(result["compliance"])
        ]
        for f in fins
    }
    if EI != expected_EI:
        ledger.find("identity", name, "EI differs from the original protocol")
    last = count - 1
    for k, metric in enumerate(result["iterations"]):
        total = np.zeros(3)
        for f, fin in fins.items():
            load = data[f + "__shape_load_N"][k]
            force = data[f + "__aero_force_N"][k]
            total += force.sum(axis=0)
            n_ref = axis(fin["source"])
            ledger.compare(
                f"{name}.{k}.{f}.aero_load_normal",
                force @ n_ref,
                data[f + "__aero_load_normal_N"][k],
            )
            if k in (
                0,
                1,
                last,
            ):  # geometry: same-code rebuild, plus closed-form deflection
                lat = deform(fin, load, EI[f])
                for key, array in [
                    ("A", "lattice_A_m"),
                    ("B", "lattice_B_m"),
                    ("C", "lattice_C_m"),
                    ("N", "lattice_unit_normal"),
                ]:
                    ledger.compare(
                        f"{name}.{k}.{f}.{array}", lat[key], data[f + "__" + array][k]
                    )
                A = data[f + "__lattice_A_m"][k]
                u = (A - fin["geometry"]["O"]) @ fin["geometry"]["eu"] - fin["lower"]
                w_closed, _ = green(u, stations(fin), load, EI[f])
                ledger.compare(
                    f"{name}.{k}.{f}.closed_form_deflection",
                    w_closed,
                    (A - fin["lattice"]["A"]) @ n_ref,
                    scale=max(float(np.max(abs(w_closed))), 1e-30),
                )
                shape = shape_validity(fin, load, EI[f], g)
                stored = metric["shape_validity"][f]
                for key in [
                    "tip_over_L",
                    "max_slope_rad",
                    "max_sampled_deflection_over_span",
                ]:
                    ledger.compare(
                        f"{name}.{k}.{f}.{key}",
                        shape[key],
                        stored[key],
                        scale=max(abs(stored[key]), 1e-30),
                    )
                if shape["valid"] != stored["valid"]:
                    ledger.find(
                        "reproduction",
                        f"{name}.{k}.{f}",
                        "closed-form validity flag differs from native",
                    )
        ledger.compare(
            f"{name}.{k}.CL",
            float(total @ lift / (0.5 * rho * speed**2 * area)),
            metric["CL_on_fixed_source_area"],
        )
    arm = result["arm"]
    loads = {f: data[f + "__shape_load_N"] for f in fins}
    targets = {f: data[f + "__aero_load_normal_N"] for f in fins}
    if arm == "one-way-frozen-load" and count >= 2:
        for f in fins:
            ledger.compare(
                f"{name}.{f}.frozen_load_definition",
                loads[f][1],
                targets[f][0],
                scale=float(np.max(abs(targets[f][0]))),
            )
    if arm == "two-way-static-feedback":
        r = p["parameters"]["underrelaxation"]
        for f in fins:
            for k in range(count - 1):
                ledger.compare(
                    f"{name}.{k}.{f}.relaxation",
                    loads[f][k + 1],
                    (1 - r) * loads[f][k] + r * targets[f][k],
                    scale=float(np.max(abs(targets[f][k]))),
                )
        x = {f: np.linspace(0, fins[f]["length"], 129) for f in fins}
        residual = max(
            float(
                np.max(
                    abs(
                        green(
                            x[f],
                            stations(fins[f]),
                            targets[f][last] - loads[f][last],
                            EI[f],
                        )[0]
                    )
                )
            )
            / fins[f]["length"]
            for f in fins
        )
        stored = result["iterations"][last]["shape_residual_over_span"]
        ledger.compare(
            f"{name}.final_shape_residual", residual, stored, scale=max(stored, 1e-30)
        )
        if result["status"] == "converged static feedback" and not (
            stored <= g["fixed_point_shape_change_over_span_max"]
            and result["iterations"][last]["CL_change"]
            <= g["fixed_point_CL_absolute_change_max"]
        ):
            ledger.find(
                "reproduction",
                name,
                "converged status without both fixed-point tolerances met",
            )
    if result["status"].startswith("model-domain"):
        record["domain_exit"] = domain_exit(
            ledger, name, fins, result, loads, targets, EI, g
        )
    if count and result["valid_for_declared_transfer"]:
        lattices = {f: deform(fin, loads[f][last], EI[f]) for f, fin in fins.items()}
        _, unit, _, _ = vlm.solve(vlm.combine(lattices), p["parameters"]["alpha_deg"])
        stored = np.vstack([data[f + "__aero_force_N"][last] for f in fins])
        ledger.compare(
            f"{name}.final_pose_fresh_VLM_force", unit * rho * speed**2, stored
        )
        record["final_pose_resolved"] = True
    if result["flight"] is not None:
        record["flight"] = audit_flight(
            ledger, name, path, result, fins, loads, EI, area, p
        )
    elif result["valid_for_declared_transfer"]:
        ledger.find("reproduction", name, "valid arm without flight")
    return record


def domain_exit(ledger, name, fins, result, loads, targets, EI, g):
    """A native domain exit must be reproduced by the closed-form shape it names; it is never repaired."""
    last = len(result["iterations"]) - 1
    proposed = result["status"].endswith("proposed linear-beam shape")
    if proposed:
        shapes = {
            f: shape_validity(fin, targets[f][last], EI[f], g)
            for f, fin in fins.items()
        }
    elif last >= 0:
        shapes = {
            f: shape_validity(fin, loads[f][last], EI[f], g) for f, fin in fins.items()
        }
    else:
        shapes = {}
    exceeded = sorted(f for f, s in shapes.items() if not s["valid"])
    if proposed and not exceeded:
        ledger.find(
            "reproduction",
            name,
            "proposed-shape domain exit not reproduced by closed form",
        )
    if (
        not proposed
    ):  # the rejected current shape is not saved as a frame; record what is known
        ledger.find(
            "info",
            name,
            "linear-beam domain exit on a shape with no saved frame; closed form checks the last saved frame only",
        )
    return {
        "kind": "proposed" if proposed else "current",
        "fins_outside_domain": exceeded,
        "closed_form": shapes,
    }


def audit_flight(ledger, name, path, result, fins, loads, EI, area, p):
    f = p["glide"]
    flight = result["flight"]
    final_CL = result["iterations"][-1]["CL_on_fixed_source_area"]
    outline = np.vstack(
        [
            displaced(fin, np.asarray(fin["source"]["outline_m"]), loads[k][-1], EI[k])
            for k, fin in fins.items()
        ]
    )
    AR = float(np.ptp(outline[:, 1])) ** 2 / area
    ranges = []
    for label, dt in [("main", f["dt_s"]), ("half", f["half_dt_s"])]:
        meta = flight[label]
        for key, value in [
            ("CL_fixed", final_CL),
            ("reference_area_m2", area),
            ("mass_kg", f["mass_kg"]),
            ("dt_s", dt),
        ]:
            if meta[key] != value:
                ledger.find(
                    "reproduction",
                    f"{name}.glide-{label}.{key}",
                    f"{meta[key]} != {value}",
                )
        ledger.compare(f"{name}.glide-{label}.AR", AR, meta["AR"])
        series = np.load(path / f"glide-{label}.npz", allow_pickle=False)
        t, state = series["time_s"], series["state_x_h_V_gamma"]
        if not (
            np.isfinite(state).all()
            and t[0] == 0
            and np.all(np.diff(t) > 0)
            and len(t) == meta["actual_integrated_saved_states"]
        ):
            ledger.find(
                "reproduction", f"{name}.glide-{label}", "time/state identity invalid"
            )
            continue
        ledger.compare(f"{name}.glide-{label}.time_grid", t, np.arange(len(t)) * dt)
        energy = 0.5 * f["mass_kg"] * state[:, 2] ** 2 + f["mass_kg"] * G * state[:, 1]
        cd = glide.drag_coeff(final_CL, f["CD0"], f["oswald_e"], meta["AR"])
        ledger.compare(
            f"{name}.glide-{label}.energy", energy, series["mechanical_energy_J"]
        )
        ledger.compare(
            f"{name}.glide-{label}.drag_power",
            -0.5 * p["parameters"]["rho_kg_m3"] * state[:, 2] ** 3 * area * cd,
            series["drag_power_W"],
        )
        last_x, last_h = state[-1, 0], state[-1, 1]
        if not (meta["end_reason"] == 0 and meta["range_m"] >= last_x and last_h > 0):
            ledger.find(
                "reproduction",
                f"{name}.glide-{label}",
                "range is not a water-contact interpolation beyond the last saved state",
            )
        ranges.append(meta["range_m"])
    if len(ranges) == 2:
        ratio = abs(ranges[0] - ranges[1]) / max(abs(ranges[1]), 1e-12)
        ledger.compare(
            f"{name}.glide_dt_ratio",
            ratio,
            flight["range_relative_difference"],
            scale=max(ratio, 1e-30),
        )
        if (ratio <= f["range_relative_discrepancy_max"]) != flight["dt_gate_passed"]:
            ledger.find("reproduction", name, "dt gate flag differs")
    return {
        "range_main_m": flight["main"]["range_m"],
        "dt_gate_passed": flight["dt_gate_passed"],
    }


# ---------------------------------------------------------------- separate three-grid implementation
def three_grid(coarse, medium, fine, r, small):
    d1, d2 = medium - coarse, fine - medium
    if abs(d1) <= small and abs(d2) <= small:
        return "roundoff_insensitive", None, fine, small
    if d1 == 0 or not 0 < d2 / d1 < 1:
        return (
            ("oscillatory" if d1 != 0 and -1 < d2 / d1 < 0 else "divergent"),
            None,
            None,
            None,
        )
    order = -math.log(d2 / d1) / math.log(r)
    gain = r**order - 1
    return "monotone", order, fine + d2 / gain, 1.25 * abs(d2) / gain


def judge(series, floor, fp, tolerance):
    """Re-implementation of the frozen resolved / sign_resolved / not_resolved rule."""
    trip = {}
    for key, t in fp["triples"].items():
        a, b, c = (series[m] for m in t["lattices"])
        small = tolerance["absolute"] + tolerance["relative"] * max(abs(b), abs(c))
        trip[key] = three_grid(a, b, c, t["ratio"], small)
    v64, v32 = series["l64x16"], series["l32x8"]
    one_sign = np.all(np.array(list(series.values())) > 0) or np.all(
        np.array(list(series.values())) < 0
    )
    floor_ok = abs(v64) >= 10 * floor
    ok = all(x[0] in ("monotone", "roundoff_insensitive") for x in trip.values())
    if ok:
        ok = all(x[1] is None or 0.5 <= x[1] <= 4 for x in trip.values())
        ok = ok and trip["T2"][3] / max(abs(v64), 1e-300) <= 0.10
        ok = (
            ok
            and abs(trip["T2"][2] - trip["T1.5"][2]) <= trip["T2"][3] + trip["T1.5"][3]
        )
    if ok and one_sign and floor_ok:
        return "resolved", trip
    if one_sign and floor_ok and abs(v64) >= 3 * abs(v64 - v32):
        return "sign_resolved", trip
    return "not_resolved", trip


def recompute_effects(arms, fp, p, tolerance):
    """Paired effects and frozen decisions from raw arm results, compared later with summary.json."""
    names = p["parameters"]["arms"]
    out = {}
    for c in fp["selected_contexts"]:
        key = f"chi{c['compliance']}-u{c['speed_m_s']:g}"
        rows = {
            m: {a: arms.get(f"{key}-{m}-{a}") for a in names} for m in fp["lattices"]
        }
        if not all(
            x is not None and x.get("valid_for_declared_transfer")
            for g in rows.values()
            for x in g.values()
        ):
            out[key] = {"assessable": False}
            continue
        CL = {
            m: {a: g[a]["iterations"][-1]["CL_on_fixed_source_area"] for a in names}
            for m, g in rows.items()
        }
        bending = {m: CL[m][names[1]] - CL[m][names[0]] for m in CL}
        feedback = {m: CL[m][names[2]] - CL[m][names[1]] for m in CL}
        rigid = {m: CL[m][names[0]] for m in CL}

        def bound(arm):  # contraction bound from the stored residual history
            if arm["arm"] != names[2]:
                return 0.0
            h = [x["shape_residual_over_span"] for x in arm["iterations"]]
            pairs = list(itertools.pairwise(h))[
                -3:
            ]  # consecutive pairs, as the protocol states
            q = max((b / a for a, b in pairs if a > 0), default=math.inf)
            return (
                abs(arm["iterations"][-1]["CL_change"]) * q / (1 - q)
                if q < 1
                else math.inf
            )

        finest = rows["l64x16"]
        b_status, b_trip = judge(
            bending, bound(finest[names[0]]) + bound(finest[names[1]]), fp, tolerance
        )
        f_status, f_trip = judge(
            feedback, bound(finest[names[1]]) + bound(finest[names[2]]), fp, tolerance
        )
        r_status, r_trip = judge(rigid, 0.0, fp, tolerance)
        decision = {"bending": "undetermined", "feedback": "undetermined"}
        if b_status == "resolved":
            reference = (
                r_trip["T2"][2]
                if r_trip["T2"][0] in ("monotone", "roundoff_insensitive")
                else rigid["l64x16"]
            )
            size = abs(b_trip["T2"][2])
            decision["bending"] = (
                "retain_bending" if size / abs(reference) >= 0.01 else "reject_bending"
            )
            if f_status == "resolved":
                decision["feedback"] = (
                    "two_way_needed"
                    if abs(f_trip["T2"][2]) >= 0.10 * size
                    else "one_way_sufficient"
                )
            elif f_status == "sign_resolved":
                width = abs(feedback["l64x16"]) + abs(
                    feedback["l64x16"] - feedback["l32x8"]
                )
                decision["feedback"] = (
                    "one_way_sufficient" if width < 0.10 * size else "undetermined"
                )
        out[key] = {
            "assessable": True,
            "dCL_one_way_minus_rigid": b_status,
            "dCL_two_way_minus_one_way": f_status,
            "CL_rigid": r_status,
            "decision": decision,
            "series": {"bending": bending, "feedback": feedback},
        }
    return out


# ---------------------------------------------------------------- whole return
def audit(output, report, collection=None):
    output = Path(output)
    fa, fp, p = frozen(), json.loads((FID / "protocol.json").read_text()), protocol()
    ledger = Ledger(fa["tolerance"])
    identity = {}
    if collection is not None:
        try:
            manifest = read(collection)
            for ref in manifest["artifacts"]:
                local = Path(ref["local_path"])
                if (
                    not local.is_file()
                    or local.stat().st_size != ref["bytes"]
                    or digest(local) != ref["sha256"]
                ):
                    ledger.find(
                        "identity",
                        str(local),
                        "transport bytes differ from collection manifest",
                    )
            identity["collection_sha256"] = digest(collection)
        except (KeyError, TypeError, ValueError) as exc:
            ledger.find(
                "identity", str(collection), f"collection manifest unreadable: {exc}"
            )
    receipt = (
        read(output / "receipt.json") if (output / "receipt.json").is_file() else None
    )
    if receipt is None:
        ledger.find("identity", "receipt.json", "missing")
    else:
        identity |= {
            "receipt_sha256": digest(output / "receipt.json"),
            "native_failure": receipt["failure"],
            "environment": receipt["environment"],
            "wall_seconds": receipt["wall_seconds"],
            "output_bytes": receipt["output_bytes"],
            "output_cap_exceeded": receipt["output_cap_exceeded"],
        }
        if receipt["fidelity_protocol_sha256"] != fa["fidelity_protocol_sha256"]:
            ledger.find(
                "identity",
                "fidelity protocol",
                "executed protocol differs from the frozen one",
            )
        if receipt["original_protocol_sha256"] != fa["original_protocol_sha256"]:
            ledger.find(
                "identity", "original protocol", "executed physics protocol differs"
            )
        packet = {
            x["path"]: x["sha256"]
            for x in json.loads((FID / "packet.json").read_text())["files"]
        }
        for name, value in receipt["sources"].items():
            if packet.get(name) != value:
                ledger.find(
                    "identity", name, "executed source differs from the admitted packet"
                )
        if (receipt["environment"]["numpy"], receipt["environment"]["scipy"]) != (
            "2.5.4",
            "1.17.1",
        ):
            ledger.find("identity", "environment", "pinned versions not used")
        listed = {x["path"] for x in receipt["files"]}
        for ref in receipt["files"]:
            target = output / ref["path"]
            if (
                not target.is_file()
                or target.stat().st_size != ref["bytes"]
                or digest(target) != ref["sha256"]
            ):
                ledger.find(
                    "identity",
                    ref["path"],
                    "returned bytes differ from the native receipt",
                )
        for extra in sorted(
            str(x.relative_to(output)) for x in output.rglob("*") if x.is_file()
        ):
            if extra != "receipt.json" and extra not in listed:
                ledger.find("identity", extra, "file not listed in the native receipt")
    progress = {}
    for path in sorted((output / "progress").glob("*.json")):
        for row in read(path):
            progress[row["id"]] = row
    declared = [
        f"chi{c['compliance']}-u{c['speed_m_s']:g}-{m}-{a}"
        for c in fp["selected_contexts"]
        for m in fp["lattices"]
        for a in p["parameters"]["arms"]
    ]
    arms, records, statuses = {}, [], {}
    for name in declared:
        folder = output / "arms" / name
        row = progress.get(name)
        if (folder / "result.json").is_file():
            result = read(folder / "result.json")
            statuses[name] = result["status"]
            if row is not None and (
                row["status"] != result["status"]
                or row.get("iterations") != result["iterations"]
            ):
                ledger.find(
                    "reproduction", name, "progress row differs from result.json"
                )
            try:
                records.append(audit_arm(ledger, folder, result, p))
            except (
                Exception
            ) as exc:  # an unreadable arm is a finding, the audit goes on
                ledger.find(
                    "reproduction",
                    name,
                    f"arm could not be audited: {type(exc).__name__}: {exc}",
                )
                records.append(
                    {"id": name, "status": result["status"], "audit_error": str(exc)}
                )
            arms[name] = result
        elif (folder / "failure.json").is_file():
            failure = read(folder / "failure.json")
            statuses[name] = failure["status"]
            records.append(
                {"id": name, "status": failure["status"], "error": failure.get("error")}
            )
            ledger.find("native_failure", name, failure.get("error", failure["status"]))
        elif row is not None:
            statuses[name] = row["status"]
            records.append({"id": name, "status": row["status"]})
            ledger.find("native_incomplete", name, row["status"])
        else:
            statuses[name] = "missing"
            ledger.find("missing", name, "no result, failure or progress row")
    for name, status in statuses.items():
        if status.startswith(("model-domain", "unconverged", "partial", "not-started")):
            ledger.find(
                "native_" + status.split(":")[0].replace(" ", "_"), name, status
            )
    if (output / "task-failures.json").is_file():
        for row in read(output / "task-failures.json"):
            ledger.find("native_task_crash", row["task"], row["error"])
    controls = {}
    for mesh in fp["lattices"]:
        path = output / "lattice-controls" / f"{mesh}.json"
        if not path.is_file():
            ledger.find("missing", f"lattice-controls/{mesh}", "not returned")
            continue
        c = read(path)
        controls[mesh] = {
            "passed": c["passed"],
            "failed_checks": sorted(k for k, v in c["checks"].items() if not v),
        }
        if c["passed"] != all(c["checks"].values()):
            ledger.find(
                "reproduction",
                f"lattice-controls/{mesh}",
                "passed flag inconsistent with its checks",
            )
        if not c["passed"]:
            ledger.find(
                "native_control_failure",
                f"lattice-controls/{mesh}",
                controls[mesh]["failed_checks"],
            )
    if (output / "controls-original.json").is_file() and not read(
        output / "controls-original.json"
    )["passed"]:
        ledger.find(
            "native_control_failure", "controls-original", "original controls failed"
        )
    reproduction = []
    for item in fp["references"]:
        name = Path(item["path"]).parent.name
        ref, new = read(ROOT / item["path"]), arms.get(name)
        if new is None:
            reproduction.append({"id": name, "present": False})
            continue
        a = [x["CL_on_fixed_source_area"] for x in ref["iterations"]]
        b = [x["CL_on_fixed_source_area"] for x in new["iterations"]]
        same = ref["status"] == new["status"] and len(a) == len(b)
        ok = same and ledger.compare(f"reference.{name}.CL_history", b, a)
        if same and ref["flight"] and new["flight"]:
            ok &= ledger.compare(
                f"reference.{name}.range",
                [new["flight"][d]["range_m"] for d in ["main", "half"]],
                [ref["flight"][d]["range_m"] for d in ["main", "half"]],
            )
        reproduction.append(
            {
                "id": name,
                "present": True,
                "status_and_counts_equal": same,
                "within_roundoff": bool(ok),
                "exact": same and a == b,
            }
        )
    recomputed = recompute_effects(arms, fp, p, fa["tolerance"])
    native = (
        read(output / "summary.json") if (output / "summary.json").is_file() else None
    )
    agreement = []
    if native is None:
        ledger.find(
            "native_incomplete",
            "summary.json",
            "missing; effects recomputed from raw arms only",
        )
    else:
        for context in native["contexts"]:
            key = f"chi{context['compliance']}-u{context['speed_m_s']:g}"
            mine = recomputed[key]
            row = {
                "context": key,
                "assessable_agrees": mine["assessable"] == context["assessable"],
            }
            if mine["assessable"] and context["assessable"]:
                for effect in [
                    "dCL_one_way_minus_rigid",
                    "dCL_two_way_minus_one_way",
                    "CL_rigid",
                ]:
                    row[effect] = (mine[effect], context["effects"][effect]["status"])
                row["decision"] = (
                    mine["decision"],
                    {k: v["decision"] for k, v in context["decision"].items()},
                )
                if (
                    any(
                        a != b
                        for a, b in [
                            row[e]
                            for e in [
                                "dCL_one_way_minus_rigid",
                                "dCL_two_way_minus_one_way",
                                "CL_rigid",
                            ]
                        ]
                    )
                    or mine["decision"] != row["decision"][1]
                ):
                    ledger.find("analysis_disagreement", key, row)
            elif not row["assessable_agrees"]:
                ledger.find("analysis_disagreement", key, row)
            agreement.append(row)
    blocking = {"identity", "reproduction", "analysis_disagreement", "missing"}
    result = {
        "schema": "frontier.aeroelastic.fidelity-return-audit/1",
        "audit_protocol_sha256": digest(FID / "return-audit-protocol.json"),
        "audit_code_sha256": digest(Path(__file__)),
        "output_dir": str(output),
        "identity": identity,
        "declared_arms": len(declared),
        "native_statuses": statuses,
        "arms": records,
        "lattice_controls": controls,
        "reproduction_of_a54f478": reproduction,
        "recomputed_effects_and_decisions": recomputed,
        "agreement_with_native_summary": agreement,
        "findings": ledger.findings,
        "finding_counts": {
            k: sum(x["kind"] == k for x in ledger.findings)
            for k in sorted({x["kind"] for x in ledger.findings})
        },
        "comparisons": {
            "count": len(ledger.comparisons),
            "exact": sum(x["exact"] for x in ledger.comparisons),
            "within_roundoff": sum(x["within_roundoff"] for x in ledger.comparisons),
            "worst": sorted(ledger.comparisons, key=lambda x: -x["max_abs_difference"])[
                :20
            ],
        },
        "audit_passed": not any(x["kind"] in blocking for x in ledger.findings),
        "scope": fa["scope"],
    }
    dump(Path(report), result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collection", type=Path)
    args = parser.parse_args()
    r = audit(args.output, args.report, args.collection)
    print(
        {k: r[k] for k in ["audit_passed", "finding_counts", "declared_arms"]}
        | {"comparisons": r["comparisons"]["count"]}
    )
    raise SystemExit(0 if r["audit_passed"] else 1)
