import json

import numpy as np
import pytest

from engineering.aeroelastic import model
from engineering.fin_mechanics import beam


def test_green_response_reuses_existing_FEM_and_matches_tip_law():
    response = model.Response(0.15, np.array([0.15]))
    x = np.linspace(0, 0.15, 51)
    w, _ = response.evaluate(x, np.array([0.37]), 2.5e-4)
    assert np.allclose(
        w, beam.w_point_load(x, 0.37, 0.15, 2.5e-4), rtol=1e-10, atol=1e-12
    )
    with pytest.raises(ValueError):
        response.evaluate(x, np.array([0.37]), 0.0)
    with pytest.raises(ValueError):
        response.evaluate(np.array([0.2]), np.array([0.37]), 1.0)


def test_full_reaction_ledger_detects_omitted_normal_load():
    fin = model.setup(4, 1)["pectoral_L"]
    lat = fin["lattice"]
    from engineering.cfd3d import vlm

    _, force, _, _ = vlm.solve(lat, 4)
    normal, valid = model.transfer(fin, lat, force)
    assert valid["passed"]
    altered = normal.copy()
    altered[int(abs(altered).argmax())] = 0
    assert not model.transfer(fin, lat, force, altered)[1]["passed"]


def test_zero_load_keeps_source_lattice_and_degenerate_area_is_refused():
    fin = model.setup(4, 1)["pectoral_L"]
    lat = fin["lattice"]
    new = model.deform(fin, np.zeros(len(lat["area"])), 1.0)
    assert all(np.array_equal(new[k], lat[k]) for k in ["A", "B", "C"])
    new["area"][0] = 0
    with pytest.raises(ValueError, match="Degenerate"):
        model.validate_lattice(new)


def test_saved_control_slice_contains_actual_feedback_and_glide_states():
    root = model.ART / "control-slice"

    def read(arm):
        return json.loads((root / arm / "result.json").read_text())

    rigid = read("rigid")
    one = read("one-way-frozen-load")
    two = read("two-way-static-feedback")
    assert all(x["local_control_not_production_arm"] for x in [rigid, one, two])
    assert two["status"] == "converged static feedback"
    assert (
        one["iterations"][-1]["CL_on_fixed_source_area"]
        != rigid["iterations"][-1]["CL_on_fixed_source_area"]
    )
    assert (
        two["iterations"][-1]["shape_residual_over_span"]
        <= model.protocol()["gates"]["fixed_point_shape_change_over_span_max"]
    )
    states = np.load(root / "two-way-static-feedback/static-states.npz")
    assert len(states["pectoral_L__quads_m"]) == len(two["iterations"])
    assert not np.array_equal(
        states["pectoral_L__quads_m"][0], states["pectoral_L__quads_m"][-1]
    )
    flight = np.load(root / "two-way-static-feedback/glide-main.npz")
    assert flight["time_s"][0] == 0 and np.all(np.diff(flight["time_s"]) > 0)
    assert two["flight"]["dt_gate_passed"]
