"""Compile the hand-authored Lean file(s) for the cantilever guard and write a receipt. An explicit, capped, local job: not part of the proposal endpoint.

Reuses engineering.formal.lean_checks (same project, same cap: MemoryMax=12G, MemorySwapMax=0, TasksMax=128). The Lean text here is written by a person
to correspond to constraints C1/C2 of the hand-authored cantilever fixture; it is NOT mechanically derived from any proposal, and the receipt says so."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from engineering.formal import lean_checks as LC

HERE = Path(__file__).resolve().parent / "lean"
POSITIVE = "CantileverGuard.lean"
NEGATIVE = "CantileverGuard_negative_corrupt_law.lean"
STANDARD = {"propext", "Classical.choice", "Quot.sound"}


def run() -> dict:
    if not LC.lean_available():
        return {"lean": "not_run", "reason": f"lake or built Mathlib project not found at {LC.PROJECT}"}
    pos_src, neg_src = (HERE / POSITIVE).read_text(), (HERE / NEGATIVE).read_text()
    pos, neg = LC._compile(pos_src, "CantileverGuard"), LC._compile(neg_src, "CantileverGuardNegative")
    axioms = re.findall(r"'([\w.]+)' depends on axioms: \[([^\]]*)\]", pos["out"])
    per = {name: sorted(a.strip() for a in lst.split(",") if a.strip()) for name, lst in axioms}
    errors_neg = [l for l in neg["out"].splitlines() if ": error" in l]
    return {
        "schema": "engineering.formalize.lean-receipt/1", "lean": "ran",
        "statement_origin": "hand-authored by the market worker to correspond to C1/C2 of the hand-authored cantilever fixture; not derived mechanically from any proposal and not an LLM output",
        "proves": "for all real P, L, E, I, d with P, L, E, I > 0: 3EId = PL^3 and 10 P L^2 <= 3EI imply d <= L/10 (algebra of the stated statement only)",
        "does_not_prove": ["that the Euler-Bernoulli end-load law models a fin ray", "that any real stiffness satisfies the hypothesis", "fidelity of the Lean text to any source passage", "anything about biology"],
        "files_sha256": {POSITIVE: hashlib.sha256(pos_src.encode()).hexdigest(), NEGATIVE: hashlib.sha256(neg_src.encode()).hexdigest()},
        "provenance": LC.provenance({}), "lean_version": LC.subprocess.run(["lean", "--version"], capture_output=True, text=True).stdout.strip(),
        "positive": {"exit": pos["exit"], "seconds": pos["seconds"], "axioms_per_theorem": per, "only_standard_axioms": bool(per) and all(set(v) <= STANDARD for v in per.values()),
                     "theorems": sorted(per), "warnings_note": "the linter reports hP unused: the guard does not need P > 0"},
        "negative_corrupt_law": {"exit": neg["exit"], "seconds": neg["seconds"], "rejected": neg["exit"] != 0 and bool(errors_neg), "first_error": re.sub(r"^\S*/(\w+\.lean)", r"\1", errors_neg[0] if errors_neg else "")[-160:]},
        "caps": "systemd-run --user --scope MemoryMax=12G MemorySwapMax=0 TasksMax=128 RuntimeMaxSec=600",
    }


if __name__ == "__main__":
    out = run()
    (HERE / "RECEIPT.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: out.get(k) for k in ("lean", "positive", "negative_corrupt_law")}, sort_keys=True)[:900])
    sys.exit(0 if out.get("lean") == "ran" and out["positive"]["exit"] == 0 and out["negative_corrupt_law"]["rejected"] else 1)
