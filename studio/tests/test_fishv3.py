"""fish3d v3 candidates: one hash per candidate everywhere, closed meshes, labelled parameters, sourced counts inside
their ranges, and variants that differ only in their named knobs.  Reads committed artifacts; ~10 s."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("manifold3d")

from engineering.fishv3 import appearance as AP
from engineering.fishv3 import build as V3

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/fish3d"
IDS = [f"fish3d-v3{k}" for k in V3.VARIANTS]
STATUSES = {"sourced", "derived", "figure_read", "assumed", "aesthetic", "numerical"}


def load(cid, name):
    return json.loads((OUT / cid / name).read_text())


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize("cid", IDS)
def test_one_candidate_hash_everywhere_and_files_match(cid):
    d = OUT / cid
    csha = sha(d / "candidate.json")
    build = load(cid, "build.json")
    assert build["candidate_sha256"] == csha
    for name in ("components.json", "rays.json", "panels.json", "sections.json", "scales.json", "surface_map.json",
                 *(f"appearance-{o}.json" for o in AP.OPTIONS)):
        assert load(cid, name)["candidate_sha256"] == csha, name
    for rel, h in build["files"].items():
        assert sha(d / rel) == h, rel
    assert load("", "v3-index.json")["candidates"][cid]["candidate_sha256"] == csha


@pytest.mark.parametrize("variant", sorted(V3.VARIANTS))
def test_candidate_is_reproducible_from_code(variant):
    from engineering.fish3d.build import canon
    assert canon(V3.candidate(variant)) == (OUT / f"fish3d-v3{variant}" / "candidate.json").read_bytes()


@pytest.mark.parametrize("cid", IDS)
def test_every_component_is_closed_oriented_positive(cid):
    for comp, c in load(cid, "build.json")["checks"].items():
        assert c["closed_two_manifold"] and c["consistently_oriented"] and c["signed_volume_mm3"] > 0, comp


def test_every_parameter_is_labelled_and_sourced_values_sit_in_their_range():
    c = V3.candidate("a-fan")
    for name, p in {**c["anatomy"], **c["numerical"]}.items():
        assert p["status"] in STATUSES, name
        if p["status"] == "sourced":
            assert p["source"] in c["sources"], name
        if "range_read" in p and isinstance(p["value"], (int, float)):
            lo, hi = p["range_read"]
            assert lo <= p["value"] <= hi, name
    for k in c["knobs"].values():
        assert k["status"]


def test_meristics_reach_the_mesh():
    an = V3.ANATOMY
    rays = load("fish3d-v3a-fan", "rays.json")["fins"]
    assert rays["pectoral_L"]["n_rays"] == an["pectoral_rays"]["value"] == 15
    assert rays["dorsal"]["n_rays"] == an["dorsal_rays"]["value"]
    assert rays["anal"]["n_rays"] == an["anal_rays"]["value"]
    assert rays["caudal"]["n_rays"] == sum(an["caudal_rays_upper_lower"]["value"])
    pect = rays["pectoral_L"]["rays"]
    assert not pect[0]["branched"] and all(r["branched"] for r in pect[1:])  # FAO: first pectoral ray unbranched
    # FAO: anal origin under dorsal ray 5-7 (we use the 6th)
    k = an["anal_origin_under_dorsal_ray"]["value"] - 1
    assert rays["anal"]["rays"][0]["root_m"][0] == pytest.approx(rays["dorsal"]["rays"][k]["root_m"][0], abs=1e-6)
    for r in pect:
        assert r["tributary_width_m"] > 0 and r["length_m"] > 0


def test_areas_hit_the_sourced_targets():
    for cid in ("fish3d-v3a-fan", "fish3d-v3c-daane-length"):
        p = load(cid, "components.json")["components"]["pectoral_L"]["params"]
        assert p["area_built_flat_mm2"]["value"] == pytest.approx(p["area_target_mm2"]["value"], rel=1e-6)
    c = load("fish3d-v3a-fan", "components.json")["components"]["caudal"]["params"]
    bio = V3.candidate("a-fan")["biology"]
    assert c["hypocaudal_share_built"]["value"] == pytest.approx(bio["hypocaudal_share"]["value"], rel=1e-6)
    assert c["lower_lobe_longest_ray_mm"]["value"] > c["upper_lobe_longest_ray_mm"]["value"]  # FAO, Daane


def test_variants_differ_only_in_their_knobs():
    a, b, c = (V3.candidate(k) for k in ("a-fan", "b-glide-pose", "c-daane-length"))
    per_variant = {"id", "variant", "title", "knobs", "pectoral_length_m"}
    for x in (b, c):
        assert {k for k in a if a[k] != x[k]} <= per_variant
    assert a["pectoral_length_m"] == b["pectoral_length_m"] != c["pectoral_length_m"]
    # a pose changes angles, dihedral and camber, never the anatomy: identical ray lengths
    ra, rb = (load(f"fish3d-v3{k}", "rays.json")["fins"] for k in ("a-fan", "b-glide-pose"))
    for fin in ra:
        assert [r["length_m"] for r in ra[fin]["rays"]] == [r["length_m"] for r in rb[fin]["rays"]], fin


def test_pelvic_placement_obeys_the_fao_rule():
    for k in V3.VARIANTS:
        c = V3.candidate(k)
        sl = c["biology"]["standard_length_m"]["value"]
        hl = c["anatomy"]["head_length_over_sl"]["value"]
        x = c["knobs"]["pelvic_x_over_sl"]["value"]
        assert abs(x - hl) < abs(0.97 - x), k
        assert sl > 0


def test_appearance_never_changes_geometry():
    import trimesh
    d = OUT / "fish3d-v3a-fan"
    geo = trimesh.load(d / "fish.glb", force="scene")
    for opt in AP.OPTIONS:
        rec = load("fish3d-v3a-fan", f"appearance-{opt}.json")
        assert rec["geometry_glb_sha256"] == load("fish3d-v3a-fan", "build.json")["files"]["fish.glb"]
        col = trimesh.load(d / rec["glb"], force="scene")
        for name in ("pectoral_L", "caudal", "body"):
            assert np.array_equal(geo.geometry[name].vertices, col.geometry[name].vertices), (opt, name)
    assert "DESIGN CHOICE" in AP.OPTIONS["juvenile-bars-design"]["title"]


def test_baseline_candidate_untouched():
    """v3 is additive: the v1 fish3d candidate keeps its committed bytes."""
    try:
        old = subprocess.run(["git", "-C", str(ROOT), "show",
                              "994aac4:artifacts/fish3d/fish3d-N1-cypselurus-baseline/candidate.json"],
                             check=True, capture_output=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("commit 994aac4 not in this clone")
    now = (OUT / "fish3d-N1-cypselurus-baseline/candidate.json").read_bytes()
    assert now == old and hashlib.sha256(now).hexdigest().startswith("4a3b912e")
    assert math.isfinite(len(now))
