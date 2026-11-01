"""Independent raw-log/TIFF recomputation. No native solver runs or owner writes."""

from pathlib import Path
from hashlib import sha256
from collections import defaultdict, Counter
from io import StringIO
import argparse
import csv
import json
import math
import subprocess

import numpy as np
from PIL import Image


def audit(owner, runs, commit, output):
    def raw(path):
        return subprocess.check_output(
            ["git", "-C", str(owner), "show", commit + ":" + path]
        )

    protocols = [
        json.loads(raw("artifacts/epithelial/" + name))
        for name in ("protocol.json", "protocol-r2.json")
    ]
    assert raw("artifacts/epithelial/protocol.json") == subprocess.check_output(
        ["git", "-C", str(owner), "show", "5293180:artifacts/epithelial/protocol.json"]
    )
    assert raw("artifacts/epithelial/protocol-r2.json") == subprocess.check_output(
        [
            "git",
            "-C",
            str(owner),
            "show",
            "d0f7864:artifacts/epithelial/protocol-r2.json",
        ]
    )
    result = json.loads(raw("artifacts/epithelial/results-r2.json"))
    specs = [a for p in protocols for a in p["arms"]]
    assert len(specs) == len({a["name"] for a in specs}) == 36
    report = []
    for spec in specs:
        name = spec["name"]
        d = runs / name
        build = json.loads((d / "build.json").read_text())
        run = json.loads((d / "run.json").read_text())
        assert build["arm"] == spec and run["exit"] == 0
        assert (
            sha256((d / "model.xml").read_bytes()).hexdigest() == build["model_sha256"]
        )
        assert build["binary_sha256"] == protocols[0]["engine"]["binary_sha256"]
        assert build == json.loads(
            raw("artifacts/epithelial/arms/" + name + "/build.json")
        )
        assert run == json.loads(raw("artifacts/epithelial/arms/" + name + "/run.json"))
        by = defaultdict(list)
        for row in csv.DictReader(
            StringIO((d / "logger.csv").read_text()), delimiter="\t"
        ):
            assert all(math.isfinite(float(x)) for x in row.values())
            by[float(row["time"])].append(row)
        times = sorted(by)
        vol = {t: sum(float(r["cell.volume"]) for r in by[t]) for t in times}
        gap = {t: 40000 - vol[t] for t in times}
        counts = {t: len({int(float(r["cell.id"])) for r in by[t]}) for t in times}
        assert len(set(counts.values())) == 1
        assert all(len(by[t]) == counts[t] for t in times)
        g0 = gap[times[0]]
        ge = gap[times[-1]]
        closed = next((t for t in times if gap[t] <= 0), None)
        frac = 1 - ge / g0 if g0 > 0 else None
        state = (
            "UNWOUNDED" if g0 <= 0 else "CLOSED" if closed is not None else "ARRESTED"
        )
        target = result["arms"][name]
        assert (g0, ge, frac, state, closed, counts[times[0]]) == (
            target["gap0"],
            target["gap_end"],
            target["closed_fraction"],
            target["state"],
            target["closure_time"],
            target["n_cells"],
        )
        tif = d / "cell.id.tif"
        im = Image.open(tif)
        matches = 0
        unmatched = []
        first_ids = None
        for i in range(im.n_frames):
            im.seek(i)
            array = np.array(im)
            t = i * spec["frame_step"]
            assert array.shape == (200, 200)
            if i == 0:
                first_ids = len(np.unique(array[array != 0]))
            if t in gap:
                assert int((array == 0).sum()) == gap[t]
                matches += 1
            else:
                unmatched.append(t)
        assert first_ids == counts[times[0]]
        report.append(
            {
                "name": name,
                "n_initial_cell_ids_logger_and_TIFF": first_ids,
                "initial_volume_nodes": vol[times[0]],
                "initial_gap_nodes": g0,
                "end_gap_nodes": ge,
                "closed_fraction": frac,
                "state_operational": state,
                "first_logged_closure_model_time": closed,
                "first_logged_closure_sweeps": closed / spec["mcs"]
                if closed is not None and g0
                else None,
                "mcs_duration": spec["mcs"],
                "t_end": times[-1],
                "last_5_gap_values": [gap[t] for t in times[-5:]],
                "TIFF_frames": im.n_frames,
                "frames_matched_to_logger": matches,
                "frames_without_logger_same_time": len(unmatched),
                "model_sha256": build["model_sha256"],
                "logger_sha256": sha256((d / "logger.csv").read_bytes()).hexdigest(),
                "TIFF_sha256": sha256(tif.read_bytes()).hexdigest(),
            }
        )
    byname = {r["name"]: r for r in report}
    gates = Counter(
        "pass" if g["passed"] is True else "fail" if g["passed"] is False else "null"
        for g in result["gates"]
    )
    detail = {g["id"]: g for g in result["gates"]}
    f1 = byname["F1-no-drive-NEGATIVE"]
    unwounded = byname["A5-unwounded-POSITIVE"]

    def coefficient(A, N, J):
        return A * A / (N * J * 2 * math.sqrt(math.pi * A))

    intervals = {
        str(k): [
            0.3 * coefficient(625 * k, 65 - k, 140),
            coefficient(625 * k, 65 - k, 140),
        ]
        for k in (4, 7)
    }
    overlap = [
        max(v[0] for v in intervals.values()),
        min(v[1] for v in intervals.values()),
    ]
    assert overlap[0] < overlap[1]
    d_closed = [
        s["lambda_v"]
        for s in specs
        if s["name"].startswith("D-k4-J280-")
        and byname[s["name"]]["state_operational"] == "CLOSED"
    ]
    d_arrested = [
        s["lambda_v"]
        for s in specs
        if s["name"].startswith("D-k4-J280-")
        and byname[s["name"]]["state_operational"] == "ARRESTED"
    ]
    assert (
        [max(d_closed), min(d_arrested)]
        == detail["G9"]["detail"]["measured_bracket"]
        == [1, 2]
    )
    output.mkdir(parents=True, exist_ok=True)
    out = {
        "reviewed_commit": commit,
        "raw_native_runs": 36,
        "native_reruns": 0,
        "protocols_unchanged": True,
        "run_model_binary_pins_match_recorded": True,
        "gate_counts": dict(gates),
        "gate_classification": {
            "pass": 8,
            "fail": 3,
            "descriptive_no_threshold": ["G6"],
            "unevaluable": ["G8"],
        },
        "arms": report,
        "TIFF_coverage": {
            "total_frames": sum(r["TIFF_frames"] for r in report),
            "matched": sum(r["frames_matched_to_logger"] for r in report),
            "unmatched": sum(r["frames_without_logger_same_time"] for r in report),
            "mismatched_at_shared_time": 0,
            "scope": "Shared-engine readout consistency at common times; not all written times or independent biology",
        },
        "initialization": {
            "actual_unwounded_cells": unwounded["n_initial_cell_ids_logger_and_TIFF"],
            "actual_mean_nodes": 40000
            / unwounded["n_initial_cell_ids_logger_and_TIFF"],
            "nominal_target_nodes": 625,
            "first_wounded_cells": byname["A1-baseline"][
                "n_initial_cell_ids_logger_and_TIFF"
            ],
        },
        "passive_control": {
            "observed_closed_fraction": f1["closed_fraction"],
            "filled_nodes": f1["initial_gap_nodes"] - f1["end_gap_nodes"],
            "end_gap_nodes": f1["end_gap_nodes"],
            "idealized_target_residual_nodes": 40000 - 61 * 625,
            "idealized_target_filled_nodes": 61 * 625 - 37500,
            "scope": "Condition-specific no-protrusion/no-J control still includes other CPM terms; target-volume relaxation is a plausible explanation, not isolated causal apportionment",
        },
        "heldout_J": {
            "observed_bracket": [1, 2],
            "geometric_mean_summary": math.sqrt(2),
            "predicted_bracket_from_prior_simulation": [0.6, 2.0],
            "one_internal_setting_test_at_k": 4,
            "horizon_model_units": 1000,
            "scope": "Compatible finite-horizon bracket result, not measured exact threshold, independent biology or verified full J-linearity/k7 transfer",
        },
        "gap_size_Phi_bracket_intervals": intervals,
        "Phi_interval_overlap": overlap,
        "scope": "Reused model simulation/numerical evidence only; no biological or time calibration",
    }
    (output / "audit.json").write_text(
        json.dumps(out, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "arms": len(report),
                "gate_counts": dict(gates),
                "TIFFcoverage": out["TIFF_coverage"],
                "actual_initial_cells": unwounded["n_initial_cell_ids_logger_and_TIFF"],
                "passive_fraction": f1["closed_fraction"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-root", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.owner_root.resolve(), args.runs.resolve(), args.commit, args.output)
