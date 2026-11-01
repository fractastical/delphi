# Conditional oxygen diffusion rule

This bundle reuses one steady, constant-consumption oxygen model in two
secondary candidate project drafts. The statements are model implications; the
projects have no context-specific oxygen parameters or measurements attached.

## Rule

- Spherical source form: `Ccenter = C0 - a R^2/(6 D)` and
  `Ccenter >= 0 ↔ a R^2 <= 6 D C0`.
- Derived one-dimensional slab analogue: `Ccenter = C0 - a L^2/(2 D)` and
  `Ccenter >= 0 ↔ a L^2 <= 2 D C0`. `L` is half-thickness from a symmetry/no-flux
  center to one supplied face; for two-sided supply, total thickness is `2 L`.

The sphere coefficient is printed in Grimes et al. 2014, Eq. 2.6, in boundary
partial-pressure form. The paper's pressure-to-content variable is converted by
`C0 = p0/Omega`. The source study concerns DLD1 human colorectal tumor spheroids;
its fitted parameters are not transferred. The slab expression is derived from
`D C'' = a` and its stated ideal boundary conditions; it is not attributed to
Grimes.

## Reuse scopes

- `project-tissue-microcarrier`: proposed spherical geometry screen. `D`, `a`,
  `C0`, cell/material context and empirical limits remain unknown. This does not
  establish cell viability, actuation, deformation or motion.
- `project-epithelial-repair`: proposed one-sided slab thickness screen. Supply
  face, cell type/state and all parameters remain unknown. This does not predict
  gap closure, barrier recovery or treatment outcome.

Both draft refs are pinned in `rule-contract.json`; no live Project import or
stored-project write is claimed. A future context-matched oxygen measurement
could calibrate or refute this transport approximation. No such data is attached.

## Evidence and replay

- `lean-receipt.json`: actual Lean 4.35.0 compile, six parametric/boundary
  theorems, standard axiom lists, and both corrupted-coefficient controls
  rejected. The negative-control file first compiles parametric twins using the
  correct rule, then Lean cannot prove the same threshold for either mutated
  law and rejects an exact rational counterexample for each. The receipt checks
  that only those four marked mutant steps emit diagnostics.
- `numerical-checks.json`: 22 checks against the repository's existing sphere
  and slab profile/limit helpers with a dimensionless arithmetic fixture,
  including below/equal/above limits and boundary/zero-size values. No measured
  parameter is used.
- `geometry-control.png`: idealized geometry and normalized center-response
  curves, visibly labelled as a transport screen rather than a viability result.
- `source-provenance.json`: DOI/PMCID, exact equation-image URLs and SHA-256,
  the pressure-to-content mapping and the original tumor parameter context.
- `artifact-manifest.json`: exact file hashes for the rule, receipts, figure,
  source files and both separately pinned candidate draft refs.

Replay in the checked Mathlib project (toolchain/Mathlib revisions are recorded
in the receipt):

```bash
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
  python scripts/validate_oxygen_diffusion_lean.py
python -m engineering.lifecycle.oxygen_rule_validation
python scripts/render_oxygen_diffusion_rule.py
```

The Lean validator's final exit 0 means the positive source compiled without
`sorryAx` and the two named coefficient mutants were rejected. The expected
nonzero Lean result is captured inside the validator as a passing negative
control; it is not an accepted model result.
