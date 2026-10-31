#!/usr/bin/env python3
"""Test of wolfram2002-ch04-08: nested recurrences using only addition and subtraction.

Rules (c)-(h) from NKS pp. 129-130, f[1]=f[2]=1, computed for n <= 2^20.
Independent check: OEIS b-files for A005185 (rule e) and A004001 (rule c).

Run: python3 analysis.py   (downloads two small b-files into data/, writes derived/summary.json)
"""
import hashlib
import json
import lzma
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
N = 1 << 20
BPS_RANDOM_MIN = 0.5
BPS_NESTED_MAX = 0.15
BALANCE_MAX = 0.05

RULES = {
    "c": ("f[f[n-1]]+f[n-f[n-1]]", lambda f, n: f[f[n - 1]] + f[n - f[n - 1]]),
    "d": ("f[n-f[n-1]]+f[n-f[n-2]-1]", lambda f, n: f[n - f[n - 1]] + f[n - f[n - 2] - 1]),
    "e": ("f[n-f[n-1]]+f[n-f[n-2]]", lambda f, n: f[n - f[n - 1]] + f[n - f[n - 2]]),
    "f": ("f[n-f[n-1]-1]+f[n-f[n-2]-1]", lambda f, n: f[n - f[n - 1] - 1] + f[n - f[n - 2] - 1]),
    "g": ("f[f[n-1]]+f[n-f[n-2]-1]", lambda f, n: f[f[n - 1]] + f[n - f[n - 2] - 1]),
    "h": ("f[f[n-1]]+f[n-2f[n-1]+1]", lambda f, n: f[f[n - 1]] + f[n - 2 * f[n - 1] + 1]),
}
INDEX_ARGS = {
    "c": lambda f, n: (f[n - 1], n - f[n - 1]),
    "d": lambda f, n: (n - f[n - 1], n - f[n - 2] - 1),
    "e": lambda f, n: (n - f[n - 1], n - f[n - 2]),
    "f": lambda f, n: (n - f[n - 1] - 1, n - f[n - 2] - 1),
    "g": lambda f, n: (f[n - 1], n - f[n - 2] - 1),
    "h": lambda f, n: (f[n - 1], n - 2 * f[n - 1] + 1),
}


def compute(rule, n_max):
    f = [0] * (n_max + 1)
    f[1] = f[2] = 1
    args = INDEX_ARGS[rule]
    step = RULES[rule][1]
    for n in range(3, n_max + 1):
        i, j = args(f, n)
        if i < 1 or j < 1 or i >= n or j >= n:
            return np.array(f[1:n], dtype=np.int64), n  # undefined (or non-causal) at n
        f[n] = step(f, n)
    return np.array(f[1:], dtype=np.int64), None


def fetch(url, name):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    r = requests.get(url, timeout=60, headers={"User-Agent": "delphi-claim-tests/1.0"})
    r.raise_for_status()
    with open(path, "wb") as fh:
        fh.write(r.content)
    return {
        "download_url": url,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
        "path": path,
    }


def read_bfile(path):
    idx, vals = [], []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            a, b = line.split()[:2]
            idx.append(int(a))
            vals.append(int(b))
    return np.array(idx), np.array(vals, dtype=object)


def bits_per_symbol(r):
    d = (np.sign(np.diff(r)) + 1).astype(np.uint8)
    comp = lzma.compress(d.tobytes(), preset=9 | lzma.PRESET_EXTREME)
    return 8.0 * len(comp) / len(d)


def main():
    t0 = time.time()
    files = {
        "A005185": fetch("https://oeis.org/A005185/b005185.txt", "b005185.txt"),
        "A004001": fetch("https://oeis.org/A004001/b004001.txt", "b004001.txt"),
    }
    out = {"files": files, "rules": {}}
    seqs = {}
    for key in RULES:
        seq, undefined_at = compute(key, N)
        seqs[key] = seq
        n = np.arange(1, len(seq) + 1, dtype=np.float64)
        if key == "h":
            mask = n >= 16
            b, loga = np.polyfit(np.log(n[mask]), np.log(seq[mask].astype(float)), 1)
            trend = np.exp(loga) * n ** b
            trend_desc = f"{np.exp(loga):.4f} n^{b:.4f}"
        else:
            trend = n / 2
            trend_desc = "n/2"
        r = seq - trend
        inc = np.diff(r)
        pos, neg = float((inc > 0).mean()), float((inc < 0).mean())
        m = len(r)
        idx = np.arange(m // 4, m // 2)
        corr2 = float(np.corrcoef(r[idx - 1], r[2 * idx - 1])[0, 1]) if m >= 8 else float("nan")
        bps = bits_per_symbol(r)
        res = {
            "rule": RULES[key][0],
            "terms": int(len(seq)),
            "undefined_at": undefined_at,
            "trend": trend_desc,
            "bits_per_symbol": round(bps, 4),
            "sign_balance": round(abs(pos - neg), 4),
            "p_pos": round(pos, 4),
            "p_neg": round(neg, 4),
            "corr_r_n_r_2n": round(corr2, 4),
            "resid_std_first_eighth": round(float(np.std(r[: m // 8])), 2),
            "resid_std_last_eighth": round(float(np.std(r[-(m // 8):])), 2),
            "max_abs_resid": round(float(np.max(np.abs(r))), 1),
        }
        res["well_defined"] = undefined_at is None
        res["random_like"] = bool(res["well_defined"] and bps >= BPS_RANDOM_MIN and res["sign_balance"] <= BALANCE_MAX)
        res["nested_like"] = bool(bps < BPS_NESTED_MAX)
        out["rules"][key] = res
        print(f"({key}) {res['rule']:<28} terms={res['terms']} bps={bps:.4f} balance={res['sign_balance']:.4f} "
              f"corr2={corr2:.3f} random_like={res['random_like']}", file=sys.stderr)

    # OEIS cross-checks
    checks = {}
    for key, aid in (("e", "A005185"), ("c", "A004001")):
        idx, vals = read_bfile(files[aid]["path"])
        seq = seqs[key]
        ok = True
        n_checked = 0
        first_mismatch = None
        for i, v in zip(idx, vals):
            if 1 <= i <= len(seq):
                n_checked += 1
                if int(seq[i - 1]) != int(v):
                    ok = False
                    first_mismatch = int(i)
                    break
        checks[aid] = {"rule": key, "terms_compared": n_checked, "all_match": ok, "first_mismatch_n": first_mismatch}
    out["oeis_checks"] = checks

    random_like = [k for k in ("e", "f", "g", "h") if out["rules"][k]["random_like"]]
    controls_ok = out["rules"]["c"]["nested_like"] and out["rules"]["d"]["nested_like"]
    oeis_ok = all(c["all_match"] for c in checks.values())
    out["measured"] = {
        "value": len(random_like),
        "unit": "rules among (e)-(h) that are complex/random-like by the pre-registered criteria",
        "n": 4,
        "uncertainty": None,
        "extra": {
            "random_like_rules": random_like,
            "nested_controls_detected": controls_ok,
            "oeis_terms_match": oeis_ok,
            "per_rule": out["rules"],
            "oeis_checks": checks,
            "N": N,
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps(out["measured"], indent=2, default=str))
    print(json.dumps(files, indent=2))


if __name__ == "__main__":
    main()
