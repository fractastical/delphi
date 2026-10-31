"""python -m attention {view|rank|ledger|score-events|evaluate|trace-gate}  (read-only; writes only with --out)"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import experiment, forecast, rank, traces, view


def _load(p):
    return json.loads(Path(p).read_text())


def _records(path):
    d = _load(path)
    return d["records"] if isinstance(d, dict) and "records" in d else d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="attention")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("view"); v.add_argument("--records", required=True); v.add_argument("--events"); v.add_argument("--annotations", nargs="*", default=[]); v.add_argument("--now"); v.add_argument("--out")
    s = sub.add_parser("score-events"); [s.add_argument(f"--{a}", required=True) for a in ("specs", "forecasts", "resolutions", "now")]
    e = sub.add_parser("evaluate"); e.add_argument("--rows", required=True); e.add_argument("--frozen", required=True); e.add_argument("--arms", required=True)
    g = sub.add_parser("trace-gate"); g.add_argument("--commons-runs", required=True); g.add_argument("--out")
    a = ap.parse_args(argv)
    if a.cmd == "view":
        now = a.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        out = view.build_view(_records(a.records), _load(a.events) if a.events else [], [_load(p) for p in a.annotations], now)
        out["rankings"] = rank.all_baselines(out["rows"])
    elif a.cmd == "score-events":
        out = forecast.score_events(_load(a.specs), _load(a.forecasts), _load(a.resolutions), a.now)
    elif a.cmd == "evaluate":
        out = experiment.evaluate(_load(a.rows), _load(a.frozen), a.arms.split(","))
    else:
        rows = traces.commons_rows(a.commons_runs)
        out = experiment.trace_gate(rows)
    text = json.dumps(out, indent=1, sort_keys=True, default=str)
    if getattr(a, "out", None):
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0 if out.get("verdict") != "REFUSED" else 2


if __name__ == "__main__":
    sys.exit(main())
