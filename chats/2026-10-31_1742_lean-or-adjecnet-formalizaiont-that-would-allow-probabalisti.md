# lean or adjecnet formalizaiont that would allow probabalistic extensions that wo

- **Started:** 2026-10-31 17:42 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 17:46 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `e7a6120f-520c-4ea6-8bdf-1f288b1b7854`

## Conversation

### 2026-10-31 17:42 — Turn 1 (User)

> lean or adjecnet formalizaiont that would allow probabalistic extensions that would extend into bio/morphology

**Assistant:**

I'll look at what Lean formalization already exists in the repo first, so the answer is grounded in it.

This is more of a question to think through than a coding task, so I want to ground my answer in what's actually in the repo—checking the existing Lean formalizations (thompson-growth-form, darwin-origin) and seeing what probabilistic machinery Mathlib already offers that could extend toward bio/morphology.

I'm thinking about where current proofs stand: the existing work is deterministic real analysis in Mathlib, with "expected genus size" being an exponential despite the probabilistic-sounding name. So I'm considering natural ways to extend this into true probability using Mathlib's PMF and related probability constructs.

Beyond that, I'm mapping what's available versus missing — measure-theoretic probability tools like independence, strong law of large numbers, martingales, Markov kernels, and Gaussian measures exist, but branching processes, diffusion limits, and SDE/Itô calculus largely don't, though Brownian motion construction is a recent addition. I'm also noting that Tao's PFR project brought entropy and information theory into Lean, which could be another relevant direction.

I'm turning to actual probabilistic programming systems in Lean, like SampCert for verified differential privacy and discrete sampling, and considering SciLean for differentiable numerics though it lacks probability support. I'm also comparing to Isabelle/HOL, which has a much more mature probability library including Markov models and information theory work by Hölzl.

I'm scanning the AFP entries for related formalizations — concentration inequalities, expander graphs, randomized data structures like treaps and skip lists — noting that mean-field and population process formalizations seem rarer. Then I'm checking Coq's offerings: ALEA, Infotheo for information theory, and the MathComp-Analysis measure theory library which now supports Lebesgue integration and some probability.

I also note Coq frameworks for probabilistic separation logic like Polaris, Clutch, Eris, and Tachis, plus probabilistic program logics such as pGCL, Ellora, EasyCrypt, and Kaminski's weakest preexpectation calculus — these could prove bounds on expected outcomes relevant to stochastic developmental models like pattern-formation timing. I distinguish these from unformalized probabilistic programming languages like Stan or Turing.jl, and I'm now thinking about differential-equation formalizations, starting with Isabelle's HOL-ODE library and its Lorenz attractor work, and wondering what Lean offers here.

I'm checking whether Lean's Mathlib has existence results for ODEs via Picard–Lindelöf, noting SDEs seem entirely absent. Then I shift to category-theoretic approaches — Fritz's Markov categories for synthetic probability — and realize the real formalized building block already in Mathlib is the Giry monad, implemented through measure bind/join and probability kernels, which gives exactly the right abstraction for modeling morphogenesis as a stochastic process on shape space.

Turning to morphology specifically, I note Thompson's work is deterministic geometry, so a probabilistic extension would involve random tessellations like Poisson–Voronoi models and empirical regularities such as Lewis's law and the Aboav–Weaire law, though Mathlib lacks Voronoi diagrams or point process machinery despite having Poisson distributions. For Darwin's claims, branching processes like Galton–Watson or Yule birth-death processes seem like the natural way to formalize genus survival and extinction dynamics.

My first target would be proving that expected population size grows exponentially, recovering the deterministic theorem as a special case, then extending to lineage extinction probabilities, Wright–Fisher drift for variation claims, and the Kingman coalescent for tree-likeness in descent — turning that into a theorem about random genealogies rather than an assumption. For Levin's claims, I'm thinking bioelectric switching as bistable Markov chains, with competency framed as expected error-correction using pGCL-style bounds, and for Wolfram's NKS, probabilistic cellular automata — though again Mathlib offers nothing here to build on.

Given the repo's constraint of zero-sorry proofs on Mathlib, finite PCAs can be treated as finite Markov chains using PMF or Kernel structures over boolean-valued grids. The practical path is to stay entirely within discrete, finite-or-countable state spaces where Mathlib's proof automation is strong enough to close without sorry — using PMF.bind, PMF.map, and expectations as sums or integrals, reserving continuous measure-theoretic tools only where discrete models won't suffice.

Branching process extinction isn't in Mathlib, so I'd need to prove the generating-function fixed-point argument myself — a reasonable medium-sized target since it's just convex analysis on [0,1] — and I should check whether Mathlib's martingale theory covers the Galton-Watson martingale Z_n/m^n. There's also a hybrid option worth noting: using model checkers like PRISM or Storm for probabilistic CTL on finite Markov models as a weaker-trust "adjacent formalization" path, separate from actual Lean theorems in the repo's sense.

I should verify what's actually available by checking if .lake is built and grepping for things like Kernel, strong_law, BrownianMotion, Martingale, and poisson to make sure my answer about Mathlib coverage is accurate rather than speculative.

Short answer: stay in Lean 4 + Mathlib. The Mathlib you already have pinned (v4.35.0, in `darwin-origin/formalization/lean/.lake`) carries enough measure-theoretic probability to do stochastic extensions of the existing claims without a new toolchain, and the repo's rule "theorem = compiled, no `sorry`, standard axioms only" is easiest to keep if the probabilistic layer lives in the same projects. The alternatives are worth knowing about, but mostly as sources of proof strategies to port.

## Where the current proofs sit

Everything in `DarwinLaws/*.lean` and `ThompsonLaws/*.lean` is deterministic real analysis: `ℝ`, `Filter.Tendsto`, `Finset` sums, one `IntervalIntegrable` in `Spirals.lean`. The stochastic content is hidden in names, e.g.:

```81:81:claim-sources/darwin-origin/formalization/lean/DarwinLaws/Tree.lean
noncomputable def expectedGenusSize (n₀ lam t : ℝ) : ℝ := n₀ * Real.exp (lam * t)
```

"Expected" is a label here; nothing is a random variable. That is the obvious seam: make the process random and recover the current theorem as a corollary about its mean.

## What the pinned Mathlib already provides

Checked against the vendored copy:

- Foundations: `MeasureTheory.Measure` with `bind`/`join` (the Giry monad), `ProbabilityTheory.Kernel` with composition (`Kernel/Composition/*`), disintegration, invariant measures and irreducibility (`Kernel/Invariance.lean`, `Kernel/Irreducible.lean`, thin: 4 theorems), and a Markov-category view (`Kernel/Category/Stoch.lean`, `SFinKer.lean`).
- Discrete: `PMF` with `bind`/`map`, Bernoulli, binomial, geometric, Poisson (including the Poisson limit theorem).
- Limit theory: strong law (`StrongLaw.lean`), CLT (`CentralLimitTheorem.lean`), Borel–Cantelli, sub-Gaussian concentration (`Moments/SubGaussian.lean`), Cramér–Wold.
- Processes: filtrations, adapted/predictable, stopping and hitting times, martingales with optional stopping and Doob upcrossings, Ionescu-Tulcea (infinite trajectories from a sequence of kernels: exactly what a discrete-time stochastic growth model needs), Kolmogorov extension, and a Brownian motion construction (`BrownianMotion/Basic.lean`, via Kolmogorov–Chentsov).
- Statistics/decision: Bayes estimators and risk (`Decision/`), posteriors (`Kernel/Posterior.lean`), conditional expectation and variance.

Not present (grep for them returns nothing): branching processes, Wright–Fisher/Moran, coalescent, continuous-time Markov chains, stationary-distribution theory beyond the basics, Itô calculus/SDEs, point processes, random tessellations (Voronoi/Poisson–Voronoi).

## How that maps onto the claim sources

- Darwin `Tree.lean`: a Galton–Watson or Yule process. `Zₙ / mⁿ` is a martingale, so `Martingale` + optional stopping give convergence; `E[Zₜ] = n₀ e^{λt}` recovers `expectedGenusSize`. The extinction theorem (generating-function fixed point on \([0,1]\)) is not in Mathlib but is a self-contained convexity argument, a realistic medium target. Tree-likeness of descent (`TreeLike`, `clade_laminar`) becomes an almost-sure statement about a random genealogy.
- Darwin `Struggle.lean`: survival fractions `s : ℕ → ℝ` become i.i.d. or Markov-dependent random variables; `survivalProduct_tendsto_zero` becomes an a.s. statement via the strong law or Borel–Cantelli, which is closer to what Darwin actually argues (random checks, not a fixed schedule).
- Levin: cell-state switching, bioelectric bistability and "competency" are finite-state Markov kernels. Expected error-correction time is a hitting-time statement (`Process/HittingTime.lean`). Finite state space keeps everything in `PMF` and `Fintype` sums, which is where proofs actually close.
- Wolfram NKS: probabilistic cellular automata on a finite grid are finite Markov chains on `Fin n → Bool`, same toolkit.
- Thompson / `cell-geometry`: this is the hard one. Lewis's law and Aboav–Weaire are statistics of random tessellations, and Mathlib has no point processes or Voronoi geometry. Finite versions (fixed number of cells, combinatorial Euler-characteristic constraints like mean degree 6 on a planar tessellation) are provable now; the stochastic regularities are not, short of building point-process theory.
- Math-bio claims: Turing instability and reaction-diffusion stay deterministic PDE/ODE and Mathlib's ODE coverage is itself thin (Picard–Lindelöf, Grönwall). Stochastic reaction-diffusion (SPDE) is out of reach in every proof assistant today.

## Adjacent systems, honestly ranked for this use

- Isabelle/HOL: the most mature probability library among proof assistants (HOL-Probability, Hölzl's Markov chains and MDPs with pCTL, Karayel's concentration inequalities, randomised data structures in the AFP). Deeper than Mathlib on discrete Markov models, but switching would fork the repo's `theorem` pipeline and Mathlib is catching up quickly in exactly the process-theory area (Pfaffelhuber, a population geneticist, is a co-author of the Brownian motion work). Best used as a source of proof plans to port.
- Coq/Rocq: Infotheo (finite probability and information theory) and MathComp-Analysis measure theory; the probabilistic separation logics (Clutch, Eris) are for randomized programs, not models. Same fork cost, less coverage than Mathlib for the continuous side.
- Probabilistic program logics (pGCL/weakest pre-expectation, Kaminski et al.; SampCert in Lean 4 uses `PMF`-based semantics for verified sampling): the right vocabulary if the claim is about a randomized procedure ("this regeneration algorithm reaches target morphology with probability ≥ p in expected ≤ k steps"). SampCert shows this is doable inside Lean 4 against Mathlib's `PMF`, so a Levin-style competency claim could use its style directly.
- Probabilistic model checkers (PRISM, Storm): fully automatic PCTL on finite Markov chains, extremely practical for Levin/NKS-style finite models. Their outputs are numerical verifications, not proofs in the repo's sense, so they belong in `test-data/claim-tests/`, not in `lean/reports/`.
- Markov categories (Fritz): the synthetic framework; Mathlib's `Stoch` category is the start of it. Useful for stating conditional-independence structure of a developmental model without measure theory, less so for quantitative claims.
- SciLean: differentiable numerics in Lean, no probability. Relevant only if you want deterministic morphogenesis simulations with proofs about the code.

## Recommendation

Add probability inside the existing Lean projects rather than beside them. Start with discrete time and finite or countable state, where Mathlib's `PMF`, `Kernel`, Ionescu-Tulcea and martingale theory are strong enough to finish proofs without `sorry`: a Galton–Watson module under `DarwinLaws` that derives the present `Tree.lean` and `Struggle.lean` results as mean-value or a.s. corollaries, then finite Markov kernels for Levin and NKS claims. Treat SDEs, point processes and stochastic tessellations as not yet formalizable, and keep their empirical regularities in `test-data/claim-tests/`. A proved statement about a stochastic model is still only a statement about the model; the a.s. and expectation claims carry the same caveat as the deterministic ones in the file headers.

_Tools used: Shell ×5_
