#!/usr/bin/env python3
"""UCS-memory retention screen for levin-2022-grn-learning-11.

The decision rule is the pre-registered one in result.json. Do not change
thresholds after trajectories exist.

    python3 analysis.py
    python3 analysis.py --self-test

Writes derived/measured.json. Does not edit result.json.
Claim 08 imports screen_model() and does not use the retention arms.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"

BIOMODELS = [
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

# simCnt = 5000 steps of h = 0.01 is 50 time units. Samples are every 0.1.
T0 = 50.0
DT = 0.1
CLAMP_SCALE = 100.0
R_SCALE = 2.0
BUDGET_S = 240.0
USER_AGENT = "DelphiClaimTest/1.0 (levin-2022-grn-learning-11; computational reimplementation)"


def download_url(model_id: str) -> str:
    return (
        "https://www.ebi.ac.uk/biomodels/model/download/"
        f"{model_id}?filename={model_id}_url.xml"
    )


def fetch_sbml(cache: Path, model_id: str) -> dict:
    sbml_dir = cache / "sbml"
    sbml_dir.mkdir(parents=True, exist_ok=True)
    path = sbml_dir / f"{model_id}.xml"
    meta_path = sbml_dir / f"{model_id}.meta.json"
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != meta["sha256"] or len(data) != meta["byte_size"]:
            raise RuntimeError(f"cache checksum mismatch for {model_id}")
        meta["path"] = str(path)
        return meta
    url = download_url(model_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        final_url = resp.geturl()
    path.write_bytes(data)
    meta = {
        "biomodel_id": model_id,
        "download_url": url,
        "final_url": final_url,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "path": str(path),
    }
    meta_path.write_text(json.dumps({k: v for k, v in meta.items() if k != "path"}, indent=2) + "\n")
    return meta


def _concs(rr) -> np.ndarray:
    return np.asarray(rr.model.getFloatingSpeciesConcentrations(), dtype=float)


def _set_concs(rr, values: np.ndarray) -> None:
    rr.model.setFloatingSpeciesConcentrations(np.asarray(values, dtype=float))


def _configure(rr, abs_tol: float, rel_tol: float) -> None:
    rr.integrator.absolute_tolerance = abs_tol
    rr.integrator.relative_tolerance = rel_tol


def _load(path: str, abs_tol: float, rel_tol: float):
    import roadrunner

    rr = roadrunner.RoadRunner(path)
    _configure(rr, abs_tol, rel_tol)
    ids = list(rr.model.getFloatingSpeciesIds())
    rr.timeCourseSelections = ["time"] + [f"[{s}]" for s in ids]
    return rr, ids


def integrate_mean(rr, duration: float, deadline: float, clamp_index: int | None = None, clamp_value: float | None = None):
    """Advance `duration` from the current state. Time is whatever the solver holds.

    Returns the mean concentration of each floating species.
    """
    steps = int(round(duration / DT))
    if steps <= 0:
        raise RuntimeError("empty window")
    acc = np.zeros(rr.model.getNumFloatingSpecies())
    # After reset() or a concentration restore, model time is 0. After simulate() it is the end time.
    try:
        t = float(rr.model.getTime())
    except Exception:
        t = 0.0
    stim_min = np.inf
    stim_max = -np.inf
    for _ in range(steps):
        if time.monotonic() > deadline:
            raise TimeoutError("integration budget")
        if clamp_index is not None:
            _set_concs_one(rr, clamp_index, clamp_value)
        t = float(rr.oneStep(t, DT))
        sample = _concs(rr)
        if not np.all(np.isfinite(sample)):
            raise RuntimeError("non-finite concentration")
        acc += sample
        if clamp_index is not None:
            stim_min = min(stim_min, float(sample[clamp_index]))
            stim_max = max(stim_max, float(sample[clamp_index]))
            _set_concs_one(rr, clamp_index, clamp_value)
    stimulus_range = 0.0 if clamp_index is None else float(stim_max - stim_min)
    return acc / steps, stimulus_range


def _set_concs_one(rr, index: int, value: float) -> None:
    values = _concs(rr)
    values[index] = value
    _set_concs(rr, values)


def relax_mean(rr, duration: float, deadline: float):
    """Unstimulated advance using one simulate() call. Returns the column means.

    Samples every 0.5 time units. Leaves the solver at the end of the window.
    """
    if time.monotonic() > deadline:
        raise TimeoutError("integration budget")
    try:
        t0 = float(rr.model.getTime())
    except Exception:
        t0 = 0.0
    n_points = int(round(duration / 0.5)) + 1
    data = np.asarray(rr.simulate(t0, t0 + duration, n_points), dtype=float)
    if data.ndim != 2 or data.shape[1] < 2:
        raise RuntimeError("simulate returned no species")
    block = data[:, 1:]
    if not np.all(np.isfinite(block)):
        raise RuntimeError("non-finite concentration")
    return block.mean(axis=0)


def restores(rr, state: np.ndarray) -> None:
    """Return to a saved concentration. reset() restarts time; concentrations are then overwritten."""
    rr.reset()
    _set_concs(rr, state)


def retains(baseline: float, stim: float, relax: float, updn: int) -> bool:
    """DetectMem: at least half the excursion is still present after the relax."""
    if not (np.isfinite(baseline) and np.isfinite(stim) and np.isfinite(relax)):
        return False
    if updn == 1:
        return bool(relax >= baseline + (stim - baseline) / 2.0)
    if updn == 2:
        return bool(relax <= baseline - (baseline - stim) / 2.0)
    return False


def regulates(baseline: float, ref: float, stim: float, updn: int) -> bool:
    """Factor-of-two regulation against both the baseline window and the next free window."""
    if not (np.isfinite(baseline) and np.isfinite(ref) and np.isfinite(stim)):
        return False
    if updn == 1:
        return bool(stim >= R_SCALE * baseline and stim > R_SCALE * ref)
    if updn == 2:
        return bool(stim <= baseline / R_SCALE and stim < ref / R_SCALE)
    return False


def is_ucs_memory(baseline: float, ref: float, stim: float, relax: float, updn: int) -> bool:
    return regulates(baseline, ref, stim, updn) and retains(baseline, stim, relax, updn)


def _retest(rr, state, u, level, r, updn, wait, deadline) -> bool:
    restores(rr, state)
    waited = relax_mean(rr, wait, deadline)
    stim_mean, _ = integrate_mean(rr, T0, deadline, u, level)
    relax, _ = integrate_mean(rr, T0, deadline, None, None)
    return retains(float(waited[r]), float(stim_mean[r]), float(relax[r]), updn)


def screen_model(meta: dict, deadline: float, retention: bool) -> dict:
    """UCS-memory screen. Retention arms run only when retention is True and a memory exists."""
    model_id = meta["biomodel_id"]
    record = {
        "biomodel_id": model_id,
        "table_s1_index": BIOMODELS.index(model_id) + 1,
        "testable": False,
        "retention_done": False,
        "reason": None,
        "n_species": None,
        "n_memories": 0,
        "n_stable_100": 0,
        "n_recalled_100": 0,
        "fraction_stable": None,
        "fraction_recalled": None,
        "examples": [],
        "tolerances": None,
        "file": {k: meta[k] for k in ("download_url", "final_url", "retrieved_at", "byte_size", "sha256")},
    }
    last_error = None
    for abs_tol, rel_tol in ((1e-3, 1e-3), (1e-8, 1e-6)):
        if time.monotonic() > deadline:
            record["reason"] = "time-budget"
            return record
        try:
            rr, ids = _load(meta["path"], abs_tol, rel_tol)
            n = len(ids)
            record["n_species"] = n
            record["tolerances"] = {"absolute": abs_tol, "relative": rel_tol}
            if n < 2:
                record["reason"] = "fewer-than-two-floating-species"
                return record
            rr.reset()
            x1_mean, _ = integrate_mean(rr, T0, deadline)
            state_after_x1 = _concs(rr).copy()
            ref_mean, _ = integrate_mean(rr, T0, deadline)
            # Max and min over the baseline window, including zeros, as in Initialize_Recheck.
            # Recompute by a second pass so the extrema are of X1 only.
            rr.reset()
            steps = int(round(T0 / DT))
            nz = np.zeros((steps, n))
            t = 0.0
            try:
                t = float(rr.model.getTime())
            except Exception:
                t = 0.0
            for i in range(steps):
                if time.monotonic() > deadline:
                    raise TimeoutError("integration budget")
                t = float(rr.oneStep(t, DT))
                nz[i] = _concs(rr)
            fd_up = nz.max(axis=0) * CLAMP_SCALE
            fd_dn = nz.min(axis=0) / CLAMP_SCALE
            memories = []
            for direction, fd, updn in (("up", fd_up, 1), ("down", fd_dn, 2)):
                for u, level in enumerate(fd):
                    if not np.isfinite(level) or level == 0.0:
                        continue
                    if time.monotonic() > deadline:
                        raise TimeoutError("integration budget")
                    restores(rr, state_after_x1)
                    stim_mean, stim_range = integrate_mean(rr, T0, deadline, u, float(level))
                    relax, _ = integrate_mean(rr, T0, deadline, None, None)
                    if stim_range <= 0.0:
                        continue
                    end_state = _concs(rr).copy()
                    for r in range(n):
                        if r == u:
                            continue
                        if is_ucs_memory(
                            float(x1_mean[r]), float(ref_mean[r]),
                            float(stim_mean[r]), float(relax[r]), updn,
                        ):
                            memories.append({
                                "u": u,
                                "r": r,
                                "updn": updn,
                                "level": float(level),
                                "direction": direction,
                                "ucs": ids[u],
                                "response": ids[r],
                                "end_state": end_state,
                            })
            record["testable"] = True
            record["reason"] = None
            record["n_memories"] = len(memories)
            record["examples"] = [
                {k: m[k] for k in ("ucs", "response", "direction", "level")}
                for m in memories[:3]
            ]
            if not retention or not memories:
                record["retention_done"] = bool(retention and record["testable"])
                # A model with no memories has nothing to retain. It is outside
                # the claim, but the screen itself finished.
                if retention and record["testable"]:
                    record["retention_done"] = True
                    record["fraction_stable"] = None
                    record["fraction_recalled"] = None
                return record
            n_stable = 0
            n_recalled = 0
            for mem in memories:
                if time.monotonic() > deadline:
                    raise TimeoutError("integration budget")
                try:
                    ok_stable = _retest(
                        rr, mem["end_state"], mem["u"], mem["level"], mem["r"], mem["updn"],
                        100.0 * T0, deadline,
                    )
                except TimeoutError:
                    raise
                except Exception:
                    ok_stable = False
                try:
                    # Chained arm: wait 10x, recall (stim + relax), wait 90x, test again.
                    restores(rr, mem["end_state"])
                    relax_mean(rr, 10.0 * T0, deadline)
                    integrate_mean(rr, T0, deadline, mem["u"], mem["level"])
                    integrate_mean(rr, T0, deadline, None, None)
                    waited = relax_mean(rr, 90.0 * T0, deadline)
                    stim_mean, _ = integrate_mean(rr, T0, deadline, mem["u"], mem["level"])
                    relax, _ = integrate_mean(rr, T0, deadline, None, None)
                    ok_recalled = retains(
                        float(waited[mem["r"]]), float(stim_mean[mem["r"]]),
                        float(relax[mem["r"]]), mem["updn"],
                    )
                except TimeoutError:
                    raise
                except Exception:
                    ok_recalled = False
                n_stable += int(ok_stable)
                n_recalled += int(ok_recalled)
            mcount = len(memories)
            record["n_stable_100"] = n_stable
            record["n_recalled_100"] = n_recalled
            record["fraction_stable"] = n_stable / mcount
            record["fraction_recalled"] = n_recalled / mcount
            record["retention_done"] = True
            return record
        except TimeoutError:
            record["reason"] = "time-budget"
            record["testable"] = False
            return record
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
    record["reason"] = "integration-failed"
    record["error"] = last_error
    return record


def decide(models: list[dict]) -> dict:
    """Pre-registered verdict for the retention claim."""
    finished = [
        m for m in models
        if m.get("retention_done") and m.get("n_memories", 0) > 0 and m.get("fraction_stable") is not None
    ]
    n = len(finished)
    if n < 10:
        return {
            "verdict": "inconclusive",
            "reason": "underpowered" if n else "data-unavailable",
            "confidence": 0.60,
            "n": n,
            "clause_A": None,
            "clause_B": None,
            "clause_C": None,
        }
    bulk = [m["fraction_stable"] > 0.5 for m in finished]
    recall_ok = [m["fraction_recalled"] >= m["fraction_stable"] - 0.10 for m in finished]
    strengthened = [m["fraction_recalled"] > m["fraction_stable"] + 0.05 for m in finished]
    clause_a = sum(bulk) > n / 2.0
    clause_b = (sum(recall_ok) / n) >= 0.80
    clause_c = (sum(strengthened) / n) < 0.20
    flags = (clause_a, clause_b, clause_c)
    if all(flags):
        verdict = "supports"
    elif not any(flags):
        verdict = "refutes"
    else:
        verdict = "mixed"
    # "more than n/2" flips if n_bulk is floor(n/2) (barely false) or floor(n/2)+1 (barely true).
    n_bulk = sum(bulk)
    fragile = n_bulk == (n // 2) or n_bulk == (n // 2 + 1)
    if fragile:
        confidence = 0.45
    elif n >= 20:
        confidence = 0.70
    else:
        confidence = 0.55
    return {
        "verdict": verdict,
        "reason": None,
        "confidence": confidence,
        "n": n,
        "n_bulk": n_bulk,
        "n_recall_ok": sum(recall_ok),
        "n_strengthened": sum(strengthened),
        "clause_A": clause_a,
        "clause_B": clause_b,
        "clause_C": clause_c,
    }


def decide_existential(models: list[dict]) -> dict:
    """Pre-registered verdict for levin-2022-grn-learning-08. One memory is enough."""
    testable = [m for m in models if m.get("testable")]
    n_mem = sum(m.get("n_memories", 0) for m in testable)
    n = len(testable)
    if n_mem >= 1:
        verdict, reason, confidence = "supports", None, 0.70
    elif n >= 10:
        verdict, reason, confidence = "refutes", None, 0.55
    elif n >= 1:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.60
    else:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.60
    return {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "n_testable": n,
        "n_memories": n_mem,
        "n_models_with_memory": sum(1 for m in testable if m.get("n_memories", 0) > 0),
    }


def _public(m: dict) -> dict:
    return {
        "biomodel_id": m["biomodel_id"],
        "table_s1_index": m["table_s1_index"],
        "testable": m["testable"],
        "retention_done": m["retention_done"],
        "reason": m["reason"],
        "n_species": m["n_species"],
        "n_memories": m["n_memories"],
        "n_stable_100": m["n_stable_100"],
        "n_recalled_100": m["n_recalled_100"],
        "fraction_stable": m["fraction_stable"],
        "fraction_recalled": m["fraction_recalled"],
        "tolerances": m["tolerances"],
    }


def write_retention_report(models: list[dict]) -> dict:
    decision = decide(models)
    finished = [
        m for m in models
        if m.get("retention_done") and m.get("n_memories", 0) > 0 and m.get("fraction_stable") is not None
    ]
    payload = {
        "claim_id": "levin-2022-grn-learning-11",
        "decision": decision,
        "measured": {
            "value": decision.get("n_bulk", 0) if decision["verdict"] != "inconclusive" else decision["n"],
            "unit": "models with UCS memory that keep more than half of those memories after a 100-fold wait",
            "n": decision["n"],
            "uncertainty": "deterministic given libroadrunner, the SBML files, and the tolerances recorded per model",
            "extra": {
                "verdict": decision["verdict"],
                "reason": decision["reason"],
                "confidence": decision["confidence"],
                "n_models_with_memory_and_retention": decision["n"],
                "n_bulk": decision.get("n_bulk"),
                "n_recall_ok": decision.get("n_recall_ok"),
                "n_strengthened": decision.get("n_strengthened"),
                "clause_A_most_keep_the_bulk": decision.get("clause_A"),
                "clause_B_recall_usually_spares": decision.get("clause_B"),
                "clause_C_strengthening_is_uncommon": decision.get("clause_C"),
                "n_testable": sum(1 for m in models if m.get("testable")),
                "n_with_any_memory": sum(1 for m in models if m.get("n_memories", 0) > 0),
                "n_memories": sum(m.get("n_memories", 0) for m in models if m.get("testable")),
                "per_model": [_public(m) for m in models],
            },
        },
        "examples": [
            {"biomodel_id": m["biomodel_id"], "examples": m["examples"]}
            for m in models if m.get("examples")
        ],
        "files": [m["file"] for m in models if m.get("file")],
    }
    # value for inconclusive should still be a measured count, not a verdict label.
    if decision["verdict"] == "inconclusive":
        payload["measured"]["value"] = decision.get("n_bulk", decision["n"]) if decision.get("n_bulk") is not None else decision["n"]
        payload["measured"]["unit"] = "models with a finished retention screen"
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def run_ids(ids: list[str], cache: Path, retention: bool) -> list[dict]:
    models = []
    for model_id in ids:
        print(f"fetch {model_id}", flush=True)
        started = time.monotonic()
        try:
            meta = fetch_sbml(cache, model_id)
        except Exception as exc:
            models.append({
                "biomodel_id": model_id,
                "table_s1_index": BIOMODELS.index(model_id) + 1,
                "testable": False,
                "retention_done": False,
                "reason": "download-failed",
                "error": f"{type(exc).__name__}: {exc}",
                "n_species": None,
                "n_memories": 0,
                "n_stable_100": 0,
                "n_recalled_100": 0,
                "fraction_stable": None,
                "fraction_recalled": None,
                "examples": [],
                "tolerances": None,
                "file": None,
            })
            print(f"  download failed: {exc}", flush=True)
            continue
        print(f"  {meta['byte_size']} bytes", flush=True)
        record = screen_model(meta, started + BUDGET_S, retention)
        models.append(record)
        print(
            f"  testable={record['testable']} species={record['n_species']} "
            f"mem={record['n_memories']} stable={record['fraction_stable']} "
            f"recalled={record['fraction_recalled']} reason={record['reason']}",
            flush=True,
        )
    return models


def self_test() -> None:
    assert retains(1.0, 3.0, 2.5, 1)
    assert not retains(1.0, 3.0, 1.5, 1)
    assert retains(4.0, 1.0, 2.0, 2)  # midpoint is 2.5? baseline 4, stim 1, half excursion: 4 - (4-1)/2 = 2.5. relax 2 <= 2.5. yes
    assert not retains(4.0, 1.0, 3.0, 2)
    assert regulates(1.0, 1.0, 2.1, 1)  # >= 2x baseline and strictly > 2x the free window
    assert not regulates(1.0, 1.0, 2.0, 1)  # exactly 2x the free window is not enough
    assert regulates(4.0, 4.0, 1.9, 2)
    assert not regulates(4.0, 4.0, 2.0, 2)
    assert is_ucs_memory(1.0, 1.0, 3.0, 2.5, 1)
    assert not is_ucs_memory(1.0, 1.0, 3.0, 1.2, 1)
    # Verdict boundaries, fabricated counts, no trajectories.
    def row(stable, recalled, memories=4):
        return {
            "retention_done": True,
            "n_memories": memories,
            "fraction_stable": stable,
            "fraction_recalled": recalled,
            "testable": True,
        }
    # 10 models, 6 keep the bulk, recall matches, none strengthen: supports, and
    # n_bulk == 6 == n/2+1, so the majority is fragile and confidence is 0.45.
    good = [row(0.75, 0.75) for _ in range(6)] + [row(0.25, 0.25) for _ in range(4)]
    d = decide(good)
    assert d["verdict"] == "supports" and d["confidence"] == 0.45, d
    # 20 models, 15 keep the bulk: not on the one-model boundary.
    solid = [row(0.8, 0.8) for _ in range(15)] + [row(0.2, 0.2) for _ in range(5)]
    d = decide(solid)
    assert d["verdict"] == "supports" and d["confidence"] == 0.70, d
    # Majority fails, recall fails (recalled much lower), strengthening not rare: refutes.
    bad = [row(0.2, 0.0) for _ in range(8)] + [row(0.9, 1.0) for _ in range(2)]
    d = decide(bad)
    assert d["verdict"] == "refutes", d
    assert decide([row(0.8, 0.8) for _ in range(9)])["verdict"] == "inconclusive"
    ex = decide_existential([
        {"testable": True, "n_memories": 0},
        {"testable": True, "n_memories": 2},
    ])
    assert ex["verdict"] == "supports" and ex["confidence"] == 0.70
    none = [{"testable": True, "n_memories": 0} for _ in range(10)]
    assert decide_existential(none)["verdict"] == "refutes"
    assert decide_existential([{"testable": True, "n_memories": 0}])["reason"] == "underpowered"
    print("self-test ok")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    ids = list(args.only) if args.only else list(BIOMODELS)
    unknown = [i for i in ids if i not in BIOMODELS]
    if unknown:
        raise SystemExit(f"not in Table S1: {unknown}")
    models = run_ids(ids, HERE / "cache", retention=True)
    if args.only:
        print("debug subset; not writing derived/measured.json")
        return
    payload = write_retention_report(models)
    print(json.dumps(payload["decision"], indent=2))


if __name__ == "__main__":
    main()
