#!/usr/bin/env python3
"""Pre-registered ODE protocol for three Levin pathway-learning claims.

The numeric thresholds live in each directory's result.json under
"preregistration". This file implements that protocol. It does not edit
pass_criterion, fail_criterion, hypothesis, test_contract, interpretation,
or preregistration.

Dependency (not in the stdlib): pip install libroadrunner numpy requests
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

try:
    import roadrunner
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "libroadrunner is required: python3 -m pip install libroadrunner"
    ) from exc

UA = "delphi-claim-test/2026-11-01"
BIOMD_URLS = (
    "https://www.ebi.ac.uk/biomodels/model/files/{mid}?format=xml",
    "https://www.ebi.ac.uk/biomodels/model/download/{mid}",
)
META_URL = "https://www.ebi.ac.uk/biomodels/{mid}?format=json"
TABLE_PAGES = (
    "https://www.mdpi.com/1422-0067/24/1/285/s1",
    "https://www.mdpi.com/1422-0067/24/1/285",
    "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9820177/fullTextXML",
)
CACHE_DIR = Path("/tmp/delphi-levin-grn-cache")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def http_get(url: str, role: str, log: list, timeout: int = 45, max_bytes: int = 5_000_000):
    rec = {
        "download_url": url,
        "retrieved_at": now_utc(),
        "byte_size": 0,
        "sha256": None,
        "http_status": None,
        "role": role,
        "final_url": None,
        "error": None,
    }
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
        content = resp.content
        rec["http_status"] = resp.status_code
        rec["final_url"] = resp.url
        rec["byte_size"] = len(content)
        rec["sha256"] = sha256_bytes(content)
        log.append(rec)
        if resp.status_code != 200 or len(content) > max_bytes or len(content) == 0:
            return None
        return content
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
        log.append(rec)
        return None


def biomod_ids_in(blob: bytes) -> list[str]:
    found = re.findall(rb"BIOMD\d{10}", blob, flags=re.IGNORECASE)
    out = []
    for raw in found:
        mid = raw.decode("ascii").upper()
        if mid not in out:
            out.append(mid)
    return out


def discover_table_ids(cfg: dict, log: list) -> tuple[list[str], list[dict]]:
    """Pull BioModels ids from the paper's public supplementary pages.

    Only the id strings are kept. Numeric result columns are never parsed.
    """
    ids: list[str] = []
    used = []
    pages = list(TABLE_PAGES)
    seen_urls = set(pages)
    extra = []
    for url in pages:
        blob = http_get(url, "table-s1-source", log)
        if not blob:
            continue
        for mid in biomod_ids_in(blob):
            if mid not in ids:
                ids.append(mid)
        if b"BIOMD" in blob.upper():
            used.append({"download_url": url, "byte_size": len(blob), "sha256": sha256_bytes(blob)})
        # Follow a few supplementary links on HTML pages. Do not parse numbers.
        if url.endswith("/s1") or "mdpi.com" in url:
            hrefs = re.findall(rb'href="([^"]+)"', blob)
            for href in hrefs[:40]:
                try:
                    link = href.decode("utf-8", "ignore")
                except Exception:
                    continue
                if not any(k in link.lower() for k in ("supplement", "/s1", "ijms-24-00285", ".zip", ".xlsx", ".pdf", ".csv")):
                    continue
                if link.startswith("//"):
                    link = "https:" + link
                elif link.startswith("/"):
                    link = "https://www.mdpi.com" + link
                if not link.startswith("http") or link in seen_urls:
                    continue
                seen_urls.add(link)
                extra.append(link)
    for url in extra[:6]:
        blob = http_get(url, "table-s1-attachment", log, max_bytes=8_000_000)
        if not blob:
            continue
        before = len(ids)
        for mid in biomod_ids_in(blob):
            if mid not in ids:
                ids.append(mid)
        if len(ids) > before:
            used.append({"download_url": url, "byte_size": len(blob), "sha256": sha256_bytes(blob)})
    return ids, used


def sequential_ids(start: int, count: int) -> list[str]:
    return [f"BIOMD{n:010d}" for n in range(start, start + count)]


def license_from_meta(blob: bytes) -> str | None:
    try:
        meta = json.loads(blob.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    for key in ("license", "licence", "rights", "copyright"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:240]
        if isinstance(val, dict):
            for sub in ("name", "url", "id"):
                if isinstance(val.get(sub), str) and val[sub].strip():
                    return val[sub].strip()[:240]
    return None


def tune(rr) -> None:
    rr.integrator.absolute_tolerance = 1e-8
    rr.integrator.relative_tolerance = 1e-6
    rr.integrator.maximum_num_steps = 20000


def load_model(path: Path):
    rr = roadrunner.RoadRunner(str(path))
    tune(rr)
    floating = list(rr.model.getFloatingSpeciesIds())
    boundary = list(rr.model.getBoundarySpeciesIds())
    params = tuple((p, float(rr[p])) for p in rr.model.getGlobalParameterIds())
    reactions = tuple(rr.model.getReactionIds())
    return rr, floating, boundary, params, reactions


def structure_ok(rr, params, reactions) -> bool:
    now_p = tuple((p, float(rr[p])) for p in rr.model.getGlobalParameterIds())
    now_r = tuple(rr.model.getReactionIds())
    return now_p == params and now_r == reactions


def structure_ids_ok(rr, params, reactions) -> bool:
    """True when the test has not added or removed parameters or reactions.

    Parameter values are allowed to move when the deposited model itself has
    events or rules that assign them. That is not an edit of edge strengths.
    """
    now_ids = tuple(rr.model.getGlobalParameterIds())
    now_r = tuple(rr.model.getReactionIds())
    return now_ids == tuple(k for k, _ in params) and now_r == reactions


def selections(ids: list[str]) -> list[str]:
    return ["time"] + [f"[{s}]" for s in ids]


def finite_table(data) -> bool:
    arr = np.asarray(data, dtype=float)
    return arr.size > 0 and np.isfinite(arr).all()


def col_mean(data, col: int) -> float | None:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 2 or col >= arr.shape[1]:
        return None
    sl = arr[1:, col]
    if not np.isfinite(sl).all():
        return None
    return float(np.mean(sl))


def classify(mean_pre: float, mean_stim: float, cfg: dict) -> str:
    near = float(cfg["near_zero"])
    appear = float(cfg["appear_threshold"])
    up = float(cfg["regulation_up_ratio"])
    down = float(cfg["regulation_down_ratio"])
    if abs(mean_pre) < near:
        if mean_stim >= appear:
            return "up"
        if mean_stim <= -appear:
            return "down"
        return "none"
    ratio = mean_stim / mean_pre
    if ratio >= up:
        return "up"
    if ratio <= down:
        return "down"
    return "none"


def clamp_level(direction: str, factor: float, late: float, peak_abs: float, bmin: float, cfg: dict) -> float:
    floor = float(cfg["floor"])
    amp = max(abs(late), peak_abs, floor)
    if bmin >= -float(cfg["near_zero"]):
        return factor * amp if direction == "up" else amp / factor
    if direction == "up":
        return late + (factor - 1.0) * amp
    return late - (factor - 1.0) * amp


def unclamp(rr, sids: list[str], original_boundary: set[str]) -> None:
    current = set(rr.model.getBoundarySpeciesIds())
    extra = [s for s in sids if s in current and s not in original_boundary]
    if not extra:
        return
    for sid in extra:
        rr.setBoundary(sid, False, False)
    rr.setBoundary(extra[-1], False, True)
    tune(rr)


def restore_state(rr, ids, state: dict, t: float, original_boundary: set[str]) -> None:
    current = set(rr.model.getBoundarySpeciesIds())
    extra = [s for s in current if s not in original_boundary]
    unclamp(rr, extra, original_boundary)
    for sid, val in state.items():
        rr[f"[{sid}]"] = float(val)
    rr.model.setTime(float(t))


def capture(rr, ids) -> dict:
    return {sid: float(rr[f"[{sid}]"]) for sid in ids}


def simulate_segment(rr, ids, t0: float, dur: float, clamps: dict, n_out: int = 21):
    turned = []
    for sid in clamps:
        rr.setBoundary(sid, True, False)
        turned.append(sid)
    if turned:
        rr.setBoundary(turned[-1], True, True)
        tune(rr)
        for sid, val in clamps.items():
            rr[f"[{sid}]"] = float(val)
    rr.timeCourseSelections = selections(ids)
    data = rr.simulate(float(t0), float(t0 + dur), int(n_out))
    if not finite_table(data):
        raise RuntimeError("non-finite trajectory")
    return data


def index_of(ids, sid) -> int:
    return ids.index(sid) + 1


def evenly(items: list, k: int) -> list:
    n = len(items)
    if k <= 0 or n == 0:
        return []
    if n <= k:
        return list(items)
    if k == 1:
        return [items[0]]
    chosen = []
    seen = set()
    for i in range(k):
        idx = int(round(i * (n - 1) / (k - 1)))
        if idx not in seen:
            seen.add(idx)
            chosen.append(items[idx])
    return chosen


def probe_horizon(rr, ids, horizons, original_boundary, params, reactions):
    """Longest finite horizon that still has the deposited parameter values.

    Some models fire events that rewrite rate constants late in a run. A horizon
    that has already done that is not a test of the deposited network.
    """
    drifted = False
    for H in horizons:
        try:
            rr.resetToOrigin()
            tune(rr)
            unclamp(rr, list(set(rr.model.getBoundarySpeciesIds()) - original_boundary), original_boundary)
            rr.timeCourseSelections = selections(ids)
            data = rr.simulate(0, float(H), 31)
            if not finite_table(data):
                continue
            if not structure_ok(rr, params, reactions):
                drifted = True
                continue
            return float(H), np.asarray(data, dtype=float), drifted
        except Exception:
            continue
    return None, None, drifted


def baseline_stats(data, ids, cfg):
    # columns: time + species
    n = data.shape[0]
    start = max(1, int(round(n * (1.0 - float(cfg["late_window_fraction"])))))
    late = {}
    peak = {}
    bmin = {}
    for i, sid in enumerate(ids):
        col = data[:, i + 1]
        late[sid] = float(np.mean(col[start:]))
        peak[sid] = float(np.max(np.abs(col)))
        bmin[sid] = float(np.min(col))
    state = {sid: float(data[-1, i + 1]) for i, sid in enumerate(ids)}
    t_end = float(data[-1, 0])
    return late, peak, bmin, state, t_end


def phenotype_flags(means, cfg):
    ratio = float(cfg["phenotype_ratio"])
    near = float(cfg["near_zero"])
    if means is None or len(means) < 2:
        return False, False
    hab = True
    sens = True
    for a, b in zip(means, means[1:]):
        if a <= near or b <= near:
            return False, False
        if not (b <= a / ratio):
            hab = False
        if not (b >= a * ratio):
            sens = False
    return hab, sens


class Budget:
    def __init__(self, seconds: float):
        self.t0 = time.monotonic()
        self.limit = seconds

    def ok(self) -> bool:
        return (time.monotonic() - self.t0) < self.limit

    def used(self) -> float:
        return time.monotonic() - self.t0


def analyze_loaded(rr, ids, boundary, params, reactions, cfg, budget: Budget):
    original_boundary = set(boundary)
    horizons = [float(h) for h in cfg["horizons"]]
    H, data, drifted = probe_horizon(rr, ids, horizons, original_boundary, params, reactions)
    if H is None:
        reason = "parameters-drift-on-baseline" if drifted else "baseline-failed"
        return {"baseline_ok": False, "skip_reason": reason}
    late, peak, bmin, end_state, t_end = baseline_stats(data, ids, cfg)
    if not structure_ok(rr, params, reactions):
        return {"baseline_ok": False, "skip_reason": "structure-changed-during-baseline"}
    Ts = H / float(cfg["stimulus_duration_divisor"])
    factors = [float(f) for f in cfg["stimulus_factors"]]
    normal = float(cfg["normal_training_factor"])
    pairs = [(u, r) for u in ids for r in ids if u != r]
    pairs.sort()
    tested_pairs = evenly(pairs, int(cfg["max_pairs"]))
    directions = ("up", "down")

    memory = {str(int(f)) if float(f).is_integer() else str(f): 0 for f in factors}
    memory_examples = []
    memory_errors = 0
    memory_attempts = 0
    memory_complete = True

    def key_of(factor: float) -> str:
        return str(int(factor)) if float(factor).is_integer() else str(factor)

    for ucs, resp in tested_pairs:
        for direction in directions:
            for factor in factors:
                if not budget.ok():
                    memory_complete = False
                    break
                memory_attempts += 1
                try:
                    restore_state(rr, ids, end_state, t_end, original_boundary)
                    level = clamp_level(direction, factor, late[ucs], peak[ucs], bmin[ucs], cfg)
                    stim = simulate_segment(rr, ids, t_end, Ts, {ucs: level})
                    stim_mean = col_mean(stim, index_of(ids, resp))
                    kind = classify(late[resp], stim_mean, cfg) if stim_mean is not None else "none"
                    if kind == "none":
                        unclamp(rr, [ucs], original_boundary)
                        continue
                    unclamp(rr, [ucs], original_boundary)
                    t1 = float(np.asarray(stim)[-1, 0])
                    delay = simulate_segment(rr, ids, t1, Ts, {})
                    delay_mean = col_mean(delay, index_of(ids, resp))
                    kind2 = classify(late[resp], delay_mean, cfg) if delay_mean is not None else "none"
                    if kind2 == kind:
                        memory[key_of(factor)] += 1
                        if len(memory_examples) < 12:
                            memory_examples.append({
                                "ucs": ucs, "response": resp, "direction": direction,
                                "factor": factor, "during": kind,
                            })
                    if not structure_ids_ok(rr, params, reactions):
                        raise RuntimeError("parameter or reaction identifiers changed")
                except Exception:
                    memory_errors += 1
            if not memory_complete:
                break
        if not memory_complete:
            break
    if memory_attempts and memory_errors > 0.5 * memory_attempts:
        memory_complete = False

    # Habituation / sensitization at the normal training factor.
    # The phenotype screen is independent of whether the memory screen finished.
    hab_hits = []
    sens_hits = []
    phenotype_errors = 0
    phenotype_attempts = 0
    phenotype_complete = True
    multipliers = [float(m) for m in cfg["pulse_length_multipliers"]]

    def pulse_train(ucs, resp, direction, sham: bool):
        restore_state(rr, ids, end_state, t_end, original_boundary)
        t = t_end
        means = []
        level = clamp_level(direction, normal, late[ucs], peak[ucs], bmin[ucs], cfg)
        rcol = index_of(ids, resp)
        for mult in multipliers:
            dur = Ts * mult
            clamps = {} if sham else {ucs: level}
            stim = simulate_segment(rr, ids, t, dur, clamps)
            m = col_mean(stim, rcol)
            if m is None:
                raise RuntimeError("pulse mean undefined")
            means.append(m)
            t = float(np.asarray(stim)[-1, 0])
            if not sham:
                unclamp(rr, [ucs], original_boundary)
            relax = simulate_segment(rr, ids, t, dur, {})
            t = float(np.asarray(relax)[-1, 0])
        return means, capture(rr, ids), t

    for ucs, resp in tested_pairs:
        for direction in directions:
            if not budget.ok():
                phenotype_complete = False
                break
            phenotype_attempts += 1
            try:
                stim_means, stim_end, stim_t = pulse_train(ucs, resp, direction, sham=False)
                sham_means, _, _ = pulse_train(ucs, resp, direction, sham=True)
                hab, _sens_ignored = phenotype_flags(stim_means, cfg)
                sham_hab, _ = phenotype_flags(sham_means, cfg)
                _hab_ignored, sens = phenotype_flags(stim_means, cfg)
                _, sham_sens = phenotype_flags(sham_means, cfg)
                if hab and not sham_hab:
                    hab_hits.append({
                        "ucs": ucs, "response": resp, "direction": direction,
                        "end_state": stim_end, "end_time": stim_t,
                    })
                if sens and not sham_sens:
                    sens_hits.append({
                        "ucs": ucs, "response": resp, "direction": direction,
                        "end_state": stim_end, "end_time": stim_t,
                    })
                if not structure_ids_ok(rr, params, reactions):
                    raise RuntimeError("parameter or reaction identifiers changed")
            except Exception:
                phenotype_errors += 1
        if not phenotype_complete:
            break
    if phenotype_attempts and phenotype_errors > 0.5 * phenotype_attempts:
        phenotype_complete = False

    def two_pulse_means(start_state, start_t, ucs, resp, direction, pre_clamps, pre_mode):
        """pre_mode 'control': relax 2*Ts. pre_mode 'break': clamp pre_clamps for Ts then relax Ts."""
        restore_state(rr, ids, start_state, start_t, original_boundary)
        t = start_t
        rcol = index_of(ids, resp)
        level_u = clamp_level(direction, normal, late[ucs], peak[ucs], bmin[ucs], cfg)
        if pre_mode == "control":
            relax = simulate_segment(rr, ids, t, 2 * Ts, {})
            t = float(np.asarray(relax)[-1, 0])
        else:
            stim = simulate_segment(rr, ids, t, Ts, pre_clamps)
            t = float(np.asarray(stim)[-1, 0])
            unclamp(rr, list(pre_clamps), original_boundary)
            relax = simulate_segment(rr, ids, t, Ts, {})
            t = float(np.asarray(relax)[-1, 0])
        means = []
        for _ in range(2):
            pulse = simulate_segment(rr, ids, t, Ts, {ucs: level_u})
            m = col_mean(pulse, rcol)
            if m is None:
                raise RuntimeError("break-test mean undefined")
            means.append(m)
            t = float(np.asarray(pulse)[-1, 0])
            unclamp(rr, [ucs], original_boundary)
            gap = simulate_segment(rr, ids, t, Ts, {})
            t = float(np.asarray(gap)[-1, 0])
        return means

    def persists(kind: str, m1: float, m2: float) -> bool:
        near = float(cfg["near_zero"])
        ratio = float(cfg["phenotype_ratio"])
        if m1 <= near or m2 <= near:
            return False
        if kind == "hab":
            return m2 <= m1 / ratio
        return m2 >= m1 * ratio

    breaking = {
        "hab_stable_tested": 0,
        "hab_broken": 0,
        "sens_stable_tested": 0,
        "sens_broken": 0,
        "complete": phenotype_complete,
        "examples": [],
    }

    def screen_breaks(hits, kind: str):
        chosen = evenly(hits, int(cfg["max_break_pairs"]))
        stable = 0
        broken = 0
        for hit in chosen:
            if not budget.ok():
                breaking["complete"] = False
                return stable, broken
            others = [s for s in ids if s not in (hit["ucs"], hit["response"])]
            nodes = evenly(sorted(others), int(cfg["max_break_nodes"]))
            # Control first. If the phenotype does not persist, the pair is not stable.
            try:
                ctrl = two_pulse_means(
                    hit["end_state"], hit["end_time"], hit["ucs"], hit["response"],
                    hit["direction"], {}, "control",
                )
            except Exception:
                continue
            if not persists(kind, ctrl[0], ctrl[1]):
                continue
            stable += 1
            pair_broken = False
            for node in nodes:
                for ndir in directions:
                    if not budget.ok():
                        breaking["complete"] = False
                        return stable, broken
                    try:
                        level = clamp_level(ndir, normal, late[node], peak[node], bmin[node], cfg)
                        br = two_pulse_means(
                            hit["end_state"], hit["end_time"], hit["ucs"], hit["response"],
                            hit["direction"], {node: level}, "break",
                        )
                        if not persists(kind, br[0], br[1]):
                            pair_broken = True
                            if len(breaking["examples"]) < 12:
                                breaking["examples"].append({
                                    "kind": kind, "ucs": hit["ucs"], "response": hit["response"],
                                    "ucs_direction": hit["direction"], "breaker": node,
                                    "breaker_direction": ndir,
                                })
                            break
                    except Exception:
                        continue
                if pair_broken:
                    break
            if pair_broken:
                broken += 1
        return stable, broken

    if phenotype_complete and budget.ok():
        hs, hb = screen_breaks(hab_hits, "hab")
        breaking["hab_stable_tested"] = hs
        breaking["hab_broken"] = hb
        if breaking["complete"]:
            ss, sb = screen_breaks(sens_hits, "sens")
            breaking["sens_stable_tested"] = ss
            breaking["sens_broken"] = sb
    else:
        breaking["complete"] = False

    # Associative / Pavlovian screen at the normal training factor.
    assoc_hits = 0
    assoc_examples = []
    assoc_attempts = 0
    assoc_errors = 0
    assoc_complete = True
    triples = []
    for resp in ids:
        for ucs in ids:
            if ucs == resp:
                continue
            for ns in ids:
                if ns in (resp, ucs):
                    continue
                for ud in directions:
                    for nd in directions:
                        triples.append((ucs, ns, resp, ud, nd))
    triples = evenly(triples, int(cfg["max_assoc"]))
    for ucs, ns, resp, ud, nd in triples:
        if not budget.ok():
            assoc_complete = False
            break
        assoc_attempts += 1
        try:
            rcol = index_of(ids, resp)
            # Pretest UCS
            restore_state(rr, ids, end_state, t_end, original_boundary)
            ustim = simulate_segment(
                rr, ids, t_end, Ts,
                {ucs: clamp_level(ud, normal, late[ucs], peak[ucs], bmin[ucs], cfg)},
            )
            ucs_kind = classify(late[resp], col_mean(ustim, rcol), cfg)
            unclamp(rr, [ucs], original_boundary)
            if ucs_kind == "none":
                continue
            # Pretest NS from the same baseline
            restore_state(rr, ids, end_state, t_end, original_boundary)
            nstim = simulate_segment(
                rr, ids, t_end, Ts,
                {ns: clamp_level(nd, normal, late[ns], peak[ns], bmin[ns], cfg)},
            )
            if classify(late[resp], col_mean(nstim, rcol), cfg) != "none":
                unclamp(rr, [ns], original_boundary)
                continue
            unclamp(rr, [ns], original_boundary)
            # Sham: wait the training interval and the post-training relax, then NS.
            # Regulation is versus the immediately preceding segment, as in section 4.3,
            # so a UCS level that simply stays high is not credited to the neutral node.
            restore_state(rr, ids, end_state, t_end, original_boundary)
            waited = simulate_segment(rr, ids, t_end, 2 * Ts, {})
            t_sh = float(np.asarray(waited)[-1, 0])
            pre_sham = col_mean(waited, rcol)
            sham_ns = simulate_segment(
                rr, ids, t_sh, Ts,
                {ns: clamp_level(nd, normal, late[ns], peak[ns], bmin[ns], cfg)},
            )
            if pre_sham is None or classify(pre_sham, col_mean(sham_ns, rcol), cfg) != "none":
                unclamp(rr, [ns], original_boundary)
                continue
            unclamp(rr, [ns], original_boundary)
            # Paired training, relax, NS test against the post-training relaxation.
            restore_state(rr, ids, end_state, t_end, original_boundary)
            trained = simulate_segment(rr, ids, t_end, Ts, {
                ucs: clamp_level(ud, normal, late[ucs], peak[ucs], bmin[ucs], cfg),
                ns: clamp_level(nd, normal, late[ns], peak[ns], bmin[ns], cfg),
            })
            t_tr = float(np.asarray(trained)[-1, 0])
            unclamp(rr, [ucs, ns], original_boundary)
            relaxed = simulate_segment(rr, ids, t_tr, Ts, {})
            t_re = float(np.asarray(relaxed)[-1, 0])
            pre_test = col_mean(relaxed, rcol)
            tested = simulate_segment(
                rr, ids, t_re, Ts,
                {ns: clamp_level(nd, normal, late[ns], peak[ns], bmin[ns], cfg)},
            )
            if pre_test is not None and classify(pre_test, col_mean(tested, rcol), cfg) != "none":
                assoc_hits += 1
                if len(assoc_examples) < 8:
                    assoc_examples.append({
                        "ucs": ucs, "ns": ns, "response": resp,
                        "ucs_direction": ud, "ns_direction": nd,
                        "ucs_effect": ucs_kind,
                    })
            unclamp(rr, [ns], original_boundary)
            if not structure_ids_ok(rr, params, reactions):
                raise RuntimeError("parameter or reaction identifiers changed")
        except Exception:
            assoc_errors += 1
    if assoc_attempts and assoc_errors > 0.5 * assoc_attempts:
        assoc_complete = False

    # Drop bulky end states from the returned hits.
    def slim(hits):
        return [{"ucs": h["ucs"], "response": h["response"], "direction": h["direction"]} for h in hits[:8]]

    return {
        "baseline_ok": True,
        "n_floating": len(ids),
        "horizon": H,
        "stimulus_duration": Ts,
        "n_pairs_available": len(pairs),
        "n_pairs_tested": len(tested_pairs),
        "n_assoc_tested": len(triples) if assoc_complete or assoc_attempts else len(triples),
        "memory": memory,
        "memory_examples": memory_examples,
        "memory_screen_complete": memory_complete,
        "memory_errors": memory_errors,
        "memory_attempts": memory_attempts,
        "habituation_pairs": len(hab_hits) if phenotype_complete else None,
        "sensitization_pairs": len(sens_hits) if phenotype_complete else None,
        "habituation_examples": slim(hab_hits) if phenotype_complete else [],
        "sensitization_examples": slim(sens_hits) if phenotype_complete else [],
        "phenotype_screen_complete": phenotype_complete,
        "phenotype_errors": phenotype_errors,
        "phenotype_attempts": phenotype_attempts,
        "breaking": breaking,
        "associative_hits": assoc_hits if assoc_complete else None,
        "associative_examples": assoc_examples if assoc_complete else [],
        "associative_screen_complete": assoc_complete,
        "associative_errors": assoc_errors,
        "structure_unchanged": structure_ids_ok(rr, params, reactions),
        "parameter_values_match_deposited": structure_ok(rr, params, reactions),
        "wall_seconds": round(budget.used(), 3),
    }


def analyze_sbml_file(path: Path, cfg: dict) -> dict:
    proto_sha = sha256_bytes(Path(__file__).read_bytes())
    sbml_sha = sha256_bytes(path.read_bytes())
    cfg_blob = json.dumps(cfg, sort_keys=True).encode()
    cache_key = sha256_bytes(proto_sha.encode() + sbml_sha.encode() + cfg_blob)[:24]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        cached["cache"] = "hit"
        return cached
    rr, floating, boundary, params, reactions = load_model(path)
    n = len(floating)
    if n < int(cfg["species_min"]) or n > int(cfg["species_max"]):
        out = {"baseline_ok": False, "skip_reason": "species-count", "n_floating": n}
    else:
        budget = Budget(float(cfg["model_wall_seconds"]))
        try:
            out = analyze_loaded(rr, floating, boundary, params, reactions, cfg, budget)
        except Exception as exc:
            out = {
                "baseline_ok": False,
                "skip_reason": "exception",
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }
    out["cache"] = "miss"
    cache_path.write_text(json.dumps(out))
    return out


def _is_sbml(blob: bytes) -> bool:
    return b"<sbml" in blob[:8000].lower()


def download_sbml(mid: str, dest: Path, log: list):
    """Fetch the main SBML file for a curated BioModels id.

    The files?format=xml URL is a manifest, and the bare download URL is a zip.
    The SBML member named in the manifest is fetched with the filename query.
    A zip member is used only if that query does not return SBML.
    """
    import io
    import zipfile

    dest.parent.mkdir(parents=True, exist_ok=True)
    manifest_url = BIOMD_URLS[0].format(mid=mid)
    manifest = http_get(manifest_url, f"manifest:{mid}", log)
    if manifest and _is_sbml(manifest):
        dest.write_bytes(manifest)
        log.append({
            "download_url": manifest_url,
            "retrieved_at": now_utc(),
            "byte_size": len(manifest),
            "sha256": sha256_bytes(manifest),
            "http_status": 200,
            "role": f"sbml:{mid}",
            "final_url": manifest_url,
            "error": None,
        })
        return manifest_url, manifest
    name = None
    if manifest:
        match = re.search(rb"<main>.*?<name>([^<]+)</name>", manifest, re.DOTALL)
        if match:
            name = match.group(1).decode("utf-8", "replace").strip()
    if name:
        url = "https://www.ebi.ac.uk/biomodels/model/download/" + mid + "?filename=" + requests.utils.quote(name)
        blob = http_get(url, f"sbml:{mid}", log)
        if blob and _is_sbml(blob):
            dest.write_bytes(blob)
            return url, blob
    zurl = BIOMD_URLS[1].format(mid=mid)
    zblob = http_get(zurl, f"zip:{mid}", log, max_bytes=25_000_000)
    if zblob and zblob[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(zblob)) as zf:
                members = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                preferred = [n for n in members if n.endswith("_url.xml") or (name and n.endswith(name))]
                for member in preferred + [n for n in members if n not in preferred]:
                    data = zf.read(member)
                    if not _is_sbml(data):
                        continue
                    dest.write_bytes(data)
                    log.append({
                        "download_url": zurl,
                        "retrieved_at": now_utc(),
                        "byte_size": len(data),
                        "sha256": sha256_bytes(data),
                        "http_status": 200,
                        "role": f"sbml:{mid}",
                        "final_url": zurl,
                        "error": None,
                        "zip_member": member,
                    })
                    return zurl, data
        except Exception:
            return None, None
    return None, None


def panel_name(table_ids: list[str], models: list[dict]) -> str:
    if not models:
        return "none"
    sources = {m["id_source"] for m in models}
    if sources == {"table-s1"}:
        return "table-s1"
    if "table-s1" in sources:
        return "table-s1-plus-sequential"
    return "sequential-biomodels"


def _frac(num, den):
    if den <= 0:
        return None
    return num / den


def decide(claim_id: str, models: list[dict], panel: str, cfg: dict) -> dict:
    """Apply the pre-registered decision rule. models are baseline-ok and included."""
    rule = cfg["decision"][claim_id]
    completed = []
    if claim_id.endswith("grn-learning-09"):
        completed = [m for m in models if m.get("memory_screen_complete")]
    elif claim_id.endswith("grn-learning-18"):
        completed = [m for m in models if m.get("phenotype_screen_complete") and m.get("breaking", {}).get("complete")]
    elif claim_id.endswith("wisdom-04"):
        completed = [m for m in models if m.get("phenotype_screen_complete") and m.get("associative_screen_complete")]
    n = len(completed)
    reason = None
    extra = {"panel": panel, "n_completed": n, "n_baseline_ok": len(models)}

    if not models and panel == "none":
        return _pack("inconclusive", "data-unavailable", extra, cfg, claim_id, panel)

    if claim_id.endswith("grn-learning-09"):
        if n < int(rule["min_models"]):
            extra["models"] = [_mem_row(m) for m in completed]
            return _pack("inconclusive", "underpowered", extra, cfg, claim_id, panel)
        total_m = 0
        stable = loss = gain = 0
        rows = []
        for m in completed:
            mem = m["memory"]
            # factors stored as "10","50","100"
            m10, m50, m100 = mem["10"], mem["50"], mem["100"]
            total_m += m10 + m50 + m100
            lo, hi = min(m10, m50), max(m10, m50)
            if m10 == m50 == m100:
                stable += 1
                tag = "stable"
            elif lo < m100 and hi > m100:
                loss += 1
                gain += 1
                tag = "both"
            elif hi <= m100 and lo < m100:
                loss += 1
                tag = "loss"
            elif lo >= m100 and hi > m100:
                gain += 1
                tag = "gain"
            else:
                tag = "stable"
                stable += 1
            rows.append({"id": m["biomodels_id"], "M10": m10, "M50": m50, "M100": m100, "tag": tag})
        extra.update({
            "stable_models": stable,
            "loss_models": loss,
            "gain_models": gain,
            "stable_fraction": stable / n,
            "loss_fraction": loss / n,
            "memory_hits_sum": total_m,
            "models": rows,
        })
        if total_m == 0:
            return _pack("inconclusive", "other", extra, cfg, claim_id, panel)
        sup = rule["support"]
        ref = rule["refute"]
        if (stable / n) >= float(sup["min_stable_fraction"]) and (loss / n) <= float(sup["max_loss_fraction"]) and gain >= int(sup["min_gain_models"]):
            return _pack("supports", None, extra, cfg, claim_id, panel)
        if (loss / n) >= float(ref["min_loss_fraction"]) or (gain == 0 and (stable / n) < float(ref["max_stable_fraction_if_no_gain"])):
            return _pack("refutes", None, extra, cfg, claim_id, panel)
        return _pack("mixed", None, extra, cfg, claim_id, panel)

    if claim_id.endswith("grn-learning-18"):
        sens_models = [m for m in completed if (m.get("sensitization_pairs") or 0) > 0]
        hab_models = [m for m in completed if (m.get("habituation_pairs") or 0) > 0]
        extra["n_sensitizing_models"] = len(sens_models)
        extra["n_habituating_models"] = len(hab_models)
        extra["models"] = [_break_row(m) for m in completed]
        if len(sens_models) < int(rule["min_sens_models"]) or len(hab_models) < int(rule["min_hab_models"]):
            return _pack("inconclusive", "underpowered", extra, cfg, claim_id, panel)

        def model_break_rate(group, stable_key, broken_key):
            broken_models = 0
            rare = 0
            fracs = []
            for m in group:
                br = m["breaking"]
                stable = br[stable_key]
                broken = br[broken_key]
                frac = 0.0 if stable <= 0 else broken / stable
                fracs.append(frac)
                if broken >= 1 and stable >= 1:
                    broken_models += 1
                if frac < float(rule["pair_fraction_rare"]):
                    rare += 1
            return broken_models / len(group), rare / len(group), fracs

        sens_rate, sens_rare, sens_fracs = model_break_rate(sens_models, "sens_stable_tested", "sens_broken")
        hab_rate, hab_rare, hab_fracs = model_break_rate(hab_models, "hab_stable_tested", "hab_broken")
        sens_stable_total = sum(m["breaking"]["sens_stable_tested"] for m in sens_models)
        hab_stable_total = sum(m["breaking"]["hab_stable_tested"] for m in hab_models)
        extra.update({
            "sens_break_model_rate": sens_rate,
            "hab_break_model_rate": hab_rate,
            "sens_pair_rare_fraction": sens_rare,
            "hab_pair_rare_fraction": hab_rare,
            "sens_pair_break_fractions": sens_fracs,
            "hab_pair_break_fractions": hab_fracs,
            "sens_stable_pairs": sens_stable_total,
            "hab_stable_pairs": hab_stable_total,
        })
        # Equal zeros are not evidence that the rates differ, and not evidence that they match.
        # A rate comparison is scored only when each phenotype had a pair that still showed it
        # on the two-pulse retest with no third-node clamp.
        if sens_stable_total <= 0 or hab_stable_total <= 0:
            return _pack("inconclusive", "other", extra, cfg, claim_id, panel)
        margin = float(rule["support"]["min_rate_margin"])
        if (
            sens_rate <= float(rule["support"]["max_sens_break_rate"])
            and hab_rate >= sens_rate + margin
            and sens_rare >= float(rule["support"]["min_pair_rare_fraction"])
        ):
            return _pack("supports", None, extra, cfg, claim_id, panel)
        if (
            sens_rate >= hab_rate
            or sens_rate >= float(rule["refute"]["min_sens_break_rate"])
            or sens_rare < float(rule["refute"]["max_pair_rare_fraction_exclusive"])
        ):
            return _pack("refutes", None, extra, cfg, claim_id, panel)
        return _pack("mixed", None, extra, cfg, claim_id, panel)

    if claim_id.endswith("wisdom-04"):
        hab = sum(1 for m in completed if (m.get("habituation_pairs") or 0) > 0)
        sens = sum(1 for m in completed if (m.get("sensitization_pairs") or 0) > 0)
        assoc = sum(1 for m in completed if (m.get("associative_hits") or 0) > 0)
        ids_ok = all(m.get("structure_unchanged") for m in completed) if completed else False
        values_ok = all(m.get("parameter_values_match_deposited") is True for m in completed) if completed else False
        extra.update({
            "habituation_models": hab,
            "sensitization_models": sens,
            "associative_models": assoc,
            "models": [_assoc_row(m) for m in completed],
            "parameter_identifiers_unchanged": ids_ok,
            "parameter_values_match_deposited": values_ok,
            "topology_and_parameters_unchanged": ids_ok and values_ok,
        })
        if hab >= 1 and sens >= 1 and assoc >= 1 and extra["topology_and_parameters_unchanged"]:
            return _pack("supports", None, extra, cfg, claim_id, panel)
        if n >= int(rule["min_models_to_refute"]) and (hab == 0 or sens == 0 or assoc == 0 or not extra["topology_and_parameters_unchanged"]):
            return _pack("refutes", None, extra, cfg, claim_id, panel)
        return _pack("inconclusive", "underpowered", extra, cfg, claim_id, panel)

    raise KeyError(claim_id)


def _mem_row(m):
    return {"id": m["biomodels_id"], "memory": m.get("memory"), "complete": m.get("memory_screen_complete")}


def _break_row(m):
    return {
        "id": m["biomodels_id"],
        "habituation_pairs": m.get("habituation_pairs"),
        "sensitization_pairs": m.get("sensitization_pairs"),
        "breaking": {k: v for k, v in m.get("breaking", {}).items() if k != "examples"},
        "examples": m.get("breaking", {}).get("examples", [])[:6],
    }


def _assoc_row(m):
    return {
        "id": m["biomodels_id"],
        "habituation_pairs": m.get("habituation_pairs"),
        "sensitization_pairs": m.get("sensitization_pairs"),
        "associative_hits": m.get("associative_hits"),
        "associative_examples": m.get("associative_examples", [])[:4],
        "structure_unchanged": m.get("structure_unchanged"),
        "parameter_values_match_deposited": m.get("parameter_values_match_deposited"),
    }


def _pack(verdict, reason, extra, cfg, claim_id, panel):
    conf = confidence_for(verdict, reason, panel, claim_id)
    return {"verdict": verdict, "reason": reason, "confidence": conf, "extra": extra}


def confidence_for(verdict: str, reason: str | None, panel: str, claim_id: str) -> float:
    if verdict == "inconclusive":
        if reason == "data-unavailable":
            return 0.8
        if reason == "other":
            return 0.6
        return 0.55
    if panel == "table-s1":
        c = 0.58
    elif panel == "table-s1-plus-sequential":
        c = 0.48
    else:
        c = 0.42
    if verdict == "mixed":
        c = min(c, 0.5)
    if claim_id.endswith("grn-learning-18") and verdict == "supports":
        c = min(c, 0.45)
    return c


def measured_block(claim_id: str, decision: dict) -> dict:
    extra = decision["extra"]
    if claim_id.endswith("grn-learning-09"):
        return {
            "value": extra.get("stable_fraction"),
            "unit": "fraction of completed models whose UCS-memory counts are equal at 10x, 50x and 100x",
            "n": extra.get("n_completed"),
            "uncertainty": "deterministic given libroadrunner 2.11 and the recorded SBML bytes; no sampling noise",
            "extra": extra,
        }
    if claim_id.endswith("grn-learning-18"):
        return {
            "value": extra.get("sens_break_model_rate"),
            "unit": "fraction of sensitizing models in which a third-node clamp broke at least one stable pair",
            "n": extra.get("n_sensitizing_models"),
            "uncertainty": "deterministic given libroadrunner 2.11 and the recorded SBML bytes; one breaking trial",
            "extra": extra,
        }
    return {
        "value": {
            "habituation_models": extra.get("habituation_models"),
            "sensitization_models": extra.get("sensitization_models"),
            "associative_models": extra.get("associative_models"),
        },
        "unit": "completed models showing each phenotype at least once",
        "n": extra.get("n_completed"),
        "uncertainty": "deterministic given libroadrunner 2.11 and the recorded SBML bytes",
        "extra": extra,
    }


def summary_lines(claim_id: str, decision: dict) -> list[str]:
    e = decision["extra"]
    panel = e.get("panel")
    lines = [f"Panel: {panel}. Baseline-ok models: {e.get('n_baseline_ok')}. Completed for this claim: {e.get('n_completed')}."]
    if claim_id.endswith("grn-learning-09"):
        lines.append(
            f"Stable fraction {e.get('stable_fraction')}, loss fraction {e.get('loss_fraction')}, "
            f"gain models {e.get('gain_models')}, memory-hit sum {e.get('memory_hits_sum')}."
        )
    elif claim_id.endswith("grn-learning-18"):
        lines.append(
            f"Sensitizing models {e.get('n_sensitizing_models')}, habituating models {e.get('n_habituating_models')}. "
            f"Sensitization break rate {e.get('sens_break_model_rate')}, habituation break rate {e.get('hab_break_model_rate')}, "
            f"fraction of sensitizing models with pair-break fraction under 0.05: {e.get('sens_pair_rare_fraction')}."
        )
    else:
        lines.append(
            f"Models with habituation {e.get('habituation_models')}, sensitization {e.get('sensitization_models')}, "
            f"associative conditioning {e.get('associative_models')}. "
            f"Parameter identifiers unchanged: {e.get('parameter_identifiers_unchanged')}. "
            f"Deposited parameter values unchanged: {e.get('parameter_values_match_deposited')}."
        )
    lines.append(f"Verdict {decision['verdict']}" + (f" ({decision['reason']})" if decision.get("reason") else "") + f", confidence {decision['confidence']}.")
    return lines


def run(spec: dict, here: Path) -> dict:
    cfg = spec["preregistration"]
    claim_id = spec["claim_id"]
    log: list = []
    data_dir = here / "data" / "sbml"
    data_dir.mkdir(parents=True, exist_ok=True)
    table_ids, table_files = discover_table_ids(cfg, log)
    print(f"table-s1 identifiers: {len(table_ids)}", flush=True)
    order = [(mid, "table-s1") for mid in table_ids]
    for mid in sequential_ids(int(cfg["sequential_start"]), int(cfg["sequential_count"])):
        if mid not in table_ids:
            order.append((mid, "sequential"))

    models = []
    skipped = []
    attempts = 0
    max_models = int(cfg["max_models"])
    max_attempts = int(cfg["max_download_attempts"])
    for mid, source in order:
        if len(models) >= max_models or attempts >= max_attempts:
            break
        # Prefer filling from the table before spending the attempt budget on the sequential scan,
        # but both share one attempt counter so a long miss streak still stops.
        attempts += 1
        dest = data_dir / f"{mid}.xml"
        url = None
        blob = None
        print(f"attempt {attempts} {mid} ({source})", flush=True)
        url, blob = download_sbml(mid, dest, log)
        if blob is None:
            skipped.append({"id": mid, "reason": "download-failed", "source": source})
            print(f"skip {mid} download-failed", flush=True)
            continue
        meta_blob = http_get(META_URL.format(mid=mid), f"meta:{mid}", log, max_bytes=2_000_000)
        license_name = license_from_meta(meta_blob) if meta_blob else None
        try:
            result = analyze_sbml_file(dest, cfg)
        except Exception as exc:
            skipped.append({"id": mid, "reason": "load-failed", "error": str(exc)[:200], "source": source})
            print(f"skip {mid} load-failed {exc}"[:240], flush=True)
            continue
        if not result.get("baseline_ok"):
            skipped.append({
                "id": mid,
                "reason": result.get("skip_reason"),
                "n_floating": result.get("n_floating"),
                "source": source,
            })
            print(f"skip {mid} {result.get('skip_reason')} n={result.get('n_floating')}", flush=True)
            continue
        file_rec = next((r for r in reversed(log) if r["role"] == f"sbml:{mid}" and r["http_status"] == 200), None)
        result["biomodels_id"] = mid
        result["id_source"] = source
        result["download_url"] = file_rec["download_url"] if file_rec else url
        result["retrieved_at"] = file_rec["retrieved_at"] if file_rec else None
        result["byte_size"] = file_rec["byte_size"] if file_rec else len(blob)
        result["sha256"] = file_rec["sha256"] if file_rec else sha256_bytes(blob)
        result["license"] = license_name
        models.append(result)
        print(
            f"kept {mid} n={result.get('n_floating')} H={result.get('horizon')} "
            f"wall={result.get('wall_seconds')} memory={result.get('memory')} "
            f"hab={result.get('habituation_pairs')} sens={result.get('sensitization_pairs')} "
            f"assoc={result.get('associative_hits')}",
            flush=True,
        )

    panel = panel_name(table_ids, models)
    if not models:
        panel = "none"
    decision = decide(claim_id, models, panel, cfg)
    decision["extra"]["table_s1_ids_found"] = len(table_ids)
    decision["extra"]["download_attempts"] = attempts
    decision["extra"]["skipped"] = skipped
    decision["extra"]["libroadrunner"] = roadrunner.__version__

    files = []
    for m in models:
        files.append({
            "biomodels_id": m["biomodels_id"],
            "download_url": m["download_url"],
            "retrieved_at": m["retrieved_at"],
            "byte_size": m["byte_size"],
            "sha256": m["sha256"],
            "license": m.get("license"),
            "id_source": m["id_source"],
            "n_floating": m["n_floating"],
            "horizon": m["horizon"],
        })
    dataset = {
        "id": "biomodels-curated-sbml",
        "name": "BioModels curated SBML files simulated with libroadrunner",
        "landing_url": "https://www.ebi.ac.uk/biomodels/",
        "doi": None,
        "version": "files retrieved at the timestamps in files[]",
        "license": None,
        "files": files,
        "role": "ordinary differential equations of published pathway and gene-regulatory models; stimuli are temporary clamps of state variables",
    }
    spec_files = spec.get("specification_files") or []
    datasets = [dataset] + spec_files
    if table_files:
        datasets.append({
            "id": "biswas-2023-table-s1-pages",
            "name": "Pages or attachments from which BioModels identifiers were read",
            "landing_url": "https://doi.org/10.3390/ijms24010285",
            "doi": "10.3390/ijms24010285",
            "version": None,
            "license": "CC BY 4.0",
            "files": [
                {
                    "download_url": f["download_url"],
                    "byte_size": f["byte_size"],
                    "sha256": f["sha256"],
                    "retrieved_at": next((r["retrieved_at"] for r in log if r["download_url"] == f["download_url"]), None),
                }
                for f in table_files
            ],
            "role": "source of surveyed model identifiers only; numeric result tables were not parsed",
        })

    # Per-model derived table without end-state vectors (already stripped).
    derived_models = []
    for m in models:
        derived_models.append({k: v for k, v in m.items() if k not in ("cache",)})

    run_notes = [
        f"Run panel was {panel}. Table S1 identifier strings found: {len(table_ids)}. Download attempts: {attempts}. Baseline-ok models: {len(models)}.",
        "Stimuli were temporary boundary clamps of existing species. The test does not assign parameter values and does not add or remove reactions.",
        "This computation does not show that the claim holds in organisms.",
    ]
    if any(not m.get("structure_unchanged", False) for m in models):
        run_notes.append("At least one model gained or lost a parameter or a reaction during the screens. Those models are not treated as fixed-topology hits.")
    elif models:
        run_notes.append("Parameter identifiers and reaction identifiers matched the deposited models after the screens.")
    if any(m.get("parameter_values_match_deposited") is False for m in models):
        run_notes.append("On at least one model, global parameter values at the end of the screens differed from the deposited values. The test never assigns parameters; the difference is left to the model's own rules and events. For levin-2025-wisdom-04 that difference counts as a changed parameter.")
    elif models:
        run_notes.append("Global parameter values at the end of the screens matched the deposited values.")

    return {
        "datasets": datasets,
        "measured": measured_block(claim_id, decision),
        "verdict": decision["verdict"],
        "reason": decision["reason"],
        "confidence": decision["confidence"],
        "data_kind": "computational" if models else "none",
        "results_summary": summary_lines(claim_id, decision),
        "run_notes": run_notes,
        "derived": {
            "models": derived_models,
            "skipped": skipped,
            "panel": panel,
            "decision": decision,
        },
        "retrieval_count": len(log),
    }


def apply_run(spec: dict, payload: dict) -> dict:
    """Fill result fields. Frozen prose and the preregistration block are copied through."""
    out = dict(spec)
    out["status"] = "complete"
    out["datasets"] = payload["datasets"]
    out["measured"] = payload["measured"]
    out["verdict"] = payload["verdict"]
    out["confidence"] = payload["confidence"]
    out["data_kind"] = payload["data_kind"]
    out["results_summary"] = payload["results_summary"]
    out["method"] = spec["method_template"]
    notes = [c for c in payload["run_notes"] if c not in out.get("caveats", [])]
    out["caveats"] = list(out.get("caveats", [])) + notes
    if payload["verdict"] == "inconclusive":
        out["reason"] = payload["reason"]
    else:
        out.pop("reason", None)
    return out


def self_test() -> None:
    cfg = {
        "near_zero": 1e-9,
        "appear_threshold": 1e-4,
        "regulation_up_ratio": 2.0,
        "regulation_down_ratio": 0.5,
        "floor": 1e-6,
        "phenotype_ratio": 1.5,
    }
    assert classify(1.0, 2.0, cfg) == "up"
    assert classify(1.0, 0.5, cfg) == "down"
    assert classify(1.0, 1.2, cfg) == "none"
    assert classify(0.0, 1e-4, cfg) == "up"
    assert classify(0.0, 0.0, cfg) == "none"
    assert phenotype_flags([8, 4, 2, 1, 0.5, 0.2], cfg) == (True, False)
    assert phenotype_flags([1, 2, 4, 8, 16, 32], cfg) == (False, True)
    assert phenotype_flags([1, 2, 3, 4, 5, 6], cfg) == (False, False)
    assert clamp_level("up", 100, 0.2, 0.2, 0.0, cfg) == 20
    assert abs(clamp_level("down", 10, 0.2, 0.2, 0.0, cfg) - 0.02) < 1e-12
    assert evenly(["a", "b", "c", "d", "e"], 3) == ["a", "c", "e"] or evenly(list("abcde"), 3)[0] == "a"

    # Decision: robust pattern supports claim 09.
    fake_cfg = {
        "decision": json.loads(Path(__file__).with_name("result.json").read_text())["preregistration"]["decision"]
    }
    def mem_model(i, a, b, c):
        return {"biomodels_id": f"M{i}", "memory_screen_complete": True, "memory": {"10": a, "50": b, "100": c}}
    models = [mem_model(i, 2, 2, 2) for i in range(5)] + [mem_model(9, 4, 3, 2)]
    d = decide("levin-2022-grn-learning-09", models, "table-s1", fake_cfg)
    assert d["verdict"] == "supports", d
    # Widespread loss refutes.
    models = [mem_model(i, 0, 0, 4) for i in range(6)]
    d = decide("levin-2022-grn-learning-09", models, "sequential-biomodels", fake_cfg)
    assert d["verdict"] == "refutes", d
    # No memories at all is inconclusive.
    models = [mem_model(i, 0, 0, 0) for i in range(6)]
    d = decide("levin-2022-grn-learning-09", models, "sequential-biomodels", fake_cfg)
    assert d["verdict"] == "inconclusive" and d["reason"] == "other", d

    def pheno(i, hab, sens, hab_stable, hab_broken, sens_stable, sens_broken, assoc=0, breaking_done=True):
        return {
            "biomodels_id": f"P{i}",
            "memory_screen_complete": True,
            "memory": {"10": 0, "50": 0, "100": 0},
            "phenotype_screen_complete": True,
            "breaking": {
                "complete": breaking_done,
                "hab_stable_tested": hab_stable,
                "hab_broken": hab_broken,
                "sens_stable_tested": sens_stable,
                "sens_broken": sens_broken,
            },
            "habituation_pairs": hab,
            "sensitization_pairs": sens,
            "associative_hits": assoc,
            "associative_screen_complete": True,
            "structure_unchanged": True,
            "parameter_values_match_deposited": True,
        }
    # Sensitization rarely broken, habituation often broken.
    group = []
    for i in range(4):
        group.append(pheno(i, hab=2, sens=2, hab_stable=4, hab_broken=3, sens_stable=4, sens_broken=0, assoc=1))
    d = decide("levin-2022-grn-learning-18", group, "table-s1", fake_cfg)
    assert d["verdict"] == "supports", d
    d = decide("levin-2025-wisdom-04", group, "table-s1", fake_cfg)
    assert d["verdict"] == "supports", d
    # Sensitization broken as often as habituation.
    group = [pheno(i, 2, 2, 4, 3, 4, 3, 0) for i in range(4)]
    d = decide("levin-2022-grn-learning-18", group, "sequential-biomodels", fake_cfg)
    assert d["verdict"] == "refutes", d
    # Missing associative on a large enough panel refutes wisdom-04.
    group = [pheno(i, 1, 1, 1, 0, 1, 0, 0) for i in range(6)]
    d = decide("levin-2025-wisdom-04", group, "sequential-biomodels", fake_cfg)
    assert d["verdict"] == "refutes", d
    # Deposited parameter values that differ still count as a changed parameter.
    drifted = [pheno(i, 1, 1, 1, 0, 1, 0, 1) for i in range(6)]
    for row in drifted:
        row["parameter_values_match_deposited"] = False
    d = decide("levin-2025-wisdom-04", drifted, "sequential-biomodels", fake_cfg)
    assert d["verdict"] == "refutes" and d["extra"]["topology_and_parameters_unchanged"] is False, d
    # Phenotypes that do not survive the two-pulse retest are not a rate comparison.
    group = [pheno(i, 2, 2, 0, 0, 0, 0, 1) for i in range(4)]
    d = decide("levin-2022-grn-learning-18", group, "table-s1", fake_cfg)
    assert d["verdict"] == "inconclusive" and d["reason"] == "other", d
    print("self-test ok")


if __name__ == "__main__":
    self_test()
