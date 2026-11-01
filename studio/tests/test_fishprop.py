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


# ------------------------------------------------------------------ print-v4: v3c props
OUT4 = ROOT / "artifacts" / "print-v4"
V4_SPECS = {**P.SETS["v4"]["forms"], **P.V4_PENDING}


def design4(pid: str) -> dict:
    return json.loads((OUT4 / "design" / f"{pid}.json").read_text())


@pytest.fixture(scope="module")
def man4():
    if not (OUT4 / "manifest.json").exists():
        pytest.skip("artifacts/print-v4 not built")
    return json.loads((OUT4 / "manifest.json").read_text())


def test_v4_has_two_distinct_v3c_props_and_hashes_match(man4):
    assert sorted(man4["props"]) == ["fish3d-v3c-daane-length-prop", "fish3d-v3c-daane-length-prop-reinforced"]
    meshes = {r["mesh_sha256"] for r in man4["props"].values()}
    assert len(meshes) == 2                                   # not renamed copies
    assert {"relief_degenerate_triangles_before_cleanup", "glide_pose_prop_failed_dense_wall"} <= {
        f["id"] for f in man4["findings"]}
    assert not any("glide-pose" in rel for rel in man4["files"])   # the failed form is not published
    for rel, h in man4["files"].items():
        assert sha(OUT4 / rel) == h, rel
    dl = json.loads((OUT4 / "downloads.json").read_text())
    assert dl["base"] == "artifacts/print-v4/" and len(dl["forms"]) == 2
    for f in dl["forms"]:
        assert f["mass_density_kg_m3"] == 1220.0 and set(f["mass_conditional_g"]) == {"smooth", "relief", "stand"}
        for e in f["files"]:
            p = OUT4 / e["path"]
            assert p.stat().st_size == e["bytes"] and sha(p) == e["sha256"], e["path"]


@pytest.mark.parametrize("pid", ["fish3d-v3c-daane-length-prop", "fish3d-v3c-daane-length-prop-reinforced"])
def test_v4_prop_checks_are_gated_and_stated_separately(man4, pid):
    d = design4(pid)
    src = d["source_candidate"]
    assert src["id"] == "fish3d-v3c-daane-length" and sha(ROOT / src["path"]) == src["sha256"]
    wall = d["wall_rule"]["min_wall_mm"]
    for kind, v in (("smooth", d["validation"]), ("stand", d["stand"]["validation"])):
        assert v["ok"] and v["face_connected_components"] == 1 and v["degenerate_triangles"] == 0, kind
        assert v["min_wall_ok"] and v["min_wall_mm_required"] == wall, kind
        m = v["manufacturing"]
        assert m["ok"] and m["dense_wall"]["ok"] and m["dense_wall"]["min_mm"] >= wall, kind
        assert m["dense_wall"]["samples"] == min(P.DENSE_WALL_SAMPLES, v["triangles"]) and m["extremities"]["ok"], kind
    assert d["validation"]["manufacturing"]["mirror_symmetry"]["ok"]
    r = d["validation_relief"]
    assert r["ok"] and r["degenerate_triangles"] == 0 and r["face_connected_components"] == 1
    assert "min_wall_ok" not in r and r["relief"]["wall_rule_gated"] is False
    for v in (d["validation"], r, d["stand"]["validation"]):
        assert abs(v["float32_weld"]["clean_volume_change_mm3"]) < 0.01      # the cleanup does not reshape the part
    assert r["manufacturing"]["dense_wall"]["ok"] is None and r["manufacturing"]["mirror_symmetry"]["ok"] is None
    assert r["manufacturing"]["extremities"]["ok"]
    assert r["signed_volume_mm3"] > d["validation"]["signed_volume_mm3"]
    assert set(d["checks_stated_separately"]) == {"smooth", "relief", "stand"}
    for k, mc in d["mass_conditional"].items():
        vol = {"smooth": d["validation"], "relief": r, "stand": d["stand"]["validation"]}[k]["signed_volume_mm3"]
        assert mc["mass_g"] == pytest.approx(vol * 1220e-6, rel=1e-9) and mc["card"]["commit"] == "f1796ec"
    assert all(abs(x) < 1e-9 for x in d["stand"]["assembly_overlap_mm3"].values())   # float noise, not overlap
    assert d["lineage"]["builder_parent_commit"] == "aaa71f8" and d["why"]
    assert any("not a biological claim" in x for x in d["limitations"])
    V, T = VAL.read_stl((OUT4 / d["files"]["stl_smooth"]["path"]).read_bytes())
    assert VAL.check(V, T, P.BOX_MM, thickness=False)["mesh_sha256"] == d["stl_roundtrip"]["smooth"]["mesh_sha256"]


def test_v4_reinforced_is_stricter_and_heavier_than_display(man4):
    disp, rein = design4("fish3d-v3c-daane-length-prop"), design4("fish3d-v3c-daane-length-prop-reinforced")
    assert disp["wall_rule"]["min_wall_mm"] == 1.0 and rein["wall_rule"]["min_wall_mm"] == 1.5
    assert {r["what"] for r in rein["alterations"]} - {r["what"] for r in disp["alterations"]} == {"fin root gusset"}
    assert rein["validation"]["signed_volume_mm3"] > disp["validation"]["signed_volume_mm3"]
    assert rein["validation"]["wall_thickness"]["min_mm"] >= 1.5 > disp["validation"]["wall_thickness"]["min_mm"]


def test_v4_glide_pose_changes_pose_knobs_only():
    cand = V3.candidate("c-daane-length")
    alt, rows = P.alterations(cand, 0.5, 1.0, V4_SPECS["c-glide-pose"])
    changed = {k for k in cand["knobs"] if cand["knobs"][k]["value"] != alt["knobs"][k]["value"]}
    assert changed and changed <= set(P.POSE_KNOBS)
    assert alt["knobs"]["pectoral_length_source"] == cand["knobs"]["pectoral_length_source"]
    assert alt["knobs"]["pelvic_x_over_sl"] == cand["knobs"]["pelvic_x_over_sl"]
    assert next(r for r in rows if r["what"] == "pose")["status"] == "design assumption"
    *_, fans, _srec, _body = V3.build_components(alt)
    built = V3.rays_json(fans)
    src = json.loads((ROOT / "artifacts/fish3d/fish3d-v3c-daane-length/rays.json").read_text())["fins"]
    for fin, rec in src.items():
        assert [x["length_m"] for x in rec["rays"]] == [x["length_m"] for x in built[fin]["rays"]], fin


def test_root_gusset_thickens_at_the_root_only():
    roots = np.array([[0.0, 0.0], [0.0, 10.0]])
    pts = np.array([[0.0, 5.0, 1.0], [3.0, 5.0, 1.0], [6.0, 5.0, 1.0], [9.0, 5.0, -1.0]])
    out = P.root_thicken(pts, roots, 1.0, 6.0)
    assert out[:, 2].tolist() == pytest.approx([2.0, 1.5, 1.0, -1.0])
    assert out[:, :2].tolist() == pts[:, :2].tolist()


def test_extremity_and_mirror_checks_catch_a_needle_and_an_asymmetry():
    import manifold3d as mf
    block = mf.Manifold.cube((20, 20, 20), True)
    needle = block + mf.Manifold.cylinder(15, 0.2, 0.2, 16).rotate((0, 90, 0)).translate((9, 0, 0))
    stub = block + mf.Manifold.cylinder(15, 1.0, 1.0, 32).rotate((0, 90, 0)).translate((9, 0, 0))
    assert not P.extremities(needle, 1.0)["ok"]            # positive control: a 0.4 mm needle fails a 1 mm rod
    assert P.extremities(stub, 1.0)["ok"]
    assert P.mirror_fraction(block) == pytest.approx(0.0, abs=1e-9)
    assert P.mirror_fraction(block + mf.Manifold.cube((4, 4, 4)).translate((0, 12, 0))) > P.MIRROR_MAX_FRACTION


def test_print_v3_props_are_unchanged_since_they_were_frozen():
    for rel in MANIFEST["files"]:
        p = f"artifacts/print-v3/{rel}"
        try:
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"aaa71f8:{p}"], check=True,
                                 capture_output=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("commit aaa71f8 not in this clone")
        assert (ROOT / p).read_bytes() == old, p
    assert (OUT / "manifest.json").read_bytes() == subprocess.run(
        ["git", "-C", str(ROOT), "show", "aaa71f8:artifacts/print-v3/manifest.json"], check=True,
        capture_output=True).stdout


def test_v4_page_is_what_the_generator_writes(man4):
    page = (ROOT / "docs" / "fish-print-v4.md").read_text()
    assert page == P.v4_doc()
    assert "measured" not in page.lower() and "not weighed" in page


def test_v4_records_name_the_code_that_built_them(man4):
    assert man4["run"]["code_sha256"] == P.code_hash()
    assert json.loads((OUT4 / "downloads.json").read_text())["code_sha256"] == P.code_hash()
