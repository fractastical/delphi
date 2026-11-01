#!/usr/bin/env python3
"""Locate the ZRS inside a fetched LMBR1 locus by k-mer seeding, then align.

Why seeding rather than aligning the mouse ZRS to the whole locus: the loci are
50-215 kb, and a full Smith-Waterman of 1.3 kb x 215 kb is both slow and
needless. Unique 12-mers shared with the mouse ZRS localise the orthologous
window first; only a +/-2 kb window is then aligned properly.

The procedure is validated on a positive control (the human chr7 window, whose
ZRS position is already known by exact match to NG_042169) and on a negative
control (a shuffled query, which must not localise).
"""
import random
import sys

sys.path.insert(0, "/tmp/claude-1000/-home-ubuntu-git-morphoswarm/507442cb-0fa9-4ade-b46c-d7b940105d10/scratchpad/limbless/zrs")
import zrs_lib as Z  # noqa: E402

K = 12
BIN = 2000


def unique_kmers(seq, k=K):
    counts = {}
    for i in range(len(seq) - k + 1):
        counts[seq[i:i + k]] = counts.get(seq[i:i + k], 0) + 1
    return {m for m, c in counts.items() if c == 1}


def seed_profile(query, target, k=K, binsize=BIN):
    """Return (best_bin_start, hits_in_best_bin, strand, all_bin_counts)."""
    qk = unique_kmers(query, k)
    out = {}
    for strand, t in (("+", target), ("-", Z.revcomp(target))):
        bins = {}
        for i in range(len(t) - k + 1):
            if t[i:i + k] in qk:
                # express position in PLUS-strand coordinates of `target`
                pos = i if strand == "+" else len(target) - i - k
                bins[pos // binsize] = bins.get(pos // binsize, 0) + 1
        out[strand] = bins
    best = (None, 0, None)
    for strand, bins in out.items():
        for b, n in bins.items():
            # pool adjacent bins so a window straddling a boundary is not split
            tot = n + bins.get(b + 1, 0)
            if tot > best[1]:
                best = (b * binsize, tot, strand)
    return best[0], best[1], best[2], out


def locate(query, target, flank=2000):
    """Localise then locally align. Returns dict or None."""
    start, nseed, strand, prof = seed_profile(query, target)
    if start is None or nseed < 3:
        return dict(found=False, seeds=nseed or 0, strand=strand, profile_bins=
                    {s: len(b) for s, b in prof.items()})
    lo = max(0, start - flank)
    hi = min(len(target), start + 2 * BIN + flank)
    window = target[lo:hi]
    sub = window if strand == "+" else Z.revcomp(window)
    aligner = Z.make_aligner("local")
    aln = aligner.align(query, sub)[0]
    a, b = str(aln[0]), str(aln[1])
    ident = sum(1 for x, y in zip(a, b) if x == y and x != "-")
    alen = len(a)
    # coordinates of the aligned block within `sub`
    sb, se = aln.aligned[1][0][0], aln.aligned[1][-1][-1]
    qb, qe = aln.aligned[0][0][0], aln.aligned[0][-1][-1]
    return dict(found=True, seeds=nseed, strand=strand,
                window_lo=lo, window_hi=hi,
                sub_begin=sb, sub_end=se, query_begin=qb, query_end=qe,
                identity=ident, align_len=alen,
                pid=100.0 * ident / alen if alen else 0.0,
                score=aln.score, sub=sub)


def extract_window(query, target, flank_bp=0):
    """Return the orthologous subsequence covering the FULL query span."""
    r = locate(query, target)
    if not r.get("found"):
        return r, None
    sub = r["sub"]
    lo = max(0, r["sub_begin"] - r["query_begin"] - flank_bp)
    hi = min(len(sub), r["sub_end"] + (len(query) - r["query_end"]) + flank_bp)
    return r, sub[lo:hi]


if __name__ == "__main__":
    # ---- controls -------------------------------------------------------
    mouse = "".join(l.strip() for l in open("seqs/mouse_mm10_zrs_raw.fa") if not l.startswith(">")).upper()
    chr7 = open("seqs/human_chr7_window.txt").read().strip()
    ng = open("seqs/human_NG_042169.txt").read().strip()
    known = chr7.find(ng)  # 2608, verified earlier

    r, w = extract_window(mouse, chr7)
    print("POSITIVE CONTROL (human chr7 7kb window):")
    print(f"  seeds={r['seeds']} strand={r['strand']} pid={r['pid']:.1f}% alen={r['align_len']}")
    off_in_chr7 = r["window_lo"] + r["sub_begin"]
    print(f"  aligned block starts at chr7-window offset {off_in_chr7}; "
          f"NG_042169 starts at {known} (delta {off_in_chr7 - known} bp into the record)")
    print(f"  extracted window length {len(w)}")

    rng = random.Random(0)
    shuf = "".join(rng.sample(mouse, len(mouse)))
    rn = locate(shuf, chr7)
    print(f"NEGATIVE CONTROL (shuffled mouse ZRS vs same window): found={rn.get('found')} "
          f"seeds={rn.get('seeds')}")
