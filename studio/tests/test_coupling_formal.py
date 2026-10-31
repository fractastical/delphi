"""Lean arithmetic receipt for the coupling layer (about a minute; SKIPS if Lean/Mathlib is absent)."""
import pytest

from engineering.formal import lean_checks, unit_algebra_checks

pytestmark = pytest.mark.skipif(not lean_checks.lean_available(), reason="Lean/Mathlib project not available")


@pytest.fixture(scope="module")
def res():
    return unit_algebra_checks.run()


def test_positive_file_compiles_with_standard_axioms(res):
    assert res["lean"] == "ran" and res["positive"]["exit"] == 0 and res["positive"]["errors"] == []
    assert res["positive"]["only_standard_axioms"] and res["positive"]["axiom_prints"] == 6


def test_every_mutated_law_is_rejected_inside_its_own_block(res):
    assert res["negative"]["exit"] != 0 and res["negative"]["errors_outside_blocks"] == []
    assert res["negative"]["each_block_rejected"] == {k: True for k in unit_algebra_checks.BLOCKS}


def test_scope_statement_is_arithmetic_only(res):
    assert "no biological correspondence" in res["scope"] and res["all_ok"] is True
