import numpy as np

from engineering.aeroelastic import fidelity, fidelity_report, model


def test_rigid_CL_reuses_the_runner_and_flat_normals_only_replace_normals():
    fins = model.setup(4, 1)
    expected, _ = fidelity.fixed_area_CL(
        fins, {n: f["lattice"] for n, f in fins.items()}, 20.0
    )
    assert fidelity_report.rigid_CL(fins) == expected
    flat = fidelity_report.rigid_CL(fins, "flat")
    assert (
        np.isfinite(flat) and flat != expected
    )  # the source fins are not exactly planar
    assert all(
        not np.array_equal(f["lattice"]["N"], np.tile(f["geometry"]["n_up"], (4, 1)))
        for f in fins.values()
    )


def test_leg_clearance_excludes_own_legs_and_sees_a_point_on_another_leg():
    fins = model.setup(4, 1)
    clearance = fidelity_report.leg_clearance(fins)
    assert clearance.shape == (16,) and (clearance > 0).all()
    moved = {n: dict(f, lattice=dict(f["lattice"])) for n, f in fins.items()}
    first = moved["pectoral_L"]["lattice"]
    C = first["C"].copy()
    C[0] = first["A"][1] + np.array(
        [0.01, 0, 0]
    )  # on panel 1's trailing leg, downstream of its start
    first["C"] = C
    assert fidelity_report.leg_clearance(moved)[0] < 1e-12
