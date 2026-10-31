"""3-D fish candidate: one hash across every file, closed components, scales on the surface, glTF axes."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from engineering.fish3d import build as B
from engineering.geometry import mesh as M

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/fish3d/fish3d-N1-cypselurus-baseline"


def load(name):
    return json.loads((OUT / name).read_text())


def test_one_candidate_hash_everywhere():
    h = hashlib.sha256((OUT / "candidate.json").read_bytes()).hexdigest()
    for name in ("build.json", "components.json", "scales.json", "surface_map.json", "sections.json"):
        assert load(name)["candidate_sha256"] == h, name
    rj = OUT / "render" / "render.json"
    if rj.exists():
        r = json.loads(rj.read_text())
        assert r["candidate_sha256"] == h and r["glb_sha256"] == load("build.json")["files"]["fish.glb"]


def test_candidate_is_reproducible_without_local_files():
    assert B.canon(B.candidate()) == (OUT / "candidate.json").read_bytes()


def test_components_closed_and_files_match():
    b = load("build.json")
    assert set(b["checks"]) == set(B.COMPONENTS)
    for cid, c in b["checks"].items():
        assert c["closed_two_manifold"] and c["consistently_oriented"], cid
    for rel, h in b["files"].items():
        assert hashlib.sha256((OUT / rel).read_bytes()).hexdigest() == h, rel


def test_every_parameter_is_labelled():
    comp = load("components.json")
    for cid, c in comp["components"].items():
        for k, p in c["params"].items():
            if isinstance(p, dict) and "value" in p:
                assert p.get("status") in {"derived", "measured", "assumed", "aesthetic", "numerical",
                                           "figure_read"}, (cid, k)


def test_scale_centres_lie_on_the_body_surface():
    surf, sc = load("surface_map.json"), load("scales.json")
    body = B.Body(surf["SL_mm"], surf["W_mm"], surf["height_over_width"], surf["ventral_flattening"],
                  surf["peduncle_fraction"])
    s = np.array([q["s"] for q in sc["scales"]]); phi = np.array([q["phi_rad"] for q in sc["scales"]])
    xyz = np.array([q["xyz_mm"] for q in sc["scales"]])
    assert len(s) > 500
    assert np.abs(body.point(s, phi) - xyz).max() < 1e-3


def test_glb_is_y_up_with_dorsal_up():
    trimesh = pytest.importorskip("trimesh")
    sc = trimesh.load(OUT / "fish.glb")
    g = sc.geometry["dorsal"]
    stl = trimesh.load(OUT / "components/dorsal.stl")
    assert np.isclose(g.bounds[1][1], stl.bounds[1][2])          # glTF +Y = fish +z (dorsal)
    assert np.isclose(g.bounds[0][2], -stl.bounds[1][1])         # glTF +Z = fish -y


def test_sections_are_cut_from_the_mesh():
    s = load("sections.json")
    for k in ("pectoral_mid", "body_sagittal", "planform"):
        assert s[k]["polygons_m"] and "2-D proxy" in s[k]["label"]
    t = np.array(s["pectoral_mid"]["polygons_m"][0])[:, 1]
    fin_t = B.FIDELITY["fin_thickness_mm"]["value"] / 1000
    assert np.isclose(t.max() - t.min(), fin_t, rtol=1e-3)


def test_body_profile_single_point_equals_array_value():
    s = np.linspace(0, 1, 2001)
    full = M.body_profile(s, 0.16)
    for i in (0, 140, 600, 1100, 1700, 2000):
        assert np.isclose(M.body_profile(np.array([s[i]]), 0.16)[0], full[i])
    assert np.isclose(M.body_profile(s, 0.0).max(), 1.0, atol=1e-6)  # analytic normalisation
