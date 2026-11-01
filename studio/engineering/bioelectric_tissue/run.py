"""Driver (project Python, no BETSE import): run the five BETSE scenarios in the isolated venv, then checks and the animation.

    systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
        python3 -m engineering.bioelectric_tissue.run --betse-python <venv>/bin/python --work <dir> [--skip-sim]

All BETSE children inherit the caller's scope and are given one thread. Raw trajectories (npz) go to --work; the compact, committed outputs go to artifacts/bioelectric-tissue/.
"""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENARIOS = ["baseline", "k_up", "gj_block", "k_up_gj_block", "baseline_dt"]


def stage(py: str, scenario: str, work: Path, template: Path | None) -> None:
    cmd = [py, str(HERE / "betse_stage.py"), scenario, str(work / scenario)] + (["--template-dir", str(template)] if template else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=540, env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MPLBACKEND": "Agg", "HOME": str(work)})
    (work / f"{scenario}.log").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        raise SystemExit(f"stage {scenario} failed; see {work / (scenario + '.log')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--betse-python", required=True); ap.add_argument("--work", required=True); ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--out", default=str(HERE.parents[1] / "artifacts" / "bioelectric-tissue"))
    a = ap.parse_args()
    work = Path(a.work).resolve(); work.mkdir(parents=True, exist_ok=True)
    if not a.skip_sim:
        stage(a.betse_python, "baseline", work, None)                       # seeds and inits once; every other scenario copies that world and init
        with ThreadPoolExecutor(2) as ex:                                    # two at a time: the scope already bounds memory/tasks; threads per process = 1
            list(ex.map(lambda s: stage(a.betse_python, s, work, work / "baseline"), SCENARIOS[1:]))
    from engineering.bioelectric_tissue import analysis, render
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = analysis.run(work, out, a.betse_python)
    render.render(work, out, res)
    print("checks:", {k: v["ok"] for k, v in res["checks"].items()})


if __name__ == "__main__":
    main()
