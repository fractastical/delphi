#!/usr/bin/env python3
"""Test of wolfram2002-ch10-08: structurally different lossless compressors all compress
uniform, repetitive and (partly) nested CA patterns but not complex ones.

Six methods (run-length, block Huffman, zlib, lzma, bz2, quadtree) on 1024 x 1024 interior
windows of elementary CA patterns from a single black cell, each size divided by the size
for a density-matched Bernoulli pattern.

Run: python3 analysis.py   (needs numpy; standard-library zlib, lzma, bz2, heapq)
Writes derived/measured.json and prints it.
"""
import bz2
import heapq
import json
import lzma
import math
import os
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = 2048
SEED = 20261031
CLASSES = {"uniform": [254], "repetitive": [50, 250], "nested": [90, 150],
           "complex": [30, 45], "exploratory": [110]}
METHODS = ["rle", "huffman8", "zlib", "lzma", "bz2", "quadtree"]


def eca(rule):
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    out = np.zeros((T, 2 * T + 1), dtype=np.uint8)
    out[0, T] = 1
    row = out[0].copy()
    for t in range(1, T):
        pad = np.concatenate([[0], row, [0]])
        row = table[4 * pad[:-2] + 2 * pad[1:-1] + pad[2:]]
        out[t] = row
    return out[T // 2:T, T - 512:T + 512]


# ---------------------------------------------------------------------------
# Compressors (sizes in bytes)
# ---------------------------------------------------------------------------
def size_rle(img):
    b = img.ravel()
    change = np.nonzero(b[1:] != b[:-1])[0]
    runs = np.diff(np.concatenate([[-1], change, [len(b) - 1]]))
    bits = 1 + int(np.sum(2 * np.floor(np.log2(runs)).astype(np.int64) + 1))
    return math.ceil(bits / 8)


def size_huffman8(img):
    data = np.packbits(img.ravel())
    counts = np.bincount(data, minlength=256)
    syms = [(int(c), i) for i, c in enumerate(counts) if c > 0]
    if len(syms) == 1:
        return 256 + math.ceil(syms[0][0] / 8)
    heap = [(c, k, [i]) for k, (c, i) in enumerate(syms)]
    heapq.heapify(heap)
    depth = {i: 0 for _, i in syms}
    k = len(heap)
    while len(heap) > 1:
        c1, _, s1 = heapq.heappop(heap)
        c2, _, s2 = heapq.heappop(heap)
        for i in s1 + s2:
            depth[i] += 1
        heapq.heappush(heap, (c1 + c2, k, s1 + s2))
        k += 1
    bits = sum(int(counts[i]) * d for i, d in depth.items())
    return 256 + math.ceil(bits / 8)


def size_quadtree(img):
    n = img.shape[0]
    cost = np.ones_like(img, dtype=np.int64)  # 1x1 leaves: 1 bit
    s = img.astype(np.int64)
    size = 1
    while size < n:
        size *= 2
        m = cost.shape[0] // 2
        child = cost.reshape(m, 2, m, 2).sum(axis=(1, 3))
        s = s.reshape(m, 2, m, 2).sum(axis=(1, 3))
        uniform = (s == 0) | (s == size * size)
        cost = np.where(uniform, 2, 1 + child)
    return math.ceil(int(cost[0, 0]) / 8)


def sizes(img):
    raw = np.packbits(img.ravel()).tobytes()
    return {"rle": size_rle(img), "huffman8": size_huffman8(img),
            "zlib": len(zlib.compress(raw, 9)),
            "lzma": len(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME)),
            "bz2": len(bz2.compress(raw, 9)), "quadtree": size_quadtree(img)}


def main():
    rng = np.random.default_rng(SEED)
    out = {"T": T, "window": "rows 1024-2047, x in [-512, 511]", "seed": SEED, "rules": {}}
    for cls, rules in CLASSES.items():
        for rule in rules:
            img = eca(rule)
            d = float(img.mean())
            dc = min(max(d, 0.01), 0.99)
            ctrl = (rng.random(img.shape) < dc).astype(np.uint8)
            s, c = sizes(img), sizes(ctrl)
            r = {m: round(s[m] / c[m], 4) for m in METHODS}
            out["rules"][rule] = {"class": cls, "black_fraction": round(d, 4), "control_p": dc,
                                  "sizes": s, "control_sizes": c, "r": r}
            print(rule, cls, round(d, 4), r)

    R = {rule: v["r"] for rule, v in out["rules"].items()}
    a = all(R[254][m] <= 0.10 for m in METHODS)
    b = all(sum(R[x][m] <= 0.20 for m in METHODS) >= 4 for x in (50, 250))
    c = all(sum(R[x][m] <= 0.80 for m in METHODS) >= 3 for x in (90, 150))
    d = all(R[x][m] >= 0.85 for x in (30, 45) for m in METHODS)
    min_complex = min(R[x][m] for x in (30, 45) for m in METHODS)
    if min_complex < 0.60 or (not b and not c):
        verdict = "refutes"
    elif a and b and c and d:
        verdict = "supports"
    else:
        verdict = "mixed"
    out["conditions"] = {"a_uniform": a, "b_repetitive": b, "c_nested": c, "d_complex": d,
                         "min_r_complex": min_complex, "verdict_by_rule": verdict}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out["conditions"], indent=1))


if __name__ == "__main__":
    main()
