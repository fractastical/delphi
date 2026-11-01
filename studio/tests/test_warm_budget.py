import pytest
from frontier_compute.vendor.compute_ops.warm_budget import queue_budget


def test_three_hour_science_is_not_silently_clamped():
    assert queue_budget(
        {"max_wall_s": 11400, "margin_s": 60, "workloads": [{"timeout_s": 11280}]}
    ) == (11400, 60)


@pytest.mark.parametrize(
    "maximum,timeout", [(7200, 11280), (14401, 100), (float("nan"), 100), (100, 100)]
)
def test_impossible_or_unbounded_queue_rejected(maximum, timeout):
    with pytest.raises(ValueError):
        queue_budget({"max_wall_s": maximum, "workloads": [{"timeout_s": timeout}]})


def test_old_forty_minute_nca_budget_unchanged():
    assert queue_budget(
        {"max_wall_s": 2800, "margin_s": 60, "workloads": [{"timeout_s": 2500}]}
    ) == (2800, 60)
