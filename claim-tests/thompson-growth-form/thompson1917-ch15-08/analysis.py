#!/usr/bin/env python3
"""thompson1917-ch15-08: are S. mansoni and S. haematobium one species?

Pairwise uncorrected p-distances between GenBank cox1 sequences (derived/schistosoma_cox1.fasta,
from fetch.py). Each pair is aligned with Biopython's PairwiseAligner in local mode (match 2,
mismatch -3, gap open -5, extend -2; both orientations tried, best score kept) and the
p-distance is mismatches / aligned nucleotide columns, counted only where both sequences have
A/C/G/T; pairs with fewer than 300 such columns are discarded.
"""
import itertools
import json
import os

import numpy as np
from Bio import SeqIO
from Bio.Align import PairwiseAligner
from Bio.Seq import Seq

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_OVERLAP = 300

aligner = PairwiseAligner()
aligner.mode = "local"
aligner.match_score = 2
aligner.mismatch_score = -3
aligner.open_gap_score = -5
aligner.extend_gap_score = -2


def p_distance(a, b):
    best = None
    for cand in (b, str(Seq(b).reverse_complement())):
        aln = aligner.align(a, cand)
        if len(aln) == 0:
            continue
        al = aln[0]
        if best is None or al.score > best.score:
            best = al
    if best is None:
        return None
    mism = 0
    cols = 0
    for (s1, e1), (s2, e2) in zip(*best.aligned):
        x, y = best.target[s1:e1], best.query[s2:e2]
        for c1, c2 in zip(x, y):
            if c1 in "ACGT" and c2 in "ACGT":
                cols += 1
                mism += c1 != c2
    if cols < MIN_OVERLAP:
        return None
    return mism / cols, cols


def main():
    recs = list(SeqIO.parse(os.path.join(HERE, "derived", "schistosoma_cox1.fasta"), "fasta"))
    seqs, species = [], []
    for r in recs:
        sp = r.description.split("[")[1].split("]")[0]
        seqs.append(str(r.seq).upper())
        species.append(sp)
    n = len(seqs)
    D = {}
    for i, j in itertools.combinations(range(n), 2):
        pd_ = p_distance(seqs[i], seqs[j])
        if pd_ is not None:
            D[(i, j)] = pd_[0]

    def group(sp1, sp2):
        vals = [d for (i, j), d in D.items() if {species[i], species[j]} == ({sp1, sp2} if sp1 != sp2 else {sp1})
                and (species[i] == sp1 and species[j] == sp2 or species[i] == sp2 and species[j] == sp1)]
        if not vals:
            return {"n_pairs": 0}
        v = np.array(vals)
        return {"n_pairs": int(v.size), "mean": round(float(v.mean()), 4), "median": round(float(np.median(v)), 4),
                "min": round(float(v.min()), 4), "max": round(float(v.max()), 4)}

    M, H = "Schistosoma mansoni", "Schistosoma haematobium"
    out = {"n_sequences": n, "n_pairs_with_overlap": len(D),
           "n_by_species": {sp: species.count(sp) for sp in sorted(set(species))},
           "within_mansoni": group(M, M), "within_haematobium": group(H, H),
           "mansoni_vs_haematobium": group(M, H),
           "reference_recognised_species_pairs": {
               "haematobium_vs_bovis": group(H, "Schistosoma bovis"),
               "mansoni_vs_rodhaini": group(M, "Schistosoma rodhaini"),
               "haematobium_vs_curassoni": group(H, "Schistosoma curassoni"),
               "haematobium_vs_guineensis": group(H, "Schistosoma guineensis"),
               "haematobium_vs_intercalatum": group(H, "Schistosoma intercalatum"),
               "mansoni_vs_japonicum": group(M, "Schistosoma japonicum")},
           "within_other_species": {sp: group(sp, sp) for sp in ("Schistosoma bovis", "Schistosoma rodhaini",
                                                                  "Schistosoma japonicum", "Schistosoma curassoni")}}
    mh = out["mansoni_vs_haematobium"]
    wm, wh = out["within_mansoni"], out["within_haematobium"]
    gap = mh["min"] > max(wm["max"], wh["max"])
    hb = out["reference_recognised_species_pairs"]["haematobium_vs_bovis"]["mean"]
    mr = out["reference_recognised_species_pairs"]["mansoni_vs_rodhaini"]["mean"]
    overlap = mh["min"] < min(wm["max"], wh["max"])
    if mh["mean"] <= 0.03 or overlap:
        verdict = "supports"
    elif gap and mh["mean"] >= 0.10 and mh["mean"] >= hb and mh["mean"] >= mr:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["decision"] = {"barcode_gap_mansoni_haematobium": gap, "mean_between": mh["mean"],
                       "max_within": max(wm["max"], wh["max"]), "mean_haematobium_bovis": hb,
                       "mean_mansoni_rodhaini": mr, "verdict": verdict}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
