import ast
import csv
import math
from pathlib import Path


def helper():
    source = Path("frontier_compute/vendor/compute_ops/warm_worker.py").read_text()
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "gpu_window"
    )
    namespace = {"csv": csv, "math": math}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), "<gpu-window>", "exec"),
        namespace,
    )
    return namespace["gpu_window"]


def test_actual_samples_only(tmp_path):
    path = tmp_path / "device.csv"
    path.write_text(
        "timestamp,gpu,memory,used,total,power,temp\n"
        "2026/11/01 03:00:00.000,0,0,100,80000,70,30\n"
        "2026/11/01 03:00:01.000,50,0,200,80000,90,31\n"
        "2026/11/01 03:00:02.000,100,0,300,80000,100,32\n"
        "partial,999\n"
    )
    result = helper()(path)
    assert result["samples"] == 3 and result["gpu_utilization_pct_mean"] == 50
    assert result["gpu_memory_used_mib_max"] == 300
    assert result["window_device_clock"] == [
        "2026/11/01 03:00:00.000",
        "2026/11/01 03:00:02.000",
    ]


def test_unavailable_is_not_zero_utilization(tmp_path):
    path = tmp_path / "device.csv"
    path.write_text("time,N/A,0,100,1,1,1\ntime,nan,0,100,1,1,1\n")
    assert helper()(path) is None
