# Subagent: Approaches: Claude Opus

- **Parent chat:** [let's find 10-20 geniuinely hard open problems in bio or math that potentially c](../2026-10-31_2218_let-s-find-10-20-geniuinely-hard-open-problems-in-bio-or-mat.md)
- **Started:** 2026-10-31 22:44 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 01:11 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `316f669d-dd76-4053-96c3-323fa38aa37f`

---

### 2026-10-31 22:44 — Turn 1 (User)

> Repository: /Users/jdietz/Documents/GitHub/dev/delphisci (a project that extracts candidate laws of biology as claims, tests them against data, formalizes some in Lean 4, and publishes everything as nanopublications).
> 
> Your task: read /Users/jdietz/Documents/GitHub/dev/delphisci/problems/approaches/INSTRUCTIONS.md and follow it exactly. Read /Users/jdietz/Documents/GitHub/dev/delphisci/problems/problems.json (20 open problems in biology and mathematics). For EVERY one of the 20 problems, propose 2 to 4 concrete approaches by which an agent swarm with the listed tools (Lean 4, large-scale computation, pre-registered data tests, GBIF/PBDB/AnAge organism data, INDRA CoGEx, bioelectric simulation, morphometrics) could attack it. Follow the JSON output format in INSTRUCTIONS.md precisely.
> 
> Your model slug is `claude-opus-5-5` and your provider is `Anthropic`. Write your output to /Users/jdietz/Documents/GitHub/dev/delphisci/problems/approaches/claude-opus-5-5.json and nothing else; do not edit any other file.
> 
> Rules that matter: every DOI or URL you include must be one you have verified resolves (use web fetch to check; if you cannot verify, omit the doi and describe the reference in `note`). No placeholder text, no TODOs, no invented datasets. Be specific and technical: name lemmas, null models, estimators, datasets, sample sizes. Approaches for the same problem must differ in kind, not be rephrasings. Rate difficulty honestly. To understand the repo's standards for tests and Lean, skim /Users/jdietz/Documents/GitHub/dev/delphisci/test-data/claim-tests/README.md and /Users/jdietz/Documents/GitHub/dev/delphisci/claim-sources/thompson-growth-form/lean/INSTRUCTIONS.md (read-only).
> 
> When done, validate the JSON parses (node -e 'JSON.parse(require("fs").readFileSync("problems/approaches/claude-opus-5-5.json","utf8"))' from the repo root), then reply with: the number of approaches written, the number of problems covered (must be 20), and any problems where you could only propose fewer than 2 approaches and why.

**Assistant:**

I'll read the instructions and problem list first.

Let me start by reading through the instructions carefully.

I should skim the two referenced docs briefly and verify DOIs, reusing them from problems.json where possible but still confirming each one—maybe via curl HEAD requests to doi.org to check redirects. Let me also check the existing approaches directory while I'm at it.

I've read the instructions and the 20 problems. Next I'll verify every DOI and URL I plan to cite, checking each against Crossref titles so the right paper is attached to each DOI.

I'm compiling a candidate list of DOIs and URLs to cite as references, drawing from problems.json plus additional sources like Cook 2004, Neary and Woods, and Smith 2020, which I'll need to verify before using.

I'm expanding the list further with more candidates — Neary 2009, Martinez 2006, the Wolfram Rule 30 prize announcement, Jen 1990 on aperiodicity in cellular automata, the Lean Mathlib repo, and several Turing instability papers (Satnoianu et al., Anma et al., Diego et al.) along with Queller's kin selection model — flagging each as needing a verification check before I commit to citing it.

Verifying the CAPD library link and Swinton et al.'s sunflower Fibonacci citizen science study in PNAS/Royal Society Open Science. Then checking Lewontin-related citations: Romiguier et al. 2014 in Nature, Charlesworth 2009 on effective population size in Nature Reviews Genetics, and Kern & Hahn 2018.

Now I'm confirming more sources: Kern & Hahn's neutral theory piece in MBE, plus simulation tools SLiM and stdpopsim. I'm also checking Murphy, Elyashiv, Amster, and Sella's 2022 eLife paper on purifying selection and genetic diversity, and Mackintosh et al.'s 2019 Nature Communications paper on determinants of genetic diversity in butterflies.

I'm also pulling together metabolic scaling references—Li & Durbin's PSMC paper, Glazier's review on body-size scaling laws, Kolokotrones et al. on curvature in metabolic scaling, Savage et al. on quarter-power scaling, and Banavar, Maritan, and Rinaldo on efficient transportation networks.

Now I'm noting key dataset sources like AnAge, PanTHERIA, and VertLife phylogenies, along with Upham's 2019 mammal tree paper, while considering whether phylogenetic GLS methods fit within standard Python tooling conventions. I'm also checking McNab's analysis of factors influencing mammalian BMR scaling and starting to reference Dodds, Rothman, and Weitz's work.

Also checking Chao's rarity estimators and the iNEXT package for diversity extrapolation. For clade trajectories, I'm verifying Alroy's work on Phanerozoic diversification controls and the Gould/Gilinsky/German paper on lineage asymmetry in evolutionary time.

Now verifying Gould Schopf Simberloff's stochastic phylogeny models, Silvestro's PyRate software, Kocsis's divDyn package, and Raup's cladogenesis models, plus checking the PBDB API reference and Liow et al.'s PNAS paper on ecological interactions in macroevolutionary timescales.

I'm also cross-checking Jablonski et al.'s 2003 Science paper, and working through shell morphology references including Raup's classic work, Gerber 2017, Okamoto's heteromorph ammonoid analysis, and Noshita/Asami/Ubukata's gastropod coiling geometry paper, while flagging uncertainty around Stone 1996 and other morphospace citations still needing verification.

I'm trying to recall more sources on ammonoid morphospace work and shell parameter datasets like MolluscaBase, but I'm wary of inventing references I'm not sure exist. Shifting to somite segmentation research, I'm thinking through papers like Lauschke et al. on phase-gradient scaling and Matsuda et al. on species-specific segmentation clock speeds.

Now I'm considering vertebral count datasets, including Ward & Brainerd's work on axial patterning in elongate fishes and FishBase's morphology records that include vertebrae counts, before moving into squamate vertebral data.

For snakes specifically, I'm thinking of Head & Polly's work on snake body form evolution and Hox gene homoplasy, plus Gomez & Pourquié's and Ebisuya & Briscoe's reviews on developmental timing. I'm also working toward formalizing the clock-and-wavefront model mathematically — somite number as elongation duration divided by oscillation period, adjusted for presomitic mesoderm shrinkage dynamics based on Gomez's 2008 model.

Shifting gears, I'm now pulling together references on vascular imaging and analysis — the DRIVE and HRF retinal datasets, Todorov's VesSAP whole-brain vasculature machine learning paper, Kirst's brain vasculature mapping study in Cell, and Huo & Kassab's work on vascular scaling laws.

Kassab 1993 on pig coronary arterial tree morphometry is another candidate to verify. I'm also considering formalizing Murray's law derivation via Lagrangian cost minimization—balancing flow resistance against metabolic cost of vessel volume—which yields r³ ∝ Q and the conservation relation r0³ = r1³+r2³, plus the turbulent-flow variant giving exponent 7/3; this seems tractable to formalize in Lean. I should also look into gene overlap data from Levin 2022 and cross-reference Gene Ontology and Human Phenotype Ontology resources.

Beyond that, I'm compiling citations on gene annotation bias and understudied genes—Gillis & Pavlidis on multifunctional genes skewing guilt-by-association analysis, Haynes, Tomczak & Khatri on annotation bias impeding biomedical research, plus GTEx tissue-specificity data, MGI phenotype records, and Stoeger et al.'s large-scale investigation into why important genes remain understudied.

I'm thinking through independent verification approaches beyond annotation-based evidence: using IMPC mouse knockout phenotypes to compare morphology versus behavioral/learning effects, and applying network-level proximity metrics like Menche et al.'s network separation measure to assess relationships between gene sets within the INDRA causal graph. I'm also starting to note Levin, Martyniuk, Pietak, and Durant's work on bioelectric prepatterning.

Also noting the BETSE repository for bioelectric simulation. My plan has four prongs: curating an image dataset with leave-one-paper-out validation for a decoder, using BETSE to simulate Vmem changes from ion channel perturbations and pre-registering predictions against published anatomy outcomes, running a meta-analysis on whether Vmem perturbation sign/magnitude predicts phenotype dose-response across a coded literature corpus, and computing mutual information between Vmem maps and outcomes.

For GRN memory, I'm drawing on Biswas et al.'s work on transcriptional network memory and pathway-level interventions, pulling from BioModels. I'm designing null model comparisons: a degree-preserving random ODE ensemble with matched Hill kinetics, and edge-swap rewiring of the actual biological models while keeping kinetics fixed, to separate the contribution of topology from kinetics.

I'm also considering an analytical angle, linking memory to multistability and slow manifolds via chemical reaction network theory and deficiency theory, hypothesizing a theorem that UCS memory requires either multistability or slow timescales. I'm noting tools like libroadrunner, tellurium, and CRNToolbox, plus Feinberg's deficiency zero theorem, and planning to add parameter randomization and Erdős–Rényi comparisons. Then I shift toward active inference, starting from Friston's 2015 generative model formulation as a basis for a formal derivation.

I recall the complete class theorem connects to Friston's framework — I could formalize a finite version in Lean showing any deterministic policy minimizes expected free energy under some prior, demonstrating unfalsifiability without added constraints, then explore which independent constraints restore empirical content. Another route would be a pre-registered test using Xenopus tadpole craniofacial remodeling ("Picasso tadpoles") data.

For Kelvin's conjecture, I'm thinking through verification approaches: a computer-assisted proof of local optimality for Weaire-Phelan using Surface Evolver's Hessian with interval arithmetic, and a Lean-formalized isoperimetric lower bound based on per-cell surface area constraints with shared faces counted twice.

I recall Kusner's 1992 result bounding average faces in a minimal foam at ≤13.39. Formalizing the sphere isoperimetric lower bound in Lean would need machinery likely absent from Mathlib, making a full proof hard — maybe a conditional theorem assuming the inequality is more tractable, but that's weaker. I'll rate this approach as difficult and move to considering biological data on scutoid frequency versus curvature as a third angle.

Thinking about relevant datasets, I recall the Gómez-Gálvez et al. work on 3D cellular connectivity in curved epithelia (likely published in Cell Systems 2022) plus Drosophila salivary gland data, and also the Wolny et al. 2020 eLife Arabidopsis ovule dataset from PlantSeg as potential sources to test against.

I'm also considering checking Lewis's law and Aboav-Weaire law statistics, and running vertex-model simulations on curved tubes to compare predicted scutoid frequencies against observations. Separately, for the mutant-morphant angle I'm thinking about ZFIN data downloads, the Ma et al. 2019 Nature paper on genetic compensation via Upf3a, and Ensembl BioMart as a resource for gathering gene annotation data.

For the discrepancy analysis, I'm sketching three approaches: a classifier as a baseline, a pre-registered logistic regression testing El-Brolosy's mechanistic hypothesis (paralog similarity/tissue expression plus PTC-triggered NMD), and a confound audit checking whether morpholino off-target toxicity (p53 activation) better explains the discrepancy than the proposed mechanism, using ZFIN morpholino sequences blasted against the genome. These differ meaningfully in kind, which is good.

For formalizing Cook's Rule 110 construction, I'm weighing a direct Lean formalization approach (defining the ECA, ether periodicity, glider definitions, collision lemmas via bounded computation, and a cyclic tag system simulation) against a verified checker approach where I prove soundness of a tile/collision checker once and then feed it externally generated certificates, since the full direct proof seems like a long shot within a month given how complex Cook's and Neary-Woods' proofs are.

A third distinct option is purely computational: an independent SAT-based or exhaustive-simulation audit of each collision as a falsifier route to find gaps, separate from the Lean formalization work.

Recalling that Cook's glider tables use types A through H, with ether having spatial period 14 and temporal period 7. I'm also considering Mathlib's Turing namespace (TM0/TM1/TM2 and ToPartrec) to connect universality claims to partial recursive functions, though proving universality of cyclic tag systems would require its own chain through 2-tag systems and Minsky machines.

For the (2,3) Turing machine, I'm weighing a decidability-style attack: classifying behavior on eventually periodic tapes using Busy Beaver community deciders like cyclers, translated cyclers, backward reasoning, and closed tape language methods. But this machine has no halt state, which complicates what "universal" even means without a halting convention for output.

I want to verify the 2024 BB(5) Coq proof and the 2025 arXiv paper on the fifth Busy Beaver value, since the formal decider tools involved there seem directly relevant to checking tape patterns here.

Thinking through Smith's construction more carefully, I suspect the non-periodicity in the initial tape comes from needing infinitely many encoded copies to drive the cyclic tag system emulation, and I'm trying to figure out whether a fixed-program version could instead rely on an eventually periodic background.

Another angle is whether that background is generated by something weaker than full universal computation, like a finite-state transducer or a morphic sequence—if so, formalizing this bound in Lean might let me reframe the complexity claim precisely rather than just assert Smith's original result.

For Rule 54, I should check Neary & Woods' work on weakly universal machines with periodic backgrounds, and consider a systematic glider collision search building a full binary collision table before looking for a compiled cyclic tag system via automated synthesis.

For the impossibility route, I'm thinking about whether I could prove bounded information flow — showing collisions reduce to a decidable ballistic particle system, which would rule out universality if particle counts decrease monotonically or the dynamics stay linear. As a fallback, a partial Lean formalization of the glider catalogue could serve as a stepping stone, though the problem likely remains open; alternatively I could search for universality on a different, non-ether background.

I should also note there's a known "integrable Rule 54" in physics literature (Bobenko et al.'s RCA54, later studied by Prosen) — but I need to be careful since this is a distinct, reversible staggered-lattice automaton and not literally the same as elementary CA Rule 54, though clearly related.

For Rule 30 itself, I'm thinking through approaches: large-scale computation of the center column (checking how far it's been verified, possibly up to around a billion steps), combined with structural arguments ruling out small periods — referencing work like Jen's periodicity-exclusion results from the late 1980s.

Density arguments alone wouldn't constitute proof, so I'm thinking about restricted computational models instead — maybe showing the center column can't be computed by finite automata or bounded-depth circuits, which would be a weaker but provable lower bound. Automatic sequences can still be aperiodic, so I'd need to check feasibility with Walnut, a tool that could test small automata hypotheses computationally.

I'm also considering the periodicity angle: if the center column were eventually periodic, left-permutivity of Rule 30's update rule might let me derive a contradiction by tracing how each cell depends on its neighbors.

I'm trying to figure out whether the near-boundary regularity of the Rule 30 pattern could be leveraged into a structural lower bound on the center column's period, but honestly this route feels speculative rather than decisive — I should note it as a long-shot direction rather than pursue it rigorously.

For the Turing instability question with n=3 species, I realize this reduces to a first-order real-arithmetic existence problem: instability exists iff the Jacobian is stable and some diffusion-scaled perturbation flips the determinant sign or triggers a wave instability. Since this is expressible in real-closed field logic, it's actually decidable via quantifier elimination — cylindrical algebraic decomposition tools like QEPCAD or Redlog could in principle settle each of the sign patterns (up to isomorphism) exhaustively.

I'm now thinking about whether there's a cleaner combinatorial characterization, connecting to sign-stability theory (Quirk-Ruppert) — the idea that Turing instability should correspond to some principal submatrix of the Jacobian failing to be sign-stable, which would give a much more elegant criterion than brute-force pattern enumeration.

Right -- Turing instability for some diagonal D occurs exactly when J is stable but not additively D-stable, a known characterization (Cross 1978). This reframes the problem: I need to find sign patterns admitting a matrix that's stable yet not additively D-stable, drawing on 3×3 D-stability literature, while noting that sign-stable patterns are always additively D-stable and thus Turing-incapable.

For n=3 I'm conjecturing Turing-capability coincides with being potentially stable but not sign-stable, though I need to watch for edge cases where stable realizations happen to be additively D-stable without the pattern itself being sign-stable -- something an exhaustive CAD enumeration could catch. My plan combines a direct proof with computational verification: exact rational witnesses checked via decision procedures for capable patterns, and CAD or sign-stability arguments for incapable ones, plus a probabilistic genericity argument for larger n examining how the fraction of potentially stable patterns behaves as n grows.

I'm also thinking about restricting the diffusion matrix to have zeros when fewer species diffuse than total species, which changes the stability condition accordingly, and I want to pull in relevant references on matrix stability classifications to ground this combinatorial approach.

For the Hamilton direction, I'm considering formalizing the Price equation as an identity over finite populations in Lean, connecting the covariance/expectation decomposition to the regression form with partial regression coefficients from least squares.

For a counterexample, I'm thinking of using a frequency-dependent, nonadditive model—like a synergistic public goods game with nonzero deviation from additivity—where the regression coefficients become state-dependent, so that the fixed-coefficient rb>c criterion fails to predict direction, drawing on van Veelen et al.'s critique of inclusive fitness regressions.

For phyllotaxis, I'm considering a computer-assisted proof using interval arithmetic to rigorously discretize the Douady-Couder least-crowded disk-packing dynamics on a cylinder, following the Atela-Golé framework.

I should use the Conley-Morse database approach (Arai, Kalies, Kokubu, Mischaikow et al.) for rigorous global dynamics via Conley index, contrasting with local analysis. I also want to test the model against real sunflower citizen-science data (Swinton et al.) to check predicted Fibonacci/Lucas/bijugate basin frequencies, and consider a Lean formalization of the Fibonacci parastichy theorem for the golden angle lattice.

For Lewontin's paradox, I'm sketching a pre-registered PGLS test comparing nucleotide diversity against census size proxies, with slopes predicted under neutral theory, linked selection (per Corbett-Detig's model), and fluctuating demography, using Buffalo's 2021 dataset.

I'm also considering simulation-calibrated approaches: SLiM forward simulations with tree-sequence recording to quantify the maximum diversity compression achievable from background selection and sweeps, compared against what's actually required. Additionally, I'm thinking about empirical demographic routes using PSMC-inferred population histories across hundreds of species with published genome assemblies to assess how time since bottlenecks affects equilibrium diversity.

I want to flag a circularity risk though: using PSMC-derived harmonic-mean Ne to predict π is problematic since PSMC itself is calibrated from θ (which depends on π), so that test wouldn't be independent. A cleaner angle might be mutation rate covariation—since π = 4Neμ, and the drift-barrier hypothesis (Lynch 2016) predicts μ scales inversely with Ne, pedigree-based mutation rate estimates could offer an independent check.

With Bergeron et al. 2023's germline mutation rate data across 68 vertebrate species, I could decompose log π into log Ne plus log μ using measured mutation rates, then test the residual relationship between Ne and census size—this feels like a genuinely distinct approach.

For the metabolic scaling question, I'm thinking through a pre-registered PGLS analysis of BMR versus body mass in mammals and birds, with temperature correction. AnAge and PanTHERIA could supply the trait data, Upham 2019's VertLife tree for phylogeny, and I'd want to compare a simple power law against the Kolokotrones curvature model and taxon-specific fits.

I should avoid overclaiming the exact sample size—better to pre-register a minimum of 300 mammal species and just use whatever AnAge entries have both metabolic rate and mass at retrieval time. I'm also considering a Lean formalization of West-Brown-Enquist theory, deriving how branching ratios set the radius and length scaling exponents under area-preservation and space-filling constraints, leading to how capillary number should scale with body mass.

The key insight is that the 3/4 exponent only emerges exactly in the infinite-levels limit—this is the disputed Kozlowski-Konarzewski critique, and I should check against Savage et al. 2008's finite-size corrections paper. A finite-N Lean formalization could make explicit which assumption (volume proportional to mass, invariant capillary size) drives the discrepancy, and this feels like a tractable, well-scoped project. I'm also weighing a third option: comparing optimal network theory (Banavar-style) against finite WBE predictions through simulation.

As an alternative to that third approach, I could instead look at data across different taxonomic groups—checking Makarieva et al. 2008 and DeLong et al. 2010 for evidence that the metabolic scaling exponent actually differs between prokaryotes, protists, and metazoans, since DeLong reportedly found superlinear, linear, and 3/4 scaling in different domains.

For species-area relationships, I'm sketching out a pre-registered test using GBIF data across island archipelagos like the Canaries, Galápagos, Hawaii, Azores, and Philippines, focusing on land snails, birds, and vascular plants. I'd compute richness using coverage-based rarefaction methods like iNEXT and Chao, then compare power-law, Gleason log-linear, and METE model fits.

Alongside this, I'm considering a theoretical/simulation approach testing whether a sampling-only null — drawing from Preston's canonical lognormal species abundance distribution — can reproduce the observed z≈0.25 scaling and its variance across the large Triantis 2012 dataset of island surveys, which would be a decisive test of whether this "universal" scaling is actually just a statistical artifact of sampling.

So approach 2 becomes the null model computation while approach 3 turns into a random-effects meta-analysis of heterogeneity in z across datasets. For clade trajectories, I'm sketching a pre-registered PBDB test using subsampled richness curves per stage, measuring hat-shapedness via center-of-gravity and unimodality statistics against a matched MBL birth-death null, alongside a model-based alternative using PyRate with time-varying diversification rates to test whether rates decline over a clade's lifespan.

I also want a clade-definition artifact audit comparing monophyletic phylogeny-backed groupings against paraphyletic taxonomic ones, including a pull-of-the-recent check and a simulation showing how much hat-shape is imposed purely by Linnaean classification artifacts. That gives distinct lines of evidence, so now I'm turning to shell morphology tests, starting with one that requires an actual measured width/diameter/thickness dataset.

Data from MorphoSource 3D scans or the morpholib pipeline is too sparse to rely on alone, so I'm considering a functional computation approach instead — modeling mechanical and hydrostatic properties across the full Raup morphospace to predict which regions should be empty for functional reasons, then comparing that against real occupancy data from Raup's original compilations and published ammonoid measurements. I'm also thinking about a developmental-constraint model using growth-based generative frameworks to figure out which shell geometries are even reachable given local growth rules and self-contact constraints that rule out impossible whorl overlaps.

I want to formalize the geometric boundary conditions in Lean — specifically Raup's condition for when whorls just touch versus overlap — to derive the limits of the "constructionally possible" region rigorously. That gives me a third approach combining formal derivation with a generative constraint map, plus a fourth approach using phylogenetic null models like Brownian motion or Ornstein-Uhlenbeck processes, which folds into the first approach. Then for the somite clock problem, I'm shifting to designing a pre-registered comparative test across species with measured clock periods and elongation rates — zebrafish, medaka, chick, and other model organisms.

For a fitted dynamics approach, I'd model tailbud growth input and PSM consumption to predict N in held-out species. For a macroevolutionary approach, I'd leverage vertebral count datasets alongside temperature-dependent clock period data, testing whether Arrhenius scaling of clock versus elongation rates could explain Jordan's rule—the tendency for fish to have more vertebrae in colder waters.

If the clock and elongation processes have different temperature sensitivities (Q10 values), that predicts somite number should shift with rearing temperature, though zebrafish data suggests somite count is largely temperature-invariant even as vertebral meristic plasticity is documented in other fishes. I should compile literature on rearing-temperature meristic experiments as a direct empirical test, and also rank candidate species to measure using a value-of-information framework.

Now I'm verifying a batch of DOIs by checking HTTP response codes against each URL.

I realize publishers often block HEAD requests from bots, so I'll switch to the doi.org handle API instead, which confirms registration, and cross-check titles against Crossref's API to make sure each DOI maps to the correct paper. I'll draft the DOI list and run this verification script from a temp directory rather than the repo.

That didn't run yet - I'll write the list file using the Write tool, then execute the script.

I'm noticing some DOI mismatches - the one attributed to Martínez Rule 54 is actually Gutman's, and the Fisch paper was mislabeled as Jen's, so I need to drop or correct those citations. I'll also need to retry the rate-limited title lookups sequentially with delays.


Found that the Martínez Rule 54 DOI and my guessed Jen 1990 DOI both resolve to the wrong papers. Crossref is rate-limiting me, so I'll re-check the remaining titles one at a time.

I'm finding several citations with mismatched DOIs that need to be dropped — Liow & Stenseth, Noshita, Schröter, Ward & Brainerd, Montgomery & Coward, Kusner, and Levitov's phyllotaxis paper all have incorrect identifiers.

I still need to track down correct DOIs for Martínez's Rule 54 glider paper, Jen 1990, Liow & Stenseth 2007, Schröter 2008, and Kusner 1992 — I'll try the Crossref search API for these.


Some DOIs resolve to unrelated papers, including the Martínez Rule 54 paper and Liow & Stenseth 2007 from problems.json. I'll search for the correct DOIs bibliographically, then check the dataset and tool URLs.

The correct DOIs are Martínez 2006 → `10.1016/j.chaos.2005.05.013` and Liow & Stenseth → `10.1098/rspb.2007.1006`. I'm retrying the remaining searches more slowly.

I'm hitting Crossref's rate limit, so I'll bump the sleep time to 4 seconds before retrying the rest, and narrow the list down to just the entries I'll actually use.

The heredoc approach might be causing issues, so I'll just write search2.py directly with the Write tool instead.

I should verify how many steps the center column was computed to for the Rule 30 prize, and check the Wolfram writings page for mentions of "billion" and Jen's result.


I've located correct DOIs for Jen 1990, Schröter 2008, Kusner 1992, Levitov's EPL paper, Kassab 1993, Brakke 1992, Lehmann & Keller 2006, Damuth 1981, and Ellegren & Galtier 2016. Now I'll verify a few factual details, like how far the Rule 30 column has been computed.

I'm noting that Jen's result works on any two columns, and that rule 30's left-side diagonals are periodic. I should also reference the Wolfram Data Repository for the billion-bits dataset, and double-check the ether period for rule 110 before moving on.

I'm cross-checking several other facts: rule 54's ether period isn't something I'm confident enough to state numerically, Mathlib's Turing machine formalizations exist as cited, BB(5) was indeed Coq-verified in 2024, and the AnAge/PanTHERIA/GIFT/DRIVE/HRF/VesSAP dataset fields I'm recalling line up correctly. I'm also verifying ZFIN's phenotype and morpholino download files, and trying to recall the exact figures from Kok et al.'s comparison of morphant versus mutant phenotypes.

For the remaining citations, I'm wary of overstating precision — Bergeron 2023's species count I'll hedge as "dozens of vertebrate species" rather than committing to a specific number, and I'm confirming Romiguier 2014's transcriptome study covered dozens of non-model animal species, plus checking that Biswas 2021 and the Buffalo 2021 repository details match what's already established.

I'm also running through other examples: Leffler's 167-species comparison, Corbett-Detig's 40-species study, Swinton's sunflower spiral analysis (hedging the count as "several hundred heads" rather than a precise figure), Gomez's work across zebrafish, chick, mouse and corn snake, Matsuda's comparison of segmentation clock timing between mouse and human tissue, and Head & Polly's work on vertebral counts across squamates.

Beyond that, I'm recalling Schröter's work on temperature-dependent zebrafish clock periods, Gómez-Gálvez's scutoid connectivity findings tied to tissue curvature, Wolny's PlantSeg datasets on Arabidopsis ovules and roots, and Kusner's minimal foam face-count proof.

Now I'm checking the numbers: Kusner's bound of roughly 13.397 average faces, Weaire-Phelan's ~0.3% area savings over Kelvin's structure, and comparing normalized surface-to-volume ratios—Kelvin at 5.306, Weaire-Phelan at 5.288, against the sphere's isoperimetric minimum of 2.418.

I'm also thinking the 3D isoperimetric inequality likely isn't formalized in Mathlib—this would need a Brunn-Minkowski approach. I'm noting the Murray turbulent exponent of 7/3 comes directly from the problem statement, and recalling Turing's characterization criteria.

On matrix stability, I recall Cross 1978's "Three types of matrix stability" covering D-stability, additive D-stability, and Volterra-Lyapunov stability—relevant here since Turing instability with arbitrary nonnegative diffusion for some wavenumber corresponds to a Jacobian not being additively D-stable. Satnoianu et al. 2000 likely discuss this connection too, and I should also flag sign-stable pattern results from Quirk-Ruppert and Jeffries-Klee-van den Driessche.

I'm checking whether every sign-stable matrix is automatically additively D-stable, working through how adding a negative diagonal perturbation affects the sign pattern—particularly cases where diagonal entries are zero and the perturbation flips them negative, then testing this against Jeffries' conditions for sign stability (nonpositive diagonal, at least one strictly negative, off-diagonal sign reciprocity, no long cycles, nonzero determinant).

This makes me suspect sign-stable implies additively D-stable, meaning sign-stable patterns can't produce Turing instability, so I'm forming a conjecture that among potentially stable patterns, Turing capability is equivalent to not being sign-stable—essentially tied to whether the digraph contains cycles of length three or more, since those cycles become rare as the number of nodes grows, which would support a genericity argument for the conjecture.

Switching tracks, I'm formalizing Hamilton's rule in finite populations using the Price equation, defining the selection and relatedness coefficients as OLS regression coefficients of fitness on gene frequency and group gene frequency, then deriving the sign of the change in mean gene frequency from the standard 2x2 normal equations decomposition of covariance.

I'm sketching a counterexample from synergistic game theory (Queller 1985) where interaction payoffs include a nonlinear term, making the regression coefficients frequency-dependent and causing the rule to fail predictively — this seems tractable as an explicit rational example.

I'm also recalling phyllotaxis models, particularly the Douady-Couder repulsion-based model where new primordia form at least-energy points on a growing circle governed by a growth parameter.

For Lean formalization, I'm thinking about continued fractions in Mathlib and the classical result linking divergence angle convergents to visible parastichy numbers, though I need to track down a citation. For shell morphology, I'm noting Raup's W=1/D boundary separating overlapping and non-overlapping coiling, and considering where to source actual measured W, D, T data — likely CT scans from MorphoSource or 2D images from iDigBio.

For ammonoid shell coiling data, I'm recalling Raup's 1967 Journal of Paleontology paper on geometric analysis of coiling. For morpholino phenotype data I can rely on ZFIN records, though I'm uncertain whether there's an official code repository for the gene regulatory network memory model. Since some tools timed out or got blocked, I'm substituting GitHub links for roadrunner/tellurium and SLiM instead.

I'm also verifying GBIF's API endpoint since the main site blocks requests, checking Wolfram's data repository entry for the Rule 30 billion-bits dataset, and confirming CRAN package pages for sars, iNEXT, divDyn, phylolm, along with the PyRate GitHub repo.

Then I shift to checking symbolic math alternatives like Redlog and SageMath for the QEPCAD problem, z3's nlsat solver, and the Coq-BB5 repository along with Wolfram's TM(2,3) prize page for busy beaver verification. I also note that Xenbase redirects to a captcha so I should avoid it, and I'm checking Ensembl's REST API for paralog data via compara.

I continue verifying sources: INDRA CoGEx on GitHub, HPO and GO look fine, Alliance of Genome Resources, and I decide to skip Triantis 2012 supplementary data and PlantSeg's OSF repository. BioModels checks out, and for the scutoids work by Gómez-Gálvez I can cite their GitHub organization as the code source. I also confirm Dryad, VertLife, AnAge, and NCBI's datasets portal are usable, while Planosphere times out and should be skipped.

Continuing through the list, BETSE checks out fine, and I note PyRate's GitHub repository and the divDyn package for SQS analysis as valid sources.


I've confirmed that no two columns of Rule 30 can both be periodic, with the centre column verified non-periodic through the first billion steps. Now I'm doing a final check of the tool and code repository URLs.

All citations are verified. I'm writing the approaches file now: three approaches per problem, each set mixing proof, computation and data routes.

I'm planning to write a large JSON file covering roughly 20 problems with about three approaches each, keeping entries concise but technical, and being careful about quote escaping as I write it directly.

I'm also compiling my list of verified references and DOIs to cite—covering cellular automata universality, reaction-diffusion patterns, kin selection theory, and phyllotaxis dynamics—so I can accurately attribute each approach to its source.

Now I'm pulling together references on paleobiology extinction/origination rates (Foote, Liow, Raup, PyRate, Alroy), disparity and morphospace work (Gerber, Moulton), somitogenesis clock models (Cooke-Zeeman, Oates, Lauschke), and vascular network scaling citations (Murray, Sherman, West-Brown-Enquist metabolic theory, Kassab).

I'm now gathering citations on bioelectricity and morphogenesis (Levin, Pietak, Vandenberg, Durant), epithelial packing geometries (Gómez-Gálvez, Weaire-Phelan foam structures), and free energy/active inference frameworks (Friston, Kuchling, Daunizeau).

With references compiled, I'm planning the tool slugs needed for the approaches section—covering formal verification, large-scale computation, biodiversity databases, and simulation frameworks—before drafting the actual file content starting with the rule110 problem.

For that first approach, I'm structuring a Lean formalization following Cook's construction directly, defining the rule110 step function and the ether's spacetime periodicity, though I'm uncertain about the exact shift value Cook specifies for the ether's horizontal/vertical periods.

Then I'd model gliders as finite words spliced into the ether, with a locality/light-cone lemma enabling splicing (cells outside the light cone of a change remain unaffected), and build toward a "glider calculus" abstracting configurations as sequences of glider type, phase, and gap, with a theorem connecting this abstraction to actual CA evolution.

For the actual universality argument, I'd need Cook's cyclic tag system encoding via tape/appendant/ossifier gliders, then prove CTS simulate 2-tag systems and 2-tag systems simulate Turing machines—possibly leveraging Mathlib's Turing machine formalization. This is a long-shot in terms of difficulty given the scale of Cook's construction and the number of glider spacings involved, plus performance concerns since `decide` lacks native acceleration. I'd also want an independent computational audit: re-deriving Cook's full glider catalogue and collision table via exhaustive simulation and SAT solving to verify every collision used in the construction.

I'm also considering an alternative route through a verified checker approach—formalizing in Lean an executable certificate checker that decomposes the infinite Rule 110 spacetime diagram into a finite Wang-tile-style set with matching edges, each tile's correctness verified computationally.

For the (2,3) TM problem, I'm starting with a decidability route targeting eventually-periodic tapes, planning to use automated deciders from the bbchallenge project.

A second route: try modifying Smith's emulation chain (the sequence of systems from the (2,3) machine down to a cyclic tag system) to work with an eventually-periodic background instead of a genuinely infinite one. That means formalizing each layer of Smith's reduction as executable specs, pinpointing exactly where non-periodicity becomes essential, and searching for replacement gadgets (perhaps via SAT or enumeration) that could generate the needed structure from a periodic seed — something like a self-replicating 'refuel' gadget. This is another long-shot, but it points toward formalizing Smith's proof itself, precisely stating the initial-tape condition.

For Rule 54, the strategy would be building an exhaustive catalogue of gliders and collisions, then automating the search for a Cook-like emulation of a cyclic tag system — looking for data gliders, a moving tape, ossifiers, and a periodic program stream within the collision graph, using SAT or graph search with timing constraints. A decisive result would be a working emulation of a small universal CTS, verified by direct simulation and then checked in Lean.

Alternatively, I could pursue an impossibility route: proving a structural bound showing that collisions are reversible-like with a conserved quantity, or that the reachable configurations from any finite ether perturbation form a decidable ballistic particle system. If I can compute the particle collision algebra and show a potential function (like weighted glider count) strictly decreases, then the long-run dynamics would be ballistic rather than universal, meaning gliders eventually become free — this connects to Bobenko's integrable RCA54 analogy where solitons only phase-shift.

A third angle: cataloguing spatially periodic backgrounds up to period 30 with temporally periodic dynamics, using de Bruijn diagram methods (à la McIntosh) to enumerate gliders on each background and look for one supporting richer collisions like Rule 110. This classification task is tractable as a deliverable even if full universality remains open, and it would feed directly into the other two approaches.

For Rule 30, I'm sketching a Lean formalization plan: encode the rule itself, the left-permutivity reconstruction lemma, Jen's theorem (no two columns both eventually periodic), and then push toward a conditional result about what happens when the center column is eventually periodic with period p — trying to pin down whether the neighboring column becomes determined.

On the computational side, I'm estimating feasibility of extending the center column to huge bit lengths. Naive O(n²) updates become astronomically expensive at n=10^12, but with bit-parallel SIMD and GPU throughput, something like n=10^10–10^11 seems within reach over roughly a day of compute — though this alone wouldn't settle the conjecture, so it'd need to be paired with a structural argument.

I'm thinking about a more decisive approach: certified non-periodicity checks excluding periods up to N/2, combined with a pre-registered statistical test comparing density deviations against the law-of-iterated-logarithm scaling √(n log log n), which gives computational evidence without constituting proof. There's also a path through restricted-model lower bounds — using Walnut-style automatic sequence exclusion to rule out the column being generated by any small-state DFAO over various bases via prefix analysis.

The DFAO exclusion claim reduces to a finite but potentially large SAT-style search, checkable in Lean via `decide` on a prefix. Similar restricted-computation lower bounds could apply to problem 3 — showing the n-th bit isn't computable by a small finite transducer or isn't a small morphic sequence — though I'm unsure whether "not automatic" is trivially true here. For problem 5 on Turing topologies, I'm trying to characterize the pattern via additive D-stability, starting from a known lemma about Turing-capable patterns with arbitrary diffusion coefficients.

Then I move to a lemma showing sign-stability implies every realization is additively D-stable and hence Turing-incapable, followed by a conjecture for the n=3 case: potentially stable but not sign-stable implies Turing-capable, which I plan to prove by case analysis on which Jeffries condition fails, constructing explicit witness matrices for each case. For diffusion restricted to a subset of species, the stability condition generalizes to diagonal matrices supported on that subset, which brings in principal submatrices.

For formalizing this in Lean, I consider building explicit witness families with polynomial inequalities handled by nlinarith or positivity, and stating Routh-Hurwitz conditions for 3×3 matrices as characteristic polynomial coefficient inequalities, though proving full Routh-Hurwitz equivalence in Lean is nontrivial given Mathlib's current state—I may need to just state stability definitionally via these conditions and flag this as a hard gap. Alternatively, I consider exhaustive enumeration: for n=3 there are 3^9 sign patterns, reducible to roughly 3300 up to relabeling, and for each combined with diffusing subsets I'd need to decide the existential-real problem via cylindrical algebraic decomposition.

I'm thinking that for stable cases, a sampled numerical witness could be verified exactly as a rational point checkable by norm_num in Lean, while unstable cases would need a CAD-generated false certificate or a sign-stability proof instead. Scaling to n=4 is much harder—3^16 is about 43 million patterns, ~1.8 million up to relabeling—so I'd want numeric sampling plus exact witnesses for feasible cases, reserving full CAD only for the hard residue, and I should compare results against the Marcon 2016 and Scholes 2019 atlases. This confirms n=3 is tractable but n=4 pushes computational limits. I'm also considering a combinatorial genericity argument: the fraction of sign-stable patterns among potentially stable ones with feedback loops should tend to zero, since sign stability forbids certain cycle lengths.

I want to show the digraph must decompose as a forest of 2-cycles, and prove asymptotically that patterns with no cycles of length 3 or more are vastly outnumbered by all sign patterns—then argue that for large n, almost all patterns become Turing-capable, though this depends on generalizing Conjecture C and may not hold universally. As an unconditional alternative, I could try a perturbation lemma showing that any pattern embedding a 3-node capable subpattern remains capable under small coupling changes, though this seems difficult. Shifting to Hamilton's rule, I'm sketching a finite-population Lean formalization using the Price equation to establish the regression-based identity linking the sign of average fitness change to the sign of rb − c.

I want to show that b and c, defined as OLS partial regression coefficients on realized population data, satisfy a 'content' theorem: under an additive fitness model with uncorrelated noise, these regression coefficients equal the true model parameters across all population states, making the rule genuinely predictive rather than tautological. I'm also planning explicit counterexamples using known synergy games (Queller, van Veelen) in structured populations with relatedness r, choosing rational parameters where rb > c holds by the model's definition yet allele frequency actually decreases, demonstrating that the regression b and c are frequency-dependent. Finally, I'm mapping out a computational sweep across model classes—Wright-Fisher island models and Moran processes on various population structures—to classify when Hamilton's rule holds predictively versus merely descriptively.

Beyond the kin selection problem, I'm turning to phyllotaxis, aiming at a computer-assisted proof classifying attractors in the cylindrical hard-disk model, using interval arithmetic and rigorous root-finding methods to verify branches of the rhombic lattice solutions and their stability.

I'm also considering formalizing in Lean the parastichy number theory connecting continued fraction expansions of the divergence angle to visible parastichy pairs, with the golden angle case yielding Fibonacci numbers.

This covers the lattice combinatorics but not the dynamics itself — it gives the target statements without settling the classification. For the dynamical side, I'd want large-scale simulations of the DC model to estimate basin measures across Fibonacci, Lucas, bijugate and other phyllotactic patterns.

For Lewontin's paradox, I'm thinking through a pre-registered PGLS analysis extending the Buffalo 2021 dataset with GBIF range data and Damuth density estimates for census size, testing whether the observed slope of log diversity on log N matches neutral predictions versus linked-selection reductions from a Corbett-Detig-style fit — tractable in principle but limited by how noisy census estimates really are.

Two more approaches come to mind: decomposing mutation rate using Bergeron 2023 pedigree estimates to back out effective population size and test for drift-barrier effects on mutation rate itself, which seems feasible with the smaller available dataset; and running SLiM/msprime simulations across a huge range of census sizes with background selection and recurrent sweeps to find the maximum possible flattening of the diversity curve, which would be decisive but computationally expensive and vulnerable to rescaling artifacts at extreme population sizes.

For the metabolic scaling question, I'm thinking through a pre-registered PGLS analysis comparing power-law, curvature, and order-specific models across mammals and birds with phylogenetic correction and temperature covariates, and also deriving a finite-N geometric-series version of WBE theory that only converges to the 3/4 exponent as network size goes to infinity.

Next I'm planning a cross-domain heterogeneity test using DeLong 2010 data across prokaryotes, protists, and metazoans plus ectotherm compilations, with a hierarchical model where non-overlapping group-specific exponent intervals would falsify a universal scaling exponent.

For species-area relationships, I'm designing a pre-registered GBIF island test across archipelagos like the Canary Islands, Galápagos, Hawaiian Islands, Azores, and Balearic Islands, using GIFT island area and checklist data as an independent ground truth for vascular plants.

I'm also considering a null-model check: testing whether random-placement sampling from lognormal or log-series species abundance distributions reproduces the observed z-value distribution, following Coleman's 1981 random placement model, computed against Triantis' 601 datasets and validated with a random-effects meta-analysis of z estimating heterogeneity (τ²) and checking slope variation against METE predictions.

Then I'm noting that since METE predicts z as a function of log(N/S), testing that collapse would require abundance data rather than just occurrence counts from GBIF, which is a real data limitation — so I'll apply it only where abundance data exists, and rely on the broader meta-analytic heterogeneity approach otherwise. I confirm the remaining planned sections (clade trajectories, shells, somites, Murray) stay as previously outlined.

For the Murray's law piece, I'm designing a pre-registered exponent estimation across multiple vascular datasets (retina, brain, coronary, xylem) using per-bifurcation root-finding to solve for the branching exponent, then a hierarchical model with errors-in-variables correction. I'm pairing this with a Lean formalization of Murray's law and its turbulent variant, plus a synthetic-tree simulation that models image blur, pixel quantization, and segmentation errors to calibrate how much bias these introduce into exponent estimates — this calibration step is decisive for determining whether current data can actually distinguish between competing exponent values. Then I start into the gene overlap section, planning a matched permutation test.

For the bioelectric predictions, I'm laying out three approaches: a cross-study leave-one-out decoder, pre-registered mechanistic forward predictions for channel perturbations using BETSE simulation, and a dose-response meta-analysis linking membrane voltage shifts to phenotype penetrance from a coded literature corpus.

For GRN memory, I'm considering matched random ODE ensembles, degree-preserving rewiring to separate topology from kinetics effects, and a theoretical approach linking memory types to dynamical features like multistability—using chemical reaction network theory to predict which BioModels can't sustain long-term memory and testing that prediction.

For active inference, I'm sketching a formal complete-class result in Lean along with pre-registered derivations.

Then I'm thinking through Xenopus craniofacial remodeling data: active inference with fixed precision predicts organs farther displaced remodel faster, while a hardwired-movement model predicts displacement-independent rates—a genuinely discriminating test, though limited by image data availability from the published papers.

For the Kelvin problem, I'm weighing four directions: computer-assisted verification of local optimality of the Weaire-Phelan structure via second variation, a Lean-formalized isoperimetric lower bound (possibly a long-shot full Brunn-Minkowski formalization), testing scutoid geometry against curvature using Gómez-Gálvez data with a Voronoi-tube model, and Surface Evolver simulations computing minimal-energy scutoid frequency versus radial expansion ratio—likely combining the empirical and simulation approaches.

For the final problems, I'm settling on three approaches each, bringing the total to sixty, and deciding against adding extra empirical entries. I'm also working through formatting conventions—using empty arrays for datasets when no empirical data applies, matching the reference format with doi or url plus notes, and double-checking citation details like the Lauschke et al. publication year discrepancy between print and online dates.

Now I'm ready to assemble the complete JSON structure carefully, entry by entry.

Time to write out the full file now.

The file is written. Next I'll validate the JSON and cross-check that every DOI and URL in it was verified. One DOI (Stoeger 2018) was added while drafting and has not been checked yet.

I noticed one DOI I added, the Stoeger 2018 paper, is still unverified and needs checking, while the other doi.org dataset URLs appear properly registered. Now I should validate the JSON, count entries, and confirm every DOI in the file matches my verified set.

JSON parses: 60 approaches across all 20 problems. Twelve titles go over the 90-character limit, so I'll shorten them, then confirm every DOI and URL is in the verified set.

I need to fix 12 titles that are too long, then cross-check the DOIs against my verified list.

Only one DOI (Stoeger 2018) and the JSTOR link for Raup 1966 remain unchecked; the `doi.org` URLs wrap DOIs that are already verified. I'm checking those two now.

The DOIs look like valid registered identifiers, but I should double-check that the JSTOR URL actually resolves and verify the Stoeger DOI specifically.

The rsos DOI itself resolves fine via the doi.org API even though the publisher page is blocking bots with a 403 — that's just bot-blocking, not a broken link, so I should be cautious about whether the build process might drop it anyway.

Every link resolves. Now shortening the 12 long titles.

Good, all the links resolve through doi.org. Next I need to address the overly long titles.

That file showing as modified is odd since I didn't touch it directly—someone else may have committed changes in between. I should check the git log for that file to figure out what happened.


Git shows my output file as modified rather than new, meaning a version was committed after my initial directory listing. I'll check its current contents before making changes to avoid overwriting someone else's work.

I realize the committed version is actually my own first write that someone else committed while I was still working, so the diff is just my title edits plus json.dump's reformatting expanding inline objects into multi-line. That reformatting bloats the diff unnecessarily, so I should apply the title changes directly via string replace on the original committed file instead to keep the diff minimal.

I also notice pending/claude-opus-5-5.json was modified by someone else, not me, so I'll leave that file alone.


I see the committed copy matches my draft, but my title-fix script re-serialized the whole file, bloating the diff. I'll redo the 12 title fixes as plain text edits on the committed version so the diff stays minimal, and leave `pending/claude-opus-5-5.json` untouched since I didn't modify it.

I wrote 60 approaches covering all 20 problems, 3 per problem, to `problems/approaches/claude-opus-5-5.json`. The file parses with the `node -e` command you gave, and no problem got fewer than 2 approaches.

**Difficulty:** 33 approaches are rated tractable, 20 hard and 7 long-shot. The long-shots are mainly the full proofs: the Rule 110 Lean proof, the (2,3) machine on periodic tapes, Rule 54 universality or impossibility, and rigorous Weaire–Phelan local optimality. Where an approach needs something the swarm lacks, the `missing` field says so. Examples are new lab measurements (somite clocks, Vmem imaging) and geometric measure theory that Mathlib doesn't have yet.

**Citations:** every DOI was checked: it is registered at doi.org and its Crossref title matches the paper cited. Every URL returned HTTP 200 or a valid doi.org redirect.

**Wrong DOIs in `problems.json`:** two of its DOIs point to unrelated papers. I used the correct ones and said so in the relevant notes:
- **Martínez, Adamatzky & McIntosh 2006 (Rule 54):** the listed DOI is a 2006 paper by Gutman; the correct DOI is `10.1016/j.chaos.2005.05.013`.
- **Liow & Stenseth 2007:** the listed DOI is a 2007 paper by Siveter; the correct DOI is `10.1098/rspb.2007.1006`.

`problems.json` also labels `10.1103/PhysRevLett.66.224` as Levitov's "Energetic approach to phyllotaxis". That DOI is actually his flux-lattice paper, so I cited the Europhysics Letters paper instead.

**State of the repo:** while I was working, someone committed my first draft of the output file. The only uncommitted change now is 12 titles I shortened to fit the 90-character limit. `problems/approaches/pending/claude-opus-5-5.json` also shows as modified, but I didn't touch it. I edited no other file.

_Tools used: Read ×4, Shell ×21, StrReplace, UpdateCurrentStep ×4, Write ×11_
