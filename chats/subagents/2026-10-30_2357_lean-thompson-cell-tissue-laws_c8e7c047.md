# Subagent: Lean: Thompson cell & tissue laws

- **Parent chat:** [Thompson's On Growth and Form claims as nanopubs](../2026-10-30_2015_thompson-s-on-growth-and-form-claims-as-nanopubs.md)
- **Started:** 2026-10-30 23:57 UTC-4 (EDT)
- **Last activity:** 2026-10-31 01:53 UTC-4 (EDT)
- **Final status:** success
- **Transcript ID:** `c8e7c047-38ef-4859-a713-4be9c9c5a1e2`

---

### 2026-10-30 23:57 — Turn 1 (User)

> Repository: /Users/jdietz/Documents/GitHub/dev/delphisci. Read /Users/jdietz/Documents/GitHub/dev/delphisci/thompson-growth-form/lean/INSTRUCTIONS.md fully and follow it exactly.
> 
> Module: Cells (file thompson-growth-form/lean/ThompsonLaws/Cells.lean, namespace ThompsonLaws.Cells, report thompson-growth-form/lean/reports/Cells.json).
> 
> Your claim ids (from thompson-growth-form/claims.json): thompson1917-ch05-10 thompson1917-ch05-11 thompson1917-ch05-12 thompson1917-ch05-17 thompson1917-ch05-23 thompson1917-ch05-24 thompson1917-ch07-02 thompson1917-ch07-04 thompson1917-ch07-06 thompson1917-ch07-09 thompson1917-ch07-11 thompson1917-ch08-01 thompson1917-ch08-02 thompson1917-ch08-03 thompson1917-ch08-04 thompson1917-ch08-05 thompson1917-ch08-06 thompson1917-ch08-09
> 
> Other agents are writing other modules in the same Lake project at the same time; do not touch their files, the lakefile, or anything outside your module and report file.

**Assistant:**

I want to quickly check the "Stub proofs" section within the best practices documentation.

Looking at ch05-10, I'm weighing whether to formalize mean curvature for sphere and cylinder cases versus treating this as an empirical claim about commonness in organisms—the math itself (constant mean curvature like 2/r for spheres, 1/r for cylinders) is solid, but the frequency claim seems more empirical than something I can formalize.

For ch05-11, I'm working through the Laplace pressure problem: a cylinder of radius R with tension T gives pressure T/R, while a matching spherical cap with the same pressure and tension gives Rc=2R, leading to a 30° half-angle and height R(2-√3)≈0.268R where the cap meets the cylinder.

I'm checking this matches the "little more than one-eighth" claim both as a fraction of diameter (0.25R) and sphere radius (0.25R), confirming 0.268R clears the bound. Now I'm sketching the Lean formalization: defining cylinder and sphere pressure functions, proving equality forces ρ=2R, defining cap height, and proving it equals R(2-√3), plus the arcsin relation giving the half-angle π/6.

For the numeric bounds I'm verifying 0.25 < 2-√3 < 0.27 via squaring inequalities on √3 (between 1.73 and 1.75), then bundling everything—the ρ=2R relation, the arcsin angle, and the cap height formula—into one combined theorem with its bounds corollary.

Moving to the next problem, this one's about Plateau-Rayleigh instability for a cylinder of radius r and length l, recalling Thompson's classical stability argument where the critical wavelength equals the circumference, perturbing the radius sinusoidally along the length.

I'm checking whether second-order area expansion under volume conservation can realistically be formalized in Lean, since the exact perturbative formula requires heavy integral manipulation. I'm also testing a simpler substitute—comparing a cylinder's surface area to a sphere of equal volume—but realizing that threshold doesn't match the true Plateau-Rayleigh limit, so I need to go back and check the reference text for the correct faithful statement of Thompson's argument.

I'm working out the exact volume-preserving mean radius a(ε) from conservation, then deriving the second-order area expansion in terms of a, ε, and k, aiming to set up a comparison theorem showing the perturbed area is less than the baseline for small ε.

Trying the "iff k r0 < 1" condition directly turns out to only hold at second order, not exactly, so I'm pivoting to a cleaner quadratic-order expansion of the area change instead.

This definition captures two physical effects together: surface stretching from the undulation and mean radius reduction from volume conservation. The key theorem is that this quantity is negative exactly when λ exceeds 2πr0 — Rayleigh's criterion — with Lean proving the criterion from the hand-derived second-order expansion. I should also verify exact volume conservation and the mean radius inequality as supporting lemmas.

When k r0 < 1 both correction terms come out negative, confirming the undulated area drops below the cylinder area exactly. I realize the sqrt(1+x) ≤ 1+x/2 bound I'm using isn't just an approximation but a genuine upper bound, so I can push through to get a rigorous inequality on the true surface area per wavelength rather than just a second-order estimate.

This gives a genuine instability result, though the converse stability case for λ < 2πr0 would need a lower bound argument I'll skip for now, keeping just the instability theorem tied to the threshold λ = 2πr0. I'll set a = sqrt(r0² − ε²/2) and k = 2π/λ to finish the proof.

That should be manageable with nlinarith given the right hints. Moving to the next case, I don't think the unduloid shape can be faithfully formalized since Delaunay surfaces require solving an ODE, so I'll mark it as not-formalized, and similarly the mechanism case is not-formalized. For the biconcave shape not being CMC, I can formalize the core argument: at the dimple center both principal curvatures are negative while at the rim both are positive, so the mean curvature isn't constant, which violates Laplace's equilibrium condition for a fluid drop under uniform pressure.

Now I'm working through why a partition meeting a rigid wall must do so at 90°: since the wall itself can slide freely along the junction, the tangential components of the wall-film tensions on both sides cancel by symmetry, so the partition's own tangential tension component must vanish, forcing the angle to be a right angle.

Next I'm setting up the three-wall junction case, where three equal tensions meeting at a point must balance in both horizontal and vertical directions, which geometrically forces the three angles between them to each be 120°.

I can get arccos(-1/2) = 2π/3 directly since cos(π - π/3) = -cos(π/3) = -1/2, so Real.arccos_cos with the right bounds handles it cleanly. Also the equilibrium condition itself (sum of tension vectors equals zero) is independent of cell size—curvature only comes in separately, so I should define the junction equilibrium purely in terms of the three unit vectors and their weighted sum.

For the second theorem, wall curvature relates to the pressure difference divided by tension: κ = (p1 − p2)/T, matching Laplace's law in the cylindrical case where p_i = T/r_i. This would capture how relative cell sizes only affect wall curvature, not the 120° junction angles.

For unequal tension cases, I'm thinking about the Neumann triangle for two cells in a medium with distinct tensions — when the two cell-medium tensions are equal, the shared wall bisects the angle, and force balance along the axis gives the relation T_cc = 2T·cos(φ/2) between the cell-cell tension and the external angle between the two cell-medium interfaces.

Formalizing with unit vectors u, v, w along the three film directions with tension-weighted sum equal to zero, I can derive that the cosine of the angle between two films equals (T3²−T1²−T2²)/(2T1T2), so the external angle stays below 120° exactly when that cosine exceeds −1/2. This confirms Thompson's claim that if one tension dominates the other two, the opposing angle shrinks below 120°.

If T3 equals T1+T2 exactly, the angle collapses to zero so the two outer surfaces align in direction, meaning contact only happens at a single point rather than along a finite wall; if T3 strictly exceeds T1+T2, no equilibrium configuration exists at all.

Now I want to formalize this: from the force balance equation, taking norms squared gives T3² = T1² + T2² + 2T1T2⟨u,v⟩, so I need to work through the inner product expansion carefully in Lean using lemmas for norms of sums and scalar multiplication. I'll set this up in a two-dimensional Euclidean space for concreteness, aiming for a generic lemma that covers both the ch07-04 and ch07-06 cases.

For ch07-04, the special case where all three tensions are equal, I need an angle bound: when the inner product exceeds -1/2 for unit vectors, the angle is strictly less than 2π/3, relying on arccos being strictly decreasing -- I'll need to verify the exact Lean lemma signature for that monotonicity fact. Then for ch07-09, I'm shifting to hexagonal tilings under uniform pressure, where the key fact involves the mean number of neighbors at three-fold vertices in a planar tiling.

Actually there's a cleaner formalization here: a convex polygon that's equiangular at 120° must be a hexagon, since the interior angle formula (n-2)π/n equals 2π/3 exactly when n=6. I'm sketching out the theorem statement for this angle-sum argument, requiring n≥3 and the total angle sum condition, to conclude n must equal 6.

Then I move on to the rhombic dodecahedron's characteristic angle of 109°28' (cos θ = -1/3), and recall that the "bee's cell minimizes surface" claim is actually known to be false—Fejes Tóth found a better closing shape—though it is minimal within the restricted Maraldi/Koenig family where the hexagonal prism is fixed and only the apex slope varies.

Setting derivative to zero gives cos θ = 1/√3, confirming the known minimal surface result, with volume staying constant regardless of θ since the truncation removes and adds equal volume. I want to verify this is truly the minimum by showing f(θ) = √3/sinθ − cotθ is bounded below by √2 at this critical angle, which reduces to proving an inequality after squaring both sides.

Let me check the diagonal ratio directly: for the rhombic dodecahedron's characteristic obtuse angle, cos φ = -1/3 implies a diagonal ratio of √2, so I'm verifying whether my computed d2 at the optimal θ actually matches that ratio — plugging in cos θ = 1/√3 gives a ratio of √3/√2, which doesn't match, so something in my setup is off.

I should go back to Stewart's original area formula for this classic calculus optimization problem, where θ is the angle between the hexagonal base's altitude and the lateral rhombic faces, with the known optimum at cos θ = 1/√3. I'm working out the geometry of the rhombus diagonals — the short diagonal is horizontal with length s√3, while the long diagonal runs from the apex to the opposite lateral vertex, and I need to find its horizontal projection relative to the hexagon's center.

Checking the apex angle using the half-angle tangent gives cos α = −1/3, confirming an obtuse angle near 109.47°, consistent with the tetrahedral-like geometry. The rhombus area works out to (√3/2)s² csc θ per face, matching the earlier Stewart's theorem term when tripled.

Now I'm formalizing the total surface area formula as a function of side length, height, and tilt angle, then setting up a theorem that the minimum occurs at the critical angle where cos θ = 1/√3, giving the known bound of 6sh + (3√2/2)s² with equality there. I'm also verifying that at this optimal angle, the rhombus diagonals and resulting obtuse angle match the expected geometric value.

I should note that the volume-independence of θ isn't actually proven here, just assumed, and that the global minimality claim is false by Fejes Tóth's 1964 result — Lean only establishes minimality within the classical one-parameter family, which is worth flagging as a scope limitation.

Moving to the rectangular box problem: for a ≥ b ≥ c, cutting with a plane perpendicular to the longest axis gives the smallest cross-sectional area among the three axis-parallel options, since bc ≤ ac ≤ ab.

Now I'm working through successive perpendicular cuts — after halving along the longest axis a, the daughter cell becomes a/2 × b × c, and I need to check whether the new longest axis is now b (which happens when b ≥ a/2). This mirrors Thompson's observation about cell division planes alternating at right angles, and I'm verifying the condition under which this alternation actually holds for successive halvings of a rectangle.

Tracing the successive-bisection case: after cutting across a, the daughter box a/2×b now has b as its longest side, so the new cut must be perpendicular to the previous one, across b — and this alternation follows directly from a ≤ 2b forcing a/2 ≤ b, which is really just basic arithmetic once stated correctly.

I'm now considering the Errera principle as a variational postulate rather than something provable outright, noting that Sachs's rule looks like a special case of it.

Actually this gives a cleaner formalization: define a minimality condition on cut areas across the three axes, show it's equivalent to cutting across the longest box dimension, which makes Sachs' rule a formal corollary of Errera's minimal-area principle.

Working through ch08-03's concrete examples: for a unit cube, a plane cut parallel to a face always gives area 1, while a quarter-cylinder cut along an edge with radius r gives volume πr²/4 and area πr/2, beating the plane when r < 2/π (volume fraction under about 1/π ≈ 0.318, matching "about three-tenths"). I'm now comparing that against a spherical octant cut from a corner, computing its volume πr³/6 and area πr²/2, and matching volumes with the quarter-cylinder case to see which shape gives less area at the same volume.

Setting the two area expressions equal in terms of shared volume v, I raise both sides to clear fractional exponents and simplify, finding the octant beats the cylinder when v < 4π/81 ≈ 0.155, confirming "about 0.15." Then I check whether the octant also beats the plane cut, which requires r² < 2/π.

Now I'm setting up formal theorems parameterized by radius: defining quarter-cylinder volume and area in terms of r, proving the area-vs-volume inequality reduces cleanly to a radius bound, and preparing a matching comparison between octant and cylinder at equal volumes.

That confirms the threshold is 4π/81, which checks out numerically between 0.155 and 0.156 using the standard pi bounds of 3.14 and 3.15, giving a clean rational comparison for 1/π as well. I should probably also set up a numeric bounds lemma alongside the main theorem.

Now I'm thinking about the geometric setup itself — a unit cube with a quarter cylinder running along an edge and an octant tucked into a corner, plus a related problem about bisecting a quadrant with a circular arc orthogonal to both the outer boundary and the straight radius.

For that arc, orthogonality forces its center onto the extension of the straight side, with the distance relation d² = 1 + ρ² linking it to the outer circle. I'm working out where this arc intersects the side and the periphery, trying to match the cut-off area to π/8, which seems to correspond to the arc slicing off roughly 55°22′ of the 90° quadrant near the corner.

I realize the cut-off piece near A is actually the overlap between the unit disk's sector and circle C's disk, since A lies inside circle C. So I need the lens-shaped intersection area between the two orthogonal circles, restricted to the upper half, to find the piece being subtracted.

Using the standard circle-intersection area formula, I work out the upper half-lens as a function of φ, using the relation d sinφ = ρ (since tanφ = ρ). Setting this equal to π/8 for the bisection condition, I solve and get φ ≈ 0.9664 rad (55.37°).

Plugging numbers back in confirms this checks out numerically: ρ ≈ 1.4473, and the half-lens area formula evaluates to almost exactly π/8, with the extra distance d − ρ coming out to about 0.3 as expected. Now I'm setting up to formalize this as a statement that there exists φ between 55° and 56° satisfying the half-lens area equation, planning to prove existence via the intermediate value theorem.

I'm realizing that formalizing this in Lean is going to be tricky since it requires numeric bounds on tangent at 55° and 56°, which is hard to establish rigorously with transcendental functions — so I'm considering whether to instead focus on proving the clean geometric relationships (orthogonality giving d² = 1 + ρ², cos φ = 1/d, and the symmetric relation between the start point and d+ρ) while treating the precise numeric angle as something to verify separately.

Actually, I can use the intermediate value theorem more cleanly: at φ=π/4, the halfLensArea function evaluates to about 0.285, below the target π/8 ≈ 0.393, while at φ=π/3 it evaluates to about 0.443, above the target. This gives IVT a guaranteed root between 45° and 60° using exact values like tan(π/4)=1 and tan(π/3)=√3, consistent with Thompson's claimed ~55°22' even if I can't narrow the bracket further.

Using intermediate_value_Icc for the IVT step seems doable though fiddly, and I'd derive the half-lens area formula by hand, noting the assumptions since tan(55°) isn't exact so there's no point tightening the bracket further. For ch08-05 I'm now considering a sector cell of angle θ with radius 1, thinking through how the anticlinal wall would be a circular arc orthogonal to both bounding radii.

I'm also looking at the periclinal arc concentric at the center cutting across both radii with length θ/√2, and need to check Thompson's actual comparison around the 62½° threshold to confirm how the anticlinal wall is defined — a radial bisector versus an arc. For ch08-06 I need the growth numbers 1.345 and 1.517 from the text on quadrant division, and for ch08-09 I'm puzzling over the claim of 13 partition types for n=8 cells, trying to figure out the combinatorial structure of n regions all touching a common outer boundary.

This looks like a disk subdivided into n regions, each touching the boundary, with interior walls meeting three at a time — so dually it's like a triangulation of a convex n-gon using n−3 diagonals. Counting triangulations of an octagon up to rotation and reflection gives 12 rather than 13, based on the known sequence of triangulation counts by polygon size, so I'm trying to reconcile that discrepancy with the stated count of 13.

Working through the Euler relation on the disk subdivision gives 3t = 2d + n and t = d + 1, so solving confirms d = n − 3. I'm trying to re-derive this directly using the cell picture, distinguishing interior triple junctions from boundary vertices where the dividing walls meet the circle.

Solving the system gives I = n − 2 interior points and e = 2n − 3 total partition segments, so subtracting the n segments touching the boundary leaves exactly n − 3 internal partitions, matching Thompson's count. This confirms the formula holds generally via Euler's formula combined with the degree-sum equation at each vertex.

As for the specific claim of 13 triangulation types, I'm uneasy asserting this formally — OEIS sequences for octagon triangulations under symmetry suggest a count of 12, which doesn't cleanly match Thompson's 13, so I should flag this discrepancy rather than assume Lean verifies it.

Confirmed: octagon gives 12 types, matching A000207. Since I only actually proved the n−3 partition count rather than the full classification count of 13, I should correct the notation to reflect just what was proven rather than claim the unverified 13 figure, and explain that distinction. Next I need to check the text for ch08-05, ch08-06, ch05-24, ch05-12 stability section, and ch08-04.

I'm converting between Thompson's angle convention and mine, substituting φ = π/2 − θ into my equation and confirming it reduces to the same form as his f(θ) = 0.

Now I'm checking numerically that the quadrant-cut area function crosses π/8 between θ = π/6 and θ = π/4, confirming a root exists there matching Thompson's 34°38' value, and starting to verify that the arc length θ cot θ stays below 1 on this interval.

Using Mathlib's strict tangent inequality (x < tan x for 0 < x < π/2), the arc length comparison reduces to confirming 2√2 < π, which establishes that the curved wall is shorter than both the radial wall and the periclinal wall — exactly Thompson's argument for why the arc gives the minimal bisecting partition. I also notice OM simplifies nicely to tan(θ/2), which should make the monotonicity analysis straightforward.

I think the cleanest approach is to just state that an arc solving the bisection exists for θ between 30° and 45°, corresponding to cutting off between 45° and 60° of the circle, and that this arc is shorter than the radial or periclinal alternatives — leaving the precise numeric value (55°22′) as a separate computation rather than something I need to derive symbolically. For the existence argument I'll need intermediate value theorem reasoning, which requires establishing continuity of the relevant trigonometric function on the interval [π/6, π/4].

Applying the IVT version gives θ within the closed interval, which works fine for the proof even though strictly the solution lies in the open interval. I'll state θ ∈ Set.Icc (π/6) (π/4) and move on to the next problem involving a bisected sector, where the periclinal and anticlinal lengths relate through cot θ depending on angle α.

Working through the geometry, the angle AOP = π/2 − θ stays fixed regardless of α since it's local to side OA, so the area of region PMA equals half the sector area, giving α = π − 2θ + 2θcot²θ − 2cotθ, with the equality condition MP = RS determining θ.

Translating this to a comparison criterion, anticlinal division is shorter when θcotθ < α/√2, which reduces to the known numeric threshold around 62.5°. Checking boundary cases: at α=90° the anticlinal side clearly wins (0.875 vs 1.111), but at α=60° the values (0.73 vs 0.72) are too close to settle definitively without more careful analysis, and there's still the feasibility constraint on θ to account for.

This feels laborious to formalize rigorously, so I'm considering a partial approach: proving the weaker but cleaner bound that anticlinal wall length θcotθ is always less than 1, while periclinal RS equals α/√2, giving a clean threshold around 81° rather than the exact 62.5° claim.

Finding the exact crossover numerically is too costly, so I'll settle for a partial result: formalize the anticlinal arc length function and its bound below 1, plus the periclinal bisection formula showing it equals α/√2, and state the comparison theorem only in the regime where it's provable without the full numeric threshold.

Checking Thompson's doubling radius calculation against his approximate value confirms it, so I'll define doublingRadius φ as the radius satisfying the sector-margin area increment equaling the cell's original area π/8.

Since φ_T = π/2 − θ exceeds φ_Q = θ for θ < π/4, the triangular cell's doubling radius is smaller, meaning it divides first — I should prove this monotonicity directly from the defining equation, possibly bounding it for θ in [π/6, π/4] to match Thompson's numeric values.

So the theorem holds strictly for 0<θ<π/4, giving R_T < √2 < R_Q. Since f(π/4) ≠ π/8, the root θ from the earlier result can't actually hit π/4, so I can refine that closed interval into an open one and get strict inequality everywhere I need it.

Now I'm checking whether Q's growth truly matches the arc angle θ — Thompson's assumption that increments are proportional to the arc's angle, which does hold since Q's margin is the arc BP subtending θ. That confirms the setup is consistent, so I should go back and quickly verify the relevant passages in ch05-24 and ch05-12 to make sure nothing contradicts this.

That matches up—a quarter of the radius checks out. Now for the pressure problem, I'm thinking through the Laplace pressure relation at the rim versus the dimple: at point A the curvatures both contribute positively giving net positive pressure, while at C both principal curvatures are negative, making the sum negative there.

So the pressures at A and C genuinely differ, meaning there's no single consistent pressure value that equals both. I'm working toward building the Lean formalization now, starting with a junction lemma relating three tension vectors summing to zero to their squared magnitudes via the inner product, using the law of cosines-style identity. I need to be careful about Mathlib's current inner product notation conventions as I write this out.

For the angle calculation involving arccos(-1/2), I'm checking whether Mathlib has a direct lemma for arccos of one-half or whether I need to derive it from arccos_neg and known cosine values at π/3.

I'm trying to figure out how to prove the angle equals 2π/3 using arccos, searching for relevant lemmas like arccos_cos or something bounding arccos for the strict inequality case.

Since cosine is strictly antitone on [0,π], I can argue by contradiction: if the angle were ≥ 2π/3, cosine of the angle would be ≤ cos(2π/3) = -1/2, computed via cos(π - π/3) = -cos(π/3). I'm now ready to draft the actual Lean proof.

I'm fixing some naming issues—avoiding the reserved keyword λ by renaming it to L for wavelength, simplifying a trivial theorem to take no arguments, and cleaning up a messy inequality step in the bee cell area proof by deriving it more directly from a square-root comparison.

For that inequality, I'll just use by_contra combined with nlinarith to handle the contradiction when √2·n exceeds √3−c, since the squared terms make the contradiction straightforward.

I'm noticing the inner product notation with the `_ℝ` suffix is causing a parsing issue, where it's interpreting part of the expression as a type rather than the intended real-valued inner product syntax.

I decide to just switch to writing `inner ℝ a b` explicitly instead of the bracket notation to avoid ambiguity. For the sachsRule proof, I'm working out how to use injectivity of cosine on `[0, π]` to conclude the angle equals π/2 from the cosine equaling zero, and I also want to clean up a redundant proof step that's now hitting "no goals" after a simplification already closed it, plus fix a ring_nf failure in another lemma using field_simp before ring.

The edit script didn't run; retrying it.

The tool infrastructure seems flaky, so I'll switch to using StrReplace edits instead.

I realize the issue is with ordering: the `set` tactic is hiding the cosine term before I can prove the area formula. I should restructure the proof to establish the area equation explicitly first, using field_simp and ring, before introducing any substitutions.

For the equality step, I can derive it by cancelling the common factor of 3/2·s² from both sides using mul_left_cancel₀, after rearranging the given equation with linarith.

There's also a positivity failure around line 526 I need to track down, so I should look at the surrounding lines to see exactly which expression is failing.

I'm checking that the equation reduces to matching terms on both sides, since the coefficients involving √2 should simplify correctly via ring normalization, so linarith should close it. I'm also double-checking whether the earlier error list was complete or if some errors were hidden.

I notice there's a leftover unused helper in octant_lt_quarterCyl that compiled but isn't needed—I should remove it along with its stray comment, and add the #print axioms lines for verification.

I'm noticing the second conjunct in that bisection conclusion is trivially weak, so I want to reframe it using a cleaner 2D definition of the wall length across a rectangle, then try simplifying the 3D case by setting the daughter dimensions to half the original along one axis.

With c ≤ b ≤ a ≤ 2b, the daughter's longest axis becomes b, so the minimal-cut axis shifts to index 1, perpendicular to the original axis-0 cut. I'm restructuring the theorem into two conjuncts proved via boxCut_longest_minimal, each needing a case split over all axis indices to confirm the minimal condition holds — though I suspect `simp` might fully close some goals before `linarith` even gets a chance, so I need to guard against "no goals" errors by using `try linarith` or similar fallback tactics.

The helper theorems junction_inner and cos_two_pi_div_three are also fine, and the report correctly places junction_inner under claims 07-06 and 07-04. Time to run it.

I should remove the debug print lines now, and check that each block has a doc comment naming its claim id — junction_inner and cos_two_pi_div_three are missing theirs, so I'll add those in.

Now removing the `#print` lines and running a final check.

Good, the doc-comment additions are already done, so now I'll write up the report in JSON following the same order as claims.json.

I should verify each label stays under 90 characters, confirm the JSON is well-formed, and double-check the order aligns with claims.json.

The Cells module checks with no errors and no `sorry`: 15 of the 18 claims are formalized and 3 are not. I ran `#print axioms` on all 27 theorems and each one uses only `propext`, `Classical.choice` and `Quot.sound`. I then removed the `#print` lines and checked the module again, with no output.

- **Module:** `thompson-growth-form/lean/ThompsonLaws/Cells.lean`, in namespace `ThompsonLaws.Cells`.
- **Report:** `thompson-growth-form/lean/reports/Cells.json` has 18 entries in claims.json order, and every label is 90 characters or fewer.

**Not formalized (3):**
- ch05-10 is an empirical generalization about which cell shapes are common.
- ch05-17 identifies observed Vorticella cup shapes with unduloids, which is empirical.
- ch05-23 is a proposed mechanism with no mathematical consequence to prove.

**Formalized, with theorem names:**
- ch05-11: `cylinderCap_geometry`, `capHeight_bounds`
- ch05-12: `liquidCylinder_unstable`
- ch05-24: `biconcave_not_equilibrium`
- ch07-02: `sachsRule`
- ch07-04: `junction_inner`, `cos_two_pi_div_three`, `tripleJunction_120`, `partitionCurvature_eq`
- ch07-06: `junction_inner`, `external_angle_lt_120`, `contact_at_point`
- ch07-09: `hexagon_of_120`
- ch07-11: `beeCellArea_min`, `beeCell_rhombus_angle`
- ch08-01: `boxCut_longest_minimal`, `successive_bisection_perpendicular`
- ch08-02: `errera_implies_sachs`
- ch08-03: `quarterCyl_lt_plane`, `octant_lt_quarterCyl`, `corner_thresholds`
- ch08-04: `quadrant_bisected`, `anticlinal_shortest`
- ch08-05: `periclinal_bisects`, `anticlinal_lt_periclinal`
- ch08-06: `doublingRadius_spec`, `triangular_divides_first`
- ch08-09: `intermediatePartitions`

**Limits recorded in the report's scope notes:**
- **Values not proved:** Thompson's numbers come from his tables or plots: 55° 22′ (ch08-04), 62½° (ch08-05) and 1.345 / 1.517 (ch08-06). Lean proves weaker bounds instead:
  - ch08-04: the bisecting angle lies between 30° and 45°.
  - ch08-05: an anticlinal wall wins whenever the sector angle is at least about 81°.
  - ch08-06: the triangular cell is ready to divide before the disc radius reaches √2, the quadrilateral only after.
- **Bee's cell (ch07-11):** the least-area result holds only within the classical one-parameter family of closings. A 1964 result found closings with slightly less area, so "least surface for a given volume" is true only in that restricted sense.
- **Eight-celled groups (ch08-09):**
  - I proved the n − 3 partitions part and shortened the notation to match.
  - The count of 13 types is not proved. An octagon has 12 triangulations up to rotation and reflection (OEIS A000207), so Thompson's 13 depends on how he counted types.
- **Corner division (ch08-03):** I changed the notation to the exact thresholds that were proved: 1/π ≈ 0.32 for the quarter-cylinder and 4π/81 ≈ 0.155 for the spherical octant.
- **Hand-derived inputs:** Lean takes some area formulas as given rather than deriving them. These are the area integral for ch05-12, Thompson's own area formula for ch08-04, and the standard bee's-cell area formula for ch07-11.

I did not touch any file other than the module and its report.

_Tools used: Read ×6, Shell ×15, StrReplace ×17, UpdateCurrentStep ×4, Write ×2_
