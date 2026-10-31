# Vendored pinned sources (read-only copies; do not edit)

| What | Origin | Pin |
|---|---|---|
| `scopedesk/oracles/{pde,kinetics,linear}.py`, `nonlinear_sweep/{ensemble,solvers,run}.py`, `nonlinear_sweep/PREREG.md` | delphi-evolve worktree `rethink-nca` (author `delphi-rethink-nca`) | commit `cb27cf2` (PREREG committed before any scored cell) |
| `compute_ops/*` (batch.py updated: 40 KiB chunks, no __pycache__), `pde_oracle/*` | delphi-evolve branch `work/gpuops` (author dx-gpuops) | commit `f7e92c740b119a83e9cc12118da714b33f2d67ff` |

Licence: Apache-2.0, copied unchanged as `LICENSE` and `NOTICE` (the NOTICE of the origin repository: original work for the ScienceClaw 2026 hackathon; third-party data and papers are NOT relicensed).
`scopedesk/__init__.py` is an empty file I created (the origin commit has none, the package is used as a namespace).
`pde_oracle` is used only for its reaction terms (`reaction`); its periodic FFT solver is not used here because the frozen protocol uses Neumann ends.

File sha256 (first 16 hex shown; full values recomputable with `sha256sum`), as of freeze 2:

| file | sha256 |
|---|---|
| `LICENSE` | `31e96d04f17a8212…` |
| `NOTICE` | `d7308cd898555fb7…` |
| `compute_ops/__init__.py` | `91dc31a215d069c6…` |
| `compute_ops/batch.py` | `442f52c6eef6320b…` |
| `compute_ops/cops_run.py` | `5ea507e9d792f34c…` |
| `pde_oracle/__init__.py` | `10ddcdbb3a4c1c96…` |
| `pde_oracle/solver.py` | `44466ec43697c8c4…` |
| `scopedesk/__init__.py` | `e3b0c44298fc1c14…` |
| `scopedesk/oracles/__init__.py` | `30ffd3c94ac95aef…` |
| `scopedesk/oracles/kinetics.py` | `3136ee99f6c0d2fd…` |
| `scopedesk/oracles/linear.py` | `fe5d18245db045f3…` |
| `scopedesk/oracles/nonlinear_sweep/PREREG.md` | `0d338a94c61a98be…` |
| `scopedesk/oracles/nonlinear_sweep/__init__.py` | `e3b0c44298fc1c14…` |
| `scopedesk/oracles/nonlinear_sweep/ensemble.py` | `59edef582295f646…` |
| `scopedesk/oracles/nonlinear_sweep/run.py` | `29644bcbd94c5ef7…` |
| `scopedesk/oracles/nonlinear_sweep/solvers.py` | `5f68e73b5345099a…` |
| `scopedesk/oracles/pde.py` | `30932c876c2e1981…` |
