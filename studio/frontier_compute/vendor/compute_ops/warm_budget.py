"""Validate declared warm-worker durations without silently clamping them."""

import math


def queue_budget(queue):
    maximum = float(queue.get("max_wall_s", 7200))
    margin = float(queue.get("margin_s", 60))
    if not math.isfinite(maximum) or not 0 < maximum <= 14400:
        raise ValueError("Warm queue duration must be positive and at most14400s")
    if not math.isfinite(margin) or not 0 <= margin < maximum:
        raise ValueError("Invalid warm queue margin")
    workloads = queue.get("workloads")
    if not isinstance(workloads, list) or not 1 <= len(workloads) <= 100:
        raise ValueError("Warm queue must contain1..100workloads")
    for workload in workloads:
        duration = float(workload["timeout_s"])
        if not math.isfinite(duration) or not 0 < duration <= maximum - margin:
            raise ValueError(
                "Workload duration plus margin exceeds declared queue bound"
            )
    return maximum, margin
