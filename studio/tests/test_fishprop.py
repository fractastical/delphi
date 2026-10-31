"""v3 fish display props: each names the exact v3 candidate it was built from, states its display scale and every
manufacturing alteration, passes the mesh checks it claims, and leaves the 1:1 candidate files alone.

Reads the committed artifacts in artifacts/print-v3 (a few seconds); one test rebuilds a candidate's fins (~10 s).
Run without the Postgres fixtures:  pytest --noconftest tests/test_fishprop.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("manifold3d")

from engineering.fishprop import build as P
from engineering.fishv3 import build as V3
from engineering.geometry import validate as VAL

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "print-v3"
MANIFEST = json.loads((OUT / "manifest.json").read_text())
PROPS = sorted(MANIFEST["props"])


def design(pid: str) -> dict:
    return json.loads((OUT / "design" / f"{pid}.json").read_text())


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_two_props_from_v3a_and_v3b():
    assert PROPS == ["fish3d-v3a-fan-prop", "fish3d-v3b-glide-pose-prop"]


def test_manifest_and_downloads_hashes_match_the_files():
    for rel, h in MANIFEST["files"].items():
        assert sha(OUT / rel) == h, rel
    dl = json.loads((OUT / "downloads.json").read_text())
    assert dl["base"] == "artifacts/print-v3/"
    for form in dl["forms"]:
        for e in form["files"]:
            p = OUT / e["path"]
            assert p.stat().st_size == e["bytes"] and sha(p) == e["sha256"], e["path"]


@pytest.mark.parametrize("pid", PROPS)
def test_prop_names_the_committed_candidate(pid):
    d = design(pid)
    src = d["source_candidate"]
    assert pid == f"{src['id']}-prop"
    assert sha(ROOT / src["path"]) == src["sha256"] == d["source_candidate"]["sha256"]
    assert json.loads((ROOT / "artifacts/fish3d" / src["id"] / "build.json").read_text())["candidate_sha256"] == \
        src["sha256"]
    assert d["cfd_geometry"]["path"] == f"artifacts/fish3d/{src['id']}/"


@pytest.mark.parametrize("pid", PROPS)
def test_smooth_prop_and_stand_pass_the_gated_checks(pid):
    d = design(pid)
    for v in (d["validation"], d["stand"]["validation"]):
        assert v["ok"] and v["closed_two_manifold"] and v["consistently_oriented"]
        assert v["face_connected_components"] == 1 and v["degenerate_triangles"] == 0
        assert v["min_wall_ok"] and v["min_wall_mm_required"] == d["wall_rule"]["min_wall_mm"]
        assert v["fits_box"] and v["signed_volume_mm3"] > 0
    assert d["stand"]["assembly_overlap_mm3"] == {"smooth": 0.0, "relief": 0.0}
    assert d["stl_roundtrip"]["smooth"]["ok"] and d["stl_roundtrip"]["relief"]["ok"]


@pytest.mark.parametrize("pid", PROPS)
def test_scale_relief_prop_is_one_closed_piece_and_says_it_is_not_wall_gated(pid):
    d = design(pid)
    v = d["validation_relief"]
    assert v["closed_two_manifold"] and v["consistently_oriented"] and v["face_connected_components"] == 1
    assert v["degenerate_triangles"] == 0 and v["fits_box"]
    assert "min_wall_ok" not in v and v["relief"]["wall_rule_gated"] is False
    assert v["signed_volume_mm3"] > d["validation"]["signed_volume_mm3"]  # relief only adds material
    assert all(abs(f["volume_mm3"]) <= P.DROP_MAX_MM3 for f in d["boolean_fragments_dropped"]["relief"])


@pytest.mark.parametrize("pid", PROPS)
def test_stl_on_disk_is_the_checked_mesh(pid):
    d = design(pid)
    V, T = VAL.read_stl((OUT / d["files"]["stl_smooth"]["path"]).read_bytes())
    c = VAL.check(V, T, P.BOX_MM, thickness=False)
    assert c["ok"] and c["mesh_sha256"] == d["stl_roundtrip"]["smooth"]["mesh_sha256"]


@pytest.mark.parametrize("pid", PROPS)
def test_display_scale_and_alterations_are_explicit(pid):
    d = design(pid)
    s = d["display_scale"]["value"]
    assert s == P.DISPLAY_SCALE and d["display_scale"]["prop_standard_length_mm"] == pytest.approx(
        s * d["display_scale"]["biological_standard_length_mm"])
    # prop length is the candidate's length times the scale, plus at most the thickened ray-tip and rim caps at
    # each end
    import trimesh
    g = trimesh.load(ROOT / "artifacts/fish3d" / d["source_candidate"]["id"] / "fish.glb", force="scene")
    bio_len_mm = (g.bounds[1][0] - g.bounds[0][0]) * 1000
    w = d["wall_rule"]["min_wall_mm"]
    cap = 0.5 * max(P.RAY_DIAMETER_OVER_WALL[0] * w, P.RIM_OVER_MEMBRANE * P.MEMBRANE_OVER_WALL * w)
    assert 0 <= d["validation"]["bounds_mm"]["size"][0] - s * bio_len_mm <= 2 * cap
    whats = {r["what"] for r in d["alterations"]}
    assert {"display scale", "fin membrane thickness (mm)", "fin ray diameter root, tip (mm)", "fin margin",
            "scales", "gill cover", "assembly"} <= whats
    assert all(r["status"] == "manufacturing alteration" for r in d["alterations"])


@pytest.mark.parametrize("pid", PROPS)
def test_labels_do_not_overclaim(pid):
    d = design(pid)
    assert d["printer_resin"]["printer"] == "unknown" and d["printer_resin"]["resin"] == "unknown"
    assert "unvalidated" in d["label"] and "provisional" in d["wall_rule"]["status"]
    assert {"bioprint", "living", "ready to print on a named printer"} <= set(d["may_not_say"])
    assert "physical print" in d["not_checked"]


def test_wall_rule_is_configurable():
    cand = V3.candidate("a-fan")
    for wall in (1.0, 1.5):
        _, rows = P.alterations(cand, P.DISPLAY_SCALE, wall)
        r = {x["what"]: x for x in rows}
        assert r["fin membrane thickness (mm)"]["prop"] == pytest.approx(P.MEMBRANE_OVER_WALL * wall)
        assert r["fin ray diameter root, tip (mm)"]["prop"] == pytest.approx(
            [k * wall for k in P.RAY_DIAMETER_OVER_WALL])


def test_alterations_change_thickness_only():
    cand = V3.candidate("b-glide-pose")
    alt, _ = P.alterations(cand, P.DISPLAY_SCALE, 1.0)
    *_, fans, _srec, _body = V3.build_components(alt)
    built = V3.rays_json(fans)
    src = json.loads((ROOT / "artifacts/fish3d/fish3d-v3b-glide-pose/rays.json").read_text())["fins"]
    for fin, rec in src.items():
        assert [r["length_m"] for r in rec["rays"]] == [r["length_m"] for r in built[fin]["rays"]], fin
        assert np.allclose([r["root_m"] for r in rec["rays"]], [r["root_m"] for r in built[fin]["rays"]],
                           rtol=0, atol=1e-9), fin


def test_v3_candidates_untouched():
    """Props are additive: the 1:1 candidates keep the bytes they were integrated with."""
    for cid in ("fish3d-v3a-fan", "fish3d-v3b-glide-pose"):
        for name in ("candidate.json", "build.json", "fish.glb"):
            try:
                old = subprocess.run(["git", "-C", str(ROOT), "show", f"8dc5cc4:artifacts/fish3d/{cid}/{name}"],
                                     check=True, capture_output=True).stdout
            except (subprocess.CalledProcessError, FileNotFoundError):
                pytest.skip("commit 8dc5cc4 not in this clone")
            assert (ROOT / "artifacts/fish3d" / cid / name).read_bytes() == old, (cid, name)
