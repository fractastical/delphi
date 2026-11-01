import numpy as np

from engineering.ecology.model import FLIP, aero, build, protocol


def test_actual_polar_and_geometry_pins_and_si_mass():
    p = protocol()
    m, d, g, ids, _ = build(1, p["parameters"], p["solver"]["dt_s"])
    assert abs(m.body_mass.sum() - 0.05) < 1e-12
    assert 0.15 < g["length_m"] < 0.17
    assert len(ids[0]["joints"]) == 4
    assert np.linalg.det(FLIP) == 1
    assert np.allclose(d.qpos[3:7], [1, 0, 0, 0])


def test_lift_is_orthogonal_and_drag_dissipative_with_mutation():
    velocity = np.array([20.0, 2.0, -1.0])
    normal = np.array([0.0, 0.0, 1.0])
    lift, drag = aero(velocity, normal, 0.005, 0.5, 0.08, 1.204)
    assert abs(np.dot(lift, velocity)) < 1e-12
    assert np.dot(drag, velocity) < 0
    assert np.dot(-drag, velocity) > 0
