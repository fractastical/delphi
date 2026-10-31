"""Scale layer: Hayden 2021 Erk trigger waves + wave-gated growth.  Short horizons keep this under a minute."""
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest

from engineering.scales import erk_wave as M

ROOT = Path(__file__).resolve().parents[1]
SRC = json.loads((ROOT / "engineering/scales/sources.json").read_text())


@pytest.fixture(scope="module")
def std40():
    return M.simulate(M.Run(hours=40.0))


def test_parameters_are_table1_and_every_one_has_a_status():
    table = {p["name"]: p for p in SRC["parameters"]}
    for k, v in asdict(M.Params()).items():
        assert table[k]["value"] == v, k
    assert {p["status"] for p in SRC["parameters"]} <= {"fitted-in-source", "from-source", "measured", "assumed", "unknown"}
    assert table["growth.rate_after_peak_per_h"]["value"] == M.Growth().rate_after_peak_per_h
    assert table["growth.window_h"]["status"] == "assumed"


def test_no_source_means_nothing_happens():
    r = M.simulate(M.Run(hours=10.0, mode="no_source"))
    assert float(np.abs(r["E"]).max()) == 0.0 and r["area_um2"][-1] == r["area_um2"][0]


def test_standard_wave_speed_is_in_the_measured_band(std40):
    v = M.wave_speed(std40)["speed_um_per_h"]
    assert v is not None and 5.0 <= v <= 20.0


def test_positive_feedback_sign_mutant_has_no_wave():
    s = M.summary(M.simulate(M.Run(hours=40.0, mode="pf_sign_mutant")))
    assert s["cells_reached_fraction"] < 0.05 and s["wave_speed"]["speed_um_per_h"] is None


def test_growth_only_where_a_wave_has_passed(std40):
    reached = std40["n_peaks"] > 0
    grown = std40["loga"][-1] > 0
    assert grown[std40["scale"]].any()
    assert not (grown & ~reached).any()


def test_unstable_step_is_refused():
    with pytest.raises(ValueError):
        M.simulate(M.Run(hours=1.0, geometry=replace(M.Geometry(), dt_h=0.02)))


def test_committed_receipt_matches_files_and_code():
    out = ROOT / "artifacts/scales/erk-wave"
    rec = json.loads((out / "receipt.json").read_text())
    for name, f in rec["files"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == f["sha256"], name
    from engineering.scales import run as R
    assert rec["code_sha256"] == R.code_hash()
    assert rec["controls_pass"] is True
    assert rec["media"]["video"]["sha256"] == rec["files"]["erk_growth.mp4"]["sha256"]
