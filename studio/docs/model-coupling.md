# Model coupling: typed ports, explicit contracts, refusal instead of invention

Files: `engineering/coupling.py` (stdlib only), `tests/test_coupling.py`, `tests/test_coupling_formal.py`,
`engineering/formal/UnitAlgebra*.lean`, generated `engineering/COUPLING_MANIFEST.json` and
`engineering/model_interfaces/*.json`. Author: dx-guilds. Not Codex-reviewed.

## What this is and is not
A *coupling layer* decides whether the **output port of one model may feed the input port of another**, and says
`composable`, `scenario` or `refused`. It does not solve constraints (that is `engineering/constraints.py`), does not
simulate, and does not claim two models describe the same organism. **No real calibration is registered today**, so
every cross-scale or cross-context bridge is refused or labelled assumption-level, and a Problem is proposed instead.

| verdict | meaning | may it run? |
|---|---|---|
| `composable` | typed identity, exact unit conversion, or a structurally complete **calibration record**; dimension, scope, time, uncertainty all pass | yes |
| `scenario` | runnable only as an **assumption-level** scenario (named assumptions, unknown bounds/time scale/uncertainty, extrapolation) | yes, labelled; never evidence about an organism |
| `refused` | a bridge is missing or inconsistent (no mapping, non-dimensional model fed to an SI port, scope mismatch with no bridging calibration, proposed endpoint, dimension mismatch, concurrent coupling) | no |

## Model interface JSON (`frontier.model.interface/1`) — defined now, root integrates
Strict parser: `model_from_json` rejects unknown keys, wrong schema, floats, bad enums. Fields:

```
{ "schema": "frontier.model.interface/1",
  "model_id": str, "name": str, "engine": str,
  "status": "implemented_replayed" | "implemented" | "proposed",
  "reference": {"repo","branch","commit","path","read_by"} | null,     // required unless status == "proposed"
  "ports": [ { "name": str, "direction": "in" | "out", "quantity": str,
               "kind": "dimensional" | "dimensionless" | "model_units",
               "unit": str,
               "dim": {"kg": int, "m": int, "s": int} | null,           // non-zero if dimensional; all zero if dimensionless; null if model_units
               "scale": "molecular|cell|tissue|organ|organism|environment",
               "regime": str, "context": str,                           // organism / taxon / design envelope; never empty
               "provenance": {"source": str, "status": "measured|fitted|assumed|simulated|unknown", "read_level": "full-text|data|abstract|file|none"},
               "bounds": null | {"lo": decimal-string|null, "hi": decimal-string|null, "source": str, "status": ...} } ],
  "timescale": {"kind": "static" | "seconds" | "unknown", "seconds": decimal-string|null, "source": str},
  "run": {"entrypoint": str|null, "deterministic": bool|null, ...},     // free-form; root fills the runner
  "scope": str, "not_established": [str] }
```
`model_units` means **non-dimensional as stored, no SI meaning** (e.g. the Collier two-cell file declares no units). A
`model_units` port can never be identity-mapped or unit-converted to an SI port.

## Coupling contract (`frontier.coupling.contract/1`, Python `Coupling`)
`from` (an `out` port) → `to` (an `in` port) with explicit edges:
* **mapping**: `identity` (same quantity), `unit_conversion` (positive exact factor, same quantity, dimensionless factor),
  `calibrated` (a registered `Calibration`), `assumed` (≥1 named assumption; explicit factor if units differ), `none`.
* **time**: `static_input` (source has no dynamics), `quasi_static` (source time scale ≥ 10× target; the 10 is a declared
  design parameter, printed in the manifest), `concurrent` (**refused**: not supported), `unknown` (downgrades to scenario).
* **uncertainty**: `exact` (arithmetic only), `calibration_relative_bound`, `declared_interval` (scenario only), `unknown` (scenario).
* **assumptions**: ids from the registry; any assumption edge makes the verdict at best `scenario`.
* **scope**: scale, context and regime must be equal, or a calibration must declare that exact bridge. Otherwise `refused`
  (`assumed` mappings may cross scope only as a `scenario`, and a missing-calibration entry is recorded).
* **bounds**: mapped source range must sit inside the target's declared bounds; a calibration's domain must contain the
  source range. Unknown bounds downgrade a value-transforming mapping to `scenario` (identity and exact unit conversion add no extrapolation).

A **Calibration** is a *structural* record: `measured|fitted_to_measured`, source read at `full-text|data` level, 64-hex data
hash, closed domain, factor > 0 with its dimension, relative uncertainty, ≥ 2 points, and the scale/context it bridges. The
layer cannot verify the data say this; reviewers must.

## Registered models (`default_registry()`; from the owners' hand-off notes in `messages/`, code not re-read here)
| id | what | status | reference |
|---|---|---|---|
| `flying_fish_constraints` | exact-rational mass/area/span/speed solver | implemented | `work/guilds-engineering` `engineering/constraints.py` |
| `glide_pointmass` | point-mass RK4 glide simulation (priors, not measurements) | implemented | `work/nca-glide` @ `4dee158` |
| `rdfield_nonlinear_sweep` | Schnakenberg/Brusselator 1-D zero-flux field sweep | implemented | `kganjam/delphi-evolve` `work/rethink-nca` @ `0234681` |
| `collier1996_two_cell` | BIOMD0000001047 lateral inhibition, libRoadRunner 2.10.0, non-dimensional | implemented_replayed | `work/biomodels` @ `c41188dd2b47` |
| `finbeam_euler_bernoulli` | **proposed** fin beam; nothing exists | proposed | none |

## Current verdicts (`engineering/COUPLING_MANIFEST.json`, schema `frontier.coupling.manifest/1`)
3 composable, 1 scenario, 4 refused.
* `c01–c03` constraint witness `m, S, b` → glide inputs: **composable** — same quantity, unit, scale, context and regime;
  the source is a static design point. This says the *interface* matches; it does **not** say the witness is a viable fish
  (the constraint model is a level-flight proxy, L = W).
* `c04` witness `V` → glide `release_speed`: **scenario** — the glide model defaults to 1.5 × stall speed; using `V` is assumption `A1`.
* `c05/c06` Collier Notch/Delta → fin stiffness: **refused** — no mapping exists, the model is non-dimensional, cell vs organ scale,
  taxon vs fish context, and the fin-beam model is only proposed. Even naming assumption `A2` cannot make a proposed model run.
* `c07` reaction-diffusion mode number → wing span: **refused** — a dimensionless mode number has no length scale in metres.
* `c08` fin deflection → glide speed: **refused** — needs camber → CL/CD; the only candidate source (Park & Choi 2010 tables) has not been read.

## Problem proposals (`frontier.problem.proposal/1`)
One per non-composable coupling, `status: proposed`, `not_a_claim: true`, with `success`, `falsifier` and `action_bounds`
(CPU-only ≤ 2 h cap, no GPU, no paid calls, bounded named searches, stop rule, forbidden actions). **No threshold is invented**:
the success text says the held-out fraction and bound are frozen *before* the fit.

## Lean (optional, scoped)
`engineering/formal/UnitAlgebra.lean` proves only the arithmetic the validator relies on: conversion composes, positive
factors keep values positive, a nonzero factor is undone by its inverse, an interval maps to `[lo·f, hi·f]` for `f > 0`
(positivity is necessary: Lean-proved counterexample), and dimension exponents add. Controls: four mutated statements
(`x·f·g = x·(f+g)`, interval map without positivity, inverse without nonzero, subtracted exponents) are each rejected inside
their own block. Receipt: `engineering/formal/UNIT_ALGEBRA_RECEIPT.json` (compiler output, hashes, toolchain, Mathlib rev).
**Lean proves nothing about biological correspondence, calibrations, or whether any two models describe the same system.**

## Integration (root)
```
from engineering.coupling import default_registry, default_couplings, build_manifest, validate_coupling, model_from_json, model_to_json
reg = default_registry();  reg.add_model(model_from_json(json.load(...)))      # register an interface file
manifest = build_manifest(reg, couplings)                                        # deterministic; self-hashed
```
Never present a `scenario` result without its label; never say "the models are coupled" for anything but a `composable`
edge, and then only as "interface-compatible". `manifest["must_display"]` / `["must_not_say"]` are the wording constraints.
Regenerate: `python -m engineering.coupling engineering`. A test fails if the committed manifest is stale.

## Limits
Port details were taken from other workers' hand-off notes, not from their code. No calibration exists. Time scales are
mostly undeclared. `scale`/`context`/`regime` are free-text equality checks, not an ontology. The Collier parameters'
provenance is unknown (paper not read). Not Codex-reviewed.
