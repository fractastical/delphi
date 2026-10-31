"""v3a leading-edge ray: geometry pins, thin-airfoil reference, member-pressure/2 transfer, patch emitter.

The section fixtures below are SYNTHETIC test data built from the analytic thin-airfoil jump: they
exercise the emitter's arithmetic and refusals and are never written as results.
"""
import copy
import math
import shutil

import numpy as np
import pytest

from engineering.coupled_mechanics import fin_geometry as fg
from engineering.coupled_mechanics import fin_patch as fpch
from engineering.coupled_mechanics import thin_airfoil as ta
from engineering.fin_mechanics.load_bridge import Refusal


@pytest.fixture(scope="module")
def g():
    return fg.load()


def test_geometry_pins_fail_closed(tmp_path):
    shutil.copytree(fg.V3A, tmp_path / "v3a", ignore=shutil.ignore_patterns("*.glb", "*.png"))
    p = tmp_path / "v3a" / "rays.json"
    p.write_text(p.read_text().replace('"n_rays": 15', '"n_rays": 16', 1))
    with pytest.raises(fg.GeometryError, match="rays.json sha256"):
        fg.load(tmp_path / "v3a")


def test_ray0_is_a_straight_leading_edge_member(g):
    r = fg.ray0(g)
    assert r["max_off_axis_m"] < 1e-7 and r["normal_in_plane_check"] < 1e-6
    assert abs(r["L_polyline_m"] - float(r["L_exact"])) < 1e-7
    assert math.degrees(r["sweep_rad"]) == pytest.approx(8.0, abs=1e-3)  # components.json lead_angle_deg
    for f in (0.0, 0.5, 1.0):
        assert fg.section(g, f)["ray0_offset_from_le_m"] == pytest.approx(0.0, abs=1e-12)


def test_branched_rays_are_not_offered_as_straight_members(g):
    assert all(r["branched"] for r in g["rays"]["rays"][1:])


def test_thin_airfoil_identities():
    a = math.radians(5)
    assert ta.G(1.0) == pytest.approx(math.pi / 2, rel=1e-15)  # 4 a G(1) = 2 pi a
    xs = np.linspace(0, 0.3, 300001)[1:]
    mid = 0.5 * (xs[1:] + xs[:-1])
    num = np.sum(ta.dcp(mid, a) * np.diff(xs))
    # midpoint rule misses the integrable sqrt singularity on [0, xs[0]] (exact there ~ 8 a sqrt(xs0))
    num += 8 * a * math.sqrt(xs[0])
    assert num == pytest.approx(4 * a * ta.G(0.3), rel=1e-4)


def test_zero_alpha_gives_zero_load(g):
    flow = copy.deepcopy(ta.DEFAULT_FLOW)
    flow["alpha_deg"]["value"] = 0.0
    ref = ta.reference(g, flow)
    tr = fpch.transfer_load(ta.record(ref, g), fpch.member_target(g))
    assert tr["F_N"] == 0.0 and tr["M_root_Nm"] == 0.0


def test_reference_scales_as_U2_and_alpha_eff(g):
    base = ta.reference(g)
    flow = copy.deepcopy(ta.DEFAULT_FLOW)
    flow["U_m_s"]["value"] *= 2
    dbl = ta.reference(g, flow)
    for a, b in zip(base["stations"], dbl["stations"]):
        assert b["q_true_N_per_m"] == pytest.approx(4 * a["q_true_N_per_m"], rel=1e-12)
    two_d = ta.reference(g, lifting_line=False)
    ratio = base["stations"][2]["q_true_N_per_m"] / two_d["stations"][2]["q_true_N_per_m"]
    assert ratio == pytest.approx(1 / (1 + 2 / base["aspect"]["AR"]), rel=1e-12)


def test_analytic_record_meets_the_contract(g):
    rec = ta.record(ta.reference(g), g)
    assert rec["schema"] == "frontier.coupled.member-pressure/2"
    tgt = fpch.member_target(g)
    tr = fpch.transfer_load(rec, tgt)
    assert tr["scope"].startswith("analytic") and tr["F_N"] > 0
    assert tr["deflection"].startswith("NOT COMPUTED") and tr["stress"].startswith("NOT COMPUTED")
    # wrong frame or member geometry is still refused, exactly as before
    bad = copy.deepcopy(rec)
    bad["member"]["tip_m"][0] = "0.0798"
    with pytest.raises(Refusal, match="GEOMETRY_MISMATCH"):
        fpch.transfer_load(bad, tgt)
    bad = copy.deepcopy(rec)
    bad["pressure"]["unit"] = "grid"
    with pytest.raises(Refusal, match="WRONG_PRESSURE_UNIT"):
        fpch.transfer_load(bad, tgt)


def test_v2_widths_are_ray0s_own_strip_from_the_pinned_geometry(g):
    ref = ta.reference(g)
    rec = ta.record(ref, g)
    t = rec["tributary"]
    assert t["geometry_sha256"] == fg.canonical_sha(fg.PINS) and t["unit"] == "m"
    assert [w["s_m"] for w in t["widths"]] == [st["s_m"] for st in rec["stations"]]
    lam = fg.ray0(g)["sweep_rad"]
    w = [float(x["width_m"]) for x in t["widths"]]
    for wi, st in zip(w, ref["stations"]):
        # dA/ds of the strip = (chordwise strip width) cos(sweep), recomputed here from the section cut
        assert wi == pytest.approx((st["tributary_local_m"] + st["ray0_offset_from_le_m"]) * math.cos(lam), rel=1e-12)
    assert all(b > a > 0 for a, b in zip(w, w[1:]))  # a fan: the strip widens root -> tip


def test_v1_constant_width_discrepancy_is_reproduced_and_v2_removes_it(g):
    import json
    ref = ta.reference(g)
    tgt = fpch.member_target(g)
    retained = json.loads((fg.ROOT / "artifacts/fin-patch/v1-constant-width/reference.json").read_text())
    tr1 = fpch.transfer_load(ta.record(ref, g, version=1), tgt)
    gap1 = fpch.fan_width_gap(ref, tr1)
    # the retained f8ebc13 numbers, recomputed from code: F +15.5 %, root moment -8.6 %
    assert tr1["F_exact"] == retained["transfer"]["F_exact"]
    assert tr1["M_root_exact"] == retained["transfer"]["M_root_exact"]
    assert gap1["F_contract_over_strip"] == pytest.approx(retained["gaps"][0]["F_contract_over_strip"], rel=1e-12)
    assert gap1["M_contract_over_strip"] == pytest.approx(retained["gaps"][0]["M_contract_over_strip"], rel=1e-12)
    assert round(gap1["F_contract_over_strip"] - 1, 3) == 0.155 and round(1 - gap1["M_contract_over_strip"], 3) == 0.086
    w = gap1["local_width_chordwise_m"]
    assert w[0] < gap1["declared_width_m"] < w[-1]
    gap2 = fpch.fan_width_gap(ref, fpch.transfer_load(ta.record(ref, g), tgt))
    assert gap2["F_contract_over_strip"] == pytest.approx(1, abs=1e-12)
    assert gap2["M_contract_over_strip"] == pytest.approx(1, abs=1e-12)


def test_v2_station_error_is_measured_and_shrinks(g):
    rows = fpch.station_convergence(g)["rows"]
    errs = [abs(r["F_rel_to_densest"]) for r in rows[:-1]]
    assert all(b < a for a, b in zip(errs, errs[1:]))
    assert errs[0] < 0.02  # the five-station load quoted in reference.json is within 2 % of 65 stations


def test_protocol_resolution_and_hashes(g):
    p = fpch.protocol(g)
    t = g["component"]["params"]["thickness_mm"]["value"]["membrane"] / 1000
    assert t / p["grid"]["h_m"] >= 2 and t / p["grid"]["h_fine_m"] >= 3 - 1e-9
    assert p["inputs"]["candidate_sha256"] == fg.CANDIDATE and p["member"]["member_sha256"]
    # gates are frozen: the move to member-pressure/2 changes no threshold
    assert p["gates"] == {"resolution_cells_across_membrane_min": 2, "grid_pair_rel_diff_max": 0.10,
                          "stationarity_rel_change_last_two_windows_max": 0.05,
                          "zero_alpha_control_jump_over_alpha_case_max": 0.02,
                          "sign": "strip-mean jump p_ventral - p_dorsal > 0 for alpha > 0"}
    assert "member-pressure/2" in p["output_contract"]["transfer"]
    assert all(s["ray0_width_per_ds_m"] > 0 for s in p["sections"])
    q = dict(p)
    sha = q.pop("protocol_sha256")
    assert fg.canonical_sha(q) == sha


# ------------------------------------------------------------------ emitter (synthetic sections)
def synthetic(g, proto, h_m, thickness_m, medium="air", n_rows=4000, **over):
    ref = ta.reference(g)
    cases, surfs = [], []
    for st, ps in zip(ref["stations"], proto["sections"]):
        c = st["chord_m"]
        edges = np.linspace(0, c, n_rows + 1)
        xm = 0.5 * (edges[1:] + edges[:-1])
        jump = ta.dcp(xm / c, ref["alpha_eff_rad"])
        rows = np.zeros((n_rows, 10), dtype=float)
        rows[:, 0] = xm
        rows[:, 5] = 1.0
        rows[:, 6] = np.diff(edges)
        rows[:, 7] = -jump / 2
        rows[:, 8] = jump / 2
        case = {"schema": fpch.SECTION_SCHEMA, "station_s_over_L": st["s_over_L"],
                "member_sha256": proto["member"]["member_sha256"], "frame_sha256": proto["member"]["frame_sha256"],
                "candidate_sha256": fg.CANDIDATE, "h_m": h_m, "thickness_m": thickness_m, "medium": medium,
                "rho_kg_m3": 1.225, "U_m_s": 5.0, "time_window_s": [1.0, 2.0],
                "surface_sha256": "f" * 64, **over}
        cases.append(case)
        surfs.append(rows)
    return cases, surfs


def test_emitter_round_trips_the_analytic_strip_and_passes_the_contract(g):
    proto = fpch.protocol(g)
    cases, surfs = synthetic(g, proto, h_m=5e-5, thickness_m=1e-4)
    rec = fpch.record_from_sections(cases, surfs, proto, g)
    assert rec["schema"] == "frontier.coupled.member-pressure/2"
    assert rec["tributary"] == ta.record(ta.reference(g), g)["tributary"]  # same widths, same provenance
    assert rec["resolution"]["cells_across_member_thickness"] == 2
    tr = fpch.transfer_load(rec, fpch.member_target(g))
    assert tr["scope"].startswith("2d-extrusion section scenario")
    ref_F = fpch.transfer_load(ta.record(ta.reference(g), g), fpch.member_target(g))["F_N"]
    # Rows sampled at segment midpoints miss part of the integrable 1/sqrt(xi) leading-edge peak; the
    # deficit scales as sqrt(row width), so 4x the rows must halve it. That is the emitter's measured
    # behaviour on a singular strip, and why a producer's row density at the LE is part of the contract.
    e = []
    for n in (4000, 16000):
        c2, s2 = synthetic(g, proto, h_m=5e-5, thickness_m=1e-4, n_rows=n)
        F = fpch.transfer_load(fpch.record_from_sections(c2, s2, proto, g), fpch.member_target(g))["F_N"]
        e.append((ref_F - F) / ref_F)
    assert 0 < e[1] < e[0] < 0.05
    assert e[1] / e[0] == pytest.approx(0.5, abs=0.1)


def test_emitter_computes_resolution_itself_and_refuses(g):
    proto = fpch.protocol(g)
    cases, surfs = synthetic(g, proto, h_m=1e-4, thickness_m=1e-4)  # 1 cell across
    with pytest.raises(Refusal, match="MEMBER_UNRESOLVED"):
        fpch.transfer_load(fpch.record_from_sections(cases, surfs, proto, g), fpch.member_target(g))
    cases, surfs = synthetic(g, proto, h_m=5e-5, thickness_m=1e-4, medium="none")
    with pytest.raises(Refusal, match="WRONG_PRESSURE_UNIT"):
        fpch.record_from_sections(cases, surfs, proto, g)
    cases, surfs = synthetic(g, proto, h_m=5e-5, thickness_m=1e-4, member_sha256="0" * 64)
    with pytest.raises(Refusal, match="GEOMETRY_MISMATCH"):
        fpch.record_from_sections(cases, surfs, proto, g)
    cases, surfs = synthetic(g, proto, h_m=5e-5, thickness_m=1e-4)
    rec = fpch.record_from_sections(cases, surfs, proto, g)
    with pytest.raises(Refusal, match="SAGITTAL_2D_NOT_3D"):
        fpch.transfer_load(rec, fpch.member_target(g, claim="whole_fin_3d"))


def test_emitter_needs_every_contract_station(g):
    proto = fpch.protocol(g)
    cases, surfs = synthetic(g, proto, h_m=5e-5, thickness_m=1e-4)
    rec = fpch.record_from_sections(cases[1:], surfs[1:], proto, g)  # root section missing
    with pytest.raises(Refusal, match="STATION_COVERAGE"):
        fpch.transfer_load(rec, fpch.member_target(g))


def test_committed_fin_patch_artifacts_are_current(g):
    import hashlib
    import json
    art = fg.ROOT / "artifacts" / "fin-patch"
    manifest = json.loads((art / "manifest.json").read_text())
    for group in ("outputs",):
        for name, pin in manifest[group].items():
            assert hashlib.sha256((art / name).read_bytes()).hexdigest() == pin["sha256"], name
    for group in ("code_files", "inputs"):
        for name, pin in manifest[group].items():
            assert hashlib.sha256((fg.ROOT / name).read_bytes()).hexdigest() == pin, name
    proto = json.loads((art / "protocol.json").read_text())
    assert proto == json.loads(json.dumps(fpch.protocol(g), default=str))
    # the superseded v1 artifacts are retained byte for byte, pinned by their own manifest and by ours
    v1 = art / manifest["retained_v1"]["dir"]
    v1_manifest = json.loads((v1 / "manifest.json").read_text())
    for name, pin in v1_manifest["outputs"].items():
        assert hashlib.sha256((v1 / name).read_bytes()).hexdigest() == pin["sha256"], name
    for name, sha in manifest["retained_v1"]["sha256"].items():
        assert hashlib.sha256((v1 / name).read_bytes()).hexdigest() == sha, name
