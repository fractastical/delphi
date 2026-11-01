"""Independent returned-data review; no solver import or simulation execution."""

from collections import defaultdict
from fractions import Fraction
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import csv
import json
import math
import re
import subprocess
import tarfile
import xml.etree.ElementTree as ET

OWNER = Path("/data/worktrees/delphi-frontier/epithelial-repair")
RETURN = Path(
    "/data/artifacts/delphi-evolve-rethink/gcp/epithelial-j-scaling-v1/frontier-cpu-20261031-02/final-ae15a56498cc4a0e80ad1b00a7e7fc0c"
)
COMMIT = "3c65c17f93ccb22d13bde0b5a05a6c840a8c963b"


def git(path, commit=COMMIT):
    return subprocess.check_output(
        ["git", "-C", str(OWNER), "show", f"{commit}:{path}"]
    )


def digest(data):
    return sha256(data).hexdigest()


def main():
    manifest = json.loads((RETURN / "collection_receipt.json").read_text())
    for item in manifest["artifacts"]:
        data = (RETURN / item["path"]).read_bytes()
        assert len(data) == item["bytes"] and digest(data) == item["sha256"], item[
            "path"
        ]
    native = json.loads((RETURN / "science/j-scaling-report.json").read_text())
    owner_audit = json.loads(git("artifacts/epithelial/sweep-audit.json"))
    with tarfile.open(
        fileobj=BytesIO(
            git("artifacts/epithelial/packet/epithelial-sweep-packet.tgz", "e2f74f2")
        ),
        mode="r:gz",
    ) as packet:
        criterion = packet.extractfile("analyze_sweep.py").read()
        specs = json.loads(packet.extractfile("arms.json").read())
        declared = {a["name"] for a in specs}
        assert len(declared) == len(specs) == 240
        assert digest(criterion) == native["criterion"]["criterion_sha256"]
        assert native["criterion"]["tolerance_ratio"] == 2
        cells = defaultdict(dict)
        results = {}
        total_rows = 0
        for name in sorted(declared):
            d = RETURN / "science" / name
            model = (d / "model.xml").read_bytes()
            assert model == packet.extractfile(f"models/{name}.xml").read()
            assert (d / "exit.txt").read_text().strip() == "exit=0"
            xml = ET.fromstring(model)
            assert float(xml.find("./Time/StopTime").get("value")) == 1000
            assert (
                float(xml.find("./CPM/MonteCarloSampler/MCSDuration").get("value")) == 1
            )
            volumes = defaultdict(float)
            ids = defaultdict(set)
            rows = 0
            with (d / "logger.csv").open() as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    t = float(row["time"])
                    v = float(row["cell.volume"])
                    assert math.isfinite(t) and math.isfinite(v)
                    volumes[t] += v
                    ids[t].add(row["cell.id"])
                    rows += 1
            ts = sorted(volumes)
            assert ts == list(range(0, 1001, 10))
            assert len({len(v) for v in ids.values()}) == 1
            gaps = {t: 40000 - volumes[t] for t in ts}
            assert all(v >= 0 and v == int(v) for v in gaps.values())
            match = re.fullmatch(r"S-k(\d+)-J([\d.]+)-lamV([\d.]+)-s(\d+)", name)
            k, j, lam, seed = match.groups()
            k, j, lam, seed = int(k), Fraction(j), Fraction(lam), int(seed)
            assert gaps[0] == k * 625
            closed = any(v == 0 for v in gaps.values())
            cells[k, seed, j][lam] = closed
            results[name] = {
                "k": k,
                "J": float(j),
                "lambda_V": float(lam),
                "seed": seed,
                "closed_by_1000": closed,
                "gap0": gaps[0],
                "gap1000": gaps[1000],
                "gap800_minus_gap1000": gaps[800] - gaps[1000],
                "logger_sha256": digest((d / "logger.csv").read_bytes()),
                "rows": rows,
            }
            total_rows += rows
    assert len(cells) == 30
    brackets = {}
    for (k, seed, j), states in sorted(cells.items()):
        closed = [lam for lam, yes in states.items() if yes]
        open_ = [lam for lam, yes in states.items() if not yes]
        assert len(states) == 8 and closed and open_ and max(closed) < min(open_)
        lo, hi = max(closed), min(open_)
        label = f"k{k}-s{seed}-J{j}"
        assert [float(lo), float(hi)] == native["resolved"][label]["bracket"]
        brackets[k, seed, j] = (lo / j, hi / j, lo, hi)
    per_gap = {}
    for k in [4, 7]:
        chosen = {key: value for key, value in brackets.items() if key[0] == k}
        largest_lower = max(v[0] for v in chosen.values())
        smallest_upper = min(v[1] for v in chosen.values())
        minimum_spread = max(Fraction(1), largest_lower / smallest_upper)
        # Construct a value in each interval that attains the lower bound; no optimizer needed.
        witness = [max(v[0], smallest_upper) for v in chosen.values()]
        assert all(v[0] <= w <= v[1] for v, w in zip(chosen.values(), witness))
        assert max(witness) / min(witness) == minimum_spread
        assert (
            float(minimum_spread)
            == owner_audit["interval_audit"][str(k)]["min_feasible_spread"]
        )
        endpoint = {}
        for j in [Fraction(35), Fraction(560)]:
            endpoint[str(j)] = [
                min(v[2] for key, v in chosen.items() if key[2] == j),
                max(v[3] for key, v in chosen.items() if key[2] == j),
            ]
        ratio_bounds = [
            endpoint["560"][0] / endpoint["35"][1],
            endpoint["560"][1] / endpoint["35"][0],
        ]
        per_seed = {}
        for seed in [1, 2, 3]:
            group = [v for key, v in chosen.items() if key[1] == seed]
            per_seed[str(seed)] = float(
                max(Fraction(1), max(v[0] for v in group) / min(v[1] for v in group))
            )
        per_gap[str(k)] = {
            "cells": len(chosen),
            "largest_ratio_lower_bound": str(largest_lower),
            "smallest_ratio_upper_bound": str(smallest_upper),
            "minimum_feasible_spread_exact": str(minimum_spread),
            "minimum_feasible_spread": float(minimum_spread),
            "attaining_witness_checked": True,
            "exceeds_frozen_tolerance_2": minimum_spread > 2,
            "per_seed_minimum_spread": per_seed,
            "endpoint_brackets": {
                j: [float(x) for x in v] for j, v in endpoint.items()
            },
            "endpoint_factor_bounds": [float(x) for x in ratio_bounds],
            "endpoint_secant_exponent_bounds": [
                math.log(float(x)) / math.log(16) for x in ratio_bounds
            ],
        }
    high_j = [
        dict(id=n, **r)
        for n, r in results.items()
        if r["J"] == 560 and not r["closed_by_1000"]
    ]
    out = {
        "schema": "frontier.epithelial-sweep-independent-review/1",
        "source_commit": COMMIT,
        "packet_commit": subprocess.check_output(
            ["git", "-C", str(OWNER), "rev-parse", "e2f74f2"]
        )
        .decode()
        .strip(),
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_files_rehashed": len(manifest["artifacts"]),
        "manifest_total_bytes_rehashed": sum(x["bytes"] for x in manifest["artifacts"]),
        "raw_rows": total_rows,
        "native_verdict": native["verdict"],
        "criterion_sha256": digest(criterion),
        "all_240_models_match_frozen_packet": True,
        "all_240_exit_zero": True,
        "all_240_have_101_finite_times_0_to_1000": True,
        "all_30_brackets_match_native": True,
        "spatial_frames": len(list((RETURN / "science").rglob("*.tif")))
        + len(list((RETURN / "science").rglob("*.tiff"))),
        "independent_interval_review": per_gap,
        "highest_J_nonclosed_arm_diagnostics": high_j,
        "arms": results,
        "source_pins": [
            {"path": p, "sha256": digest(git(p))}
            for p in [
                "engineering/epithelial/audit_return.py",
                "artifacts/epithelial/sweep-audit.json",
                "docs/epithelial-repair-card.md",
            ]
        ],
        "scope": "Same-model returned trajectories at fixed horizon, not independent biology or asymptotic arrest; no solver reruns.",
    }
    out["late_window_individual_counts"] = {
        f"k{k}-J{j}": {
            "nonclosed": sum(
                1
                for r in results.values()
                if r["k"] == k and r["J"] == j and not r["closed_by_1000"]
            ),
            "delta_gt_1": sum(
                1
                for r in results.values()
                if r["k"] == k
                and r["J"] == j
                and not r["closed_by_1000"]
                and r["gap800_minus_gap1000"] > 1
            ),
        }
        for k in [4, 7]
        for j in [35, 70, 140, 280, 560]
    }
    out["review_disposition"] = {
        "fixed_horizon_native_FAIL_supported": True,
        "main_interval_calculation_correct": True,
        "late_window_prose_requires_correction": True,
        "defect": "Across-seed mean diagnostics were described as every individual arm; actual k4 counts9/15 lowJ and1/12 highJ, not3/5 and0/4 individualarms.",
        "threshold_or_raw_data_change_requested": False,
        "long_horizon_outcome": "unknown",
        "spatial_media": "No lattice/TIFF frames; cell-center x/y and scalar summaries are logged, not cell boundaries.",
    }
    (Path(__file__).parent / "review.json").write_text(json.dumps(out, indent=2) + "\n")
    print(
        json.dumps(
            {
                "arms": len(results),
                "rows": total_rows,
                "minimum_feasible_spreads": {
                    k: v["minimum_feasible_spread"] for k, v in per_gap.items()
                },
                "highest_J_individual_positive_late_deltas": [
                    (r["id"], r["gap800_minus_gap1000"])
                    for r in high_j
                    if r["gap800_minus_gap1000"] > 1
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
