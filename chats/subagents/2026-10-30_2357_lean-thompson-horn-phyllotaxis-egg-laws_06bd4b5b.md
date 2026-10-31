# Subagent: Lean: Thompson horn, phyllotaxis & egg laws

- **Parent chat:** [Thompson's On Growth and Form claims as nanopubs](../2026-10-30_2015_thompson-s-on-growth-and-form-claims-as-nanopubs.md)
- **Started:** 2026-10-30 23:57 UTC-4 (EDT)
- **Last activity:** 2026-10-31 00:20 UTC-4 (EDT)
- **Final status:** success
- **Transcript ID:** `06bd4b5b-26fb-45a2-9bea-ad51d6ef4f93`

---

### 2026-10-30 23:57 — Turn 1 (User)

> Repository: /Users/jdietz/Documents/GitHub/dev/delphisci. Read /Users/jdietz/Documents/GitHub/dev/delphisci/thompson-growth-form/lean/INSTRUCTIONS.md fully and follow it exactly.
> 
> Module: HornsLeavesEggs (file thompson-growth-form/lean/ThompsonLaws/HornsLeavesEggs.lean, namespace ThompsonLaws.HornsLeavesEggs, report thompson-growth-form/lean/reports/HornsLeavesEggs.json).
> 
> Your claim ids (from thompson-growth-form/claims.json): thompson1917-ch13-01 thompson1917-ch13-03 thompson1917-ch13-04 thompson1917-ch13-06 thompson1917-ch13-13 thompson1917-ch14-07 thompson1917-ch14-08 thompson1917-ch14-09 thompson1917-ch14-10 thompson1917-ch15-06 thompson1917-ch15-10 thompson1917-ch15-11 thompson1917-ch15-12 thompson1917-ch15-15
> 
> Other agents are writing other modules in the same Lake project at the same time; do not touch their files, the lakefile, or anything outside your module and report file.

**Assistant:**

I should check source texts on Tait's work and branching derivation for key claims, then plan out formalizations starting with the horn growth problem—where a constant ratio between anterior and posterior velocity produces a logarithmic spiral curve.

I'm working through why two curves sharing the same pole with proportional exponential radii (r = ae^(kθ) and r = be^(kθ)) naturally yield a constant ratio of arc lengths, which captures the stated growth law in reverse.

The cleanest formulation is the ODE dr/dθ = k·r, whose solution r(θ) = r(0)·e^(kθ) is exactly the log spiral with constant growth-per-angle — and I'm considering how to prove this uniqueness result, perhaps by differentiating r(θ)·e^(-kθ).

The harder part is justifying why unequal growth rates in a tapering horn produce this exact constant-ratio relationship. I want to trace through Thompson's discrete argument: segments growing by different outer/inner lengths that bend through an angle proportional to the mismatch, trying to see if self-similarity forces the growth ratio to stay fixed at each step.

Now let me check relevant Mathlib API names in the local Mathlib.

I'm working through growth patterns with constant ratios, thinking about log spirals and equiangular self-similarity—modeling a growing horn's outer and inner curves as the tube bends, with lengths varying at each angle along the axis.

The cleanest formalization treats this as a differential growth equation: the derivative of the radius with respect to angle is proportional to the radius itself, giving an exponential relationship, while trying to tie together the ratio between a horn's two sides using separate exponential curves around a common pole.

With a constant ratio λ between outer and inner side growth increments, the width scales proportionally with the inner side, which is exactly the self-similarity condition that forces a logarithmic spiral shape — so I can parameterize by total turning angle θ, with inner arc length s(θ) and outer arc length λ·s(θ), both growing from zero together.

This confirms it: exponential arc length in tangent angle is exactly equivalent to the log spiral, with the growth constant matching cot α. Now I want to formalize a theorem stating that if arc length satisfies this linear ODE in θ, it must equal the exponential solution — proving uniqueness via the standard trick of showing the derivative of s(θ)·exp(−kθ) vanishes identically.

I'm also considering whether the ch13-01 and ch13-03 claims can share a definition, since both concern the plane spiral without lateral twist, and thinking about whether a separate theorem is needed for ch13-03 capturing the self-similarity property — that equal increments in turning angle multiply the arc length by a constant ratio.

For ch13-13 on claws and teeth, I reuse the same spiral law, proving turning grows unboundedly with length so the curve only looks conspicuous once the radius vector has swept a considerable angle. ch13-04 seems purely empirical with nothing meaningful to formalize, so I'll mark it as not-formalized. Moving to ch13-06, I'm checking the condition for a plane spiral in terms of maximum and minimum distances.

Checking the collinearity condition for max/min points with the origin, I realize it only requires the angles differ by a multiple of π, which doesn't strongly single out the "diametrically opposite" case Thompson implies. This claim seems too loose to formalize faithfully in Lean, so I'm inclined to mark it as not-formalized rather than force a shaky derivation linking asymmetry to helical growth.

This is really just the classic fact that two distinct points on a circle are collinear with the center exactly when they're antipodal — so coplanarity with the axis reduces to that diametrically-opposite condition. I can formalize this cleanly as the core geometric lemma, while flagging that the leap from "non-coplanar" to an actual helix remains Thompson's physical claim rather than something proven here.

I realize this is nicely provable algebraically using det²+dot²=1, avoiding trig subtraction identities entirely. Now I'm thinking about Tait's theorem on coprime pairs (m,n) and the Euclidean-style descent (m,n)→(n,m−n)→...→(1,1), connecting this to Fibonacci parastichy pairs on an unwrapped cylindrical lattice model, where the core reduction step mirrors this same descending process.

Confirming gcd preservation under subtraction, then formalizing the step as a function on pairs using Nat.fib's recurrence to show fib(k+2) - fib(k+1) = fib k, letting omega close the arithmetic. I'm defining the iterated step on pairs and stating that for every j ≤ k, iterating j times from the starting Fibonacci pair lands correctly along the sequence.

I'm working through an induction over the iteration count, using the successor-application lemma to peel off one step at a time, and setting up the index shifts carefully so the inductive hypothesis matches up with the shifted indices.

For the phyllotaxis problem, I'm thinking about the mathematical core more precisely: the turn condition t=2 corresponds to divergence angles strictly between 1/3 and 1/2 of a turn, which could potentially be stated as a clean equivalence rather than just an empirical majority claim.

I'm defining a recursive sequence phylloSeries indexed by a starting value t, where it begins at 1, then t, then each subsequent term is the sum of the previous two -- essentially a generalized Fibonacci recurrence. The conjecture is that for t=2 this sequence matches the Fibonacci numbers shifted by two indices, and for t=3 it should give a different but analogous known series.

I notice the t=3 series matches Lucas numbers rather than Fibonacci, but since Mathlib likely lacks a Lucas sequence definition I'll skip formalizing that. Moving to ch14-09: Thompson notes conspicuousness depends on the rhomboid diagonal ratio rather than divergence angle itself, and admits he hasn't worked out the underlying mathematics — Figure 327 shows the same lattice producing different conspicuous parastichies depending on leaf shape.

For ch14-10, the conceptual claim about biological insignificance isn't formalizable, but the embedded mathematical fact is: the ratio of consecutive Fibonacci numbers converges to the golden ratio conjugate. I'm checking whether Mathlib has existing lemmas on Fibonacci ratios tending toward the golden ratio, perhaps via Binet's formula.

I recall Mathlib may have renamed these lemmas under a `Real` namespace, and I need the bound |ψ| < 1 < φ to apply the standard theorem that powers of a number with absolute value less than one tend to zero. I'm weighing whether to just mark this result as formalized given the groundwork already laid out.

For the equilibrium equation of membranes, I'm thinking the claim about significance isn't something I can formalize, but the convergence itself is the real mathematical content, so I'll note that with a scope comment. For the egg-shape equation, deriving full membrane mechanics is tricky, but I can focus on the simpler consequence: when tensions are equal, the equation reduces to a spherical case where pressure relates inversely to curvature, which captures the essential mathematical relationship Thompson points to.

I'm wary that solving directly for curvature just restates the hypothesis, so the comparison theorem (more pressure yields flatter curvature) is the stronger result, alongside the uniform-pressure case giving constant mean curvature. I'll also note the equal-tension case trivially reduces to the symmetric form, and move to ch15-10 where P = T/R and tension scales with wall thickness, so at constant pressure thickness grows proportionally with radius.

For the monotonicity result, I'm defining wall thickness as proportional to P·R/σ, showing t/R equals P/σ and is monotone in pressure -- so as pressure drops with decreasing radius, thickness-to-radius ratio also falls. Then for ch15-11, within a single cavity where pressure is uniform, I derive that thickness times mean curvature stays constant across the cavity, meaning regions of higher curvature must be thinner-walled.

For ch15-12, I extend this to compare two different cavities (like left and right heart chambers): if both have equal dilation and the same wall stress, the ratio of thicknesses equals the ratio of pressures, which matches the empirical 6-7x figure. For ch15-15, I'm formalizing Hess's branching law by setting up the energy cost of a vascular branch as a function of where it leaves the trunk, then minimizing that cost to show the optimal branching angle's cosine equals the ratio of the two branch lengths.

I can get there via Cauchy-Schwarz too: writing L' times the branch length as at least L' times (cu + sh) for appropriate constants, with equality exactly at the stationary point, which gives a cleaner global minimality argument. That's a stronger but more involved route, so maybe I'll stick with the direct stationarity proof using the derivative formula instead.

Stationarity suffices here since it directly captures Thompson's reasoning of equating marginal costs along contiguous routes, so I don't need the full minimality claim. I'm setting up the derivative of branch cost with respect to the vertical offset, then showing that the derivative vanishing is equivalent to the cosine of the branch angle equaling L/L', which is just algebra once I have the derivative formula.

For 13-01 I need the exponential solution to the horn's growth ODE, skipping the general plane spiral case as out of scope. For 13-03 I'm working out self-similarity: equal turning multiplies arc length by a constant factor, so I'm defining a spiral growth rate parameter as a function of λ and β, then setting up the hypothesis that the arc length satisfies this constant-ratio growth condition via its derivative.

Now I'm deriving the physical hypotheses more carefully — defining the outer side length as a constant multiple λ of the inner side, the width as β times the inner side, and a bending condition relating the derivatives of outer and inner lengths to the width. From these I want to conclude that the inner side length grows exponentially with rate β/(λ−1), though I'm double-checking the velocity ratio reasoning before committing to that form.

Working out that the simplest hypothesis is that the derivative of the outer length equals λ times the derivative of the inner length, which cleanly gives (λ−1)s' = βs with fewer differentiability assumptions needed. I'm noting that λ is reserved in Lean 4, so I'll rename variables to avoid conflicts, and planning follow-up theorems about gnomonic self-similarity under equal turning angles and the relationship between turning angle and the logarithm of the length ratio.

I'm checking the standard polar notation for equiangular spirals against my own intrinsic Whewell-form result, and deciding to adjust notation with an explanatory note on their equivalence rather than proving the polar form outright, since that would be extra scope. Next I need to verify the correct Mathlib API names for this Lean version before writing the actual proof.

The theorem tendsto_fib_div_fib_succ_atTop gives -ψ, and since ψ = (1-√5)/2 by definition, unfolding Real.goldenConj and using ring shows -ψ equals (√5-1)/2. I should double check the namespace for that theorem.

Writing the module now.

I'm setting up the module with a membrane pressure function combining tension and curvature terms, then defining an equilibrium proposition relating normal pressure, tension, and curvature to total pressure, aiming toward a theorem showing the egg flattens under increased pressure.

Next I'm formalizing vessel wall thickness as a function of pressure, radius, and stress, deriving it from Laplace's law hypotheses, and proving that thinner-walled vessels correspond to lower pressure relative to radius. Then I'm extending the same approach to heart wall thickness, relating pressure to stress and mean curvature.

I left two placeholder sorries to fix after the first compile, and now I want to simplify the successor case of taitStep_iterate_fib by rewriting the goal using iterate_succ_apply, adjusting the index expression accordingly.

Setting k = i+j+1, taitStep_fib k gives exactly the form I need, so after rewriting the successor terms match the inductive hypothesis up to defeq, letting me close it with exact ih i.

For the vessel inequality, I'm planning to prove a helper lemma that P*R/σ/R simplifies to P/σ for positive R, then rewrite both sides and finish with a division inequality lemma.

I should add a doc comment naming the claim id to branchEnergyLoss_hasDerivAt as well, keeping it as one block per convention, and confirm that using `L'` as an identifier is valid in Lean 4 before compiling.

I realize `set c` could cause issues by unfolding later, so I should use `clear_value c` to keep it atomic, then apply linear_combination using the identity that (c-1)(c+1) equals c²-1, derived from the hypothesis.

Also I need to go back and remove the stray trailing `ring` after the stationary iff proof around line 314.

Clean compile with only standard axioms. Removing the `#print` lines and writing the report.

Everything looks clean with no warnings now, so I just need to remove those print lines by restoring the copy from /tmp, which was saved before the appending happened.

I need to write up the report now, keeping labels under 90 characters. I should correct the notation for ch13-01/03/13 to Whewell form, while ch15-15 and ch14-07 are already fine, and ch15-12's range notation can stay with a scope note. For each entry I'm noting the corresponding lean_declaration: taitStep for ch14-07, phyllotaxisSeries for ch14-08, phyllotacticFraction for ch14-10, and grow for ch13-06.

I formalized 12 of the 14 claims; the other 2 are marked not formalized. The module is `thompson-growth-form/lean/ThompsonLaws/HornsLeavesEggs.lean` and the report is `thompson-growth-form/lean/reports/HornsLeavesEggs.json`. `lake env lean` checks the module with no errors or warnings and no `sorry`. A `#print axioms` on every theorem listed only `propext`, `Classical.choice` and `Quot.sound` (some needed fewer). I removed those `#print` lines afterwards. I touched only these two files.

**Formalized claims and their theorems** (all in `ThompsonLaws.HornsLeavesEggs`):
- **ch13-01**: `hornLength_eq_exp`. The two sides of the horn grow in a constant ratio and the width is proportional to the length, so the length grows exponentially in the turning angle. That is a logarithmic spiral.
- **ch13-03**: `hornLength_selfSimilar`, `hornSpiralRate_antitone`
- **ch13-06**: `growthDirections_coplanar_iff_opposite`. This covers only the geometric core: the fastest and slowest growth points lie in one plane with the horn's axis exactly when they are diametrically opposite. The step from "not opposite" to "helical" is not proved.
- **ch13-13**: `accretionTurning_eq_log`. The angle turned grows only as the log of the length, so the spiral shows only when the structure is long.
- **ch14-07**: `taitStep_fib`, `taitStep_iterate_fib`, `taitStep_reaches_one_one`
- **ch14-08**: `phyllotaxisSeries_two`, `phyllotaxisSeries_three_not_fib`
- **ch14-10**: `phyllotacticFraction_tendsto_goldenMean`. This proves only the convergence to (√5 − 1)/2. The "no biological significance" part is a judgement, not maths.
- **ch15-06**: `eggEquation_equalTensions`, `egg_flatter_where_pressed`, `egg_uniformPressure_constCurvature`
- **ch15-10**: `vesselWall_eq`, `vesselWall_relThinner`
- **ch15-11**: `heartWall_mul_curvature`, `heartWall_thinner_where_curved`
- **ch15-12**: `ventricleThickness_ratio`. The 6–7 figure is Thompson's measurement and is left to data.
- **ch15-15**: `branchEnergyLoss_hasDerivAt`, `branchEnergyLoss_stationary_iff`. These show the energy loss is stationary exactly when cos x = L/L′. I did not prove it is the global minimum.

**Not formalized:**
- **ch13-04**: it only lists measured spiral angles for particular species.
- **ch14-09**: "conspicuous" is a matter of what the eye picks out, and Thompson says he didn't work out the maths.

**Notation changes:** I rewrote the claims.json notation where it didn't match what was proved, and each report entry's `scope_note` explains the change. For the three spiral claims (ch13-01, ch13-03, ch13-13), I proved length as an exponential of turning angle (the Whewell form) instead of the polar form r = a·e^(θ cot α). The two forms are equivalent, but the polar form itself isn't proved.

The egg equation p_n + T(1/r + 1/r′) = P (ch15-06) is assumed rather than derived from membrane mechanics. The Lean proves its consequences, such as the egg being flatter where the external pressure is greater.

_Tools used: Grep, Read ×3, Shell ×11, StrReplace ×8, UpdateCurrentStep ×3, Write ×2_
