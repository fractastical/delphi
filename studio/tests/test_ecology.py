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


def test_missing_only_continuation_rejects_recipe_change_and_repeated_case():
    import copy
    import pytest
    from engineering.ecology.continuation import validate_missing_tasks

    original = {
        "settings": [{"id": "hinge-stiff", "overrides": {"fin_stiffness_Nm_rad": 0.3}}],
        "seeds": [1, 2],
        "neighbor_modes": [True, False],
    }
    tasks = [
        {
            "id": f"hinge-stiff-s2-{'neighbors' if mode else 'ablated'}",
            "setting": "hinge-stiff",
            "overrides": {"fin_stiffness_Nm_rad": 0.3},
            "seed": 2,
            "neighbors": mode,
        }
        for mode in [True, False]
    ]
    done = ["hinge-stiff-s1-neighbors", "hinge-stiff-s1-ablated"]
    summary = {
        "results": [{"id": name, "status": "computed"} for name in done]
        + [
            {"id": task["id"], "status": "not-started: soft deadline reached"}
            for task in tasks
        ]
    }
    cfg = {"tasks": tasks, "prohibited_already_computed_ids": done}
    assert validate_missing_tasks(cfg, summary, original) == tasks
    changed = copy.deepcopy(cfg)
    changed["tasks"][0]["overrides"]["fin_stiffness_Nm_rad"] = 0.4
    with pytest.raises(ValueError, match="recipe changed"):
        validate_missing_tasks(changed, summary, original)
    changed = copy.deepcopy(cfg)
    changed["tasks"][0]["id"] = done[0]
    with pytest.raises(ValueError, match="repeat/change"):
        validate_missing_tasks(changed, summary, original)
