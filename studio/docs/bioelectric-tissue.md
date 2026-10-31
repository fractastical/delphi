# Bioelectric tissue slice: ions, pumps and gap junctions on a 2-D cell patch (BETSE 1.5.0)

**Status: SIMULATED, single-reader work (Claude Sonnet 5.5, market worker), not independently reviewed.** Generic 2-D patch with BETSE default parameters. Not measured, not calibrated, **not a fish fin**; fin tissue applicability is an explicit **unknown**. No wet-lab design is made.

## What this adds beyond `engineering/bioelectric/`
The existing slice is an independent NumPy Hodgkin–Huxley membrane with an assumed 12-cell chain and *fixed* ion reservoirs (no concentrations, no pumps). This slice runs the **official BETSE package** (betsee/betse, PyPI `betse==1.5.0`, wheel sha256 `17a11601255e6570cff866fda8d3eb1b9852dcd921cf1dd6c42b6ea834c8945a`, Python 3.12 venv outside the repo, pins in `engineering/bioelectric_tissue/requirements-betse.txt`) on a hexagonal 2-D patch: dynamic Na+/K+/anion concentrations, an electrogenic Na/K-ATPase, electrodiffusion across the membrane, and voltage-gated gap-junction coupling between cells. We do not copy BETSE code (it is GPL-licensed); we call it and read its saved state.

## What was run (all numbers in `artifacts/bioelectric-tissue/summary.json`)
World: 80 µm square, hexagonal lattice with BETSE's default disorder, **66 cells**, **364 membranes**, cell radius 5 µm and height 10 µm, T = 310 K, "basic" ion profile (extracellular Na 145, K 5, anion 140, protein 10 mmol/L), BETSE default membrane diffusion constants (Dm_Na 2e-18, Dm_K 1e-18, Dm_M 1e-18, Dm_P 0 m²/s), gap-junction surface fraction 5e-8 with voltage gating (threshold 15 mV, minimum 0.10). Extracellular spaces are off (ideal infinite bath), the gene-regulatory network is off. Init 3 s, then 4 s of simulation at 1 ms steps, sampled every 0.1 s (39 samples). One seeded world and one init are shared by all scenarios, so a difference from baseline is the intervention.

| scenario | change from baseline (config in `configs/`) |
|---|---|
| baseline | none |
| k_up | K+ membrane permeability ×5 in the 2 cells of the `Spot` tissue profile, ramped over t = 1 to 3 s. A generic K+ permeability scale, **not the Kir2.1 channel** |
| gj_block | all gap junctions blocked (BETSE's ramp starts before t = 1 s; see the right-hand plot) |
| k_up_gj_block | both |
| baseline_dt | baseline at half the solver time step (numerical-sensitivity control) |

## Results (simulated; effect = difference from the baseline run)
* Resting Vm of this default configuration is about −23.5 mV (all cells nearly equal). This is a property of BETSE defaults, not a calibrated epithelium. A leak-only GHK reference with the same concentrations and permeabilities gives +0.7 mV; the 24 mV difference is **not decomposed** here (pump and coupling contributions are not isolated).
* k_up: Vm of the two targeted cells falls by at most 4.67 mV (peak at t ≈ 2.8 s) and cells that were not targeted by up to 2.62 mV: the change spreads through gap junctions.
* k_up_gj_block: the targeted cells fall by up to 19.8 mV and the others change by 0.16 mV at most. Blocking the junctions confines the effect to the cells that were changed.
* gj_block alone: the mean open fraction drops from 0.967 to about 1e-11 and Vm changes by at most 0.16 mV, because a homogeneous patch has almost no voltage differences for the junctions to equalise.
* After the window the K control leaves at most 0.41 mV of residual change at t ≥ 3.5 s.

## Checks (all in `summary.json`; thresholds are check criteria, not statistics)
1. finite values, positive concentrations, −150 < Vm < 50 mV: pass.
2. charge consistency: ρ = F Σ z c within 3.4e-6 (relative) and Vm = ρV/(C_m A) within 3.2e-16. BETSE defines Vm this way, so this confirms the saved fields agree; it is not independent validation.
3. mass: total impermeant protein is conserved to a relative range of 0 in every scenario. Na, K and anion exchange with the ideal bath by design, so their totals are not conserved and no closed budget exists for them here.
4. time step: halving the solver step changes Vm by at most 3.8e-5 mV (4.7e-5 of the K-control peak) and concentrations by 1.4e-7 relative.
5. direction and reversal of the K control, 6. gap-junction block control, 7. the expectation that blocking junctions reduces the effect seen by untargeted cells: all met. The last is an expectation, and a miss would have been reported as a result.
Test coverage: `tests/test_bioelectric_tissue.py` recomputes every committed check from the committed trajectories, hand-works the charge and GHK formulas, and has must-fail controls for each check.

## Mathematical interface (see `artifacts/bioelectric-tissue/model_interface.json`)
Outputs: Vm (per cell and membrane), cytosolic ion concentrations, gap-junction open fraction, cell centres/volumes/areas. Inputs used: K-permeability multiplier, gap-junction block, cell size. **Gap conductance in siemens and channel conductance are UNKNOWN**: BETSE uses a junction surface fraction and membrane diffusion constants, and no conversion is made here. **Growth coupling is an assumption/open question** with no sourced mapping.

## Kcnj13 candidate link (source link only)
Zebrafish Kcnj13 (UniProt Q0KIZ7 / NCBI BAF03613.1) is listed in `model_interface.json` as an **unparameterized, unverified channel candidate; conductance and gating are unknown**. The hosted OpenFold2 monomer (provider confidence 52.86, pTM 0.273, no membrane, tetramer or ligand; see `artifacts/bio-services/kcnj13_openfold2/bioelectric_handoff.md` on the integration branch) is a weak structural hypothesis and was **not** used to set or calibrate any BETSE parameter. The K+ permeability scale in `k_up` is a generic control, unrelated to Kcnj13. The RefSeq NP_001429136.1 source discrepancy stays open.

## Limits
Not a fin, not zebrafish or any measured tissue; T = 310 K is the BETSE default (a fish fin is not at 37 °C). No ion depletion in the environment, no flow, no deformation, no gene regulation, no Kir2.1 or other gene-regulatory-network channels. One seed, one patch size, one intervention strength: no sensitivity sweep. BETSE itself has no independent re-implementation here, and not every BETSE equation was re-derived. The video is a rendering of saved samples (one frame per sample, 5 fps), not a separate computation.

## Reproduce
```
python3.12 -m venv <venv> && <venv>/bin/pip install -r engineering/bioelectric_tissue/requirements-betse.txt
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
  python3 -m engineering.bioelectric_tissue.run --betse-python <venv>/bin/python --work <scratch dir>
```
Observed wall time of the five BETSE runs on this host: about 1 to 2 minutes each, two at a time. Outputs: `artifacts/bioelectric-tissue/{summary.json,bioelectric_tissue.mp4,poster.png,trajectories/*.npz,configs/*.yaml,model_interface.json}`.
