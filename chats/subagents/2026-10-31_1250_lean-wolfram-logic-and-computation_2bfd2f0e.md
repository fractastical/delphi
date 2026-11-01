# Subagent: Lean: Wolfram logic and computation

- **Parent chat:** [none of the wolfram ones got verified](../2026-10-31_1244_none-of-the-wolfram-ones-got-verified.md)
- **Started:** 2026-10-31 12:50 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:07 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** aborted
- **Transcript ID:** `2bfd2f0e-a8f3-4f86-a6d5-5f0ba3c7ebd8`

---

### 2026-10-31 12:50 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci. Follow books/wolfram-nks/lean/INSTRUCTIONS.md exactly (read it first, plus the BEST_PRACTICES.md sections it names). Your module is `Logic`: write books/wolfram-nks/lean/WolframLaws/Logic.lean and books/wolfram-nks/lean/reports/Logic.json. Do not touch any other module or report (other agents are writing Finite, Additive, Digits in parallel).
> 
> Your claim ids, in claims.json order (look them up in books/wolfram-nks/claims.json): wolfram2002-ch01-07, wolfram2002-ch01-10, wolfram2002-ch11-06, wolfram2002-ch11-07, wolfram2002-ch11-10, wolfram2002-ch11-11, wolfram2002-ch11-14, wolfram2002-ch11-27, wolfram2002-ch12-04, wolfram2002-ch12-09, wolfram2002-ch12-21, wolfram2002-ch12-22, wolfram2002-ch12-26, wolfram2002-ch12-27, wolfram2002-ch12-30, wolfram2002-ch12-31, wolfram2002-ch12-32, wolfram2002-ch12-34, wolfram2002-ch12-35, wolfram2002-ch12-39, wolfram2002-ch12-40, wolfram2002-ch12-42. (Verify the claims.json order and use it in the report.)
> 
> Suggested targets (use your judgement; faithfulness beats count):
> - ch12-39: strings of length n over a finite alphabet with a fixed-point-free involution `neg` (negation), and T the set of generated theorems of that length. Define consistent (no s with s ∈ T and neg s ∈ T) and complete (for every s, s ∈ T or neg s ∈ T). Prove: card T > half ⇒ inconsistent; card T < half ⇒ incomplete; complete ∧ consistent ⇒ card T = half. Note that exactly half does NOT imply complete and consistent (give a counterexample, ideally as a Lean theorem), so Wolfram's 'exactly when' is only one direction; say so in scope_note and correct the notation. If the length-preserving involution in the claim can have fixed points, address that (with a fixed point no consistent complete system exists for strings that equal their negation).
> - ch12-31: using Mathlib's computability (ComputablePred, RePred, `ComputablePred.computable_iff_re_compl_re`), prove: if the set of provable statements and the set of refutable statements are both r.e. (e.g. images of a partial recursive enumeration) and the system is complete and consistent (refutable = complement of provable), then provability is decidable; contrapositive: an undecidable provability predicate forces incompleteness or inconsistency. Model the multiway system abstractly over ℕ-coded strings; keep it faithful to the claim.
> - ch11-10 (transitivity of emulation + existence of a universal CA ⇒ universal examples) is close to definitional; formalize only if you can make the conclusion non-trivial, else decline.
> - ch12-42: Wolfram's single Nand axiom ((p·q)·r)·(p·((p·r)·p)) = r. Its soundness (a Boolean identity for Nand) is easy by decide, but completeness for propositional logic is the actual claim and is a long equational derivation: decline unless you formalize completeness; at most mention soundness in the reason.
> - ch12-22: PCP is decidable for 2 pairs and undecidable for ≥ 5 (Neary 2015), open for 3 and 4; Wolfram's 'already with three pairs ... undecidable' is not established: decline and say so.
> - Everything else (rule 110 universality ch11-14, 2,5 Turing machine ch11-27, universal CA ch11-06, P≠NP ch12-26, NP-completeness for rule 30 ch12-27, Gödel/arithmetic ch12-34/35/30/40, ch12-32 universality of axiom systems, heuristics 'almost all', ch01-07/10, ch11-07, ch11-11 (Minsky/Conway fractran style: decline unless a faithful core is feasible), ch12-04, ch12-09, ch12-21): decline with precise reasons, noting when the statement is a known literature result (e.g. Cook 2004 for rule 110; Matiyasevich for Diophantine universality; Conway 1972 for generalized Collatz functions) versus open or heuristic.
> 
> Check with `cd books/wolfram-nks/lean && lake env lean WolframLaws/Logic.lean` (≈90 s per check; keep iterating until clean). Return: module path, counts formalized / not-formalized, theorem names, and confirmation of the #print axioms check.

**Assistant:**

I'm starting by reviewing the instructions provided.

Now the claims.

The order matches the iteration order of claims.json, so that checks out. Now I need to check the book pages for chapters 12-39 and 12-31 to verify those references.

Wolfram's framing of negation as a length-preserving involution with possible fixed points gives me a concrete model: strings as functions from a finite index set to an alphabet, with negation as a self-inverse map on that type.

I'm defining consistency (a set T never containing both a string and its negation) and completeness (every string or its negation is in T), then working through the cardinality arguments: injectivity of negation forces disjointness of T and its image, giving 2|T| ≤ |S| whenever T is consistent, and completeness forces the reverse inequality, so together they pin down 2|T| = |S|. The fixed-point case is special—if negation fixes some string s, that s can't belong to any consistent T, yet completeness forces s into T, so no set can be both complete and consistent when fixed points exist.

Now I want a counterexample showing the converse fails: having exactly half the elements doesn't guarantee completeness or consistency. I'm constructing a concrete case with length-2 bit strings under bitwise negation (00↔11, 01↔10), picking T={00,11}—exactly half the universe—but it's neither consistent (contains both 00 and its negation 11) nor complete (missing 01 and 10), something I can verify by decision procedure.

I'm also considering whether to connect this to a more faithful multiway-system model, defining rewrite rules and taking T as the set of strings reachable from a starting string at a fixed length, rather than just an arbitrary subset satisfying the cardinality condition.

I'm thinking a more faithful approach would define a Multiway structure with rewrite rules and a step relation, then derive theorems via reflexive-transitive closure, eventually restricting to fixed-length words using Vector types.

Rather than fighting with Vector/Fintype instances, I realize it's simpler to express length-n strings as sets of lists satisfying a length predicate, then define consistency and completeness at length n directly in terms of derivability and its negation, with cardinality bounded by the alphabet size raised to n.

Now I'm working out the counting argument: the theorem that if twice the size of the derivable set exceeds the total word count then the system can't be consistent at that length requires showing negation is injective (so it preserves cardinality) and that the finiteness of length-n word sets holds, which I suspect comes from a Mathlib lemma about lists of fixed length over a finite alphabet being finite.

I'm also sketching the formal setup: a negation operation on lists that preserves length and is an involution, letting me state Wolfram's completeness-and-consistency claim per length rather than globally, with consistency meaning no string and its negation are both derivable. Then I'm thinking ahead to how chapters 12-31 would be modeled abstractly as a multiway system with a recursively enumerable derivability relation.

The key lemma I want: if the derivability predicate is complete and consistent, then it's actually decidable, since under those assumptions the complement of the derivable set equals the set of strings whose negation is derivable, and since negation is computable and derivability is r.e., that gives me an r.e. complement too—making the whole predicate computable.

Proving full r.e.-ness of multiway derivability from scratch would be a large effort, so instead I'll take it as an honest explicit hypothesis — essentially formalizing Wolfram's "one just runs the system" as `RePred (m.Derives tru)` over a general Primcodable type of strings, rather than trying to derive it from more primitive assumptions.

I'll structure the theorem as `computable_of_complete_consistent` with its contrapositive giving undecidability implies incompleteness-or-inconsistency, keeping the formalization tied closely to the specific claim rather than a generic fact.

For the remaining items, I'm deciding to decline attempting emulation transitivity and soundness mentions since they're too close to definitional or overreach the suggestion's scope. Now I'm moving into checking Lean API names like `Set.ncard_image_of_injective` and `Set.ncard_union_eq` to make sure the finite set cardinality lemmas I need actually exist before writing the file.

I'll write the module with a simple import of Mathlib rather than its own public section, taking a quick look at Thompson's module header for stylistic conventions first.

I'm defining a Lean structure for multiway string rewriting systems, with a step relation that applies rules by splitting strings into prefix/suffix plus matched pattern, then building toward a derivation relation as the transitive closure.

With that, I set up per-length and global notions of consistency and completeness relative to a negation function, planning to prove the stronger per-length statements first: if negation is length-preserving and injective, then consistency at length n means theorems and their negations are disjoint subsets of strings of that length, giving a counting bound, while completeness at n means every string of that length is either a theorem or has a theorem negation.

I also want a theorem stating when exactly half are derivable the system is on the boundary, plus one showing a fixed point of neg blocks both completeness and consistency together. I'm trying to construct an explicit Boolean counterexample at length 2 with negation as "not," checking which strings get derived from the single rule to confirm the reachable set is exactly {ff, tt}, making the system neither fully complete nor fully consistent.

To prove that invariant rigorously, I'd induct on the reflexive-transitive closure, showing from ff the substitution forces empty prefix/suffix (yielding tt), and from tt no matching substring exists at all—using length arguments to pin u and v to the empty list.

Beyond that, I still need: ncard of the length-2 reachable set is 2, inconsistency at position 2 is easy since both ff and its negation are derivable, but completeness failing there needs the same invariant, plus ncard of all length-2 boolean strings equals 4, which I can verify by explicitly listing the four strings and computing the set cardinality directly.

I'm proving that if derivability is RE and negation is computable with completeness and consistency, then derivability is a computable predicate, using the fact that a set and its complement both being RE implies decidability — the complement RE-ness comes from composing the derivability RE proof with the computable negation, then showing equivalence via consistency and completeness.

This gives the contrapositive: undecidability plus consistency forces the existence of statements where neither the statement nor its negation is derivable. I also need to check whether the global consistency/completeness notions match the per-length versions used elsewhere, since the global definitions should imply the length-indexed ones.

For the negation map in the later argument, I'll assume it's any length-preserving involution, with hypotheses that it preserves string length and is involutive — for counting purposes I really just need injectivity, which follows from the involution property.

I'm checking the negation case uses the global Consistent lemma correctly, and confirming exists_undecided produces the right hypothesis after push_neg. Let me run it to verify.

_Tools used: Grep, Read ×3, Shell ×8, UpdateCurrentStep ×2, Write_

_Turn ended: aborted_
