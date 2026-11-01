"""smedinx-11 hemichannel (AlphaFold3 octamer) and alkanol docking (DiffDock) on Nebius.

Step 1 folds the octamer into data/octamer/. Step 2 docks each ligand into it, 3 seeds x 4 poses,
into data/dock/<ligand>-s<seed>/. derived/runs.json keeps operation IDs and checksums
(data/ is gitignored). Safe to re-run.

    python3 test-data/claim-tests/levin-papers/levin-2015-girardia-11/nebius_run.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "plugins" / "nebius"))
from fold import Client, uniprot, submit_alphafold3, wait_all  # noqa: E402

ACC, START, END, COPIES = "A7RDN9", 1, 370, 8
LIGANDS = {"ethanol": 702, "hexanol": 8103, "heptanol": 8129, "octanol": 957, "carbenoxolone": 636403}  # PubChem CIDs
SEEDS = (1, 2, 3)


def octamer_input(seq):
    chains = [chr(ord("A") + i) for i in range(COPIES)]
    return {"name": "smedinx11_octamer", "modelSeeds": [1], "dialect": "alphafold3", "version": 2,
            "sequences": [{"protein": {"id": chains, "sequence": seq[START - 1:END]}}]}


def main():
    data = HERE / "data"
    (data / "tmp").mkdir(parents=True, exist_ok=True)
    u = uniprot(ACC, data / "sequences")
    client = Client()
    runs_path = HERE / "derived" / "runs.json"
    runs = json.loads(runs_path.read_text()) if runs_path.exists() else {}
    runs_path.parent.mkdir(exist_ok=True)
    op = submit_alphafold3(client, "smedinx11-octamer", octamer_input(u["sequence"]), data / "tmp")
    runs["octamer"] = {"operation_id": op}
    runs["construct"] = {"uniprot": {k: v for k, v in u.items() if k != "sequence"}, "range": [START, END], "copies": COPIES}
    runs_path.write_text(json.dumps(runs, indent=1))
    print(f"octamer: {op}", flush=True)
    runs["octamer"] = wait_all(client, {"octamer": op}, data, every=60)["octamer"]
    runs_path.write_text(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main()
