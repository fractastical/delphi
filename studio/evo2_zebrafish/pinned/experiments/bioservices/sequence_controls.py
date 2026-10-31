"""Composition-matched negative controls for DNA sequences.

Shared by the GPU generation job and the CPU diagnostics so both arms build
their controls with exactly the same code. A control computed two slightly
different ways is not a control.
"""

from __future__ import annotations

import random


def dinucleotide_shuffle(seq: str, rng: random.Random) -> str:
    """Shuffle preserving exact dinucleotide counts (Altschul-Erikson style).

    A mononucleotide shuffle preserves only base composition, which is too weak
    a control for DNA: dinucleotide content, CpG above all, carries much of what
    a motif scan responds to. Preserving it means a surviving difference is not
    merely a difference in dinucleotide composition.
    """
    if len(seq) < 2:
        return seq
    edges: dict[str, list[str]] = {}
    for a, b in zip(seq, seq[1:]):
        edges.setdefault(a, []).append(b)
    for v in edges.values():
        rng.shuffle(v)
    out, cur = [seq[0]], seq[0]
    for _ in range(len(seq) - 1):
        nxt = edges[cur].pop() if edges.get(cur) else rng.choice("ACGT")
        out.append(nxt)
        cur = nxt
    return "".join(out)


def gc_matched_random(length: int, gc: float, rng: random.Random) -> str:
    """Independent bases drawn at a target GC fraction."""
    half_gc, half_at = gc / 2, (1 - gc) / 2
    return "".join(rng.choices("GCAT", weights=[half_gc, half_gc, half_at, half_at], k=length))


def gc_fraction(seq: str) -> float:
    return (seq.count("G") + seq.count("C")) / len(seq) if seq else 0.0
