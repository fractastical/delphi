"""Existing beam FEM responses coupled to actual deformed VLM lifting surfaces."""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from engineering.cfd3d import vlm
from engineering.fin_mechanics import beam

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/aeroelastic"
GEOM = ROOT / "artifacts/fish3d/fish3d-v3a-fan"


def protocol():
    return json.loads((ART / "protocol.json").read_text())


def dump(path, value):
    def scalar(x):
        if isinstance(x, np.generic):
            return x.item()
        raise TypeError(type(x).__name__)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=scalar) + "\n"
    )
    temporary.replace(path)


def check_inputs():
    for item in protocol()["inputs"]:
        raw = (ROOT / item["path"]).read_bytes()
        if len(raw) != item["bytes"] or sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Frozen geometry/aero input changed")


class Response:
    """Point-load superposition using the unchanged existing Hermite FEM solver.

    A tip force at station a bends [0,a]; [a,L] is unloaded and extends linearly.
    One cubic element represents each constant-EI tip-loaded subproblem exactly.
    """

    def __init__(self, length, stations, n_el=1):
        self.length = float(length)
        self.stations = np.asarray(stations)
        if np.any(self.stations < 0) or np.any(self.stations > length):
            raise ValueError("Load station outside beam")
        self.solutions = [
            beam.solve_cantilever(float(a), 1.0, tip_force=1.0, n_el=n_el)
            if a > 1e-12
            else None
            for a in self.stations
        ]
        self.cache = {}

    def matrix(self, locations):
        x = np.asarray(locations, dtype=float)
        tolerance = protocol()["gates"]["coordinate_roundoff_tolerance_m"]
        if (
            not np.isfinite(x).all()
            or x.min() < -tolerance
            or x.max() > self.length + tolerance
        ):
            raise ValueError("Shape query outside source beam domain")
        x = np.clip(x, 0, self.length)
        key = x.tobytes()
        if key not in self.cache:
            w, theta = [], []
            for a, solution in zip(self.stations, self.solutions, strict=True):
                if solution is None:
                    w.append(np.zeros_like(x))
                    theta.append(np.zeros_like(x))
                    continue
                displacement, slope = solution.evaluate(np.minimum(x, a))
                displacement += np.maximum(x - a, 0) * solution.theta[-1]
                w.append(displacement)
                theta.append(slope)
            self.cache[key] = (np.asarray(w).T, np.asarray(theta).T)
        return self.cache[key]

    def evaluate(self, locations, normal_forces, EI):
        if not np.isfinite(EI) or EI <= 0:
            raise ValueError("EI must be finite and positive")
        forces = np.asarray(normal_forces)
        if forces.shape != self.stations.shape or not np.isfinite(forces).all():
            raise ValueError("Invalid normal-force vector")
        w, slope = self.matrix(locations)
        return w @ forces / EI, slope @ forces / EI


@lru_cache(maxsize=4)
def setup(ns, nc):
    fins = json.loads((GEOM / "panels.json").read_text())["fins"]
    result = {}
    for name in vlm.PAIRED:
        source = fins[name]
        lat, geo = vlm.fin_setup(source, ns, nc)
        u = (np.asarray(source["outline_m"]) - geo["O"]) @ geo["eu"]
        lower, upper = float(u.min()), float(u.max())
        load_positions = ((lat["A"] + lat["B"]) / 2 - geo["O"]) @ geo["eu"] - lower
        result[name] = {
            "source": source,
            "lattice": lat,
            "geometry": geo,
            "lower": lower,
            "length": upper - lower,
            "response": Response(upper - lower, load_positions),
        }
    return result


def span(fin, points):
    return (np.asarray(points) - fin["geometry"]["O"]) @ fin["geometry"]["eu"] - fin[
        "lower"
    ]


def displaced(fin, points, forces, EI):
    points = np.asarray(points)
    shape = points.shape
    flat = points.reshape(-1, 3)
    w, _ = fin["response"].evaluate(span(fin, flat), forces, EI)
    return (flat + w[:, None] * fin["geometry"]["n_up"]).reshape(shape)


def deform(fin, forces, EI):
    source = fin["lattice"]
    result = {
        key: value.copy() if isinstance(value, np.ndarray) else value
        for key, value in source.items()
    }
    for key in ["A", "B", "C"]:
        result[key] = displaced(fin, source[key], forces, EI)
    _, slope = fin["response"].evaluate(span(fin, source["C"]), forces, EI)
    geo = fin["geometry"]
    normals = source["N"] - (slope * (source["N"] @ geo["n_up"]))[:, None] * geo["eu"]
    norms = np.linalg.norm(normals, axis=1)
    if np.any(norms < 1e-12):
        raise ValueError("Degenerate transformed normals")
    result["N"] = normals / norms[:, None]
    uw = source["uw"]
    corners = geo["O"] + uw[..., 0, None] * geo["eu"] + uw[..., 1, None] * geo["ew"]
    corners = displaced(fin, corners, forces, EI)
    result["area"] = (
        np.linalg.norm(
            np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]),
            axis=1,
        )
        + np.linalg.norm(
            np.cross(corners[:, 2] - corners[:, 0], corners[:, 3] - corners[:, 0]),
            axis=1,
        )
    ) / 2
    validate_lattice(result)
    return result


def validate_lattice(lat):
    g = protocol()["gates"]
    if any(not np.isfinite(lat[k]).all() for k in ["A", "B", "C", "N", "area"]):
        raise ValueError("Nonfinite lattice")
    if np.any(lat["area"] <= g["minimum_cell_area_m2"]):
        raise ValueError("Degenerate lattice area")
    if np.max(abs(np.linalg.norm(lat["N"], axis=1) - 1)) > g["normal_unit_error_max"]:
        raise ValueError("Lattice normal is not unit")
    if np.any(np.linalg.norm(lat["B"] - lat["A"], axis=1) <= 1e-10):
        raise ValueError("Degenerate bound segment")


def transfer(fin, lattice, full_forces, supplied_normal_forces=None):
    geo = fin["geometry"]
    n = geo["n_up"]
    eu = geo["eu"]
    original_normal = full_forces @ n
    normal = (
        original_normal if supplied_normal_forces is None else supplied_normal_forces
    )
    positions = (lattice["A"] + lattice["B"]) / 2
    root = geo["O"] + fin["lower"] * eu
    s = fin["response"].stations
    total_force = full_forces.sum(axis=0)
    total_moment = np.cross(positions - root, full_forces).sum(axis=0)
    constrained_force = (full_forces - original_normal[:, None] * n).sum(axis=0)
    constrained_moment = total_moment - np.sum(s * original_normal) * np.cross(eu, n)
    force_residual = normal.sum() * n + constrained_force - total_force
    moment_residual = (
        np.sum(s * normal) * np.cross(eu, n) + constrained_moment - total_moment
    )
    gross = max(float(np.linalg.norm(full_forces, axis=1).sum()), 1e-30)
    virtual_w = 0.001 * (s / fin["length"]) ** 2 + 0.002 * (s / fin["length"]) ** 3
    actual_work = float(np.sum((full_forces @ n) * virtual_w))
    mapped_work = float(normal @ virtual_w)
    result = {
        "force_relative_residual": float(np.linalg.norm(force_residual) / gross),
        "moment_relative_residual": float(
            np.linalg.norm(moment_residual) / (gross * fin["length"])
        ),
        "virtual_work_relative_residual": abs(actual_work - mapped_work)
        / max(float(np.sum(abs((full_forces @ n) * virtual_w))), 1e-30),
        "total_force_world_N": total_force.tolist(),
        "total_moment_root_world_Nm": total_moment.tolist(),
        "constraint_force_world_N": constrained_force.tolist(),
        "constraint_moment_root_world_Nm": constrained_moment.tolist(),
        "constraint_scope": "Tangential/axial and torsional/chordwise reactions are retained; finite torsional compliance is NOT modeled",
    }
    g = protocol()["gates"]
    result["passed"] = (
        result["force_relative_residual"] <= g["transfer_force_relative_max"]
        and result["moment_relative_residual"] <= g["transfer_moment_relative_max"]
        and result["virtual_work_relative_residual"] <= g["virtual_work_relative_max"]
    )
    return original_normal, result
