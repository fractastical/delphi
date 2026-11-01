# Fittest

[Fittest MCP](https://fittest-mcp.westus2.cloudapp.azure.com/) ([source](https://github.com/Pavel-Tk/fittest))
routes molecular structures between three ML interatomic potentials (MACE-MPA-0, AIMNet2, Orb-v3)
and DFT. Per structure it returns the model to serve, a Beta-posterior trust score with a 90%
interval and the number of DFT labels behind it, and `send_to_dft` with reasons. It is calibrated on
gas-phase C/H/N/O reaction chemistry (Transition1x, at most 7 heavy atoms) and warns outside it.
Configured as `fittest` in `.cursor/mcp.json`. Tracking issue:
[#57](https://github.com/fractastical/delphi/issues/57).

Two scripts, standard library plus numpy:

- `pilot.py` sends PubChem 3D conformers to the hosted server and writes `pilot-results.json`.
- `route.py` applies the same trust-or-escalate design to our assessor truth scores and writes
  `routing-results.json`.

Neither tests a claim or writes to claim files, assessments or nanopubs.

## Pilot: enantiomers and broken bonds (`pilot.py`)

Context claim `thompson1917-ch09-03` (one-handed molecular asymmetry may start from circularly
polarised light). Fittest cannot test it: the claim is about an external chiral field, which no
interatomic potential models. The pilot checks the premise a computational test would rely on, that
an isolated molecule and its mirror image get the same energy. Run 2026-10-31 on L-alanine,
L-lactic acid and D-glyceraldehyde, each with its exact mirror image, a random rotation and the
first C–O bond stretched 1.4×, 1.7× and 2×, plus (S)-2-chloropropanoic acid.

- MACE-MPA-0 and AIMNet2 give the mirror image exactly the same energy. Orb-v3 differs by 1–6 meV,
  about as much as it differs under a plain rotation (3–5 meV); it is not exactly equivariant. The
  served model (AIMNet2) is exact, and verdicts never changed under mirroring or rotation.
- Unstretched molecules: `trust`, score 0.86 (90% interval 0.61–0.99), 4 DFT labels.
- Stretched bonds are trusted longer than they should be. At 1.4× all three are trusted at 0.60
  (interval 0.25–0.90, 2 labels). At 2× alanine is still trusted at 0.67 (interval 0.34–0.92,
  3 labels), while lactic acid at 2× and glyceraldehyde at 1.7× escalate (0.28, 22 labels). The rule
  checks the posterior mean, so a sparse bucket passes on a handful of labels. Requiring the 5th
  percentile to reach 0.5, or a minimum label count, would have escalated all of these.
- The chlorine molecule gets `trust` with a domain warning that the score is an extrapolation.

The only drug named in the Levin claims, monensin (C36H62O11, 109 atoms), exceeds the 100-atom limit.

## Routing assessor truth scores (`route.py`)

Each claim in `docs/claims.json` has two truth scores (GPT-5.6 Sol, Grok 4.7). The committee
disagreement is |p_a − p_b|; τ is its 70th percentile (0.15), as in Fittest. Claims fall into four
buckets (agree/disagree × confident/uncertain, where confident means the mean is at least 0.2 from
0.5), and a Beta ledger records how often each candidate (either assessor or their mean) is on the
right side of 0.5. Labels are the 99 decisive data tests in `test-data/claim-tests/` (78 supports,
21 refutes). Lean and literature proofs are reported separately but do not calibrate the ledger: a
proof shows the formal statement follows from its assumptions, while the truth scores judge whether
organisms behave that way, and three proved Thompson claims are ones both assessors judged false.

Leave-one-out on the 99 data tests:

| | Trusted | Flagged | Assessor errors caught | Silent failures | Accuracy when trusted |
|---|---|---|---|---|---|
| Report the mean score for every claim | 99 | 0 | 0 of 17 | 17 | 0.83 |
| Route (either rule) | 77 | 22 | 12 of 17 | 5 | 0.935 |

The point-estimate rule and the 5th-percentile rule agree here, since every bucket either has
enough labels or sits clearly below 0.5. The ledger says only one bucket deserves trust: both
assessors confident and agreeing (92% correct, 77 labels). When they agree but are unsure, they
are right 30–40% of the time (8 labels). The five silent failures are claims where both assessors
were confidently wrong, which disagreement-based routing cannot catch: `darwin1859-ch11-16`,
`thompson1917-ch11-06`, `wolfram2002-ch09-24`, `wolfram2002-ch12-23`, `wolfram2002-ch12-41`
(the last two have test confidence below 0.5).

Applied to the 1,091 claims without a decisive test, the router flags 598 (55%): 100 of 219 Darwin,
197 of 308 Levin, 156 of 269 Thompson, 142 of 274 Wolfram, 3 of 21 math-bio. That is more than the
test budget, so `exec_queue` in `routing-results.json` is sorted by assessor disagreement and then
testability. The labels are not a random sample (builders chose claims they could test, and 79%
support the claim), so the ledger should be refit as tests accumulate.
