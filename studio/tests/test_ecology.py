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


def test_biological_component_stl_uses_metres_not_print_millimetres():
    import json
    import trimesh
    from engineering.ecology.model import GEOM

    mesh = trimesh.load(GEOM / "components/body.stl", process=False)
    metadata = json.loads((GEOM / "components.json").read_text())
    bounds_m = np.asarray(metadata["components"]["body"]["check"]["bbox_mm"]) * 0.001
    assert np.allclose(mesh.bounds, bounds_m, atol=1e-8)
    assert 0.15 < np.ptp(mesh.bounds[:, 0]) < 0.17


def test_batch_endpoint_does_not_substitute_earlier_terminal_state():
    from engineering.ecology.batch import endpoint

    result = {"frames": [{"time_s": 0.5, "fish": []}]}
    value = endpoint(result, 0.6)
    assert not value["available"] and value["response_count"] is None


def test_batch_freezes_seven_axial_settings_and_paired_seed_design():
    import json
    from engineering.ecology.model import ART

    p = json.loads((ART / "uncertainty-protocol.json").read_text())
    assert len(p["settings"]) == 7
    assert len(p["settings"]) * len(p["seeds"]) * len(p["neighbor_modes"]) == 28
    assert p["endpoint_time_s"] == 0.6
    assert p["dt_s"] / p["half_dt_s"] == 2
