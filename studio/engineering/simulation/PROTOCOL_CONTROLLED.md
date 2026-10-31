# Controlled comparison protocol (frozen before the run; the original sweep and its null are preserved unchanged in results/)

Authorized follow-up after the original sweep found that release at 1.5 x stall speed let wing loading choose the launch energy (zoom-climbing, tiny-mass Pareto boundary). **The original Pareto set is not a design recommendation and is not shipped as one.**

## What changes
* Every geometry in a scenario gets the SAME explicit release speed V0 and release height (1 m, level, gamma0 = 0). Release speeds: 12 m/s (design assumption), 16 and 20 m/s (Fish 1990 p.397 citing Shoulejkin et al.: taxi speed rise 10 -> 16-20 m/s; not a measured flight envelope).
* Constraint (level-flight proxy, labelled as such): V0 >= V_stall = sqrt(2 m g / (rho S CL_max)). Designs violating it are recorded as infeasible in that scenario and cannot win.
* Source envelope: a design must have wing loading inside the observed range of its genus (Fish Table II) to win; AR is NOT extrapolated: whole-wing AR = b^2/S is varied only +-20% around the genus baseline.
* Baselines are dataset-grounded: Fish 1990 Table I reduced-major-axis fits, wing span (m) and wing area (m^2) as functions of body mass for Cypselurus (Park & Choi's genus) and Exocoetus, with Fish's wing-area definition (pectoral + pelvic fins + intervening segments). Table I was inspected as an image (decimal points are missing in the print for some coefficients: 0651, 0039 read as 0.651, 0.039); each baseline's implied wing loading m g / S is cross-checked against the separate Table II fit (Cypselurus within 0.05-8.3%, Exocoetus 3.9-22%). Baselines whose implied wing loading lies outside the genus's observed Table II range are excluded and listed.
* Masses 0.05, 0.1, 0.2, 0.4 kg.

## Design family and scenarios
S = f_S x S_baseline, f_S in {0.7, 0.85, 1, 1.15, 1.3}; AR = f_AR x AR_baseline, f_AR in {0.8, 0.9, 1, 1.1, 1.2}; b = sqrt(AR S); mass fixed at the baseline mass (25 designs per baseline, one is the baseline).
Polars (both are ASSUMPTIONS; neither is a measured fish polar): P1 CL_max 1.2, CD0 0.06, e 0.8; P2 CL_max 1.03, CD0 0.25, e 0.8, informed by a SECONDARY source (Deng et al. 2019 numerical study of a Cypselurus hiraii pectoral-fin model: max CL 1.03, max L/D 4.7; seen at search-snippet level only; not Park & Choi data). Commanded CL = min(CL_max, sqrt(pi e AR CD0)); rho 1.225 kg/m^3; RK4 dt 0.002 s with dt/2 control (relative range difference <= 1e-4 else unconverged and excluded from wins).
Scenarios = 3 release speeds x 2 polars.

## Outcome
Per design and scenario: glide range from the release (m) and equilibrium sink rate (m/s) as ratios to the genus/mass baseline in the SAME scenario. WIN = feasible, inside envelope, converged, range ratio >= 1.02 and sink ratio <= 0.98. ROBUST WIN = wins in every scenario where the baseline is itself feasible. Reported: counts of any-win, robust-win, flips between scenarios, designs that are infeasible or outside envelope somewhere. No Pareto ranking, no recommendation.

## Solver-witness check (guilds)
A real witness from dx-guilds' engineering/constraints.py (z3-solver 5.3.3.0 in an isolated venv; their `solve` and independent `verify_certificate`) with rho 1.225, CL 6/5, opt-ins on, query V <= 12 m/s is simulated with this package and compared with the Fish genus fit at the witness mass (area, AR, wing loading).

## Calibration status
**No calibrated aerodynamic claim.** Park & Choi 2010 (DOI 10.1242/jeb.046052): publisher returns 403 (bot challenge); the author PDF host's TLS certificate has expired (I did not bypass certificate checks); IUTAM 2007 proceedings host refuses connections; Europe PMC / orx paper return the abstract only. A sourced polar is therefore unavailable; the polars above stay design assumptions and every receipt says so. If a sourced polar is read later it replaces P1/P2 and this protocol is re-run as a new, labelled revision.
