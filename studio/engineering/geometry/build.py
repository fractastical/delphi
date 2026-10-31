"""Build every printable form, its stand, its checks and its receipts into artifacts/print/.

    python -m engineering.geometry.build [--out artifacts/print] [--solver-repo .] [--skip-thickness]

Run under a capped scope, e.g.
    systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 ...
Output is deterministic for a given code hash, solver blob and library versions (no timestamps written).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

import manifold3d as mf
import numpy as np

from . import forms as F
from . import graph, render, solver_bridge as SB, stand as ST, validate as VAL, viewer
from .mesh import Resolution

HERE = Path(__file__).resolve().parent
LAUNCH_SPEED = Fraction(16)  # m/s; lower end of the 16-20 m/s take-off speed Fish 1990 p.397 relays
RESOLUTIONS = {"coarse": Resolution(36, 24, 24, 16), "default": Resolution(), "fine": Resolution(144, 96, 96, 64)}
BOX_MM = 120.0
CONVERGENCE_TOL = 0.01  # relative volume / extent change default -> fine


def code_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(HERE.glob("*.py")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def library_versions() -> dict:
    import importlib.metadata as md
    out = {}
    for pkg in ("manifold3d", "numpy", "matplotlib", "trimesh", "z3-solver"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def wjson(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def glide_receipt(out: Path, form_id: str, candidate_path: Path | None) -> dict:
    """Attach NCA's receipt only if it names this exact candidate and reports a converged run."""
    rp = out / "glide" / f"{form_id}.receipt.json"
    if candidate_path is None:
        return {"status": "not_applicable", "reason": "solver did not return feasible; the simulator refuses it"}
    if not rp.exists():
        return {"status": "not_run", "expected_path": str(rp.relative_to(out.parent.parent)),
                "candidate_sha256": sha(candidate_path)}
    r = json.loads(rp.read_text())
    cand = r.get("inputs", {}).get("candidate_sha256")
    ok = cand in (sha(candidate_path), SB.canonical_sha256(json.loads(candidate_path.read_text())))
    return {"status": "attached" if ok else "mismatch", "receipt_sha256": sha(rp), "verdict": r.get("verdict"),
            "converged": r.get("numerics", {}).get("converged"), "results": r.get("results"),
            "candidate_sha256_matches": ok}


def mesh_arrays(m: mf.Manifold):
    """Double-precision mesh, welded at float32 so the STL (float32 by format) has no coincident vertices."""
    mesh = m.to_mesh64()
    V = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    T = np.asarray(mesh.tri_verts).astype(np.int64)
    V, T, info = VAL.weld_float32(V, T)
    return V, T, info


def convergence(spec, bio, scale) -> dict:
    rows = {}
    for name, res in RESOLUTIONS.items():
        m, rep = F.build_prop(spec, bio, scale, res)
        bb = m.bounding_box()
        rows[name] = {"triangles": m.num_tri(), "volume_mm3": m.volume(), "surface_mm2": m.surface_area(),
                      "extent_mm": [bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]],
                      "body_loft_volume_mm3": rep["body_loft_volume_mm3"]}
    d, f = rows["default"], rows["fine"]
    rel_v = abs(d["volume_mm3"] - f["volume_mm3"]) / f["volume_mm3"]
    rel_e = max(abs(a - b) / b for a, b in zip(d["extent_mm"], f["extent_mm"]))
    return {"resolutions": {k: vars(v) for k, v in RESOLUTIONS.items()}, "rows": rows,
            "default_vs_fine_rel_volume": rel_v, "default_vs_fine_rel_extent": rel_e,
            "tolerance": CONVERGENCE_TOL, "converged": bool(rel_v < CONVERGENCE_TOL and rel_e < CONVERGENCE_TOL)}


def b64(a: np.ndarray, dtype) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/print")
    ap.add_argument("--solver-repo", default=".")
    ap.add_argument("--solver-rev", default=SB.GUILDS_COMMIT)
    ap.add_argument("--skip-thickness", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    for d in ("design", "solver", "glide", "stl", "web", "img"):
        (out / d).mkdir(parents=True, exist_ok=True)

    mod, solver_prov = SB.load_solver(Path(a.solver_repo), a.solver_rev)
    run = {"code_sha256": code_hash(), "libraries": library_versions(), "solver": solver_prov,
           "launch_speed_query_m_s": str(LAUNCH_SPEED), "box_mm": BOX_MM}

    bios = F.complete_all()
    scale = F.display_scale([F.built_extents(s, b) for s, b in zip(F.FORMS, bios)])
    manifest = {"schema": "frontier.print.manifest/1", "run": run, "display_scale": scale,
                "display_scale_note": "one scale for all forms (same 0.1 kg biological mass), so sizes compare",
                "label": F.LABEL, "forms": {}, "files": {}}
    viewer_designs, viewer_meshes = [], []

    for spec, bio in zip(F.FORMS, bios):
        # 1. solver judges the biological design point
        m_, S_, b_ = (SB.rational(bio["mass_kg"]["value"]), SB.rational(bio["wing_area_m2"]["value"]),
                      SB.rational(bio["wing_span_m"]["value"]))
        srun = SB.solve_point(mod, m_, S_, b_, LAUNCH_SPEED)
        srun["solver"] = solver_prov
        sp = out / "solver" / f"{spec.id}.solver.json"
        wjson(sp, srun)
        cand = SB.glide_candidate(srun)
        cp = None
        if cand is not None:
            cp = out / "glide" / f"{spec.id}.candidate.json"
            wjson(cp, cand)
        glide = glide_receipt(out, spec.id, cp)
        status = srun["default"]["status"]
        # geometry consumes the solver's exact witness when feasible, else the query point it rejected
        point = srun["default"]["witness"] or srun["query"]
        for key, sym in (("mass_kg", "m"), ("wing_area_m2", "S"), ("wing_span_m", "b")):
            bio[key]["value"] = float(Fraction(point[sym]))
            bio[key]["solver_exact"] = point[sym]
        if spec.fins_from == "fish_fit":  # re-lay the fins on the exact solver values
            bio["fin_layout_bio"]["value"] = F.fin_layout(spec, bio)

        # 2. prop solid, convergence, checks, files
        conv = convergence(spec, bio, scale)
        solid, built = F.build_prop(spec, bio, scale)
        V, T, weld = mesh_arrays(solid)
        checks = VAL.check(V, T, BOX_MM, thickness=not a.skip_thickness)
        checks["float32_weld"] = weld
        stl = VAL.stl_bytes(V, T, f"Delphi Frontier print form {spec.id}, units mm")
        stl_path = out / "stl" / f"{spec.id}.stl"
        stl_path.write_bytes(stl)
        V2, T2 = VAL.read_stl(stl)
        roundtrip = VAL.check(V2, T2, BOX_MM, thickness=False)
        hw_at, bottom_at = F.body_section_mm(spec, bio, scale)
        stand_m, stand_info = ST.build_stand(solid, V, T, hw_at, bottom_at)
        SV, STt, sweld = mesh_arrays(stand_m)
        stand_checks = VAL.check(SV, STt, BOX_MM, thickness=not a.skip_thickness)
        stand_checks["float32_weld"] = sweld
        stand_path = out / "stl" / f"{spec.id}-stand.stl"
        stand_path.write_bytes(VAL.stl_bytes(SV, STt, f"Delphi Frontier stand for {spec.id}, units mm"))
        inter = (solid ^ stand_m).volume()
        glb_path = out / "web" / f"{spec.id}.glb"
        try:
            import trimesh
            glb_path.write_bytes(trimesh.Trimesh(V, T, process=False).export(file_type="glb"))
        except ImportError:
            glb_path = None
        img = out / "img" / f"{spec.id}.png"
        render.render([(V, T, (0.32, 0.55, 0.78))], img, spec.title)
        img_s = out / "img" / f"{spec.id}-on-stand.png"
        render.render([(V, T, (0.32, 0.55, 0.78)), (SV, STt, (0.7, 0.7, 0.66))], img_s, spec.title + " (on stand)")

        k = 1000 * scale
        design = {
            "schema": "frontier.print.design/1", "id": spec.id, "title": spec.title, "role": spec.role,
            "label": F.LABEL, "status_note": spec.status_note or None,
            "engineering_status": {
                "solver": status,
                "solver_conflict": srun["default"]["conflict"],
                "meaning": {"feasible": "an exact point satisfies the declared constraints in guilds' model; "
                                        "not organism feasibility",
                            "unsat": "the declared constraints conflict at this point (named); this form is shown "
                                     "as a rejected candidate",
                            "unknown": "not decided"}[status],
                "glide": glide,
                "may_not_say": ["feasible organism", "viable", "evolutionarily reachable", "ancestor",
                                "flight-tested", "aerodynamically faithful"],
            },
            "biological_design_SI": bio,
            "solver_run": {"path": str(sp.relative_to(out)), "sha256": sha(sp)},
            "glide_candidate": {"path": str(cp.relative_to(out)), "sha256": sha(cp)} if cp else None,
            "aesthetic_and_shape_parameters": spec.params,
            "print_parameters": F.PRINT,
            "prop_mm": {
                "display_scale": scale, "display_scale_meaning": f"1 m biological = {k:.0f} mm prop",
                "built": built,
                "fin_thickness_exaggeration": {
                    "prop_mm": F.PRINT["fin_thickness_mm"]["value"],
                    "equivalent_biological_mm": F.PRINT["fin_thickness_mm"]["value"] / scale,
                    "note": "fins are not biological thickness; the plate is a print choice"},
                "resin": "prop volume is reported in mm^3; resin mass and print time come only from the slicer "
                         "for the chosen printer and resin",
                "biological_mass_kg": bio["mass_kg"]["value"],
            },
            "convergence": conv,
            "validation": checks,
            "stl_roundtrip": {k2: roundtrip[k2] for k2 in ("ok", "triangles", "closed_two_manifold",
                                                            "consistently_oriented", "face_connected_components",
                                                            "signed_volume_mm3", "mesh_sha256")},
            "files": {"stl": {"path": str(stl_path.relative_to(out)), "sha256": sha(stl_path)},
                      "glb": {"path": str(glb_path.relative_to(out)), "sha256": sha(glb_path)} if glb_path else None,
                      "image": {"path": str(img.relative_to(out)), "sha256": sha(img)},
                      "image_on_stand": {"path": str(img_s.relative_to(out)), "sha256": sha(img_s)}},
            "stand": {"stl": {"path": str(stand_path.relative_to(out)), "sha256": sha(stand_path)},
                      "validation": stand_checks, "placement": stand_info,
                      "assembly_overlap_mm3": inter,
                      "note": "separate part; it sits under the prop and is printed on its own"},
            "not_checked": ["global self-intersection", "slicing", "supports / minima / cups (orientation-dependent)",
                            "resin-specific thin-wall limit", "aerodynamics of the prop", "physical print"],
            "run": run,
        }
        dp = out / "design" / f"{spec.id}.json"
        wjson(dp, design)
        manifest["forms"][spec.id] = {
            "design": str(dp.relative_to(out)), "solver": status, "glide": glide["status"],
            "valid": checks["ok"], "stand_valid": stand_checks["ok"], "converged": conv["converged"],
            "bounds_mm": checks["bounds_mm"]["size"], "volume_mm3": checks["signed_volume_mm3"],
            "mesh_sha256": checks["mesh_sha256"], "stl_sha256": sha(stl_path)}
        viewer_designs.append(design)
        viewer_meshes.append({"v": b64(V, "<f4"), "t": b64(T, "<u4"), "sv": b64(SV, "<f4"), "st": b64(STt, "<u4")})

    gj = graph.graph_json()
    wjson(out / "species-graph.json", gj)
    graph.render_graph(out / "img" / "species-graph.png")
    (out / "viewer.html").write_text(viewer.page(viewer_designs, viewer_meshes,
                                                  (out / "img" / "species-graph.png").read_bytes(), F.LABEL, run, scale))
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            manifest["files"][str(p.relative_to(out))] = sha(p)
    wjson(out / "manifest.json", manifest)
    lo_mm, hi_mm = F.PRINT["min_length_mm"]["value"], BOX_MM
    bad = [k for k, v in manifest["forms"].items() if not (v["valid"] and v["stand_valid"] and v["converged"]
                                                           and lo_mm <= v["bounds_mm"][0] <= hi_mm)]
    print(json.dumps({k: {kk: v[kk] for kk in ("solver", "glide", "valid", "stand_valid", "converged", "bounds_mm",
                                                "volume_mm3", "mesh_sha256")} for k, v in manifest["forms"].items()},
                     indent=1))
    print("display_scale", scale, "code_sha256", run["code_sha256"])
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
