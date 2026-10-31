# Subagent: Lean: Thompson mechanics & transformation laws

- **Parent chat:** [Thompson's On Growth and Form claims as nanopubs](../2026-10-30_2015_thompson-s-on-growth-and-form-claims-as-nanopubs.md)
- **Started:** 2026-10-30 23:57 UTC-4 (EDT)
- **Last activity:** 2026-10-31 00:19 UTC-4 (EDT)
- **Final status:** success
- **Transcript ID:** `9c546093-0191-4f57-8ba2-ab9614ebb24c`

---

### 2026-10-30 23:57 — Turn 1 (User)

> Repository: /Users/jdietz/Documents/GitHub/dev/delphisci. Read /Users/jdietz/Documents/GitHub/dev/delphisci/thompson-growth-form/lean/INSTRUCTIONS.md fully and follow it exactly.
> 
> Module: Mechanics (file thompson-growth-form/lean/ThompsonLaws/Mechanics.lean, namespace ThompsonLaws.Mechanics, report thompson-growth-form/lean/reports/Mechanics.json).
> 
> Your claim ids (from thompson-growth-form/claims.json): thompson1917-ch16-04 thompson1917-ch16-05 thompson1917-ch16-10 thompson1917-ch16-14 thompson1917-ch17-04 thompson1917-ch17-06 thompson1917-ch17-08 thompson1917-ch17-18
> 
> Other agents are writing other modules in the same Lake project at the same time; do not touch their files, the lakefile, or anything outside your module and report file.

**Assistant:**

Let me skim the BEST_PRACTICES sections briefly and check the claims against them.

Let me quickly check section 9 and verify the source text backing up some of these claims.

For the tube wall problem, I'm working through the bending stress relation for a thin-walled tube, using the approximation that the moment of inertia scales as πr³t and the section modulus as πr²t. Setting the max stress equal to the allowable stress gives wall thickness proportional to the bending moment, t(x) = M(x)/(πr²σ₀), so now I need the moment distribution for a simply supported beam under central or uniform loading.

For ch16-05, I'm turning to the principal stress problem — showing that eigenvectors of a symmetric 2D stress tensor corresponding to distinct eigenvalues are orthogonal. I want to formalize this with explicit matrix components, proving (λ-μ)(u·v)=0 by equating the two expressions for Su·v via symmetry, then deriving orthogonality algebraically with linear_combination or nlinarith.

For ch16-10, I'm now considering a girder model: upper tension and lower compression flanges separated by depth h, carrying force F with moment M = Fh. If flange force is capped at F₀, the required depth scales linearly with M.

I define spineHeight as M divided by F₀, then formalize that F₀ times this height equals M and that the height scales proportionally with moment. I'm setting aside the 2/3-1/3 ordinate example for now.

Moving to ch16-14, I'm examining three struts arranged at equal 120° angles for "greatest and most uniform strength" — the key mathematical fact is that the second moment of area summed over three equal struts at angles θ, θ+120°, θ+240° is constant regardless of the reference axis direction, since the sum of cos² terms reduces to a fixed value independent of φ.

I work through the trigonometric identity reducing each cos² term and showing the oscillating cosine terms cancel across the three angles, then try an alternative approach using explicit unit vectors at 0°, 120°, and 240° to verify the sum of squared projections onto any direction stays constant.

I'm defining bending stiffness as the sum of squared projections onto the strut directions, giving the clean result 3/2 (n1²+n2²) confirming uniformity.

For ch17-04, the claim about Cartesian transformations between related organisms feels empirical rather than mathematically precise, so I'll mark it as not formalized rather than force an affine-map framing. Moving to ch17-06, I'm now considering a one-axis stretch transformation.

With s=3/2 giving 2/3 and s=3 giving 1/3, I can state the general theorem plus instance: after uniform rescaling by 1/s, breadth scales by c=1/s at equal length, matching the notation convention. Now moving to the next item, ch17-08, I'm working through angle scaling θ'=kθ at equal radii, setting up radial coordinates for curves on each side.

For this I define halfLeafImage mapping (r,θ) to (r,kθ), with a theorem stating that for points at equal radius, the angle ratio is constant k — encoding side1's curve r=f(θ) and side2's curve g(θ)=f(θ/k), relying on monotonicity of f to compare points at equal radii.

I'm now moving to the volume scaling case: fixed shape with volume proportional to length, depth, and thickness, where doubling depth and halving thickness preserves the k=W/L³ coefficient. I'm formalizing lengthWeightCoeff with W=ρ·c·L·D·T and proving that scaling D by a and T by 1/a leaves k unchanged.

The plaice weight-length relationship is the empirical example grounding this, so this claim counts as an empirical generalization with a solid mathematical core underneath. I'm ready to write this to the file.

I'm trying to wrap the proof in a noncomputable section to fix the error, then working through the linear_combination residual by expanding the hu1 and hu2 terms to see what coefficients are needed.

After tracing through the cancellation, I realize the sign needs to flip, so the combination should be u1*hv1 + u2*hv2 - v1*hu1 - v2*hu2. For the refine step, I'm also simplifying the approach to a more robust simp call followed by field_simp.

All theorems check with only the standard axioms. Removing the `#print` lines and re-checking.

I should double-check that uniformStressThickness_stress doesn't rely on an unused hypothesis, and that the simplification requires M ≠ 0 since σ₀ = M/(π r² (M/(π r² σ₀))). Once I confirm there are no linter warnings, I'll remove the debug print lines and do a final check.

I formalized 7 of the 8 Mechanics claims; one is marked not formalized. The module checks with no errors and no `sorry`. I checked each theorem with `#print axioms`, and every one depends only on `propext`, `Classical.choice` and `Quot.sound`. I removed those lines afterwards and the module still checks cleanly.

- **Module:** `thompson-growth-form/lean/ThompsonLaws/Mechanics.lean`, in namespace `ThompsonLaws.Mechanics`.
- **Report:** `thompson-growth-form/lean/reports/Mechanics.json`, with 8 entries in `claims.json` order.

**Formalized claims and their theorems** (all names are in `ThompsonLaws.Mechanics`):
- **ch16-04, femur wall thickness:** `uniformStressThickness_stress`, `uniformStressThickness_prop`, `uniformStressThickness_max_mid`. A thin tube whose wall keeps bending stress at a fixed working value has thickness proportional to the bending moment. Under a uniform load on a simply supported beam, that thickness is greatest at mid-shaft.
- **ch16-05, trabeculae along stress lines:** `principalDirections_orthogonal`. The two principal stress directions of a symmetric plane-stress tensor are perpendicular when the stresses differ, so lines following them cross at 90°.
- **ch16-10, vertebral spine height:** `spineHeight_balances`, `spineHeight_ratio`. With a fixed force in the ligament and in the vertebral bodies, the spine height needed is the bending moment divided by that force. Heights at two points are therefore in the ratio of the moments there.
- **ch16-14, fish processes at 120°:** `threeStrutStiffness_isotropic`, `threeStrutStiffness_uniform`. Three equal struts at 120° give stiffness of 3/2 in every direction. This proves "most uniform", but not that 120° gives the greatest strength.
- **ch17-06, cannon-bones:** `lengthStretch_equalLength`, `lengthStretch_sheep_giraffe`. Stretching the length by a factor s and then rescaling to equal length leaves breadth multiplied by 1/s. That gives 2/3 for the sheep and 1/3 for the giraffe.
- **ch17-08, begonia leaf:** `unequalHalf_equalRadii`. If one half of the leaf is the other with every angle multiplied by k, points at equal radii have angles in the ratio k. This assumes the first half's radius never repeats as the angle changes.
- **ch17-18, plaice and haddock:** `lengthWeightCoeff_scale`, `lengthWeightCoeff_inverse`. Multiplying depth by a and thickness by b multiplies k = W/L³ by ab. Doubling depth and halving thickness leaves k unchanged.

**Not formalized: ch17-04 (Cartesian transformations).** This is a general claim that related forms are in fact simple deformations of one another. The text gives no mathematical definition of "simple and symmetrical", so any theorem would be generic arithmetic rather than Thompson's law. Two specific cases of it are covered by ch17-06 and ch17-08.

Each entry's `scope_note` says what is left to data. For ch17-06, it also notes that in the existing notation y is breadth and x is length. I did not change any notation.

_Tools used: Read, Shell ×6, UpdateCurrentStep ×3, Write ×2_
