"""Score HCN2 WT vs GYG->AAA tetramers against the pre-registered criteria.

Reads AlphaFold3 outputs from data/<job>/ (written by nebius_run.py) and, when present,
stab-ddG results from derived/ddg.json (written by ddg_run.py). Writes derived/summary.json.
`--control-residue` prints the chain-A residue with the most inter-subunit contacts (the
sensitivity-control site) and its PDB export, for ddg_run.py.

    uv run --with gemmi --with numpy test-data/claim-tests/levin-papers/levin-2018-hcn2-16/analysis.py
"""
import json
import sys
from pathlib import Path

import gemmi
import numpy as np

HERE = Path(__file__).resolve().parent
JOBS = ("wt4", "aaa1wt3", "aaa4")
START, GYG = 131, 402


def files(job, suffix):
    hits = sorted((HERE / "data" / job).glob(f"*{suffix}"))
    if not hits:
        raise FileNotFoundError(f"{job}: no *{suffix}")
    return hits[0]


def confidences(job):
    c = json.loads(files(job, ".json" if not (HERE / "data" / job / "summary-confidence.json").exists()
                         else "summary-confidence.json").read_text())
    return {"iptm": c.get("iptm"), "ptm": c.get("ptm"), "ranking_score": c.get("ranking_score"),
            "chain_pair_iptm": c.get("chain_pair_iptm")}


def wt_structure():
    st = gemmi.read_structure(str(files("wt4", ".cif")))
    st.setup_entities()
    return st


def control_residue(st):
    """Chain-A residue with the most heavy-atom contacts (<= 4 A) to other chains."""
    ns = gemmi.NeighborSearch(st[0], st.cell, 5).populate()
    counts = {}
    a = st[0]["A"]
    for res in a:
        n = 0
        for atom in res:
            for m in ns.find_atoms(atom.pos, "\0", radius=4.0):
                cra = m.to_cra(st[0])
                if cra.chain.name != "A":
                    n += 1
        counts[(res.seqid.num, res.name)] = n
    (num, name), n = max(counts.items(), key=lambda kv: kv[1])
    return {"residue_number": num, "uniprot_number": num + START - 1,
            "wild_type": gemmi.find_tabulated_residue(name).one_letter_code.upper(), "contacts": n}


def main():
    if "--control-residue" in sys.argv:
        st = wt_structure()
        out = HERE / "data" / "wt4" / "wt4.pdb"
        st.remove_ligands_and_waters()
        st.write_pdb(str(out))
        print(json.dumps({"pdb": str(out), "control": control_residue(st),
                          "gyg_model_numbers": [GYG - START + 1 + i for i in range(3)]}))
        return
    conf = {j: confidences(j) for j in JOBS}
    wt, het = conf["wt4"]["iptm"], conf["aaa1wt3"]["iptm"]
    ddg_path = HERE / "derived" / "ddg.json"
    ddg = json.loads(ddg_path.read_text()) if ddg_path.exists() else None

    checks = {"wt_iptm_ok": wt >= 0.60, "het_within_0.10": het >= wt - 0.10, "het_drop_over_0.20": het < wt - 0.20}
    if ddg:
        aaa, ctl = ddg["aaa"]["ddg"], ddg["control"]["ddg"]
        checks.update({"aaa_ddg_le_1": aaa <= 1.0, "aaa_ddg_ge_2": aaa >= 2.0, "control_sensitive": ctl >= 2.0})
    if not checks["wt_iptm_ok"] or (ddg and not checks["control_sensitive"]):
        verdict = "inconclusive"
    elif ddg is None:
        verdict = "pending-ddg"
    elif checks["het_within_0.10"] and checks["aaa_ddg_le_1"]:
        verdict = "supports"
    elif checks["aaa_ddg_ge_2"] or checks["het_drop_over_0.20"]:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {"verdict": verdict, "alphafold3": conf, "stab_ddg": ddg, "checks": checks}
    (HERE / "derived").mkdir(exist_ok=True)
    (HERE / "derived" / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
