#!/usr/bin/env python3
"""Slow, independent reference for the Rule 30 center column.

No light-cone trimming, no tiling, no bit tricks beyond Python big integers: the whole row
(cells -N-1 .. N+1 around the seed) is one integer, updated with x' = left XOR (x OR right).
Cell index i is bit (M + i) with M = N + 2; the left neighbour of cell i is cell i-1 (bit-1),
so 'left' is `x << 1`, 'right' is `x >> 1`.  The seed pattern never reaches the integer's
edges within N steps, so no boundary effect exists.

usage: ref_slow.py N [outfile.packed]   -> prints sha256 of the packed column (MSB-first)
"""
import hashlib, sys


def center_column(N):
    M = N + 2
    x = 1 << M
    bits = [1]
    for _ in range(N):
        x = (x << 1) ^ (x | (x >> 1))
        bits.append((x >> M) & 1)
    return bits


def pack(bits):
    out = bytearray((len(bits) + 7) // 8)
    for t, b in enumerate(bits):
        if b:
            out[t >> 3] |= 0x80 >> (t & 7)
    return bytes(out)


if __name__ == "__main__":
    N = int(sys.argv[1])
    b = center_column(N)
    pk = pack(b)
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(pk)
    print(hashlib.sha256(pk).hexdigest(), "ones=%d" % sum(b), "N=%d" % N)
