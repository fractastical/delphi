import math
import json

import pytest
import torch

from engineering.windtunnel.geometry import mask_from_mesh
from engineering.windtunnel.geometry import ROOT
from engineering.windtunnel.lbm import LBM
from engineering.windtunnel.model import (
    no_body_control,
    request_parameters,
    run_request,
)


def test_mesh_projection_is_real_pinned_geometry_and_knobs_change_mask():
    mask, receipt = mask_from_mesh("N1-cypselurus-baseline", 24, 8.0, 1.0)
    thick, _ = mask_from_mesh("N1-cypselurus-baseline", 24, 8.0, 1.5)
    rotated, _ = mask_from_mesh("N1-cypselurus-baseline", 24, -8.0, 1.0)
    assert (
        receipt["sha256"]
        == "7582e66eff22a698f5f5a9710133e9200e5a4d4bc608e1b7f0f9f7ce7ab84043"
    )
    assert receipt["mesh_triangles"] > 1000 and mask.sum() > 8
    assert mask.shape == (288, 144)
    assert thick.sum() > mask.sum()
    assert not (mask == rotated).all()


def test_no_body_control_is_uniform_with_exactly_zero_integrated_force():
    torch.set_num_threads(2)
    control = no_body_control()
    assert control["passed"]
    assert control["max_force"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"speed_m_s": 12.0},
        {"speed_m_s": float("nan")},
        {"body_length_m": -1},
        {"aoa_deg": 90},
        {"length_cells": 10000},
        {"mesh_id": "../../private"},
        {"lattice_speed": 0.5},
        {"frames": True},
        {"kinematic_viscosity_m2_s": 0.001},
    ],
)
def test_domain_stability_and_resource_input_refusals(payload):
    with pytest.raises(ValueError):
        request_parameters(payload)


def test_low_re_physical_mapping_is_consistent_and_requires_real_prerequisite():
    p, re = request_parameters({})
    assert re == pytest.approx(80)
    nu_lattice = p["lattice_speed"] * p["length_cells"] / re
    dx = p["body_length_m"] / p["length_cells"]
    dt = p["lattice_speed"] * dx / p["speed_m_s"]
    assert nu_lattice * dx * dx / dt == pytest.approx(p["kinematic_viscosity_m2_s"])
    assert math.sqrt(3) * p["lattice_speed"] < 0.3
    with pytest.raises(ValueError, match="analytic"):
        run_request({}, "unused")


def test_actual_force_sign_mutant_is_detected_and_cannot_be_rendered(
    monkeypatch, tmp_path
):
    gate = json.loads(
        (ROOT / "artifacts/windtunnel/analytic-controls.json").read_text()
    )
    original = LBM.step

    def reversed_force(self, want_force=False):
        result = original(self, want_force=want_force)
        return tuple(-f for f in result) if want_force else result

    monkeypatch.setattr(LBM, "step", reversed_force)
    result = run_request(
        {"length_cells": 16, "convective_time": 0.5, "frames": 2},
        tmp_path / "negative",
        analytic_receipt=gate,
    )
    assert result["status"] == "FAIL"
    assert result["mean_Cd_last20pct"] < 0
    from engineering.windtunnel.render import render

    with pytest.raises(ValueError, match="failing"):
        render(tmp_path, case="negative")
