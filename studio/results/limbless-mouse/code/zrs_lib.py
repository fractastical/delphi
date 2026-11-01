#!/usr/bin/env python3
"""Alignment + motif machinery for the ZRS comparative analysis.

Two pieces:

1. A reference-anchored (centre-star) multiple alignment. Every species is
   aligned pairwise to the mouse ZRS with an affine-gap global/glocal aligner
   (Biopython PairwiseAligner), then the pairwise alignments are merged onto a
   single mouse-anchored column frame. Columns where a species has an insertion
   relative to mouse are added as extra columns (all other species gapped).
   The mouse is the centre because every quantity reported here is
   "relative to the mouse ZRS", which is the sequence the knock-ins replaced.

2. A position-weight-matrix scanner with a FIMO-style p-value threshold.
   The threshold is derived by exact enumeration of the score distribution
   under a uniform background, so "p < 0.0032" means the same thing it means
   in FIMO rather than an eyeballed cutoff.
"""
import math
from collections import Counter

from Bio import Align

BASES = "ACGT"


# --------------------------------------------------------------------------
# 1. Alignment
# --------------------------------------------------------------------------
def make_aligner(mode="global"):
    """Affine-gap nucleotide aligner.

    Scores follow the BLASTN-style scheme actually used for the ortholog
    search (match +2, mismatch -3) with affine gaps, so the alignment and the
    search that found the sequences are scored consistently. End gaps are free
    so a species whose fetched window is shorter is not penalised for the
    missing flank (that is coverage, not divergence).
    """
    a = Align.PairwiseAligner()
    a.mode = mode
    a.match_score = 2.0
    a.mismatch_score = -3.0
    a.open_gap_score = -5.0
    a.extend_gap_score = -2.0
    a.target_end_gap_score = 0.0
    a.query_end_gap_score = 0.0
    return a


def pairwise_to_mouse(mouse, other, aligner=None):
    """Return (aligned_mouse, aligned_other) strings."""
    aligner = aligner or make_aligner()
    aln = aligner.align(mouse, other)[0]
    return str(aln[0]), str(aln[1])


def centre_star(mouse, others):
    """Merge pairwise alignments-to-mouse into one mouse-anchored MSA.

    others: dict name -> sequence
    Returns (columns_mouse, dict name -> aligned string, list of insertion
    counts per mouse position).
    """
    aligner = make_aligner()
    pairs = {n: pairwise_to_mouse(mouse, s, aligner) for n, s in others.items()}

    # How many inserted (non-mouse) columns are needed after each mouse position?
    # Index 0 = before mouse base 1; index i = after mouse base i.
    need = [0] * (len(mouse) + 1)
    per_species_ins = {}
    for n, (am, ao) in pairs.items():
        ins = [[] for _ in range(len(mouse) + 1)]
        mpos = 0
        for cm, co in zip(am, ao):
            if cm == "-":
                ins[mpos].append(co)
            else:
                mpos += 1
        per_species_ins[n] = ins
        for i, block in enumerate(ins):
            need[i] = max(need[i], len(block))

    # Mouse row
    def build_row(symbols_at_mouse_pos, ins):
        """symbols_at_mouse_pos: list length len(mouse), char aligned to each mouse base."""
        row = []
        for i in range(len(mouse) + 1):
            block = ins[i]
            row.append("".join(block) + "-" * (need[i] - len(block)))
            if i < len(mouse):
                row.append(symbols_at_mouse_pos[i])
        return "".join(row)

    mouse_row = build_row(list(mouse), [[] for _ in range(len(mouse) + 1)])

    rows = {}
    for n, (am, ao) in pairs.items():
        at_pos = []
        mpos = 0
        for cm, co in zip(am, ao):
            if cm != "-":
                at_pos.append(co)
                mpos += 1
        # glocal end-gaps may leave the tail short
        at_pos += ["-"] * (len(mouse) - len(at_pos))
        rows[n] = build_row(at_pos, per_species_ins[n])

    # map: alignment column index -> mouse position (1-based) or None
    colmap = []
    for i in range(len(mouse) + 1):
        colmap.extend([None] * need[i])
        if i < len(mouse):
            colmap.append(i + 1)

    assert all(len(r) == len(mouse_row) for r in rows.values()), "ragged MSA"
    assert len(colmap) == len(mouse_row)
    return mouse_row, rows, colmap


def pct_identity(a, b, ignore_end_gaps=True):
    """Identity over columns where BOTH sequences have a residue.

    Gaps are excluded rather than counted as mismatches, and the denominator is
    reported alongside so a short/partial sequence cannot masquerade as a
    divergent one.
    """
    lo, hi = 0, len(a)
    if ignore_end_gaps:
        for i in range(len(b)):
            if b[i] != "-":
                lo = i
                break
        for i in range(len(b) - 1, -1, -1):
            if b[i] != "-":
                hi = i + 1
                break
    ident = cols = 0
    for i in range(lo, hi):
        if a[i] == "-" or b[i] == "-":
            continue
        cols += 1
        ident += (a[i] == b[i])
    return (100.0 * ident / cols if cols else float("nan")), ident, cols


def column_conservation(rows_in_order):
    """Per-column fraction of sequences sharing the most common residue.

    Only sequences with a residue in that column count (gaps excluded from
    the denominator); the per-column depth is returned so a column supported
    by two species is distinguishable from one supported by ten.
    """
    cons, depth, major = [], [], []
    n = len(rows_in_order[0])
    for i in range(n):
        col = [r[i] for r in rows_in_order if r[i] != "-"]
        depth.append(len(col))
        if not col:
            cons.append(0.0)
            major.append("-")
            continue
        c = Counter(col).most_common(1)[0]
        major.append(c[0])
        cons.append(c[1] / len(col))
    return cons, depth, major


# --------------------------------------------------------------------------
# 2. PWM scanning with a FIMO-style p-value threshold
# --------------------------------------------------------------------------
class PWM:
    def __init__(self, pfm, name, pseudo=0.25, bg=0.25, scale=100):
        """pfm: dict base -> list of counts."""
        self.name = name
        self.length = len(pfm["A"])
        self.bg = bg
        self.lods = []
        for i in range(self.length):
            tot = sum(pfm[b][i] for b in BASES) + 4 * pseudo
            col = {}
            for b in BASES:
                p = (pfm[b][i] + pseudo) / tot
                col[b] = math.log2(p / bg)
            self.lods.append(col)
        self.scale = scale
        self._int = [{b: int(round(c[b] * scale)) for b in BASES} for c in self.lods]

    def score(self, seq):
        if len(seq) != self.length:
            return None
        s = 0.0
        for i, ch in enumerate(seq):
            if ch not in self.lods[i]:
                return None
            s += self.lods[i][ch]
        return s

    def pvalue_threshold(self, p):
        """Smallest score whose upper-tail probability under the uniform
        background is <= p. Exact, by convolution of the integerised columns."""
        dist = {0: 1.0}
        for col in self._int:
            nd = {}
            for s0, pr in dist.items():
                for b in BASES:
                    k = s0 + col[b]
                    nd[k] = nd.get(k, 0.0) + pr * self.bg
            dist = nd
        items = sorted(dist.items(), reverse=True)
        cum = 0.0
        thr = None
        for sc, pr in items:
            cum += pr
            if cum > p:
                break
            thr = sc
        return (thr / self.scale if thr is not None else float("inf")), dist

    def pvalue_of(self, score, dist):
        k = int(round(score * self.scale))
        return sum(pr for sc, pr in dist.items() if sc >= k)


def revcomp(s):
    return s[::-1].translate(str.maketrans("ACGTN-", "TGCAN-"))


def scan(seq, pwm, threshold):
    """Scan both strands of an UNGAPPED sequence. Returns list of hits."""
    hits = []
    rc = revcomp(seq)
    n = len(seq)
    for i in range(n - pwm.length + 1):
        w = seq[i:i + pwm.length]
        s = pwm.score(w)
        if s is not None and s >= threshold:
            hits.append(dict(start=i, end=i + pwm.length, strand="+", motif=w, score=round(s, 3)))
        wr = rc[n - i - pwm.length:n - i]
        sr = pwm.score(wr)
        if sr is not None and sr >= threshold:
            hits.append(dict(start=i, end=i + pwm.length, strand="-", motif=wr, score=round(sr, 3)))
    return hits
