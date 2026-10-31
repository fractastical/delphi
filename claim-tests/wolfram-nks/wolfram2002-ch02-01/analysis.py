#!/usr/bin/env python3
"""Test of wolfram2002-ch02-01: rule 90 from a single black cell gives a nested
self-similar pattern of triangles.

1. Evolve ECA rule 90 from one black cell for T = 2048 steps on a line wide enough
   that the boundary is never reached.
2. Self-similarity: for k = 1..11, check that the triangle of rows 0..2^k-1 is exactly
   three copies of the triangle of rows 0..2^(k-1)-1 (top copy centred, two bottom
   copies shifted by -2^(k-1) and +2^(k-1)) with an all-white inverted triangle between.
3. External check: compare every row with OEIS A001317 (Pascal's triangle mod 2 rows
   read as binary numbers), downloaded from oeis.org; the b-file's size, SHA-256 and
   retrieval time are recorded in derived/measured.json.

Run: python3 analysis.py   (needs numpy, requests)
"""
import datetime
import hashlib
import json
import os

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RULE = 90
T = 2048
HALF = 2048
KMAX = 11
BFILE_URL = "https://oeis.org/A001317/b001317.txt"


def evolve(rule, steps, half):
    width = 2 * half + 1
    rule_bits = np.array([(rule >> k) & 1 for k in range(8)], dtype=np.uint8)
    row = np.zeros(width, dtype=np.uint8)
    row[half] = 1
    rows = [row.copy()]
    for _ in range(steps - 1):
        left = np.concatenate(([0], row[:-1]))
        right = np.concatenate((row[1:], [0]))
        row = rule_bits[4 * left + 2 * row + right]
        rows.append(row.copy())
    return np.array(rows)


def triangle(grid, k, half):
    """Rows 0..2^k-1, columns x = -(2^k-1)..(2^k-1) around the origin."""
    n = 1 << k
    return grid[:n, half - (n - 1): half + n]


def check_self_similar(grid, half, kmax):
    mismatches = {}
    for k in range(1, kmax + 1):
        big = triangle(grid, k, half)          # shape (2^k, 2^(k+1)-1)
        small = triangle(grid, k - 1, half)    # shape (2^(k-1), 2^k-1)
        n = 1 << (k - 1)
        w = 2 * n - 1
        recon = np.zeros_like(big)
        c = big.shape[1] // 2                  # column index of x = 0
        # top copy centred
        recon[:n, c - (n - 1): c + n] = small
        # bottom-left and bottom-right copies, shifted by -n and +n
        recon[n:, c - n - (n - 1): c - n + n] = small
        recon[n:, c + n - (n - 1): c + n + n] = small
        bad = int((recon != big).sum())
        # the central inverted triangle (rows n..2n-1, between the two copies) must be white
        # In rows r = n..2n-1 the two lower copies occupy |x -+ n| <= r - n, so the
        # inverted triangle between them is |x| < n - (r - n); count black cells there.
        central = 0
        for r in range(n, 2 * n):
            gap = n - (r - n)
            if gap > 0:
                central += int(big[r, c - gap + 1: c + gap].sum())
        mismatches[k] = {"cells_compared": int(big.size), "mismatching_cells": bad,
                         "black_cells_in_central_inverted_triangle": central}
    return mismatches


def fetch_bfile(url):
    t = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(url, timeout=60, headers={"User-Agent": "delphisci-claim-test/1.0"})
    r.raise_for_status()
    data = r.content
    meta = {"download_url": url, "retrieved_at": t, "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
    values = {}
    for line in data.decode("ascii", "replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            values[int(parts[0])] = int(parts[1])
    return meta, values


def main():
    grid = evolve(RULE, T, HALF)
    assert grid[:, 0].sum() == 0 and grid[:, -1].sum() == 0, "boundary reached"
    # Row t has black cells only at x with x = t mod 2; |x| <= t.
    ss = check_self_similar(grid, HALF, KMAX)
    total_bad = sum(v["mismatching_cells"] for v in ss.values())
    total_central = sum(v["black_cells_in_central_inverted_triangle"] for v in ss.values())

    out = {"rule": RULE, "steps": T, "self_similarity": ss,
           "self_similarity_mismatching_cells_total": total_bad,
           "central_triangle_black_cells_total": total_central}
    try:
        meta, oeis = fetch_bfile(BFILE_URL)
        compared = 0
        bad_rows = []
        for t in range(T):
            if t not in oeis:
                continue
            cells = grid[t, HALF - t: HALF + t + 1: 2]  # positions x = -t, -t+2, ..., t
            val = int("".join(str(int(b)) for b in cells), 2)
            compared += 1
            if val != oeis[t]:
                bad_rows.append(t)
        out["oeis_a001317"] = {"file": meta, "terms_in_bfile": len(oeis),
                               "rows_compared": compared, "mismatching_rows": len(bad_rows),
                               "first_mismatches": bad_rows[:5]}
    except Exception as e:  # network failure: record, do not fabricate
        out["oeis_a001317"] = {"error": repr(e)}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
