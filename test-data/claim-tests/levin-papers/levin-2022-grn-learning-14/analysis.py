#!/usr/bin/env python3
"""Habituation screen for levin-2022-grn-learning-14.

The decision rule below is the pre-registered one in result.json. Do not change
the thresholds, the model list, the pulse schedule, or the verdict function
after BioModels trajectories have been generated. Implementation repairs that
leave those rules untouched are recorded in result.json caveats.

Re-run from the repo root or from this directory:

    python3 analysis.py

Writes derived/measured.json. Does not edit result.json.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import traceback
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
SBML_DIR = CACHE / "sbml"
DERIVED = HERE / "derived"

# Table S1 of Biswas, Clawson and Levin, Int. J. Mol. Sci. 2023, 24, 285,
# in the order printed there. Copied before any SBML download.
BIOMODELS = [
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

# Chunk index ranges (1-based, inclusive) for the six stimulation windows.
# Each chunk is 0.1 time (ten steps of h = 0.01). Lengths are 500, 600, 700,
# 800, 900, 1000 chunks = 50, 60, 70, 80, 90, 100 time units.
STIM_WINDOWS = (
    (501, 1000),
    (1601, 2200),
    (2901, 3600),
    (4401, 5200),
    (6101, 7000),
    (8001, 9000),
)
N_CHUNKS = 10100
CHUNK_DT = 0.1
CLAMP_SCALE = 100.0
RATIO = 1.5
MEAN_FLOOR = 1e-3
INTEGRATION_BUDGET_S = 240.0
HARD_BUDGET_S = 360.0
MIN_TESTABLE = 10
USER_AGENT = "DelphiClaimTest/1.0 (levin-2022-grn-learning-14; computational reimplementation)"


def download_url(model_id: str) -> str:
    return (
        "https://www.ebi.ac.uk/biomodels/model/download/"
        f"{model_id}?filename={model_id}_url.xml"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_sbml(model_id: str) -> dict:
    """Download one SBML file into the gitignored cache. Idempotent."""
    SBML_DIR.mkdir(parents=True, exist_ok=True)
    path = SBML_DIR / f"{model_id}.xml"
    meta_path = SBML_DIR / f"{model_id}.meta.json"
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        data = path.read_bytes()
        digest = sha256_bytes(data)
        if digest != meta["sha256"] or len(data) != meta["byte_size"]:
            raise RuntimeError(f"cache checksum mismatch for {model_id}")
        return meta
    url = download_url(model_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        final_url = resp.geturl()
    retrieved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_bytes(data)
    meta = {
        "biomodel_id": model_id,
        "download_url": url,
        "final_url": final_url,
        "retrieved_at": retrieved_at,
        "byte_size": len(data),
        "sha256": sha256_bytes(data),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def _configure(rr, abs_tol: float, rel_tol: float) -> None:
    rr.integrator.absolute_tolerance = abs_tol
    rr.integrator.relative_tolerance = rel_tol


def _concentrations(rr) -> np.ndarray:
    return np.asarray(rr.model.getFloatingSpeciesConcentrations(), dtype=float)


def _set_one(rr, index: int, value: float) -> None:
    values = _concentrations(rr)
    values[index] = value
    rr.model.setFloatingSpeciesConcentrations(values)


def _in_stim(chunk: int) -> int | None:
    """Return the stimulation-window index (0..5) if this 1-based chunk is inside one."""
    for k, (a, b) in enumerate(STIM_WINDOWS):
        if a <= chunk <= b:
            return k
    return None


def integrate(rr, clamp_index: int | None, clamp_value: float | None, deadline: float):
    """One full 10100-chunk trajectory.

    Returns (stim_means[6, n], baseline_mean[n], stim_range[n], stimulus_range)
    or raises TimeoutError / RuntimeError.
    """
    n = rr.model.getNumFloatingSpecies()
    stim_sum = np.zeros((6, n))
    stim_cnt = np.zeros(6)
    base_sum = np.zeros(n)
    base_cnt = 0
    stim_min = np.full(n, np.inf)
    stim_max = np.full(n, -np.inf)
    traj_min = np.inf
    traj_max = -np.inf
    t = 0.0
    for chunk in range(1, N_CHUNKS + 1):
        if time.monotonic() > deadline:
            raise TimeoutError("integration budget")
        window = _in_stim(chunk)
        if window is not None and clamp_index is not None:
            _set_one(rr, clamp_index, clamp_value)
        t = float(rr.oneStep(t, CHUNK_DT))
        sample = _concentrations(rr)
        if not np.all(np.isfinite(sample)):
            raise RuntimeError("non-finite concentration")
        if clamp_index is not None:
            traj_min = min(traj_min, float(sample[clamp_index]))
            traj_max = max(traj_max, float(sample[clamp_index]))
        if chunk <= 500:
            base_sum += sample
            base_cnt += 1
        if window is not None:
            stim_sum[window] += sample
            stim_cnt[window] += 1
            stim_min = np.minimum(stim_min, sample)
            stim_max = np.maximum(stim_max, sample)
        if window is not None and clamp_index is not None:
            _set_one(rr, clamp_index, clamp_value)
    if np.any(stim_cnt == 0) or base_cnt == 0:
        raise RuntimeError("empty window")
    stim_means = stim_sum / stim_cnt[:, None]
    baseline = base_sum / base_cnt
    stim_range = stim_max - stim_min
    stimulus_range = 0.0 if clamp_index is None else float(traj_max - traj_min)
    return stim_means, baseline, stim_range, stimulus_range


def unstimulated_extrema(rr, deadline: float):
    """Nonzero max and min of each species on the unstimulated schedule.

    Zeros are ignored, matching nonzeros() in Find_DrugRes_Sensitize_SLURM1.m.
    A species that is always zero gets max = min = 0.
    """
    n = rr.model.getNumFloatingSpecies()
    nz_max = np.full(n, -np.inf)
    nz_min = np.full(n, np.inf)
    seen = np.zeros(n, dtype=bool)
    t = 0.0
    for chunk in range(1, N_CHUNKS + 1):
        if time.monotonic() > deadline:
            raise TimeoutError("integration budget")
        t = float(rr.oneStep(t, CHUNK_DT))
        sample = _concentrations(rr)
        if not np.all(np.isfinite(sample)):
            raise RuntimeError("non-finite concentration")
        mask = np.abs(sample) > 0.0
        if np.any(mask):
            nz_max[mask] = np.maximum(nz_max[mask], sample[mask])
            nz_min[mask] = np.minimum(nz_min[mask], sample[mask])
            seen |= mask
    nz_max[~seen] = 0.0
    nz_min[~seen] = 0.0
    return nz_max, nz_min


def is_habituation(means: np.ndarray) -> bool:
    """Progressive 1/1.5 drop across the six stimulation-window means.

    means[0] .. means[4] must be at least MEAN_FLOOR (the paper's absolute
    tolerance) so each compared level is resolved. means[5] may be smaller.
    Negative values are not an expression drop.
    """
    if means.shape != (6,):
        return False
    if not np.all(np.isfinite(means)):
        return False
    if np.any(means < 0.0):
        return False
    if np.any(means[:5] < MEAN_FLOOR):
        return False
    for a, b in zip(means[:5], means[1:]):
        if not (b * RATIO <= a * (1.0 + 1e-9)):
            return False
    return True


def is_flip(baseline: float, means: np.ndarray) -> bool:
    """Descriptive copy of the MATLAB drug-resistance counter. Not the verdict."""
    if not np.isfinite(baseline) or baseline <= 0.0:
        return False
    if not np.all(np.isfinite(means)) or np.any(means <= 0.0):
        return False
    status = [0] * 6
    if means[0] > RATIO * baseline:
        status[0] = 1
        for t in range(5):
            if means[t + 1] > RATIO * means[t]:
                status[t + 1] = 1
            elif means[t + 1] <= means[t] / RATIO:
                status[t + 1] = 2
    elif means[0] <= baseline / RATIO:
        status[0] = 2
        for t in range(5):
            if means[t + 1] <= means[t] / RATIO:
                status[t + 1] = 1
            elif means[t + 1] > RATIO * means[t]:
                status[t + 1] = 2
    nonzero = [s for s in status if s]
    return len(nonzero) > 1 and nonzero[0] != nonzero[-1]


def _load(path: Path, abs_tol: float, rel_tol: float):
    import roadrunner

    rr = roadrunner.RoadRunner(str(path))
    _configure(rr, abs_tol, rel_tol)
    return rr


def analyze_model(model_id: str, meta: dict) -> dict:
    """Run the habituation screen on one model. Never raises for model failure."""
    path = SBML_DIR / f"{model_id}.xml"
    started = time.monotonic()
    record = {
        "biomodel_id": model_id,
        "table_s1_index": BIOMODELS.index(model_id) + 1,
        "testable": False,
        "reason": None,
        "n_species": None,
        "species_ids": None,
        "n_pairs": 0,
        "n_habituating": 0,
        "fraction": None,
        "n_flip": 0,
        "examples": [],
        "tolerances": None,
        "seconds": None,
        "file": {k: meta[k] for k in ("download_url", "final_url", "retrieved_at", "byte_size", "sha256")},
    }
    last_error = None
    for abs_tol, rel_tol in ((1e-3, 1e-3), (1e-8, 1e-6)):
        if time.monotonic() - started > HARD_BUDGET_S:
            record["reason"] = "time-budget"
            record["seconds"] = round(time.monotonic() - started, 3)
            return record
        try:
            rr = _load(path, abs_tol, rel_tol)
            ids = list(rr.model.getFloatingSpeciesIds())
            n = len(ids)
            record["n_species"] = n
            record["species_ids"] = ids
            record["tolerances"] = {"absolute": abs_tol, "relative": rel_tol}
            if n < 2:
                record["reason"] = "fewer-than-two-floating-species"
                record["seconds"] = round(time.monotonic() - started, 3)
                return record
            deadline = started + INTEGRATION_BUDGET_S
            nz_max, nz_min = unstimulated_extrema(rr, deadline)
            fd_up = nz_max * CLAMP_SCALE
            fd_dn = nz_min / CLAMP_SCALE
            n_pairs = 0
            n_hab = 0
            n_flip = 0
            n_skipped = 0
            examples = []
            for direction, fd in (("up", fd_up), ("down", fd_dn)):
                for u, level in enumerate(fd):
                    if not np.isfinite(level) or level == 0.0:
                        continue
                    if time.monotonic() > deadline:
                        raise TimeoutError("integration budget")
                    rr.reset()
                    try:
                        stim_means, baseline, _stim_range, stimulus_range = integrate(
                            rr, u, float(level), deadline
                        )
                    except TimeoutError:
                        raise
                    except Exception:
                        # This stimulus direction did not integrate. It is not a
                        # scored pair and not a habituating pair.
                        n_skipped += 1
                        continue
                    if stimulus_range <= 0.0:
                        continue
                    for r in range(n):
                        if r == u:
                            continue
                        n_pairs += 1
                        means = stim_means[:, r]
                        hab = is_habituation(means)
                        flip = is_flip(float(baseline[r]), means)
                        if hab:
                            n_hab += 1
                            if len(examples) < 3:
                                examples.append(
                                    {
                                        "ucs": ids[u],
                                        "response": ids[r],
                                        "direction": direction,
                                        "clamp": float(level),
                                        "stimulation_means": [float(x) for x in means],
                                    }
                                )
                        if flip:
                            n_flip += 1
            record["testable"] = True
            record["reason"] = None
            record["n_pairs"] = n_pairs
            record["n_habituating"] = n_hab
            record["fraction"] = (n_hab / n_pairs) if n_pairs else None
            record["n_flip"] = n_flip
            record["n_skipped_stimuli"] = n_skipped
            record["examples"] = examples
            record["seconds"] = round(time.monotonic() - started, 3)
            if n_pairs == 0:
                record["testable"] = False
                record["reason"] = "no-scored-pairs"
            return record
        except TimeoutError:
            record["reason"] = "time-budget"
            record["seconds"] = round(time.monotonic() - started, 3)
            return record
        except Exception as exc:  # solver, SBML, or numerical failure; retry once
            last_error = f"{type(exc).__name__}: {exc}"
            continue
    record["reason"] = "integration-failed"
    record["error"] = last_error
    record["seconds"] = round(time.monotonic() - started, 3)
    return record


def decide(models: list[dict]) -> dict:
    """Apply the pre-registered verdict and confidence rules."""
    testable = [m for m in models if m.get("testable")]
    n = len(testable)
    if n < MIN_TESTABLE:
        reason = "underpowered" if n else "data-unavailable"
        return {
            "verdict": "inconclusive",
            "reason": reason,
            "confidence": 0.60,
            "n_testable": n,
            "n_with_habituation": sum(1 for m in testable if m["n_habituating"] >= 1),
            "fractions_inside_band": None,
        }
    has_one = [m["n_habituating"] >= 1 for m in testable]
    inside = []
    for m in testable:
        fraction = m["fraction"]
        inside.append(fraction is not None and 0.01 <= fraction <= 0.50)
    clause_a = all(has_one)
    clause_b = all(inside)
    if clause_a and clause_b:
        verdict = "supports"
    elif clause_a != clause_b:
        verdict = "mixed"
    else:
        verdict = "refutes"
    fragile = False
    for m in testable:
        h = m["n_habituating"]
        p = m["n_pairs"]
        # Reclassifying one pair flips "at least one" or the 1–50% band.
        if h <= 1:
            fragile = True
        if p and (abs(h / p - 0.01) * p < 1.0 or abs(h / p - 0.50) * p < 1.0):
            fragile = True
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
        "n_testable": n,
        "n_with_habituation": sum(1 for flag in has_one if flag),
        "clause_every_model_has_one": clause_a,
        "clause_every_fraction_in_band": clause_b,
        "fractions_inside_band": sum(1 for flag in inside if flag),
    }


def measured_block(models: list[dict], decision: dict) -> dict:
    testable = [m for m in models if m.get("testable")]
    fractions = [m["fraction"] for m in testable if m["fraction"] is not None]
    n_scored_pairs = sum(m["n_pairs"] for m in testable)
    n_habituating_pairs = sum(m["n_habituating"] for m in testable)
    n_flip_pairs = sum(m["n_flip"] for m in testable)
    n_with_zero = sum(1 for m in testable if m["n_habituating"] == 0)
    n_flip_models = sum(1 for m in testable if m["n_flip"] >= 1)
    per_model = []
    for m in models:
        per_model.append(
            {
                "biomodel_id": m["biomodel_id"],
                "table_s1_index": m["table_s1_index"],
                "testable": m["testable"],
                "reason": m["reason"],
                "n_species": m["n_species"],
                "n_pairs": m["n_pairs"],
                "n_habituating": m["n_habituating"],
                "fraction": m["fraction"],
                "n_flip": m["n_flip"],
                "tolerances": m["tolerances"],
            }
        )
    value = decision["n_with_habituation"]
    return {
        "value": value,
        "unit": "testable models with at least one habituating UCS-R pair",
        "n": decision["n_testable"],
        "uncertainty": "deterministic given libroadrunner, the SBML files, and the tolerances recorded per model",
        "extra": {
            "n_models_attempted": len(models),
            "n_testable": decision["n_testable"],
            "n_with_at_least_one": decision["n_with_habituation"],
            "n_fraction_inside_0.01_0.50": decision.get("fractions_inside_band"),
            "clause_every_model_has_one": decision.get("clause_every_model_has_one"),
            "clause_every_fraction_in_band": decision.get("clause_every_fraction_in_band"),
            "min_fraction": min(fractions) if fractions else None,
            "max_fraction": max(fractions) if fractions else None,
            "n_scored_pairs": n_scored_pairs,
            "n_habituating_pairs": n_habituating_pairs,
            "n_flip_pairs": n_flip_pairs,
            "n_testable_with_zero": n_with_zero,
            "n_testable_with_flip": n_flip_models,
            "verdict": decision["verdict"],
            "reason": decision["reason"],
            "confidence": decision["confidence"],
            "per_model": per_model,
        },
    }


def write_report(models: list[dict]) -> dict:
    decision = decide(models)
    payload = {
        "claim_id": "levin-2022-grn-learning-14",
        "decision": decision,
        "measured": measured_block(models, decision),
        "examples": [
            {"biomodel_id": m["biomodel_id"], "examples": m["examples"]}
            for m in models
            if m.get("examples")
        ],
        "files": [m["file"] for m in models if m.get("file")],
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2) + "\n"
    (DERIVED / "measured.json").write_text(text)
    return payload


def self_test() -> None:
    """Classifier, verdict rule, and a toy clamp. No BioModels access."""
    assert is_habituation(np.array([8.0, 5.0, 3.0, 2.0, 1.2, 0.7]))
    assert not is_habituation(np.array([8.0, 5.0, 3.0, 2.5, 2.0, 1.5]))
    assert not is_habituation(np.array([1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11]))
    assert not is_habituation(np.array([8.0, 5.0, 3.0, 2.0, 1.2, -0.1]))
    # Exactly 1/1.5 five times from a resolved start.
    means = [1.0]
    for _ in range(5):
        means.append(means[-1] / 1.5)
    assert is_habituation(np.array(means))
    # One step that fails to drop.
    means[3] = means[2] * 0.9
    assert not is_habituation(np.array(means))

    def fake(h, p, testable=True):
        return {
            "testable": testable,
            "n_habituating": h,
            "n_pairs": p,
            "fraction": (h / p) if p else None,
        }

    # 10 models, one pair in 50 = 2%, all inside the band.
    good = [fake(1, 50) for _ in range(10)]
    assert decide(good)["verdict"] == "supports"
    # Single pair out of 50 is fragile (h <= 1), so confidence is 0.45.
    assert decide(good)["confidence"] == 0.45
    # 20 models, 10 of 100 pairs: not fragile, confidence 0.70.
    solid = [fake(10, 100) for _ in range(20)]
    assert decide(solid)["verdict"] == "supports"
    assert decide(solid)["confidence"] == 0.70
    # One model with zero pairs that habituate, fractions otherwise inside: mixed
    # only if the zero-model's fraction is inside the band. 0/50 = 0 is outside,
    # so both clauses fail: refutes.
    both = [fake(10, 100) for _ in range(9)] + [fake(0, 50)]
    assert decide(both)["verdict"] == "refutes"
    # Every model has one, but one fraction is 60/100 = 0.60: mixed.
    mixed = [fake(10, 100) for _ in range(9)] + [fake(60, 100)]
    assert decide(mixed)["verdict"] == "mixed"
    assert decide([fake(1, 50) for _ in range(9)])["verdict"] == "inconclusive"
    assert decide([])["reason"] == "data-unavailable"

    import roadrunner

    sbml = """<?xml version="1.0" encoding="UTF-8"?>
<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core" level="3" version="1">
  <model id="toy">
    <listOfCompartments><compartment id="c" size="1" constant="true"/></listOfCompartments>
    <listOfSpecies>
      <species id="A" compartment="c" initialConcentration="1" boundaryCondition="false" constant="false" hasOnlySubstanceUnits="false"/>
      <species id="B" compartment="c" initialConcentration="0.1" boundaryCondition="false" constant="false" hasOnlySubstanceUnits="false"/>
    </listOfSpecies>
    <listOfParameters>
      <parameter id="k" value="0.2" constant="true"/>
    </listOfParameters>
    <listOfReactions>
      <reaction id="decayA" reversible="false">
        <listOfReactants><speciesReference species="A" stoichiometry="1"/></listOfReactants>
        <kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML">
          <apply><times/><cn>0.05</cn><ci>A</ci></apply></math></kineticLaw>
      </reaction>
      <reaction id="makeB" reversible="false">
        <listOfProducts><speciesReference species="B" stoichiometry="1"/></listOfProducts>
        <listOfModifiers><modifierSpeciesReference species="A"/></listOfModifiers>
        <kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML">
          <apply><times/><cn>0.4</cn><ci>A</ci></apply></math></kineticLaw>
      </reaction>
      <reaction id="decayB" reversible="false">
        <listOfReactants><speciesReference species="B" stoichiometry="1"/></listOfReactants>
        <kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML">
          <apply><times/><cn>0.2</cn><ci>B</ci></apply></math></kineticLaw>
      </reaction>
    </listOfReactions>
  </model>
</sbml>
"""
    toy = CACHE / "toy.xml"
    toy.parent.mkdir(parents=True, exist_ok=True)
    toy.write_text(sbml)
    rr = roadrunner.RoadRunner(str(toy))
    _configure(rr, 1e-6, 1e-6)
    deadline = time.monotonic() + 60
    # A short clamp check, not the full 10100 chunks: 20 steps free, then 20 clamped.
    t = 0.0
    for _ in range(20):
        t = float(rr.oneStep(t, 0.1))
    free_b = float(_concentrations(rr)[1])
    for _ in range(20):
        _set_one(rr, 0, 30.0)
        t = float(rr.oneStep(t, 0.1))
        _set_one(rr, 0, 30.0)
    clamped_b = float(_concentrations(rr)[1])
    if not (clamped_b > free_b * 2):
        raise AssertionError(f"clamp did not raise B: free {free_b}, clamped {clamped_b}")
    # Window bookkeeping: six windows, chunk counts 500..1000, total 10100.
    counts = [b - a + 1 for a, b in STIM_WINDOWS]
    if counts != [500, 600, 700, 800, 900, 1000]:
        raise AssertionError(counts)
    if STIM_WINDOWS[-1][1] + 1100 != N_CHUNKS:
        raise AssertionError("final relaxation does not end at chunk 10100")
    print("self-test ok")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--only", nargs="*", default=None, help="subset of BIOMD ids, for debugging a hang")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    ids = args.only if args.only else list(BIOMODELS)
    unknown = [i for i in ids if i not in BIOMODELS]
    if unknown:
        raise SystemExit(f"not in Table S1: {unknown}")
    # A partial --only run must not be written as the claim measurement.
    if args.only:
        print("debug subset; not writing derived/measured.json")
    models = []
    for model_id in ids:
        print(f"fetch {model_id}", flush=True)
        try:
            meta = fetch_sbml(model_id)
        except Exception as exc:
            models.append(
                {
                    "biomodel_id": model_id,
                    "table_s1_index": BIOMODELS.index(model_id) + 1,
                    "testable": False,
                    "reason": "download-failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "n_species": None,
                    "n_pairs": 0,
                    "n_habituating": 0,
                    "fraction": None,
                    "n_flip": 0,
                    "examples": [],
                    "tolerances": None,
                    "seconds": None,
                    "file": None,
                }
            )
            print(f"  download failed: {exc}", flush=True)
            continue
        print(f"  {meta['byte_size']} bytes, integrating", flush=True)
        record = analyze_model(model_id, meta)
        models.append(record)
        print(
            f"  testable={record['testable']} species={record['n_species']} "
            f"pairs={record['n_pairs']} hab={record['n_habituating']} "
            f"fraction={record['fraction']} reason={record['reason']} "
            f"t={record['seconds']}",
            flush=True,
        )
    if args.only:
        return
    payload = write_report(models)
    decision = payload["decision"]
    print(
        json.dumps(
            {"verdict": decision["verdict"], "reason": decision["reason"], "confidence": decision["confidence"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
