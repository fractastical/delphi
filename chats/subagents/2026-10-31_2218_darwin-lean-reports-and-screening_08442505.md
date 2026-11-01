# Subagent: Darwin Lean reports and screening

- **Parent chat:** [let's send fable to go through all of the most validated claims of darwin and se](../2026-10-31_1700_let-s-send-fable-to-go-through-all-of-the-most-validated-cla.md)
- **Started:** 2026-10-31 22:18 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 22:29 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `08442505-4a42-4abf-bd41-d8f27f510e46`

---

### 2026-10-31 22:18 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci. Read AGENTS.md and BEST_PRACTICES.md (sections on stub proofs and 'Formulas and Lean live on a law concept').
> 
> CONTEXT: A previous agent formalized Darwin (*Origin of Species*) claims in Lean 4. The Lake project is `claim-sources/darwin-origin/lean/` (lib `DarwinLaws`, modules `DarwinLaws/{Struggle,Islands,Tree,Succession}.lean`, root `DarwinLaws.lean`). I have verified: `lake build DarwinLaws` succeeds, there is no `sorry`, and all 48 theorems depend only on a subset of {propext, Classical.choice, Quot.sound}. Doc comments name the claim id each theorem serves (e.g. `/-- darwin1859-ch03-01: ...`). DO NOT change the Lean proofs' statements; you should not need to edit the .lean files at all (if you must, re-run `cd claim-sources/darwin-origin/lean && lake build DarwinLaws`, ~5 min).
> 
> TASK 1 - Lean reports. Write `claim-sources/darwin-origin/lean/reports/<Module>.json` for each of the four modules, in exactly the format of `claim-sources/thompson-growth-form/lean/reports/Cells.json` (read it and another report first). One entry per claim id the module covers: `claim_id`, `status: "formalized"`, `label` (from `claim-sources/darwin-origin/claims.json`), `notation` (LaTeX of the formal core), `lean_declaration` (main def, fully qualified, e.g. `DarwinLaws.Islands.mwEquilibrium`), `lean_theorems` (fully qualified theorem names serving that claim), `assumptions` (the model assumptions, plainly), `scope_note` (what is lost relative to Darwin's wording; say clearly when the result is model-dependent, e.g. MacArthur-Wilson equilibrium, two-state Markov endemism, constant-fitness selection). Be honest and specific: a scope_note is what stops a reader over-reading a proof as an empirical confirmation. Check each claim id exists in claims.json and that each named theorem exists in the module. Then run `node scripts/site/load-claims.mjs`-dependent build `node scripts/site/build-claim-graph.mjs` is NOT for you to run; instead just sanity-check by running: `node -e 'import("./scripts/site/load-claims.mjs").then(async m=>{const f=Object.values(m).find(x=>typeof x==="function");const r=await f();const cs=(r.claims??r).filter(c=>c.id.startsWith("darwin1859")&&c.proof==="lean");console.log(cs.length,cs.map(c=>c.id))})'` (adapt to the module's actual exports) to confirm the claims are picked up as proof: lean. Do not write docs/.
> 
> TASK 2 - Screening report. Choose the most-validated Darwin claims: data-test verdicts in `test-data/claim-tests/darwin-origin/<id>/result.json` (41 claims, see `test-data/claim-tests/SUMMARY.md`), model truth scores / assessments in `docs/claims.json` (`{built, claims}`, fields `evidence`, `data_test`, truth fields) and `claim-sources/darwin-origin/assessment/assessments.json`; `node mcp/cli.mjs graph|tests|rank` help. Screen ~40-60 top claims and classify each: A (faithful precise math statement), B (model-dependent formalization; name the model), C (not a mathematical proposition; one-line reason). Mark which are now in Lean. For promising A/B claims NOT yet formalized, give a LaTeX statement and assumptions as future work. Write `claim-sources/darwin-origin/formalization/REPORT.md` (ranked table + per-candidate sections) and `claim-sources/darwin-origin/formalization/candidates.json` (id, validation signals, class, latex, assumptions, lean_file, lean_theorems, lean_status).
> 
> RULES: do NOT modify `claim-sources/darwin-origin/claims.json`, `docs/`, nanopubs, or publish anything. Do not touch the Thompson project. A claim is only 'proved' via a formalized Lean report; truth scores never promote a claim.
> 
> FINAL MESSAGE: list of claim ids now formalized (with module and one-line statement), counts per A/B/C class, top unformalized A/B candidates, and any claim where you think the Lean statement over-claims relative to Darwin.

**Assistant:**

I should start by looking at the relevant files to understand the context.

I need to gather the claim labels from claims.json, check how load-claims.mjs parses report fields, and review the Thompson INSTRUCTIONS.md, SUMMARY.md, and assessments.json for ground-truth structure, while noting the various claim ids referenced across the struggle modules.

I'm working out that the module path comes from the first entry's lean declaration, so file names need to match module names, like DarwinLaws mapping to its Struggle.lean file. I also need to handle duplicate claim ids across reports, where the last one wins, and I'm considering whether secondary "with" claims should get their own entries.

Going through the list, I think ch01-16 can reasonably count as formalized since the probability argument about large numbers favoring selection is mathematically equivalent. For intro-02, which combines overproduction and slight variation leading to selection, I could formalize it using theorems from both underlying claims. But ch02-01, about individual differences supplying material for selection, isn't really a mathematical statement, so I'd mark that as not formalized with a reason, and the same goes for ch04-21 about competing neighbors belonging to different genera, since that's empirical rather than provable.

For ch03-12, the claim that congeners compete more severely doesn't follow from nicheOverlap without extra assumptions, so I'd lean toward not-formalized or heavily caveated. ch13-06 about varieties forming nested groups could reuse the clade_laminar theorem since it applies to any partial order, though I want to stay conservative and only mark something formalized when the theorem truly captures the claim's core. ch13-02 about the Natural System expressing descent isn't a mathematical proposition either. For ch02-08, about larger genera having more varieties, I'm weighing whether the Yule model's expected gain proportional to size actually matches Darwin's claim about proportion versus absolute count of varieties.

Working through more claims, I'm checking whether the Yule model's constant per-species rate actually matches Darwin's claim about larger genera having more varieties per species — since the model gives absolute scaling rather than the per-species ratio Darwin describes, I'll mark it not-formalized with that reasoning. I'm going through similar checks for the claim about small genera growing while large genera peak and decline (not covered by the pure-birth Yule model), the assumption that extinct species never reappear (better treated as a hypothesis than a theorem), and the claim about ancient species differing more from living ones, which I can tie to the olderFauna theorem with a scope note about shared lineages. Now I'm looking at whether different genera and classes evolve at different rates, considering how the expected time theorem might apply there.

I'll mark ch04-18 formalized in Succession citing theorems from both modules, since each half has a corresponding result even though the paths are fully qualified. For ch10-07, the gradualness claim is empirical, while the existing theorem only shows intermediate values are attained under unit steps — similarly ch10-06 assumes gradual steps as a premise rather than proving gradual rise and decline outright.

The Lean proof only shows that gradual change entails passing through every intermediate count, not that the dynamics are actually gradual—so marking it "formalized" would misrepresent the original claim as proved. Given the honesty principle that only formalized Lean reports count as proved, I'll mark both ch10-06 and ch10-07 as not-formalized and explain why in the reasons.

weakest point, then move through the remaining chapters: ch04-18 combines selection with rarity; ch12-04/05 and ch04-20 are model-dependent formalizations; ch03-11 uses Cauchy-Schwarz for niche overlap but I'm flagging it as somewhat tautological since self-overlap is trivially maximal under normalization. ch13-01 on tree-like descent producing laminar clades looks faithful and solid, and I'm now starting to work through ch04-24.

I continue classifying each chapter's formalization quality — ch02-15 (Yule model), ch14-07 (Poisson extinction), ch10-16 (range-through, combinatorially sound), and the sequence ch03-01 through ch04-01 covering Malthusian growth, stationarity giving s=1/r as trivial algebra, independent Bernoulli selection, and constant-fitness haploid models — before moving on to check intro-02 and ch01-16.

For intro-02, I'm matching the "overproduction plus slight profitable variation" claim against the Struggle theorems (not_all_survive and selectedTrajectory_tendsto_one), confirming both pieces are present and marking it formalized with a scope note. Ch01-16's claim about large population numbers favoring successful selection maps to probAnyFavourable in the artificial selection context, so that's formalized too, while ch02-01 remains not-formalized. Next I need to verify theorem existence programmatically, then move to gathering validation signals by checking SUMMARY.md, the claims.json fields for Darwin claims, the assessments.json structure, and briefly the Thompson instructions and MCP CLI help.

Now let me build a ranking table of Darwin claims by validation signals.

I should also check the truth and assessment for the remaining Lean-covered ids that weren't in the top 70.

I need to write up four reports and cross-check the theorem names against the actual Lean files using regex. Let me work through the struggle.json entries, starting with intro-02, which maps to several theorems like not_all_survive, survivalProduct_tendsto_zero, selectedFrequency_gt, and selectedTrajectory_tendsto_one, trying to pin down the right declaration.

Going down the list: ch01-16 pairs with probAnyFavourable plus strictMono and tendsto_one; ch02-01 isn't formalized; ch03-01 ties to geometricPopulation and its cluster of theorems (bounds, surplus, survival product); ch03-02 covers growthMultiplier and its lemmas; ch03-03 lacks a dedicated definition so I'll use stationary_survival_eq as both declaration and theorem, following the pattern from Thompson's ch08-09; and both ch04-01 and ch04-14 formalize selectedFrequency with the same set of selectedFrequency/selectedTrajectory theorems.

Now checking islands.json: ch03-11 formalizes nicheOverlap with its self and le_self lemmas, ch03-12 is unformalized, ch04-20 covers supportedLife with monotonicity and growth theorems, ch04-21 is unformalized, ch12-04 formalizes mwEquilibrium with its iff and monotonicity results including the remoter-island-poorer theorem, and ch12-05 introduces endemicFraction.

In tree.json, ch02-08 and ch02-09 are unformalized, ch02-15 formalizes expectedGenusSize with proportionality and ratio/gap results, ch04-24 covers PathAdditive with the ancestor-between lemma, ch13-01 formalizes TreeLike with clade_laminar and related theorems, ch13-02 is unformalized, and I'm checking whether ch13-06 counts as formalized since clade_laminar is generic enough to apply to varieties forming nested groups the same way species do.

I'm weighing whether labeling ch13-06 formalized is overreaching — the Lean theorem only shows that nesting follows IF descent is tree-like, not that varieties' descent actually is tree-like, which is the empirical claim ch13-06 makes. Given the emphasis on honesty, I'm leaning conservative and treating it as a conditional/structural match rather than a full formalization of the empirical assertion.

Now I'm going through the succession.json entries one by one, checking which chapters have formalized theorems versus which are marked not-formalized due to being empirical claims or hypotheses, making sure each has a clear reason attached.

But I'm catching a snag on ch10-06 and ch10-07: the previous agent authored "gradual_rise_and_fall" specifically to formalize those, so marking them not-formalized would leave that theorem orphaned without attribution.

I'm weighing whether gradualness itself is the empirical claim being tested, not just a side assumption, which means a theorem proving consequences under that hypothesis would overclaim. I decide to mark it not-formalized and flag the over-claiming issue in the final message, then apply the same reasoning to ch10-09's UnitStepsDown hypothesis about gradual decline.

That settles the classification as B. Now I'll move on to writing up the LaTeX notation for each and saving the files.

Now validate: claim ids exist, every theorem/declaration exists in the Lean sources, no duplicate claim ids across reports, and load-claims picks them up.

This looks like a pre-existing issue unrelated to my changes, probably from another agent's uncommitted work, so I shouldn't try to fix it directly. Instead I'm considering a workaround—maybe copying the load-claims logic somewhere I can modify without the throw, checking how ROOT is defined relative to the module's location first.

That failure is in someone else's in-progress Levin tests, not my files. I'll run a patched copy from /tmp that skips the throw.

I see the module path issue stems from load-claims using the first entry's lean_declaration to derive the directory, but my first Tree entry isn't formalized. The straightforward fix is just reordering Tree.json so a formalized entry comes first, even though Thompson's Cells.json has the same underlying issue.

With Task 1 finished (20 formalized, 10 declined), I'm moving to Task 2's screening report. I need to pull the top 50 claims by composite score plus the Lean-covered set of 30, taking their union (roughly 60 total), then gather statements for all of them so I can classify each one.

I need to classify all 68 claims now, so I'm setting up a scheme to generate a candidates file and then build the report from it for consistency. I'm defining categories like "faithful precise math statement" versus "model-dependent," where the latter has a formal core but relies on unstated assumptions from a named model.

Going through the Lean-formalized claims one by one, I'm weighing whether each belongs in the precise category or the model-dependent one—several like the Malthusian overproduction argument, the stationary population identity, and the haploid selection cases are borderline, since their formal versions often simplify or add structure not explicit in Darwin's original wording.

Then for the declined cases, I'm noting which ones might actually be rescuable with a different kind of model, like a rate-heterogeneity process for varieties arising per species, or a birth-death process for genus survival, versus which ones are purely empirical and resist formalization.

Expected trajectory under birth-death conditioned on extinction rises and falls, a real result (Nee et al.), so I mark that B future. The remaining non-Lean cases—electric organ convergence, biogeography patterns, historical/geological claims, and cave fauna relatedness to local surface species—mostly look like C (empirical/historical), though the cave fauna one might be arguable as B if colonization is strictly local.

I'm now checking barrier-isolation claims: an island-model F_ST-like measure 1/(1+4Nm) decreases with migration rate and divergence grows with time under drift/mutation, which matches "more impassable and long-standing barriers → greater difference," so this is a promising B candidate via Wright's island model. The succession-of-types claim stays C despite tempting tree+geography framing, and I continue through the remaining historical/empirical items marking them C.

For ch12-18, Brownian motion on a phylogeny gives a clean B formalization: expected squared geographic distance between two tips equals 2σ² times divergence time, strictly increasing with patristic distance — this becomes my top B candidate. I mark ch11-14 and ch14-03 as C, then start exploring whether Darwin's argument about trees favoring separate sexes (to avoid self-pollination among many flowers) could be formalized probabilistically as another B candidate.

Continuing through more chapters: geitonogamy models where self-pollen proportion scales with flowers per individual are weak B candidates, while ch12-02, ch12-08, and ch11-16 get marked C. For ch08-02, inbreeding depression offers a stronger B formalization via standard quantitative genetics — fitness declining with inbreeding coefficient F, either linearly with dominance or multiplicatively across loci (ln W(F) = ln W(0) − BF), which I flag as a solid candidate before marking ch07-04 as C.

For ch04-22, I'm working through whether naturalised floras gaining proportionally more genera than species can be formalized as a statistical sampling property: if n species are drawn randomly from a pool partitioned into genera, the fraction of genera represented should be at least the fraction of species sampled, since each genus only needs one representative species to count. This feels like a workable B candidate built on random sampling from a genus-structured pool.

For ch12-09, I'm settling on C, treating that one as refuted.

Then ch13-08 also gets C. For ch09-03, I'm flagging it as A — it's a clean arithmetic case: time equals distance over rate, applied to the Weald denudation estimate (22 miles at 1 inch/century yields roughly 300 million years). Even though the underlying geological assumption is wrong, the math itself is a faithful, trivially-formalizable statement, so it's worth including as a low-value but honest Class A example. ch14-01 and ch11-13 both land as C.

Moving on, ch12-10, ch09-14, ch11-06, ch01-09, ch10-12, ch14-02, ch09-04 (taphonomy), and ch06-17 all come out as C. ch12-11 is a tentative B — depth could predict genetic affinity through a sea-level model where shallower channels were more recently land bridges, meaning less time since isolation and thus less divergence; it's a weak, forward-looking case. ch08-13 is also a possible B, built around the Mendelian expectation that an F1 generation between two homozygous lines should be uniform while F2 segregates, so variance in F2 should exceed variance in F1.

I'm tallying that this counts as a strong, precise A/B candidate rooted in Mendelian inheritance, even though Darwin himself wouldn't have had this framework — genetic variance in F1 should be zero while F2 shows measurable segregating variance. intro-04 and ch14-04 come out as C, and ch12-12 is mostly C with a faint possible B via dispersal distance-decay. I'm noting the list is now around 68 items, comfortably within the 40-60 range the user asked for, and I still need to finish tallying the unformalized A/B candidates, including ch12-18 (Brownian motion on a tree) and ch11-02 (island model F_ST).

Now I'm planning to write candidates.json alongside a small script that builds the classification data as a structured object, then generates REPORT.md from it. I'll draft that generator in a temporary location, run it, and clean it up afterward.

I should verify the ch09-03 Weald numbers against Darwin's actual text before proceeding, so let me search the source for those figures.

Working through Darwin's arithmetic: converting 22 miles to inches gives 1,393,920 inches, which at one inch per century yields 139,392,000 years for a 500ft cliff rate, then scaling to 1100ft gives exactly 306,662,400 years. So the formula is T = D × (h/500ft) / v, and I need to update the equation accordingly.

I need to correct the math: 68 total is 45 top scores plus 23 non-overlapping additions, since 7 of the 30 Lean ids already appear in the top 45. I should fix this in the generator and regenerate the data.

That manifest.jsonl change isn't something I made, so I want to verify it was already modified before I touched anything—checking the file's timestamp since git diff alone won't tell me when it changed.

The manifest.jsonl timestamp predates my session, confirming that diff was already there before I touched anything. Good, I can finalize my message now.

## Files written

- `claim-sources/darwin-origin/lean/reports/{Struggle,Islands,Tree,Succession}.json` (Thompson `Cells.json` format; every claim id checked against `claims.json`, every declaration/theorem checked against the `.lean` sources; no duplicate ids across reports).
- `claim-sources/darwin-origin/formalization/REPORT.md` and `candidates.json`.

No `.lean` file, `claims.json`, `docs/` or nanopub was touched. Sanity check: `loadClaims()` picks up 20 Darwin claims with `proof: "lean"`, `theorem: true`, module paths `claim-sources/darwin-origin/lean/DarwinLaws/<Module>.lean`, and 10 as "Lean formalization attempted and declined". (Two quirks: `load-claims.mjs` currently throws on three in-progress Levin tests lacking `data_kind`, unrelated to this work, so I ran a patched copy from `/tmp`; and it derives the module path from the *first* entry's `lean_declaration`, so I moved `ch02-15` to the top of `Tree.json`.)

## Claims now formalized (20)

**Struggle.lean**
- `ch03-01` Geometric increase \(N_0 r^t\), \(r>1\), in a world bounded by \(K\) ⇒ surplus unbounded, cumulative survival fraction → 0.
- `ch03-02` At fixed fecundity, higher survival gives a higher multiplier; growth to any size \(M\) in \(\log(M/N_0)/\log\lambda\) generations.
- `ch03-03` Stationary population ⇒ \(s = 1/r\).
- `ch04-01` Haploid constant-fitness selection: any advantage raises frequency, disadvantage lowers it, trajectory → 1.
- `ch04-14`, `ch01-16` \(1-(1-p)^N\) strictly increasing in \(N\), → 1.
- `intro-02` The two results above combined (struggle + selection).

**Islands.lean**
- `ch12-04` MacArthur–Wilson \(S^* = PI/(I+E) < P\), decreasing in distance at equal area.
- `ch12-05` Two-state chain: endemic fraction \(\sigma/(\sigma+m)\) rises with isolation.
- `ch04-20` Additive resource partition: unused resources ⇒ strictly less life supported.
- `ch03-11` Cauchy–Schwarz: niche overlap with any other form ≤ self-overlap (= 1).

**Tree.lean**
- `ch13-01` Tree-like descent ⇔ clades are nested or disjoint (groups subordinate to groups).
- `ch13-06` Same theorem, read for varieties (derivative).
- `ch04-24` In a path-additive metric the common ancestor is metrically between its descendants.
- `ch02-15` Yule: expected gain ∝ size; absolute gap between genera grows; ratio constant.

**Succession.lean**
- `ch10-16` Range-through faunas: shared lineages are present in all intermediate stages; shared counts weakly antitone in distance; Markov \(p^k\) strictly decreasing.
- `ch10-13` Older fauna shares no more lineages with the living than a younger one.
- `ch14-07` Poisson turnover \(1-e^{-\mu D}\): strictly increasing in \(D\), exactly invertible, and increasing in \(\mu\) (the "imperfect" clause).
- `ch10-09` Unit-step decline ⇒ count hits 1 before 0.
- `ch04-18` Selection against the less favoured + the ch10-09 lemma.

Declined (not-formalized, reason recorded): `ch02-01`, `ch02-08`, `ch02-09`, `ch03-12`, `ch04-21`, `ch10-02`, `ch10-04`, `ch10-06`, `ch10-07`, `ch13-02`. 46 of 48 theorems are attributed; `exists_eq_of_unitStepsUp` and `gradual_rise_and_fall` are left as lemmas (see over-claiming below).

## Screening counts (68 claims: top 45 by composite validation score ∪ 30 Lean-named ids)

- **A** 5 (4 formalized: `ch03-01`, `ch13-01`, `ch13-06`, `ch10-16`; 1 not: `ch09-03`)
- **B** 26 (16 formalized; 10 not)
- **C** 37

## Top unformalized A/B candidates (LaTeX + assumptions in REPORT.md)

1. `ch12-18` Closer relatives closer in space: Brownian dispersal on a tree, \(\mathbb{E}\|X_i-X_j\|^2 = 2\sigma^2\tau_{ij}\) (B; data test supports 0.75).
2. `ch08-13` F1 uniform, F2 variable: Mendelian \(\mathrm{Var}_G(F_1)=0\), \(\mathrm{Var}_G(F_2)=\sum(\tfrac12 a^2+\tfrac14 d^2)>0\) (B; Darwin's pattern is right, his explanation wrong).
3. `ch11-02` Barriers ↔ biotic difference: island model \(F_{ST}=1/(1+4Nm)\) decreasing in \(m\), increasing in time (B; supports 0.8).
4. `ch08-02` Inbreeding depression \(\ln\bar W(F)=\ln\bar W(0)-BF\) (B).
5. `ch10-06` Rise-and-fall: birth–death conditioned on extinction gives a unimodal expected trajectory (B; would replace the current assume-the-shape lemma).
6. `ch02-09` Birth–death: extinction certain when \(\mu\ge\lambda\), yet positive probability of reaching any size (B).
7. `ch09-03` Weald arithmetic: \(1{,}393{,}920\,\text{in}\times100\times\tfrac{1100}{500} = 306{,}662{,}400\) yr, reproduces Darwin's figure exactly (A; trivially true, empirically refuted premise).
8. Weaker: `ch04-13` (geitonogamy fraction), `ch10-04` (Dollo as measure-zero), `ch12-11`, `ch04-22`.

## Where the Lean over-claims relative to Darwin

1. **`ch10-09`** (and half of `ch04-18`): the hypothesis "numbers fall at most one per period" *is* the gradualist premise; the proof only shows gradual decline logically entails prior rarity and cannot distinguish Darwin from Cuvier. Kept formalized because the conclusion differs from the hypothesis, but it is the thinnest result. `ch10-06`/`ch10-07`, whose lemma has the conclusion nearly restating the hypothesis, I marked not-formalized.
2. **`ch03-11`**: Cauchy–Schwarz self-overlap maximality is close to a tautology of the chosen measure; the biology is assumed.
3. **`ch03-03`**: \(s=1/r\) is a one-line identity and proves far less than "abundance depends only indirectly on fecundity".
4. **`ch04-24`**: betweenness of the LCA under additivity is immediate; most extinct species are not ancestors.
5. **`ch13-06`**: nothing proved beyond `ch13-01`; could be demoted to not-formalized without loss if you prefer one theorem per distinct piece of mathematics.
6. **`ch02-15`**: Yule gives a growing absolute gap but a constant ratio, weaker than "dominant forms become more dominant" (truth score 0.40 agrees).
7. **`ch12-04`/`ch12-05`**: sound but prove monotonicities in distance, not Darwin's quantitative contrasts; the empirical support is the data test.

_Tools used: Read ×8, Shell ×18, StrReplace, UpdateCurrentStep ×5, Write ×5_
