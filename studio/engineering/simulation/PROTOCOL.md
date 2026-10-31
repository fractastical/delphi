# Glide simulation protocol (frozen before the sweep)

Owner: delphi-rethink-nca (Claude Sonnet 5.5), branch `work/nca-glide` of kganjam/delphi-frontier. Evidence kind: **simulated**. Not a biological-feasibility claim, no fin-tissue coupling, no genetic claim.

## Model
Point mass in a vertical plane, fixed commanded lift coefficient, RK4 (`glide.py` docstring has the equations). `CD = CD0 + CL^2/(pi e AR)`, `AR = b^2/S`. Standard flight-mechanics equations, verified by the controls below, **not** by a page-level re-read of a textbook in this session. Fish 1990 (13-page PDF, read) supplies allometry only: mass 0.003-0.53 kg (p.393), wing loading 11.7-208.9 N/m^2 (p.394; the lower bound belongs to a 0.001 kg specimen), pectoral-fin AR 3.0-16.9 (p.395; applied to the whole wing here as a flagged modelling choice), and "glide 1 m above the water" (introduction). Park & Choi 2010: PDF host unreachable from this machine; no Park/Choi coefficient is used. `CD0`, `e`, `CL_max` are **design assumptions** with declared prior ranges. No Euler-Bernoulli fin-stiffness model (no source read).

## Design grid (720 designs)
12 log-spaced masses in [0.003, 0.53] kg x 12 log-spaced wing loadings in [11.7, 208.9] N/m^2 (S = m g / WL, g = 9.80665) x aspect ratio {3, 5, 8, 12, 16.9}; b = sqrt(AR S).
Nominal assumptions: rho 1.225 kg/m^3 (ISA sea level, design assumption), CL_max 1.2, CD0 0.06, e 0.8, release height 1 m, release speed 1.5 V_stall (V_stall = sqrt(2 m g/(rho S CL_max))), release flight-path angle 0. Commanded CL = min(CL_max, sqrt(pi e AR CD0)).
Uncertainty: paired Monte Carlo, n = 200 draws shared by all designs, seed 20261031, uniform: CL_max [0.8, 1.6], CD0 [0.03, 0.12], e [0.6, 0.95] (ranges are mine, not measurements).

## Outcomes and Pareto set
Per design: nominal glide range and time, equilibrium L/D, sink rate, stall speed, MC quantiles (q10/q50/q90) of range, fraction stalled. Pareto set over (maximise q10 range, minimise equilibrium sink rate, minimise A* = S/m^(2/3)), exact pairwise non-domination among converged finite designs. Time series (x, h, V, gamma vs t) for three Pareto designs. "Selected dimensions" = {m, S, b, AR, WL} with units and receipt hash.

## Controls (must pass before the sweep result is reported; thresholds fixed now)
1 ballistic (no lift, no drag, level release): range = V0 sqrt(2 h0/g) within 1e-3. 2 energy: drag off, lift on: E = V^2/2 + g h drift <= 1e-4. 3 equilibrium start: range = h0/tan(-gamma_eq) within 1e-4. 4 dt-halving (dt 0.002 s vs 0.001 s): relative range difference <= 1e-4; designs above this are flagged `converged=false` and excluded from the Pareto set but kept in the table. 5 refusals (tests): missing/invalid inputs return a code, never a default.

## Stop / resource cap
CPU only, <= 2 threads, `systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=1800`; per-case caps: 120 s of flight time, stall floor 0.2 V_stall, non-finite => end_reason 3 (recorded, not dropped). Expected cost: seconds to a few minutes (vectorised RK4 over 720 nominal + 144,000 MC cases). **GPU not requested**; revisit only if the measured CPU time exceeds 2 h (via dx-gpuops, which alone submits).

## Requested dataset (for calibration, NOT needed for this baseline)
Measured CL/CD vs angle of attack for flying-fish-like bodies (Park & Choi 2010 tables; PDF unreachable), and per-species fin/body geometry (Fish 1990 Table III is in the PDF already read). Until such data are read, every coefficient stays a design assumption.
