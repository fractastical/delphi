# Subagent: Lean: Wolfram digits and substitution

- **Parent chat:** [none of the wolfram ones got verified](../2026-10-31_1244_none-of-the-wolfram-ones-got-verified.md)
- **Started:** 2026-10-31 12:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:07 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** aborted
- **Transcript ID:** `88694f78-772e-48a0-b10d-8a68dd67e638`

---

### 2026-10-31 12:49 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci. Follow books/wolfram-nks/lean/INSTRUCTIONS.md exactly (read it first, plus the BEST_PRACTICES.md sections it names). Your module is `Digits`: write books/wolfram-nks/lean/WolframLaws/Digits.lean and books/wolfram-nks/lean/reports/Digits.json. Do not touch any other module or report (other agents are writing Finite, Additive, Logic in parallel).
> 
> Your claim ids, in claims.json order (look them up in books/wolfram-nks/claims.json): wolfram2002-ch02-17, wolfram2002-ch03-10, wolfram2002-ch03-13, wolfram2002-ch04-14, wolfram2002-ch04-15, wolfram2002-ch04-18, wolfram2002-ch04-19, wolfram2002-ch05-07, wolfram2002-ch10-14, wolfram2002-ch10-23, wolfram2002-ch11-09.
> 
> Suggested targets (use your judgement; faithfulness beats count):
> - ch04-14: base-b digits of a rational p/q (0 ≤ p/q < 1, q > 0) are eventually periodic with period ≤ q - 1 (or ≤ q if that is what you can prove; then correct the notation and say so) via the remainder recursion r ↦ b·r mod q and pigeonhole; and conversely an eventually periodic digit sequence gives a rational number. Define digits by the remainder recursion and relate it to the real number if you can (e.g. digit n = ⌊b^{n+1} x⌋ mod b); at minimum both directions must be about the same notion of digit sequence of a real number.
> - ch04-19: the shift map x ↦ fract(2x) on [0,1) shifts binary digits: digit n of fract(2x) equals digit (n+1) of x, with digit n x := ⌊2^{n+1} x⌋ mod 2; hence its iterates read off the initial digits (the map adds no information). The 'random only if initial digits random' part follows as the interpretation: say so in scope_note.
> - ch03-13: a tag system that deletes one element per step and appends σ(head) acts as the neighbour-independent substitution σ: after |w| steps, w becomes σ(w) (flatMap), so iterating gives σ^n(w) on the 'generation' boundaries. Prove it over List.
> - ch03-10, ch05-07, ch11-09: 'neighbour-independent substitution ⇒ nested' needs a notion of nested; a faithful core is self-similarity: σ^(n+1)(w) = σ^n(σ(w)) and σ^(n+m) a = flatMap σ^n (σ^m a) (each level is the concatenation of copies of earlier levels), possibly plus: for uniform σ of length k, letter at position i of σ^n(a) is determined by the base-k digits of i (automaticity). Only mark formalized if the theorem genuinely captures 'nested'; otherwise decline with reason. ch11-09's claim that such systems cannot emulate rule 30 is not provable here.
> - ch04-15 (automatic sequences are never algebraic irrationals: Adamczewski–Bugeaud 2007), ch04-18 (continued fractions of sine crossings), ch02-17 (primes 'seem random'), ch10-14 (statistical non-randomness), ch10-23 (no universal regularity detector; you may decline or relate to Kolmogorov complexity uncomputability if you judge it faithful — probably decline): decline with precise reasons, noting when the result is known in the literature.
> 
> Check with `cd books/wolfram-nks/lean && lake env lean WolframLaws/Digits.lean` (≈90 s per check; keep iterating until clean). Return: module path, counts formalized / not-formalized, theorem names, and confirmation of the #print axioms check.

**Assistant:**

I'll start by reviewing the instructions provided.

There's a conflict: claims.json order puts a not-formalized entry first, but the rule says the first entry must be formalized if any exist. I'll resolve this by placing a formalized claim first out of order, then listing the rest in their original sequence.

I should lead with the formalized claim since it stands out, then follow the rest in claims.json order — moving ch03-10 to the front. Now I need to pull the page texts for each claim: ch03-10, ch03-13, ch04-14, ch04-19, ch05-07, and ch11-09.

I'm planning the Lean module structure, defining substitution via flatMap over a word and iterating it n times, then working out a nested theorem showing that iterating the substitution n+m times equals composing the n-fold and m-fold iterations.

The key property is that substitution distributes over concatenation, so iterating it n times on any word is just mapping each letter to its own n-fold substitution and concatenating the results — this captures Wolfram's observation that patterns are built from identical nested pieces, where every occurrence of a letter always gets subdivided the same way. I'm also noting that for a uniform substitution (where every letter maps to a block of the same length k), the n-fold iterate of a single letter has length k^n, and want to express how letters at a given position relate across iteration levels, though the cleanest formulation is just the recursive unfolding of one more level of substitution.

I'm working out the main theorem statement using option binding to track digit-based indexing, then trying to prove the key uniform-length lemma by induction on the word and index, splitting into the base case where the position falls within the first block and the inductive case where it shifts into the remainder of the flatMap.

Switching to least-significant-first digits, I can express the letter lookup as a foldr over the digit list, and induction using iterate_succ_apply' shows this matches the recursive substitution structure — essentially confirming that reading base-k digits of the position with a finite automaton computes the letter, which is exactly the Cobham characterization I'm after.

With chapters 3-10 formalized, covering both the block decomposition and automaticity theorems, I'm noting that non-uniform substitutions like Fibonacci give morphic sequences that are nested only in a generalized sense, while the automaticity theorem requires uniformity. Now I want to turn to chapters 5-7 on 2D geometric replacement: formalizing a geometric replacement rule as a finite set of affine contraction maps applied independently, where the level-n set is the union over length-n words of composed maps, giving a clean self-similarity recursion from level n to level n+1.

I'm working out whether geomStep commutes with image under f, since that symmetry would justify why n+1 steps from a single shape decomposes into |fs| transformed copies of the n-step pattern, composing chains of maps g1∘...∘gn applied to the base shape.

That only holds if the pieces genuinely behave independently, which requires representing elements as similarity transforms in their own frame — so each shape h''X0 gets replaced by h∘f for every f in the rule, meaning the composition order, not raw set unions, is what actually captures the self-similar structure.

I can generalize this: let M be any monoid (affine similarities, Function.End, whatever), represent elements as a set of monoid elements, and define the step as left-multiplying every current element by each generator in fs, starting from the identity.

Then I want to prove level(n+1) equals the union over generators f of f composed with everything in level n. By induction, using associativity of the monoid, I can show level n is exactly the set of products f*h where f is a generator and h is in the previous level — the base case checks out since step{1} gives fs itself, and the inductive step follows by just regrouping the product f*(h*g) via associativity.

This matches the classical IFS Hutchinson self-similarity, where attractor approximants satisfy K_{n+1} = ⋃ f_i(K_n), giving a nested faithful core. I'm now defining the geometric step function where each placement h is replaced by h ∘ f for f in the transformation set, building up geomLevel as iterated application starting from identity, then constructing geomPattern from this.

I'm proving the successor relations for both geomLevel and geomPattern, showing how each level unfolds in terms of the previous one via union over the transformation set. For the 1D case, this connects to substitution systems from earlier chapters, letting me reuse the substIter_flatMap theorem. For the "cannot emulate rule 30" claim, that's not provable in this formalization—I could at least capture the first clause about nestedness using earlier scope theorems.

I'm now considering whether there's actually something provable hiding in the rule 30 non-emulation claim, since rule 30's center column periodicity is a genuinely open Wolfram prize problem—so proving non-emulation outright isn't feasible here.

For ch03-13, I'm setting up a tag system with a tagStep function that processes lists by moving the head element through substitution σ, then proving that iterating this step by the list's length applied to a concatenated sequence yields the tail plus the substituted prefix, which gives a clean recursive characterization of the tag system's evolution.

I then want to track generation boundaries — defining step counts t_n as cumulative sums of substitution lengths across generations, and proving that applying tagStep exactly t_n times reproduces the n-th substitution iterate. The proof goes by induction, splitting the sum at n+1 into the sum at n plus the length of generation n, then using the iterate-addition lemma (f^[m+n] x = f^[m] (f^[n] x)) to combine the two applications.

The induction step checks out via the inductive hypothesis, and the edge case where σ a is empty still holds since lengths depend only on u. I'm noting this scope applies through ch03-10's repetitive/nested case, then moving to ch04-14 on digits of rationals, where I need to define the digit function for reals in [0,1) using floor and mod in a given base.

I'm setting up the rational case with x = p/q, defining the remainder recursion r_0 = p, r_{n+1} = b·r_n mod q with digit_n = (b·r_n)/q, and working through the algebra to show this matches the floor-mod digit formula by expanding b^(n+1)p as b times the division of b^n p by q.

I should instead define the digit using nat floor since x is nonnegative in [0,1): digit b x n := ⌊b^(n+1) * x⌋₊ % b, relying on a nat floor division lemma. Then I want to show periodicity: the digit at n depends only on r_n = b^n p mod q, since b^(n+1)p = b*(q*(b^n p/q) + r_n), reducing to (b*r_n)/q mod b.

The remainders r_n satisfy r_{n+1} = b*r_n mod q, and since there are only q possible values, pigeonhole among r_0 through r_q gives a repeat within q+1 terms, so the sequence is eventually periodic with period at most q.

The special case q=1 breaks a bound of q-1 since x=0 gives digits 0,0,0... with period 1 > 0, so I should prove period ≤ q generally, or handle q=1 separately. Excluding zero remainders, the nonzero values live in {1,...,q-1}, giving q-1 possibilities, so pigeonhole on r_0 through r_{q-1} should yield the tighter bound of q-1 when r_n is never 0.

I can split into two cases: either the remainder eventually hits zero, in which case it stays zero forever with period 1, or it never hits zero, in which case it stays within the q-1 nonzero residues, giving a period bounded by q-1. So for q ≥ 2, the period is always between 1 and q-1.

I'm proving this via pigeonhole: mapping the sequence values into a finite set over a range larger than the set's cardinality forces two equal values at indices i<j, giving a period j-i bounded by the set size, and then showing eventual periodicity follows by induction from that repeated equality.

For the modular exponentiation sequence specifically, I'm trying to establish the recurrence r(n+1) = b·r(n) mod q directly using Nat.mul_mod, working through how to pull the mod outside the multiplication correctly.

For the converse direction, I need to show that if a digit sequence is eventually periodic, the number it represents is rational—this likely requires expressing x as the series sum of digits times powers of b, then arguing the periodic tail forms a geometric series.

So x must be rational since that difference is a nonzero integer multiple. I can show y_m equals y_{m+per} directly: if digits match from m onward, the difference D_k = y_{m+k} - y_{m+per+k} satisfies D_{k+1} = b D_k, so D_k = b^k D_0, but |D_k| stays bounded under 1 for all k, forcing D_0 = 0 — a purely elementary argument with no series needed.

Now I'm working out how to formalize this with real-valued fractional parts, defining the digit function using floor and mod, and searching Mathlib for lemmas relating integer floor division to rational floor computations.

Splitting the floor into b times the previous floor plus the floor of b times the fractional part lets me reduce mod b, since the digit term is already bounded between 0 and b, so it survives the mod unchanged via Int.add_mul_emod_self_left and emod_eq_of_lt. This gives the recurrence for the fractional part at the next step as b times the current fractional part minus the digit just extracted.

Now I'm setting up the periodicity argument: assuming the digit sequence repeats with period "per" starting at index m, I show by induction that the difference between fractional parts at shifted indices scales by b^k each step, but since both fractional parts lie in [0,1) their difference is bounded by 1, forcing b^k times a fixed nonzero difference to stay bounded — which fails for b ≥ 2 as k grows, so the difference must be zero.

From that equality, I extract that b^(m+per)x - b^m x equals an integer N, giving x as N divided by (b^(m+per) - b^m), and I verify the denominator is nonzero since b^per > 1. I then construct the rational r = N/(b^(m+per) - b^m) and cast it back to reals to conclude x equals this rational.

Now I'm reconsidering whether the converse direction actually requires x to lie in [0,1), and I think it doesn't — the digit extraction via floor and mod works for any real x, including negatives, since the recursive relation b*⌊b^n x⌋ + ⌊b*y_n⌋ still holds. So I could state the converse more generally for all real x, though the forward direction still needs 0 ≤ p < q.

I'm now framing the two theorems: one showing rationals have eventually periodic digit expansions (for p < q, 1 < q, b ≥ 2), and a full iff version restricted to x ∈ [0,1), where eventual periodicity of digits is equivalent to x being rational, with the rational representation p/q satisfying 0 ≤ p < q.

I'm working through the shift map T x = fract(2x) for binary digits, showing digit 2 (T x) n = digit 2 x (n+1) holds for all real x by analyzing the floor function modulo 2, then extending this to iterates of T so that digit 2 (T^[k] x) n relates to digit 2 x (n+k).

I'm also noting that T^[k] x = fract(2^k x), which gives a determinism result: if two numbers agree on all their binary digits, then their entire forward orbits under T agree on all digits too — a trivial but useful corollary of the digit-shift theorem.

Now I'm working out the proof that shifting preserves digits correctly: expanding Int.fract(2x) in terms of floor, applying floor_sub_int to handle the integer subtraction, then reducing the resulting expression mod 2 by factoring out the power of 2 so the floor term vanishes modulo 2.

Turning to the ch04-15 claim, Adamczewski–Bugeaud's 2007 Annals result establishes transcendence for automatic irrational numbers, but the problem statement as phrased seems false since rational roots can have periodic digit sequences, which are themselves trivially automatic.

I'll note the Sturmian/general morphic result is murkier, so I'll stick to the automatic (uniform substitution) case as the solid claim. For problem 18, I'm factoring sin x + sin(ax) into a product of sines, which shows the zeros split into two arithmetic families whose interleaving pattern forms a Sturmian-type sequence governed by the continued fraction expansion of (a-1)/(a+1).

For the quadratic irrational case, a full proof would need Sturmian substitution theory (Crisp-Moran-Pollington-Shiue, Yasutomi) that isn't available in Mathlib, so I'll decline to formalize that and just note it as background.

For the empirical "seems random" claim, this is a heuristic statement rather than a provable mathematical fact like the prime number theorem or Cramér's model, so I'll decline.

For the block-frequency claim, equal frequencies across lengths don't imply randomness — Champernowne's sequence is the standard counterexample, being provably normal yet highly non-random in structure.

Rice's theorem is actually close here, but the real target is undecidability of Kolmogorov complexity bounds — deciding K(x) ≤ c isn't computable, and building that from scratch in Lean would be heavy given Mathlib lacks a Kolmogorov complexity framework. Also the informal notion of "simple description" doesn't map cleanly onto Wolfram's actual argument about computational irreducibility, so I'll decline but note the nearest formal analog.

Tallying up: formalizable ones are ch03-10, ch03-13, ch04-14, ch04-19, ch05-07 (5 total), while ch02-17, ch04-15, ch04-18, ch10-14, ch10-23, ch11-09 should be declined (6 total) — ch11-09's claim about rule 30 emulation isn't provable here either, consistent with the others.

Now I should start writing the Lean proofs, first checking which Mathlib lemma names actually exist by searching the local library.

For the rational case, I'm thinking of using a floor characterization lemma: expressing the floor of b^(n+1) times x as a natural number division, then proving it via the standard floor equivalence condition and connecting it to division identities for natural number casts.

_Tools used: Grep, Read, Shell ×6, UpdateCurrentStep ×2, Write_

_Turn ended: aborted_
