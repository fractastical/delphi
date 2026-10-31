"""Publication adapter for the single fail-closed RD-DDPM collection auditor.

Raw primary files remain unchanged. The shared implementation checks identities,
counts, controls, timing, source/weight hashes, and every reported summary.
"""

import json
from pathlib import Path
import sys

from frontier_compute.diffusion_audit import (
    CODE_SHA, CONFIG_SHA, METHODS, NonFinite, audit as collection_audit,
    load_strict,
)

FROZEN = {"code_sha256": CODE_SHA, "config_sha256": CONFIG_SHA}
__all__ = ["FROZEN", "METHODS", "NonFinite", "audit", "load_strict"]


def audit(directory, control_path=None):
    """Keep publication field names while using exactly the collection criteria."""
    result = collection_audit(Path(directory), control_path)
    return {
        **result,
        "problems": result["failures"],
        "train_failed_runs_disclosed": result.get("training_failed_runs"),
        "note": "Complete means artifact completeness only, not model quality or biological validity. Nonfinite or missing results fail closed.",
    }


if __name__ == "__main__":
    result = audit(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["complete"] else 4)
