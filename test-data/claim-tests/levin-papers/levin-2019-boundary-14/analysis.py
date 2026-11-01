"""TM-align the animal sensory channels and controls against the bacterial channels.

Reads the ESMFold2 structures written by nebius_run.py and writes derived/tm_scores.json
(every pair, TM-score normalised by the bacterial chain) and derived/summary.json (verdict
inputs under the pre-registered rules in result.json).

    uv run --with tmtools --with gemmi --with numpy \
        test-data/claim-tests/levin-papers/levin-2019-boundary-14/analysis.py
"""
import json
from pathlib import Path

import gemmi
import numpy as np
from tmtools import tm_align

HERE = Path(__file__).resolve().parent
PANEL = json.loads((HERE / "panel.json").read_text())
SENSES = ("touch", "temperature", "taste", "hearing")
SAME_FOLD, MARGIN, MIN_PLDDT = 0.50, 0.10, 50.0


def tags(acc):
    """Structure directories for a protein: itself, or its windows if it was folded in pieces."""
    root = HERE / "data" / "structures"
    whole = root / acc / "prediction.0.0.cif"
    return [acc] if whole.exists() else sorted(p.parent.name for p in root.glob(f"{acc}_w*/prediction.0.0.cif"))


def load(tag):
    st = gemmi.read_structure(str(HERE / "data" / "structures" / tag / "prediction.0.0.cif"))
    ca = [(r, r.find_atom("CA", "*")) for r in st[0][0]]
    ca = [(r, a) for r, a in ca if a]
    coords = np.array([[a.pos.x, a.pos.y, a.pos.z] for _, a in ca])
    seq = gemmi.one_letter_code([r.name for r, _ in ca])
    b = np.array([a.b_iso for _, a in ca])
    plddt = float(b.mean() * (100 if b.max() <= 1.0 else 1))
    return coords, seq, plddt


def main():
    accs = [acc for g in PANEL.values() for acc in g]
    missing = [a for a in accs if not tags(a)]
    if missing:
        raise SystemExit(f"no structure yet for {missing}; run nebius_run.py")
    structs = {t: load(t) for a in accs for t in tags(a)}
    bacterial = list(PANEL["bacterial"])
    others = [a for g, accs_ in PANEL.items() if g != "bacterial" for a in accs_]
    tm = {}
    for a in others:
        for b in bacterial:
            best = None
            for t in tags(a):
                r = tm_align(structs[t][0], structs[b][0], structs[t][1], structs[b][1])
                row = {"tm_norm_bacterial": round(float(r.tm_norm_chain2), 4),
                       "tm_norm_animal": round(float(r.tm_norm_chain1), 4), "rmsd": round(float(r.rmsd), 2), "piece": t}
                if best is None or row["tm_norm_bacterial"] > best["tm_norm_bacterial"]:
                    best = row
            tm[(a, b)] = best
    plddt = {a: round(float(np.mean([structs[t][2] for t in tags(a)])), 1) for a in accs}
    name = {acc: n for g in PANEL.values() for acc, n in g.items()}

    glut1 = {b: tm[("P11166", b)]["tm_norm_bacterial"] for b in bacterial}
    senses = {}
    for sense in SENSES:
        best, rows = None, []
        for a in PANEL[sense]:
            for b in bacterial:
                s = tm[(a, b)]["tm_norm_bacterial"]
                row = {"animal": name[a], "bacterial": name[b], "tm": s, "glut1_tm": glut1[b],
                       "margin": round(s - glut1[b], 4), "plddt": plddt[a]}
                rows.append(row)
                ok = plddt[a] >= MIN_PLDDT
                if ok and (best is None or (s, row["margin"]) > (best["tm"], best["margin"])):
                    best = row
        determined = any(plddt[a] >= MIN_PLDDT for a in PANEL[sense])
        shared = bool(best and best["tm"] >= SAME_FOLD and best["margin"] >= MARGIN)
        senses[sense] = {"determined": determined, "shared": shared, "best": best,
                         "best_overall_tm": max(r["tm"] for r in rows)}

    pos = tm[("P16389", "P0A334")]["tm_norm_bacterial"]
    neg = {name[n]: max(tm[(n, b)]["tm_norm_bacterial"] for b in bacterial) for n in PANEL["negative_control"]}
    controls_ok = pos >= SAME_FOLD and all(v < SAME_FOLD for v in neg.values())
    n_shared = sum(s["shared"] for s in senses.values())
    if not controls_ok:
        verdict = "inconclusive"
    elif n_shared == 4:
        verdict = "supports"
    elif n_shared == 0 and all(s["determined"] for s in senses.values()):
        verdict = "refutes"
    else:
        verdict = "mixed"

    (HERE / "derived").mkdir(exist_ok=True)
    (HERE / "derived" / "tm_scores.json").write_text(json.dumps(
        [{"animal_or_control": name[a], "animal_acc": a, "bacterial": name[b], "bacterial_acc": b, **v}
         for (a, b), v in tm.items()], indent=1))
    summary = {"verdict": verdict, "senses_shared": n_shared, "senses": senses,
               "positive_control_kcna2_vs_kcsa": pos, "negative_controls_best_tm": neg,
               "controls_ok": controls_ok, "mean_plddt": {name[a]: p for a, p in plddt.items()}}
    (HERE / "derived" / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
