#!/usr/bin/env python3
"""Re-run this claim's pre-registered ODE test.

Thresholds are read from result.json and are not modified.
Requires: python3 -m pip install libroadrunner numpy requests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from protocol import apply_run, run, self_test

FROZEN = (
    "claim_id",
    "claim_iri",
    "project",
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "interpretation",
    "test_contract",
    "preregistration",
    "method_template",
    "specification_files",
    "created",
    "preregistered_at",
    "agent",
)


def main() -> None:
    here = Path(__file__).resolve().parent
    if "--self-test" in sys.argv:
        self_test()
        return
    spec = json.loads((here / "result.json").read_text())
    frozen = {k: spec.get(k) for k in FROZEN}
    payload = run(spec, here)
    out = apply_run(spec, payload)
    for key, value in frozen.items():
        if out.get(key) != value:
            raise SystemExit(f"frozen field changed: {key}")
    derived = here / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(payload["derived"], indent=2) + "\n")
    (here / "result.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({
        "claim_id": out["claim_id"],
        "verdict": out["verdict"],
        "reason": out.get("reason"),
        "confidence": out["confidence"],
        "n": out["measured"].get("n"),
        "data_kind": out["data_kind"],
    }, indent=2))


if __name__ == "__main__":
    main()
