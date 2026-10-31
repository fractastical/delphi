# Subagent: Lean: Thompson magnitude & growth laws

- **Parent chat:** [Thompson's On Growth and Form claims as nanopubs](../2026-10-30_2015_thompson-s-on-growth-and-form-claims-as-nanopubs.md)
- **Started:** 2026-10-30 23:57 UTC-4 (EDT)
- **Last activity:** 2026-10-31 00:03 UTC-4 (EDT)
- **Final status:** success
- **Transcript ID:** `fe3d2333-ab62-4e4b-86df-fc1e84c948ef`

---

### 2026-10-30 23:57 — Turn 1 (User)

> Repository: /Users/jdietz/Documents/GitHub/dev/delphisci. Read /Users/jdietz/Documents/GitHub/dev/delphisci/thompson-growth-form/lean/INSTRUCTIONS.md fully and follow it exactly.
> 
> Module: Magnitude (file thompson-growth-form/lean/ThompsonLaws/Magnitude.lean, namespace ThompsonLaws.Magnitude, report thompson-growth-form/lean/reports/Magnitude.json).
> 
> Your claim ids (from thompson-growth-form/claims.json): thompson1917-ch02-01 thompson1917-ch02-02 thompson1917-ch02-03 thompson1917-ch02-05 thompson1917-ch02-06 thompson1917-ch02-09 thompson1917-ch02-10 thompson1917-ch02-12 thompson1917-ch02-15 thompson1917-ch03-07 thompson1917-ch03-17 thompson1917-ch03-21 thompson1917-ch03-23 thompson1917-ch03-30
> 
> Other agents are writing other modules in the same Lake project at the same time; do not touch their files, the lakefile, or anything outside your module and report file.

**Assistant:**

Let me quickly check the best practices doc for guidance on stub proofs and the relevant section 9.

I should check a few source passages for the trickier problems before designing the proofs. I know the underlying physics here—weight scaling as the cube of length with a constant coefficient—so I'm setting up the theorem statement for that relationship.

For Greenhill's formula on critical buckling height, I'm formalizing it so height scales with diameter to the two-thirds power, then deriving the equivalent statement that minimum diameter scales with height to the three-halves power, framing it as an iff between the stability inequality and the diameter bound.

I could also add a scaling theorem showing minDiam(λh) = λ^(3/2) * minDiam(h), tying back to the 300 ft empirical case. For strength-to-weight, I'll formalize that requiring a minimum ratio r forces an upper bound L ≤ a/(b·r), mirroring the self-support constraint. Then for muscle work, I'm thinking through Thompson's scaling argument where energy storage/power goes as L^3 while supply rate scales as L^2.

I'm working through the scaling argument: muscle force scales with L^3 while oxygen supply scales with L^2, so the ratio of supply rate to muscle capacity falls as 1/L — which seems to suggest larger fish should have less sustained power relative to burst capacity, yet Thompson claims smaller fish fatigue faster. I'm trying to reconcile that apparent contradiction in the math.

For the flight work problem, I'm deriving Thompson's momentum-balance equations: weight scales as l^3, lift as l^2·V, and setting them equal gives V proportional to sqrt(l). Substituting back shows the work required scales as l^(7/2), and I want to formalize this with a theorem connecting the momentum balance to the final flight-work scaling law using real exponents.

I realize squaring W avoids needing fractional exponents entirely -- W^2 ends up proportional to l^7, which is a cleaner polynomial relationship to prove, so doubling body length roughly doubles the difficulty by a factor of sqrt(2).

I'm setting up a flight speed function as the square root of the ratio k times l, then defining flight work as proportional to l squared times that speed cubed. I want to prove a balance theorem showing that given the force equation holds with positive constants, the speed must equal this flight speed formula, derived by squaring and taking the square root.

Next I'm proving that doubling the wing length multiplies flight work by 8 times sqrt(2), using the scaling property of the square root. From this I derive that the ratio of flight difficulty (work divided by mass times length cubed) between doubled and original length equals sqrt(2), bounding it between 1.4 and 1.42. I also establish that flight work squared equals c squared times k cubed times l to the seventh power, confirming the 7/2 power relationship.

Moving to jump height, I define it in terms of takeoff velocity, mass, and gravity, then apply Borelli's scaling law where velocity is proportional to mass, showing jump height becomes independent of mass entirely—so animals of different sizes following this scaling should jump to the same height. For chapter 2-10, I'm working through three separate mechanisms that all yield velocity proportional to the square root of length: analyzing a walking pendulum's period and stride to derive velocity scaling, and considering corresponding speeds via equal Froude number.

I'm formalizing all three mechanisms (Froude scaling, flight speed, and pendulum walking) as instances of a general property where velocity equals some constant times the square root of length, then working through the algebra to prove the pendulum case reduces to this same form.

For the empirical generalization about surface-to-mass ratios in similar forms, I'm capturing the core idea mathematically: surface area scales as L² while mass scales as L³, so to keep the surface-to-mass ratio constant, the surface-folding factor must grow linearly with L rather than staying fixed as in geometrically similar shapes.

I'm also thinking through cell division as a related case — when a sphere of fixed volume splits into equal daughter spheres, total surface area increases by a cube-root factor of the number of divisions, which explains how cleavage at constant volume boosts surface area and can restore the surface-to-mass ratio as a cell grows and divides.

I'm also setting up the surface-to-volume ratio for a daughter cell using rpow_sub, confirming it scales the same way. Then for ch03-07, I'm defining weight as proportional to length cubed, proving a ratio formula between two time points, and establishing the derivative relationship showing weight's rate of change depends on length squared times the length's own derivative, which distinguishes the weight curve's shape from the stature curve.

For ch03-17, I'm noting this is an empirical claim—the proportionality constant isn't actually constant according to the data—so there's no real mathematical statement to formalize, just an observation to mark as not-formalized.

Moving to ch03-21, van't Hoff's law: I'm defining a rate function as v0 times x raised to θ, then proving that shifting θ by n multiplies the rate by x^n, and that Q10 (the rate ratio over a 10-degree shift) equals x^10. I note the general multiplicative law for all real n trivially implies the exponential form by setting θ=0, and the empirical bound that Q10 falls between 2 and 3 just gets left as data without further proof.

Now for ch03-23, I'm modeling seasonal growth as a baseline trend plus a damped sinusoidal term, and proving that if the amplitude tends to zero, the deviation from the baseline also tends to zero—bounding the sine term by the amplitude and applying a squeeze argument to zero.

I could also note the seasonal term has a one-year period for consistency. Then turning to another case, I'm thinking about a power-law relation like V^m T^n = constant, formalizing regeneration velocity as inversely proportional to T squared, and more generally deriving V in terms of a rpow expression with log V as a linear combination of log K and log T.

Writing the log-linearity proof...

I'm fixing the proof by rewriting only the RHS occurrence of d using the backward hypothesis, then applying rpow_le_rpow_iff and div_le_iff₀' to close the iff goal. For the second fix, I'm working out how to rewrite h3 using a multiplication lemma.

Writing simp/rw fixes...

For fix 3, I'm removing the unnecessary `ring` call on line 137. For fixes 4 and 5, I'm deciding whether to use targeted rewrites with hLL or n, or fall back to field_simp combined with a rewrite to close the equality goals without clobbering other occurrences.

I'm trying a calc proof instead: rewriting n times a fraction as n^(1/3)*n^(2/3) times the same fraction using the key identity, then using field_simp to collapse it down to n^(1/3) times the product — that way the rewrite hits both sides identically and simplifies cleanly.

I need to check that the calc's first expression matches the goal exactly after unfolding and rewriting with div_rpow, comparing both sides term by term before running it.

I realize flightWork_double doesn't actually need those hk hl hypotheses, since sqrt_mul only requires the first argument to be nonnegative. I'll remove them and update the call site in flightDifficulty_double, then add a check for axiom dependencies.

Module checks; now adding the `#print axioms` lines temporarily to verify axioms.

Checking each chapter's formalization status one by one: ch02-05's scaling notation holds up, ch02-12's generalization is fine with its formalized core, but ch03-17 still isn't formalized. I'm noting ch02-02's empirical ceiling value needs a scope caveat, and reviewing ch02-06's flight power notation next.

I've written the Magnitude module at `thompson-growth-form/lean/ThompsonLaws/Magnitude.lean`. **13 of the 14 claims are formalized and 1 is not.** It checks with `lake env lean` with no errors, no warnings and no `sorry`.

**Axioms:** I added `#print axioms` for all 32 theorems. Every one depends only on `propext`, `Classical.choice` and `Quot.sound`. I then removed those lines again.

**Report:** `thompson-growth-form/lean/reports/Magnitude.json` has 14 entries in claims.json order. All labels are 90 characters or fewer, and the notation is the same as in claims.json for every claim.

**Not formalized:** thompson1917-ch03-17 (the plaice weight–length coefficient \(k = W/L^3\) peaking near 30 cm) is purely empirical. Its definition is already covered by `weightCoeff` under ch02-01.

**Formalized** (all names are in `ThompsonLaws.Magnitude.`):

| Claim | Definition | Theorems |
|---|---|---|
| ch02-01 | `weightCoeff` | `weightCoeff_eq`, `weightCoeff_const_iff_form_const` |
| ch02-02 | `greenhillCriticalHeight` | `greenhill_stands_iff`, `greenhillMinDiameter_scale` |
| ch02-03 | `strengthToWeight` | `strengthToWeight_eq`, `strengthToWeight_size_bound` |
| ch02-05 | `burstToSupplyRatio` | `burstToSupplyRatio_eq`, `burst_advantage_exceeds_supply_advantage` |
| ch02-06 | `flightWork` | `flightSpeed_of_balance`, `flightWork_sq`, `flightWork_double`, `flightDifficulty_double` |
| ch02-09 | `jumpHeight` | `jumpHeight_borelli`, `jumpHeight_same_actual` |
| ch02-10 | `VelocityScalesAsSqrt` | `froudeSpeed_sqrt`, `flightSpeed_sqrt`, `pendulumWalkSpeed_sqrt`, `locomotion_speed_sqrt` |
| ch02-12 | `surfaceToMass` | `surfaceToMass_similar`, `surfaceToMass_const_iff` |
| ch02-15 | `sphereSurface` | `division_total_surface`, `division_increases_surface`, `division_restores_surface_ratio` |
| ch03-07 | `weightOfLength` | `weightOfLength_ratio`, `weightOfLength_hasDerivAt` |
| ch03-21 | `vantHoffRate` | `vantHoffRate_shift`, `vantHoffRate_q10` |
| ch03-23 | `seasonalGrowth` | `seasonalGrowth_damped`, `seasonalGrowth_annual` |
| ch03-30 | `regenVelocity` | `regen_log_linear`, `regenVelocity_family`, `regenVelocity_decreasing` |

Three of these are only partly formalized; each `scope_note` says what is left to data:
- **ch02-02:** Greenhill's buckling law (critical height \(\propto d^{2/3}\)) is taken as the definition rather than derived, and the 300 ft limit for the Kew pine isn't proved.
- **ch02-05:** only the cube-versus-square scaling is proved. Thompson's predictions about equal yearly distance and fatigue don't follow from the scalings alone.
- **ch02-06:** the \(L^{7/2}\) law is stated as \(W^2 \propto L^7\), which avoids real powers. The claim's "≈ 1.4" is proved as \(1.4 < \sqrt{2} < 1.42\).

I didn't touch any file outside the module and its report.

_Tools used: Grep, Read, Shell ×6, StrReplace ×7, UpdateCurrentStep ×3, Write ×2_
