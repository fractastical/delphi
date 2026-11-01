#!/usr/bin/env python3
"""ZRS comparative analysis: alignment, conservation, ETS motifs, ClinVar mapping."""
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/tmp/claude-1000/-home-ubuntu-git-morphoswarm/507442cb-0fa9-4ade-b46c-d7b940105d10/scratchpad/limbless/zrs")
import zrs_lib as Z  # noqa: E402

ORDER = ["mouse", "human", "chicken", "lizard", "coelacanth", "elephant_shark",
         "eryx", "python", "king_cobra", "rattlesnake", "garter_snake"]
SNAKES = {"eryx", "python", "king_cobra", "rattlesnake", "garter_snake", "corn_snake"}
LIMBED_TETRAPODS = ["mouse", "human", "chicken", "lizard"]
P_THRESH = 0.0032   # the threshold Kvon et al. state for their FIMO ETS1 scan


def main():
    rec = json.load(open("seqs/final_set.json"))
    present = [k for k in ORDER if rec[k]["detected"]]
    mouse = rec["mouse"]["sequence"]
    others = {k: rec[k]["sequence"] for k in present if k != "mouse"}

    # ---- 1. alignment ---------------------------------------------------
    mouse_row, rows, colmap = Z.centre_star(mouse, others)
    aln = {"mouse": mouse_row}
    aln.update(rows)
    rows_in_order = [aln[k] for k in present]
    cons, depth, major = Z.column_conservation(rows_in_order)
    L = len(mouse_row)
    print(f"alignment: {len(present)} species, {L} columns "
          f"({len(mouse)} mouse positions + {L - len(mouse)} insertion columns)")

    # identity matrix (over columns where both have a residue)
    idm = {}
    for a in present:
        idm[a] = {}
        for b in present:
            pid, ident, nc = Z.pct_identity(aln[a], aln[b])
            idm[a][b] = dict(pct=round(pid, 2), identities=ident, compared_columns=nc)

    # two identity flavours vs mouse, because they answer different questions
    vs_mouse = {}
    for k in present:
        pid, ident, nc = Z.pct_identity(mouse_row, aln[k])
        # gapped identity over the mouse 1,324 bp frame: indels count against you
        mi = sum(1 for i in range(L) if colmap[i] and mouse_row[i] == aln[k][i] != "-")
        vs_mouse[k] = dict(pct_identity_alignable=round(pid, 2),
                           alignable_columns=nc,
                           pct_identity_over_mouse_frame=round(100.0 * mi / len(mouse), 2),
                           coverage_of_mouse_frame=round(
                               100.0 * sum(1 for i in range(L) if colmap[i] and aln[k][i] != "-")
                               / len(mouse), 2))

    # ---- 2. ETS1 PWM scan ------------------------------------------------
    pfm = json.load(open("motifs/MA0098.3.json"))["pfm"]
    pwm = Z.PWM(pfm, "ETS1_MA0098.3")
    thr, dist = pwm.pvalue_threshold(P_THRESH)
    consensus = "".join(max("ACGT", key=lambda b: pfm[b][i]) for i in range(pwm.length))
    print(f"ETS1 PWM JASPAR MA0098.3, consensus {consensus}, "
          f"log-odds threshold {thr:.3f} bits at p<{P_THRESH}")

    # ungapped -> alignment column map per species
    ets = {}
    col_of = {}
    for k in present:
        row = aln[k]
        m, j = [], 0
        for i in range(L):
            if row[i] != "-":
                m.append(i)
                j += 1
        col_of[k] = m
        hits = Z.scan(rec[k]["sequence"], pwm, thr)
        for h in hits:
            h["pvalue"] = pwm.pvalue_of(h["score"], dist)
            h["aln_start"] = m[h["start"]] if h["start"] < len(m) else None
            h["aln_end"] = m[h["end"] - 1] if h["end"] - 1 < len(m) else None
            h["inferred"] = True
        ets[k] = hits

    # conserved ETS blocks: a column window where >=3 of the 4 limbed tetrapods hit
    tet_cols = {}
    for k in LIMBED_TETRAPODS:
        for h in ets[k]:
            if h["aln_start"] is None:
                continue
            tet_cols.setdefault(h["aln_start"] // 12, set()).add(k)
    blocks = sorted(b for b, s in tet_cols.items() if len(s) >= 3)
    # merge adjacent bins into sites
    sites, cur = [], None
    for b in blocks:
        if cur and b <= cur[1] + 1:
            cur[1] = b
        else:
            cur = [b, b]
            sites.append(cur)
    conserved_sites = []
    for b0, b1 in sites:
        lo, hi = b0 * 12, (b1 + 1) * 12 + pwm.length
        occ = {}
        for k in present:
            occ[k] = any(h["aln_start"] is not None and lo <= h["aln_start"] < hi for h in ets[k])
        conserved_sites.append(dict(aln_start=lo, aln_end=hi,
                                    mouse_pos=[colmap[i] for i in range(lo, min(hi, L)) if colmap[i]][:1],
                                    present_in=occ, inferred=True))
    print(f"inferred tetrapod-conserved ETS sites: {len(conserved_sites)}")

    # ---- 3. snake-specific deletions ------------------------------------
    nonsnake = [k for k in present if k not in SNAKES]
    snake = [k for k in present if k in SNAKES]
    delcols = []
    for i in range(L):
        if all(aln[k][i] == "-" for k in snake) and all(aln[k][i] != "-" for k in nonsnake):
            delcols.append(i)
    runs, cur = [], None
    for i in delcols:
        if cur and i == cur[-1] + 1:
            cur.append(i)
        else:
            cur = [i]
            runs.append(cur)
    runs = sorted(runs, key=len, reverse=True)
    snake_dels = []
    for r in runs[:6]:
        mp = [colmap[i] for i in r if colmap[i]]
        snake_dels.append(dict(length=len(r), aln_start=r[0], aln_end=r[-1] + 1,
                               mouse_start=mp[0] if mp else None,
                               mouse_end=mp[-1] if mp else None,
                               mouse_seq=mouse_row[r[0]:r[-1] + 1],
                               mean_conservation_in_nonsnakes=round(
                                   sum(cons[i] for i in r) / len(r), 3)))
    print("\nruns deleted in EVERY snake and present in EVERY non-snake:")
    for d in snake_dels:
        print(f"  {d['length']:3d} bp  mouse {d['mouse_start']}-{d['mouse_end']}  {d['mouse_seq']}")

    # ---- 4. ClinVar -------------------------------------------------------
    inz = json.load(open("clinvar/in_zrs.json"))
    ZRS_G0 = 156790608
    human_row = aln["human"]
    hcols = col_of["human"]
    hseq_g0 = int(rec["human"]["coords"].split(":")[1].split("-")[0])
    cv = []
    for v in inz:
        if v["clin"] not in ("Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"):
            continue
        off = v["start"] - hseq_g0          # 0-based offset into the human window
        if not (0 <= off < len(rec["human"]["sequence"])):
            continue
        c = hcols[off]
        cv.append(dict(accession=v["acc"], name=v["name"], chr7_grch38=v["start"],
                       classification=v["clin"], human_offset=off, aln_col=c,
                       mouse_pos=colmap[c], conservation=round(cons[c], 3),
                       human_base=human_row[c], mouse_base=mouse_row[c]))
    print(f"\npathogenic/likely-pathogenic ClinVar SNVs mapped into the aligned human ZRS: {len(cv)}")

    out = dict(alignment=aln, colmap=colmap, conservation=cons, depth=depth,
               present=present, identity_matrix=idm, vs_mouse=vs_mouse,
               ets=ets, conserved_sites=conserved_sites, snake_dels=snake_dels,
               clinvar=cv, pwm=dict(name="ETS1 JASPAR MA0098.3", consensus=consensus,
                                    threshold_bits=thr, p_threshold=P_THRESH,
                                    length=pwm.length),
               generated_at=datetime.now(timezone.utc).isoformat())
    json.dump(out, open("analysis.json", "w"))
    print("\nwrote analysis.json")


if __name__ == "__main__":
    main()
