"""Build every printable form, its stand, its checks and its receipts into artifacts/print/.

    python -m engineering.geometry.build [--edition v1|v2] [--out DIR] [--solver-repo .] [--skip-thickness]

One edition per output directory: v1 (default) -> artifacts/print, the published sets with their frozen body-profile
defect; v2 -> artifacts/print-v2, the same forms under new ids with the corrected profile (forms.FORMS_V2).

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
from . import graph, nca_link as NCA, render, solver_bridge as SB, stand as ST, validate as VAL, viewer
from .mesh import Resolution

HERE = Path(__file__).resolve().parent
LAUNCH_SPEED = Fraction(16)  # m/s; lower end of the 16-20 m/s take-off speed Fish 1990 p.397 relays
RESOLUTIONS = {"coarse": Resolution(36, 24, 24, 16), "default": Resolution(), "fine": Resolution(144, 96, 96, 64)}
BOX_MM = 120.0
MIN_WALL_MM = 1.0  # provisional prop choice (brief: walls >= ~1 mm), not a certified printer setting
PRINTER_RESIN = {"printer": "unknown", "resin": "unknown", "layer_height": "unknown",
                 "note": "not chosen by the user yet; Formlabs minimums read here are stated for Form 2, Clear, "
                         "100 um and are not assumed to apply; run the docs/printing.md checklist in PreForm"}
CONVERGENCE_TOL = 0.01  # relative volume / extent change default -> fine


def code_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(HERE.glob("*.py")):
        if p.name == "turntable.py":  # media only; it reads the build's outputs and has its own code hash
            continue
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
    ap.add_argument("--edition", choices=sorted(F.EDITIONS), default="v1")
    ap.add_argument("--out", default=None, help="default: artifacts/print (v1) or artifacts/print-<edition>")
    ap.add_argument("--solver-repo", default=".")
    ap.add_argument("--solver-rev", default=SB.GUILDS_COMMIT)
    ap.add_argument("--nca-repo", default=None, help="clone holding dx-nca's commit (default: --solver-repo)")
    ap.add_argument("--skip-thickness", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out or ("artifacts/print" if a.edition == "v1" else f"artifacts/print-{a.edition}")).resolve()
    forms = F.EDITIONS[a.edition]
    for d in ("design", "solver", "glide", "stl", "web", "img"):
        (out / d).mkdir(parents=True, exist_ok=True)

    mod, solver_prov = SB.load_solver(Path(a.solver_repo), a.solver_rev)
    run = {"code_sha256": code_hash(), "libraries": library_versions(), "solver": solver_prov,
           "launch_speed_query_m_s": str(LAUNCH_SPEED), "box_mm": BOX_MM}

    bios = F.complete_all(forms)
    sets = {}
    for sid, meta in F.SETS.items():
        members = [(s, b) for s, b in zip(forms, bios) if s.set_id == sid]
        if not members:
            continue
        sc, aim = F.display_scale(members)
        sets[sid] = {"title": meta["title"], "note": meta["note"], "display_scale": sc, "length_aim": aim,
                     "forms": [s.id for s, _ in members]}
        if "supersedes" in meta:
            sets[sid]["supersedes"] = meta["supersedes"]
    manifest = {"schema": "frontier.print.manifest/2", "run": run, "sets": sets,
                "display_scale_note": "one scale per set, so sizes compare within a set; sets have different masses",
                "printer_resin": PRINTER_RESIN, "label": F.LABEL, "forms": {}, "files": {}}
    if a.edition != "v1":
        manifest["edition"] = {"id": a.edition, "body_profile": sorted({f.body_profile for f in forms}),
                               "supersedes": {f.id: v1.id for f, v1 in zip(forms, F.FORMS)},
                               "v1_directory": "artifacts/print", "note": F.V2_NOTE}
    viewer_designs, viewer_meshes = [], []
    nca_repo = Path(a.nca_repo or a.solver_repo)

    for spec, bio in zip(forms, bios):
        scale = sets[spec.set_id]["display_scale"]
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
        checks = VAL.check(V, T, BOX_MM, thickness=not a.skip_thickness, min_wall_mm=MIN_WALL_MM)
        checks["float32_weld"] = weld
        stl = VAL.stl_bytes(V, T, f"Delphi Frontier print form {spec.id}, units mm")
        stl_path = out / "stl" / f"{spec.id}.stl"
        stl_path.write_bytes(stl)
        V2, T2 = VAL.read_stl(stl)
        roundtrip = VAL.check(V2, T2, BOX_MM, thickness=False)
        hw_at, bottom_at = F.body_section_mm(spec, bio, scale)
        stand_m, stand_info = ST.build_stand(solid, V, T, hw_at, bottom_at)
        SV, STt, sweld = mesh_arrays(stand_m)
        stand_checks = VAL.check(SV, STt, BOX_MM, thickness=not a.skip_thickness, min_wall_mm=MIN_WALL_MM)
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

        sim = None
        if spec.wing_factors is not None:
            sim = NCA.controlled_rows(nca_repo, spec.genus, spec.mass_kg, *spec.wing_factors,
                                      bio["wing_area_m2"]["value"], bio["wing_span_m"]["value"])
        k = 1000 * scale
        design = {
            "schema": "frontier.print.design/2", "id": spec.id, "title": spec.title, "short": spec.short,
            "role": spec.role, "set": {"id": spec.set_id, **{kk: sets[spec.set_id][kk] for kk in ("title", "note")}},
            "label": F.LABEL, "status_note": spec.status_note or None, "printer_resin": PRINTER_RESIN,
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
            "simulation_comparison": sim,
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
            "set": spec.set_id, "display_scale": scale,
            "design": str(dp.relative_to(out)), "solver": status, "glide": glide["status"],
            "simulation_comparison": None if sim is None else {"evidence_kind": sim["evidence_kind"],
                                                               "commit": sim["commit"], "rows": len(sim["rows"]),
                                                               "geometry_matches": sim["geometry_matches"]},
            "valid": checks["ok"], "stand_valid": stand_checks["ok"], "converged": conv["converged"],
            "bounds_mm": checks["bounds_mm"]["size"], "volume_mm3": checks["signed_volume_mm3"],
            "mesh_sha256": checks["mesh_sha256"], "stl_sha256": sha(stl_path)}
        viewer_designs.append(design)
        viewer_meshes.append({"v": b64(V, "<f4"), "t": b64(T, "<u4"), "sv": b64(SV, "<f4"), "st": b64(STt, "<u4")})

    gj = graph.graph_json()
    wjson(out / "species-graph.json", gj)
    graph.render_graph(out / "img" / "species-graph.png")
    (out / "viewer.html").write_text(viewer.page(viewer_designs, viewer_meshes,
                                                  (out / "img" / "species-graph.png").read_bytes(), F.LABEL, run, sets))
    wjson(out / "downloads.json", downloads(out, viewer_designs, sets, run))
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json" and p.relative_to(out).parts[0] != "media":
            manifest["files"][str(p.relative_to(out))] = sha(p)
    wjson(out / "manifest.json", manifest)
    bad = [k for k, v in manifest["forms"].items() if not form_passes(v, sets[v["set"]]["length_aim"])]
    print(json.dumps({k: {kk: v[kk] for kk in ("set", "solver", "glide", "valid", "stand_valid", "converged",
                                                "bounds_mm", "volume_mm3", "mesh_sha256")}
                      for k, v in manifest["forms"].items()}, indent=1))
    print("scales", {k: v["display_scale"] for k, v in sets.items()}, "code_sha256", run["code_sha256"])
    print("FAILED:", bad) if bad else None
    return 1 if bad else 0


def form_passes(row: dict, aim: dict) -> bool:
    """Valid prop and stand, converged, inside the box; at least min_length_mm long whenever a listed scale met
    the set's length aim (a set where none did carries the reason in the manifest and fails nothing silently)."""
    length = row["bounds_mm"][0]
    length_ok = length >= aim["min_length_mm"] if aim["met"] else True
    return bool(row["valid"] and row["stand_valid"] and row["converged"] and length <= BOX_MM and length_ok)


def _check_summary(v: dict) -> dict:
    w = v.get("wall_thickness") or {}
    return {"ok": v["ok"], "closed_two_manifold": v["closed_two_manifold"],
            "consistently_oriented": v["consistently_oriented"],
            "face_connected_components": v["face_connected_components"],
            "degenerate_triangles": v["degenerate_triangles"], "signed_volume_mm3": v["signed_volume_mm3"],
            "genus": v["genus"], "fits_box_mm": v["fits_box_mm"], "fits_box": v["fits_box"],
            "min_wall_mm_required": v.get("min_wall_mm_required"), "min_wall_ok": v.get("min_wall_ok"),
            "min_sampled_wall_mm": w.get("min_mm"), "wall_samples": w.get("samples"),
            "min_wall_scope": v.get("min_wall_scope"), "self_intersection": v["self_intersection"],
            "mesh_sha256": v["mesh_sha256"]}


def _base(out: Path) -> str:
    try:
        return f"{out.relative_to(HERE.parents[1]).as_posix()}/"
    except ValueError:
        return f"{out.as_posix()}/"


def downloads(out: Path, designs: list[dict], sets: dict, run: dict) -> dict:
    """What a site may offer for download: every file with size and sha256, the mesh checks it passed, and the
    limits that travel with it.  Paths are relative to `base` (the output directory, e.g. artifacts/print/)."""
    def entry(kind, rel, units=None):
        p = out / rel
        e = {"kind": kind, "path": rel, "bytes": p.stat().st_size, "sha256": sha(p)}
        return {**e, "units": units} if units else e
    forms = []
    for d in designs:
        f = d["files"]
        forms.append({
            "id": d["id"], "short": d["short"], "title": d["title"], "set": d["set"]["id"], "label": d["label"],
            "solver": d["engineering_status"]["solver"], "glide_sim": d["engineering_status"]["glide"]["status"],
            "simulation_comparison": None if d["simulation_comparison"] is None else
            {"evidence_kind": "simulated", "commit": d["simulation_comparison"]["commit"],
             "path": d["simulation_comparison"]["path"]},
            "display_scale": d["prop_mm"]["display_scale"], "biological_mass_kg": d["prop_mm"]["biological_mass_kg"],
            "prop_size_mm": d["validation"]["bounds_mm"]["size"],
            "files": [entry("stl_prop", f["stl"]["path"], "mm"), entry("stl_stand", d["stand"]["stl"]["path"], "mm"),
                      entry("glb_prop", f["glb"]["path"], "mm"), entry("png_prop", f["image"]["path"]),
                      entry("png_on_stand", f["image_on_stand"]["path"]),
                      entry("design_json", f"design/{d['id']}.json")],
            "prop_checks": _check_summary(d["validation"]),
            "stand_checks": _check_summary(d["stand"]["validation"]),
        })
    return {"schema": "frontier.print.downloads/1", "code_sha256": run["code_sha256"], "base": _base(out),
            "sets": sets, "printer_resin": PRINTER_RESIN, "forms": forms,
            "viewer": entry("html_viewer", "viewer.html"),
            "limitations": [
                "Printer and resin are unknown; nothing has been sliced, loaded into PreForm or printed.",
                "Minimum wall (>= 1.0 mm, our provisional prop choice, not a certified setting) is checked on "
                "sampled faces only; a thinner region between samples can be missed.",
                "Closed, oriented, single-component manifold, positive volume and box fit are checked on every "
                "file; global self-intersection is not checked.",
                "Fins are thickened print plates, not biological thickness; no aerodynamic fidelity is claimed.",
                "Engineered illustrative forms: not ancestors, viable organisms or demonstrated evolutionary paths."]}


if __name__ == "__main__":
    raise SystemExit(main())
