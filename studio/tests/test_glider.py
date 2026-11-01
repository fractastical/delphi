"""Launch-prototype glider fish (artifacts/glider/<revision>): every part file is the mesh that was checked and
weighed, the mass properties are exact for the mesh (analytic controls), the labels do not overclaim, and earlier
artifacts are untouched.

Reads the committed artifacts (seconds); the controls build three small solids.
Run without the Postgres fixtures:  pytest --noconftest tests/test_glider.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("manifold3d")

from engineering.geometry import validate as VAL
from engineering.glider import build as G
from engineering.glider import mass as MP

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "glider"
REVS = sorted(p.name for p in OUT.iterdir() if (p / "manifest.json").exists())


def manifest(rev: str) -> dict:
    return json.loads((OUT / rev / "manifest.json").read_text())


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_revisions_are_the_declared_lineage():
    assert REVS == sorted(G.REVISIONS)
    for rev in REVS:
        assert manifest(rev)["parent_revision"] == G.REVISIONS[rev]["parent"]


def test_mass_properties_controls_are_exact():
    rows = MP.controls()
    assert len(rows) == 3 and all(r["ok"] for r in rows), rows


@pytest.mark.parametrize("rev", REVS)
def test_files_hash_and_parts_are_the_checked_meshes(rev):
    m = manifest(rev)
    for rel, h in m["files"].items():
        assert sha(OUT / rev / rel) == h, rel
    for r in m["parts"]:
        V, T = VAL.read_stl((OUT / rev / r["stl"]).read_bytes())
        c = VAL.check(V, T, None, thickness=False)
        assert c["ok"] and c["mesh_sha256"] == r["stl_file"]["mesh_sha256"], r["id"]
        assert r["validation"]["ok"] and r["validation"]["face_connected_components"] == 1, r["id"]
        assert r["envelope"]["fits_axis_aligned"], r["id"]


@pytest.mark.parametrize("rev", REVS)
def test_part_mass_is_the_stl_volume_at_the_card_density(rev):
    """The recorded mass is the print-pose STL's volume x the card's density (the fish-frame copy is the same solid
    moved, so the volume agrees to float32 rounding)."""
    m = manifest(rev)
    for r in m["parts"]:
        V, T = VAL.read_stl((OUT / rev / r["stl"]).read_bytes())
        p = MP.properties(V, T, m["material"]["density_kg_m3"])
        assert p["mass_g"] == pytest.approx(r["mass_properties"]["mass_g"], rel=1e-4), r["id"]


@pytest.mark.parametrize("rev", REVS)
def test_wall_rule_and_the_edge_limited_readings_are_reported(rev):
    m = manifest(rev)
    for r in m["parts"]:
        w = r["wall"]
        assert w["rule_mm"] == r["min_wall_rule_mm"] == G.v(G.COMMON["min_wall_mm"])
        assert r["min_wall_ok"] == (w["wall_min_mm"] >= w["rule_mm"] and w["no_hit"] == 0), r["id"]
        assert w["raw_min_mm"] <= w["wall_min_mm"]  # the raw minimum is kept beside the gated one
        assert w["wall_readings"] + w["edge_limited_readings"] + w["no_hit"] == w["samples"]


@pytest.mark.parametrize("rev", REVS)
def test_assembly_is_interference_free_and_dry_mass_adds_up(rev):
    m = manifest(rev)
    na = m["nominal_assembly"]
    assert all(v <= 1e-6 for v in na["fin_body_overlap_mm3"].values())
    parts = {r["id"]: r for r in m["parts"]}
    total = sum(parts[i]["mass_properties"]["mass_g"] for i in na["parts"])
    assert na["dry"]["mass_g"] == pytest.approx(total, rel=1e-12)
    assert len(na["parts"]) == (6 if m["launch_catch"].get("adjustable") else 5)


@pytest.mark.parametrize("rev", REVS)
def test_mass_limit_verdict_is_reported_not_hidden(rev):
    t = manifest(rev)["trim_speed_hand"]
    assert t["mass_limit_g"]["value"] == 10.5
    assert t["within_mass_limit"] == (t["ballasted_mass_g_at_nominal_cg"] <= 10.5)


@pytest.mark.parametrize("rev", REVS)
def test_catch_geometry_matches_the_rule_it_was_built_to(rev):
    """r1: the fixed seat 0.5-2.5 mm below the CG (claude-07's first R3, since withdrawn; r1 keeps it, labelled).
    r2 on: the corrected R3, four seat heights relative to the design CG on each of two slots, a plug part for
    every seat but the slot top, and the nominal plug in the nominal assembly."""
    m = manifest(rev)
    h = m["launch_catch"]
    if not h.get("adjustable"):
        assert 0.5 <= h["seat_below_dry_cg_mm"] <= 2.5
        assert 17.0 <= h["seat_mm"][0] <= 32.0 and h["contact_radius_mm"] >= 1.5
        return
    assert h["contact_radius_mm"] >= 1.5
    ids = {r["id"] for r in m["parts"]}
    for x in h["slot"]["x_positions_mm"]:
        seats = [st for st in h["seats"] if st["slot_x_mm"] == x]
        offs = sorted(st["offset_from_design_cg_z_mm"] for st in seats)
        assert offs == [-1.5, 0.0, 1.5, 3.0]
        for st in seats:
            assert st["seat_mm"][1] - h["design_cg_z_mm"] == pytest.approx(st["offset_from_design_cg_z_mm"], abs=1e-6)
            assert (st["plug"] is None) == (st["offset_from_design_cg_z_mm"] == 3.0)
            assert st["plug"] is None or st["plug"] in ids
    assert abs(h["design_cg_z_mm"] - m["nominal_assembly"]["dry"]["cg_mm"][2]) < 0.05
    nom = h["nominal"]
    assert f"catch_plug-x{nom['slot_x_mm']:.0f}-dz{nom['offset_mm']:+.1f}" in m["nominal_assembly"]["parts"]


@pytest.mark.parametrize("rev", REVS)
def test_ballast_rows_are_consistent(rev):
    b = manifest(rev)["ballast"]
    dry = manifest(rev)["nominal_assembly"]["dry"]
    for r in b["rows"]:
        if r["feasible"]:
            x = (dry["mass_g"] * dry["cg_mm"][0] + r["ballast_g"] * r["fill_centroid_mm"][0]) / r["total_mass_g"]
            assert x == pytest.approx(r["cg_target_x_mm"], abs=0.01)
            assert r["fill_volume_mm3"] <= b["bay_volume_mm3"]


@pytest.mark.parametrize("rev", REVS)
def test_labels_do_not_overclaim(rev):
    m = manifest(rev)
    assert "UNTESTED" in m["label"] and "not claimed" in m["label"]
    assert {"flight-tested", "flightworthy", "compatible with Form Studio 1"} <= set(m["may_not_say"])
    assert "physical print" in m["not_checked"] and "any flight" in m["not_checked"]
    assert "ROOT's provisional" in m["decisions_provenance"] and "not user-confirmed" in m["decisions_provenance"]
    assert all(r["printed"] is False for r in m["parts"])
    assert m["biological_constraints"]["outline_check"]["all"]


@pytest.mark.parametrize("rev", REVS)
def test_flight_model_points_at_these_bytes(rev):
    f = json.loads((OUT / rev / "flight_model.json").read_text())
    m = manifest(rev)
    assert f["schema"] == "frontier.glider.flight-model/1" and f["source_candidate_sha256"] == \
        m["source_candidate"]["sha256"]
    for p in f["parts"]:
        assert sha(OUT / rev / p["stl"]) == p["stl_sha256"]
    assert f["assembled_dry"]["mass_kg"] == pytest.approx(m["nominal_assembly"]["dry"]["mass_kg"])


def test_earlier_artifacts_untouched():
    """Additive: the v3 candidate and the v3 display props keep the bytes they were merged with."""
    for rel in ("artifacts/fish3d/fish3d-v3a-fan/candidate.json", "artifacts/print-v3/manifest.json"):
        try:
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"46e47a7:{rel}"], check=True,
                                 capture_output=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("commit 46e47a7 not in this clone")
        assert (ROOT / rel).read_bytes() == old, rel
