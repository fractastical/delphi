"""AlphaFold3 tetramers of mouse HCN2 (residues 131-520), wild type and GYG->AAA, on Nebius.

Writes data/<job>/{*_model.cif, *_summary_confidences.json, run.json}; derived/runs.json keeps
operation IDs and checksums (data/ is gitignored). Safe to re-run.

    python3 test-data/claim-tests/levin-papers/levin-2018-hcn2-16/nebius_run.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "plugins" / "nebius"))
from fold import Client, uniprot, submit_alphafold3, wait_all  # noqa: E402

ACC, START, END = "O88703", 131, 520
GYG = 402  # UniProt numbering of the selectivity-filter G of GYG


def constructs():
    u = uniprot(ACC, HERE / "data" / "sequences")
    full = u["sequence"]
    assert full[GYG - 1:GYG + 2] == "GYG", full[GYG - 4:GYG + 5]
    wt = full[START - 1:END]
    i = GYG - START
    aaa = wt[:i] + "AAA" + wt[i + 3:]
    return u, wt, aaa


def jobs(wt, aaa):
    def af3(name, chains):
        return {"name": name, "modelSeeds": [1], "dialect": "alphafold3", "version": 2,
                "sequences": [{"protein": {"id": ids, "sequence": s}} for ids, s in chains]}
    return {
        "wt4": af3("hcn2_wt4", [(["A", "B", "C", "D"], wt)]),
        "aaa1wt3": af3("hcn2_aaa1wt3", [(["A"], aaa), (["B", "C", "D"], wt)]),
        "aaa4": af3("hcn2_aaa4", [(["A", "B", "C", "D"], aaa)]),
    }


def main():
    data = HERE / "data"
    (data / "tmp").mkdir(parents=True, exist_ok=True)
    u, wt, aaa = constructs()
    client = Client()
    runs_path = HERE / "derived" / "runs.json"
    ops = {}
    for tag, fi in jobs(wt, aaa).items():
        ops[tag] = submit_alphafold3(client, f"hcn2-{tag}", fi, data / "tmp")
        print(f"{tag}: {ops[tag]}", flush=True)
    runs_path.parent.mkdir(exist_ok=True)
    runs_path.write_text(json.dumps({t: {"operation_id": o} for t, o in ops.items()}, indent=1))
    done = wait_all(client, ops, data, every=60)
    meta = {"uniprot": {k: v for k, v in u.items() if k != "sequence"}, "range": [START, END], "gyg": GYG}
    runs_path.write_text(json.dumps({"construct": meta, **done}, indent=1))


if __name__ == "__main__":
    main()
