"""Focused checks on cfd3d's committed packet, case artifacts and regime/grid summaries (no solver run)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/cfd3d"
PACKET = ART / "packet"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"engineering/cfd3d/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_regime_converts_re_to_speed_in_each_medium():
    s = _load("summarize")
    r = s.regime(200)
    assert r["same_Re_in_each_medium"]["water_20C"]["U_m_s"] == pytest.approx(200 * 1.004e-6 / 0.230699)
    assert r["same_Re_in_each_medium"]["air_20C"]["U_m_s"] == pytest.approx(200 * 1.516e-5 / 0.230699)
    for v in r["intended"].values():          # intended regimes stay far above the simulated one
        assert min(v["gap_factor"]) > 100 and v["status"].startswith("assumed")
    assert "NOT" in r["label"].upper() and "flight" in r["label"]


def test_cpu_pair_is_reported_not_grid_independent():
    s = json.loads((ART / "summary-cpu.json").read_text())
    (pair,) = s["grid_pairs"]
    assert pair["rel_diff"] > 0.10 and pair["grid_rule_met"] is False
    assert "no force claim" in pair["reading"]


@pytest.mark.parametrize("case", ["fish_L24_Re200", "fish_L32_Re200"])
def test_case_artifacts_match_their_header(case):
    c = json.loads((ART / case / "case.json").read_text())
    geo = json.loads((ART / "geometry/components.json").read_text())
    assert c["candidate_sha256"] == geo["candidate_sha256"]
    assert c["resolution"]["fins_resolved"] is False and c["resolution"]["fin_thickness_cells"] < 2
    assert "body force" in c["coefficients"]["sign"] or "ON THE BODY" in c["coefficients"]["sign"].upper()
    for k, v in c["components"].items():
        assert v["stl_sha256"] == geo["components"][k]["stl_sha256"]
        n = (ART / case / "surface" / f"{k}.f32").stat().st_size
        assert n == v["rows"] * 10 * 4                        # 10 float32 columns per STL triangle
        assert v["resolved"] == (k in ("body", "eye_L", "eye_R"))
    r = json.loads((ART / case / "render/render.json").read_text())
    assert r["video"]["sha256"] == sha(ART / case / "render/flow.mp4")
    assert "FAILED" in r["caption"] and "not swimming" in r["caption"]


def test_reference_gate_failure_is_carried_by_the_packet():
    pk = json.loads((ROOT / "engineering/cfd3d/packet.json").read_text())
    ctl = json.loads((ART / "controls/cpu_controls.json").read_text())
    assert pk["reference_gate"]["C1_sphere_Re100"] == "FAIL" and ctl["C1"]["pass"] is False
    assert pk["local_cpu_pins"]["sphere_D16_Cd"] == ctl["C1"]["D16"]["Cd_mean"]


def test_packet_manifest_matches_archive_and_git():
    m = json.loads((PACKET / "packet-manifest.json").read_text())
    blob = (PACKET / m["archive"]).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == m["archive_sha256"] and m["inject_total_raw"] <= 45_000
    with tarfile.open(PACKET / m["archive"]) as tf:
        for row in m["files"]:
            data = tf.extractfile(row["path"]).read()
            assert hashlib.sha256(data).hexdigest() == row["sha256"]
            src = row["path"].removeprefix("fish3d_src/")
            assert subprocess.run(["git", "-C", str(ROOT), "rev-parse", f"{row['rev']}:{src}"],
                                  capture_output=True, text=True).stdout.strip() == row["blob"]


def _launch(tmp_path, digest, extra_env=None):
    m = json.loads((PACKET / "packet-manifest.json").read_text())
    env = dict(os.environ, PREFLIGHT="1", TMPDIR=str(tmp_path), **(extra_env or {}))
    return subprocess.run([sys.executable, "-I", str(ROOT / m["launcher"]), str(PACKET / m["archive"]), digest],
                          env=env, capture_output=True, text=True, timeout=60)


def test_preflight_passes_and_wrong_hash_is_refused(tmp_path):
    m = json.loads((PACKET / "packet-manifest.json").read_text())
    ok = _launch(tmp_path, m["archive_sha256"])
    assert ok.returncode == 0 and '"preflight": true' in ok.stdout
    bad = _launch(tmp_path, "0" * 64)
    assert bad.returncode == 9 and "refused" in bad.stdout


def test_preflight_fails_on_a_missing_file(tmp_path):
    m = json.loads((PACKET / "packet-manifest.json").read_text())
    job = tmp_path / "job"
    with tarfile.open(PACKET / m["archive"]) as tf:
        tf.extractall(job, filter="data")
    (job / "engineering/cfd3d/env_gpu/pins.tsv").unlink()
    r = subprocess.run([sys.executable, "-I", "engineering/cfd3d/gpu_entry.py"], cwd=job,
                       env=dict(os.environ, PREFLIGHT="1"), capture_output=True, text=True, timeout=60)
    assert r.returncode != 0


def test_avx512_repair_is_geometry_only_and_evidenced():
    pk = json.loads((ROOT / "engineering/cfd3d/packet.json").read_text())
    env = pk["geometry"]["numpy_env"]
    assert "X86_V4" in env["NPY_DISABLE_CPU_FEATURES"]
    src = (ROOT / "engineering/cfd3d/gpu_entry.py").read_text()
    assert src.count('PK["geometry"]["numpy_env"]') == 2          # the build call and its status record only
    ev = ROOT / env["evidence"]
    pin = (ART / "geometry/candidate.json").read_bytes()
    assert (ev / "candidate.no_avx512.json").read_bytes() == pin          # disabled dispatch reproduces the pin
    assert (ev / "candidate.default.json").read_bytes() != pin            # default AVX-512 dispatch does not
    d = json.loads((ev / "diff-pin-vs-cloud-default.json").read_text())
    assert d["n_differences"] == 3 and d["max_ulps"] <= 2 and not d["non_numeric"]


VLM = ART / "vlm"
V3 = ("fish3d-v3a-fan", "fish3d-v3b-glide-pose", "fish3d-v3c-daane-length")


def test_vlm_controls_pass_and_the_mutant_fails():
    r = json.loads((VLM / "controls.json").read_text())
    g = json.loads((ROOT / "engineering/cfd3d/gates_vlm.json").read_text())["controls"]
    assert set(g) <= set(r) and r["all_pass"] is True
    assert r["V5_mutant_collocation_quarter_chord"]["rel_err"] > g["V1_elliptic_AR6"]["pass"]["rel_err_max"]


def test_vlm_seg_vel_matches_an_infinite_line_vortex():
    v = _load("vlm")
    import numpy as np
    P = np.array([[0.0, 0.0, 1.0]])
    u = v.seg_vel(P, np.array([[-1e6, 0.0, 0.0]]), np.array([[1e6, 0.0, 0.0]]))[0, 0]
    assert u == pytest.approx([0.0, -1 / (2 * 3.141592653589793), 0.0], abs=1e-9)     # Gamma/(2 pi r), right-hand


@pytest.mark.parametrize("v", V3)
def test_vlm_fish_record_carries_its_candidate_and_conserves_force(v):
    import numpy as np
    r = json.loads((VLM / v / "vlm.json").read_text())
    assert len(r["candidate_sha256"]) == 64 and r["source"].endswith(v)
    assert all(m["modelled_as"].startswith("zero-thickness") for m in r["membrane"].values())
    assert set(r["dynamic_pressure_Pa"]) == {"air_20C", "water_20C"}
    for c in r["cases"].values():
        assert c["side_force_over_lift"] < 1e-9
        for f in c["fins"].values():
            assert f["transfer_vector_residual_over_gross"] < 1e-12
            assert len(f["quad_dCp"]) == len(f["quad_area_m2"]) == len(f["quad_upper_normal"])
            assert np.isfinite(f["quad_dCp"]).all()


GPU = ART / "gpu-v1"


def test_gpu_bundle_matches_its_receipt_and_keeps_the_failed_gate():
    r = json.loads((GPU / "receipt.json").read_text())
    for row in r["files"]:
        assert sha(GPU / row["path"]) == row["sha256"]
    st = json.loads((GPU / "status.json").read_text())
    assert st["reference_gate"]["C1_sphere_Re100"] == "FAIL" and "FAILED" in st["science"]
    assert r["candidate_sha256"] == json.loads((ART / "geometry/components.json").read_text())["candidate_sha256"]
    d = json.loads((GPU / "gpu_diag.json").read_text())
    assert abs(d["sphere_D32"]["Cd_mean"]) < 0.95            # still below the frozen band at D 32


def test_gpu_grid_pairs_never_make_a_force_claim():
    s = json.loads((ART / "summary-gpu-v1.json").read_text())
    assert len(s["grid_pairs"]) == 2 and all(p["physical_force_claim"] is False for p in s["grid_pairs"])


def test_vlm_v3b_is_flagged_not_converged():
    r = json.loads((VLM / "fish3d-v3b-glide-pose" / "vlm.json").read_text())
    assert r["status"].startswith("NOT CONVERGED")
    cl0 = [v[0] for v in r["convergence_sweep"]["bilinear_surface_normal"].values()]
    assert min(cl0) < 0 < max(cl0)                     # the sign itself is lattice-dependent
