import math

import numpy as np

from engineering.aeroelastic import fidelity, model
from engineering.cfd3d import vlm


def series(values):
    return dict(zip(["main", "fine", "l32x8", "l36x9", "l64x16"], values, strict=True))


def ladder(limit, constant, order):
    """E(h) = limit + constant h^order on the protocol's five lattices, h = 16 / span."""
    spans = {"main": 16, "fine": 24, "l32x8": 32, "l36x9": 36, "l64x16": 64}
    return {m: limit + constant * (16 / s) ** order for m, s in spans.items()}


def test_triple_recovers_order_and_limit_and_names_bad_behaviour():
    exact = fidelity.triple([1 + 0.04, 1 + 0.01, 1 + 0.0025], 2.0)
    assert exact["behaviour"] == "monotone"
    assert math.isclose(exact["p"], 2.0, rel_tol=1e-12)
    assert math.isclose(exact["extrapolated"], 1.0, rel_tol=1e-12)
    assert fidelity.triple([1.0, 1.1, 1.05], 2.0)["behaviour"] == "oscillatory"
    assert fidelity.triple([1.0, 1.1, 1.3], 2.0)["behaviour"] == "divergent"
    assert (
        fidelity.triple([0.25, 0.25, 0.25], 2.0)["behaviour"] == "roundoff_insensitive"
    )


def test_classify_resolves_a_clean_ladder_and_refuses_sign_change_and_floor():
    fp = fidelity.fprotocol()
    clean = ladder(-0.0059, 0.0004, 2.0)
    assert fidelity.classify(clean, 1e-9, fp)["status"] == "resolved"
    flipped = ladder(1e-6, -4e-6, 1.0)  # crosses zero between lattices
    result = fidelity.classify(flipped, 1e-12, fp)
    assert result["status"] == "not_resolved"
    assert "sign changes across lattices" in result["reasons"]
    floored = fidelity.classify(clean, 1e-3, fp)
    assert floored["status"] != "resolved"
    assert "finest value below 10x numerical floor" in floored["reasons"]
    noisy = series([-0.0059, -0.0060, -0.0058, -0.0061, -0.0059])
    assert fidelity.classify(noisy, 1e-9, fp)["status"] in (
        "sign_resolved",
        "not_resolved",
    )


def test_decide_applies_frozen_thresholds_only_to_resolved_effects():
    fp = fidelity.fprotocol()

    def effects(bending, feedback):
        return {
            "dCL_one_way_minus_rigid": fidelity.classify(
                ladder(bending, 0.1 * bending, 2.0), 1e-12, fp
            ),
            "dCL_two_way_minus_one_way": fidelity.classify(
                ladder(feedback, 0.1 * feedback, 2.0), 1e-12, fp
            ),
            "CL_rigid": fidelity.classify(ladder(0.25, 0.001, 2.0), 0.0, fp),
        }

    strong = fidelity.decide(effects(-0.0059, 9e-5))
    assert strong["bending"]["decision"] == "retain_bending"
    assert strong["feedback"]["decision"] == "one_way_sufficient"
    weak = fidelity.decide(effects(-0.0013, 4e-6))
    assert weak["bending"]["decision"] == "reject_bending"
    coupled = fidelity.decide(effects(-0.0059, 1e-3))
    assert coupled["feedback"]["decision"] == "two_way_needed"
    unresolved = effects(-0.0059, 9e-5)
    unresolved["dCL_one_way_minus_rigid"] = fidelity.classify(
        series([-0.0059, -0.0050, -0.0070, -0.0040, -0.0080]), 1e-12, fp
    )
    assert fidelity.decide(unresolved)["bending"]["decision"] == "undetermined"


def test_independent_transfer_fails_mutations_the_ledger_identities_pass():
    fins = model.setup(4, 1)
    fin = fins["pectoral_L"]
    _, unit, _, _ = vlm.solve(fin["lattice"], 4)
    force = unit * 1.204 * 20**2
    EI = model.protocol()["parameters"]["EI_inputs"]["pectoral_L"][
        "EI_Nm2_by_compliance"
    ]["0.8"]
    assert all(fidelity.independent_transfer(fin, force, EI)["checks"].values())
    shifted = dict(
        fin, response=model.Response(fin["length"], 0.8 * fin["response"].stations)
    )
    assert model.transfer(shifted, fin["lattice"], force)[1][
        "passed"
    ]  # bookkeeping cannot see it
    bad = fidelity.independent_transfer(shifted, force, EI)["checks"]
    assert not bad["stations"] and not bad["beam_equilibrium"]
    swapped = dict(fin, geometry=dict(fin["geometry"], n_up=fin["geometry"]["ew"]))
    assert model.transfer(swapped, fin["lattice"], force)[1]["passed"]
    bad = fidelity.independent_transfer(swapped, force, EI)["checks"]
    assert not bad["axis"] and not bad["beam_equilibrium"]


def test_scale_checks_catch_unit_and_factor_two_slips():
    fins = model.setup(
        16, 4
    )  # the production main lattice: 1.2-1.7% from the upstream 48x16 force
    _, force = fidelity.fixed_area_CL(
        fins, {n: f["lattice"] for n, f in fins.items()}, 20.0
    )
    assert all(fidelity.scale_checks(fins, force, 20.0)["checks"].values())
    assert not fidelity.scale_checks(fins, force / (1.204 * 400), 20.0)["checks"][
        "upstream_force"
    ]
    doubled = fidelity.scale_checks(fins, 2 * force, 20.0)["checks"]
    assert not doubled["thin_airfoil_bound"] and not doubled["upstream_force"]


def test_protocol_keeps_original_physics_pinned_and_rejects_changed_reference(tmp_path):
    fp = fidelity.fprotocol()
    fidelity.check_references(fp)
    assert set(fp["lattices"]) == {"main", "fine", "l32x8", "l36x9", "l64x16"}
    assert all(fidelity.override(fp, m) is None for m in ["main", "fine"])
    altered = dict(
        fp,
        references=[dict(fp["references"][0], sha256="0" * 64)] + fp["references"][1:],
    )
    try:
        fidelity.check_references(altered)
    except ValueError as exc:
        assert "Packed reference changed" in str(exc)
    else:
        raise AssertionError("changed reference accepted")
    assert np.isclose(sum(1 for _ in fp["references"]), 18)
