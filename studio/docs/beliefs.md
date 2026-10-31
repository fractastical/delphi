# frontier.beliefs: decision-conditioned inference over exact finite factor graphs

`frontier/beliefs.py` composes declared evidence into a forecast for one declared decision. Pure Python
standard library, exact `Fraction` arithmetic, deterministic, about 560 lines.

## What it is not (read first)

* **Scientific calibration is UNKNOWN.** No output of this module has been compared with outcomes.
  Every result carries `metadata.calibration = "UNKNOWN: ..."`. The numbers are arithmetic consequences
  of the declared assumptions, not measured accuracy.
* **There is no truth score.** Output is "under these declared priors and factors, this event in this
  context has this probability, and this declared action has this expected value". Probabilities are
  indexed by an event and a context string the author wrote down.
* **Not causal.** Action `assumes` is conditioning. A `do` key is an unknown key and raises.
  (Same rule as the MorphoSwarm belief graph's refusal of do-queries.)
* **The bundled example is a declared illustration**, not data. Nothing in it was observed; no variant,
  assay or paper is referenced.

## Provenance of the design (concepts reused, no code copied)

Read on 2026-10-31 from `morphoswarm/src/morphoswarm/evidence/`: `belief/graph.py` (loop test by edge
counting, refuse a factor over an unknown variable, refuse do-queries), `belief/potentials.py` (every
factor has provenance; exact rational tables), `belief/priors.py` (a prior states its method; no default
prior), `belief/engines/exact.py` and `loopy.py` (exact variable elimination; a loopy approximation must
never come back looking converged), `belief/sensitivity.py` (leave-one-out, prior sweeps),
`belief/decide.py`, `overlap.py`, `decision_market.py` (decision-conditional forecasts, shared lineage).
This module is a small re-derivation, not a port. It does not implement MorphoSwarm's rubric
compilation, credal ranges, decibans, or VOI ranking. Ideas of this family also appear in published
recursive-Bayesian-claim-graph work; this module makes no novelty claim.

## Model

A scenario is JSON (`schema: "frontier-beliefs-0.1"`):

* `variables`: `id`, `event` (what is asked), `context` (declared scope), `states` (2..6 strings).
* `priors`: exactly one per variable, with a `method`: `declared` (table + source),
  `reference-class` (table + source + reference_class text) or `uniform-ignorance`
  (no numbers; says "no information", which is not evidence). A missing prior gives
  `unresolved-no-prior`; nothing is defaulted.
* `factors`: `scope` (1..4 variables), a complete `table` of rows `[state..., weight]` with weight >= 0,
  `source` (who or what supplied it) and `group` (evidence group). Weights are multiplicative potentials,
  so a unary factor is a likelihood ratio. Weight 0 is a hard zero.
* `decision`: `outcome` variable, `actions` (each may `assumes` fixed states of variables), `utility`
  per action per outcome state, `cost` per action (0 must be written). Value = expected utility - cost.
* `collapse` (optional): the declared rule for duplicate evidence, see below.
* Numbers are ints or strings (`"3/10"`); floats raise. `input_hash` is sha256 of the canonical JSON
  (same bytes as `frontier.models.canonical`, a test checks equality).

Posterior is prior x product of factors, normalised, by exact variable elimination (greedy min-cells
order). Tree or cyclic makes no difference to the solver; `structure.cyclic` reports it.

## Caps (explicit constants, `Caps` overrides them for tests)

| constant | value | refused with |
|---|---|---|
| `MAX_VARIABLES` | 20 | `refused-cap-exceeded` |
| `MAX_STATES` | 6 per variable | `refused-cap-exceeded` |
| `MAX_FACTORS` | 80 | `refused-cap-exceeded` |
| `MAX_FACTOR_SCOPE` | 4 variables | `refused-cap-exceeded` |
| `MAX_TABLE_CELLS` | 1296 rows | `refused-cap-exceeded` |
| `MAX_ACTIONS` | 8 | `refused-cap-exceeded` |
| `MAX_ELIM_CELLS` | 50,000 | `unsupported-cyclic-beyond-exact-cap` (or `unsupported-beyond-exact-cap` if acyclic) |

Input caps are checked on the raw input before any table is built. The elimination cap is checked
before an intermediate table is allocated. There is no fallback: no loopy BP, no sampling, no
truncation. With the elimination check disabled the dense-graph test did not finish within two minutes, which is what the cap prevents.
The cap values are engineering choices for a small adapter, not derived from any benchmark.

## Duplicate evidence paths

Detected before solving, always reported in `duplicate_paths`:

* `group`: two or more factors (or non-uniform priors) declare the same `group`.
* `source`: two or more entries share a `source` and, transitively, a variable.

Default is refusal: `refused-duplicate-evidence`, no posterior, with the sets named. The only way
through is a declared rule `collapse: {"group:NAME": "<id to keep>"}` (or `"source:NAME"`), which keeps
one member and drops the rest; drops are listed in `collapsed`. This discards information and does
not pool; it is conservative on purpose. A collapse rule that matches nothing raises. Dropping a prior
leaves the variable unresolved.

Limit: indirect routes (the same upstream source reaching a variable only through intermediate factors,
without sharing a variable or a declared group) are not detected. Authors must put dependent entries in
one group. Groups and sources are labels the author supplies; a wrong label defeats detection.

## Explicit non-answers

`status` is one of `ok`, `refused-cap-exceeded`, `refused-duplicate-evidence`, `unresolved-no-prior`,
`unsupported-cyclic-beyond-exact-cap`, `unsupported-beyond-exact-cap`, `contradiction`. Anything but
`ok` has no `variables` and no `decision` blocks. For `contradiction` (all joint states have weight 0)
the result lists factors with hard zeros and the entries whose removal restores support. In an `ok`
result, `ruled_out_states` lists states driven to 0 and `prior_only` marks variables no factor touches.
An action whose own assumptions contradict the evidence is `impossible-under-its-assumptions`.
Exact ties give `preferred: null` and `tied: [...]`. Malformed input raises `BeliefError`.

## Decision output and sensitivity

Per action: `forecast` (posterior of the outcome variable given the action's assumptions) and
`expected_value`; then `preferred`, `ev_margin_over_runner_up` and `preferred_changes_when`:

* `breakeven` (binary outcome, no action assumptions): the exact probability of the first state at
  which the preferred action ties with each alternative, with the direction of the flip.
* `variations`: re-decision after dropping each factor and after replacing each non-uniform prior with
  uniform-ignorance; `flipping_assumptions` lists those that change the preferred action.
* Only declared priors and factors are varied. Utilities, costs, table weights and anything unlisted are
  not perturbed; "no flip listed" is not robustness.

## Hand-worked controls and the replayable example

`tests/test_beliefs.py` has controls computed by hand in the comments with `Fraction`: two independent
LR factors (6/7); a two-variable chain (13/20, 3/4); a cyclic triangle (3/4, 17/28, also cross-checked by
a separately written brute-force enumeration); the example (P=3/5, EV 17/5, breakeven 5/14, only dropping
`e1` flips). Negative controls that must refuse: duplicate group, duplicate source, prior+evidence from one
source, cap exceeded (states, variables, scope), cyclic beyond cap (and the boundary cap passes),
12-variable dense graph under default caps, contradiction, missing prior, malformed or float input,
`do` keys, and a mutated factor table that changes the preferred action (so the example is not vacuous).
A mutation of the code that disables duplicate detection or contradiction handling makes tests fail.

Replay: `python -m frontier.beliefs [scenario.json]` prints the result; `solve(EXAMPLE_SCENARIO)` always
gives the same `input_hash` (`8a7f8372...`) and `output_hash`. The example hash is for the example as
committed; any edit changes it.

## Known limits

Exact but small; potentials, not a probabilistic program. No continuous variables. Calibration unknown.
Not wired into the store or MCP surface; callers pass a scenario dict.

## Consumer contract (from the independent review of 2b2ad18; binding for web and UI code)

1. **Rationals are exact `"p/q"` strings; parse them exactly.** `float("17/5")` throws, `float("0")`
   silently succeeds, so a consumer tested only on integral values ships and then breaks. Use
   Python `fractions.Fraction(s)` (`Fraction("17/5") == Fraction(17, 5)`) or, in JS, split on `/`
   and use `BigInt` (`const [n, d = "1"] = s.split("/"); BigInt(n)`, `BigInt(d)`), converting to a
   display decimal only at the last step. **Web consumers must parse "p/q" strings exactly.** The
   bundled example is deliberately non-integral (`"3/5"`, `"17/5"`, `"5/14"`); a consumer test that
   uses it fails on day one if it parses with `float`/`Number`. The site is asked to integrate this.
2. **`status == "ok"` does not mean every action is renderable.** An action whose own `assumes`
   contradict the evidence is the bare object `{"status": "impossible-under-its-assumptions"}` with no
   `expected_value` and no `forecast`, inside an otherwise `ok` response. Check each action's keys.
3. **The only guard is `status === "ok"`.** The vocabulary has no safe prefix (`contradiction`,
   `unresolved-no-prior` and `unsupported-*` do not start with `refused`). Vocabulary:
   `beliefs.STATUSES` = ok, refused-cap-exceeded, refused-duplicate-evidence, unresolved-no-prior,
   unsupported-cyclic-beyond-exact-cap, unsupported-beyond-exact-cap, contradiction. Every non-ok
   result omits `decision`, `variables` and `structure` (diagnostics, if any, move to `diagnostics`);
   a parametrised test pins this for every status, and fails if a status is added without a fixture.
   `metadata.calibration` (UNKNOWN), `input_hash`, `output_hash` and `reasons` are on every status.

## Web adapter: `frontier/beliefs_api.py`

`solve_scenario(dict)` and `parse_body(bytes)` for a website. Request: finite JSON, at most 32 KB
(`request_too_large`, 413), top-level keys only those of the scenario schema (no code, equations,
commands; nested validation is `frontier.beliefs`', and `do` is refused). The solve runs in a fresh
child of the same interpreter (`sys.executable -m frontier.beliefs_api --worker`), request on stdin,
canonical JSON on stdout, environment limited to PATH, OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1,
MKL_NUM_THREADS=1, PYTHONDONTWRITEBYTECODE=1, timeout 8 s, at most 2 concurrent slots (a third gets
`FrontierError` code `solver_busy`, HTTP 429). A timeout returns `{"status": "unknown", ...}` with no
result, never a posterior. A worker failure is the fixed `solver_unavailable` (503), no trace or
request echoed. A rejected scenario is `invalid_request` (400) with the validator's message (at most
300 characters, authored by `frontier.beliefs`, describing the caller's own input).
Every response, error bodies included (`error_body(exc)`), carries `calibrated: false` and
`assumed_scope`, the declared-assumption scope text. Success shape:
`{schema, status, calibrated, assumed_scope, result}` with `result` as above (the status is mirrored,
so the guard in item 3 applies to both). Not wired into `frontier/web.py`; that belongs to the web
owner. Limits: wall-clock timeout only (the memory and process bounds are the service unit's); the
timeout is the stdlib `subprocess` kill of the direct child, which spawns nothing.
