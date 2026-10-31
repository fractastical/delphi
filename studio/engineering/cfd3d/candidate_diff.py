"""Key-by-key difference between two fish3d candidate JSONs (e.g. local pin vs a cloud rebuild).

    python engineering/cfd3d/candidate_diff.py EXPECTED.json GOT.json
Prints each differing path with both values; numbers also get abs/rel difference and their float64 ULP distance.
"""
from __future__ import annotations

import json
import struct
import sys


def ulps(a: float, b: float) -> int:
    ia, ib = (struct.unpack("<q", struct.pack("<d", float(x)))[0] for x in (a, b))
    ia, ib = (i if i >= 0 else -(1 << 63) - i for i in (ia, ib))
    return abs(ia - ib)


def diff(a, b, path="$", out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append({"path": f"{path}.{k}", "only_in": "expected" if k in a else "got"})
            else:
                diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if a != b:
            out.append({"path": path, "expected": a, "got": b, "abs": abs(a - b),
                        "rel": abs(a - b) / max(abs(a), 1e-300), "ulps": ulps(a, b)})
    elif a != b:
        out.append({"path": path, "expected": a, "got": b})
    return out


if __name__ == "__main__":
    d = diff(json.load(open(sys.argv[1])), json.load(open(sys.argv[2])))
    print(json.dumps({"n_differences": len(d), "max_ulps": max((x.get("ulps", 0) for x in d), default=0),
                      "non_numeric": [x["path"] for x in d if "ulps" not in x], "differences": d}, indent=1))
