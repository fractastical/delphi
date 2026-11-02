#!/usr/bin/env python3
"""Existential UCS-memory screen for levin-2022-grn-learning-08.

Uses the same UCS-memory definition as levin-2022-grn-learning-11 and
recomputes it. Does not read that claim's measured.json.

    python3 analysis.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "levin-2022-grn-learning-11" / "analysis.py"


def load_screen():
    spec = importlib.util.spec_from_file_location("ucs_memory_screen", SRC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    screen = load_screen()
    models = screen.run_ids(list(screen.BIOMODELS), HERE / "cache", retention=False)
    decision = screen.decide_existential(models)
    testable = [m for m in models if m.get("testable")]
    payload = {
        "claim_id": "levin-2022-grn-learning-08",
        "decision": decision,
        "measured": {
            "value": decision["n_memories"],
            "unit": "UCS memories formed with SBML parameters left unchanged",
            "n": decision["n_testable"],
            "uncertainty": "deterministic given libroadrunner, the SBML files, and the tolerances recorded per model",
            "extra": {
                "verdict": decision["verdict"],
                "reason": decision["reason"],
                "confidence": decision["confidence"],
                "n_testable": decision["n_testable"],
                "n_memories": decision["n_memories"],
                "n_models_with_memory": decision["n_models_with_memory"],
                "parameters_edited": False,
                "per_model": [
                    {
                        "biomodel_id": m["biomodel_id"],
                        "table_s1_index": m["table_s1_index"],
                        "testable": m["testable"],
                        "reason": m["reason"],
                        "n_species": m["n_species"],
                        "n_memories": m["n_memories"],
                        "tolerances": m["tolerances"],
                    }
                    for m in models
                ],
            },
        },
        "examples": [
            {"biomodel_id": m["biomodel_id"], "examples": m["examples"]}
            for m in models if m.get("examples")
        ],
        "files": [m["file"] for m in models if m.get("file")],
    }
    out = HERE / "derived"
    out.mkdir(parents=True, exist_ok=True)
    (out / "measured.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
