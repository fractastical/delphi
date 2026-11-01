# Plant hygromorph mechanics

Key quantitative claims about how plant tissues turn a humidity or turgor change into motion:
pine cone scales bending (Reyssat & Mahadevan 2009, after Timoshenko 1925 and Dawson, Vincent &
Rocca 1997), wheat awns and chiral seed pods twisting (Elbaum et al. 2007, Armon et al. 2011), the
Venus flytrap snapping (Forterre et al. 2005), and the compositional framing Marom, Tibbits, Zardini
& Buehler (2026) give to such multiscale hierarchies. Tracked in
[issue #65](https://github.com/fractastical/delphi/issues/65).

Why this source: each claim is a short mathematical statement with a recorded formal status, and
published measurements on organisms exist to test the central one. It is the first plant mechanics
in the claim graph, and it sits next to Thompson's mechanics claims (`thompson1917-ch01-05`,
`ch02-02`, `ch16-03`–`ch16-05`, `ch16-10`): same beam theory, inverse direction.

## Files

| Path | What |
|---|---|
| `CLAIMS.md` | The claims written out: statement, math, assumptions, formal status, Lean theorems, what is left to data, and the candidates for the next batch. |
| `claims/key-claims.json` | Five claims, same schema as `claim-sources/math-bio-claims/claims/key-claims.json`: `statement`, LaTeX `notation`, `context` ending in `Formal status: …`, `proposed_test`, paper DOI (checked against Crossref 2026-10-31). |
| `../thompson-growth-form/lean/ThompsonLaws/Hygromorphs.lean` and `…/lean/reports/Hygromorphs.json` | Lean 4 formalizations. They live in the Thompson Lake project because Lean reports are keyed by claim id across projects (`scripts/site/load-claims.mjs`) and a second Mathlib checkout is 7 GB. |
| `../../test-data/claim-tests/plant-hygromorph-mechanics/<claim-id>/` | Pre-registered tests against published measurements. |

No nanopubs have been built or published for this source yet; `claim-sources/math-bio-claims/build-nanopubs.mts`
is the template when that happens (new domain `plant-hygromorph-mechanics`).

## Claims

| id | Law | Formal status |
|---|---|---|
| `hygromorph-bilayer-curvature` | Timoshenko bilayer: \(\kappa = C(h, m, n)\,\Delta\varepsilon\) | proved (1925) |
| `hygromorph-response-time` | \(\tau \sim h^2/D\) | proved (diffusion time scale) |
| `hygromorph-antisymmetric-twist` | \(\pm\phi\) fibre layers give pure shear mismatch \((\varepsilon_L-\varepsilon_T)\sin 2\phi\), zero axial mismatch | proved (tensor algebra) |
| `flytrap-snap-geometry` | bistability iff \(\alpha = L^4\kappa^2/h^2 \gtrsim 0.8\) | partial (threshold numerical) |
| `stimulus-response-systems-category` | systems with simulation-preserving maps form a category | proved (Marom et al. 2026, App. A.2) |

A proof shows the law follows from its assumptions (linear elasticity, Fickian diffusion, a
tensor transformation); whether a pine cone scale satisfies them is what the data tests are for.
