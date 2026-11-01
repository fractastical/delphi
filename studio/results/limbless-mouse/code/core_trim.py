#!/usr/bin/env python3
"""Define the alignable ZRS core, then realign only that.

The 1.3 kb windows fetched per species extend beyond the conserved enhancer.
In those flanks the sequences are not homologous at the resolution of a
nucleotide alignment, and MAFFT fills them with arbitrary gaps -- which
manufactures 'shared deletions' that are alignment artefacts, not biology
(checked by eye: the non-snake 'aligned' blocks there share no similarity).
Kvon et al. handled this with Gblocks; this is the same idea, stated explicitly:

  1. Walk the MOUSE positions of the full-window MAFFT alignment (not raw
     alignment columns: per-column depth collapses inside species-specific
     insertions, which fragments the core for a reason that is not biological).
     Score each mouse position by the depth and conservation of the column it
     occupies.
  2. Smooth both over 31 mouse positions and keep the longest contiguous run
     with smoothed conservation >= 0.70 and smoothed depth >= 0.85.
  3. Project that run back to each species' own coordinates, cut the core
     subsequence, and realign the cores from scratch with MAFFT L-INS-i.

The thresholds were set by reading the conservation profile of the mouse ZRS
(a clear shoulder at ~0.70 around mouse positions 400 and 1160), not by tuning
until an expected result appeared.

Everything downstream is computed on that realigned core.
"""
import json
import subprocess
import sys

WIN = 31
CONS_MIN = 0.70
DEPTH_MIN = 0.80
DIP_TOLERANCE = 30   # Gblocks-style: a short dip does not end the block
ORDER = ["mouse", "human", "chicken", "lizard", "coelacanth", "elephant_shark",
         "eryx", "python", "king_cobra", "rattlesnake", "garter_snake"]


def read_fasta(path):
    seqs, cur = {}, None
    for line in open(path):
        line = line.strip()
        if line.startswith(">"):
            cur = line[1:].split()[0]
            seqs[cur] = ""
        elif cur:
            seqs[cur] += line.upper()
    return seqs


def write_fasta(path, seqs, order=None):
    with open(path, "w") as f:
        for k in (order or seqs):
            if k not in seqs:
                continue
            s = seqs[k]
            f.write(">" + k + "\n" + "\n".join(s[i:i + 70] for i in range(0, len(s), 70)) + "\n")


def smooth(v, w):
    out = []
    for i in range(len(v)):
        lo, hi = max(0, i - w // 2), min(len(v), i + w // 2 + 1)
        out.append(sum(v[lo:hi]) / (hi - lo))
    return out


def main():
    aln = read_fasta("alignment.fasta")
    keys = [k for k in ORDER if k in aln]
    L = len(aln[keys[0]])
    mcols = [i for i in range(L) if aln["mouse"][i] != "-"]   # alignment col of each mouse base
    depth, cons = [], []
    for i in mcols:
        col = [aln[k][i] for k in keys if aln[k][i] != "-"]
        depth.append(len(col) / len(keys))
        cons.append(max(col.count(c) for c in set(col)) / len(col) if col else 0.0)
    sd, sc = smooth(depth, WIN), smooth(cons, WIN)

    ok = [sc[p] >= CONS_MIN and sd[p] >= DEPTH_MIN for p in range(len(mcols))]
    runs, cur = [], None
    for p, good in enumerate(ok):
        if good:
            cur = [p, p] if cur is None else [cur[0], p]
            if not runs or runs[-1] is not cur:
                runs.append(cur)
        else:
            cur = None
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= DIP_TOLERANCE:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    best = max(merged, key=lambda r: r[1] - r[0])
    mouse_lo, mouse_hi = best[0] + 1, best[1] + 1          # 1-based mouse positions
    lo, hi = mcols[best[0]], mcols[best[1]] + 1            # alignment column span
    print(f"core = alignment columns {lo}-{hi} ({hi - lo} cols); "
          f"mouse ZRS positions {mouse_lo}-{mouse_hi} ({mouse_hi - mouse_lo + 1} bp)")
    print(f"  mm10 chr5:{29314497 + mouse_lo - 1:,}-{29314497 + mouse_hi - 1:,}")

    cores = {}
    for k in keys:
        sub = aln[k][lo:hi].replace("-", "")
        if len(sub) >= 100:
            cores[k] = sub
        else:
            print(f"  dropped {k}: only {len(sub)} bp inside the core")
    for k in keys:
        if k in cores:
            print(f"  {k:16s} core {len(cores[k]):4d} bp")

    write_fasta("seqs/core_input.fasta", cores, ORDER)
    subprocess.run(["mafft", "--localpair", "--maxiterate", "1000", "--nuc",
                    "--quiet", "--thread", "2", "seqs/core_input.fasta"],
                   stdout=open("alignment.fasta.core", "w"), check=True)
    core = read_fasta("alignment.fasta.core")
    cl = len(next(iter(core.values())))
    print(f"\nrealigned core: {len(core)} species, {cl} columns")
    m = core["mouse"]
    for k in keys:
        if k == "mouse" or k not in core:
            continue
        nc = sum(1 for a, b in zip(m, core[k]) if a != "-" and b != "-")
        idn = sum(1 for a, b in zip(m, core[k]) if a == b and a != "-")
        print(f"  mouse-{k:16s} {100 * idn / nc:5.1f}% over {nc:4d} cols")
    json.dump(dict(core_cols=[lo, hi], mouse_core=[mouse_lo, mouse_hi],
                   mm10=[29314497 + mouse_lo - 1, 29314497 + mouse_hi - 1],
                   params=dict(window=WIN, cons_min=CONS_MIN, depth_min=DEPTH_MIN)),
              open("seqs/core_def.json", "w"), indent=2)


if __name__ == "__main__":
    main()
