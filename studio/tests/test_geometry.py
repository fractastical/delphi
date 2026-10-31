"""Printable flying-fish forms: the validator catches what it claims to, and the committed artifacts pass it.

Run without the Postgres fixtures:  pytest --noconftest tests/test_geometry.py
The geometry stack (manifold3d, trimesh, matplotlib, numpy) is not a project dependency; these tests skip when
manifold3d is absent rather than fail.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("manifold3d")

from engineering.geometry import build as B  # noqa: E402
from engineering.geometry import forms as F  # noqa: E402
from engineering.geometry import graph as G  # noqa: E402
from engineering.geometry import solver_bridge as SB  # noqa: E402
from engineering.geometry import validate as VAL  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "artifacts" / "print"
DIRS = {"v1": OUT, "v2": REPO / "artifacts" / "print-v2"}  # one edition per directory (build.py --edition)
MANIFESTS = {ed: json.loads((d / "manifest.json").read_text()) for ed, d in DIRS.items()}
MANIFEST = MANIFESTS["v1"]
FORM_IDS = [f.id for f in F.FORMS]
CASES = [(ed, f.id) for ed, forms in F.EDITIONS.items() for f in forms]
EDITION_OF = {fid: ed for ed, fid in CASES}


def design(form_id: str) -> dict:
    return json.loads((DIRS[EDITION_OF[form_id]] / "design" / f"{form_id}.json").read_text())


def cube(offset=(0.0, 0.0, 0.0)):
    V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
    T = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                  [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return V + np.array(offset), T


# ---- the validator: a positive control and one negative control per claimed check ----

def test_cube_passes():
    r = VAL.check(*cube(), box_mm=2, thickness=False)
    assert r["ok"] and r["genus"] == 0 and r["signed_volume_mm3"] == pytest.approx(1.0)


def test_missing_face_is_not_closed():
    V, T = cube()
    r = VAL.check(V, T[:-1], thickness=False)
    assert not r["closed_two_manifold"] and not r["ok"]


def test_flipped_face_is_not_oriented():
    V, T = cube()
    T = T.copy()
    T[0] = T[0][::-1]
    r = VAL.check(V, T, thickness=False)
    assert not r["consistently_oriented"] and not r["ok"]


def test_inside_out_has_negative_volume():
    V, T = cube()
    r = VAL.check(V, T[:, ::-1], thickness=False)
    assert r["signed_volume_mm3"] < 0 and not r["ok"]


def test_two_pieces_are_two_components():
    V1, T1 = cube()
    V2, T2 = cube((3, 0, 0))
    r = VAL.check(np.vstack([V1, V2]), np.vstack([T1, T2 + len(V1)]), thickness=False)
    assert r["face_connected_components"] == 2 and not r["ok"]


def test_nonfinite_vertex_fails():
    V, T = cube()
    V[6, 0] = np.nan
    assert not VAL.check(V, T, thickness=False)["ok"]


def test_degenerate_triangle_fails():
    V, T = cube()
    T = np.vstack([T, [[0, 0, 1]]])
    r = VAL.check(V, T, thickness=False)
    assert r["degenerate_triangles"] == 1 and not r["ok"]


def test_box_limit_is_enforced():
    V, T = cube()
    r = VAL.check(V * 130, T, box_mm=120, thickness=False)
    assert not r["fits_box"] and not r["ok"]


def test_thickness_sampler_measures_a_known_slab():
    V, T = cube()
    V = V * np.array([20.0, 20.0, 1.0])  # a 1 mm slab
    t = VAL.thickness_samples(V, T, n=200)
    assert t["no_hit"] == 0 and t["min_mm"] == pytest.approx(1.0, abs=1e-3)


def test_min_wall_gate_fails_a_thin_slab():
    V, T = cube()
    V = V * np.array([20.0, 20.0, 0.5])  # a 0.5 mm slab against a 1 mm requirement
    r = VAL.check(V, T, min_wall_mm=1.0)
    assert r["closed_two_manifold"] and not r["min_wall_ok"] and not r["ok"]
    assert VAL.check(V * np.array([1, 1, 3.0]), T, min_wall_mm=1.0)["ok"]  # 1.5 mm passes


def test_stl_roundtrip_and_weld():
    V, T = cube()
    V2, T2 = VAL.read_stl(VAL.stl_bytes(V, T, "cube"))
    assert VAL.check(V2, T2, thickness=False)["ok"] and len(V2) == 8
    Vd = np.vstack([V, V[1:2] + [1e-9, 0, 0]])  # float32-identical to vertex 1 (1 + 1e-9 rounds to 1)
    Td = np.vstack([T, [[0, 8, 1]]])  # and a face that collapses once it is welded
    Vw, Tw, info = VAL.weld_float32(Vd, Td)
    assert info == {"merged_vertices": 1, "dropped_faces": 1} and VAL.check(Vw, Tw, thickness=False)["ok"]


# ---- the committed artifacts ----

@pytest.mark.parametrize("edition,form_id", CASES)
def test_committed_stls_pass_the_validator(edition, form_id):
    for name in (f"{form_id}.stl", f"{form_id}-stand.stl"):
        data = (DIRS[edition] / "stl" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == MANIFESTS[edition]["files"][f"stl/{name}"]
        r = VAL.check(*VAL.read_stl(data), box_mm=B.BOX_MM, thickness=False)
        assert r["ok"], (name, r)
        assert r["face_connected_components"] == 1 and r["degenerate_triangles"] == 0


@pytest.mark.parametrize("edition,form_id", CASES)
def test_design_records_its_checks(edition, form_id):
    d = design(form_id)
    v = d["validation"]
    assert v["ok"] and d["stand"]["validation"]["ok"] and d["stl_roundtrip"]["ok"]
    assert d["convergence"]["converged"]
    length, span, _height = v["bounds_mm"]["size"]
    assert 90 <= length <= 120 and span <= 120
    for w in (v, d["stand"]["validation"]):
        assert w["min_wall_mm_required"] == 1.0 and w["min_wall_ok"] and w["wall_thickness"]["min_mm"] >= 1.0
    assert d["printer_resin"]["printer"] == "unknown" and d["printer_resin"]["resin"] == "unknown"
    assert v["self_intersection"] == "not checked"
    # The saddle is cut by the prop itself, so they share a contact surface; simplify() moves surfaces < 1 um,
    # which leaves an overlap of order contact area x 1 um (measured ~1e-4 mm^3).  A real clash is >> 0.01.
    assert d["stand"]["assembly_overlap_mm3"] < 0.01
    assert "Not an ancestor" in d["label"] and "viable" in d["engineering_status"]["may_not_say"]


@pytest.mark.parametrize("edition,form_id", CASES)
def test_prop_rebuilds_from_its_design_json(edition, form_id):
    """The design JSON is the whole input: rebuilding from it gives the committed mesh, byte for byte."""
    d = design(form_id)
    solid, _ = F.build_prop(F.FORMS_BY_ID[form_id], d["biological_design_SI"], d["prop_mm"]["display_scale"])
    V, T, _ = B.mesh_arrays(solid)
    assert VAL.mesh_hash(V, T) == d["validation"]["mesh_sha256"]


def test_every_parameter_is_kind_labelled():
    kinds = {"functional", "figure_read", "design_assumption", "aesthetic", "derived", "print"}
    for _, form_id in CASES:
        d = design(form_id)
        for group in ("biological_design_SI", "aesthetic_and_shape_parameters", "print_parameters"):
            for name, p in d[group].items():
                assert p["kind"] in kinds, (form_id, group, name)


def test_biology_scale_and_resin_stay_separate():
    for ed, form_id in CASES:
        d = design(form_id)
        mm = d["prop_mm"]
        mass = {"morphology": 0.1, "nca-comparison": 0.05}[d["set"]["id"].rsplit("-", 1)[0]]
        assert d["biological_design_SI"]["mass_kg"]["value"] == pytest.approx(mass)
        assert mm["display_scale"] == MANIFESTS[ed]["sets"][d["set"]["id"]]["display_scale"]
        assert "slicer" in mm["resin"]
        built = mm["built"]
        assert built["pectoral_prop_area_exaggeration"] == pytest.approx(1.0, abs=0.02)


# ---- solver links ----

@pytest.mark.parametrize("edition", sorted(DIRS))
def test_solver_statuses_and_candidates(edition):
    status = {k: v["solver"] for k, v in MANIFESTS[edition]["forms"].items()}
    sfx = "" if edition == "v1" else f"-{edition}"
    assert status == {f"A-precursor-short-fin{sfx}": "unsat", f"B-two-wing-glider{sfx}": "feasible",
                      f"C-four-wing-glider{sfx}": "feasible", f"N1-cypselurus-baseline{sfx}": "feasible",
                      f"N2-area-x1.3{sfx}": "feasible", f"N3-area-x1.3-ar-x1.2{sfx}": "feasible"}
    out = DIRS[edition]
    for form_id, st in status.items():
        d = design(form_id)
        cand = d["glide_candidate"]
        assert (cand is not None) == (st == "feasible")
        if cand:
            c = json.loads((out / cand["path"]).read_text())
            assert c["schema"] == SB.CANDIDATE_SCHEMA
            assert hashlib.sha256((out / cand["path"]).read_bytes()).hexdigest() == cand["sha256"]
            w = c["solver_result"]["witness"]
            assert d["biological_design_SI"]["wing_area_m2"]["solver_exact"] == w["S"]
        assert d["engineering_status"]["glide"]["status"] in ("not_run", "not_applicable", "attached")


def _have_solver_commit() -> bool:
    try:
        subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", SB.GUILDS_COMMIT], check=True,
                       capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not _have_solver_commit(), reason="guilds' solver commit is not in this clone")
def test_solver_rerun_matches_recorded_result():
    pytest.importorskip("z3")
    mod, prov = SB.load_solver(REPO)
    for ed, form_id in CASES:
        assert prov["blob_sha256"] == MANIFESTS[ed]["run"]["solver"]["blob_sha256"]
        rec = json.loads((DIRS[ed] / "solver" / f"{form_id}.solver.json").read_text())
        q = rec["query"]
        from fractions import Fraction
        run = SB.solve_point(mod, Fraction(q["m"]), Fraction(q["S"]), Fraction(q["b"]), B.LAUNCH_SPEED)
        assert run["default"]["status"] == rec["default"]["status"]
        # an unsat core is a set; z3 lists it in an order that depends on what this process solved before (measured:
        # A-v2 re-solved after the six v1 queries lists the same three constraints rotated), so compare as sets
        assert sorted(run["default"]["conflict"] or []) == sorted(rec["default"]["conflict"] or [])


# ---- sources and the species graph ----

def test_daane_summary_is_internally_consistent():
    from engineering.geometry import sources as src
    s = src.daane_summary()
    assert s["specimens"] == sum(g["n"] for g in s["groups"].values()) == 109
    assert s["groups"]["halfbeak"]["pectoral_over_sl"]["median"] == pytest.approx(0.1402, abs=1e-4)
    assert s["groups"]["flying fish"]["pectoral_over_sl"]["median"] == pytest.approx(0.687, abs=1e-3)


def test_fish1990_tables_agree_where_they_overlap():
    from engineering.geometry import sources as src
    assert src.table_cross_check("Cypselurus", 0.1)["relative_difference"] < 0.05
    assert src.table_cross_check("Exocoetus", 0.1)["relative_difference"] < 0.12


def test_graph_keeps_conjecture_apart():
    groups = {n["id"]: n["group"] for n in G.NODES}
    for e in G.EDGES:
        if e["kind"] == "conjectured_route":
            assert groups[e["from"]] == groups[e["to"]] == "engineered"
            assert "not demonstrated" in e["label"]
        else:
            assert groups[e["from"]] != "engineered", e
    for n in G.NODES:
        if n["group"] != "engineered":
            assert n["source"] and n["read_level"], n["id"]
    assert json.loads((OUT / "species-graph.json").read_text()) == G.graph_json()


def test_artifacts_were_built_by_this_code():
    """A geometry edit without a rebuild leaves artifacts describing other code; rebuild with build.py."""
    for m in MANIFESTS.values():
        assert m["run"]["code_sha256"] == B.code_hash()


# ---- sets, the NCA comparison set and the site's download manifest ----

@pytest.mark.parametrize("edition", sorted(DIRS))
def test_every_set_meets_the_length_aim_at_one_scale(edition):
    m = MANIFESTS[edition]
    for sid, s in m["sets"].items():
        assert s["length_aim"]["met"], (sid, s["length_aim"])
        assert {m["forms"][f]["display_scale"] for f in s["forms"]} == {s["display_scale"]}


@pytest.mark.parametrize("sfx", ["", "-v2"])
def test_comparison_set_is_ncas_geometry(sfx):
    """N1-N3 are dx-nca's three geometries (Fish Cypselurus fit at 0.05 kg, S x fS, whole-wing AR x fAR), and the
    quoted simulation rows come from NCA's committed CSV with the recorded sha256."""
    from engineering.geometry import sources as src
    expect = {"N1-cypselurus-baseline": (0.005699, 0.2117), "N2-area-x1.3": (0.007409, 0.2414),
              "N3-area-x1.3-ar-x1.2": (0.007409, 0.2644)}  # nca-to-print.md table, written out independently
    for form_id, (S, b) in expect.items():
        d = design(form_id + sfx)
        bio = d["biological_design_SI"]
        assert bio["wing_area_m2"]["value"] == pytest.approx(S, abs=5e-7)
        assert bio["wing_span_m"]["value"] == pytest.approx(b, abs=5e-5)
        sim = d["simulation_comparison"]
        assert sim["geometry_matches"] and sim["sha256"] == src.NCA_CONTROLLED["comparison_csv_sha256"]
        assert sim["evidence_kind"] == "simulated" and len(sim["rows"]) == 6
    sink = [float(design(f + sfx)["simulation_comparison"]["rows"][0]["sink_eq_ms"]) for f in expect]
    assert sink[0] > sink[1] > sink[2]  # NCA's one robust effect, as recorded, not re-derived here


def test_morphology_set_files_are_preserved():
    """A new dimension set gets new ids; the merged v1 meshes, solver runs and candidates stay byte-identical."""
    try:
        listed = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", "3c97a38", "--",
                                 "artifacts/print/stl", "artifacts/print/glide", "artifacts/print/web",
                                 "artifacts/print/solver"], check=True, capture_output=True, text=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("commit 3c97a38 is not in this clone")
    assert len(listed) == 14
    for path in listed:
        old = subprocess.run(["git", "-C", str(REPO), "show", f"3c97a38:{path}"], check=True,
                             capture_output=True).stdout
        assert (REPO / path).read_bytes() == old, path


@pytest.mark.parametrize("edition", sorted(DIRS))
def test_download_manifest_matches_the_files(edition):
    out = DIRS[edition]
    dl = json.loads((out / "downloads.json").read_text())
    assert dl["base"] == f"{out.relative_to(REPO).as_posix()}/"
    assert dl["printer_resin"]["printer"] == "unknown" and any("Printer and resin are unknown" in x
                                                              for x in dl["limitations"])
    assert [f["id"] for f in dl["forms"]] == [f.id for f in F.EDITIONS[edition]]
    for f in dl["forms"]:
        assert {e["kind"] for e in f["files"]} >= {"stl_prop", "stl_stand", "glb_prop"}
        for e in f["files"]:
            data = (out / e["path"]).read_bytes()
            assert len(data) == e["bytes"] and hashlib.sha256(data).hexdigest() == e["sha256"]
        for c in (f["prop_checks"], f["stand_checks"]):
            assert c["ok"] and c["closed_two_manifold"] and c["consistently_oriented"] and c["min_wall_ok"]
            assert c["face_connected_components"] == 1 and c["self_intersection"] == "not checked"


# ---- the v2 edition: corrected body profile, new ids, v1 untouched ----

PUBLISHED_V1 = "518671a"  # work/print-forms with the six v1 turntables, as the site took them


def test_v1_binaries_unchanged_since_publication():
    """v2 is additive: every v1 mesh, stand, GLB, solver run, candidate, image and video keeps its published bytes.
    Only JSON/HTML records that carry the build code hash may change."""
    try:
        listed = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", PUBLISHED_V1, "--",
                                 "artifacts/print"], check=True, capture_output=True, text=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"commit {PUBLISHED_V1} is not in this clone")
    binaries = [p for p in listed if p.endswith((".stl", ".glb", ".png", ".mp4", ".gif"))
                or "/solver/" in p or "/glide/" in p]
    assert len(binaries) == 12 + 6 + 13 + 6 * 3 + 6 + 5, len(binaries)  # stl, glb, img, media, solver, glide
    for path in binaries:
        old = subprocess.run(["git", "-C", str(REPO), "show", f"{PUBLISHED_V1}:{path}"], check=True,
                             capture_output=True).stdout
        assert (REPO / path).read_bytes() == old, path


def test_v2_is_v1_with_the_pointwise_profile_only():
    """Same specs except id, set, labels and body_profile; the recorded body width at each fin root is the
    pointwise profile for v2 and the frozen v1 function for v1; and every v2 prop mesh differs from its v1 form."""
    from dataclasses import asdict

    from engineering.geometry import mesh as M
    m2 = MANIFESTS["v2"]
    for v1, v2 in zip(F.EDITIONS["v1"], F.EDITIONS["v2"]):
        a, b = asdict(v1), asdict(v2)
        changed = {k for k in a if a[k] != b[k]}
        assert changed <= {"id", "set_id", "short", "title", "status_note", "body_profile", "fin_shape_from"}
        assert (v1.body_profile, v2.body_profile) == ("v1", "pointwise") and v2.id == v1.id + "-v2"
        assert m2["edition"]["supersedes"][v2.id] == v1.id
        for spec, fn in ((v1, M.body_profile_v1), (v2, M.body_profile)):
            bio = design(spec.id)["biological_design_SI"]
            W = bio["body_half_width_max_m"]["value"]
            ped = spec.params["peduncle_fraction"]["value"]
            got = bio["fin_layout_bio"]["value"]["body_width_at_fins_m"]
            for fin, x in bio["fin_x_over_sl"]["value"].items():
                assert got[fin] == pytest.approx(2 * W * float(fn(np.array([x]), ped)[0]), rel=1e-12), (spec.id, fin)
        assert design(v2.id)["validation"]["mesh_sha256"] != design(v1.id)["validation"]["mesh_sha256"]
    for sid, s in m2["sets"].items():
        assert s["supersedes"] == sid.replace("-v2", "-v1")
