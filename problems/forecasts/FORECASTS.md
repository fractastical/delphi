# Open-problem forecasts

Built by `node problems/forecasts/build/merge.mjs`; do not edit. Round **r1-2026-11-01** (2026-11-01, blind), 4 forecasters (claude-opus-5-5, gemini-4-argon, gpt-5-6-sol, grok-4-7), 12 slice files.

Probabilities are medians across forecasters with the range in brackets. "Solved" means the problem's acceptance criteria are met or a falsifier is hit definitively, by logged artifacts. Nothing counts unless run and logged (`runs.json`, Lean reports, `test-data/claim-tests/`). Definitions: [INSTRUCTIONS.md](INSTRUCTIONS.md).

## Problems

| Problem | Tier | Solved in 30 days | Δ | Solved in 365 days | Δ | Best approach (success = complete × settle) |
|---|---|---|---|---|---|---|
| hamiltons-rule-exact-scope | A | 56% (46%–75%) |  | 86% (81%–92%) |  | proof, 62% (claude-opus-5-5 #2) |
| morphogenesis-cognition-gene-overlap | C | 62% (55%–72%) |  | 84% (80%–90%) |  | data-test, 58% (grok-4-7 #1) |
| metabolic-scaling-exponent | B | 51% (31%–75%) |  | 82% (70%–92%) |  | computation, 62% (grok-4-7 #3) |
| limb-bone-scaling-vs-mechanical-similarity | B | 52% (25%–70%) |  | 74% (60%–88%) |  | formalization, 52% (grok-4-7 #2) |
| grn-memory-generic-or-biological | C | 46% (33%–62%) |  | 73% (62%–86%) |  | computation, 43% (claude-opus-5-5 #1) |
| clade-trajectory-universality | B | 45% (35%–55%) |  | 71% (65%–80%) |  | computation, 42% (grok-4-7 #2) |
| murrays-law-vascular-optimality | B | 42% (25%–60%) |  | 69% (60%–85%) |  | formalization, 64% (grok-4-7 #1) |
| mutant-morphant-discrepancy-prediction | C | 43% (30%–65%) |  | 69% (60%–85%) |  | data-test, 41% (claude-opus-5-5 #1) |
| species-area-exponent | B | 31% (25%–45%) |  | 61% (54%–75%) |  | computation, 40% (claude-opus-5-5 #2) |
| lewontins-paradox-of-variation | B | 27% (22%–65%) |  | 60% (50%–88%) |  | data-test, 47% (grok-4-7 #1) |
| biocomposite-toughness-from-hierarchy | B | 26% (7%–42%) |  | 54% (30%–70%) |  | formalization, 46% (claude-opus-5-5 #3) |
| somite-number-control | B | 29% (15%–45%) |  | 52% (40%–70%) |  | computation, 53% (grok-4-7 #2) |
| trabecular-stress-alignment-wolffs-law | B | 25% (7%–30%) |  | 52% (30%–60%) |  | formalization, 49% (grok-4-7 #3) |
| biomineral-form-physical-vs-biological-control | C | 25% (12%–41%) |  | 49% (35%–68%) |  | formalization, 55% (grok-4-7 #2) |
| turing-capable-network-topologies | A | 16% (8%–45%) |  | 48% (30%–80%) |  | formalization, 57% (grok-4-7 #1) |
| empty-shell-morphospace | B | 16% (4%–35%) |  | 41% (20%–65%) |  | formalization, 46% (grok-4-7 #1) |
| active-inference-morphogenesis-falsifiable | C | 18% (7%–45%) |  | 41% (22%–72%) |  | formalization, 37% (claude-opus-5-5 #1) |
| hollow-tube-mass-optimality | B | 17% (4%–35%) |  | 41% (20%–65%) |  | formalization, 47% (grok-4-7 #1) |
| hygromorph-bilayer-scaling | B | 16% (7%–38%) |  | 40% (25%–65%) |  | computation, 33% (grok-4-7 #2) |
| kelvin-problem-in-epithelia | C | 11% (5%–20%) |  | 32% (15%–40%) |  | data-test, 28% (claude-opus-5-5 #3) |
| bioelectric-prepattern-predicts-anatomy | C | 11% (5%–25%) |  | 27% (18%–52%) |  | formalization, 21% (grok-4-7 #3) |
| phyllotaxis-attractor-classification | A | 8% (5%–15%) |  | 25% (18%–45%) |  | simulation, 42% (grok-4-7 #3) |
| rule30-center-column | A | 8% (7%–10%) |  | 22% (18%–30%) |  | mixed, 29% (claude-opus-5-5 #3) |
| printed-stress-aligned-lattice-beats-uniform | B | 4% (2%–5%) |  | 17% (8%–25%) |  | computation, 38% (grok-4-7 #1) |
| rule110-universality-machine-checked | A | 4% (2%–8%) |  | 15% (12%–35%) |  | formalization, 26% (grok-4-7 #2) |
| rule54-universality | A | 2% (1%–4%) |  | 6% (3%–14%) |  | formalization, 34% (claude-opus-5-5 #3) |
| smallest-universal-turing-machine-2-3 | A | 2% (1%–2%) |  | 6% (3%–9%) |  | formalization, 17% (grok-4-7 #1) |

Expected problems solved (sum of medians): **6.9** of 27 in 30 days, **12.9** in 365 days.

## By method

Mean over approaches of each kind, using medians across forecasters.

| Kind | Approaches | Complete in 30 days | Settle if complete | Success | Best problem for this kind |
|---|---|---|---|---|---|
| data-test | 83 | 42% | 57% | 25% | morphogenesis-cognition-gene-overlap (58%) |
| computation | 44 | 50% | 54% | 27% | metabolic-scaling-exponent (62%) |
| formalization | 41 | 48% | 70% | 34% | murrays-law-vascular-optimality (64%) |
| simulation | 22 | 46% | 51% | 23% | phyllotaxis-attractor-classification (42%) |
| proof | 16 | 10% | 70% | 7% | hamiltons-rule-exact-scope (62%) |
| mixed | 13 | 25% | 61% | 14% | printed-stress-aligned-lattice-beats-uniform (37%) |

## Largest disagreements (365-day range)

- turing-capable-network-topologies: 30%–80%
- active-inference-morphogenesis-falsifiable: 22%–72%
- empty-shell-morphospace: 20%–65%
- hollow-tube-mass-optimality: 20%–65%
- hygromorph-bilayer-scaling: 25%–65%

## Calibration

No round has passed its 30-day horizon yet, so nothing is scored. Once one has, Brier scores per forecaster appear here (outcomes come only from `runs.json`).

