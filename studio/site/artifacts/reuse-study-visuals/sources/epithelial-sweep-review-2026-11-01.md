# Independent review of the returned epithelial sweep

Reviewed owner09 **3c65c17f93ccb22d13bde0b5a05a6c840a8c963b**, including
`engineering/epithelial/audit_return.py`, the frozen analyzer/packet at
**e2f74f2a8d9fe2edf4d2dae0d6bcd1abf739a22b**, `sweep-audit.json`, card §10 and native return.
Reviewer branch is based at root **795f1405e9ebea4554d3c7e4d62b924742aab2ad**.
This is a same-fleet independent calculation on the same simulated data, not an independent
biological replication. No cloud physics or solver execution was repeated.

**Decision:** the frozen, fixed-horizon **FAIL is correctly reported and interval-supported**.
Its public summary can be exposed with the qualifications below. The new late-window prose
needs correction before being copied verbatim: it mistakes seed means for every run and
misstates an individual-arm denominator. That error does not change the frozen verdict.

## Checks actually executed

- [x] Rehashed all **971 returned files / 97,404,808 bytes** against the collection receipt;
  all sizes and digests match. Manifest digest:
  `39f32c4d97c86aecab6e1dd02b3147cca8d029652ba2380adf99a10d06e116f7`.
- [x] Compared **240 native model XMLs** to the exact frozen packet; all byte-identical.
  All 240 exit receipts are zero. Each model has StopTime 1000 and MCSDuration 1.
- [x] Independently streamed **1,442,280 logger rows**: finite time/volume, 101 sample times
  0,10,…,1000 per arm, constant cell-ID count, nonnegative integer gap, initial gap 625k.
- [x] Recomputed all **30** `(gap,seed,J)` brackets from eight tested λ values; every bracket
  matches the native report. All cells are resolved, none discarded.
- [x] Matched the native criterion digest to the analyzer inside the preregistered packet:
  `5df249c404fc51b9de865cd3481ff4a67e70989a2b04962bcd759eca6b9e887f`;
  tolerance is still **2**, native summary spreads still **8 / 16**, verdict still FAIL.
- [x] Independently computed the tight interval-spread lower bound using exact rational
  arithmetic and constructed an attaining value in every interval, rather than relying on
  geometric bracket midpoints. Ran only returned-data postprocessing under 1 CPU, 2 GiB,
  128-task bounds; Ruff and diff checks passed.

Reproducible reviewer code and complete per-arm readback:
[`review.py`](../../artifacts/audits/epithelial-sweep/review.py),
[`review.json`](../../artifacts/audits/epithelial-sweep/review.json).
The JSON pins exact owner source/card/audit bytes and the returned file identity chain.

## Why the interval result supports this FAIL

For each sampled operational threshold bracket, write `[li,ui] = [λclosed/J, λnonclosed/J]`.
Let `L=max(li)` and `U=min(ui)`. The smallest possible ratio of largest to smallest chosen
value is `max(1,L/U)`: the extrema force this lower bound, and clipping choices into
`[U,L]` attains it when `L>U`. Closed interval endpoints are deliberately favorable here;
using an open endpoint cannot reduce this lower bound.

| Gap k | L | U | Minimum feasible spread | Frozen tolerance |
|---|---|---|---|---|
| 4 | 2/175 | 1/350 | **4** | 2 |
| 7 | 1/175 | 1/1400 | **8** | 2 |

The failure is not solely an artifact of pooling seeds: separate-seed minimum spreads are
4,4,4 for k=4 and 8,4,4 for k=7, all above 2. These are model-repeat diagnostics, not a
population confidence interval or biological failure probability.

The reported endpoint bounds also reproduce: J=35→560 gives λ-factor intervals [1,4]
and [0.5,4], equivalent to endpoint secant log-slopes [0,0.5] and [−0.25,0.5]. These are
bracket-derived endpoint bounds over these declared scenarios, **not measured biological
exponents, confidence intervals, or proof of a global power law**. The regression slopes
0.300/0.133 are geometric-summary regressions and must remain labelled that way.

A finite sampled monotone response ladder brackets an operational threshold only under
that threshold interpretation; it does not establish monotonicity at every untested λ or
an asymptotic transition in a stochastic CPM. The native criterion tests its explicitly
chosen summaries; the interval analysis is additional, post hoc support, not a replacement
acceptance criterion.

## Concrete remaining wording defect at 3c65c17

`audit_return.py` groups late-window gap deltas across nonclosed seeds at each λ and reports
**mean** delta. Card/handoff prose instead says every high-J arm was flat or reopening.
That universal claim is false. Direct `gap(800)-gap(1000)` counterexamples:

| Arm | Gap shrinkage, nodes |
|---|---|
| k4, J560, λ12.8, seed3 | **+22** (group mean +1) |
| k7, J560, λ6.4, seed2 | **+3** (group mean −10.333) |
| k7, J560, λ12.8, seed2 | **+8** (group mean −8.333) |

For k4 the true individual-arm counts with delta >1 are **9/15** at J35 and **1/12** at
J560, not “3 of 5 arms versus 0 of 4”. The first fraction was reduced; the second hides
an individual closing run behind its seed mean. The two k7 λ levels 0.4 and 0.8 are also
not “two arms”: one nonclosed run at 0.4 and three at 0.8 have positive deltas. It is safe
to describe correctly labelled across-seed means, or to show these individual values.
The >1-node diagnostic is post hoc and is not a frozen trend/plateau test.

A durable precise correction was sent through root/infra in
`messages/epithelial-sweep-independent-review.md`. No criterion change, raw-result rewrite
or rerun is requested.

## Safe current-page conclusions and remaining unknowns

**Safe to expose:** 240/240 completed model runs; frozen criterion FAIL; fixed-horizon
summary spreads 8/16 and separately labelled minimum feasible spreads 4/8 versus tolerance 2;
exact sampled threshold brackets over J35–560, k4/k7, three seeds. State **closure observed
at logged times by StopTime 1000**, not permanent arrest. Local G9 remains a passing,
low-discrimination single-doubling bracket test: the larger-range failure limits the proposed
J-law without changing that historical local result. The gap-size law remains unsupported /
untested by this J-scaling assay; do not restore the withdrawn local midpoint refutation.

**Still unknown:** long-horizon closure and threshold, behavior between untested parameter
values, spatial/numerical refinement of this new assay, physical time/rate, tissue-specific
parameters, any cell-line/species validation, viability or clinical repair. Late-window
plateaus and reopening cannot bound a stochastic process's future. The Φ hypothesis is not
a reliable control surface over the tested fixed-horizon range; this is not a theorem that
no useful control surface or fit can ever exist.

**Media:** zero TIFF/lattice frames were returned. The loggers do contain cell-center x/y
coordinates and scalar volume/surface summaries; those are not cell shapes or wound-boundary
frames. A labelled center-track diagnostic would be possible, but logs cannot justify an
invented tissue-boundary movie. Existing spatial movies are the earlier local 36-arm runs,
not this sweep. Keep that distinction on the page and beside any media.
