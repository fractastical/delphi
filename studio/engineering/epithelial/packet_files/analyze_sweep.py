"""Score the J-scaling sweep against a criterion declared in this file and hashed into the output.

Repair R6 after infra source review of packet 4f33453. The criterion below is fixed here, in
source, and this file's own sha256 is written into every report, so a report can be checked
against the criterion that produced it. There is no flag that changes a threshold.

The rule under test, derived from the CPM energy and never fitted:
    Phi = lambda_V * A_gap^2 / (N * J * P_gap)  =>  the closure threshold lambda* is
    proportional to J. So lambda*/J must be constant across J at a fixed gap.

Verdicts are three-valued. UNRESOLVED is NOT a pass:
    PASS        every gap size resolved a bracket at every J, and max(lambda*/J)/min(lambda*/J)
                <= TOLERANCE_RATIO within that gap size.
    FAIL        all resolved, and the ratio exceeds TOLERANCE_RATIO somewhere.
    UNRESOLVED  any (gap, seed, J) cell failed to bracket inside the swept lambda_V range.
                An unresolved cell is reported by id and is never dropped to let the
                remaining cells satisfy the rule.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

# ---- the declared criterion. Changing any of these changes CRITERION_SHA256. ----------------
TOLERANCE_RATIO = 2.0          # max/min of lambda*/J within one gap size
TOTAL_NODES = 40000
MIN_SAMPLED_TIMES = 2
ARM_RE = re.compile(r"^S-k(?P<k>\d+)-J(?P<J>[\d.]+)-lamV(?P<lam>[\d.]+)-s(?P<seed>\d+)$")


def criterion_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def arm_state(d: Path) -> tuple[str, dict]:
    """CLOSED / ARRESTED / UNUSABLE, from the logger alone."""
    log = d / "logger.csv"
    if not log.exists():
        return "UNUSABLE", {"why": "logger.csv missing"}
    rows = list(csv.DictReader(log.read_text().splitlines(), delimiter="\t"))
    if not rows:
        return "UNUSABLE", {"why": "no data rows"}
    by = defaultdict(float)
    for r in rows:
        try:
            by[float(r["time"])] += float(r["cell.volume"])
        except (KeyError, TypeError, ValueError):
            return "UNUSABLE", {"why": "unparseable logger field"}
    ts = sorted(by)
    if len(ts) < MIN_SAMPLED_TIMES:
        return "UNUSABLE", {"why": f"only {len(ts)} sampled time(s)"}
    gaps = {t: TOTAL_NODES - by[t] for t in ts}
    if not all(math.isfinite(v) for v in gaps.values()):
        return "UNUSABLE", {"why": "non-finite gap"}
    closed = any(gaps[t] <= 0 for t in ts)
    return ("CLOSED" if closed else "ARRESTED"), {"gap0": gaps[ts[0]], "gap_end": gaps[ts[-1]]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    declared = json.loads(Path(a.arms).read_text())
    root = Path(a.out)

    cells = defaultdict(dict)       # (k, seed, J) -> {lambda_V: state}
    unusable = {}
    for spec in declared:
        m = ARM_RE.match(spec["name"])
        if not m:
            continue
        st, info = arm_state(root / spec["name"])
        if st == "UNUSABLE":
            unusable[spec["name"]] = info["why"]
            continue
        key = (int(m["k"]), int(m["seed"]), float(m["J"]))
        cells[key][float(m["lam"])] = st

    resolved, unresolved = {}, {}
    for key, lam in cells.items():
        cl = [v for v, s in lam.items() if s == "CLOSED"]
        ar = [v for v, s in lam.items() if s == "ARRESTED"]
        label = f"k{key[0]}-s{key[1]}-J{key[2]:g}"
        if cl and ar and max(cl) < min(ar):
            resolved[label] = dict(k=key[0], seed=key[1], J=key[2], bracket=[max(cl), min(ar)],
                                   lambda_star=math.sqrt(max(cl) * min(ar)),
                                   ratio=math.sqrt(max(cl) * min(ar)) / key[2])
        else:
            unresolved[label] = ("no bracket: closes at every swept lambda_V" if not ar else
                                 "no bracket: arrests at every swept lambda_V" if not cl else
                                 "closed and arrested interleave; threshold not monotone in lambda_V")

    per_gap = {}
    for k in sorted({v["k"] for v in resolved.values()}):
        rs = [v["ratio"] for v in resolved.values() if v["k"] == k]
        if rs:
            per_gap[k] = dict(n=len(rs), min=min(rs), max=max(rs), spread=max(rs) / min(rs),
                              within_tolerance=(max(rs) / min(rs)) <= TOLERANCE_RATIO)

    if unusable or unresolved or not per_gap:
        verdict = "UNRESOLVED"
    elif all(v["within_tolerance"] for v in per_gap.values()):
        verdict = "PASS"
    else:
        verdict = "FAIL"

    report = dict(schema="frontier.epithelial-jscaling.v1",
                  criterion=dict(tolerance_ratio=TOLERANCE_RATIO,
                                 statement="lambda*/J constant within TOLERANCE_RATIO at each gap size; "
                                           "any unresolved cell makes the whole verdict UNRESOLVED",
                                 source_file=Path(__file__).name,
                                 criterion_sha256=criterion_sha256()),
                  verdict=verdict, per_gap=per_gap, resolved=resolved,
                  unresolved=unresolved, unusable_arms=unusable,
                  counts=dict(cells=len(cells), resolved=len(resolved),
                              unresolved=len(unresolved), unusable=len(unusable)))
    Path(a.report).write_text(json.dumps(report, indent=1, default=float))
    print(f"verdict {verdict}: {len(resolved)} resolved, {len(unresolved)} unresolved, "
          f"{len(unusable)} unusable")
    for k, v in per_gap.items():
        print(f"  k={k}: lambda*/J in [{v['min']:.4g}, {v['max']:.4g}], spread {v['spread']:.3f} "
              f"(tolerance {TOLERANCE_RATIO})")
    for lab, why in list(unresolved.items())[:10]:
        print(f"  UNRESOLVED {lab}: {why}")
    raise SystemExit({"PASS": 0, "FAIL": 1, "UNRESOLVED": 2}[verdict])


if __name__ == "__main__":
    main()
