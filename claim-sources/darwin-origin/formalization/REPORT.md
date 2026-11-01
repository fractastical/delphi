# Formalization screening: Darwin, *On the Origin of Species* (1859)

Which of the best-validated Darwin claims are mathematical propositions, which are only
formalizable inside a named model, and which are not mathematics at all. Built from the
validation signals in `docs/claims.json` (data-test verdicts from
`test-data/claim-tests/darwin-origin/`, model truth scores) and
`claim-sources/darwin-origin/assessment/assessments.json`, together with the Lean 4 project
`claim-sources/darwin-origin/lean/` (lib `DarwinLaws`) and its reports in
`lean/reports/*.json`. Machine-readable version: [candidates.json](candidates.json).

## How to read this

- **Validation signals** are evidence that organisms behave as Darwin said. They never make a
  claim a theorem. A claim is *proved* only through a `formalized` entry in a Lean report, which
  means a statement with explicit hypotheses was accepted by the Lean kernel with no `sorry` and
  only the standard axioms.
- **Class A**: the claim, as Darwin states it, is (or has as its core) a precise mathematical
  proposition whose premises are part of the claim. **Class B**: a formal core exists only inside
  a model whose assumptions go beyond Darwin's wording; the model is named, and the proof shows
  the conclusion follows from the model, not that nature satisfies it. **Class C**: no mathematical
  proposition; a one-line reason is given.
- **Composite score** (for ranking only): data-test weight (supports 2, refutes 1.5, mixed 1,
  inconclusive 0.5) × test confidence, plus the model truth score, plus the mean assessor
  `overall`. Maximum about 3.9.

## Counts

| | |
|---|---|
| Claims screened | 68 (top 45 by composite score ∪ every id named in the Lean modules) |
| Class A | 5 (4 formalized) |
| Class B | 26 (16 formalized) |
| Class C | 37 |
| Formalized in Lean (reports say `formalized`) | 20 |
| Declined in Lean reports (`not-formalized`, reason recorded) | 10 |
| A/B candidates not yet formalized | 11 |

Of the 48 theorems in `DarwinLaws`, 46 are attributed to a formalized claim; the two left
unattributed (`Succession.exists_eq_of_unitStepsUp`, `Succession.gradual_rise_and_fall`) were
written for ch10-06/ch10-07 and are kept as lemmas because their hypothesis (gradual change) is
the whole content of those claims.

## Ranked table

| # | Claim | Class | Data test | Truth | Assess. | Lean | Model / reason |
|---|---|---|---|---|---|---|---|
| 1 | `darwin1859-ch06-10` Selection can independently produce similar organs in distantly related beings | C | supports (0.95) | 0.96 | 0.78 | no | Historical statement that convergence has occurred (electric organs); no derivation from premises. |
| 2 | `darwin1859-ch12-04` Oceanic islands have fewer species than equal continental areas | B | supports (0.9) | 0.94 | 0.86 | yes (Islands.lean) | MacArthur–Wilson immigration–extinction equilibrium with immigration decreasing in distance |
| 3 | `darwin1859-ch10-16` Fossils from consecutive formations are more alike than those from remote ones | A | supports (0.9) | 0.91 | 0.83 | yes (Succession.lean) | — |
| 4 | `darwin1859-ch12-05` Oceanic islands have a very high proportion of endemic species | B | supports (0.85) | 0.94 | 0.81 | yes (Islands.lean) | two-state Markov chain per lineage (divergence rate σ, replacement rate m decreasing in distance) |
| 5 | `darwin1859-ch11-03` Species of the same continent or sea are related despite differing stations | C | supports (0.85) | 0.93 | 0.80 | no | Empirical biogeographic pattern (regional affinity across habitats). |
| 6 | `darwin1859-ch14-12` Succession by generation has never been broken by a world-wide cataclysm | C | supports (0.85) | 0.97 | 0.74 | no | Historical negative existential (no world-wide cataclysm); its logical form (unbroken descent ⇒ no total extinction) is a restatement. |
| 7 | `darwin1859-ch11-08` Continents and oceanic islands were not united by land in the recent period | C | supports (0.9) | 0.78 | 0.81 | no | Geological-historical inference about land bridges. |
| 8 | `darwin1859-ch05-06` Cave animals are related to surface fauna of their own continent | C | supports (0.8) | 0.94 | 0.84 | no | Prediction about affinities of cave faunas; follows from local colonisation only tautologically. |
| 9 | `darwin1859-ch01-10` All domestic pigeon breeds descend from the rock-pigeon | C | supports (0.75) | 0.97 | 0.86 | no | Historical inference about pigeon ancestry. |
| 10 | `darwin1859-ch11-02` Barriers to migration correspond closely to differences between regional biotas | B | supports (0.8) | 0.91 | 0.79 | no | Wright's island model of two demes exchanging migrants at rate m across the barrier, with drift for time t |
| 11 | `darwin1859-ch10-18` Each region's fossils are succeeded by allied living forms in the same region | C | supports (0.8) | 0.90 | 0.76 | no | Law of succession of types; empirical/historical pattern. |
| 12 | `darwin1859-ch12-01` Fresh-water species range widely and allied species occur worldwide | C | supports (0.75) | 0.86 | 0.80 | no | Empirical statement about ranges of fresh-water taxa. |
| 13 | `darwin1859-ch11-01` Physical conditions do not explain the similarity or dissimilarity of regional biotas | C | supports (0.75) | 0.82 | 0.83 | no | Negative empirical statement (climate does not predict biotic similarity). |
| 14 | `darwin1859-ch10-02` Species of different genera and classes change at different rates | C | supports (0.7) | 0.97 | 0.76 | declined | Empirical statement that rates differ between groups; only its consequence (more turnover at higher hazard) is provable, and is proved under ch14-07. |
| 15 | `darwin1859-ch12-18` Closer relatives tend to be closer together in time and space | B | supports (0.75) | 0.80 | 0.77 | no | Brownian motion of geographic position along a phylogeny (dispersal variance σ² per unit time) |
| 16 | `darwin1859-ch11-14` Plants of high mountains and temperate lowlands worldwide are identical or closely related | C | supports (0.8) | 0.67 | 0.80 | no | Empirical floristic pattern. |
| 17 | `darwin1859-ch14-03` All living things share chemical composition, cell structure and laws of growth | C | supports (0.7) | 0.79 | 0.81 | no | Empirical statement of shared biochemistry and cell structure. |
| 18 | `darwin1859-ch04-13` Trees more often have separate sexes than other plants | B | supports (0.7) | 0.79 | 0.81 | no | random pollen movement among the flowers of an individual (geitonogamy) versus between individuals |
| 19 | `darwin1859-ch12-02` Fresh-water fish species are not shared between distant continents | C | refutes (0.8) | 0.84 | 0.88 | no | Empirical (and refuted) distributional statement. |
| 20 | `darwin1859-ch12-08` Frogs, toads and newts are absent from oceanic islands | C | refutes (0.93) | 0.63 | 0.88 | no | Empirical (and refuted) distributional statement with a dispersal-barrier explanation. |
| 21 | `darwin1859-ch11-16` Northern species naturalise far more often in the south than the reverse | C | refutes (0.7) | 0.85 | 0.85 | no | Empirical asymmetry in naturalisation (refuted). |
| 22 | `darwin1859-ch08-02` Close interbreeding lowers fertility while occasional crossing raises it | B | supports (0.65) | 0.67 | 0.75 | no | multiplicative multilocus model with partially recessive deleterious alleles; fitness as a function of the inbreeding coefficient F |
| 23 | `darwin1859-ch07-04` Instincts vary within species in a state of nature | C | mixed (0.7) | 0.97 | 0.84 | no | Empirical statement that instincts vary. |
| 24 | `darwin1859-ch04-22` Naturalised floras add proportionally more new genera than new species | B | supports (0.55) | 0.57 | 0.84 | no | random sampling of n colonist species from a species pool partitioned into genera |
| 25 | `darwin1859-ch12-09` No native terrestrial mammals on islands more than 300 miles from a continent | C | refutes (0.9) | 0.28 | 0.87 | no | Empirical (refuted) distributional statement with a distance threshold. |
| 26 | `darwin1859-ch14-07` Amount of fossil change between formations measures elapsed time | B | supports (0.7) | 0.34 | 0.76 | yes (Succession.lean) | constant-hazard (Poisson) extinction, expected turnover 1 − e^{−μD} |
| 27 | `darwin1859-ch13-08` Distinct lineages adapted to similar conditions converge in external form | C | mixed (0.75) | 0.94 | 0.77 | no | Historical statement about convergence and its taxonomic value. |
| 28 | `darwin1859-ch09-03` Denudation of the Weald implies roughly 300 million years since the late Chalk | A | refutes (0.98) | 0.02 | 0.94 | no | — |
| 29 | `darwin1859-ch14-01` Descent with modification embraces all members of each class | C | mixed (0.6) | 0.96 | 0.80 | no | Historical inference from chains of affinities. |
| 30 | `darwin1859-ch11-13` The Glacial period was simultaneous across the whole world | C | mixed (0.75) | 0.74 | 0.86 | no | Palaeoclimatic claim about synchrony. |
| 31 | `darwin1859-ch12-10` Bats occur on almost every island, often as endemic species | C | mixed (0.7) | 0.78 | 0.85 | no | Empirical distributional statement about bats. |
| 32 | `darwin1859-ch09-14` Oceans and continents have kept roughly their present positions since the Silurian | C | refutes (0.95) | 0.04 | 0.82 | no | Geological-historical claim (refuted). |
| 33 | `darwin1859-ch12-11` Sea depth between island and mainland predicts their mammalian affinity | B | mixed (0.6) | 0.90 | 0.78 | no | isolation time increasing in channel depth (sea-level history) and divergence increasing in isolation time |
| 34 | `darwin1859-ch11-06` Many genera are confined to one region and the most natural genera are local | C | mixed (0.7) | 0.77 | 0.78 | no | Empirical statement about endemism of taxa. |
| 35 | `darwin1859-ch01-09` Domestic dogs descend from several wild species | C | refutes (0.85) | 0.07 | 0.86 | no | Historical inference (refuted). |
| 36 | `darwin1859-ch10-12` Marine forms of life change almost simultaneously throughout the world | C | mixed (0.6) | 0.71 | 0.82 | no | Empirical statement about synchrony of marine faunal change. |
| 37 | `darwin1859-ch10-06` Groups rise gradually in species number to a maximum, then gradually decline | B | mixed (0.7) | 0.60 | 0.80 | declined | constant-rate birth–death process conditioned on eventual extinction |
| 38 | `darwin1859-ch14-02` Animals from at most four or five progenitors, plants from as many or fewer | C | inconclusive (0.5) | 0.95 | 0.79 | no | Historical inference about the number of progenitors. |
| 39 | `darwin1859-ch09-04` Soft-bodied organisms and remains on non-depositing sea floor are not preserved | C | mixed (0.85) | 0.28 | 0.81 | no | Taphonomic generalization. |
| 40 | `darwin1859-ch10-07` Species and groups disappear gradually, place by place, not by global catastrophes | C | mixed (0.6) | 0.49 | 0.77 | declined | Gradual, place-by-place extinction is the empirical question (mass extinctions exist); it is the hypothesis of the existing lemmas, not a conclusion. |
| 41 | `darwin1859-ch06-17` Unity of type is explained by unity of descent | C | — | 0.98 | 0.80 | no | Explanatory claim (unity of type by descent); not a proposition with a proof. |
| 42 | `darwin1859-ch08-13` Hybrids vary little in the first generation but greatly in later generations | B | mixed (0.5) | 0.53 | 0.75 | no | Mendelian inheritance at unlinked diallelic loci from two inbred (homozygous) parental lines |
| 43 | `darwin1859-intro-04` Species are not immutable but descend from other, mostly extinct, species | C | — | 0.97 | 0.78 | no | Historical thesis of descent. |
| 44 | `darwin1859-ch12-12` Island endemics are related to species of the nearest continent | C | — | 0.91 | 0.76 | no | Empirical biogeographic rule; a dispersal-distance model would assume it. |
| 45 | `darwin1859-ch14-04` Probably all organisms descend from one primordial form | C | — | 0.92 | 0.73 | no | Historical inference by analogy. |
| 47 | `darwin1859-ch03-01` Overproduction makes a struggle for existence inevitable | A | — | 0.95 | 0.69 | yes (Struggle.lean) | — |
| 49 | `darwin1859-ch10-04` A species that has gone extinct never reappears | B | — | 0.93 | 0.70 | declined | character state as a point in a continuous (or very large discrete) space evolving by a non-atomic process |
| 52 | `darwin1859-ch13-01` Descent with divergence and extinction produces groups subordinate to groups | A | — | 0.95 | 0.67 | yes (Tree.lean) | — |
| 55 | `darwin1859-ch10-09` Rarity precedes extinction | B | — | 0.88 | 0.74 | yes (Succession.lean) | integer count falling by at most one per period (gradual decline) |
| 56 | `darwin1859-ch02-09` Small genera often grow large while large genera peak, decline and vanish | B | — | 0.86 | 0.75 | declined | linear birth–death process per genus (speciation λ, extinction μ) |
| 62 | `darwin1859-ch02-01` Individual differences supply the material for natural selection | C | — | 0.97 | 0.62 | declined | Identifies the source of heritable variation; existential statement about populations, not a consequence of premises. |
| 75 | `darwin1859-ch10-13` The more ancient a form, the more it differs from living forms | B | — | 0.84 | 0.70 | yes (Succession.lean) | range-through faunas; 'difference' = fewer shared lineages with the living fauna |
| 76 | `darwin1859-intro-02` Overproduction plus slight profitable variation leads to natural selection | B | — | 0.94 | 0.61 | yes (Struggle.lean) | geometric increase in a bounded world + constant-fitness haploid selection |
| 79 | `darwin1859-ch01-16` Keeping large numbers of individuals favours successful selection | B | — | 0.95 | 0.59 | yes (Struggle.lean) | same Bernoulli model as ch04-14 |
| 80 | `darwin1859-ch04-01` Natural selection preserves favourable and destroys injurious variations | B | — | 0.93 | 0.61 | yes (Struggle.lean) | deterministic constant-fitness haploid selection (infinite population, no drift/mutation) |
| 83 | `darwin1859-ch04-14` Large populations favour natural selection by supplying more variations | B | — | 0.93 | 0.60 | yes (Struggle.lean) | independent Bernoulli appearance of a favourable variation with common probability p |
| 89 | `darwin1859-ch03-03` Average abundance depends only indirectly on fecundity | B | — | 0.83 | 0.66 | yes (Struggle.lean) | stationary population with constant fecundity r and survival s |
| 90 | `darwin1859-ch13-06` Varieties form nested groups for the same reason species do | A | — | 0.91 | 0.59 | yes (Tree.lean) | — |
| 92 | `darwin1859-ch03-02` Geometrical increase explains rapid spread of naturalised species | B | — | 0.84 | 0.65 | yes (Struggle.lean) | geometric growth with multiplier r·s; lowered mortality s' > s |
| 99 | `darwin1859-ch04-24` Extinct species are often intermediate between living groups | B | — | 0.82 | 0.66 | yes (Tree.lean) | nonnegative path-additive (tree) metric on character space |
| 107 | `darwin1859-ch04-20` Divergence of character maximises the life an area supports | B | — | 0.79 | 0.67 | yes (Islands.lean) | additive resource partition: life supported = Σ K_i over resources used |
| 110 | `darwin1859-ch13-02` The Natural System expresses propinquity of descent | C | — | 0.82 | 0.63 | declined | A claim about what classifications track; showing that resemblance-based groups recover clades is phylogenetic-inference theory under a character model, not a proposition in Darwin's text. |
| 131 | `darwin1859-ch04-18` Favoured forms make less favoured forms rare, and rarity precedes extinction | B | — | 0.66 | 0.70 | yes (Succession.lean) | constant-fitness selection (first half) + unit-step decline in numbers (second half) |
| 135 | `darwin1859-ch02-08` Species of larger genera more often present varieties | C | — | 0.61 | 0.73 | declined | Tabulation result about the proportion of varying species; a constant per-species rate gives no such effect, and a size-dependent rate assumes it. |
| 153 | `darwin1859-ch03-11` Struggle is most severe between members of the same species | B | — | 0.73 | 0.56 | yes (Islands.lean) | MacArthur–Levins niche overlap (cosine similarity of utilisation vectors) |
| 158 | `darwin1859-ch03-12` Congeners compete more severely than species of different genera | C | — | 0.64 | 0.64 | declined | Within the niche-overlap model it reduces to 'congeners have more similar utilisation vectors', an empirical premise. |
| 168 | `darwin1859-ch04-21` The closest-competing neighbours tend to belong to different genera and orders | C | — | 0.56 | 0.69 | declined | Taxonomic composition of small plots; no derivation from stated premises without assuming genera map to resources. |
| 206 | `darwin1859-ch02-15` Larger genera tend to grow larger and dominant forms more dominant | B | — | 0.41 | 0.62 | yes (Tree.lean) | Yule pure-birth process, expectations only |

## Where the Lean statements over-claim, or nearly do

Ordered from most to least concerning. None of these is a wrong proof; each is a place where the
theorem's hypothesis carries the claim's empirical content, so reading the Lean as a confirmation
of Darwin would be a mistake.

1. **ch10-09 Rarity precedes extinction** (and the second half of ch04-18). Hypothesis: numbers fall
   by at most one per period. Conclusion: the count equals 1 before 0. The hypothesis *is* the
   gradualist premise, and it is exactly what catastrophic extinction violates. The report keeps it
   formalized because the conclusion (rarity) is distinct from the hypothesis (no sudden wipe-out),
   but this is the thinnest result in the project. ch10-06 and ch10-07, whose lemma
   `gradual_rise_and_fall` has the same structure with the conclusion a near-restatement of the
   hypothesis, are marked *not-formalized* for that reason.
2. **ch03-11 Struggle most severe within species.** Cauchy–Schwarz on utilisation vectors: self-overlap
   is maximal. Any normalised inner-product similarity has this property, so the theorem is close to a
   tautology of the measure; the biological content (that overlap in resource use is what makes
   competition severe) is assumed.
3. **ch03-03 Abundance depends only indirectly on fecundity.** The proof is the identity s = 1/r at
   stationarity. It shows N is not fixed by r alone, which is far less than Darwin's statement about
   what *does* set average numbers.
4. **ch04-24 Extinct species intermediate between living groups.** Given a path-additive metric, the
   common ancestor is between its descendants; immediate. Most extinct species are side branches,
   not ancestors, and 'intermediate in character' is not metric betweenness.
5. **ch13-06 Varieties nest for the same reason species do.** Nothing is proved beyond ch13-01; the
   report marks it formalized only because the theorem is rank-free. If the project wants one theorem
   per distinct piece of mathematics, this entry could be dropped to *not-formalized* without loss.
6. **ch02-15 Larger genera grow larger.** The Yule model gives a growing *absolute* gap and a *constant
   ratio*; Darwin's 'dominant forms become more dominant' suggests a relative advantage the model
   does not deliver. The truth score (0.40) already reflects this.
7. **ch12-04 / ch12-05 Islands.** MacArthur–Wilson and a two-state endemism chain. The theorems are
   sound, but 'fewer species than equal continental areas' and 'very high proportion of endemics' are
   proved only as monotonicities in distance, not as the quantitative contrasts Darwin reports; the
   supporting evidence is the data test, not the proof.

## Formalized claims

### `darwin1859-ch12-04` — Oceanic islands have fewer species than equal continental areas

- Class B; model: MacArthur–Wilson immigration–extinction equilibrium with immigration decreasing in distance. Rank 2 (score 3.59); data test supports (0.9); truth 0.94; assessors 0.86.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Islands.lean`, declaration `DarwinLaws.Islands.mwEquilibrium`, theorems `Islands.mwEquilibrium_iff`, `Islands.mwEquilibrium_lt_pool`, `Islands.mwEquilibrium_strictMono_I`, `Islands.mwEquilibrium_strictAnti_E`, `Islands.remoter_island_poorer`.
- Statement: $I(P - S) = E S \iff S^* = \frac{P I}{I + E};\quad E > 0 \Rightarrow S^* < P;\ \partial S^*/\partial I > 0,\ \partial S^*/\partial E < 0;\quad d_1 < d_2 \Rightarrow S^*(I(d_2)) < S^*(I(d_1))$
- Assumptions: MacArthur–Wilson (1963) equilibrium theory: a source pool of P > 0 species; absent species immigrate at a per-species rate I ≥ 0 that is a strictly decreasing function of distance from the source; resident species go extinct at a per-species rate E > 0 set by area; richness S is the balance point I(P − S) = E S. 'Equal continental area' is read as equal E with the continent at the near (high-immigration) limit.
- Scope: Model-dependent (MacArthur–Wilson). Proves that the equilibrium richness is unique, lies strictly below the pool whenever extinction is positive, rises with immigration and falls with extinction, and that at equal area a remoter island is strictly poorer. It does not prove that islands sit at equilibrium, that immigration falls with distance (assumed), that extinction depends on area only, or anything about in-situ speciation, which the model omits. Darwin's clause that the deficit is 'not explained by physical conditions' is not represented; the theorem shows isolation suffices, not that conditions are irrelevant. The empirical support is the data test, not this proof.

### `darwin1859-ch10-16` — Fossils from consecutive formations are more alike than those from remote ones

- Class A. Rank 3 (score 3.53); data test supports (0.9); truth 0.91; assessors 0.83.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Succession.lean`, declaration `DarwinLaws.Succession.fauna`, theorems `Succession.shared_subset_fauna_between`, `Succession.shared_antitone_right`, `Succession.shared_antitone_left`, `Succession.persistence_strictAnti`.
- Statement: $i \le j \le k \Rightarrow F_i \cap F_k \subseteq F_j,\ |F_i \cap F_k| \le |F_i \cap F_j|,\ |F_i \cap F_k| \le |F_j \cap F_k|;\quad \text{Markov: } p^n < p^m\ (0 < p < 1,\ m < n)$
- Assumptions: Range-through model: each lineage occupies a single stage interval [first, last] (darwin1859-ch10-04), the fauna of a stage is the set of lineages covering it, and similarity between two stages is the number of shared lineages. For the strict version: each lineage persists across a stage boundary independently with constant probability 0 < p < 1 (Markov turnover), and expected similarity k stages apart is p^k.
- Scope: Proves (1) intermediacy: any lineage common to two stages is present in every stage between them, so the intermediate fauna is intermediate; (2) decay: shared-lineage counts are weakly antitone in stratigraphic distance, a purely combinatorial fact needing no rates; (3) under the constant-rate Markov idealisation the expected similarity strictly decreases with separation. The combinatorial part is faithful to Darwin's wording provided 'closely related' means 'shares lineages', which the data test also uses (Jaccard-type similarity on PBDB genera). It does not address morphological relatedness of non-shared lineages, and the weak inequality allows plateaus; strictness is model-dependent. The range-through assumption is Darwin's own ch10-04 and is not proved.

### `darwin1859-ch12-05` — Oceanic islands have a very high proportion of endemic species

- Class B; model: two-state Markov chain per lineage (divergence rate σ, replacement rate m decreasing in distance). Rank 4 (score 3.44); data test supports (0.85); truth 0.94; assessors 0.81.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Islands.lean`, declaration `DarwinLaws.Islands.endemicFraction`, theorems `Islands.endemicFraction_iff`, `Islands.endemicFraction_strictAnti_m`, `Islands.remoter_island_more_endemic`.
- Statement: $\sigma(1 - \pi) = m \pi \iff \pi^* = \frac{\sigma}{\sigma + m};\quad m_1 < m_2 \Rightarrow \pi^*(m_2) < \pi^*(m_1);\quad d_1 < d_2 \Rightarrow \pi^*(m(d_1)) < \pi^*(m(d_2))$
- Assumptions: Each resident lineage is a two-state Markov chain: a non-endemic resident diverges into an endemic species at rate σ > 0, and an endemic is replaced or genetically swamped by renewed immigration from the source at rate m ≥ 0, with m a strictly decreasing function of distance. The endemic fraction is the stationary probability of the endemic state.
- Scope: Model-dependent (two-state divergence/replacement chain, built for this claim rather than taken from the literature). Proves that the stationary endemic fraction is σ/(σ + m), falls strictly as replacement rises, and so is higher on remoter islands. It does not prove 'very high' or 'extremely large relative to area' (no quantitative threshold), does not treat extinction of endemics without replacement, time since colonisation, or the 'often' in Darwin's wording; the stationary distribution may not be reached. The relation of m to immigration is assumed, not derived from darwin1859-ch12-04's I.

### `darwin1859-ch14-07` — Amount of fossil change between formations measures elapsed time

- Class B; model: constant-hazard (Poisson) extinction, expected turnover 1 − e^{−μD}. Rank 26 (score 2.5); data test supports (0.7); truth 0.34; assessors 0.76.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Succession.lean`, declaration `DarwinLaws.Succession.expectedTurnover`, theorems `Succession.expectedTurnover_strictMono`, `Succession.elapsedTime_expectedTurnover`, `Succession.expectedTurnover_strictMono_in_hazard`.
- Statement: $T(D) = 1 - e^{-\mu D};\ \mu > 0,\ D_1 < D_2 \Rightarrow T(D_1) < T(D_2);\quad D = -\frac{\log(1 - T)}{\mu};\quad \mu_1 < \mu_2 \Rightarrow T_{\mu_1}(D) < T_{\mu_2}(D)$
- Assumptions: Constant-hazard (Poisson) extinction: each lineage goes extinct independently at a constant rate μ > 0, so the expected fraction of lineages lost over a duration D is 1 − e^{−μD}; μ is known when reading time from turnover.
- Scope: Model-dependent (constant hazard). Proves that expected turnover is a strictly increasing function of elapsed time, that it inverts exactly to recover D when μ is known, and, as Darwin's 'imperfect' qualification and darwin1859-ch10-02 require, that the same elapsed time gives more turnover in a group with higher hazard, so the clock is only valid within a group of constant rate. It does not prove that extinction is Poisson, that rates are constant through time (pulsed turnover and mass extinctions violate this), or that the clock is 'fair' in practice: the truth score for this claim is low (0.34) because rates vary, which the theorem on hazard explicitly concedes rather than refutes. Expected values only; variance of the clock is not treated.

### `darwin1859-ch03-01` — Overproduction makes a struggle for existence inevitable

- Class A. Rank 47 (score 1.64); data test —; truth 0.95; assessors 0.69.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.geometricPopulation`, theorems `Struggle.geometricPopulation_exceeds_bound`, `Struggle.surplus_tendsto_atTop`, `Struggle.supportableFraction_tendsto_zero`, `Struggle.realisedPopulation_eq`, `Struggle.survivalProduct_le`, `Struggle.survivalProduct_tendsto_zero`, `Struggle.not_all_survive`.
- Statement: $N_t = N_0 r^t,\ r > 1:\ \forall K\ \exists t\ N_t > K;\quad \sup_t N_0 r^t \prod_{i<t} s_i \le K \Rightarrow \prod_{i<t} s_i \le \frac{K}{N_0 r^t} \to 0$
- Assumptions: Discrete non-overlapping generations; unchecked numbers multiply by a constant r > 1 each generation from N₀ > 0 founders (Malthusian geometric increase); the area supports at most K individuals, so the realised population N₀ rᵗ ∏ sᵢ never exceeds K, where sᵢ ∈ [0,1] is the fraction of generation i's offspring that survive to breed.
- Scope: Proves that geometric increase exceeds any bound, that the surplus grows without limit, and that in a bounded population the cumulative survival fraction is at most K/(N₀ rᵗ) and tends to zero, so not every generation can survive in full. 'Struggle for existence' is rendered only as inevitable mortality; competition, its forms (with conspecifics, other species, physical conditions) and its intensity are not represented. Whether any species has a constant r > 1 under unchecked conditions is empirical; Darwin's elephant calculation is not reproduced.

### `darwin1859-ch13-01` — Descent with divergence and extinction produces groups subordinate to groups

- Class A. Rank 52 (score 1.63); data test —; truth 0.95; assessors 0.67.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Tree.lean`, declaration `DarwinLaws.Tree.TreeLike`, theorems `Tree.clade_laminar`, `Tree.clades_containing_chain`, `Tree.treeLike_of_laminar`.
- Statement: $\text{TreeLike}:\ u \le w \wedge v \le w \Rightarrow u \le v \vee v \le u;\quad C(v) = \{w : v \le w\};\quad \text{TreeLike} \iff \forall u v,\ C(u) \cap C(v) = \varnothing \vee C(u) \subseteq C(v) \vee C(v) \subseteq C(u)$
- Assumptions: Descent is a partial order on forms (u ≤ w means u is an ancestor of w or w itself) in which the ancestors of any form are totally ordered: each form has a single line of ancestry, no hybrid origin between distinct lineages. Groups are clades, the set of all descendants of a founder.
- Scope: Proves that tree-like descent makes every pair of clades disjoint or nested (groups subordinate to groups), that the clades containing a form are a chain, and conversely that laminarity forces tree-likeness. This is the mathematical core of Darwin's explanation and is not model-dependent beyond the tree assumption. What it does not cover: 'divergence' and 'extinction' play no role (nesting holds with or without them; Darwin invokes them to explain the gaps between groups, which are not formalized), classifications are not proved to be clades (that naturalists' groups coincide with clades is the empirical claim of ch13-02), and reticulate descent (hybridisation, horizontal transfer) violates the hypothesis.

### `darwin1859-ch10-09` — Rarity precedes extinction

- Class B; model: integer count falling by at most one per period (gradual decline). Rank 55 (score 1.62); data test —; truth 0.88; assessors 0.74.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Succession.lean`, declaration `DarwinLaws.Succession.UnitStepsDown`, theorems `Succession.exists_eq_of_unitStepsDown`, `Succession.rarity_precedes_extinction`.
- Statement: $\forall t,\ N_t \le N_{t+1} + 1;\ N_a \ge 1;\ N_{a+d} = 0 \Rightarrow \exists t \in [a, a+d],\ N_t = 1$
- Assumptions: The number of individuals of a species (or of species in a group) per period is a natural-number sequence that never falls by more than one per period; the species is present (N ≥ 1) at some period and extinct (N = 0) at a later one.
- Scope: A discrete intermediate-value argument: under a decline of at most one per period the count must equal 1 (the extreme of rarity) at some period before extinction. Model-dependent in the strongest sense: the hypothesis (no sudden wipe-out) is itself a gradualist premise, and it is exactly what catastrophic extinctions violate, so the theorem cannot distinguish Darwin's view from Cuvier's; it only shows that gradual decline logically entails prior rarity. 'Rare' is rendered as a single survivor, not as Darwin's 'rare' relative to other species; the step size 1 is a normalisation, and any bounded step size with a suitably coarser notion of rarity gives the same result. Darwin's evidence (Tertiary shells, human exterminations) is empirical.

### `darwin1859-ch10-13` — The more ancient a form, the more it differs from living forms

- Class B; model: range-through faunas; 'difference' = fewer shared lineages with the living fauna. Rank 75 (score 1.54); data test —; truth 0.84; assessors 0.70.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Succession.lean`, declaration `DarwinLaws.Succession.shared`, theorems `Succession.shared_antitone_left`, `Succession.olderFauna_shares_fewer_with_living`.
- Statement: $i \le j \le \text{now} \Rightarrow |F_i \cap F_{\text{now}}| \le |F_j \cap F_{\text{now}}|,\quad F_t = \{L : \text{first}_L \le t \le \text{last}_L\}$
- Assumptions: Each lineage has a single stratigraphic range (darwin1859-ch10-04, no reappearance); the fauna of a stage is the set of lineages whose range covers it; 'difference from living forms' is measured by the number of lineages a fauna shares with the living fauna (lower shared count = greater difference).
- Scope: Proves that an older fauna shares no more lineages with the living fauna than a younger one does (weak inequality). This is a combinatorial consequence of interval ranges and is faithful only if 'differs more' means 'shares fewer lineages'; Darwin's claim is about degree of morphological difference of individual fossil forms, which range-through counting does not measure. The inequality is not strict (two stages can share the same lineages with the present), and the 'as a general rule' is empirical. Darwin's own caveats (living fossils, long-persisting forms) are compatible with the weak inequality.

### `darwin1859-intro-02` — Overproduction plus slight profitable variation leads to natural selection

- Class B; model: geometric increase in a bounded world + constant-fitness haploid selection. Rank 76 (score 1.54); data test —; truth 0.94; assessors 0.61.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.selectedFrequency`, theorems `Struggle.not_all_survive`, `Struggle.survivalProduct_tendsto_zero`, `Struggle.selectedFrequency_gt`, `Struggle.selectedTrajectory_tendsto_one`.
- Statement: $N_0 r^t \to \infty\ (r > 1),\ \sup_t N_t \le K \Rightarrow \prod_{i<t} s_i \to 0;\quad w_B < w_A \Rightarrow p' = \frac{p w_A}{p w_A + (1-p) w_B} > p$
- Assumptions: Overproduction: each generation multiplies numbers by a constant r > 1 and the realised population never exceeds a carrying bound K, with per-generation survival fractions s_t ∈ [0,1]. Selection: a discrete-time, asexual (haploid) population of two types with constant fitnesses w_A > w_B > 0 and initial variant frequency 0 < p₀ < 1.
- Scope: Two separate results are joined here: (1) under geometric increase in a bounded world the cumulative survival fraction tends to zero, so not every generation can survive in full (the struggle); (2) under a constant fitness advantage the favoured variant increases every generation and its frequency tends to one. Lean proves neither that real fecundity is geometric nor that a 'slight profitable variation' corresponds to a constant fitness difference; it also does not connect the two halves (the struggle does not by itself produce the fitness difference). The inference that selection follows is model-dependent: constant-fitness haploid selection with no drift, mutation, frequency dependence or environmental change.

### `darwin1859-ch01-16` — Keeping large numbers of individuals favours successful selection

- Class B; model: same Bernoulli model as ch04-14. Rank 79 (score 1.54); data test —; truth 0.95; assessors 0.59.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.probAnyFavourable`, theorems `Struggle.probAnyFavourable_strictMono`, `Struggle.probAnyFavourable_tendsto_one`.
- Statement: $P(\text{some favourable variation among } N) = 1 - (1-p)^N,\ \text{strictly increasing in } N,\ \to 1$
- Assumptions: Each of N individuals independently presents a useful variation with the same probability p, 0 < p < 1.
- Scope: Proves that the chance of at least one useful variation rises strictly with the number of individuals kept and tends to certainty. Same mathematics as darwin1859-ch04-14, applied to breeders' stock. Independence and a common p are idealisations; the claim's practical conclusion (that large stocks are 'of the highest importance' to breeders, and the breeder's ability to recognise and preserve the variation) is not modelled.

### `darwin1859-ch04-01` — Natural selection preserves favourable and destroys injurious variations

- Class B; model: deterministic constant-fitness haploid selection (infinite population, no drift/mutation). Rank 80 (score 1.54); data test —; truth 0.93; assessors 0.61.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.selectedFrequency`, theorems `Struggle.selectedFrequency_gt`, `Struggle.selectedFrequency_lt`, `Struggle.selectedTrajectory_succ`, `Struggle.selectedTrajectory_tendsto_one`.
- Statement: $p' = \frac{p w_A}{p w_A + (1-p) w_B};\ w_A > w_B \Rightarrow p' > p;\ w_A < w_B \Rightarrow p' < p;\quad p_t = \frac{p_0 w_A^t}{p_0 w_A^t + (1-p_0) w_B^t} \to 1\ (w_A > w_B)$
- Assumptions: Discrete-time haploid (asexual) selection between a variant with constant fitness w_A and the rest of the population with constant fitness w_B > 0; infinite population (deterministic frequencies), no mutation, no drift, no frequency or density dependence; initial frequency 0 < p₀ < 1.
- Scope: Proves that any fitness advantage, however slight, raises the variant's frequency in one generation, any disadvantage lowers it, and that under a constant advantage the frequency tends to one so the less favoured type is eliminated. Model-dependent: with finite populations a slight advantage is often lost to drift (the 'however slight' part fails for s ≲ 1/N), with diploid inheritance recessive variants behave differently, and fitnesses in nature are not constant. The claim's causal clause (that this follows from overproduction) is not derived; the fitness difference is assumed. 'Natural selection' is here a name for the recursion, not an empirical process.

### `darwin1859-ch04-14` — Large populations favour natural selection by supplying more variations

- Class B; model: independent Bernoulli appearance of a favourable variation with common probability p. Rank 83 (score 1.53); data test —; truth 0.93; assessors 0.60.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.probAnyFavourable`, theorems `Struggle.probAnyFavourable_strictMono`, `Struggle.probAnyFavourable_tendsto_one`.
- Statement: $P_N = 1 - (1-p)^N;\ m < n \Rightarrow P_m < P_n;\ P_N \to 1\ (N \to \infty)$
- Assumptions: Each of N individuals independently presents a profitable variation in a given period with the same probability p, 0 < p < 1.
- Scope: Proves that the chance that at least one profitable variation arises in a period rises strictly with population size and tends to one. This is the supply side only; that selection then acts more effectively in large populations (the fixation side, where Kimura's 2s approximation and the drift barrier enter) is not proved. The compensating clause in Darwin's statement, that each individual in a large population is less variable, is not modelled. Independent Bernoulli trials is an idealisation.

### `darwin1859-ch03-03` — Average abundance depends only indirectly on fecundity

- Class B; model: stationary population with constant fecundity r and survival s. Rank 89 (score 1.5); data test —; truth 0.83; assessors 0.66.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.stationary_survival_eq`, theorems `Struggle.stationary_survival_eq`.
- Statement: $r s N = N,\ N \ne 0 \Rightarrow s = 1/r$
- Assumptions: A stationary population: N individuals each produce r offspring of which a fraction s survive to breed, and the resulting number r s N equals N; r, N ≠ 0.
- Scope: Proves only the stationarity identity s = 1/r: in a population of constant average size the survival fraction is the reciprocal of fecundity, so fecundity is exactly compensated by destruction and does not by itself set N. This is a one-line algebraic fact. The claim's substance, that average numbers are set by the checks (destruction, especially early in life) and only indirectly by egg or seed number, is a statement about what determines N, which the identity does not determine; it only shows N is not fixed by r alone. Not an independent theorem of population dynamics.

### `darwin1859-ch13-06` — Varieties form nested groups for the same reason species do

- Class A. Rank 90 (score 1.5); data test —; truth 0.91; assessors 0.59.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Tree.lean`, declaration `DarwinLaws.Tree.TreeLike`, theorems `Tree.clade_laminar`, `Tree.clades_containing_chain`.
- Statement: $\text{TreeLike}(\alpha) \Rightarrow \forall u v,\ C(u) \cap C(v) = \varnothing \vee C(u) \subseteq C(v) \vee C(v) \subseteq C(u),\ \text{for any type } \alpha \text{ of forms}$
- Assumptions: The same as darwin1859-ch13-01 with the forms taken to be varieties and sub-varieties under a species: descent is a partial order with a single line of ancestry for each form.
- Scope: The only mathematical content of 'for the same reason' is that the nesting theorem is stated for an arbitrary partially ordered type of forms and so applies to varieties exactly as to species; no separate proof is needed and none is given. It does not prove that domestic or natural varieties actually fall into nested groups (Darwin's observation), nor that their descent is tree-like: domestic breeds are often of hybrid origin, which breaks the hypothesis, and 'various degrees of modification' is not represented. Counts as a theorem only in this derivative sense.

### `darwin1859-ch03-02` — Geometrical increase explains rapid spread of naturalised species

- Class B; model: geometric growth with multiplier r·s; lowered mortality s' > s. Rank 92 (score 1.49); data test —; truth 0.84; assessors 0.65.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean`, declaration `DarwinLaws.Struggle.growthMultiplier`, theorems `Struggle.growthMultiplier_lt_of_survival_lt`, `Struggle.geometricPopulation_reaches_in_log_time`.
- Statement: $\lambda = r s;\ s < s' \Rightarrow r s < r s';\quad \lambda > 1,\ t \ge \frac{\log(M/N_0)}{\log \lambda} \Rightarrow N_0 \lambda^t \ge M$
- Assumptions: Realised per-generation multiplier λ = r·s with fixed fecundity r > 0 and survival fraction s; in the new country survival is higher (s' > s) because enemies are fewer; growth is geometric with multiplier λ > 1 and target size M ≥ N₀ > 0.
- Scope: Proves that at fixed fecundity higher survival gives a strictly higher multiplier, and that a geometrically growing population reaches any size M within log(M/N₀)/log λ generations ('extraordinarily rapid' read as logarithmic time). It does not prove that naturalised species spread because of lowered mortality rather than raised fertility: the alternative (a rise in r) is not shown to be absent, only that lowered destruction suffices. The model has no spatial spread, density dependence or lag phase.

### `darwin1859-ch04-24` — Extinct species are often intermediate between living groups

- Class B; model: nonnegative path-additive (tree) metric on character space. Rank 99 (score 1.48); data test —; truth 0.82; assessors 0.66.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Tree.lean`, declaration `DarwinLaws.Tree.PathAdditive`, theorems `Tree.ancestor_between`.
- Statement: $d(x,y) = d(x,a) + d(a,y),\ a = \mathrm{lca}(x,y),\ d \ge 0 \Rightarrow d(x,a) \le d(x,y) \wedge d(a,y) \le d(x,y)$
- Assumptions: Character distance between forms is a nonnegative path-additive (tree) metric: the distance between two forms equals the sum of their distances to their last common ancestor. 'Intermediate in character' is read as metric betweenness of that ancestor.
- Scope: Model-dependent (tree metric) and mathematically slight: given additivity and nonnegativity the conclusion is immediate. Proves that the common ancestor of two living groups is no farther from either than they are from each other. It does not prove that extinct species in general are such ancestors (most are side branches), that character change is additive along lineages (convergence and reversal break this), or the 'often' in Darwin's wording, which is the empirical content and is left to data.

### `darwin1859-ch04-20` — Divergence of character maximises the life an area supports

- Class B; model: additive resource partition: life supported = Σ K_i over resources used. Rank 107 (score 1.46); data test —; truth 0.79; assessors 0.67.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Islands.lean`, declaration `DarwinLaws.Islands.supportedLife`, theorems `Islands.supportedLife_mono`, `Islands.supportedLife_lt_of_unused`, `Islands.supportedLife_increases_with_new_niche`.
- Statement: $L(U) = \sum_{i \in U} K_i,\ K_i > 0;\quad U \subsetneq I \Rightarrow L(U) < L(I);\quad A \subseteq B \Rightarrow L(A) \le L(B)$
- Assumptions: The area's resources ('places in the economy of nature') form a finite set, each resource i alone supporting K_i > 0 units of life; the life supported by an assemblage is the sum of K_i over the resources its species' niches cover (additive partition, no interaction between resources, no cost of specialisation).
- Scope: Model-dependent (additive resource partition). Proves that an assemblage leaving some resource unused supports strictly less life than one covering every resource, and that adding a species whose niche includes an unused resource strictly increases the total. 'Diversification of structure' is identified with covering more resource classes; the theorem does not show that diversified assemblages cover more resources than uniform ones, nor that selection produces divergence (the mechanism half of Darwin's principle of divergence). Darwin's supporting evidence (Lamb and grass-plot experiments, naturalised floras) is empirical.

### `darwin1859-ch04-18` — Favoured forms make less favoured forms rare, and rarity precedes extinction

- Class B; model: constant-fitness selection (first half) + unit-step decline in numbers (second half). Rank 131 (score 1.36); data test —; truth 0.66; assessors 0.70.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Succession.lean`, declaration `DarwinLaws.Succession.UnitStepsDown`, theorems `Struggle.selectedFrequency_lt`, `Struggle.selectedTrajectory_tendsto_one`, `Succession.rarity_precedes_extinction`.
- Statement: $w_A < w_B \Rightarrow p' < p,\ p_t \to 0\ \text{(less favoured)};\quad N_t \le N_{t+1} + 1,\ N_a \ge 1,\ N_{a+d} = 0 \Rightarrow \exists t \in [a, a+d],\ N_t = 1$
- Assumptions: First half: constant-fitness haploid selection as in darwin1859-ch04-01, the less favoured form having fitness w_A < w_B, so its frequency falls every generation and the favoured form's tends to one. Second half: the count of individuals of the less favoured form falls by at most one per period (no instantaneous wipe-out).
- Scope: Two halves from two models. Selection: the less favoured variant's frequency decreases monotonically and tends to zero, which is read as 'becomes rare'; this is frequency, not number, and the full-stocking premise ('every area is already fully stocked', which is what turns a frequency change into a decline in numbers) is not modelled. Rarity before extinction: given a decline of at most one individual per period, the count must pass through 1. The unit-step hypothesis does the work and excludes catastrophic extinction by assumption; see darwin1859-ch10-09. Neither half is an empirical result.

### `darwin1859-ch03-11` — Struggle is most severe between members of the same species

- Class B; model: MacArthur–Levins niche overlap (cosine similarity of utilisation vectors). Rank 153 (score 1.29); data test —; truth 0.73; assessors 0.56.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Islands.lean`, declaration `DarwinLaws.Islands.nicheOverlap`, theorems `Islands.nicheOverlap_self`, `Islands.nicheOverlap_le_self`.
- Statement: $\alpha(u,v) = \frac{\sum_i u_i v_i}{\sqrt{\sum_i u_i^2}\sqrt{\sum_i v_i^2}};\quad \alpha(u,u) = 1,\ \alpha(u,v) \le \alpha(u,u)$
- Assumptions: Competition intensity between two forms is their MacArthur–Levins competition coefficient, the cosine similarity of their resource-utilisation vectors over a finite set of resource classes; both vectors are nonzero; members of one species share a single utilisation vector.
- Scope: Model-dependent (MacArthur–Levins niche overlap). Proves by Cauchy–Schwarz that no other form's overlap with a given form exceeds its self-overlap, which is 1. This is close to a tautology of the chosen measure: any normalised inner-product similarity is maximised on the diagonal, so the theorem says nothing about real competition unless one already accepts that utilisation similarity is what makes the struggle severe. It does not prove the 'almost always' in Darwin's wording, does not treat intraspecific variation in resource use (which would make α(u,u) a within-species average less than 1), and does not model non-resource competition (mates, predators, disease). The ≤ is not strict: a different form with a proportional utilisation vector competes just as hard.

### `darwin1859-ch02-15` — Larger genera tend to grow larger and dominant forms more dominant

- Class B; model: Yule pure-birth process, expectations only. Rank 206 (score 1.03); data test —; truth 0.41; assessors 0.62.
- Lean: `claim-sources/darwin-origin/lean/DarwinLaws/Tree.lean`, declaration `DarwinLaws.Tree.expectedGenusSize`, theorems `Tree.expectedGain_proportional`, `Tree.expectedGenusSize_ratio`, `Tree.expectedGenusSize_gap_strictMono`.
- Statement: $\mathbb{E}[n(t)] = n_0 e^{\lambda t};\ \mathbb{E}[n(t)] - n_0 = n_0(e^{\lambda t} - 1);\ \frac{\mathbb{E}[n_1(t)]}{\mathbb{E}[n_2(t)]} = \frac{n_1}{n_2};\quad n_1 > n_2,\ \lambda > 0 \Rightarrow (n_1 - n_2)e^{\lambda t} \text{ strictly increasing in } t$
- Assumptions: Yule's pure-birth process (1925, built for this very claim): every species in every genus gives rise to new species at the same constant rate λ > 0, with no extinction; only expected sizes n₀ e^{λt} are treated, not the stochastic process.
- Scope: Model-dependent (Yule pure birth, expectations only). Proves that the expected gain of a genus is proportional to its size, that two genera with the same rate keep a constant ratio of expected sizes, and that the absolute gap between a larger and a smaller genus grows strictly with time. It does not prove 'dominant forms become more dominant' in any sense beyond this absolute gap: the ratio is constant, so no relative advantage accrues, and Darwin's mechanism (dominant species vary more and their varieties become species) is replaced by a uniform rate that gives large genera no per-species edge. With extinction or rate heterogeneity (ch02-09) large genera can shrink. The data test for this claim is pending; the truth score is low (0.4), which is consistent with the theorem proving less than the claim says.

## Candidates for future formalization (A/B, not yet in Lean)

Ordered by how clean the statement is and how much of Darwin's wording it captures.

### `darwin1859-ch12-18` — Closer relatives tend to be closer together in time and space

- Class B; model: Brownian motion of geographic position along a phylogeny (dispersal variance σ² per unit time). Rank 15 (score 3.07); data test supports (0.75); truth 0.80; assessors 0.77.
- Proposed statement: $\mathbb{E}\,\|X_i - X_j\|^2 = 2\sigma^2\, \tau_{ij},\quad \tau_{ij} = \text{time since the last common ancestor of } i, j;\ \tau_{ij} < \tau_{ik} \Rightarrow \mathbb{E}\|X_i - X_j\|^2 < \mathbb{E}\|X_i - X_k\|^2$
- Assumptions: Lineages disperse as independent Brownian motions after splitting, with the same σ² and no barriers; 'nearer in time' is the divergence time itself. Long-distance dispersal and barriers break the model.
- Note: Not yet formalized. The expected squared geographic distance between two lineages is 2σ² times their time since divergence, so it is strictly increasing in patristic distance; time proximity follows from the tree by definition. The cleanest unformalized candidate.

### `darwin1859-ch08-13` — Hybrids vary little in the first generation but greatly in later generations

- Class B; model: Mendelian inheritance at unlinked diallelic loci from two inbred (homozygous) parental lines. Rank 42 (score 1.78); data test mixed (0.5); truth 0.53; assessors 0.75.
- Proposed statement: $\mathrm{Var}_G(F_1) = 0;\quad \mathrm{Var}_G(F_2) = \sum_{\ell} \left(\tfrac{1}{2} a_\ell^2 + \tfrac{1}{4} d_\ell^2\right) > 0 \text{ whenever some } a_\ell \ne 0 \text{ or } d_\ell \ne 0$
- Assumptions: Parents are homozygous at every differing locus; loci are unlinked and additive across loci with within-locus effects a (additive) and d (dominance); no environmental variance in the genetic comparison; the F2 is produced by random mating or selfing of F1.
- Note: Not yet formalized. The F1 between two homozygous lines is genetically uniform (zero genetic variance), while the F2 segregates with genetic variance Σ(a²/2 + d²/4) per locus > 0; this is exactly 'little variation in the first generation, great in later ones'. Darwin's explanation (disturbed reproductive system) is wrong but the pattern is a theorem of Mendelism. Strong B candidate.

### `darwin1859-ch11-02` — Barriers to migration correspond closely to differences between regional biotas

- Class B; model: Wright's island model of two demes exchanging migrants at rate m across the barrier, with drift for time t. Rank 10 (score 3.29); data test supports (0.8); truth 0.91; assessors 0.79.
- Proposed statement: $F_{ST}^* = \frac{1}{1 + 4Nm},\ \partial F_{ST}^*/\partial m < 0;\quad F_{ST}(t) = F_{ST}^*\left(1 - e^{-(2m + 1/(2N))t}\right) \text{ strictly increasing in } t$
- Assumptions: Two demes of effective size N, symmetric migration m per generation, neutral alleles, no mutation; 'difference between inhabitants' is read as genetic differentiation, not species-level turnover.
- Note: Not yet formalized. Differentiation F_ST = 1/(1 + 4Nm) at equilibrium is strictly decreasing in m (impassability), and before equilibrium F_ST(t) increases with t (long-standing). A promising B candidate because both of Darwin's clauses map to monotonicities.

### `darwin1859-ch08-02` — Close interbreeding lowers fertility while occasional crossing raises it

- Class B; model: multiplicative multilocus model with partially recessive deleterious alleles; fitness as a function of the inbreeding coefficient F. Rank 22 (score 2.71); data test supports (0.65); truth 0.67; assessors 0.75.
- Proposed statement: $\ln \bar W(F) = \ln \bar W(0) - B F,\ B > 0;\quad F_{\text{selfing}, t} = 1 - 2^{-t} \uparrow 1;\quad F_{\text{outcross}} = 0$
- Assumptions: Deleterious alleles at many unlinked loci with dominance h < 1/2, multiplicative fitness, random mating in the base population; 'fertility' is read as fitness. Darwin's statement is quantitative-genetic in content but model-dependent in form.
- Note: Not yet formalized. Mean log fitness falls linearly in F (ln W(F) = ln W(0) − B·F with inbreeding load B > 0), and an outcross resets F to 0, so crossing raises fitness. Also a candidate for Mendelian formalization alongside ch08-13.

### `darwin1859-ch10-06` — Groups rise gradually in species number to a maximum, then gradually decline

- Class B; model: constant-rate birth–death process conditioned on eventual extinction. Rank 37 (score 2.1); data test mixed (0.7); truth 0.60; assessors 0.80. Currently *not-formalized* in `claim-sources/darwin-origin/lean/reports/Succession.json`.
- Proposed statement: $\mathbb{E}[n(t) \mid \text{extinct eventually}] \text{ rises from } 1 \text{ and tends to } 0;\ \text{unconditionally } \mathbb{E}[n(t)] = e^{(\lambda-\mu)t}$
- Assumptions: Kendall's linear birth–death process with λ, μ > 0; the group is the lineage count; 'gradually' is the continuous-time sample-path property that n changes by ±1.
- Note: Not yet formalized; the existing Lean lemma gradual_rise_and_fall assumes the shape rather than deriving it. The expected diversity of a clade conditioned on extinction rises from 1 and falls back to 0, giving a unimodal expected trajectory.

### `darwin1859-ch02-09` — Small genera often grow large while large genera peak, decline and vanish

- Class B; model: linear birth–death process per genus (speciation λ, extinction μ). Rank 56 (score 1.61); data test —; truth 0.86; assessors 0.75. Currently *not-formalized* in `claim-sources/darwin-origin/lean/reports/Tree.json`.
- Proposed statement: $\text{Linear birth–death from } n_0 = 1:\ \mu \ge \lambda \Rightarrow P(\text{extinction}) = 1;\ \mu < \lambda \Rightarrow P(\text{extinction}) = \mu/\lambda;\ \forall M\ P(\sup_t n(t) \ge M) \ge (\lambda/(\lambda+\mu))^{M-1} > 0$
- Assumptions: Each species speciates at rate λ and goes extinct at rate μ independently (Kendall 1948); the genus is the lineage count; 'often' is read as positive probability.
- Note: Not yet formalized. With μ > λ every genus eventually goes extinct, and with λ > 0 any genus has positive probability of reaching any size first; this is the only sense in which 'often' can be derived.

### `darwin1859-ch09-03` — Denudation of the Weald implies roughly 300 million years since the late Chalk

- Class A. Rank 28 (score 2.43); data test refutes (0.98); truth 0.02; assessors 0.94.
- Proposed statement: $T = \frac{D}{v}\cdot\frac{h}{h_0};\quad D = 22\,\text{mi} = 1{,}393{,}920\,\text{in},\ v = 1\,\text{in}/\text{century for a cliff of } h_0 = 500\,\text{ft},\ h = 1100\,\text{ft} \Rightarrow T = 1{,}393{,}920 \times 100 \times \tfrac{1100}{500} = 306{,}662{,}400\ \text{yr}$
- Assumptions: Retreat rate of one inch per century for a 500-ft cliff, scaled linearly with cliff height (Darwin's 'at this rate, on the above data'); the Weald is 22 miles across with formations averaging 1,100 ft thick (Ramsay). The product reproduces Darwin's figure exactly (checked against inputs/pg1228.txt lines 8671–8699); the data test refutes the rate, not the arithmetic.
- Note: Not yet formalized. Pure arithmetic: time = distance ÷ rate. Darwin's figure of 306,662,400 years follows exactly from his stated denudation and rate; the data test refutes the premise (rate), not the arithmetic. A faithful Lean statement would prove the number from the inputs and nothing more.

### `darwin1859-ch04-13` — Trees more often have separate sexes than other plants

- Class B; model: random pollen movement among the flowers of an individual (geitonogamy) versus between individuals. Rank 18 (score 2.99); data test supports (0.7); truth 0.79; assessors 0.81.
- Proposed statement: $s(F) = \frac{F - 1}{P F - 1} \text{ strictly increasing in } F \text{ for } P > 1;\quad s \to 1/P \text{ as } F \to \infty$
- Assumptions: Pollen moves uniformly at random among all other flowers in the population; plants have equal flower numbers; the selective premise that self-pollination is harmful is taken from ch08-02.
- Note: Not yet formalized. For a hermaphrodite plant bearing F flowers among a population of P plants with equal flower number, the fraction of self pollen received under uniform pollen movement is (F − 1)/(PF − 1), increasing in F; dioecy sets it to zero. Explains Darwin's reasoning, not the comparative frequency.

### `darwin1859-ch10-04` — A species that has gone extinct never reappears

- Class B; model: character state as a point in a continuous (or very large discrete) space evolving by a non-atomic process. Rank 49 (score 1.63); data test —; truth 0.93; assessors 0.70. Currently *not-formalized* in `claim-sources/darwin-origin/lean/reports/Succession.json`.
- Proposed statement: $X_t \in \mathbb{R}^k \text{ with } X_t \text{ having a density for } t > 0 \Rightarrow P(X_t = x_0) = 0 \text{ for every fixed } x_0$
- Assumptions: The identical form means identical character vector; the evolutionary process has a non-atomic marginal law (e.g. Brownian motion on characters). Says nothing about near-identical forms (iterative evolution).
- Note: Not yet formalized. Dollo's law as a measure-zero statement: a lineage with a continuous character distribution revisits an exact earlier state with probability zero. Used in the Lean modules as the range-through hypothesis instead.

### `darwin1859-ch12-11` — Sea depth between island and mainland predicts their mammalian affinity

- Class B; model: isolation time increasing in channel depth (sea-level history) and divergence increasing in isolation time. Rank 33 (score 2.28); data test mixed (0.6); truth 0.90; assessors 0.78.
- Proposed statement: $t_{\text{iso}} = g(\text{depth}),\ g \uparrow;\quad d = h(t_{\text{iso}}),\ h \uparrow \Rightarrow d \text{ increasing in depth}$
- Assumptions: Glacial low-stands expose shallow channels, so isolation time is monotone in depth; divergence (e.g. expected pairwise differences 2μt) is monotone in time.
- Note: Not yet formalized and weak: both monotonicities are premises, so the theorem is a composition of two monotone functions. Would only be worth stating together with a neutral-divergence model.

### `darwin1859-ch04-22` — Naturalised floras add proportionally more new genera than new species

- Class B; model: random sampling of n colonist species from a species pool partitioned into genera. Rank 24 (score 2.51); data test supports (0.55); truth 0.57; assessors 0.84.
- Proposed statement: $\text{Species in genera of size 1 in the pool contribute a new genus per species; for pool genus sizes } s_g,\ \mathbb{E}[\#\text{new genera}] = \sum_g \left(1 - \binom{S - s_g}{n}/\binom{S}{n}\right)$
- Assumptions: Colonists are a uniform random sample of the pool and belong to no native genus; the comparison to native ratios needs the natives' genus-size distribution as a further assumption.
- Note: Not yet formalized, and weak: the natural statement compares genera gained per native genus with species gained per native species, which depends on the genus-size distribution of pool and natives. Only a conditional inequality can be derived; the data test gives supports at 0.55.

## Class C: not mathematical propositions

- `darwin1859-ch06-10` Selection can independently produce similar organs in distantly related beings: Historical statement that convergence has occurred (electric organs); no derivation from premises.
- `darwin1859-ch11-03` Species of the same continent or sea are related despite differing stations: Empirical biogeographic pattern (regional affinity across habitats).
- `darwin1859-ch14-12` Succession by generation has never been broken by a world-wide cataclysm: Historical negative existential (no world-wide cataclysm); its logical form (unbroken descent ⇒ no total extinction) is a restatement.
- `darwin1859-ch11-08` Continents and oceanic islands were not united by land in the recent period: Geological-historical inference about land bridges.
- `darwin1859-ch05-06` Cave animals are related to surface fauna of their own continent: Prediction about affinities of cave faunas; follows from local colonisation only tautologically.
- `darwin1859-ch01-10` All domestic pigeon breeds descend from the rock-pigeon: Historical inference about pigeon ancestry.
- `darwin1859-ch10-18` Each region's fossils are succeeded by allied living forms in the same region: Law of succession of types; empirical/historical pattern.
- `darwin1859-ch12-01` Fresh-water species range widely and allied species occur worldwide: Empirical statement about ranges of fresh-water taxa.
- `darwin1859-ch11-01` Physical conditions do not explain the similarity or dissimilarity of regional biotas: Negative empirical statement (climate does not predict biotic similarity).
- `darwin1859-ch10-02` Species of different genera and classes change at different rates: Empirical statement that rates differ between groups; only its consequence (more turnover at higher hazard) is provable, and is proved under ch14-07. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Succession.json`.)
- `darwin1859-ch11-14` Plants of high mountains and temperate lowlands worldwide are identical or closely related: Empirical floristic pattern.
- `darwin1859-ch14-03` All living things share chemical composition, cell structure and laws of growth: Empirical statement of shared biochemistry and cell structure.
- `darwin1859-ch12-02` Fresh-water fish species are not shared between distant continents: Empirical (and refuted) distributional statement.
- `darwin1859-ch12-08` Frogs, toads and newts are absent from oceanic islands: Empirical (and refuted) distributional statement with a dispersal-barrier explanation.
- `darwin1859-ch11-16` Northern species naturalise far more often in the south than the reverse: Empirical asymmetry in naturalisation (refuted).
- `darwin1859-ch07-04` Instincts vary within species in a state of nature: Empirical statement that instincts vary.
- `darwin1859-ch12-09` No native terrestrial mammals on islands more than 300 miles from a continent: Empirical (refuted) distributional statement with a distance threshold.
- `darwin1859-ch13-08` Distinct lineages adapted to similar conditions converge in external form: Historical statement about convergence and its taxonomic value.
- `darwin1859-ch14-01` Descent with modification embraces all members of each class: Historical inference from chains of affinities.
- `darwin1859-ch11-13` The Glacial period was simultaneous across the whole world: Palaeoclimatic claim about synchrony.
- `darwin1859-ch12-10` Bats occur on almost every island, often as endemic species: Empirical distributional statement about bats.
- `darwin1859-ch09-14` Oceans and continents have kept roughly their present positions since the Silurian: Geological-historical claim (refuted).
- `darwin1859-ch11-06` Many genera are confined to one region and the most natural genera are local: Empirical statement about endemism of taxa.
- `darwin1859-ch01-09` Domestic dogs descend from several wild species: Historical inference (refuted).
- `darwin1859-ch10-12` Marine forms of life change almost simultaneously throughout the world: Empirical statement about synchrony of marine faunal change.
- `darwin1859-ch14-02` Animals from at most four or five progenitors, plants from as many or fewer: Historical inference about the number of progenitors.
- `darwin1859-ch09-04` Soft-bodied organisms and remains on non-depositing sea floor are not preserved: Taphonomic generalization.
- `darwin1859-ch10-07` Species and groups disappear gradually, place by place, not by global catastrophes: Gradual, place-by-place extinction is the empirical question (mass extinctions exist); it is the hypothesis of the existing lemmas, not a conclusion. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Succession.json`.)
- `darwin1859-ch06-17` Unity of type is explained by unity of descent: Explanatory claim (unity of type by descent); not a proposition with a proof.
- `darwin1859-intro-04` Species are not immutable but descend from other, mostly extinct, species: Historical thesis of descent.
- `darwin1859-ch12-12` Island endemics are related to species of the nearest continent: Empirical biogeographic rule; a dispersal-distance model would assume it.
- `darwin1859-ch14-04` Probably all organisms descend from one primordial form: Historical inference by analogy.
- `darwin1859-ch02-01` Individual differences supply the material for natural selection: Identifies the source of heritable variation; existential statement about populations, not a consequence of premises. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Struggle.json`.)
- `darwin1859-ch13-02` The Natural System expresses propinquity of descent: A claim about what classifications track; showing that resemblance-based groups recover clades is phylogenetic-inference theory under a character model, not a proposition in Darwin's text. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Tree.json`.)
- `darwin1859-ch02-08` Species of larger genera more often present varieties: Tabulation result about the proportion of varying species; a constant per-species rate gives no such effect, and a size-dependent rate assumes it. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Tree.json`.)
- `darwin1859-ch03-12` Congeners compete more severely than species of different genera: Within the niche-overlap model it reduces to 'congeners have more similar utilisation vectors', an empirical premise. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Islands.json`.)
- `darwin1859-ch04-21` The closest-competing neighbours tend to belong to different genera and orders: Taxonomic composition of small plots; no derivation from stated premises without assuming genera map to resources. (recorded as not-formalized in `claim-sources/darwin-origin/lean/reports/Islands.json`.)

## Method notes

- Screening set: the 45 highest composite scores plus the 30 ids named in the four Lean modules
  (23 not already in the top 45), 68 claims in all. Claims outside this set were not classified.
- Validation fields come from `docs/claims.json` as built on its `built` date; re-running
  `node scripts/site/build-claim-graph.mjs` will change the truth scores and the Lean fields
  (the four Darwin reports were added after that build).
- Nothing here changes `claims.json`, `site/` or any nanopub. The Lean sources were not edited.
