"""Decide whether a sweep run is complete. This script's exit status IS the run's result.

Repair R3 after infra source review of packet 4f33453. Previously `run_one` ended in `rm`,
so its status was the remove's, and xargs could exit 0 with every scientific invocation
failed. Nothing in the runner now decides success; this does, and it fails loudly.

A run is COMPLETE only if every declared arm id is present, exited 0, and produced a logger
with the required fields, at least two sampled times, and finite values throughout.
Zero successful arms is never complete, even if the arm list were somehow empty.
Failures are preserved and listed by id; none is dropped, and none is repaired here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

REQUIRED_FIELDS = ("time", "cell.id", "cell.center.x", "cell.center.y", "cell.volume", "cell.surface")


def check_arm(d: Path) -> dict:
    r = {"present": d.is_dir(), "exit": None, "rows": 0, "times": 0,
         "fields_ok": False, "finite": False, "logger_sha256": None, "problems": []}
    if not r["present"]:
        r["problems"].append("directory missing")
        return r
    ex = d / "exit.txt"
    if not ex.exists():
        r["problems"].append("exit.txt missing (arm did not finish)")
    else:
        try:
            r["exit"] = int(ex.read_text().strip().split("=", 1)[1])
        except Exception:
            r["problems"].append(f"exit.txt unparseable: {ex.read_text()[:40]!r}")
        if r["exit"] not in (0, None):
            r["problems"].append(f"solver exit {r['exit']}"
                                 + (" (timeout)" if r["exit"] in (124, 137) else ""))
    log = d / "logger.csv"
    if not log.exists():
        r["problems"].append("logger.csv missing")
        return r
    raw = log.read_bytes()
    r["logger_sha256"] = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode().splitlines(), delimiter="\t"))
    r["rows"] = len(rows)
    if not rows:
        r["problems"].append("logger.csv has no data rows")
        return r
    missing = [f for f in REQUIRED_FIELDS if f not in rows[0]]
    r["fields_ok"] = not missing
    if missing:
        r["problems"].append(f"logger missing fields {missing}")
    vals, bad = 0, 0
    times = set()
    for row in rows:
        for f in REQUIRED_FIELDS:
            if f not in row or row[f] is None:
                bad += 1
                continue
            try:
                v = float(row[f])
            except (TypeError, ValueError):
                bad += 1
                continue
            vals += 1
            if not math.isfinite(v):
                bad += 1
        if "time" in row:
            try:
                times.add(float(row["time"]))
            except (TypeError, ValueError):
                pass
    r["times"] = len(times)
    r["finite"] = bad == 0 and vals > 0
    if bad:
        r["problems"].append(f"{bad} non-finite or unparseable values")
    if r["times"] < 2:
        r["problems"].append(f"only {r['times']} sampled time(s); a trajectory needs at least 2")
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--job-wrapper-exit", type=int, default=0)
    a = ap.parse_args()
    declared = [x["name"] for x in json.loads(Path(a.arms).read_text())]
    out = Path(a.out)

    per = {n: check_arm(out / n) for n in declared}
    good = [n for n, r in per.items() if not r["problems"]]
    bad = {n: r["problems"] for n, r in per.items() if r["problems"]}
    extra = sorted(p.name for p in out.iterdir() if p.is_dir() and p.name not in per)

    complete = len(good) == len(declared) and len(declared) > 0 and len(good) > 0
    report = {
        "schema": "frontier.epithelial-sweep-completeness.v1",
        "declared_arms": len(declared), "complete_arms": len(good), "failed_arms": len(bad),
        "complete": complete,
        "job_wrapper_exit": a.job_wrapper_exit,
        "job_wrapper_exit_note": "recorded only. The runner's wrapper status never decides "
                                 "completeness; this report does.",
        "unexpected_directories": extra,
        "failures": bad,
        "per_arm": per,
        "manifest_sha256": hashlib.sha256(
            json.dumps({n: per[n]["logger_sha256"] for n in declared}, sort_keys=True).encode()).hexdigest(),
    }
    Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"complete {len(good)}/{len(declared)} arms; {len(bad)} failed; complete={complete}")
    for n in sorted(bad)[:20]:
        print(f"  FAILED {n}: {'; '.join(bad[n])}")
    if len(bad) > 20:
        print(f"  ... and {len(bad) - 20} more, all listed in {a.report}")
    raise SystemExit(0 if complete else 1)


if __name__ == "__main__":
    main()
