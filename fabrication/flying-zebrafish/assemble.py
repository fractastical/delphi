"""Fuse body + stripes + wings + fins into one printable mesh. Run from this folder with .venv/bin/python."""
import sys, json
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from stripes.emboss import emboss_stripes

OUT = ROOT / "out"; OUT.mkdir(exist_ok=True)


def mirror_y(m):
    r = m.copy(); r.vertices = r.vertices * np.array([1, -1, 1]); r.invert(); return r


def union(meshes):
    return trimesh.boolean.union(meshes, engine="manifold")


def load(p): return trimesh.load(ROOT / p, force="mesh")


def main():
    body = load("parts/body/body_nostripes.stl")
    body = emboss_stripes(body)                                   # Nakamasu 2009 stripes
    pec = load("parts/pectoral/pectoral.stl"); pel = load("parts/pelvic/pelvic.stl")
    tail = load("parts/tail/tail.stl")
    parts = [body, pec, mirror_y(pec), pel, mirror_y(pel)] + list(tail.split(only_watertight=False))
    print("parts:", [(len(p.faces), p.is_watertight) for p in parts])
    fish = union(parts)
    # keep the largest shell, drop debris
    shells = fish.split(only_watertight=False)
    shells.sort(key=lambda s: -abs(s.volume))
    print("shells after union:", [(round(s.volume, 1)) for s in shells[:6]])
    fish = shells[0]
    fish.merge_vertices(); fish.fix_normals()
    fish.export(OUT / "flying-zebrafish.stl")
    try:
        fish.export(OUT / "flying-zebrafish.3mf")
    except Exception as e:
        print("3mf export failed:", e)
    info = {"watertight": bool(fish.is_watertight), "winding": bool(fish.is_winding_consistent),
            "volume_mm3": float(fish.volume), "faces": int(len(fish.faces)),
            "bounds": fish.bounds.round(2).tolist(), "extents": fish.extents.round(2).tolist(),
            "shells_dropped": len(shells) - 1}
    json.dump(info, open(OUT / "assembly.json", "w"), indent=1); print(info)
    return fish


if __name__ == "__main__":
    main()
