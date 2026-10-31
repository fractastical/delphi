"""Tests for engineering/rd_diffusion. Hand-worked expectations; the batched solver is compared with the existing scipy/numpy rd_frames solver."""
import hashlib, json, math, os, sys
from pathlib import Path

import numpy as np
import pytest
torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engineering" / "rd_diffusion"))
import rd_ddpm as R

CFG = R.CFG


def test_dct_matrix_matches_scipy_orthonormal_dct2():
    from scipy.fft import dct
    for n in (8, 64, 81):
        assert np.abs(R.dct_matrix(n).numpy() - dct(np.eye(n), type=2, norm="ortho", axis=0)).max() < 1e-13


def test_dominant_mode_of_a_pure_cosine_basis_function_is_its_index():
    n = 64; x = (np.arange(n) + 0.5)
    for k in (1, 3, 11):
        assert int(R.dominant_mode(np.cos(k * math.pi * x / n))) == k                 # cos(k pi (j+1/2)/N) is exactly DCT-II basis k


def test_batched_torch_solver_reproduces_the_existing_numpy_solver_for_the_frozen_schnakenberg_cell():
    from fractions import Fraction as Fr
    from engineering.simulation import rd_frames as rf
    cells = json.loads((ROOT / "engineering/simulation/rd/cells.json").read_text())["cells"]; c = [x for x in cells if x["model"] == "schnakenberg"][0]
    c = {**c, "T_tau": 10.0}; t, U, V, _ = rf.run_cell(c, save_every=2.0)
    a, b = float(Fr(c["params"]["a"])), float(Fr(c["params"]["b"])); d = float(Fr(c["Dv"])); L, n = c["L"], c["NA"]
    ust, vst = a + b, b / (a + b) ** 2; pu, pv = R.ic_modal(c["seed"], c["K"], L, n, c["eps"] * abs(ust), c["eps"] * abs(vst))
    T = lambda x: torch.tensor(np.atleast_1d(np.asarray(x, float)), dtype=torch.float64)
    u, v, sv = R.advance(T(ust + pu)[None] if False else torch.tensor((ust + pu)[None]), torch.tensor((vst + pv)[None]), T(a), T(b), T(d), T(L), 500, save_steps=[100, 200, 300, 400, 500], D=R.dct_matrix(n))
    for k, (uu, vv) in enumerate(sv, start=1):
        assert np.abs(uu.numpy()[0] - U[k]).max() < 1e-9 and np.abs(vv.numpy()[0] - V[k]).max() < 1e-9, k


def test_uniform_steady_state_is_preserved_when_the_perturbation_is_zero():
    P = np.array([[0.1, 0.9, 20.0, 40.0], [0.2, 0.7, 12.0, 55.0]]); f, bad = R.simulate(P, np.array([1, 2]), "cpu", eps=0.0, save_tau=[5.0])
    ust = P[:, 0] + P[:, 1]; vst = P[:, 1] / ust ** 2
    assert not bad.any() and np.abs(f[:, 0, 0] - ust[:, None]).max() < 1e-10 and np.abs(f[:, 0, 1] - vst[:, None]).max() < 1e-10


def test_failed_runs_are_flagged_not_dropped_silently():
    P = np.array([[0.1, 0.9, 20.0, 40.0], [5.0, 0.0001, 20.0, 40.0]]); f, bad = R.simulate(P, np.array([1, 2]), "cpu", eps=5.0, save_tau=[40.0])
    assert f.shape[0] == 2 and (bad.dtype == bool) and (f[bad] == 0).all()


def test_split_design_is_disjoint_and_seeds_never_reused():
    sp = CFG["splits"]; ids = lambda n: set(range(*sp[n]["setting_ids"]))
    assert not (ids("train") & ids("test_param")) and not (ids("train") & ids("dev")) and not (ids("dev") & ids("test_param")) and max(ids("test_param")) < CFG["n_settings"]
    assert ids("ensemble") <= ids("test_param") and ids("test_seed") <= ids("train")
    seeds = lambda n: set(R.split_seeds(sp[n]))
    assert not (seeds("train") & seeds("test_seed")) and not (seeds("test_param") & seeds("ensemble")) and len(seeds("ensemble")) == 32
    keys = [{s * 1000 + j for s in ids(n) for j in seeds(n)} for n in ("train", "dev", "test_param", "test_seed", "ensemble")]
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            assert not (keys[i] & keys[j]), (i, j)                                      # no (setting, seed) initial condition appears in two splits


def test_settings_table_is_reproducible_and_inside_the_prior():
    t1, t2 = R.settings_table(), R.settings_table(); assert np.array_equal(t1, t2) and t1.shape == (CFG["n_settings"], 4)
    for i, k in enumerate("abdL"): assert t1[:, i].min() >= CFG["prior"][k][0] and t1[:, i].max() <= CFG["prior"][k][1]


def test_ens_metrics_hand_worked():
    n = 64; x = np.arange(n) + 0.5; D = R.dct_matrix(n)
    mk = lambda k, amp: np.stack([1.0 + amp * np.cos(k * math.pi * x / n), 2.0 + 0 * x])
    sol = np.stack([mk(3, 0.5)] * 8); same = R.ens_metrics(sol.copy(), sol, D)
    assert same["mode_tv"] == 0 and same["amp_w1_rel"] == 0 and same["mode_agree_argmax"] and same["negative_frac"] == 0 and same["nonfinite_frac"] == 0
    other = R.ens_metrics(np.stack([mk(5, 0.5)] * 8), sol, D); assert other["mode_tv"] == 1.0 and not other["mode_agree_argmax"] and other["amp_w1_rel"] < 1e-9     # same amplitude, other mode
    half = np.stack([mk(3, 0.5)] * 4 + [mk(5, 0.5)] * 4); assert R.ens_metrics(half, sol, D)["mode_tv"] == 0.5
    big = R.ens_metrics(np.stack([mk(3, 1.0)] * 8), sol, D); assert big["amp_mean_rel_err"] == pytest.approx(1.0, rel=1e-9)             # amplitude doubled
    neg = sol.copy(); neg[0, 0, 0] = -0.1; assert R.ens_metrics(neg, sol, D)["negative_frac"] == pytest.approx(1 / 8)
    nan = sol.copy(); nan[0] = np.nan; m = R.ens_metrics(nan, sol, D); assert m["nonfinite_frac"] == pytest.approx(1 / 8) and np.isfinite(m["mode_tv"])
    allnan = R.ens_metrics(np.full_like(sol, np.nan), sol, D); assert allnan["nonfinite_frac"] == 1.0 and allnan["mode_tv"] == 1.0 and allnan["amp_w1_rel"] == float("inf")


def test_training_statistics_come_from_the_rows_it_is_given_only(tmp_path):
    rng = np.random.default_rng(0); f = (rng.standard_normal((40, 2, 64)) * np.array([2.0, 5.0])[None, :, None] + np.array([1.0, -3.0])[None, :, None]).astype(np.float32)
    c = np.stack([rng.uniform(*CFG["prior"][k], 40) for k in ("a", "b", "d", "L", "t")], 1).astype(np.float32)
    tc = dict(CFG["train"], steps=2, batch=8, log_every=1); _, mean, std, *_ = R.train(c, f, tc, "cpu", str(tmp_path))
    assert np.allclose(mean[0, :, 0], f.mean((0, 2))) and np.allclose(std[0, :, 0], f.std((0, 2))) and (tmp_path / "checkpoint.pt").exists()


def test_condition_scaling_maps_the_prior_range_to_minus_one_one():
    lo = np.array([[CFG["prior"][k][0] for k in ("a", "b", "d", "L", "t")]], np.float32); hi = np.array([[CFG["prior"][k][1] for k in ("a", "b", "d", "L", "t")]], np.float32)
    assert np.allclose(R.cscale(lo), -1) and np.allclose(R.cscale(hi), 1)


def test_network_shape_zero_flux_padding_and_schedule():
    net = R.Net(); out = net(torch.randn(3, 2, 64), torch.tensor([0, 10, 199]), torch.randn(3, 5)); assert out.shape == (3, 2, 64) and 2e6 > sum(p.numel() for p in net.parameters()) > 1e6
    assert all(m.padding_mode == "replicate" for m in net.modules() if isinstance(m, torch.nn.Conv1d) and m.kernel_size == (3,) and m.stride == (1,))
    beta, alpha, abar = R.schedule(200, "cpu"); assert len(beta) == 200 and float(abar[0]) > 0.99 and float(abar[-1]) < 0.01 and (abar[1:] < abar[:-1]).all()


def test_packet_files_match_manifest_and_stay_small():
    d = ROOT / "engineering" / "rd_diffusion"; man = json.loads((d / "MANIFEST.json").read_text())
    for f, h in man["sha256"].items(): assert hashlib.sha256((d / f).read_bytes()).hexdigest() == h, f
    assert sum((d / f).stat().st_size for f in man["sha256"]) < 45_000


def test_preregistration_pins_the_frozen_config_and_code():
    d = ROOT / "engineering" / "rd_diffusion"; text = (d / "PREREG.md").read_text()
    for f in ("config.json", "rd_ddpm.py"): assert hashlib.sha256((d / f).read_bytes()).hexdigest() in text, f
