#!/usr/bin/env python3
"""Memory counts at clamp scales 10, 50 and 100 for the Table S1 pathway models.

Recomputes measured in result.json. SBML is downloaded to /tmp, not the repo.

Usage:
  python3 analysis.py
  python3 analysis.py --one BIOMD0000000010
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone

import numpy as np
from scipy.integrate import solve_ivp

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("GRN_SBML_CACHE", "/tmp/delphi-grn-sbml")
UA = "delphi-claim-test/levin-2022-grn-learning-09"

TABLE_S1 = [
    "BIOMD0000000001",
    "BIOMD0000000002",
    "BIOMD0000000003",
    "BIOMD0000000004",
    "BIOMD0000000005",
    "BIOMD0000000006",
    "BIOMD0000000010",
    "BIOMD0000000069",
    "BIOMD0000000016",
    "BIOMD0000000017",
    "BIOMD0000000022",
    "BIOMD0000000021",
    "BIOMD0000000023",
    "BIOMD0000000024",
    "BIOMD0000000026",
    "BIOMD0000000027",
    "BIOMD0000000483",
    "BIOMD0000000029",
    "BIOMD0000000031",
    "BIOMD0000000631",
    "BIOMD0000000203",
    "BIOMD0000000204",
    "BIOMD0000000209",
    "BIOMD0000000210",
    "BIOMD0000000539",
    "BIOMD0000000664",
    "BIOMD0000000275",
    "BIOMD0000000697",
    "BIOMD0000000600",
    "BIOMD0000000039",
    "BIOMD0000000050",
    "BIOMD0000000035",
    "BIOMD0000000036",
    "BIOMD0000000037",
    "BIOMD0000000038",
]

SCALES = (10.0, 50.0, 100.0)
FACTOR = 2.0
EPOCH = 50.0
MIN_N = 3
MAX_N = 12
TIMEOUT_S = 240.0


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download(mid):
    os.makedirs(CACHE, exist_ok=True)
    url = (
        "https://www.ebi.ac.uk/biomodels/model/download/"
        f"{mid}?filename={mid}_url.xml"
    )
    path = os.path.join(CACHE, f"{mid}_url.xml")
    # Reuse a file downloaded by a sibling test if the bytes are already there,
    # but always record a retrieval by re-fetching so the hash is of this run's
    # bytes. A conditional GET is not used; the file is what the URL returns.
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    retrieved = now_iso()
    with urllib.request.urlopen(req, timeout=90) as resp:
        blob = resp.read()
    with open(path, "wb") as fh:
        fh.write(blob)
    name = None
    match = re.search(br'<model\b[^>]*\bname="([^"]*)"', blob)
    if match:
        name = match.group(1).decode("utf-8", "replace")
    return {
        "path": path,
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "name": name,
        "license": "CC0 1.0" if b"CC0" in blob else None,
    }


def load_runner(path):
    import roadrunner

    rr = roadrunner.RoadRunner(path)
    try:
        rr.conservedMoietyAnalysis = False
    except Exception:
        pass
    y0 = np.array(rr.model.getFloatingSpeciesConcentrations(), dtype=float)
    return rr, y0


def integrate(rr, y0, duration, clamps, deadline):
    """clamps is a dict index -> value. Time is local to the epoch."""
    y_start = np.array(y0, dtype=float)
    for idx, value in clamps.items():
        y_start[idx] = float(value)
    n = y_start.size

    def rhs(t, y):
        if time.monotonic() > deadline:
            raise TimeoutError("model timeout")
        y_eval = np.array(y, dtype=float)
        for idx, value in clamps.items():
            y_eval[idx] = float(value)
        if not np.all(np.isfinite(y_eval)):
            raise FloatingPointError("non-finite state")
        rr.model.setTime(float(t))
        rr.model.setFloatingSpeciesConcentrations(y_eval.tolist())
        rates = np.array(rr.getRatesOfChange(), dtype=float)
        if rates.shape != (n,):
            raise RuntimeError(f"rate length {rates.shape}")
        for idx in clamps:
            rates[idx] = 0.0
        if not np.all(np.isfinite(rates)):
            raise FloatingPointError("non-finite rate")
        return rates

    sol = solve_ivp(
        rhs,
        (0.0, float(duration)),
        y_start,
        method="BDF",
        rtol=1e-4,
        atol=1e-6,
        t_eval=np.linspace(0.0, float(duration), 21),
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y[:, -1].copy(), sol.y.mean(axis=1)


def direction(baseline, stimulated):
    if stimulated >= FACTOR * baseline and stimulated > baseline:
        return 1
    if stimulated <= baseline / FACTOR and stimulated < baseline:
        return 2
    return 0


def retains(baseline, stimulated, released, which):
    mid = baseline + 0.5 * (stimulated - baseline)
    if which == 1:
        return bool(released >= mid)
    if which == 2:
        return bool(released <= mid)
    return False


def ns_regulates(relax_mean, test_mean):
    return direction(relax_mean, test_mean) != 0


def counts_at_scale(rr, y0, scale, deadline):
    # Max and min include zeros, over the first 50 time units from the SBML initial state.
    y_ss, base_mean, samples = _integrate_samples(rr, y0, EPOCH, {}, deadline)
    maxima = samples.max(axis=1)
    minima = samples.min(axis=1)
    up = maxima * scale
    down = minima / scale
    n = y0.size
    # Single-node clamps from the baseline end state.
    stim = {}
    stim_end = {}
    for node in range(n):
        for which, value in ((1, up[node]), (2, down[node])):
            if not np.isfinite(value) or value == 0.0:
                continue
            y_end, mean = integrate(rr, y_ss, EPOCH, {node: float(value)}, deadline)
            stim[(node, which)] = mean
            stim_end[(node, which)] = y_end
    ucs_mem = 0
    # Release each clamp that regulates at least one response.
    release_mean = {}
    for (node, which), mean in stim.items():
        regulated = [
            r
            for r in range(n)
            if r != node and direction(base_mean[r], mean[r]) == which
        ]
        if not regulated:
            continue
        _y, rel = integrate(rr, stim_end[(node, which)], EPOCH, {}, deadline)
        release_mean[(node, which)] = rel
        for r in regulated:
            if retains(base_mean[r], mean[r], rel[r], which):
                ucs_mem += 1
    assoc = 0
    keys = list(stim.keys())
    for ucs, ucs_dir in keys:
        for ns, ns_dir in keys:
            if ns == ucs:
                continue
            # Responses for which UCS regulates and NS does not.
            responses = []
            for r in range(n):
                if r == ucs or r == ns:
                    continue
                if direction(base_mean[r], stim[(ucs, ucs_dir)][r]) == 0:
                    continue
                if direction(base_mean[r], stim[(ns, ns_dir)][r]) != 0:
                    continue
                responses.append(r)
            if not responses:
                continue
            y, _paired = integrate(
                rr,
                y_ss,
                EPOCH,
                {ucs: float(up[ucs] if ucs_dir == 1 else down[ucs]),
                 ns: float(up[ns] if ns_dir == 1 else down[ns])},
                deadline,
            )
            y, relax = integrate(rr, y, EPOCH, {}, deadline)
            ns_value = float(up[ns] if ns_dir == 1 else down[ns])
            _y, tested = integrate(rr, y, EPOCH, {ns: ns_value}, deadline)
            for r in responses:
                if ns_regulates(relax[r], tested[r]):
                    assoc += 1
    return {
        "ucs_memories": ucs_mem,
        "associative_memories": assoc,
        "memory_count": ucs_mem + assoc,
    }


def _integrate_samples(rr, y0, duration, clamps, deadline):
    y_start = np.array(y0, dtype=float)
    for idx, value in clamps.items():
        y_start[idx] = float(value)
    n = y_start.size

    def rhs(t, y):
        if time.monotonic() > deadline:
            raise TimeoutError("model timeout")
        y_eval = np.array(y, dtype=float)
        for idx, value in clamps.items():
            y_eval[idx] = float(value)
        rr.model.setTime(float(t))
        rr.model.setFloatingSpeciesConcentrations(y_eval.tolist())
        rates = np.array(rr.getRatesOfChange(), dtype=float)
        if rates.shape != (n,):
            raise RuntimeError(f"rate length {rates.shape}")
        for idx in clamps:
            rates[idx] = 0.0
        if not np.all(np.isfinite(rates)):
            raise FloatingPointError("non-finite rate")
        return rates

    sol = solve_ivp(
        rhs,
        (0.0, float(duration)),
        y_start,
        method="BDF",
        rtol=1e-4,
        atol=1e-6,
        t_eval=np.linspace(0.0, float(duration), 21),
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y[:, -1].copy(), sol.y.mean(axis=1), sol.y


def screen(mid):
    started = time.monotonic()
    deadline = started + TIMEOUT_S
    meta = download(mid)
    out = {
        "id": mid,
        "status": "excluded",
        "reason": None,
        "n_species": None,
        "size_eligible": False,
        "counts": {},
        "seconds": None,
        "file": meta,
    }
    try:
        rr, y0 = load_runner(meta["path"])
        n = int(y0.size)
        out["n_species"] = n
        out["size_eligible"] = MIN_N <= n <= MAX_N
        if not out["size_eligible"]:
            out["reason"] = f"floating species {n} outside {MIN_N}-{MAX_N}"
            out["seconds"] = round(time.monotonic() - started, 3)
            return out
        for scale in SCALES:
            out["counts"][str(int(scale))] = counts_at_scale(rr, y0, scale, deadline)
        out["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc(limit=3)
    out["seconds"] = round(time.monotonic() - started, 3)
    return out


def decide(rows):
    downloaded = [r for r in rows if r.get("file")]
    if len(downloaded) < len(TABLE_S1) / 2:
        return "inconclusive", "data-unavailable", {}
    size_ok = [r for r in rows if r.get("size_eligible")]
    if not size_ok:
        return "inconclusive", "underpowered", {}
    failed = [r for r in size_ok if r["status"] != "ok"]
    if len(failed) > 0.5 * len(size_ok):
        return "inconclusive", "underpowered", {
            "size_eligible": len(size_ok),
            "failed_size_eligible": len(failed),
        }
    done = [r for r in size_ok if r["status"] == "ok"]
    n_models = len(done)
    if n_models < 12:
        return "inconclusive", "underpowered", {
            "N": n_models,
            "size_eligible": len(size_ok),
            "failed_size_eligible": len(failed),
        }

    def c(row, scale):
        return row["counts"][scale]["memory_count"]

    same = sum(1 for r in done if c(r, "10") == c(r, "50") == c(r, "100")) / n_models
    lost = sum(1 for r in done if c(r, "10") < c(r, "100") or c(r, "50") < c(r, "100")) / n_models
    gained = sum(1 for r in done if c(r, "10") > c(r, "100") or c(r, "50") > c(r, "100"))
    stats = {
        "N": n_models,
        "same": same,
        "lost": lost,
        "gained": gained,
        "size_eligible": len(size_ok),
        "failed_size_eligible": len(failed),
    }
    if same >= 0.50 and lost <= 0.20 and gained >= 1:
        return "supports", None, stats
    if lost >= 0.40 or (gained == 0 and same < 0.50):
        return "refutes", None, stats
    return "mixed", None, stats


def public_row(row):
    return {
        "id": row["id"],
        "status": row["status"],
        "reason": row.get("reason"),
        "n_species": row.get("n_species"),
        "size_eligible": row.get("size_eligible"),
        "counts": row.get("counts"),
        "seconds": row.get("seconds"),
        "sha256": (row.get("file") or {}).get("sha256"),
        "byte_size": (row.get("file") or {}).get("byte_size"),
        "name": (row.get("file") or {}).get("name"),
    }


def main(argv):
    if len(argv) >= 3 and argv[1] == "--one":
        row = screen(argv[2])
        row.pop("traceback", None)
        print(json.dumps(row))
        return 0
    rows = []
    for mid in TABLE_S1:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--one", mid],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S + 60,
            cwd=HERE,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            rows.append(
                {
                    "id": mid,
                    "status": "excluded",
                    "reason": f"worker exit {proc.returncode}: {(proc.stderr or '')[-400:]}",
                    "size_eligible": False,
                    "counts": {},
                    "file": None,
                }
            )
        else:
            rows.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        brief = public_row(rows[-1])
        print(
            f"{brief['id']} n={brief['n_species']} {brief['status']} "
            f"{brief.get('counts')} {brief.get('seconds')}s {brief.get('reason') or ''}",
            flush=True,
        )
    verdict, reason, stats = decide(rows)
    payload = {
        "verdict": verdict,
        "reason": reason,
        "stats": stats,
        "models": [public_row(r) for r in rows],
        "files": [
            {
                "id": r["id"],
                "name": (r.get("file") or {}).get("name"),
                "download_url": (r.get("file") or {}).get("download_url"),
                "retrieved_at": (r.get("file") or {}).get("retrieved_at"),
                "byte_size": (r.get("file") or {}).get("byte_size"),
                "sha256": (r.get("file") or {}).get("sha256"),
                "license": (r.get("file") or {}).get("license"),
            }
            for r in rows
            if r.get("file")
        ],
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    dest = os.path.join(HERE, "derived", "measured.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "stats": stats}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
