#!/usr/bin/env python3
"""Sensitization versus habituation breaking in the Biswas, Clawson and Levin
Table S1 pathway models.

Recomputes measured in result.json. Downloads SBML into /tmp (not the repo).
One model per subprocess so a solver crash does not stop the batch.

Usage:
  python3 analysis.py           # screen every model and write derived/measured.json
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
UA = "delphi-claim-test/levin-2022-grn-learning-18"

# Table S1 of ijms-24-00285-s001, in the table's own order. Read from the
# supplement PDF after the preregistration commit 240c8a17, before scoring.
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

# Epoch edges in time units. Stimulation epochs are the odd intervals after
# the opening relaxation: indices 1, 3, 5, 7, 9, 11.
BOUNDS = [0, 500, 1000, 1600, 2200, 2900, 3600, 4400, 5200, 6100, 7000, 8000, 9000]
STIM_INTERVALS = [1, 3, 5, 7, 9, 11]
RATIO = 1.5
SCALE = 100.0
MIN_N = 3
MAX_N = 15
TIMEOUT_S = 180.0
BREAK_LEN = 100.0


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download(mid):
    os.makedirs(CACHE, exist_ok=True)
    url = (
        "https://www.ebi.ac.uk/biomodels/model/download/"
        f"{mid}?filename={mid}_url.xml"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    retrieved = now_iso()
    with urllib.request.urlopen(req, timeout=90) as resp:
        blob = resp.read()
    path = os.path.join(CACHE, f"{mid}_url.xml")
    with open(path, "wb") as fh:
        fh.write(blob)
    name = None
    match = re.search(br'<model\b[^>]*\bname="([^"]*)"', blob)
    if match:
        name = match.group(1).decode("utf-8", "replace")
    license_name = "CC0 1.0" if b"CC0" in blob else None
    return {
        "path": path,
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "name": name,
        "license": license_name,
    }


def load_runner(path):
    import roadrunner

    rr = roadrunner.RoadRunner(path)
    try:
        rr.conservedMoietyAnalysis = False
    except Exception:
        pass
    ids = list(rr.model.getFloatingSpeciesIds())
    y0 = np.array(rr.model.getFloatingSpeciesConcentrations(), dtype=float)
    return rr, ids, y0


def integrate(rr, y0, t0, t1, clamp, deadline, n_eval=21):
    """One adaptive integration. clamp is (index, value) or None."""
    y_start = np.array(y0, dtype=float)
    if clamp is not None:
        y_start[clamp[0]] = float(clamp[1])
    n = y_start.size

    def rhs(t, y):
        if time.monotonic() > deadline:
            raise TimeoutError("model timeout")
        y_eval = np.array(y, dtype=float)
        if clamp is not None:
            y_eval[clamp[0]] = float(clamp[1])
        if not np.all(np.isfinite(y_eval)):
            raise FloatingPointError("non-finite state")
        rr.model.setTime(float(t))
        rr.model.setFloatingSpeciesConcentrations(y_eval.tolist())
        rates = np.array(rr.getRatesOfChange(), dtype=float)
        if rates.shape != (n,):
            raise RuntimeError(f"rate length {rates.shape} != {n}")
        if clamp is not None:
            rates[clamp[0]] = 0.0
        if not np.all(np.isfinite(rates)):
            raise FloatingPointError("non-finite rate")
        return rates

    t_eval = np.linspace(t0, t1, n_eval)
    sol = solve_ivp(
        rhs,
        (float(t0), float(t1)),
        y_start,
        method="BDF",
        rtol=1e-4,
        atol=1e-6,
        t_eval=t_eval,
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y[:, -1].copy(), sol.y.mean(axis=1), sol.y


def unforced_levels(rr, y0, deadline):
    """Nonzero max and min over an unforced 1010-time-unit trajectory."""
    _y_end, _mean, traj = integrate(rr, y0, 0.0, 1010.0, None, deadline, n_eval=202)
    n = y0.size
    up = np.zeros(n)
    down = np.zeros(n)
    for j in range(n):
        nz = traj[j][traj[j] != 0]
        if nz.size == 0:
            continue
        up[j] = float(np.max(nz)) * SCALE
        down[j] = float(np.min(nz)) / SCALE
    return up, down


def six_epoch(rr, y0, ucs, clamp_value, deadline):
    """Return (n, 7) means: opening relax and six stimulation epochs, and y_end."""
    y = np.array(y0, dtype=float)
    means = []
    for i in range(len(BOUNDS) - 1):
        t0, t1 = BOUNDS[i], BOUNDS[i + 1]
        clamp = (ucs, clamp_value) if i in STIM_INTERVALS else None
        y, mean, _samples = integrate(rr, y, t0, t1, clamp, deadline)
        if i == 0 or i in STIM_INTERVALS:
            means.append(mean)
    return np.column_stack(means), y


def is_sens(series):
    prev = series[0]
    for value in series[1:]:
        if not (value >= RATIO * prev and value > prev):
            return False
        prev = value
    return True


def is_hab(series):
    prev = series[0]
    for value in series[1:]:
        if not (value <= prev / RATIO and value < prev):
            return False
        prev = value
    return True


def ratio_holds(m1, m2, kind):
    if kind == "sens":
        return bool(m2 >= RATIO * m1 and m2 > m1)
    return bool(m2 <= m1 / RATIO and m2 < m1)


def two_ucs(rr, y, ucs, ucs_value, deadline):
    y, mean1, _samples = integrate(rr, y, 0.0, BREAK_LEN, (ucs, ucs_value), deadline)
    y, _mean, _samples = integrate(rr, y, 0.0, BREAK_LEN, None, deadline)
    y, mean2, _samples = integrate(rr, y, 0.0, BREAK_LEN, (ucs, ucs_value), deadline)
    return mean1, mean2


def apply_two_clamps(rr, y, node, value, deadline):
    y, _mean, _samples = integrate(rr, y, 0.0, BREAK_LEN, (node, value), deadline)
    y, _mean, _samples = integrate(rr, y, 0.0, BREAK_LEN, None, deadline)
    y, _mean, _samples = integrate(rr, y, 0.0, BREAK_LEN, (node, value), deadline)
    y, _mean, _samples = integrate(rr, y, 0.0, BREAK_LEN, None, deadline)
    return y


def pair_broken(rr, y_trained, ucs, ucs_value, response, levels, deadline, kind):
    """True if some third node breaks the ratio and the no-node control still holds."""
    n = levels.shape[1]
    control1, control2 = two_ucs(rr, y_trained, ucs, ucs_value, deadline)
    if not ratio_holds(control1[response], control2[response], kind):
        return False
    for node in range(n):
        if node == ucs or node == response:
            continue
        for direction in (0, 1):
            value = levels[direction, node]
            if not np.isfinite(value) or value == 0.0:
                continue
            y = apply_two_clamps(rr, y_trained, node, value, deadline)
            m1, m2 = two_ucs(rr, y, ucs, ucs_value, deadline)
            if not ratio_holds(m1[response], m2[response], kind):
                return True
    return False


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
        "sens_pairs": 0,
        "hab_pairs": 0,
        "sens_breakable": 0,
        "hab_breakable": 0,
        "seconds": None,
        "file": meta,
    }
    try:
        rr, _ids, y0 = load_runner(meta["path"])
        n = int(y0.size)
        out["n_species"] = n
        out["size_eligible"] = MIN_N <= n <= MAX_N
        if not out["size_eligible"]:
            out["reason"] = f"floating species {n} outside {MIN_N}-{MAX_N}"
            out["seconds"] = round(time.monotonic() - started, 3)
            return out
        up, down = unforced_levels(rr, y0, deadline)
        levels = np.vstack([up, down])
        sens_pairs = []
        hab_pairs = []
        trained = {}
        for ucs in range(n):
            for direction, value in ((0, up[ucs]), (1, down[ucs])):
                if not np.isfinite(value) or value == 0.0:
                    continue
                means, y_end = six_epoch(rr, y0, ucs, float(value), deadline)
                trained[(ucs, direction)] = y_end
                for response in range(n):
                    if response == ucs:
                        continue
                    series = means[response]
                    if is_sens(series):
                        sens_pairs.append((ucs, direction, response))
                    if is_hab(series):
                        hab_pairs.append((ucs, direction, response))
        out["sens_pairs"] = len(sens_pairs)
        out["hab_pairs"] = len(hab_pairs)
        sens_break = 0
        for ucs, direction, response in sens_pairs:
            if pair_broken(
                rr,
                trained[(ucs, direction)],
                ucs,
                float(levels[direction, ucs]),
                response,
                levels,
                deadline,
                "sens",
            ):
                sens_break += 1
        hab_break = 0
        for ucs, direction, response in hab_pairs:
            if pair_broken(
                rr,
                trained[(ucs, direction)],
                ucs,
                float(levels[direction, ucs]),
                response,
                levels,
                deadline,
                "hab",
            ):
                hab_break += 1
        out["sens_breakable"] = sens_break
        out["hab_breakable"] = hab_break
        out["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 — one model must not invent a score
        out["reason"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc(limit=4)
    out["seconds"] = round(time.monotonic() - started, 3)
    return out


def decide(rows):
    downloaded = [r for r in rows if r.get("file")]
    if len(downloaded) < len(TABLE_S1) / 2:
        return "inconclusive", "data-unavailable"
    size_ok = [r for r in rows if r.get("size_eligible")]
    if not size_ok:
        return "inconclusive", "underpowered"
    failed = [r for r in size_ok if r["status"] != "ok"]
    if len(failed) > 0.5 * len(size_ok):
        return "inconclusive", "underpowered"
    completed = [r for r in size_ok if r["status"] == "ok"]
    sensitizing = [r for r in completed if r["sens_pairs"] >= 1]
    habituating = [r for r in completed if r["hab_pairs"] >= 1]
    if len(sensitizing) < 8 or len(habituating) < 8:
        return "inconclusive", "underpowered"
    sb = [r for r in sensitizing if r["sens_breakable"] >= 1]
    hb = [r for r in habituating if r["hab_breakable"] >= 1]
    rate_s = len(sb) / len(sensitizing)
    rate_h = len(hb) / len(habituating)
    mostly = (
        sum(1 for r in sensitizing if (r["sens_breakable"] / r["sens_pairs"]) < 0.05)
        / len(sensitizing)
    )
    supports = (0.15 <= rate_s <= 0.45) and mostly >= 0.50 and rate_h > rate_s
    refutes = rate_s >= 0.50 or mostly < 0.25 or rate_h <= rate_s
    if supports:
        verdict, reason = "supports", None
    elif refutes:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    stats = {
        "S": len(sensitizing),
        "Sb": len(sb),
        "H": len(habituating),
        "Hb": len(hb),
        "Sb_over_S": rate_s,
        "Hb_over_H": rate_h,
        "mostly_under_5": mostly,
        "completed": len(completed),
        "size_eligible": len(size_ok),
        "failed_size_eligible": len(failed),
    }
    return verdict, reason, stats


def strip_private(row):
    keep = {
        "id": row["id"],
        "status": row["status"],
        "reason": row.get("reason"),
        "n_species": row.get("n_species"),
        "size_eligible": row.get("size_eligible"),
        "sens_pairs": row.get("sens_pairs"),
        "hab_pairs": row.get("hab_pairs"),
        "sens_breakable": row.get("sens_breakable"),
        "hab_breakable": row.get("hab_breakable"),
        "seconds": row.get("seconds"),
        "sha256": (row.get("file") or {}).get("sha256"),
        "byte_size": (row.get("file") or {}).get("byte_size"),
        "name": (row.get("file") or {}).get("name"),
    }
    return keep


def main(argv):
    if len(argv) >= 3 and argv[1] == "--one":
        row = screen(argv[2])
        row.pop("traceback", None)
        # file path is local; keep hashes
        print(json.dumps(row))
        return 0
    rows = []
    for mid in TABLE_S1:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--one", mid],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S + 45,
            cwd=HERE,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            rows.append(
                {
                    "id": mid,
                    "status": "excluded",
                    "reason": f"worker exit {proc.returncode}: {(proc.stderr or '')[-400:]}",
                    "size_eligible": False,
                    "sens_pairs": 0,
                    "hab_pairs": 0,
                    "sens_breakable": 0,
                    "hab_breakable": 0,
                    "file": None,
                }
            )
            continue
        line = proc.stdout.strip().splitlines()[-1]
        rows.append(json.loads(line))
        brief = strip_private(rows[-1])
        print(
            f"{brief['id']} n={brief['n_species']} {brief['status']} "
            f"sens={brief['sens_pairs']}/{brief['sens_breakable']} "
            f"hab={brief['hab_pairs']}/{brief['hab_breakable']} "
            f"{brief['seconds']}s {brief['reason'] or ''}",
            flush=True,
        )
    verdict = decide(rows)
    # decide returns 2 or 3
    if len(verdict) == 2:
        verdict_name, reason = verdict
        stats = {}
    else:
        verdict_name, reason, stats = verdict
    payload = {
        "verdict": verdict_name,
        "reason": reason,
        "stats": stats,
        "models": [strip_private(r) for r in rows],
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
    out_dir = os.path.join(HERE, "derived")
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "measured.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict_name, "reason": reason, "stats": stats}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except subprocess.TimeoutExpired as exc:
        print(f"parent timeout: {exc}", file=sys.stderr)
        sys.exit(1)
