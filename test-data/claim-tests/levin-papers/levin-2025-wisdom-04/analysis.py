#!/usr/bin/env python3
"""Habituation, sensitization and Pavlovian conditioning in fixed-weight
gene circuits and in the Table S1 pathway models.

Recomputes measured in result.json. SBML downloads stay in /tmp.

Usage:
  python3 analysis.py
  python3 analysis.py --grn
  python3 analysis.py --one BIOMD0000000010
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np
from scipy.integrate import solve_ivp

HERE = os.path.dirname(os.path.abspath(__file__))
RATIO = 1.5
FACTOR = 2.0
BOUNDS = [0, 500, 1000, 1600, 2200, 2900, 3600, 4400, 5200, 6100, 7000, 8000, 9000]
STIM_INTERVALS = [1, 3, 5, 7, 9, 11]
EPOCH = 50.0
SCALE = 100.0

MOTIFS = {
    "toggle": {
        "W": np.array([[0, 10, 0, 0], [10, 0, 0, 0], [0, 0, 0, 0], [-5, 0, 0, 0]], dtype=float),
        "b": np.array([-2, -2, 0, 1], dtype=float),
        "tau": np.array([1, 1, 1, 1], dtype=float),
    },
    "repression_ring": {
        "W": np.array([[0, -8, 0, 0], [0, 0, -8, 0], [-8, 0, 0, 0], [0, 0, 0, 0]], dtype=float),
        "b": np.array([2, 2, 2, 0], dtype=float),
        "tau": np.ones(4),
    },
    "incoherent_feedforward": {
        "W": np.array([[0, 0, 0, 0], [12, 0, -12, 0], [8, 0, 0, 0], [0, 0, 0, 0]], dtype=float),
        "b": np.array([0, -1, -1, 0], dtype=float),
        "tau": np.ones(4),
    },
    "slow_repressor": {
        "W": np.array([[6, -10, 0, 0], [8, 0, 0, 0], [0, 4, 0, 0], [0, 0, 0, 0]], dtype=float),
        "b": np.array([-1, -2, 0, 0], dtype=float),
        "tau": np.array([1, 5, 1, 1], dtype=float),
    },
}


def logistic(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    expz = np.exp(z[~pos])
    out[~pos] = expz / (1.0 + expz)
    return out


def grn_rhs(y, W, b, tau, clamps):
    y_eval = np.array(y, dtype=float)
    for idx, value in clamps.items():
        y_eval[idx] = value
    dy = (logistic(b + W @ y_eval) - y_eval) / tau
    for idx in clamps:
        dy[idx] = 0.0
    return dy


def grn_integrate(y0, duration, W, b, tau, clamps, n_eval=21):
    y_start = np.array(y0, dtype=float)
    for idx, value in clamps.items():
        y_start[idx] = float(value)

    def rhs(_t, y):
        return grn_rhs(y, W, b, tau, clamps)

    sol = solve_ivp(
        rhs,
        (0.0, float(duration)),
        y_start,
        method="BDF",
        rtol=1e-4,
        atol=1e-6,
        t_eval=np.linspace(0.0, float(duration), n_eval),
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y[:, -1].copy(), sol.y.mean(axis=1), sol.y


def strict_rise(series):
    prev = series[0]
    for value in series[1:]:
        if not (value >= RATIO * prev and value > prev):
            return False
        prev = value
    return True


def strict_fall(series):
    prev = series[0]
    for value in series[1:]:
        if not (value <= prev / RATIO and value < prev):
            return False
        prev = value
    return True


def reg_dir(baseline, stimulated):
    if stimulated >= FACTOR * baseline and stimulated > baseline:
        return 1
    if stimulated <= baseline / FACTOR and stimulated < baseline:
        return 2
    return 0


def phenotype_grn(W, b, tau):
    """Return booleans hab, sens, pav and confirm W is not written."""
    digest = hashlib.sha256(np.ascontiguousarray(W).tobytes()).hexdigest()
    y0 = np.full(W.shape[0], 0.5)
    _end, _mean, samples = grn_integrate(y0, 1010.0, W, b, tau, {}, n_eval=202)
    up = np.zeros(W.shape[0])
    down = np.zeros(W.shape[0])
    for j in range(W.shape[0]):
        nz = samples[j][samples[j] != 0]
        if nz.size == 0:
            continue
        up[j] = float(nz.max()) * SCALE
        down[j] = float(nz.min()) / SCALE
    hab = False
    sens = False
    n = W.shape[0]
    for node in range(n):
        for value in (up[node], down[node]):
            if not np.isfinite(value) or value == 0.0:
                continue
            y = y0.copy()
            columns = []
            for i in range(len(BOUNDS) - 1):
                clamps = {node: float(value)} if i in STIM_INTERVALS else {}
                y, mean, _s = grn_integrate(y, BOUNDS[i + 1] - BOUNDS[i], W, b, tau, clamps)
                if i == 0 or i in STIM_INTERVALS:
                    columns.append(mean)
            means = np.column_stack(columns)
            for response in range(n):
                if response == node:
                    continue
                if strict_fall(means[response]):
                    hab = True
                if strict_rise(means[response]):
                    sens = True
            if hab and sens:
                break
        if hab and sens:
            break
    # Pavlovian at scale 100, the normal training amplitude.
    y_ss, base_mean, base_samples = grn_integrate(y0, EPOCH, W, b, tau, {})
    maxima = base_samples.max(axis=1)
    minima = base_samples.min(axis=1)
    up_m = maxima * SCALE
    down_m = minima / SCALE
    single = {}
    for node in range(n):
        for which, value in ((1, up_m[node]), (2, down_m[node])):
            if not np.isfinite(value) or value == 0.0:
                continue
            _y, mean, _s = grn_integrate(y_ss, EPOCH, W, b, tau, {node: float(value)})
            single[(node, which)] = mean
    pav = False
    keys = list(single)
    for ucs, ucs_dir in keys:
        for ns, ns_dir in keys:
            if ns == ucs:
                continue
            responses = []
            for r in range(n):
                if r == ucs or r == ns:
                    continue
                if reg_dir(base_mean[r], single[(ucs, ucs_dir)][r]) == 0:
                    continue
                if reg_dir(base_mean[r], single[(ns, ns_dir)][r]) != 0:
                    continue
                responses.append(r)
            if not responses:
                continue
            clamps = {
                ucs: float(up_m[ucs] if ucs_dir == 1 else down_m[ucs]),
                ns: float(up_m[ns] if ns_dir == 1 else down_m[ns]),
            }
            y, _m, _s = grn_integrate(y_ss, EPOCH, W, b, tau, clamps)
            y, relax, _s = grn_integrate(y, EPOCH, W, b, tau, {})
            ns_value = float(up_m[ns] if ns_dir == 1 else down_m[ns])
            _y, tested, _s = grn_integrate(y, EPOCH, W, b, tau, {ns: ns_value})
            if any(reg_dir(relax[r], tested[r]) != 0 for r in responses):
                pav = True
                break
        if pav:
            break
    after = hashlib.sha256(np.ascontiguousarray(W).tobytes()).hexdigest()
    if after != digest:
        raise RuntimeError("weight matrix changed")
    return {"habituation": hab, "sensitization": sens, "pavlovian": pav, "weight_sha256": digest}


def random_panel(seed=20261101):
    rng = np.random.default_rng(seed)
    panel = []
    for i in range(40):
        W = rng.uniform(-30.0, 30.0, size=(4, 4))
        np.fill_diagonal(W, 0.0)
        b = rng.uniform(-1.0, 1.0, size=4)
        tau = np.ones(4)
        panel.append((f"random-{i:02d}", W, b, tau))
    for name, spec in MOTIFS.items():
        panel.append((name, spec["W"].copy(), spec["b"].copy(), spec["tau"].copy()))
    return panel


def run_grn():
    found = {"habituation": [], "sensitization": [], "pavlovian": []}
    rows = []
    for name, W, b, tau in random_panel():
        flags = phenotype_grn(W, b, tau)
        rows.append({"network": name, **{k: flags[k] for k in found}, "weight_sha256": flags["weight_sha256"]})
        for key in found:
            if flags[key]:
                found[key].append(name)
    return {
        "n_networks": len(rows),
        "habituation": len(found["habituation"]) > 0,
        "sensitization": len(found["sensitization"]) > 0,
        "pavlovian": len(found["pavlovian"]) > 0,
        "examples": {k: v[:5] for k, v in found.items()},
        "counts": {k: len(v) for k, v in found.items()},
        "weight_unchanged": all(r["weight_sha256"] for r in rows),
        "networks": rows,
    }


def main(argv):
    if len(argv) >= 2 and argv[1] == "--grn":
        print(json.dumps(run_grn()))
        return 0
    if len(argv) >= 2 and argv[1] == "--one":
        # Pathway half is filled by importing the sibling screen only through
        # this process's own functions, below.
        print(json.dumps(screen_pathway(argv[2])))
        return 0
    grn = run_grn()
    print("grn", {k: grn[k] for k in ("habituation", "sensitization", "pavlovian", "counts")}, flush=True)
    pathways = run_pathways(grn)
    verdict, reason = decide(grn, pathways)
    payload = {"verdict": verdict, "reason": reason, "grn": {k: v for k, v in grn.items() if k != "networks"}, "pathways": pathways}
    # Keep the per-network flags; drop nothing else. The file stays small.
    payload["grn_networks"] = grn["networks"]
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "reason": reason}, indent=2))
    return 0


# Pathway screening is appended below so --grn does not need roadrunner.


TABLE_S1 = [
    "BIOMD0000000001", "BIOMD0000000002", "BIOMD0000000003", "BIOMD0000000004",
    "BIOMD0000000005", "BIOMD0000000006", "BIOMD0000000010", "BIOMD0000000069",
    "BIOMD0000000016", "BIOMD0000000017", "BIOMD0000000022", "BIOMD0000000021",
    "BIOMD0000000023", "BIOMD0000000024", "BIOMD0000000026", "BIOMD0000000027",
    "BIOMD0000000483", "BIOMD0000000029", "BIOMD0000000031", "BIOMD0000000631",
    "BIOMD0000000203", "BIOMD0000000204", "BIOMD0000000209", "BIOMD0000000210",
    "BIOMD0000000539", "BIOMD0000000664", "BIOMD0000000275", "BIOMD0000000697",
    "BIOMD0000000600", "BIOMD0000000039", "BIOMD0000000050", "BIOMD0000000035",
    "BIOMD0000000036", "BIOMD0000000037", "BIOMD0000000038",
]
PATH_TIMEOUT = 180.0
PATH_BUDGET = 1500.0
MIN_N = 3
MAX_N = 12


def screen_pathway(mid):
    """One pathway model, using only this file's integrator."""
    return _screen_pathway_local(mid)


def _screen_pathway_local(mid):
    import hashlib as _hashlib
    import re
    import urllib.request
    from datetime import datetime, timezone
    import roadrunner

    started = time.monotonic()
    deadline = started + PATH_TIMEOUT
    url = f"https://www.ebi.ac.uk/biomodels/model/download/{mid}?filename={mid}_url.xml"
    req = urllib.request.Request(url, headers={"User-Agent": "delphi-claim-test/levin-2025-wisdom-04"})
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with urllib.request.urlopen(req, timeout=90) as resp:
        blob = resp.read()
    cache = os.environ.get("GRN_SBML_CACHE", "/tmp/delphi-grn-sbml")
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, f"{mid}_url.xml")
    with open(path, "wb") as fh:
        fh.write(blob)
    name = None
    match = re.search(br'<model\b[^>]*\bname="([^"]*)"', blob)
    if match:
        name = match.group(1).decode("utf-8", "replace")
    file_info = {
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(blob),
        "sha256": _hashlib.sha256(blob).hexdigest(),
        "name": name,
        "license": "CC0 1.0" if b"CC0" in blob else None,
    }
    out = {
        "id": mid,
        "status": "excluded",
        "reason": None,
        "n_species": None,
        "size_eligible": False,
        "habituation": False,
        "sensitization": False,
        "pavlovian": False,
        "seconds": None,
        "file": file_info,
    }
    try:
        rr = roadrunner.RoadRunner(path)
        try:
            rr.conservedMoietyAnalysis = False
        except Exception:
            pass
        y0 = np.array(rr.model.getFloatingSpeciesConcentrations(), dtype=float)
        n = int(y0.size)
        out["n_species"] = n
        out["size_eligible"] = MIN_N <= n <= MAX_N
        if not out["size_eligible"]:
            out["reason"] = f"floating species {n} outside {MIN_N}-{MAX_N}"
            out["seconds"] = round(time.monotonic() - started, 3)
            return out
        flags = _pathway_flags(rr, y0, deadline)
        out.update(flags)
        out["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}: {exc}"
    out["seconds"] = round(time.monotonic() - started, 3)
    return out


def _rr_integrate(rr, y0, duration, clamps, deadline, n_eval=21):
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
            raise RuntimeError("rate length")
        for idx in clamps:
            rates[idx] = 0.0
        if not np.all(np.isfinite(rates)):
            raise FloatingPointError("non-finite rate")
        return rates

    sol = solve_ivp(
        rhs, (0.0, float(duration)), y_start, method="BDF", rtol=1e-4, atol=1e-6,
        t_eval=np.linspace(0.0, float(duration), n_eval),
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y[:, -1].copy(), sol.y.mean(axis=1), sol.y


def _pathway_flags(rr, y0, deadline):
    n = y0.size
    _e, _m, samples = _rr_integrate(rr, y0, 1010.0, {}, deadline, n_eval=101)
    up = np.zeros(n)
    down = np.zeros(n)
    for j in range(n):
        nz = samples[j][samples[j] != 0]
        if nz.size == 0:
            continue
        up[j] = float(nz.max()) * SCALE
        down[j] = float(nz.min()) / SCALE
    hab = False
    sens = False
    for node in range(n):
        for value in (up[node], down[node]):
            if not np.isfinite(value) or value == 0.0:
                continue
            y = np.array(y0, dtype=float)
            columns = []
            for i in range(len(BOUNDS) - 1):
                clamps = {node: float(value)} if i in STIM_INTERVALS else {}
                y, mean, _s = _rr_integrate(rr, y, BOUNDS[i + 1] - BOUNDS[i], clamps, deadline)
                if i == 0 or i in STIM_INTERVALS:
                    columns.append(mean)
            means = np.column_stack(columns)
            for response in range(n):
                if response == node:
                    continue
                hab = hab or strict_fall(means[response])
                sens = sens or strict_rise(means[response])
            if hab and sens:
                break
        if hab and sens:
            break
    y_ss, base_mean, base_samples = _rr_integrate(rr, y0, EPOCH, {}, deadline)
    up_m = base_samples.max(axis=1) * SCALE
    down_m = base_samples.min(axis=1) / SCALE
    single = {}
    for node in range(n):
        for which, value in ((1, up_m[node]), (2, down_m[node])):
            if not np.isfinite(value) or value == 0.0:
                continue
            _y, mean, _s = _rr_integrate(rr, y_ss, EPOCH, {node: float(value)}, deadline)
            single[(node, which)] = mean
    pav = False
    for ucs, ucs_dir in single:
        for ns, ns_dir in single:
            if ns == ucs:
                continue
            responses = [
                r for r in range(n)
                if r != ucs and r != ns
                and reg_dir(base_mean[r], single[(ucs, ucs_dir)][r]) != 0
                and reg_dir(base_mean[r], single[(ns, ns_dir)][r]) == 0
            ]
            if not responses:
                continue
            y, _m, _s = _rr_integrate(
                rr, y_ss, EPOCH,
                {
                    ucs: float(up_m[ucs] if ucs_dir == 1 else down_m[ucs]),
                    ns: float(up_m[ns] if ns_dir == 1 else down_m[ns]),
                },
                deadline,
            )
            y, relax, _s = _rr_integrate(rr, y, EPOCH, {}, deadline)
            ns_value = float(up_m[ns] if ns_dir == 1 else down_m[ns])
            _y, tested, _s = _rr_integrate(rr, y, EPOCH, {ns: ns_value}, deadline)
            if any(reg_dir(relax[r], tested[r]) != 0 for r in responses):
                pav = True
                break
        if pav:
            break
    return {"habituation": hab, "sensitization": sens, "pavlovian": pav}


def run_pathways(grn):
    rows = []
    budget_end = time.monotonic() + PATH_BUDGET
    for mid in TABLE_S1:
        if time.monotonic() > budget_end:
            break
        # Presence is monotonic: stop once every pathway phenotype has been seen.
        seen = {k: any(r.get(k) for r in rows if r.get("status") == "ok") for k in ("habituation", "sensitization", "pavlovian")}
        if all(seen.values()) and sum(1 for r in rows if r.get("status") == "ok") >= 1:
            break
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--one", mid],
            capture_output=True, text=True, timeout=PATH_TIMEOUT + 60, cwd=HERE,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            rows.append({
                "id": mid, "status": "excluded", "size_eligible": False,
                "reason": f"worker exit {proc.returncode}: {(proc.stderr or '')[-300:]}",
            })
        else:
            rows.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        last = rows[-1]
        print(
            f"path {last.get('id')} {last.get('status')} n={last.get('n_species')} "
            f"h={last.get('habituation')} s={last.get('sensitization')} p={last.get('pavlovian')} "
            f"{last.get('seconds')} {last.get('reason') or ''}",
            flush=True,
        )
    completed = [r for r in rows if r.get("status") == "ok"]
    return {
        "completed": len(completed),
        "attempted": len(rows),
        "habituation": any(r.get("habituation") for r in completed),
        "sensitization": any(r.get("sensitization") for r in completed),
        "pavlovian": any(r.get("pavlovian") for r in completed),
        "models": [
            {k: r.get(k) for k in ("id", "status", "reason", "n_species", "size_eligible", "habituation", "sensitization", "pavlovian", "seconds")}
            for r in rows
        ],
        "files": [dict(id=r["id"], **r["file"]) for r in rows if r.get("file")],
    }


def decide(grn, pathways):
    grn_kinds = sum(1 for k in ("habituation", "sensitization", "pavlovian") if grn[k])
    completed = pathways["completed"]
    path_kinds = sum(1 for k in ("habituation", "sensitization", "pavlovian") if pathways[k])
    if completed < 1:
        if grn_kinds == 3:
            return "mixed", None
        return "inconclusive", "underpowered"
    if grn_kinds == 3 and path_kinds == 3:
        return "supports", None
    if grn_kinds == 0 and path_kinds == 0 and completed >= 3:
        return "refutes", None
    return "mixed", None


if __name__ == "__main__":
    sys.exit(main(sys.argv))
