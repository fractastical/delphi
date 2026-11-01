"""Build the xenobot print pack: one STL set per design, a build plate, previews and a manifest.

Designs come from two places:
  * the ten evolved champions of the pre-registered claim test levin-2020-xenobots-06
    (test-data/claim-tests/levin-papers/levin-2020-xenobots-06/derived/pass2_champions.json);
  * any genome in designs/*.json written by evolve.py.

Per design, in out/<name>/:
  <name>_blocky.stl        exact voxel solid (one piece, watertight)
  <name>_smooth.stl        rounded isosurface of the same voxels (the organic look)
  <name>_contractile.stl   only the contractile cells, as cubes  } print separately or use as
  <name>_passive.stl       only the passive cells, as cubes      } a paint guide; together they
                                                                 tile the blocky solid exactly
  <name>_preview.png       top / side / front, contractile red, passive grey-blue
out/plate_smooth.stl, out/plate_blocky.stl: every design laid out on one plate with 8 mm gaps.
out/manifest.json: provenance (source file and sha256, seed, simulator fitness), geometry checks.

Run with the print venv: ../flying-zebrafish/.venv/bin/python build.py [--pitch 4]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import time

import numpy as np
import trimesh

import voxel2stl as v

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CHAMPS = os.path.join(ROOT, "test-data", "claim-tests", "levin-papers", "levin-2020-xenobots-06",
                      "derived", "pass2_champions.json")


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_designs():
    designs = []
    rel = os.path.relpath(CHAMPS, ROOT)
    h = sha256(CHAMPS)
    for c in json.load(open(CHAMPS)):
        designs.append({
            "name": f"champion-s{c['seed']}",
            "mat": c["mat"], "shape": (5, 5, 4),
            "source": {"file": rel, "sha256": h, "seed": c["seed"],
                       "fitness_sim_units": round(c["fitness"], 4),
                       "setting": "claim test levin-2020-xenobots-06, second pass: water, phases fixed per clade, 50 generations",
                       "kind": "simulated"},
        })
    for p in sorted(glob.glob(os.path.join(HERE, "designs", "*.json"))):
        d = json.load(open(p))
        designs.append({
            "name": d["name"], "mat": d["mat"], "shape": tuple(d.get("shape", (5, 5, 4))),
            "source": {"file": os.path.relpath(p, ROOT), "sha256": sha256(p),
                       "seed": d["params"]["seed"], "fitness_sim_units": d["fitness_sim_units"],
                       "setting": f"evolve.py: {d['params']['env']}, {d['params']['generations']} generations, "
                                  f"phase {'evolving' if d['params']['evolve_phase'] else 'fixed'}",
                       "kind": "simulated"},
        })
    return designs


def plate(meshes, gap=8.0):
    """Lay bodies out in a near-square grid on z = 0, left to right then back, 8 mm apart."""
    n = len(meshes)
    cols = int(np.ceil(np.sqrt(n)))
    placed, x, y, row_depth = [], 0.0, 0.0, 0.0
    for i, m in enumerate(meshes):
        m = m.copy()
        lo = m.bounds[0]
        m.apply_translation((x - lo[0], y - lo[1], -lo[2]))
        placed.append(m)
        ext = m.bounding_box.extents
        x += ext[0] + gap
        row_depth = max(row_depth, ext[1])
        if (i + 1) % cols == 0:
            x, y, row_depth = 0.0, y + row_depth + gap, 0.0
    return trimesh.util.concatenate(placed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitch", type=float, default=4.0, help="mm per voxel")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    entries, smooth_all, blocky_all = [], [], []
    for d in load_designs():
        grid = v.to_grid(d["mat"], d["shape"])
        comp = v.largest_component(grid > 0)
        if comp.sum() != (grid > 0).sum():
            raise SystemExit(f"{d['name']}: design is not one face-connected piece")
        odir = os.path.join(a.out, d["name"])
        os.makedirs(odir, exist_ok=True)
        files, checks = {}, {}
        parts = {
            "blocky": v.blocky_mesh(grid, a.pitch),
            "smooth": v.smooth_mesh(grid, a.pitch),
            "contractile": v.blocky_mesh(grid, a.pitch, material=v.CONTRACTILE),
        }
        if (grid == v.PASSIVE).any():
            parts["passive"] = v.blocky_mesh(grid, a.pitch, material=v.PASSIVE)
        for k, m in parts.items():
            path = os.path.join(odir, f"{d['name']}_{k}.stl")
            m.export(path)
            files[k] = os.path.relpath(path, ROOT)
            checks[k] = v.check(m)
        # split parts must tile the whole: volumes add up to the voxel count
        vox_vol = a.pitch ** 3
        n_vox = int((grid > 0).sum())
        assert abs(checks["blocky"]["volume_mm3"] - n_vox * vox_vol) < 1e-3, d["name"]
        split = checks["contractile"]["volume_mm3"] + checks.get("passive", {"volume_mm3": 0})["volume_mm3"]
        assert abs(split - n_vox * vox_vol) < 1e-3, d["name"]
        prev = os.path.join(odir, f"{d['name']}_preview.png")
        v.preview(grid, prev, f"{d['name']}  ({n_vox} voxels, {int((grid == 3).sum())} contractile, "
                              f"sim fitness {d['source']['fitness_sim_units']})", a.pitch)
        files["preview"] = os.path.relpath(prev, ROOT)
        smooth_all.append(parts["smooth"])
        blocky_all.append(parts["blocky"])
        entries.append({
            "name": d["name"], "source": d["source"], "genome": d["mat"],
            "n_voxels": n_vox, "n_contractile": int((grid == 3).sum()),
            "pitch_mm": a.pitch, "files": files, "geometry": checks,
            "smooth_volume_fraction_of_blocky": round(checks["smooth"]["volume_mm3"] / checks["blocky"]["volume_mm3"], 3),
        })
        print(f"{d['name']}: {n_vox} vox, blocky {checks['blocky']['bbox_mm']} mm "
              f"watertight={checks['blocky']['watertight']}/{checks['smooth']['watertight']}")

    plates = {}
    for k, ms in (("smooth", smooth_all), ("blocky", blocky_all)):
        p = plate(ms)
        path = os.path.join(a.out, f"plate_{k}.stl")
        p.export(path)
        plates[k] = {"file": os.path.relpath(path, ROOT), "bodies": len(ms),
                     "bbox_mm": [round(float(x), 2) for x in p.bounding_box.extents]}
        print(f"plate_{k}: {len(ms)} bodies, {plates[k]['bbox_mm']} mm")

    manifest = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pitch_mm": a.pitch,
        "frame": "mm, Z up (simulator ground = z 0), design min corner at origin per part; plates on z = 0",
        "what_this_is": "Static casts of simulated voxel designs for Formlabs printing. Shapes come from the "
                        "in-repo stand-in simulator (not Voxelyze); fitness numbers are simulator predictions. "
                        "The pitch is a print-scale choice: living xenobots are under 1 mm across.",
        "not_established": "No print has been made or measured; nothing here says a printed part moves, "
                           "and no printed resin part will (the simulated bodies move by contracting cells).",
        "designs": entries, "plates": plates,
    }
    json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    print(f"{len(entries)} designs -> {os.path.relpath(a.out, ROOT)}/manifest.json")


if __name__ == "__main__":
    main()
