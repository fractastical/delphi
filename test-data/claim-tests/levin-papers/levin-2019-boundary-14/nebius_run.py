"""Fold the channel panel with ESMFold2 on Nebius.

Writes data/sequences/<acc>.fasta and data/structures/<acc>/{prediction.0.0.cif, confidence.json, run.json};
derived/runs.json keeps the operation IDs and checksums (data/ is gitignored).
Needs NEBIUS_SCIENTIFIC_AI_API_KEY. Safe to re-run: submissions are idempotent.

    python3 test-data/claim-tests/levin-papers/levin-2019-boundary-14/nebius_run.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "plugins" / "nebius"))
from fold import Client, uniprot, submit_esmfold, wait_all  # noqa: E402

PANEL = json.loads((HERE / "panel.json").read_text())


def main():
    data = HERE / "data"
    (data / "tmp").mkdir(parents=True, exist_ok=True)
    client = Client()
    seqs, ops = {}, {}
    for group in PANEL.values():
        for acc in group:
            seqs[acc] = uniprot(acc, data / "sequences")
    runs_path = HERE / "derived" / "runs.json"
    known = json.loads(runs_path.read_text()) if runs_path.exists() else {}
    for acc, s in seqs.items():
        ops[acc] = (known.get(acc) or {}).get("operation_id") or submit_esmfold(client, acc, s["sequence"], data / "tmp")
        print(f"{acc} ({len(s['sequence'])} aa): {ops[acc]}", flush=True)
    runs_path.parent.mkdir(exist_ok=True)
    runs_path.write_text(json.dumps({a: {"operation_id": o} for a, o in ops.items()}, indent=1))
    done = wait_all(client, ops, data / "structures")
    out = {acc: {"uniprot": {k: v for k, v in seqs[acc].items() if k != "sequence"},
                 "length": len(seqs[acc]["sequence"]), **done[acc]} for acc in ops}
    runs_path.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
