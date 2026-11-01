# Subagent: Darwin claims formalization survey

- **Parent chat:** [let's send fable to go through all of the most validated claims of darwin and se](../2026-10-31_1700_let-s-send-fable-to-go-through-all-of-the-most-validated-cla.md)
- **Started:** 2026-10-31 17:01 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 21:09 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** error
- **Transcript ID:** `4052e949-8dbf-47c1-8d35-3e28cf2efc74`

---

### 2026-10-31 17:01 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci. Read AGENTS.md and BEST_PRACTICES.md first. The repo extracts candidate laws of biology as claims, assesses them, and publishes nanopubs.
> 
> GOAL: Go through the most validated claims from Darwin's *On the Origin of Species* (project `claim-sources/darwin-origin/`, 247 claims, ids like `darwin1859-ch12-04`) and determine which can be turned into a genuine mathematical formalization. Currently none of the Darwin claims have `math: true` in `docs/claims.json`.
> 
> STEP 1 - pick the 'most validated' set. Combine these signals:
> - Data-test verdicts: `test-data/claim-tests/darwin-origin/<id>/result.json` (41 claims; verdict supports/mixed/refutes/inconclusive with a confidence). List is in `test-data/claim-tests/SUMMARY.md`. In `docs/claims.json` (`{built, claims:[...]}`) each claim has `evidence` and `data_test`.
> - Model truth scores and assessments in `docs/claims.json` and `test-data/truth/`, and dataset-resolvability assessments in `claim-sources/darwin-origin/assessment/assessments.json`.
> - You can also use `node mcp/cli.mjs <overview|search|claim|rank|graph|tests>` (e.g. `node mcp/cli.mjs graph` / `tests`) for rankings.
> Prioritise claims with verdict `supports` at high confidence and high truth scores; also include well-supported `mixed` ones and any high-truth untested claims that are obviously quantitative (e.g. island species-area, rates of change, divergence of character, geometric increase / struggle for existence in Ch. III, the tree-of-life branching, extinction-by-competition). Aim to screen roughly the top 40-60.
> 
> STEP 2 - for each screened claim, classify formalizability:
> - A: a precise mathematical statement exists that faithfully captures the claim (e.g. Malthusian geometric increase vs bounded resources implies a fraction must die; species-area relation S = cA^z with lower c or different z for oceanic islands; island endemism under a distance-dependent immigration/speciation model à la MacArthur-Wilson; fossil similarity decaying with stratigraphic distance as a monotone property of a branching/Markov model; diversity rise-and-fall curves; divergence of character as a tree/branching-process property). State assumptions explicitly.
> - B: formalizable only as a model-dependent statement (needs a chosen model; say which and how faithful it is).
> - C: not a mathematical proposition (purely historical/empirical) - say why in one line.
> Be honest: don't force formalizations that lose the claim's content. Note the repo's rule: a formalization is not a 'theorem' unless proved (Lean with no sorry, or a recorded literature proof); a proof shows the statement follows from assumptions, not that organisms satisfy them.
> 
> STEP 3 - for the A (and best B) candidates, write LaTeX formal statements with assumptions, and where tractable draft Lean 4 proofs. Follow the conventions in `claim-sources/thompson-growth-form/lean/INSTRUCTIONS.md` (the Thompson Lake project has Lean v4.35.0 + Mathlib already downloaded; module check: `cd claim-sources/thompson-growth-form/lean && lake env lean ThompsonLaws/<Module>.lean`, first run ~90s). For Darwin, create a separate scratch Lean file rather than editing Thompson modules - e.g. put Darwin modules under a new folder `claim-sources/darwin-origin/formalization/lean/` and, to check them, you may temporarily copy into the Thompson project or set up a small Lake project reusing its Mathlib (don't leave changes in the Thompson project). Only report something as proved if it compiles with no `sorry`.
> 
> OUTPUT: write `claim-sources/darwin-origin/formalization/REPORT.md` (ranked table of screened claims with validation signals and A/B/C class; then per-candidate sections with the faithful statement, LaTeX, assumptions, what's lost vs Darwin's wording, and Lean status) plus `claim-sources/darwin-origin/formalization/candidates.json` (machine-readable: id, validation signals, class, latex, assumptions, lean_file, lean_status). Do NOT modify `claim-sources/darwin-origin/claims.json`, `docs/`, or any nanopubs, and do NOT publish anything.
> 
> FINAL MESSAGE back to me: counts per class, the top ~10 formalizable claims with one-line formal statement each, which ones compiled in Lean without sorry, and any notable claims you judged unformalizable despite being well-validated.

**Assistant:**

I should check BEST_PRACTICES.md next and then start exploring the Darwin project structure.

Now let me dump a ranked table of all 247 Darwin claims with the signals.

I want to save the full output to a file and check the truncated middle section, including the Chapter III claims about geometric increase and Chapter IV's divergence of character discussion. Let me write the complete table to a temp file.

I want to dig into the result.json files for the most-supported entries to see the data details, and also check how assessments.json structures dataset-resolvability scores alongside the truth data.

With enough signals gathered, I'm now looking at setting up a Darwin Lake project that reuses Mathlib, checking the Thompson Lean project's lakefile.toml, lake-manifest.json, and a sample module to model it after. I also want to aggregate the resolvability assessments per claim—averaging verdict/confidence into a mean dataset-resolvability score across the screened set.

I'm thinking about setting up a new Lean project for the Darwin laws by reusing the existing Thompson project's dependencies—copying the lakefile, manifest, and toolchain, then symlinking the packages directory instead of re-downloading mathlib.

Before diving into Lean, I need to screen and classify the ~50 candidate claims. I'm noticing that even some refuted claims, like the Weald denudation calculation, are actually clean arithmetic computations that could be formalized despite being factually wrong—so I'll flag those as formalizable but low-priority given their refuted status.

I'm also compiling a list of untested, high-truth quantitative claims worth formalizing: geometric population growth arguments, branching/extinction patterns, nested group structure from divergence, and interesting edge cases like Darwin's honeycomb claim about hive-bee cells being maximally wax-economical—which connects to real mathematics since Hales proved the 2D honeycomb conjecture, though the 3D rhombic dodecahedron cell claim turns out not to be truly optimal per Fejes Tóth's work.

Continuing through more examples: archipelago relatedness, Darwin's seed-floating survival arithmetic (checking his 28-day float rate times drift speed against his stated fraction), and several quantitative biogeography and paleontology claims — species-area relationships, endemism, fossil similarity decay over time, and rates of change correlating with time elapsed.

Now I'm moving into formal classification, starting with overproduction leading to struggle for existence: framing it as geometric population growth exceeding a carrying capacity, so that beyond some generation the excess offspring must die off, with survival fraction shrinking accordingly.

I'm working through the bound on cumulative survival: with population capped at K and per-generation growth rate r>1, the product of survival fractions across generations must shrink toward zero, meaning fractions below 1 have to occur infinitely often to keep the population from exceeding K.

For the Lean formalization, I'm sketching a definition for geometric population growth and planning theorems showing unbounded growth without survival limits, that K/(N0·r^t) tends to zero, and that bounded population forces the survival-fraction product below that same ratio. Then I'll move on to the next section.

Doubling time follows log2/log λ once λ exceeds 1, so this seems simple enough to fold into the Malthus module. Now looking at average abundance: in an equilibrium population, N* is actually set by density-dependent mortality rather than fecundity alone, since the equilibrium condition requires survival fraction to equal 1/r — meaning Darwin's point about high fecundity compensating for heavy destruction shows up as the death fraction equaling 1 − 1/r.

For the oceanic island species question, I think a MacArthur-Wilson immigration-extinction framework works well: with immigration decreasing in distance and extinction decreasing in area, the equilibrium species count P·I/(I+E) naturally decreases with distance, explaining why remote islands have fewer species than near ones of equal area.

I confirm S* = PI/(I+E) is the unique fixed point of that dynamic and monotone in the parameters.

Now moving to the endemics question: I want a model where immigrants arrive at rate I while resident lineages speciate in situ at rate σ, and I'm working out the equilibrium endemic fraction as a function of these competing rates.

Framing it as a two-state Markov chain—non-endemic and endemic—with transition rate σ from non-endemic to endemic and swamping back via gene flow at rate m, the stationary endemic fraction is σ/(σ+m). Since m decreases with isolation distance, this fraction is strictly increasing in distance, capturing the isolation-endemism relationship cleanly as a monotonicity result.

For the fossil succession question, the same Markov turnover logic applies: if each genus persists independently across stages with probability p and extinct lineages never reappear, then similarity between any two stages decays geometrically as p raised to the gap between them, giving a clean proof that faunal resemblance declines monotonically with temporal separation.

More importantly, there's a deterministic version too — if lineages occupy continuous stratigraphic intervals without reappearing, the genera shared between two distant stages must be a subset of what's shared between each and any intermediate stage. That means the overlap count is strictly antitone in the gap size, and the middle stage necessarily contains everything common to its neighbors, which is precisely Darwin's intermediate-fauna argument.

Thinking about whether reappearance could be excluded mathematically, I consider a continuous trait-space model where re-evolving an identical form has probability zero—but that's a weak argument. I'll classify this as C: the no-reappearance claim is really a modeling assumption (interval ranges) used elsewhere, not something derivable as a proposition.

Moving to the next claim about groups rising and falling in unimodal diversity patterns, I check a basic birth-death process: with constant rates, expected lineage count is either monotonically decreasing or increasing depending on whether λ<μ or λ>μ, never producing a hump on its own. The rise-and-fall pattern seems to require something more—either time-varying rates or diversity-dependent origination that declines as the clade fills available niches.

So I consider instead a trivial but valid interpretation: any integer-valued path from 1 species to 0 that ever exceeds 1 must have an interior maximum, simply because it's bounded at the start and end. This connects to Darwin's actual point—that diversity changes gradually, one species at a time, rather than through catastrophic jumps—meaning a clade that reaches some peak diversity M must pass through every intermediate level on the way up and down.

Moving to the next case, "different groups evolve at different rates" is just an empirical observation lacking real mathematical content, so I classify it as Class C. Then I look at whether the amount of fossil change can measure elapsed time, which seems to hinge on an assumption of constant evolutionary rate.

Under a constant-rate Poisson extinction model, the fraction of genera failing to persist over duration D is 1 − e^(−μD), which is strictly increasing in D — so turnover is an invertible, monotone function of elapsed time, giving D = −ln(1−T)/μ. This is faithful precisely because it acknowledges the measure is imperfect when μ varies, tying back to the earlier case about differing rates across groups; I'd classify this as A under the constant-hazard assumption, and it's easy to prove via strict monotonicity of the exponential term.

For ch10-13 on ancient forms diverging more from living ones: this follows the same decay logic — expected trait divergence grows with time under Brownian motion, while expected shared genera with the Recent decays as p^k — so it's also A, and actually collapses into the same interval-range theorem already established (shared(i, now) is antitone in age), so no new proof needed.

Moving to ch12-18 on closer relatives being closer in time and space: I'm reasoning this is B, since under Brownian-motion dispersal on a tree, expected squared geographic distance scales with divergence time (σ² × 2×divergence time), which is monotone — and now I'm starting to think through the parallel temporal argument for genera sharing a family.

Now I realize the temporal monotonicity doesn't actually hold — first appearance times of two lineages aren't bounded by their divergence time the way I assumed, so |FAD1 − FAD2| isn't controlled. The spatial part still works fine though. Given the Lean formalization would be a trivial stub for linear monotonicity, I'm leaning toward presenting just the LaTeX statement and marking the Lean proof as not attempted, unless I can find something more substantive like a variance-of-sum argument.

Moving to ch04-20 on divergence of character maximizing life supported in an area: I'm framing this as B, setting up a niche model where n resources each have capacity K_i, species have niche-use vectors, and total biomass is bounded by the sum of the K_i.

This bound is achieved exactly when every resource gets used, which captures Darwin's division-of-labour argument nicely — total life supported is the sum of capacities over the union of resources actually used, monotone in that union and maximal when the union covers everything. This translates cleanly to Lean using Finset.sum_le_sum_of_subset with nonnegative weights, defining supported life as a sum over a used-resource finset, monotone in that set and maximized at the universal set — a good class B candidate.

For item 15, large populations favoring selection: if each individual independently has probability p>0 of a favorable variation, then the probability at least one arises among N individuals is 1−(1−p)^N, strictly increasing in N and tending to 1 — directly capturing Darwin's point about larger populations having better odds of producing profitable variations. This is straightforward to formalize in Lean via strict monotonicity of that expression and its limit, making it a solid class A candidate, while the secondary idea about compensating for lower per-individual variability seems less essential to include.

For the natural selection item, I'm formalizing the core two-type replicator dynamics: with fitness w_A > w_B, the frequency of type A strictly increases each generation when p∈(0,1), and converges to 1 over time — the standard haploid selection theorem. The convergence proof reduces to showing 1/(1+((1−p0)/p0)(w_B/w_A)^t) → 1, which Lean can handle using the geometric decay lemma for powers less than one.

For the neutral variation case, I'm considering Wright-Fisher drift where frequency is a martingale (E[p_{t+1}|p_t]=p_t) with no directional selection pressure, though technically finite populations still drift to fixation rather than staying perpetually variable — so I'm treating this as a qualified match based on the martingale/no-bias property rather than literal persistence of variation.

Moving to the tree/branching structure problems (ch13-01, ch04-26, ch13-12, ch04-24): descent with divergence producing a hierarchy of subordinate groups corresponds to a precise mathematical fact — clades in a rooted tree form a laminar family, meaning any two clades are either disjoint or one contains the other. I'm planning to formalize this by defining descendant sets in a rooted tree and proving that for any two nodes, their descendant sets are either disjoint or nested.

Thinking about ancestor counts over time: in a branching process, the number of lineages at some past time that have surviving descendants shrinks, bounded by the extant population size — connecting to the Kingman coalescent's convergence to a single common ancestor, and to reconstructed-process counts in birth-death models where this number stays below the total population at that time.

I'm thinking about this as a surjectivity argument on the tree: ancestors at a deeper time map onto ancestors at a shallower time, so the count is non-increasing, though it may be too involved to formalize in Lean right now. For the extinct-intermediate-species question, I'm framing it via additive tree metrics — an ancestor lying on the path between two descendants satisfies the betweenness identity d(x,a)+d(a,y)=d(x,y), making "metrically between" a precise, provable statement.

For the connecting-forms gap problem, I'm treating it as removing internal nodes from a tree, which only increases minimum distances between survivors — a LaTeX-only result. Then for large-genera growth, I'm modeling it as a Yule process where genus size grows proportionally to its current size, giving the rich-get-richer dynamic E[dN] = λN dt.

This directly connects to Yule's 1925 model, which literally formalized Willis's data supporting Darwin's claim, so this counts as a Class A result grounded in the literature. The gap between two genera's sizes grows exponentially over time since N₁(t) − N₂(t) = (N₁(0) − N₂(0))e^{λt}, confirming that larger genera pull further ahead.

Moving to the honeycomb item: the claim that hive-bees build maximally wax-economical combs is Class A, since the 2D hexagonal tiling optimality was proven by Hales in 2001, while Fejes Tóth showed in 1964 that the standard 3D rhombic-dodecahedron closure is not actually optimal.

I'm also noting ch07-10 on bees building at intersections of equal spheres — a geometric claim about rhombic dodecahedra forming from sphere-packing intersections, Class A but biologically dubious with a low truth score, so I'll mention it only briefly.

Then there's the denudation calculation: Darwin's figure of roughly a million years derived from dividing cliff thickness by an assumed erosion rate. The arithmetic itself checks out, but the underlying rate assumption is wrong, so it's refuted at high confidence — still Class A arithmetic, though proving "time = distance/rate" in Lean would just be a trivial stub, so I'm weighing whether it's worth including.

Next I look at the seed-drift calculation (14/100 plants surviving flotation at 33 miles/day over 28 days ≈ 924 miles) — another Class A arithmetic combination, but with low truth confidence, so I'll skip Lean for this one too. Then I move to the sea-depth-predicts-mammalian-affinity item, which is more of a proxy argument than a strict calculation, so I'm classifying it differently.

For archipelago species relatedness, it's a tree-plus-dispersal model rather than a pure formal result. And the rarity-precedes-extinction claim turns out to be a genuine discrete intermediate value theorem: in a population changing by single deaths from N₀≥2 down to 0, it must pass through every lower abundance threshold, including rarity — the same logical structure as an earlier extinction item, so this one looks Lean-provable.

Then for the struggle-most-severe-among-conspecifics claim, I'm connecting it to Lotka-Volterra competition theory: intraspecific competition coefficients equal 1 and exceed interspecific ones whenever niche overlap is below maximum, which follows from a Cauchy-Schwarz argument on resource utilization curves — a legitimate MacArthur-Levins style theorem.

Same model as before, so I'll skip it as a separate case. Going through the rest of this batch — succession, island biogeography, marine fossil correlations — these all read as historical/empirical claims (class C), with maybe one borderline gradualist case I'd lean toward class B.

For naturalized flora adding more genera than species proportionally, this looks like class B — a sampling model where since species are nested within genera, randomly drawing introduced species from a pool naturally hits genera at a disproportionate rate compared to species, making the new-genera-ratio exceed the new-species-ratio as a structural/statistical property rather than a biological one.

Moving through the rest of the list, I'm classifying several more claims: species-area relationships as A/B, arbitrary higher taxonomic ranks as conceptual (C), food-web interaction chains as B with some conceptual overlap, formation timescales versus species transformation as C, and the idea that new species roughly balance extinctions as B — essentially a near-trivial identity about stationarity where constant diversity implies origination equals extinction. I'm also noting that group extinction tends to lag behind origination, tying back to earlier data showing a median rise.

Continuing the sweep, I mark adaptive radiation after key innovations as B (early exponential growth), intermediate varieties being rarer as B since intermediate zones have smaller area and thus smaller populations, large areas producing more species as another B via species-area reasoning, and the claim about lower taxonomic groups ranging more widely as C. I'm now compiling the running list of items classified as A, including ch03-01, ch04-01, intro-02, ch02-01, ch04-14, ch01-16, and ch10-16 paired with ch10-13.

Now I'm sorting the remaining items into B categories — Malthusian/Wright-Fisher models, two-state Markov chains, additive niche models, Yule processes, and Mendel's ratios — while planning to screen the full set down to roughly 50 claims by keeping all 41 tested items plus any untested but high-confidence quantitative claims.

I'm setting up the Lean project structure: a Darwin formalization folder with a Lake project configured via lakefile.toml, copying over the lean-toolchain and lake-manifest.json files, symlinking the packages directory to Thompson's existing setup, and double-checking the .gitignore excludes the build artifacts.

I notice .lake isn't gitignored at the root, so there's likely a .gitignore inside the lean folder itself. I'll check the thompson-growth-form lean directory's .gitignore and set up a similar one for the Darwin Lake project.

Now a smoke test of the setup with a trivial module, while I start writing the real ones.

That approach works, so now I'm planning the Lean module structure: one file for struggle-related results (geometric growth versus bounds, survival multipliers, stationary distributions, probability of variation, selection convergence), and another for succession covering interval ranges.

I'm also sketching modules for tree structure (laminar clades, Yule gap growth) and island biogeography (equilibrium monotonicity, endemic fractions, niche additivity, overlap bounds). In Struggle.lean, I'm formalizing geometric population growth and proving it eventually exceeds any bound given a growth rate above one.

I'm then working toward a "must die" theorem showing the required death count grows unboundedly, using divergence of the growth rate raised to increasing powers.

`Filter.Tendsto.div_atTop` confirms the division-to-zero lemma. Now I'm thinking through a bounded-population model where realized population at each step is r times survival fraction times prior population, showing that if population stays under a cap K, the product of survival fractions must shrink toward zero as N₀r^t grows.

Writing the Lean theorem...

Still proving the bound, then I'm sketching the squeeze theorem argument to show the survival product tends to zero when r exceeds 1, bounding it between zero and K divided by the diverging geometric term.

For the next section, I'm thinking about how a realised multiplier combining r and s behaves monotonically, noting that if the product rs exceeds 1 the same divergence argument applies with the multiplier replacing r.

I also want to formalize rapid spread: the time to reach population size M from N₀ under multiplier λ>1 is bounded by the log ratio divided by log λ, essentially the doubling-time formula, which I can prove using monotonicity of the logarithm.

Using the log monotonicity lemma with positivity conditions on M/N₀ and lam^t, I can convert the inequality back through division to get M ≤ lam^t * N₀, closing that proof.

Then for the stationary population case, I'm reasoning that if the population stays constant, the survival rate must equal 1/r, derived algebraically from the recurrence r * s t * N = N.

For deaths per generation, I'm considering a trivial lemma that the number destroyed equals (r-1)*N, but deciding it's too minor to include, so I'll just keep the survival result and group ch03-03 with the shared module.

Moving to ch04-14, I'm defining the probability that at least one event is favorable across N trials as 1 minus (1-p)^N, and now working out that this function is strictly increasing in N when p is strictly between 0 and 1, using a lemma about powers of numbers less than one being strictly decreasing.

I'm also figuring out the right Mathlib name for strict monotonicity of powers under base less than one, then noting I'll use a tendsto-to-zero lemma for r in [0,1) combined with constant-subtraction to get the limit behavior, before moving to the haploid selection problem for ch04-01.

For that, I'm defining selected frequency as a ratio of fitness-weighted allele frequencies, and proving the new frequency exceeds the old one by showing the denominator is positive and reducing the inequality down to the simple fact that wB is less than wA.

Still working through whether linarith can handle this nonlinear expression as atoms, or whether I need nlinarith to close the gap directly.

Now I'm thinking through the trajectory formula for selected frequency and whether I need a separate iteration lemma showing that applying selection to the trajectory at time t gives the trajectory at time t+1, which I'd prove by defining the trajectory recursively.

After field_simp and ring simplification, the recursion identity reduces to matching p₀wA^(t+1) over the updated denominator. For convergence, I rewrite traj t as 1 over (1 + ratio·(wB/wA)^t), note (wB/wA)^t tends to 0 since the ratio is in [0,1), and conclude via standard limit lemmas that traj t tends to 1.

A cleaner approach: dividing numerator and denominator by a^t rewrites traj t as p₀/(p₀ + (1-p₀)(b/a)^t), which makes the limit p₀/(p₀+0) = 1 straightforward via field_simp and div_pow. Then I'm starting a new file for Succession.lean, defining a Lineage structure with first and last appearance stage indices to model fossil ranges.

I'm defining when a lineage is present at a given stage and computing the fauna of a stage as the filtered set of lineages active there, noting I need DecidableEq on Lineage for the filter to typecheck.

Then I'm proving intermediacy — that if i ≤ j ≤ k, any lineage present at both i and k must also be present at j — by unfolding membership and applying transitivity. From there I'm deriving that shared fauna counts are antitone in the gap: the intersection of fauna at i and k is a subset of fauna at i and j, so its cardinality is bounded by the latter.

I'm naming the special case where k is the present day as a corollary, `olderFauna_shares_fewer_with_living`, since that's the biologically meaningful statement. I'm also weighing whether to add a second theorem modeling exponential decay of shared fraction under a Markov persistence model — it feels slightly stub-ish, but since the test data specifically measures decay, I'll include a short version anyway.

I'm then working out turnover dynamics: defining expected turnover as a function of rate and duration, proving it's strictly increasing in duration via exponential inequalities, and deriving its inverse (elapsed time from turnover) to show the two functions compose back to the identity using log-exp cancellation.

I also want to show turnover varies with μ itself, formalizing the intuition from the "imperfect correspondence" discussion that different rates yield different outcomes for the same duration, plus a discrete intermediate-value-type lemma for ℕ-valued sequences that change by at most 1 per step.

I'm setting this up as an induction on the step-count difference, proving that if a sequence can only move by one unit per time step, then it must pass through every integer value between its endpoints.

I'm worried that omega might not recognize `N (a + (d+1))` and `N (a+d+1)` as the same atom since they're syntactically different, even though they're definitionally equal—so I may need a rewrite like `Nat.add_succ` to normalize the expression before omega can close the goal.

I can prove both the rising and falling step bounds symmetrically, then derive corollaries like the fact that rarity must precede extinction: if a population starts abundant and later hits zero, with steps down by at most one each time, it must pass through every intermediate value, including exactly one individual at some point. More generally, for any target m between the final and initial values, there must exist some time t where N t = m.

Now I'm setting up for the gradual rise and fall result: a clade starting near zero, peaking at some diversity M, then declining to extinction passes through every diversity level on both the way up and the way down—just two applications of the step lemma.

Next I'm starting on the tree structure file, defining what it means for a descent order to be tree-like—that the ancestors of any given form form a totally ordered chain.

Finishing the case split, I conclude that if u ≤ w then clade v ⊆ clade u, and if v ≤ w then clade u ⊆ clade v, proving the proper inclusion direction in each branch. I note I should structure the proof with explicit Or.inr applications for clarity, and I'm now thinking about the broader picture: clades containing a fixed form w are totally ordered by inclusion, which captures the idea that taxonomic groups subordinate to a common ancestor form a chain.

Moving to a new section on Yule's model, I'm defining expected genus size as exponential growth n₀·e^(λt), then proving that the difference between two genera's expected sizes scales by the same exponential factor regardless of t, and that this gap strictly increases with time when the growth rate is positive.

For the Islands file, I'm sketching the MacArthur-Wilson equilibrium model where species richness depends on immigration and extinction rates, setting up a fixed-point theorem and a simpler differential equation for species accumulation toward the pool size P.

I'm also proving monotonicity of the equilibrium in the immigration rate, reducing the inequality through cross-multiplication and nlinarith.

Since immigration decreases with distance, the equilibrium species count decreases with distance too, which captures the island biogeography result that distant islands hold fewer species — and since extinction stays positive, equilibrium always falls short of the mainland pool size. I'm also noting the area effect: extinction decreases with area, so equilibrium increases with area, giving the species–area relationship as another monotonicity lemma.

Now I'm starting a new section modeling the stationary endemic fraction of a two-state chain where resident species gradually diverge into endemics.

This confirms endemic fraction rises as distance increases since migration drops off, so continents and near islands with high migration show low endemism, which matches the theory. Moving to supported life capacity, I'm defining it as a sum of carrying-capacity contributions over a used subset of niches, then proving monotonicity: expanding the set of used niches can only increase total supported life when each contribution is nonnegative.

I also want a strict version showing that leaving a resource unused means strictly less life is supported than the full potential, and I'm setting up an assemblage model where each species occupies a niche subset, with total used niches being the union across species so that adding a new species with any new niche strictly boosts supported life.

Now I'm defining niche overlap using the MacArthur-Levins normalized formula with Cauchy-Schwarz, and sketching the lemma that overlap of a vector with itself equals one.

I need to handle the edge case where the sum of squares is zero, so I'll require positivity hypotheses for both the self-overlap and the general bound lemmas. This gives intraspecific overlap as the maximum, which fits the Lotka-Volterra interpretation that competition is most intense within a species — supporting Class B.

Moving on, ch04-24's tree-metric betweenness result is purely LaTeX, nothing to formalize in Lean. I'm now turning to writing the four Lean modules, double-checking that `Real.sqrt` and the lemma `pow_lt_pow_right_of_lt_one₀` are correctly named in the current Mathlib version — I'm fairly confident on both counts.

I'm also cross-checking a batch of lemma names I'll need: convergence results for geometric sequences, division and multiplication compatibility with `atTop` filters, the division inequality rewritten under positivity, the Cauchy-Schwarz-type inner product bound, and the multiplicative identity for `Real.sqrt`.

Down to two errors now. For selectedTrajectory_succ, field_simp isn't clearing denominators properly since it can't confirm the weighted sum is nonzero after the pow_succ rewrite, so I need to handle it manually by defining the denominator D and expressing the probability ratio explicitly in terms of it.

Still working through the lemma rewriting...

Still working through the algebra...

Still writing the algebraic manipulation...

Then I'm looking at a separate error on line 211, where `simpa [div_self hp0.ne']` seems to fail—likely because simp reduces the nonzero hypothesis for `p₀ + (1 - p₀) * 0` down to just `p₀ ≠ 0` before it can apply, so I need to trace through what the simp call actually produces at that point.

Writing the limit proof...

Now the other three modules, then check all in parallel.

The simp_rw isn't working because the goal has the function unapplied due to eta, so I need to first establish the function equality via funext and then rewrite using that equality instead.

_Tools used: Read ×3, Shell ×21, StrReplace ×3, UpdateCurrentStep ×2, Write ×5_

### 2026-10-31 19:36 — Turn 2 (User)

> Your run was cut off by a connection error after writing four Lean modules. Please continue, with these changes:
> 
> 1. LOCATION CHANGE: I moved your Lake project from `claim-sources/darwin-origin/formalization/lean/` to `claim-sources/darwin-origin/lean/` (the `formalization/` folder is gone). The repo's loader (`scripts/site/load-claims.mjs`) and exec manifest (`scripts/exec/build-manifest.mjs`) only discover `claim-sources/<project>/lean/reports/<Module>.json` alongside `lean/lakefile.toml` and `lean/<lib>/<Module>.lean`. Work there from now on. Check with `cd claim-sources/darwin-origin/lean && lake env lean DarwinLaws/<Module>.lean`.
> 
> 2. COMPILE STATUS I verified: `Struggle.lean` and `Succession.lean` compile cleanly with no sorry. `Islands.lean` fails at line 156: `Unknown constant Finset.inner_mul_le_norm_mul_norm` (find the Cauchy-Schwarz lemma in this Mathlib, e.g. `Finset.sum_mul_sq_le_sq_mul_sq` or `inner_mul_le_norm_mul_norm`). `Tree.lean` fails at line 52 in `treeLike_of_laminar` with a Disjoint type mismatch (the PartialOrder instance on α vs Set's lattice: `inst.toLE.1 u` vs `clade u`). Fix both; also replace deprecated `push_neg` with `push Not` if trivial. Do not introduce sorry or new axioms.
> 
> 3. REPORTS: write `claim-sources/darwin-origin/lean/reports/<Module>.json` for each module in the same format as `claim-sources/thompson-growth-form/lean/reports/Cells.json`: array of entries with `claim_id`, `status` (`formalized` | `not-formalized`), `label`, `notation` (LaTeX), and for formalized ones `lean_declaration`, `lean_theorems` (fully qualified, e.g. `DarwinLaws.Struggle.not_all_survive`), `assumptions`, `scope_note` (what is lost vs Darwin's wording, and that it's model-dependent if so); for not-formalized ones a `reason`. Only mark `formalized` if the module compiles with no sorry. Verify axioms with `#print axioms` (only propext, Classical.choice, Quot.sound) in a scratch file you then delete.
> 
> 4. Then write the screening outputs to `claim-sources/darwin-origin/formalization/REPORT.md` and `candidates.json` as originally specified (ranked screened claims with validation signals and A/B/C class, per-candidate statement/assumptions/what's lost, Lean status). Still do NOT modify `claims.json`, `docs/`, nanopubs, or publish.
> 
> Final message: counts per class, the top ~10 formalizable claims with one-line formal statement each, which compiled without sorry, and notable well-validated claims judged unformalizable.

**Assistant:**

I'm working out how to derive the Cauchy-Schwarz-style bound from the squared inequality, using the fact that if x² ≤ y then |x| ≤ sqrt y, combined with sqrt of a product splitting into a product of square roots.

For the tree issue, I suspect the disjointness hypothesis in `treeLike_of_laminar` is getting elaborated oddly, possibly due to how `clade u` resolves with the implicit type. Rather than guessing further, I should just rerun the Tree proof to see the actual error while I finish patching Islands.

I'm reworking the negation handling in both proofs—dropping push_neg since omega can process negated inequalities directly, and restructuring the Islands case to extract the existence witness via by_contra instead of not_exists.

Oops, that removed the bullet. Restoring the bullet lines.

Now compile all four modules (run in background so the connection isn't tied up).

While that compiles, let me look at the report format and gather claim metadata for the screening outputs.

I need to make sure the first entry in each report has a formalized DarwinLaws declaration, since the loader derives the module directory from it, otherwise the path falls back to "Lean". I'll also assign each claim primarily to one module to avoid duplicate formalization across reports, noting secondary coverage where relevant.

Now I'll wait for the compile to finish and check the logs.

It seems the process got killed when the shell call ended, and the log files might not actually exist. Let me check if those files are even there.

_Tools used: Read ×2, Shell ×12, StrReplace ×3, UpdateCurrentStep_

_Turn ended: error (Connection failed repeatedly)_
