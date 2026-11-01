# Subagent: Lean: Wolfram additive rules

- **Parent chat:** [none of the wolfram ones got verified](../2026-10-31_1244_none-of-the-wolfram-ones-got-verified.md)
- **Started:** 2026-10-31 12:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:07 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** aborted
- **Transcript ID:** `c7d911ac-33f1-48af-bad7-4df68839d4e9`

---

### 2026-10-31 12:49 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci. Follow books/wolfram-nks/lean/INSTRUCTIONS.md exactly (read it first, plus the BEST_PRACTICES.md sections it names). Your module is `Additive`: write books/wolfram-nks/lean/WolframLaws/Additive.lean and books/wolfram-nks/lean/reports/Additive.json. Do not touch any other module or report (other agents are writing Finite, Digits, Logic in parallel).
> 
> Your claim ids, in claims.json order (look them up in books/wolfram-nks/claims.json): wolfram2002-ch06-15, wolfram2002-ch06-19, wolfram2002-ch06-20, wolfram2002-ch10-17, wolfram2002-ch11-20.
> 
> Suggested targets (use your judgement; faithfulness beats count):
> - Use configurations ℤ → ZMod 2. rule90 x i = x (i-1) + x (i+1); rule150 x i = x (i-1) + x i + x (i+1). Show these agree with the elementary rule tables 90 and 150 on Bool if you define those too.
> - ch06-15: rule 90 is additive (step (x + y) = step x + step y, hence for iterates), so the evolution from any initial condition is the superposition (sum of shifted copies) of the single-cell evolution; consequently all pattern content comes from the initial condition. The 'low density persists, unlike rule 22' part is empirical/statistical: put it in scope_note.
> - ch06-20 and ch11-20: the 2^k-step law: rule90^[2^k] x i = x (i - 2^k) + x (i + 2^k) (induction using additivity and char 2), and the analogous rule150^[2^k] x i = x(i-2^k) + x i + x(i+2^k). This is the self-emulation (blocks of size 2^k evolve like single cells) and the 'simple superposition of shifted copies after 2^k steps'. Also, if feasible by decide: the elementary rules (Fin 256 tables on Bool³) that are additive (f(a⊕a',b⊕b',c⊕c') = f(a,b,c)⊕f(a',b',c')) are exactly {0, 60, 90, 102, 150, 170, 204, 240}, and up to the trivial ones (0, identity 204, shifts 170/240) and left-right reflection (60↔102) the non-trivial ones are 90, 60/102 and 150 — state carefully what Wolfram's 'only fundamentally different additive rules are 90 and 150' amounts to and whether it is accurate. Rule 184 self-emulation is optional. Non-universality of rules 90/150 (ch11-20) is not provable here without a formal definition of universality: formalize the superposition core and say so in scope_note, or decline if you judge the core too thin.
> - ch06-19 (self-emulation ⇒ nested) needs a definition of 'nested'; you may formalize it for rule 90 as the Sierpiński/Pascal-mod-2 law (single-cell evolution at time t, position i is Nat.choose t ((t+i)/2) mod 2 with parity condition) or Lucas-style self-similarity, else decline.
> - ch10-17 (hypergeometric formulas 'probably' exist) is a conjecture: decline.
> 
> Check with `cd books/wolfram-nks/lean && lake env lean WolframLaws/Additive.lean` (≈90 s per check; keep iterating until clean). Return: module path, counts formalized / not-formalized, theorem names, and confirmation of the #print axioms check.

**Assistant:**

I'll start by reading through the instructions first.

I'm thinking about checking pages 271 and 696 for details on rule 150's relationship to additive cellular automata, then sketching out a Lean namespace defining rule90 and rule150 as configurations over ZMod 2 using neighbor sums.

I want to set up an elementary CA rule table that extracts output bits from a rule number based on neighborhood patterns, then prove rule90 and rule150 correspond to XOR combinations of neighbors. I'm planning to bridge between a Boolean-based ECA step function and the ZMod 2 additive formulation via a conversion function, then prove additivity by showing rule90(x+y) equals rule90(x)+rule90(y) through function extensionality.

From there I want to extend additivity to iterated applications by induction, and establish that the rule commutes with shifts, so that any finitely-supported initial configuration can be decomposed as a sum of shifted delta functions. This superposition principle would let me express the evolution at time t as a sum over the support set of scaled, shifted copies of how a single delta function evolves.

I'm thinking about proving additivity by finite induction over sums, then generalizing to a lemma covering any function that's additive, scalar-compatible, and shift-commuting so I can instantiate it for both rule 90 and rule 150, handling the ZMod 2 scalar cases by checking 0 and 1 separately.

The cleanest route is to represent any finitely-supported initial configuration as an indicator function over a finite set s, then show the evolved pattern at time t equals a sum of shifted single-cell patterns indexed by s -- this directly captures the idea that all pattern content is a superposition of the initial condition's shifted contributions.

Actually there's an even stronger and fully general formula: for any configuration x, rule90^[t] x i equals the mod-2 binomial-weighted sum of x over the range [i-t, i+t], using Pascal's rule, provable by induction via f^[n+1] x = f^[n] (f x). This gives an explicit superposition formula valid for arbitrary configurations, not just finitely supported ones.

I'm working through the Pascal's rule identity via splitting the sum at k=0, using Finset.sum_range_succ' to peel off terms and matching coefficients C(t,k)+C(t,k+1) to rebuild the combined sum.

This simplifies nicely: substituting i = 2k - t collapses the indicator to a single term where k' = t - k, giving exactly C(t, t-k), confirming the Pascal-mod-2 structure for single-cell evolution with specific index substitutions handling the parity and boundary cases.

For the nested/Sierpinski structure, I'm thinking the evolution at time 2^k + t decomposes via the 2^k shift law plus linearity into two shifted copies of the pattern at time t, since rule90^[2^k] applied to δ splits into a left and right shifted delta. These copies stay disjoint when t < 2^k because the support of rule90^[t]δ is bounded within that range.

I'm also thinking about formalizing self-emulation directly: spreading a configuration by factor 2^k and applying rule90 2^k times should equal spreading the single-step evolution, which follows from the 2^k doubling law plus a simple integer division identity relating (i-2^k)/2^k to i/2^k - 1.

That's actually a nice faithful self-emulation identity: rule 90 scaled by 2^k equals spread composed with rule90 itself, and the same holds for rule 150. More generally, any additive radius-1 rule emulates itself under 2^k-fold iteration since the Frobenius structure over ZMod 2 lets the coefficients just shift to spacing 2^k.

This covers all eight additive elementary rules uniformly. I'm setting up the general linear rule as a weighted sum of neighbors, then proving by induction on k that iterating it 2^k times just spreads the same coefficients out to distance 2^k, using the additive property of iteration counts to split 2^(k+1) into two applications of the inductive hypothesis.

I'm thinking I can brute-force this identity in ZMod 2 by stating it as a universally quantified claim over all eight boolean coefficients and variables, then letting `decide` check all 256 cases directly rather than manually simplifying with ring arguments.

Next I need to handle the index arithmetic connecting iterate steps, aligning terms like i - 2^k - 2^k with i - 2^(k+1), then move on to classifying elementary rules 90 and 150 as additive by checking their truth tables against the XOR structure over neighboring cells.

For the actual theorem that only {0, 60, 90, 102, 150, 170, 204, 240} are additive, I'm weighing whether `decide` can brute-force this over all 256 rules and 64 boolean triples efficiently, given that Nat.testBit and related bitwise ops are GMP-accelerated in the kernel, but I suspect Finset equality decidability might still be too slow and I may need a different proof strategy.

The 8 additive rules correspond exactly to the 8 (α,β,γ) combinations: 0 is trivial, 204 is identity, 170 shifts left, 240 shifts right, and 60, 102, 90, 150 are various XOR combinations of the three cells. I'm noting that rules 60 and 102 look like sheared versions of rule 90, both still generating Pascal's triangle patterns under a different lattice embedding.

I'm working out the algebraic relationship precisely: rule 60 is a shift plus XOR of neighbors, rule 90 is XOR of the two outer neighbors, and I'm trying to show one is a sheared/sublattice version of the other by tracking how applying rule 90 twice spreads values two cells outward, mirroring rule 60's single-step spread.

I'm trying to formalize this precisely: defining a sublattice embedding y(j) = x(2j+r), then showing rule90 applied at odd offsets matches rule60 applied to that sublattice, working through the index algebra to confirm y(j)+y(j+1) matches rule60's output at j+1.

Completing the induction confirms rule 102 is rule 90 run on a skewed sublattice, with rule 60 as its mirror image — provable by checking the elementary tables directly. So I can now state the classification theorem alongside this 90/102 relation and the 60↔102 reflection, noting Wolfram's claim holds up to this trivial reparametrization.

I also wonder whether rule 150 could be shown equivalent to 90 under similar lattice tricks, but that distinction doesn't seem to have a clean formalized proof, so I should flag it as unresolved rather than assert it. Separately, I'm considering whether additivity over elementary rules can be captured by a clean algebraic characterization — something like each rule being expressible as a linear combination over ZMod 2 of its three inputs, which might also be checkable by decidability on the finite table.

For the superposition argument itself, I need to formalize the core doubling law that rule 90/150 iterated 2^k times produce shifted copies, since this is the actual mathematical premise Wolfram leans on — but the stronger conclusion about non-universality isn't something I can prove, so I'll note that gap explicitly in the scope note rather than overstate what's formalized.

I'll formalize the 2^k superposition core with a clear scope note that non-universality itself isn't proved, reusing shared definitions but giving separate theorems for rule 90 and rule 150 under ch11-20, plus the generic linear rule classification for ch06-20. I also need to cover ch06-15's additivity and superposition theorems.

For rule90 I plan to include addition, iterate-addition, finite-support superposition, and the binomial formula for arbitrary initial states, since the binomial identity already demonstrates the evolution is a fixed linear function. I'll leave the low-density persistence idea out with a scope note, and for ch06-19 cover the single-cell Pascal triangle value, the zero conditions off the light cone or wrong parity, the nested 2^k decomposition, and self-emulation properties.

I want to place the general additive self-emulation theorem in ch06-20 and reference it from ch06-19. I should double check the Wolfram rule numbering convention—verifying that rule 90 corresponds to left-xor-right by checking which bits are set in 90's binary representation against the neighborhood codes, and similarly work out rule 102's neighborhood mapping.

I continue checking: rule 60 matches left-xor-center, rule 170 reduces to just the right neighbor (shift), rule 240 to the left neighbor, and rule 204 to the identity on the center cell. Now I'm setting up the Lean file, starting with the import and defining a Config type as bi-infinite sequences of ZMod 2 cells, then beginning the definition of the elementary rule function based on Wolfram's numbering of left/center/right neighbor combinations.

Defining more rule functions...

Then I want to prove rule90's table matches the linear rule by unfolding definitions, generalizing the three boolean values involved, and deciding the resulting finite case split automatically.

Decide without native_decide should be fine since it avoids extra axioms. I'm sketching additivity proofs for rule90 over both single steps and iterates, using funext and ring to show linearity, then planning to generalize everything through the linRule framework so both rule90 statements fall out as special cases.

I'm now working on a shift-commutation lemma showing linRule commutes with translation of configurations, which requires juggling an index identity like i - 1 - j = i - j - 1 via sub_right_comm or congr to make the algebra line up.

For the delta function and indicator sums, I'm proving that an indicator for a finite set equals a sum of shifted deltas, using Finset.sum_ite_eq to collapse the sum into the right conditional. Then I'm setting up an additivity lemma for iterating a function that distributes over addition, building toward handling sums of shifts under iteration.

Now I'm applying this to prove the key superposition theorem for rule90: that applying the rule t times to an indicator function decomposes into a sum over the shifted iterates for each point in the set.

I also want to establish that any finitely-supported configuration can itself be expressed as an indicator over its support, since values live in ZMod 2 and nonzero means exactly 1 — this lets me state a version of the theorem in terms of a hypothesis rather than the indicator construction directly, proving it via a case split on the Boolean-like structure of ZMod 2. From there I'm thinking about how a binomial-style closed form would look for rule90 specifically, since the general linear rule would involve a trinomial expansion instead.

Now I'm working out the theorem stating that iterating rule90 t times at position i equals a sum over k of binomial coefficients times the initial state at shifted positions, proving it by induction on t: the base case is trivial, and the inductive step unfolds the iterate as the sum of two shifted applications at t steps, substitutes the inductive hypothesis into both, and needs to combine two binomial sums into the single sum for t+1 using Pascal's rule, which requires reindexing one of the sums to align the position shifts correctly.

Still working through the binomial sum reindexing...

I need to handle the cast arithmetic carefully: converting between `t` and `t+1` as integers, and verifying that exponent expressions like `i - 1 - t + 2k` and `i - (t+1) + 2k` match up after pushing casts and applying ring normalization.

Now I'm thinking about a single-cell version: applying rule90 iteratively to a delta function at position `t - 2k` should yield the binomial coefficient `t.choose k`, since terms only survive when the shifted position matches, isolating a single nonzero summand via `sum_eq_single`.

Now I need a lemma for zero outside the light cone: when the parity doesn't match or t is too small relative to |i|, the value stays zero, proving it by summing over the delta terms and showing each index condition forces the term to vanish via omega. I'm also starting to set up a nested version of the delta formula for composing two rule90 iterations.

Then I'm proving a splitting lemma using the iterate addition rule: rule90 applied for 2^k + t steps on delta decomposes as the sum of rule90^[t] delta shifted by ±2^k, combining the doubling identity with the iterate_add_apply fact. This leads into checking that for t < 2^k the two shifted copies have disjoint supports.

This is Sierpinski recursion. I'm now proving a general power-of-two law for linear rules by induction on k, with the base case using `pow_zero` and `Function.iterate_one` simplification, and the successor case combining `pow_succ`, `mul_two`, and `Function.iterate_add_apply` with four applications of the inductive hypothesis.

I'm working through the substitution carefully since the inductive hypothesis has universal quantifiers over x and i, and I need to make sure `simp only [ih]` doesn't loop by rewriting an instance into a form that still matches the pattern again.

I need to be careful that `sub_sub` and `add_assoc` apply cleanly to get the right forms, and worry that `pow_succ` might rewrite the ℕ exponent inside the iterate index too, mixing up with the ℤ arithmetic elsewhere in the goal — I should check whether `simp only [pow_succ, mul_two]` causes unwanted rewrites of other `2^k` instances.

Then rather than generalize each application term, I want to see if the key lemma applies directly once I expand `g` at the shifted indices, matching the coefficients `a, b, c` against the double application pattern.

I'm defining a self-emulation property: applying the local rule 2^k times to a spread-out configuration should match spreading the result of applying the rule once at the coarser scale. I'm working through the proof by cases on whether an index is divisible by 2^k, using divisibility witnesses to simplify the conditional expressions.

Still working out the simp lemmas...

Checking rule 150 as linRule 1 1 1, then proving the iterate-two-pow lemma for rule90 by reducing through rule90_eq and linRule_iterate_two_pow with simp. Then I'm defining additive elementary classification as a proposition over xor-linearity across all boolean inputs, and thinking about how to make it decidable since it quantifies over Bool.

For the final classification theorem, I can state that for n under 256, additivity holds iff n belongs to the specific set {0, 60, 90, 102, 150, 170, 204, 240}, and prove it by brute-force `decide` since everything reduces to finite Bool and Nat bounded checks the kernel can evaluate directly.

I'm also considering a linear characterization: additivity should correspond to the rule being expressible as an XOR of boolean-weighted left, center, and right cells, which is itself decidable since it's a bounded existential over Bool triples. Then I want to note symmetry relationships between rules, like showing rule 60 reflected equals rule 102 with left and right swapped.

Extracting the linear coefficients from additivity and showing they transport through toZMod to give the exact linRule form needed, then closing with a funext and case decision over booleans.

I'm also considering a stronger combined statement: that self-emulation lifts directly to iterated applications on Bool configurations via the spreadB bridging lemma, so the composite power map on elementaryStep matches spreadB composed with elementaryStep itself.

I'm proving the iteration step by induction on t, showing that applying F repeatedly and then mapping through toZMod matches applying G repeatedly on the mapped input. For injectivity, I'm working out that toZMod is injective on Bool by case analysis, since equal images under toZMod force equal Bool values at every index.

Now I'm assembling the final theorem about the elementary step commuting with the spread map under iteration, using the linearity of the elementary step and the injectivity/bridge lemmas just established to complete the proof.

I could also add an explicit theorem that rule 22 is not additive, provable by decide, since the writeup contrasts it with the additive rules — cheap to include given the classification already covers it. Time to write the file now, budgeting about 90 seconds per check.

Now I'm writing the module itself.

_Tools used: Read, Shell ×4, UpdateCurrentStep ×2, Write_

_Turn ended: aborted_
