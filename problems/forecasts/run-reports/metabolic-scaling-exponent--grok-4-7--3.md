# Finite-generation networks and the approach to 3/4

Approach `metabolic-scaling-exponent--grok-4-7--3`, a computation. It settles one algebraic piece of `metabolic-scaling-exponent` and does not settle the problem. The empirical question — whether basal metabolism has one exponent, and whether that exponent is 3/4 or 2/3 or varies by taxon, temperature and size — stays open.

Pre-registered before the run at `test-data/claim-tests/thompson-growth-form/thompson1917-ch03-07/overnight-metabolic-network/result.json`. That claim is the cube law (`weightOfLength` in `ThompsonLaws/Magnitude.lean`). The same module has the surface-to-mass law. It has no infinite-generation branching theorem. `thompson1917-ch02-01` and `thompson1917-ch03-10` were not the objects of the script.

Primary network, as written: branching ratio 2, generations 2 to 24, area-preserving radii, fixed terminal units, service volume equal to the sum of the terminal service volumes, metabolic rate equal to total terminal flow. Both the flow and that sum are exactly `2^G`. All 22 successive local exponents are exactly 1, deviation exactly 1/4 from 3/4. The ordinary-least-squares slope on those generations is 1. The pre-registered criterion fails. Area preservation and the length ratio never enter this exponent.

The method's name for the primary volume and its name for the critique's service-volume assumption are the same invariant-terminal sum (Kozłowski and Konarzewski 2004). The volume the 3/4 derivation sets proportional to mass is total tube volume. That series was reported and was not allowed to meet the pass rule. Its local exponent is within 0.01 of 3/4 from generation 13 (0.7414) and is 0.7493 at generation 24. The straight-line slope on generations 2 to 24 is 0.7326, below 3/4, as a finite-size fit of a curve that approaches 3/4 from below. Full series: `derived/summary.json`.

Claim-level verdict: `inconclusive` (`other`), confidence 0.99. The arithmetic is exact and says nothing about real animals. It does not support or refute the cube law. The failure signature of the approach is met for the volume the method names: that finite network does not realize 3/4, so the volume definition and the 3/4 claim are not both right.

This does not meet the problem's acceptance criteria. No phylogenetically controlled metabolic analysis was run, and no Lean derivation was added.
