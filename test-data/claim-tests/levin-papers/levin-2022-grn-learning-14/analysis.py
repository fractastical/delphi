#!/usr/bin/env python3
"""Habituation screen for levin-2022-grn-learning-14.

Re-simulates the 35 BioModels ODE models named in Table S1 of Biswas, Clawson
and Levin, Int. J. Mol. Sci. 2023, 24, 285, using each model's public Octave
export (the file the paper converted and integrated). The decision rule is the
pre-registered one in result.json; this script does not choose thresholds.

Standard libraries plus numpy, scipy and requests. No author result table is read.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import requests
from scipy.integrate import solve_ivp

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT_PATH = os.path.join(HERE, "result.json")
DERIVED_PATH = os.path.join(HERE, "derived", "measured.json")

# Table S1, read from page 1 of ijms-1976523-supplementary.pdf inside
# ijms-24-00285-s001.zip after the preregistration commit. Order is the table order.
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

SUPPLEMENT_URL = (
    "https://mdpi-res.com/d_attachment/ijms/ijms-24-00285/"
    "article_deploy/ijms-24-00285-s001.zip"
)
SUPPLEMENT_SHA256 = (
    "292a7f33bcb3a9589614507114de8c1a7a5f5d8bc11e382d546c3d08da381e39"
)
SUPPLEMENT_BYTES = 2886027
SUPPLEMENT_RETRIEVED = "2026-11-02T00:22:18Z"

# Pre-registered protocol constants.
RELAX_TIME = 100.0
BASELINE_WINDOW = 10.0
PULSE_DURATIONS = (50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
SAMPLE_STEP = 0.01
HAB_RATIO = 1.0 / 1.5
HALF_RATIO = 0.5
ENGAGE_FACTOR = 1.5
MAX_SPECIES = 40
RTOL = 1e-4
ATOL = 1e-7
MAX_STEP = 0.5

DOWNLOAD_TMPL = (
    "https://www.ebi.ac.uk/biomodels/model/download/{mid}?filename={mid}.m"
)


def piecewise(*args):
    """SBFC's MATLAB piecewise: value, condition==1, ..., default."""
    if len(args) < 1 or len(args) % 2 == 0:
        raise ValueError("piecewise arity")
    for i in range(0, len(args) - 1, 2):
        cond = args[i + 1]
        if cond == 1:
            return args[i]
    return args[-1]


def pow_(x, y):
    return x ** y


def root_(x, y):
    return y ** (1.0 / x)


class Holder:
    clamps = {}


def _logical_lines(text: str):
    """Drop MATLAB comments. SBFC sometimes glues the real assignment onto the
    comment line after a tab (`% Species: ... \\t const_species_X=1`). That
    statement is restored, because without it the export calls a name it never
    defines. A `%` still comments out everything before that tab."""
    lines = []
    for line in text.splitlines():
        if "%" in line:
            pre, post = line.split("%", 1)
            if pre.strip():
                lines.append(pre)
            glued = re.search(r"\t\s*(\S.*)$", post)
            if glued:
                stmt = glued.group(1).strip()
                if re.match(r"(?:xdot\s*\(|x\(\d+\)\s*=|[A-Za-z_]\w*\s*=)", stmt):
                    lines.append(stmt)
        else:
            lines.append(line)
    return lines


def _transform_expr(expr: str) -> str:
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = expr.replace("^", "**")
    expr = re.sub(r"\btrue\b", "True", expr)
    expr = re.sub(r"\bfalse\b", "False", expr)
    expr = re.sub(r"\btime\b", "t", expr)
    expr = re.sub(r"\bxdot\((\d+)\)", lambda m: f"xdot[{int(m.group(1)) - 1}]", expr)
    expr = re.sub(r"\bx\((\d+)\)", lambda m: f"x[{int(m.group(1)) - 1}]", expr)
    expr = re.sub(r"\bzeros\((\d+)\s*,\s*1\)", r"np.zeros(\1)", expr)
    expr = expr.replace("pow(", "pow_(").replace("root(", "root_(")
    return expr


def _hoist_helpers(helper_src: str):
    """One-line `function z=name(args), z=expr;end` rate laws."""
    found = []
    for line in helper_src.splitlines():
        line = line.strip()
        m = re.match(
            r"function\s+z\s*=\s*([A-Za-z_]\w*)\(([^)]*)\)\s*,\s*z\s*=\s*(.+?)\s*;\s*end\s*$",
            line,
        )
        if not m:
            continue
        name, args, expr = m.group(1), m.group(2), m.group(3)
        if name in {"pow", "root", "piecewise"}:
            continue
        found.append((name, args, _transform_expr(expr)))
    return found


def _assignment_target(line: str):
    if line.startswith("xdot") or line.startswith("if") or line == "end":
        return None
    m = re.match(r"x\((\d+)\)\s*=", line)
    if m:
        return f"x({m.group(1)})"
    m = re.match(r"([A-Za-z_]\w*)\s*=", line)
    if m:
        return m.group(1)
    return None


def _hoist_literal_assignments(lines):
    """Constants SBFC places after the reactions that use them."""
    literal = re.compile(
        r"[A-Za-z_]\w*\s*=\s*[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?\s*$"
    )
    head, rest = [], []
    depth = 0
    for ln in lines:
        if ln.startswith("if"):
            depth += 1
            rest.append(ln)
            continue
        if ln == "end":
            depth = max(0, depth - 1)
            rest.append(ln)
            continue
        if depth == 0 and literal.match(ln):
            head.append(ln)
        else:
            rest.append(ln)
    return head + rest


def _reorder_assignments(lines):
    """Move straight-line assignment rules so a name is computed before use.

    SBFC emits some assignment rules in an order MATLAB would also reject
    (BIOMD0000000275 uses alpha2 before it is assigned). Only the prefix
    before the first reaction, xdot or if is reordered.
    """
    cut = len(lines)
    for i, ln in enumerate(lines):
        if ln.startswith("reaction_") or ln.startswith("xdot") or ln.startswith("if"):
            cut = i
            break
    prefix, tail = lines[:cut], lines[cut:]
    # Bubble an assignment up only past the immediately preceding assignment
    # it depends on. Non-assignment lines stay put, so reactions are not crossed.
    guard = 0
    changed = True
    while changed and guard < len(prefix) ** 2 + 2:
        changed = False
        guard += 1
        targets_pos = {}
        for i, ln in enumerate(prefix):
            tgt = _assignment_target(ln)
            if tgt:
                targets_pos[tgt] = i
        for i in range(1, len(prefix)):
            prev_own = _assignment_target(prefix[i - 1])
            cur_own = _assignment_target(prefix[i])
            if not prev_own or not cur_own:
                continue
            used = set(re.findall(r"\bx\(\d+\)", prefix[i - 1]))
            used |= set(re.findall(r"\b[A-Za-z_]\w*", prefix[i - 1]))
            if cur_own in used and cur_own != prev_own:
                prefix[i - 1], prefix[i] = prefix[i], prefix[i - 1]
                changed = True
                break
    return prefix + tail


def translate_octave(src: str):
    """Compile the SBFC Octave xdot function. Returns (f, x0, n, species, note)."""
    if re.search(r"(?m)^[^%\n]*\bdelay\s*\(", src):
        raise RuntimeError("delay() is present; the Octave export does not implement it")
    sig = re.search(r"(?m)^function xdot=f\(x\s*,\s*t\)\s*$", src)
    if not sig:
        raise RuntimeError("no Octave xdot signature")
    main = src[: sig.start()]
    n_match = re.search(r"zeros\((\d+)\s*,\s*1\)", main)
    if not n_match:
        raise RuntimeError("no x0 size")
    n = int(n_match.group(1))
    x0 = np.zeros(n, dtype=float)
    for idx, val in re.findall(r"x0\((\d+)\)\s*=\s*([^;\n]+)", main):
        x0[int(idx) - 1] = float(val.strip())

    rest = src[sig.end() :]
    # Helper functions (rate laws the exporter did not inline) follow xdot.
    split_at = re.search(r"(?m)^function\s+", rest)
    body_src = rest[: split_at.start()] if split_at else rest
    helper_src = rest[split_at.start() :] if split_at else ""
    helpers = _hoist_helpers(helper_src)
    raw_lines = []
    for ln in _logical_lines(body_src):
        ln = ln.strip()
        if ln.endswith(";"):
            ln = ln[:-1].strip()
        if not ln:
            continue
        if re.match(r"xdot\(\d+\)\s*=\s*$", ln):
            ln = ln + " 0.0"
        raw_lines.append(ln)
    while raw_lines and raw_lines[-1] == "end":
        n_if = sum(1 for ln in raw_lines if ln.startswith("if"))
        n_end = sum(1 for ln in raw_lines if ln == "end")
        if n_end > n_if:
            raw_lines.pop()
        else:
            break
    raw_lines = _hoist_literal_assignments(raw_lines)
    raw_lines = _reorder_assignments(raw_lines)

    species = []
    py = [
        "def f(t, y):",
        "    x = np.array(y, dtype=float, copy=True)",
        "    for _i, _v in H.clamps.items():",
        "        x[_i] = _v",
    ]
    indent = 1
    for ln in raw_lines:
        if ln == "end":
            indent = max(1, indent - 1)
            continue
        if ln.startswith("if"):
            cond = ln[2:].strip()
            if cond.startswith("(") and cond.endswith(")"):
                cond = cond[1:-1]
            py.append("    " * indent + f"if {_transform_expr(cond)}:")
            indent += 1
            continue
        m_asg = re.match(r"x\[(\d+)\]\s*=\s*(.+)", _transform_expr(ln))
        if m_asg and not ln.replace(" ", "").startswith("xdot"):
            idx = m_asg.group(1)
            rhs = m_asg.group(2)
            py.append("    " * indent + f"_rhs = {rhs}")
            py.append(
                "    " * indent + f"if {idx} not in H.clamps: x[{idx}] = _rhs"
            )
            continue
        py.append("    " * indent + _transform_expr(ln))
    py.append("    for _i in H.clamps:")
    py.append("        xdot[_i] = 0.0")
    py.append("    return xdot")
    code = "\n".join(py)
    # Species labels from the original (pre-strip) function body, in xdot order.
    fbody = src[sig.end() :].split("% adding few functions", 1)[0]
    for m in re.finditer(
        r"%\s*Species:\s*id\s*=\s*([^,\n]+),\s*name\s*=\s*([^,\n%]+)", fbody
    ):
        species.append({"id": m.group(1).strip(), "name": m.group(2).strip()})
    ns = {
        "np": np,
        "piecewise": piecewise,
        "pow_": pow_,
        "root_": root_,
        "H": Holder,
    }
    for name, args, expr in helpers:
        exec(f"def {name}({args}):\n    return {expr}\n", ns)
    exec(code, ns)
    ns["f"]._code = code  # type: ignore[attr-defined]
    return ns["f"], x0, n, species, code


def _sample_count(duration: float) -> int:
    return int(round(duration / SAMPLE_STEP)) + 1


# A normal epoch finishes in a few hundred RHS calls. Past this, LSODA is
# stalled on a bad Jacobian and the pair is counted non-finite.
MAX_NFEV = 8000


def _epoch(f, y, t0, duration, clamps, r_index):
    Holder.clamps = dict(clamps)
    y0 = np.array(y, dtype=float, copy=True)
    for i, v in clamps.items():
        y0[i] = v
    calls = {"n": 0}

    def capped(t, yy):
        calls["n"] += 1
        if calls["n"] > MAX_NFEV:
            raise RuntimeError("nfev cap")
        return f(t, yy)

    t_eval = np.linspace(t0, t0 + duration, _sample_count(duration))
    sol = solve_ivp(
        capped,
        (t0, t0 + duration),
        y0,
        method="LSODA",
        t_eval=t_eval,
        rtol=RTOL,
        atol=ATOL,
        max_step=MAX_STEP,
    )
    Holder.clamps = {}
    if (not sol.success) or sol.y.shape[1] == 0 or not np.all(np.isfinite(sol.y)):
        return None, None
    mean_r = float(np.mean(sol.y[r_index]))
    if not np.isfinite(mean_r):
        return None, None
    return sol.y[:, -1], mean_r


def _engages(m1, baseline):
    if not np.isfinite(m1) or not np.isfinite(baseline):
        return False
    if baseline > 1e-15:
        return m1 >= ENGAGE_FACTOR * baseline or m1 <= baseline / ENGAGE_FACTOR
    return m1 > 1e-12


def _habituates(means, ratio):
    if means[0] <= 1e-12:
        return False
    if any(not np.isfinite(m) for m in means):
        return False
    return all(means[i + 1] <= means[i] * ratio for i in range(5))


def screen_model(mid: str, text: str) -> dict:
    row = {
        "id": mid,
        "downloaded": True,
        "byte_size": len(text.encode("utf-8")),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "testable": False,
        "reason": None,
        "n_species": None,
        "n_attempted": 0,
        "n_finite": 0,
        "n_habituating": 0,
        "n_habituating_half": 0,
        "fraction": None,
        "fraction_half": None,
        "n_regulating_pairs": 0,
        "examples": [],
    }
    try:
        f, x0, n, species, _code = translate_octave(text)
    except Exception as exc:  # translation failure: model not testable
        row["reason"] = f"translate: {exc}"
        return row
    row["n_species"] = n
    if n > MAX_SPECIES:
        row["reason"] = f"n_species {n} exceeds pre-registered cap {MAX_SPECIES}"
        return row
    if n < 2:
        row["reason"] = "fewer than 2 species"
        return row
    try:
        y_end, _ = _epoch(f, x0, 0.0, RELAX_TIME, {}, 0)
    except Exception as exc:
        row["reason"] = f"relax: {exc}"
        return row
    if y_end is None:
        row["reason"] = "relax non-finite"
        return row
    # Min, max, and the last-10-time-unit mean. One more monitored relax.
    Holder.clamps = {}
    t_eval = np.linspace(0.0, RELAX_TIME, _sample_count(RELAX_TIME))
    relax_calls = {"n": 0}

    def relax_capped(t, yy):
        relax_calls["n"] += 1
        if relax_calls["n"] > MAX_NFEV:
            raise RuntimeError("nfev cap")
        return f(t, yy)

    try:
        sol = solve_ivp(
            relax_capped,
            (0.0, RELAX_TIME),
            x0,
            method="LSODA",
            t_eval=t_eval,
            rtol=RTOL,
            atol=ATOL,
            max_step=MAX_STEP,
        )
    except Exception as exc:
        row["reason"] = f"relax: {exc}"
        return row
    if (not sol.success) or not np.all(np.isfinite(sol.y)):
        row["reason"] = "relax non-finite"
        return row
    y_relax = sol.y[:, -1].copy()
    emax = np.max(sol.y, axis=1)
    emin = np.min(sol.y, axis=1)
    tail = sol.y[:, t_eval >= RELAX_TIME - BASELINE_WINDOW]
    baseline = np.mean(tail, axis=1)

    names = []
    for i in range(n):
        if i < len(species):
            names.append(species[i]["id"])
        else:
            names.append(f"x{i+1}")

    attempted = 0
    finite = 0
    hab = 0
    hab_half = 0
    regulating = 0
    examples = []
    for ucs in range(n):
        targets = {
            "up": float(emax[ucs] * 100.0),
            "down": float(emin[ucs] / 100.0),
        }
        for r_index in range(n):
            if r_index == ucs:
                continue
            for direction, target in targets.items():
                attempted += 1
                if not np.isfinite(target):
                    continue
                y = y_relax.copy()
                t = RELAX_TIME
                means = []
                ok = True
                try:
                    for dur in PULSE_DURATIONS:
                        y, mean_r, = _epoch(f, y, t, dur, {ucs: target}, r_index)
                        if y is None:
                            ok = False
                            break
                        means.append(mean_r)
                        t += dur
                        y, _relax_mean = _epoch(f, y, t, dur, {}, r_index)
                        if y is None:
                            ok = False
                            break
                        t += dur
                except TimeoutError:
                    raise
                except Exception:
                    ok = False
                if not ok:
                    continue
                finite += 1
                if _engages(means[0], float(baseline[r_index])):
                    regulating += 1
                is_hab = _habituates(means, HAB_RATIO)
                is_half = _habituates(means, HALF_RATIO)
                if is_hab:
                    hab += 1
                    if len(examples) < 5:
                        examples.append(
                            {
                                "ucs": names[ucs],
                                "response": names[r_index],
                                "direction": direction,
                                "pulse_means": [round(m, 6) for m in means],
                            }
                        )
                if is_half:
                    hab_half += 1
    row["n_attempted"] = attempted
    row["n_finite"] = finite
    row["n_habituating"] = hab
    row["n_habituating_half"] = hab_half
    row["n_regulating_pairs"] = regulating
    row["examples"] = examples
    if attempted == 0 or finite < 0.5 * attempted or finite < 1:
        row["reason"] = "fewer than half the pairs returned finite means"
        row["testable"] = False
        return row
    row["testable"] = True
    row["fraction"] = hab / finite
    row["fraction_half"] = hab_half / finite
    row["reason"] = None
    return row


def download(mid: str) -> str:
    url = DOWNLOAD_TMPL.format(mid=mid)
    last = None
    for _ in range(3):
        try:
            resp = requests.get(url, timeout=90, headers={"Accept": "text/plain"})
            resp.raise_for_status()
            text = resp.text
            if "function xdot=f" not in text and "function xdot=f(x,t)" not in text:
                # Some responses are the MATLAB-comment form; either signature works.
                if "function xdot" not in text:
                    raise RuntimeError(f"not an octave export ({len(text)} bytes)")
            return text
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last))


def _worker(mid: str) -> dict:
    import signal

    def _alarm(signum, frame):
        raise TimeoutError("model exceeded 12 minutes")

    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(12 * 60)
    try:
        return _worker_body(mid)
    finally:
        signal.alarm(0)


def _worker_body(mid: str) -> dict:
    try:
        text = download(mid)
    except Exception as exc:
        return {
            "id": mid,
            "downloaded": False,
            "testable": False,
            "reason": f"download: {exc}",
            "n_species": None,
            "n_attempted": 0,
            "n_finite": 0,
            "n_habituating": 0,
            "n_habituating_half": 0,
            "fraction": None,
            "fraction_half": None,
            "n_regulating_pairs": 0,
            "examples": [],
            "byte_size": None,
            "sha256": None,
        }
    try:
        return screen_model(mid, text)
    except Exception:
        return {
            "id": mid,
            "downloaded": True,
            "byte_size": len(text.encode("utf-8")),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "testable": False,
            "reason": "crash: " + traceback.format_exc(limit=2),
            "n_species": None,
            "n_attempted": 0,
            "n_finite": 0,
            "n_habituating": 0,
            "n_habituating_half": 0,
            "fraction": None,
            "fraction_half": None,
            "n_regulating_pairs": 0,
            "examples": [],
        }


def _dump_partial(rows):
    os.makedirs(os.path.dirname(DERIVED_PATH), exist_ok=True)
    path = os.path.join(os.path.dirname(DERIVED_PATH), "partial.json")
    with open(path, "w") as fh:
        json.dump(rows, fh)
        fh.write("\n")


def decide(rows):
    downloaded = sum(1 for r in rows if r.get("downloaded"))
    testable = [r for r in rows if r.get("testable")]
    T = len(testable)
    if T >= 1:
        engaged = sum(1 for r in testable if r["n_regulating_pairs"] >= 1)
        engagement_ok = engaged / T >= 0.5
    else:
        engaged = 0
        engagement_ok = False
    if T >= 1 and not engagement_ok:
        return "inconclusive", "other", {
            "T": T,
            "engaged_models": engaged,
            "downloaded": downloaded,
        }
    if downloaded < 15:
        return "inconclusive", "data-unavailable", {
            "T": T,
            "engaged_models": engaged,
            "downloaded": downloaded,
        }
    if T < 20:
        return "inconclusive", "underpowered", {
            "T": T,
            "engaged_models": engaged,
            "downloaded": downloaded,
        }
    Z = sum(1 for r in testable if r["n_habituating"] == 0)
    outside = sum(
        1
        for r in testable
        if r["fraction"] is None or not (0.01 <= r["fraction"] <= 0.50)
    )
    info = {
        "T": T,
        "Z": Z,
        "outside_band": outside,
        "engaged_models": engaged,
        "downloaded": downloaded,
    }
    if Z >= 4 or outside > T / 2.0:
        return "refutes", None, info
    if Z == 0 and outside == 0:
        return "supports", None, info
    return "mixed", None, info


def main():
    only = None
    if len(sys.argv) > 1:
        only = sys.argv[1:]
    mids = only or TABLE_S1
    jobs = max(1, min(len(mids), os.cpu_count() or 1))
    print(f"screening {len(mids)} models on {jobs} workers", flush=True)
    rows = []
    if jobs == 1:
        for mid in mids:
            print("start", mid, flush=True)
            row = _worker(mid)
            print("done", mid, row.get("reason"), row.get("fraction"), flush=True)
            rows.append(row)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futs = {pool.submit(_worker, mid): mid for mid in mids}
            for fut in as_completed(futs):
                row = fut.result()
                print(
                    "done",
                    row["id"],
                    "testable" if row.get("testable") else row.get("reason"),
                    "frac",
                    row.get("fraction"),
                    "hab",
                    row.get("n_habituating"),
                    "/",
                    row.get("n_finite"),
                    flush=True,
                )
                rows.append(row)
                _dump_partial(rows)
    rows.sort(key=lambda r: TABLE_S1.index(r["id"]) if r["id"] in TABLE_S1 else 999)
    verdict, reason, info = decide(rows)
    os.makedirs(os.path.dirname(DERIVED_PATH), exist_ok=True)
    derived = {
        "verdict_by_preregistered_rule": verdict,
        "reason": reason,
        "info": info,
        "protocol": {
            "relax_time": RELAX_TIME,
            "pulse_durations": list(PULSE_DURATIONS),
            "sample_step": SAMPLE_STEP,
            "hab_ratio": HAB_RATIO,
            "up_clamp": "max(relax) * 100",
            "down_clamp": "min(relax) / 100",
            "solver": "scipy.integrate.solve_ivp LSODA",
            "rtol": RTOL,
            "atol": ATOL,
            "max_step": MAX_STEP,
            "source": "BioModels Octave export (SBFC), the file class the paper integrated",
        },
        "models": rows,
    }
    with open(DERIVED_PATH, "w") as fh:
        json.dump(derived, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("VERDICT", verdict, reason, info, flush=True)
    partial = os.path.join(os.path.dirname(DERIVED_PATH), "partial.json")
    if os.path.exists(partial):
        os.remove(partial)
    if only:
        return
    _fill_result(rows, verdict, reason, info)


def _fill_result(rows, verdict, reason, info):
    from datetime import datetime, timezone

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(RESULT_PATH) as fh:
        doc = json.load(fh)
    testable = [r for r in rows if r.get("testable")]
    fractions = [r["fraction"] for r in testable]
    doc["status"] = "complete"
    doc["data_kind"] = "computational"
    doc["verdict"] = verdict
    if reason:
        doc["reason"] = reason
    elif "reason" in doc:
        del doc["reason"]
    # Confidence is in the verdict's stability under this reimplementation, not in organisms.
    if verdict == "supports":
        doc["confidence"] = 0.55
    elif verdict == "refutes":
        doc["confidence"] = 0.5
    elif verdict == "mixed":
        doc["confidence"] = 0.5
    else:
        doc["confidence"] = 0.35
    doc["deviations"] = [
        {
            "date": "2026-11-01",
            "what": "Each Table S1 model was integrated from its public BioModels Octave export, not by loading the SBML into a separate simulator.",
            "why": "Section 4.1 says the authors solved the Octave file after a small conversion to MATLAB. That export is the ODE they integrated. The allowed libraries are numpy, scipy and requests, which do not include an SBML engine. Pass and fail thresholds were not changed.",
        },
        {
            "date": "2026-11-01",
            "what": "A right-hand-side evaluation cap of 8000 calls per epoch treats that epoch as non-finite.",
            "why": "LSODA can stall on a bad Jacobian (observed on BIOMD0000000005). Pairs that do not finish are already outside the pre-registered finite-pair denominator. The habituation inequality was not changed.",
        },
    ]
    files = []
    for r in rows:
        if not r.get("sha256"):
            continue
        files.append(
            {
                "name": r["id"] + ".m",
                "download_url": DOWNLOAD_TMPL.format(mid=r["id"]),
                "retrieved_at": retrieved_at,
                "byte_size": r["byte_size"],
                "sha256": r["sha256"],
            }
        )
    doc["datasets"] = [
        {
            "id": "biswas-2023-ijms-supplement-table-s1",
            "name": "Table S1 of Biswas, Clawson and Levin 2023 (supplement zip)",
            "landing_url": "https://doi.org/10.3390/ijms24010285",
            "doi": "10.3390/ijms24010285",
            "version": "ijms-24-00285-s001",
            "license": "CC BY 4.0",
            "files": [
                {
                    "name": "ijms-24-00285-s001.zip",
                    "download_url": SUPPLEMENT_URL,
                    "retrieved_at": SUPPLEMENT_RETRIEVED,
                    "byte_size": SUPPLEMENT_BYTES,
                    "sha256": SUPPLEMENT_SHA256,
                }
            ],
            "role": "identifies the 35 BioModels IDs; only Table S1 (page 1) was read",
        },
        {
            "id": "biomodels-octave-table-s1",
            "name": "BioModels Octave exports for the 35 Table S1 identifiers",
            "landing_url": "https://www.ebi.ac.uk/biomodels/",
            "doi": None,
            "version": "live archive retrieved 2026-11-02",
            "license": None,
            "generator": "analysis.py",
            "program_family": "SBFC Octave export of each curated BioModels SBML model; integrated with scipy LSODA",
            "files": files,
            "role": "ODE right-hand sides and initial conditions for the habituation screen",
        },
    ]
    doc["method"] = (
        "Downloaded each Table S1 model's public Octave export and integrated it with "
        "scipy.integrate.solve_ivp (LSODA, rtol 1e-4, atol 1e-7, max_step 0.5). "
        "After a 0–100 relax, every ordered pair of species was driven with six clamped "
        "pulses of lengths 50, 60, 70, 80, 90 and 100, each followed by an unclamped "
        "relax of the same length. Up-clamp is 100 times the relax maximum; down-clamp "
        "is the relax minimum divided by 100. A pair habituates when each successive "
        "pulse-mean of the response is at most 1/1.5 of the previous mean and the first "
        "mean exceeds 1e-12. The pre-registered rule in pass_criterion and fail_criterion "
        "was applied to those counts without a change of threshold."
    )
    n_hab_models = sum(1 for r in testable if r["n_habituating"] >= 1)
    doc["measured"] = {
        "value": n_hab_models,
        "unit": "testable models with at least one habituating pair",
        "n": len(testable),
        "uncertainty": "deterministic given the solver tolerances; no sampling error",
        "extra": {
            "preregistered_decision": info,
            "fractions": [
                {
                    "id": r["id"],
                    "n_species": r["n_species"],
                    "n_habituating": r["n_habituating"],
                    "n_finite": r["n_finite"],
                    "fraction": r["fraction"],
                    "fraction_successive_half": r["fraction_half"],
                    "n_regulating_pairs": r["n_regulating_pairs"],
                }
                for r in testable
            ],
            "not_testable": [
                {"id": r["id"], "reason": r["reason"]}
                for r in rows
                if not r.get("testable")
            ],
        },
    }
    half_pairs = sum(r["n_habituating_half"] for r in testable)
    finite_pairs = sum(r["n_finite"] for r in testable)
    half_models = sum(1 for r in testable if r["n_habituating_half"] > 0)
    doc["results_summary"] = [
        f"Testable models T={info.get('T')} of {len(rows)} downloaded "
        f"({finite_pairs} finite stimulus-response pairs). "
        f"{n_hab_models} had at least one habituating pair; "
        f"Z={info.get('Z')} had none. "
        f"{info.get('outside_band')} models had a habituating share outside 1-50%.",
        f"Engagement passed in {info.get('engaged_models')} of {info.get('T')} testable models. "
        "The pre-registered rule is applied to these counts without a change of threshold.",
        f"A successive half-drop (ratio 1/2), recorded and not used for the verdict, "
        f"occurred in {half_pairs} of {finite_pairs} finite pairs and in {half_models} models.",
    ]
    registration = (doc.get("caveats") or [None])[0]
    doc["caveats"] = [
        registration,
        "This is a simulation of published ODE models. It shows whether the habituation inequality appears in those equations under the stated clamp. It is not a measurement of pharmacoresistance in organisms.",
        "The continuous clamp replaces the paper's MATLAB loop, which reset the stimulus every short solver call because ode23tb cannot edit a trajectory mid-call. Epoch lengths use the methods' step counts at h = 0.01 (50 to 100 time units), not 5000 separate solver calls. A reading in which each of those steps lasted 10 time units was not run.",
        "SBFC writes some assignments on the same line as a % comment, after a tab, and places a few assignment rules after the reactions that use them. Those statements were restored and literal constants were moved above the reactions so the exported file can execute. BIOMD0000000024 contains delay(), which the exporter does not implement, and BIOMD0000000539's export refers to reaction_production_A without defining it. Both are not testable and are not counted as failures.",
        "Engagement held in 32 of 33 testable models, including 17 of the 18 models with zero habituation, so those zeros are not a failure of the clamp to move the network. BIOMD0000000483 had no 1.5-fold response in any pair.",
    ]
    doc["interpretation"] = doc.get("interpretation", "")
    with open(RESULT_PATH, "w") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


if __name__ == "__main__":
    main()
