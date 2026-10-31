import pytest

from frontier_compute.completion_report import compare


def row(identifier, arm="perturb", **changes):
    return {"id": identifier, "arm": arm, "amp": 1.0, "pattern": True, "mode": 2, "settled": True, "diverged": False, **changes}


def test_missing_and_changed_rows_are_not_silently_counted_as_passes():
    prior = [row(1, "base"), row(2, "base"), row(3)]
    result = compare(prior, [row(1, pattern=False, settled=False), row(3, amp=1.5)], [1, 2], [3])
    assert result["omitted_completion_ids"] == [2]
    assert result["pattern_flag_changes_vs_unperturbed"] == [1]
    assert result["settled_flag_changes_vs_unperturbed"] == [1]
    assert result["repeat_checks_passed"] is False
    assert result["repeat_failures"][0]["id"] == 3


def test_no_vacuous_repeat_or_unexpected_result_pass():
    with pytest.raises(ValueError, match="nonempty"):
        compare([], [], [1], [])
    with pytest.raises(ValueError, match="unexpected"):
        compare([row(1, "base"), row(2)], [row(1), row(2), row(9)], [1], [2])


def test_nonfinite_repeat_is_a_serializable_failure():
    import json

    result = compare([row(1, "base"), row(2)], [row(1), row(2, amp=float("nan"))], [1], [2])
    assert result["repeat_checks_passed"] is False
    json.dumps(result, allow_nan=False)
