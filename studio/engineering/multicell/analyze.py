"""Summarise Morpheus arm outputs: cell count, division times, feedback coupling, movie."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path


def load(arm: Path) -> dict:
    rows = list(csv.reader((arm / "logger.csv").open(), delimiter="\t"))
    hdr = [h.strip('"') for h in rows[0]]
    recs = [dict(zip(hdr, map(float, r))) for r in rows[1:] if len(r) == len(hdr)]
    by_t = defaultdict(list)
    for r in recs:
        by_t[r["t"]].append(r)
    times = sorted(by_t)
    reached = times[-1]
    count = {t: len(by_t[t]) for t in times}
    first_seen = {}
    for t in times:
        for r in by_t[t]:
            first_seen.setdefault(int(r["cell.id"]), t)
    divisions = sorted({t for t in first_seen.values() if t > 0})  # both daughters get new ids at one time
    return {"reached_t": reached, "n_final": count[reached], "division_event_times": divisions,
            "cell_count": {t: count[t] for t in times}, "recs": by_t,
            "max_g_l": max(r["g_l"] for r in recs), "max_cdk1": max(r["CDK1"] for r in recs)}


def count_at(a: dict, t: float) -> int:
    ts = [x for x in a["cell_count"] if x <= t]
    return a["cell_count"][max(ts)]


def movie(arm: Path, out: Path) -> int:
    frames = sorted(arm.glob("plot_*.png"))
    frames = [f for f in frames if f.stat().st_size > 0][:-1] if frames else []
    if not frames:
        return 0
    lst = arm / "frames.txt"
    lst.write_text("".join(f"file '{f.resolve()}'\nduration 0.25\n" for f in frames))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", "format=yuv420p", str(out)], check=True)
    return len(frames)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    arms = {p.name: load(p) for p in sorted(Path(a.arms).iterdir()) if (p / "logger.csv").exists()}
    horizon = min(v["reached_t"] for v in arms.values())
    summary = {"common_horizon_t": horizon, "arms": {}}
    for name, v in arms.items():
        summary["arms"][name] = {
            "reached_t": v["reached_t"], "cells_at_common_horizon": count_at(v, horizon),
            "cells_at_end": v["n_final"],
            "division_event_times_to_horizon": [t for t in v["division_event_times"] if t <= horizon],
            "max_g_l": v["max_g_l"], "max_cdk1": v["max_cdk1"],
            "manifest": json.loads((Path(a.arms) / name / "manifest.json").read_text())}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in arms:
        summary["arms"][name]["movie_frames"] = movie(Path(a.arms) / name, out / f"{name}.mp4")
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "arms"}),
          {n: (s["cells_at_common_horizon"], s["division_event_times_to_horizon"]) for n, s in summary["arms"].items()})


if __name__ == "__main__":
    main()
