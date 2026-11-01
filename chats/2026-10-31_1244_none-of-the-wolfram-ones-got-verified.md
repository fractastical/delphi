# none of the wolfram ones got verified

- **Started:** 2026-10-31 12:44 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:18 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 4
- **Subagents:** 4
- **Transcript ID:** `c5a45794-050d-4b6b-a326-93c682585baa`

## Subagents

| Started | Task | Status |
|---|---|---|
| 2026-10-31 12:49 | [Lean: Wolfram additive rules](subagents/2026-10-31_1249_lean-wolfram-additive-rules_c7d911ac.md) | aborted |
| 2026-10-31 12:49 | [Lean: Wolfram digits and substitution](subagents/2026-10-31_1249_lean-wolfram-digits-and-substitution_88694f78.md) | aborted |
| 2026-10-31 12:49 | [Lean: Wolfram finite systems](subagents/2026-10-31_1249_lean-wolfram-finite-systems_743aff42.md) | aborted |
| 2026-10-31 12:50 | [Lean: Wolfram logic and computation](subagents/2026-10-31_1250_lean-wolfram-logic-and-computation_2bfd2f0e.md) | aborted |

## Conversation

### 2026-10-31 12:44 — Turn 1 (User)

> none of the wolfram ones got verified

**Assistant:**

I'll check what "verified" means for the Wolfram claims here: whether there's a Lean project or assessment run for `books/wolfram-nks/` like Thompson's.

The user's claim about "none of the wolfram ones got verified" probably relates to Lean formalization status for the Wolfram NKS claims. I should check the repo state and recent transcripts to understand what's being referenced before responding.

I notice there's a verification field, and 52 Wolfram math claims that haven't been verified, while Thompson has a lean/ directory. That suggests the user wants Lean formalization for the Wolfram math claims, so I should check Thompson's lean instructions, the report format, and how load-claims maps verification, plus review recent transcripts for context.


All 321 Wolfram claims remain untested, with 52 flagged as math but no `lean/` project to generate a verified status like Thompson's. I'll now check how Thompson's Lean pipeline and `load-claims.mjs` produce that verified status.

Wolfram's book really has no Lean project, so I need to create one at books/wolfram-nks/lean and formalize the 52 math claims. Scanning through them, some are clearly unprovable like Rule 30 randomness, others are provable but massive like Rule 110 universality, while things like Rule 90 producing a Sierpinski pattern seem genuinely tractable to formalize.

Let me check the most recent transcript to see if there was already a plan drafted for Wolfram, similar to what was done for Thompson.


Confirmed: Thompson's 47 proved claims trace to `lean/reports/`, while `books/wolfram-nks/` lacks any Lean project, leaving its 52 math claims stuck at `untested`. Next I'll list those 52 claims to find which have a provable core and check if an earlier chat planned a Wolfram Lean pass.

I should set up a parallel books/wolfram-nks/lean project mirroring the Thompson structure and formalize what's tractable, with subagents handling modules. Rather than re-downloading Mathlib, I could try reusing or symlinking Thompson's existing .lake/packages to save time.

Scanning through the candidate claims, I'm identifying ones that feel formalizable with Mathlib: rational-to-periodic-digit equivalence, the binary shift map for doubling mod 1, pigeonhole arguments for eventual periodicity in finite deterministic systems, and periodicity properties of cellular automata.

For rule 90's additive structure over ZMod 2, I'm working out an inductive proof that the state at distance 2^k steps is a sum of shifted copies, using the fact that doubling vanishes mod 2 so composing the step map with itself telescopes nicely.

I also notice that among the 256 elementary rules, the additive ones (where f(x⊕y)=f(x)⊕f(y)) form exactly a set of 8 rules {0,60,90,102,150,170,204,240}, which could be verified by decide — useful for formalizing which rules support superposition.

For reversibility, only 6 of 256 rules (15,51,85,170,204,240) are injective on bi-infinite configurations. Proving injectivity for these 6 is easy via shift/identity/complement arguments, but showing the other 250 are non-injective requires exhibiting explicit colliding configurations — periodic configs might work as witnesses since non-injectivity on a cyclic ring implies non-injectivity on ℤ.

Rule 90, for instance, maps the all-zero and all-one rings of even length to the same output, giving a quick collision. I'm thinking the general strategy is to search for a small cyclic ring size n where each non-reversible rule exhibits a collision, then verify this computationally by brute-force checking all 2^n configurations for that rule.

For the 1D local-constraint question, satisfiability should extend to periodic solutions via a de Bruijn graph argument—any bi-infinite path in a finite graph must eventually cycle, which is a pigeonhole-style argument that seems feasible to formalize, though moderately involved. The substitution-based nesting problems look like they follow a similar neighbor-independence pattern.

For "nested" substitution claims, defining it faithfully is tricky since the natural statement (fixed points being self-similar under the morphism) is close to tautological, while the stronger k-automatic/Cobham-type statement is too hard—so I should probably skip or decline these unless I find a sharper formalization. The tag-system-to-substitution reduction in ch03-13 looks tractable though: showing that processing a 1-tag system word by word is equivalent to applying σ to the whole word is just a list lemma.

Going through the rest: ch04-15 about automatic sequences never being algebraic irrationals is a hard literature result (Adamczewski–Bugeaud), so decline; rule 110 universality and the 2,5 TM universality claims are far beyond current feasibility, decline both. The PCP claim is actually subtly wrong—2-pair PCP is decidable while undecidability is only established for larger instances, so that's partial/false and should be declined or heavily qualified. The Gödel-style claim linking undecidability to incompleteness in ch12-31 seems more promising as an abstract theorem about consistent, complete sets.

I'm now thinking ch12-31 is doable using Mathlib's computability tools: if a provable set and its complement (refutable set) are both recursively enumerable, consistency and completeness force the refutable set to equal the complement of the provable set, making it decidable via Mathlib's `ComputablePred.computable_iff_re_compl_re`. For ch12-39, the multiway involution-negation claim about completeness and consistency corresponding to exactly half the strings of each length being generated seems trickier than it looks—just having half the strings doesn't guarantee the right balance, since you could still have both a string and its negation included while missing other pairs entirely, so the "half" characterization isn't straightforwardly equivalent to complete-and-consistent.

For the pigeonhole direction, I can prove the provable parts cleanly: having more than half the strings implies inconsistency, having less than half implies incompleteness, and complete-and-consistent implies exactly half—while noting the converse doesn't hold. This needs a fixed-point-free involution, which should be manageable with Finset cardinality arguments. Then for ch12-42, Wolfram's single Nand axiom is a genuinely hard target since proving it's a complete axiomatization requires a long equational proof typically done via automated theorem provers—though I could settle for the weaker result of just verifying the axiom is a sound tautology over Booleans.

Since soundness alone doesn't capture the actual claim being made, I think I should decline rather than formalize just that weaker piece. For ch11-08, I can set up a light-cone lemma showing that an elementary cellular automaton with radius r and a quiescent state has its support after t steps contained within the initial support expanded by rt, which gives a linear growth bound to contrast against substitution systems' exponential growth—this seems tractable to formalize.

Going through the rest of the list, several candidates don't seem like good fits: the universality claims about class 1/2 systems are too vague, causal invariance for non-overlapping rules involves confluence arguments that are hard to formalize faithfully, the network connectivity construction and large-scale enumerations (one over 4 billion cases) are infeasible, and claims like "primes are random" aren't real math propositions. I'm leaning toward declining all of these, along with the P≠NP-related entries.

The transitivity-of-emulation claim about universal CAs looks essentially tautological, so that's a decline too. The growth-rate dimension claim is more promising though — proving that balls in ℤ^d under the L1 metric grow polynomially with degree d feels like something I could actually formalize, even if it takes work.

Tallying up, the formalizable set lands around 13 claims across the different chapters, with the remaining 52 needing writeups explaining why they can't be formalized. I also need to flag that the 269 non-mathematical claims simply aren't Lean candidates at all, since "verification" there would require empirical data tests that none of these books actually provide.

Given the scale, I'll follow Thompson's approach: set up a Lake project, write an INSTRUCTIONS.md assigning claim ownership, and launch several parallel subagents per module. First I need to confirm Mathlib loads correctly and check the size of Thompson's existing .lake setup before proceeding.


Wolfram has no Lean project yet, so none of its 52 math claims could be marked proved—most, like Rule 110 universality and P≠NP, are unformalizable, but about a dozen (eventual periodicity, rules 90/150 additivity, rational-digit periodicity, etc.) have a provable core. I'll set up `books/wolfram-nks/lean/` modeled on Thompson's, reusing its downloaded Mathlib.

Since it's 7.2G, using an APFS clone via cp -c makes sense since it's copy-on-write and essentially free—I'll go ahead and create the project files that way.

Mathlib is cloned in (copy-on-write, so it adds no real disk usage). Next I'll check that a trivial module compiles against it.

The project compiles against Mathlib. Next I'll check that `load-claims.mjs` would pick up Wolfram reports, then write the instructions file.

That approach works, so now I'll draft an adapted INSTRUCTIONS.md and split the 52 claims into modules for subagents, starting with grouping the finite systems and cellular automata claims into one module.

Then I'll organize the rest: an additive module, a digits/substitution module, and a logic/axiom-systems module (the largest with 22 claims), confirming the totals add up to 52. I should also check the pages.json structure for claim source URLs and consider memory concerns if running four Lean environments concurrently.

Now I need to figure out the top-level imports for ThompsonLaws.lean and create WolframLaws.lean afterward, and verify that the path computation in load-claims correctly resolves to books/wolfram-nks/lean/WolframLaws/Module.lean, checking whether that project is already registered in load-claims' projects list.

That's generic enough. Now I need to write INSTRUCTIONS.md for Wolfram, so let me quickly check the structure of inputs/pages.json first.


`load-claims.mjs` already picks up Wolfram reports automatically since it scans all `books/*/lean/reports/` folders. Next I'll check how the source text is stored so I can point formalizers to it.

I should check if the page text is already cached under inputs/cache, so I'll quickly list that directory to confirm whether to reference the cache path or the original URL in my instructions.

Next I'll write the Wolfram Lean instructions, adapted from Thompson's to cover discrete systems and computability.

The placeholder proof text is confusing, so I'll simplify by just showing the signature with a brief comment noting it uses a pigeonhole argument on the orbit, rather than including a fake proof body.

Instructions are written. Next I'll split the 52 claims into four modules and formalize them in parallel with subagents, as was done for Thompson.

I'll launch four subagents in parallel, first checking the Task schema to get the parameters right.

I'll run the four calls in parallel within a single message rather than backgrounding them, so they execute concurrently without leaving the turn incomplete. I'm also drafting a shared prompt template with hints tailored to each module.

_Tools used: GetDynamicTools, Read, Shell ×10, StrReplace, Task ×4, Write_

_Turn ended: error (Cancelled while awaiting host turn events.)_

### 2026-10-31 13:07 — Turn 2 (User)

> ok but we ware looking or his bio dieas

**Assistant:**

I'm thinking about Wolfram's biology chapter — pigmentation patterns, shells, phyllotaxis — and realizing the "verified" status is murky here since these claims, like Darwin's and Thompson's non-mathematical ones, are essentially untested. That makes me reconsider what "verified" should even mean for this category, maybe pointing toward how the assessment pipeline handles dataset-resolvability.


Got it, this is about Wolfram's biology claims rather than the computation theorems. I'll stop the Lean work and examine those claims along with `claim-tests/` to figure out what "verified" could mean in this context.

_Tools used: Shell_

_Turn ended: error (new_message_submitted)_

### 2026-10-31 13:07 — Turn 3 (User)

> i was trying to figure out what if anythiing has bene validated experietnatlly

**Assistant:**

I need to check the claim-tests/wolfram-nks directory for biology claims in chapter 8 to see which have been experimentally validated, and I also notice some stray Lean files from aborted subagents that should probably be cleaned up.


I'll check the `claim-tests/wolfram-nks` directory to pull Wolfram's biology claims (mainly from chapter 8) along with their assessment scores.

Now I'll check the verdicts of all Wolfram claim tests to see whether any biology claim has actually been tested.

**Short answer:** none of Wolfram's biology ideas has been tested here. Even the claims that did get tested weren't tested experimentally: all of those tests ran on data generated by simulations or computer searches.

**What has been tested.** `claim-tests/wolfram-nks/` has 59 completed tests, all on his computational claims (cellular automata, substitution systems, digit expansions, universality). The verdicts were 43 supports, 8 mixed, 5 inconclusive and 3 refutes. Every dataset was either produced by a script (enumerating rules, running rule 30, and so on) or was a reference table such as an OEIS sequence or Cook's rule 110 glider table. None was a measurement of anything in the world. The closest to an empirical test is the market model (`ch08-30`), and its verdict was mixed on simulated price series.

**What hasn't been tested.** The biology claims have no test directory at all. That covers his pigmentation and growth claims in chapter 8, the claims about natural selection (`ch08-10` to `ch08-18`, `ch01-13`, `ch07-19`) and genetic programs (`ch01-11`, `ch08-13`). The repo only has assessors' opinions of them, which don't count as verification. These are the strongest biology claims by assessor truth score:

| Claim | Idea | Truth | Testability |
|---|---|---|---|
| `ch08-28` | Coat patterns from local activation and long-range inhibition | 0.82 | 0.57 |
| `ch08-22` | Simple growth-rate models give all mollusc shell shapes | 0.81 | 0.65 |
| `ch08-21` | The 137.5° phyllotaxis angle comes from an inhibition process | 0.80 | 0.62 |
| `ch08-26` | Shell pigment patterns are generated like 1D cellular automata | 0.76 | 0.57 |
| `ch08-19` | Plant branching comes from substitution-system rules | 0.75 | 0.57 |

**Why the site shows nothing as verified.** `docs/load-claims.mjs` only counts a Lean proof or a literature proof. It never reads `claim-tests/`, so even the 43 supporting computational tests show up as `untested`. That's likely what you noticed first.

**Possible experimental support from published work.** This part comes from my own knowledge of the literature and I haven't checked it against the repo. These papers would be the candidates for real tests:
- Manukyan et al. 2017 (*Nature*) found that the scale colouring of ocellated lizards follows a hexagonal cellular automaton. That is the closest direct match to `ch08-26`/`ch08-28`.
- Kondo & Asai 1995 observed Turing patterns moving on live angelfish (`ch08-28`).
- Douady & Couder 1992 reproduced the 137.5° angle with a physical inhibition experiment, and Reinhardt et al. 2003 tied it to auxin (`ch08-21`).
- Raup 1966 modelled the range of shell shapes with a few growth parameters (`ch08-22`).

All four support the mechanisms, but none of these mechanisms is unique to Wolfram: they follow Turing and Meinhardt. His distinctive claims, that selection doesn't produce complexity and that the rules for biological form are effectively random programs, have no test here and get low truth scores (0.11 to 0.21).

The interrupted Lean work left a `books/wolfram-nks/lean/` folder with three partial modules and a copy-on-write clone of Mathlib, which takes no extra disk space. I'll delete it unless you want those claims formalized after all.

I can either pre-register and run real-data claim tests for the five strongest biology claims above, or make the site count completed claim tests as "tested". Which would you like?

None of the biology-related claims have claim tests, only the markets one does, and all testing so far relied on simulated rather than experimental data—so the claims site isn't really surfacing untested claims, which explains why nothing's been verified. I'm also thinking about what's actually known experimentally about Wolfram's biological ideas, like Meinhardt's work on mollusc shell pigmentation patterns.

From the literature, there's real experimental support for several Wolfram-style ideas: phyllotaxis spiral angles matching Douady & Couder's ferrofluid experiments, Turing-pattern animal coats like Kondo & Asai's angelfish work, and notably Manukyan et al. 2017 showing ocellated lizard scale coloration actually follows a hexagonal cellular automaton—strong real-world backing for a CA-like model. I can mention this as background knowledge with the caveat that it's not documented in the repo itself, keeping it brief. I should also flag the leftover Lean files and the large .lake clone from earlier aborted agent work and offer to clean those up.

_Tools used: Shell ×3_

### 2026-10-31 13:18 — Turn 4 (User)

> so bascialy nothing that is bio-foreard testable right?

**Assistant:**

Not quite. Several of his biology claims are testable with data that already exists; nobody has run those tests yet. The extraction triage marks nine as "testable with existing data":

- **Pattern and form:** shell pigment patterns behave like 1D cellular automata (`ch08-26`), coat patterns come from activation and inhibition (`ch08-28`), phyllotaxis comes from an inhibition process (`ch08-21`), simple growth rules cover all shell shapes (`ch08-22`), and shape differences between related animals come from differing growth rates (`ch08-24`).
- **Development:** embryos develop hierarchically because of a fixed length scale (`ch08-23`).
- **Evolution:** the complexity of organism parts has stayed roughly constant for eons (`ch08-12`), features that change fastest between species are the most complex (`ch08-16`), and selection doesn't drive organisms toward more elaborate structure (`ch08-18`).

The catch is that the testable ones mostly aren't distinctively his. The pattern and form claims are Turing, Meinhardt and Raup mechanisms that Wolfram restates in cellular-automaton language, and published experiments largely support them already. His original biology thesis is that natural selection doesn't generate complexity and that biological form comes from effectively random simple programs (`ch08-11`, `ch08-14`, `ch08-15`, `ch08-17`). Those claims are only "partly testable" and get the lowest truth scores.

If you want a test that could actually discriminate, `ch08-16` and `ch08-12` are the best bets. They make concrete predictions about Wolfram's anti-selection view that could be checked against morphological trait databases and the fossil record, and some of that data may already be in `organisms/`.

Actually, not quite — several items are testable with existing data per the triage, just not yet tested, like chapters 08-12 through 08-28. The distinctive Wolfram bio claims are only weakly testable though. I should keep this concise.
