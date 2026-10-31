"""Stage runner executed with the ISOLATED BETSE venv's Python (BETSE 1.5.0 pinned in requirements-betse.txt), never with the project/system Python.

    <venv>/bin/python betse_stage.py <scenario> <workdir> [--template-dir DIR]

Scenarios (same seeded 2-D cell world and same init for all; only the targeted intervention differs):
  baseline      no intervention
  k_up          'change K mem': multiplier on the membrane K+ permeability (Dm_K) of the Spot tissue profile, t=1..3 s. This is a generic K+ permeability
                scale, NOT the Kir2.1 channel (Kir2.1 exists in BETSE's gene-regulatory-network channel library but is not used here).
  gj_block      'block gap junctions': 100 % of gap junctions blocked, t=1..3 s
  k_up_gj_block both events together: separates what stays in the Spot cells from what spreads through gap junctions
  baseline_dt   baseline with half the solver time step (numerical-sensitivity control)
Every process this starts is a child of the bounded scope the driver creates. One writer per workdir.
"""
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

STEP = 1e-3
TOTAL = 4.0
SAMPLE = 0.1
K_MULT = 5.0
EV_START, EV_END, EV_RATE = 1.0, 3.0, 0.5


def make_config(src: Path, dst: Path, scenario: str) -> None:
    from ruamel.yaml import YAML
    y = YAML(); y.preserve_quotes = True; y.width = 4096
    d = y.load(src.read_text())
    d["general options"]["simulate extracellular spaces"] = False          # infinite ideal bath; faster; no environmental ion depletion
    d["world options"]["world size"] = 80e-6
    d["init time settings"]["time step"] = 1e-2; d["init time settings"]["total time"] = 3.0; d["init time settings"]["sampling rate"] = 1.0
    d["sim time settings"]["time step"] = STEP / (2 if scenario == "baseline_dt" else 1)
    d["sim time settings"]["total time"] = TOTAL; d["sim time settings"]["sampling rate"] = SAMPLE
    d["general network"]["implement network"] = False                       # no gene-regulatory network / gating ligand: ion + pump + gap-junction physics only
    for k in ("change K mem", "block gap junctions"):
        d[k]["event happens"] = False
    if scenario in ("k_up", "k_up_gj_block"):
        e = d["change K mem"]; e.update({"event happens": True, "change start": EV_START, "change finish": EV_END, "change rate": EV_RATE, "multiplier": K_MULT})
    if scenario in ("gj_block", "k_up_gj_block"):
        e = d["block gap junctions"]; e.update({"event happens": True, "change start": EV_START, "change finish": EV_END, "change rate": EV_RATE, "random fraction": 100})
    ws = d["results options"]["while solving"]
    ws["animations"]["show"] = False; ws["animations"]["save"] = False      # we render our own animation from the saved trajectory
    y.dump(d, dst.open("w"))


def betse(cfg: Path, phase: str, cwd: Path) -> str:
    env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "MPLBACKEND": "Agg"}
    exe = Path(sys.executable).parent / "betse"
    r = subprocess.run([str(exe), phase, cfg.name], cwd=cwd, env=env, capture_output=True, text=True, timeout=500)
    if r.returncode != 0:
        raise SystemExit(f"betse {phase} failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


def extract(workdir: Path, out: Path, scenario: str, log: str) -> None:
    import dill
    with gzip.open(workdir / "SIMS" / "sim_1.betse.gz", "rb") as f:
        sim, cells, p = dill.load(f)
    t = np.array([float(x) for x in sim.time])
    arr = lambda L: np.array([np.asarray(x, dtype=float) for x in L])
    names = {int(sim.iNa): "Na", int(sim.iK): "K", int(sim.iM): "M", int(sim.iP): "P"}
    order = [names[i] for i in range(4)]
    cc = arr(sim.cc_time)                                        # (t, ion, cell) mol/m^3 == mmol/L
    tg = sim.dyna.cell_target_inds.get("Spot")               # cell indices of the 'Spot' tissue profile = the cells the K+ permeability event is applied to (apply to: [Spot])
    spot = np.asarray(tg, dtype=int) if tg is not None else None
    kmem = np.asarray(getattr(sim.dyna, "targets_Kmem", []), dtype=int)      # membrane indices BETSE actually modifies in the K+ event
    kmem_cells = np.unique(np.asarray(cells.mem_to_cells, dtype=int)[kmem]) if kmem.size else kmem
    if spot is not None and kmem_cells.size and not np.array_equal(np.sort(spot), kmem_cells):
        raise SystemExit(f"Spot profile cells {spot} do not equal the owners of the K+-event membranes {kmem_cells}")
    np.savez_compressed(out,
        scenario=scenario, time_s=t, vm_cell_V=arr(sim.vm_ave_time), vm_mem_V=arr(sim.vm_time), cc_mol_m3=cc, ion_order=np.array(order),
        cc_env_mol_m3=arr(sim.cc_env_time)[0].mean(axis=1), gj_open_fraction_mem=arr(sim.gjopen_time), rho_cell_C_m3=arr(sim.rho_cells_time),
        nak_rate=arr(sim.rate_NaKATP_time) if len(sim.rate_NaKATP_time) else np.zeros(0),
        cell_centres_m=np.asarray(cells.cell_centres, dtype=float), cell_vol_m3=np.asarray(cells.cell_vol, dtype=float), cell_sa_m2=np.asarray(cells.cell_sa, dtype=float),
        mem_sa_m2=np.asarray(cells.mem_sa, dtype=float), mem_to_cells=np.asarray(cells.mem_to_cells, dtype=int), z=np.asarray(sim.zs, dtype=float),
        cm_F_m2=float(p.cm), temperature_K=float(p.T), spot_cells=spot if spot is not None else np.zeros(0, dtype=int), has_spot=spot is not None,
        gj_nn=np.asarray(cells.nn_i, dtype=int) if hasattr(cells, "nn_i") else np.zeros(0, dtype=int),
        n_cells=int(cells.cell_number), n_mems=int(len(cells.mem_i)), dt_s=float(p.dt), betse_log_tail=log[-600:])


def main() -> None:
    scenario, work = sys.argv[1], Path(sys.argv[2]).resolve()
    tmpl = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 and sys.argv[3] == "--template-dir" else None
    only = "--extract-only" in sys.argv
    work.mkdir(parents=True, exist_ok=True)
    cfgdir = work / "cfg"
    if only:
        extract(cfgdir, work / f"{scenario}.npz", scenario, ""); print(json.dumps({"scenario": scenario, "extract_only": True})); return
    if tmpl is None:                          # first scenario: create the default BETSE config tree (betse requires a directory component), then seed + init once
        env = {**os.environ, "MPLBACKEND": "Agg"}
        subprocess.run([str(Path(sys.executable).parent / "betse"), "config", "cfg/default.yaml"], cwd=work, env=env, check=True, capture_output=True)
    else:
        shutil.copytree(tmpl / "cfg", cfgdir, ignore=shutil.ignore_patterns("SIMS", "RESULTS", "run.yaml"))
    cfg = cfgdir / "run.yaml"
    make_config(cfgdir / "default.yaml", cfg, scenario)
    if tmpl is None:
        betse(cfg, "seed", cfgdir); betse(cfg, "init", cfgdir)
    log = betse(cfg, "sim", cfgdir) if "--extract-only" not in sys.argv else ""
    extract(cfgdir, work / f"{scenario}.npz", scenario, log)
    print(json.dumps({"scenario": scenario, "ok": True}))


if __name__ == "__main__":
    main()
