"""Lean-side checks. These run real Lean over Mathlib (about a minute); if Lean or the built project is
missing they SKIP and the receipt would say lean: "not_run" -- they never report a pass without running."""
import pytest

pytest.importorskip("z3")
from engineering.constraints import flying_fish_model, lean_conflict_certificate, q_speed_max, q_wl_min, solve  # noqa: E402
from engineering.formal import lean_checks  # noqa: E402

pytestmark = pytest.mark.skipif(not lean_checks.lean_available(), reason="Lean/Mathlib project not available")


@pytest.fixture(scope="module")
def lean():
    M = flying_fish_model(rho="1.225", CL="1")
    Q = [q_wl_min(150), q_speed_max(10)]
    cert = lean_conflict_certificate(M, solve(M, Q), Q)
    return lean_checks.run(cert)


def test_positive_file_compiles_with_standard_axioms_only(lean):
    assert lean["lean"] == "ran"
    assert lean["positive"]["exit"] == 0 and lean["positive"]["non_axiom_output"] == []
    assert lean["positive"]["only_standard_axioms"]
    assert lean["positive"]["n_axiom_prints"] == 7  # 3 theory theorems + 3 mutant refutations + the solver-emitted instance


def test_every_mutated_law_and_the_corrupted_certificate_is_rejected(lean):
    n = lean["negative"]
    assert n["exit"] != 0
    assert n["each_block_rejected"] == {"wl_k2": True, "mass_exponent": True, "stall_k2": True,
                                        "corrupted_certificate": True}
    assert n["errors_outside_blocks"] == []


def test_all_ok(lean):
    assert lean["all_ok"] is True
