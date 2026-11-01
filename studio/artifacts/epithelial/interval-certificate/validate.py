"""Pinned-source audit and actual Lean compiler receipt for the interval certificate.

Run inside the documented whole-tree resource scope. No solver, network, arbitrary command
or source generation is accepted. --prepare writes the declarative source witness artifact;
--check-only checks it without invoking Lean. A full run retains failed compiler receipts.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = "engineering/formalize/lean/ScaledThresholdIntervals.lean"
NEGATIVE = "engineering/formalize/lean/ScaledThresholdIntervalsNegative.lean"
OWNER_COMMIT = "3c65c17f93ccb22d13bde0b5a05a6c840a8c963b"
AUDIT_PATH = "artifacts/epithelial/sweep-audit.json"
AUDIT_SHA = "7a4c85fcfeb80643d2468bb54af39b99aec381e82e3121aca31dd9832680208c"
REVIEW_PATH = "artifacts/audits/epithelial-sweep/review.json"
REVIEW_SHA = "d083b080849219190931630144c4c4c0214cc8af2724d1aeab2c9cd22745ee41"
NAMES = [
    "factor_band_forces_endpoint_bound",
    "separated_intervals_reject_factor_band",
    "k4_recorded_intervals_reject_factor_two",
    "k7_recorded_intervals_reject_factor_two",
    "k4_interval_premises_nonempty",
    "k7_interval_premises_nonempty",
    "reverse_lower_counterexample",
    "reverse_upper_counterexample",
    "nonstrict_separation_counterexample",
    "dropped_factor_counterexample",
]
MUTATIONS = ["reverse_lower", "reverse_upper", "nonstrict_separation", "dropped_factor"]
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
RAW_DEFAULT = Path(
    "/data/artifacts/delphi-evolve-rethink/gcp/epithelial-j-scaling-v1/frontier-cpu-20261031-02/final-ae15a56498cc4a0e80ad1b00a7e7fc0c/science"
)


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def witness_document() -> dict:
    """Regenerate only declared source bindings, never inferred biological inputs."""
    source = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{OWNER_COMMIT}:{AUDIT_PATH}"]
    )
    reviewed = (ROOT / REVIEW_PATH).read_bytes()
    if digest(source) != AUDIT_SHA or digest(reviewed) != REVIEW_SHA:
        raise ValueError(
            "Pinned source audit or independent returned-data review changed"
        )
    audit, review = json.loads(source), json.loads(reviewed)
    if review["source_commit"] != OWNER_COMMIT or review["native_verdict"] != "FAIL":
        raise ValueError("Wrong source identity or native verdict")
    if not (
        review["all_30_brackets_match_native"]
        and review["all_240_models_match_frozen_packet"]
    ):
        raise ValueError("Missing nonempty source audit")
    cells = []
    for k in [4, 7]:
        for j in [35, 560]:
            label = f"k{k}-s1-J{j}"
            b = audit["brackets"][label]
            lo, hi = Fraction(str(b["lo"])), Fraction(str(b["hi"]))
            arms = []
            for value, expected_closed in [(lo, True), (hi, False)]:
                name = f"S-k{k}-J{j}-lamV{float(value):g}-s1"
                a = review["arms"][name]
                if a["closed_by_1000"] != expected_closed or a["rows"] <= 0:
                    raise ValueError("Missing or contradictory raw-arm source witness")
                arms.append(
                    {
                        "id": name,
                        "closed_by_1000": expected_closed,
                        "logger_sha256": a["logger_sha256"],
                        "rows": a["rows"],
                    }
                )
            cells.append(
                {
                    "id": label,
                    "k": k,
                    "seed": 1,
                    "J": j,
                    "lambda_bracket": [str(lo), str(hi)],
                    "scaled_ratio_interval": [str(lo / j), str(hi / j)],
                    "source_selector": f"brackets.{label}",
                    "arms": arms,
                }
            )
    if len(cells) != 4 or len({a["id"] for c in cells for a in c["arms"]}) != 8:
        raise ValueError("Empty, duplicate or incomplete witness collection")
    return {
        "schema": "frontier.epithelial-interval-source-witnesses/1",
        "source_audit": {
            "commit": OWNER_COMMIT,
            "path": AUDIT_PATH,
            "sha256": AUDIT_SHA,
        },
        "independent_review": {
            "commit": "d54b46d457deb83f1446c2fb8134f3f07cd34929",
            "path": REVIEW_PATH,
            "sha256": REVIEW_SHA,
        },
        "native_criterion_sha256": review["criterion_sha256"],
        "return_manifest_sha256": review["manifest_sha256"],
        "source_ensemble": {
            "arms": 240,
            "resolved_cells": 30,
            "stop_time_model_units": 1000,
            "observed_sample_times": "0,10,...,1000",
            "seeds_share_model": True,
        },
        "frozen_tolerance": "2",
        "cells": cells,
        "ratio_unit_scope": "lambda_V/J in fixed CPM model-unit convention; no SI calibration",
        "formal_instances": {
            "k4": {
                "x_cell": "k4-s1-J35",
                "y_cell": "k4-s1-J560",
                "a": "2/175",
                "b": "1/350",
                "t": "2",
            },
            "k7": {
                "x_cell": "k7-s1-J35",
                "y_cell": "k7-s1-J560",
                "a": "1/175",
                "b": "1/1400",
                "t": "2",
            },
        },
        "scope": "Conditional interval logic for sampled closure by horizon1000; not biology, untested monotonicity or asymptotic arrest.",
    }


def check_lean_binding(document: dict, text: str | None = None) -> None:
    """Compare actual Lean statement constants/directions to the pinned rational inputs."""
    text = (ROOT / SOURCE).read_text() if text is None else text

    def compact(value):
        return " ".join(value.split())

    cells = {c["id"]: c for c in document["cells"]}

    def literal(value):
        return f"({Fraction(value).numerator} : ℝ) / {Fraction(value).denominator}"

    for k in [4, 7]:
        pair = document["formal_instances"][f"k{k}"]
        name = f"k{k}_recorded_intervals_reject_factor_two"
        match = re.search(r"theorem " + name + r"\s+(.+?)\s*:= by", text, re.S)
        expected = (
            f"{{x y : ℝ}} (hx : 0 < x) (hy : 0 < y) "
            f"(hlo : {literal(pair['a'])} ≤ x) "
            f"(hhi : y ≤ {literal(pair['b'])}) : ¬ x ≤ 2 * y"
        )
        if match is None or compact(match[1]) != compact(expected):
            raise ValueError("Lean instance does not match pinned endpoints/tolerance")
        xlo, xhi = cells[pair["x_cell"]]["scaled_ratio_interval"]
        ylo, yhi = cells[pair["y_cell"]]["scaled_ratio_interval"]
        name = f"k{k}_interval_premises_nonempty"
        match = re.search(r"theorem " + name + r"\s*:\s*(.+?)\s*:= by", text, re.S)
        expected = (
            f"∃ x y : ℝ, 0 < x ∧ 0 < y ∧ "
            f"{literal(xlo)} ≤ x ∧ x ≤ {literal(xhi)} ∧ "
            f"{literal(ylo)} ≤ y ∧ y ≤ {literal(yhi)}"
        )
        if match is None or compact(match[1]) != compact(expected):
            raise ValueError(
                "Lean nonempty interval witness statement does not match source"
            )


def check_witnesses(document: dict, raw_root: Path | None = None) -> None:
    if document != witness_document():
        raise ValueError(
            "Witness bytes/values do not bind exactly to the pinned nonempty audit"
        )
    if raw_root is not None:
        for cell in document["cells"]:
            for arm in cell["arms"]:
                if (
                    digest((raw_root / arm["id"] / "logger.csv").read_bytes())
                    != arm["logger_sha256"]
                ):
                    raise ValueError("Native raw logger changed")
    check_lean_binding(document)
    # Endpoint constants in the Lean statements must also match the pinned witness ratios.
    for k in [4, 7]:
        pair = document["formal_instances"][f"k{k}"]
        cells = {c["id"]: c for c in document["cells"]}
        a = Fraction(cells[pair["x_cell"]]["scaled_ratio_interval"][0])
        b = Fraction(cells[pair["y_cell"]]["scaled_ratio_interval"][1])
        if a != Fraction(pair["a"]) or b != Fraction(pair["b"]) or not a > 2 * b:
            raise ValueError(
                "Actual interval endpoints do not exclude the declared tolerance"
            )


def command(argv: list[str], cwd: Path, env: dict, timeout: int = 300) -> dict:
    started = time.monotonic()
    p = subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    return {
        "argv": argv,
        "exit": p.returncode,
        "seconds": round(time.monotonic() - started, 3),
        "stdout": p.stdout.replace(str(ROOT) + "/", ""),
        "stderr": p.stderr.replace(str(ROOT) + "/", ""),
    }


def validate(raw_root: Path, project: Path) -> dict:
    document = json.loads((OUT / "source-witnesses.json").read_text())
    check_witnesses(document, raw_root)
    elan = Path.home() / ".elan/bin"
    env = os.environ.copy()
    env["ELAN_TOOLCHAIN"] = (project / "lean-toolchain").read_text().strip()
    env["LEAN_NUM_THREADS"] = "1"
    path_result = command(
        [str(elan / "lake"), "env", "printenv", "LEAN_PATH"], project, env, 60
    )
    if path_result["exit"] or not path_result["stdout"].strip():
        raise RuntimeError("Cached Mathlib project did not export LEAN_PATH")
    build = OUT / "build"
    build.mkdir(exist_ok=True)
    env["LEAN_PATH"] = str(build) + ":" + path_result["stdout"].strip()
    version = command([str(elan / "lean"), "--version"], ROOT, env, 30)
    manifest = json.loads((project / "lake-manifest.json").read_text())
    mathlib = next(p for p in manifest["packages"] if p["name"] == "mathlib")
    positive = command(
        [
            str(elan / "lean"),
            "-j1",
            "-o",
            str(build / "ScaledThresholdIntervals.olean"),
            str(ROOT / SOURCE),
        ],
        ROOT,
        env,
    )
    axiom_rows = re.findall(
        r"'ScaledThresholdIntervals\.(\w+)' depends on axioms: \[([^\]]*)\]",
        positive["stdout"],
    )
    axioms = {
        name: [v.strip() for v in text.split(",") if v.strip()]
        for name, text in axiom_rows
    }
    positive_ok = (
        positive["exit"] == 0
        and list(axioms) == NAMES
        and all(set(v) <= STANDARD_AXIOMS for v in axioms.values())
        and "sorryAx" not in positive["stdout"] + positive["stderr"]
    )
    negative = None
    ranges = {}
    if positive_ok:
        active = None
        for number, line in enumerate((ROOT / NEGATIVE).read_text().splitlines(), 1):
            if line.startswith("-- MUTATION-BEGIN "):
                active = line.split()[-1]
                ranges[active] = [number, None]
            if line.startswith("-- MUTATION-END "):
                if line.split()[-1] != active:
                    raise ValueError("Mismatched mutation block")
                ranges[active][1] = number
                active = None
        negative = command([str(elan / "lean"), "-j1", str(ROOT / NEGATIVE)], ROOT, env)
        errors = [
            int(n)
            for n in re.findall(
                r"ScaledThresholdIntervalsNegative\.lean:(\d+):\d+: error:",
                negative["stdout"] + negative["stderr"],
            )
        ]
        per_block = {
            name: [n for n in errors if lo < n < hi]
            for name, (lo, hi) in ranges.items()
        }
        outside = [
            n for n in errors if not any(lo < n < hi for lo, hi in ranges.values())
        ]
        negative.update(
            {
                "diagnostic_lines": errors,
                "each_block_rejected": {k: len(v) == 1 for k, v in per_block.items()},
                "errors_outside_blocks": outside,
                "unchanged_law_twins_compiled": not outside,
            }
        )
        negative_ok = (
            list(ranges) == MUTATIONS
            and negative["exit"] == 1
            and len(errors) == 4
            and not outside
            and all(negative["each_block_rejected"].values())
            and negative["stdout"].count("linarith failed to find a contradiction") == 4
        )
    else:
        negative_ok = False
    pins = [
        {"path": p, "sha256": digest((ROOT / p).read_bytes())}
        for p in [
            SOURCE,
            NEGATIVE,
            str((OUT / "source-witnesses.json").relative_to(ROOT)),
            str(Path(__file__).relative_to(ROOT)),
        ]
    ]
    result = {
        "schema": "frontier.epithelial-interval-lean-receipt/1",
        "status": "pass" if positive_ok and negative_ok else "fail",
        "source_pins": pins,
        "source_witnesses_checked": {
            "cells": 4,
            "raw_loggers": 8,
            "all_hashes_match": True,
        },
        "lean_version": version["stdout"].strip(),
        "toolchain": env["ELAN_TOOLCHAIN"],
        "mathlib": {
            "revision": mathlib["rev"],
            "manifest_sha256": digest((project / "lake-manifest.json").read_bytes()),
        },
        "positive": {
            **positive,
            "axioms_per_theorem": axioms,
            "only_standard_axioms": positive_ok,
            "expected_theorems": NAMES,
            "olean_sha256": digest(
                (build / "ScaledThresholdIntervals.olean").read_bytes()
            )
            if positive_ok
            else None,
        },
        "negative": negative,
        "mutation_roles": MUTATIONS,
        "scope": "Conditional interval algebra only. Does not prove source extraction, simulator fidelity, between-sample monotonicity, long-time arrest or biological validity.",
    }
    (OUT / "lean-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--raw-root", type=Path, default=RAW_DEFAULT)
    parser.add_argument(
        "--project", type=Path, default=Path("/data/artifacts/mathlib-probe")
    )
    args = parser.parse_args()
    if args.prepare:
        document = witness_document()
        (OUT / "source-witnesses.json").write_text(
            json.dumps(document, indent=2) + "\n"
        )
    if args.prepare or args.check_only:
        check_witnesses(
            json.loads((OUT / "source-witnesses.json").read_text()), args.raw_root
        )
        print("Four cells/eight raw loggers exactly bound to pinned source and review")
        return
    result = validate(args.raw_root, args.project)
    print(
        json.dumps(
            {
                "status": result["status"],
                "positive_exit": result["positive"]["exit"],
                "negative_exit": result["negative"]["exit"]
                if result["negative"]
                else None,
                "receipt": str((OUT / "lean-receipt.json").relative_to(ROOT)),
            }
        )
    )
    raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
