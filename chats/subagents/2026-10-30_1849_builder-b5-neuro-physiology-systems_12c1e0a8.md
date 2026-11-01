# Subagent: Builder B5: neuro, physiology, systems

- **Parent chat:** [Math-meets-biology thinkers, theorem claims as nanopubs](../2026-10-30_1844_math-meets-biology-thinkers-theorem-claims-as-nanopubs.md)
- **Started:** 2026-10-30 18:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-30 18:54 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** aborted
- **Transcript ID:** `12c1e0a8-bc19-464f-91b1-9ec8dec25a2a`

---

### 2026-10-30 18:49 — Turn 1 (User)

> You are a BUILDER agent in a Project Delphi multi-agent pipeline that evaluates which major thinkers in mathematical biology have claims that are testable and could reach theorem status. Your job is ONLY to extract and document claims precisely. You must NOT score or rank anything (separate assessor agents from other providers do that; builder != assessor).
> 
> Workspace: /Users/jdietz/Documents/GitHub/dev/delphisci/math-bio-theorems
> - Roster: inputs/roster.json — your batch is "B2-evolution-complexity-computation" (10 thinkers).
> - Rubric (for context only, do not score): inputs/rubric.json
> - MorphoEval Lean law index: inputs/morphoeval_math_laws.tsv (columns: law_id, label, source, leanVerified). Grep it for your thinkers (author names, law names) to fill lean_coverage. Note: all entries are flagged leanVerified=true but the Lean proofs may be generic lemmas, so just record matches, don't over-interpret.
> 
> For EACH thinker produce exactly 3 claims: their most central, distinctive mathematical-biology claims (e.g. for Eigen: the error threshold, the hypercycle, quasispecies selection). Prefer claims that are well-known and that a researcher would associate with the person. Mix kinds when natural (a proved model theorem, an empirical law, a conjecture/principle).
> 
> Ontology mapping: each claim will become a delphi:TestableHypothesis (subclass of delphi:Hypothesis) with delphi:proposedTest, prov:wasDerivedFrom the source DOI. A claim is a belief, not a fact.
> 
> Write ONE file: claims/B2-evolution-complexity-computation.json with this exact schema:
> {
>   "batch": "B2-evolution-complexity-computation",
>   "builder": {"agent": "builder-B2", "model": "claude-sonnet-5-5-high"},
>   "thinkers": [
>     {
>       "thinker_id": "<id from roster>", "name": "...", "lifespan_or_active": "...", "one_line_contribution": "...",
>       "claims": [
>         {
>           "claim_id": "<thinker_id>-c1",
>           "label": "short name of the claim",
>           "statement": "informal statement in 1-3 sentences, faithful to the author",
>           "formal_statement": "the most precise mathematical statement you can give (LaTeX-ish plain text), including the model assumptions; if no canonical formalization exists, say so and give the best candidate",
>           "kind": "model-theorem | empirical-law | conjecture | principle-or-framework",
>           "formal_status": "proved | proved-under-idealizations | partially-proved | open | refuted-as-stated | not-a-mathematical-statement",
>           "proof_reference": "who proved it/where, or null; mention any machine-checked formalization (mathlib, Lean, Coq, Isabelle) ONLY if you are confident it exists",
>           "source_citation": "Author (year) Title. Journal vol:pages",
>           "source_doi": "10.xxxx/... or null",
>           "doi_verified": true/false,
>           "proposed_test": "the experiment or dataset analysis that would resolve the claim empirically",
>           "measurable_quantities": ["..."],
>           "empirical_status_summary": "1-3 sentences on what tests have shown, with named key studies",
>           "evidence_for": ["short points with named studies"],
>           "evidence_against": ["short points with named studies; include critiques of the formal-to-biology bridge"],
>           "lean_coverage": ["morphoeval law_ids that match, or empty"],
>           "notes": "anything an assessor should know, or null"
>         }
>       ]
>     }
>   ]
> }
> 
> HARD RULES (from the project's BEST_PRACTICES — no dummy data):
> 1. NEVER fabricate DOIs, citations, studies, or formalizations. For each source_doi, verify it via Crossref: `curl -s "https://api.crossref.org/works/<DOI>" | python3 -c 'import sys,json; m=json.load(sys.stdin)["message"]; print(m["title"], m.get("issued"))'` and confirm the title/year match the work. If you cannot verify, set source_doi to null and doi_verified false (keep the source_citation). You can also search Crossref: `curl -s "https://api.crossref.org/works?query.bibliographic=<url-encoded title author year>&rows=3"`. Books (e.g. Rosen's Life Itself, Maturana & Varela's Autopoiesis and Cognition) may have book or chapter DOIs; check, don't assume.
> 2. No placeholders (TODO, TBD, example.org, lorem). Every field must be real content or null.
> 3. Be honest about uncertainty and disputes; evidence_against must be substantive. Several thinkers in this batch (Rosen, Maturana-Varela, England, Chaitin, Kauffman) have claims whose formal and empirical status is contested — document the contest rather than resolve it.
> 4. Validate the final file parses: `python3 -c "import json;d=json.load(open('claims/B2-evolution-complexity-computation.json'));print(len(d['thinkers']), sum(len(t['claims']) for t in d['thinkers']))"` must print `10 30`.
> 
> Do not edit any other files. When done, reply with: the file path, the count of claims, the number of DOIs verified vs null, and any thinker where you were unsure of the canonical claims.

**Assistant:**

That grep was too broad, so I should narrow it down to just the source column for our specific thinkers.

Coverage seems mostly empty for our thinkers here, so I'm checking related terms like von Neumann, Kauffman, and random Boolean networks to see if anything connects.

None of the thinkers directly match this morphogenesis index, though von Neumann's kinematic self-replication could be a loose thematic match to kriegman's xenobot evolutionary work. I'll avoid over-interpreting and just note it in the notes field, leaving lean_coverage empty.

Now I'm drafting candidate claims with DOIs for Nowak, starting with evolutionary graph theory's isothermal theorem from the 2005 Nature paper on amplifiers and suppressors of selection, and the "Five Rules for Evolution of Cooperation" from Nowak's 2006 Science paper covering kin selection, reciprocity, network reciprocity, and group selection thresholds — checking these against empirical support and later critiques like Allen et al.'s 2017 work on arbitrary population structures.

I'm weighing whether to pick the "b/c>k" network reciprocity rule from Ohtsuki et al. 2006 as a separate claim versus folding it into the five rules, and considering Nowak's eusociality paper as too controversial, before leaning toward a more mathematically solid alternative like the Nowak, Sasaki, Taylor, Fudenberg 2004 emergence of cooperation paper.

Now I'm weighing which claim to pick as the contested third candidate — the eusociality paper (Nowak, Tarnita, Wilson 2010) arguing inclusive fitness theory is unnecessary, versus the one-third law from evolutionary graph theory. The eusociality claim is more famous for sparking controversy, while the one-third law is a more rigorously provable model result, so I'm leaning toward using the eusociality debate since it offers a sharper contrast.

Now I'm moving to the second case, Eigen's error threshold theory, tracing it from Eigen's original 1971 formalism of maximum genome length as a function of mutation rate and selective superiority, through later refinements by Swetina and Schuster.

I'm also noting the counterarguments against error catastrophe — Bull, Meyers, Lachmann's "Quasispecies made simple," Summers & Litwin's critique, and the Bull-Sanjuán-Wilke distinction between lethal mutagenesis and true error catastrophe — before moving to the hypercycle concept from Eigen & Schuster's 1977 paper.

For the hypercycle itself, I'm recalling the dynamical equations governing its growth and the stability results: fixed-point persistence for small cycles (n≤4) versus stable limit cycles for larger ones (n≥5), citing Hofbauer's work on limit cycles in Lotka-Volterra-type systems and the later Hofbauer-Mallet-Paret-Smith proof of stable periodic solutions.

I also recall the vulnerability of hypercycles to parasitic sequences, raised by Maynard Smith and Bresch/Niesert/Harnasch, and the proposed solutions involving compartmentalization and spatial self-organization into spiral waves (Szathmáry/Demeter, Boerlijst/Hogeweg). On the experimental side, I'm thinking of Lincoln & Joyce's cross-catalytic RNA enzyme pair showing exponential self-sustained replication, followed by Vaidya et al.'s further work.

Turning to quasispecies theory, I'm noting Eigen's original formulation where selection operates on the mutant distribution, with the stationary state given by the dominant eigenvector of the mutation-selection matrix, later formalized by Eigen, McCaskill, and Schuster, and rigorously proved by Thompson & McBride and Jones, Enns, Rangnekar. I'm also recalling the empirical confirmation from Domingo's work on Qβ.

Moving to Kauffman's work now: Boolean network criticality at K=2, with Derrida-Pomeau's annealed approximation giving the critical condition, and attractor number scaling studies by Bastolla-Parisi and Samuelsson-Troein showing faster-than-power-law growth.

I'm also noting the empirical studies: Shmulevich's PNAS paper on eukaryotic cells being ordered or critical but not chaotic, Nykter's PRL work on macrophage gene expression criticality, and Balleza's PLoS ONE paper examining critical dynamics across four kingdoms.

For the NK fitness landscape question, I'm recalling Kauffman & Weinberger's foundational 1989 paper in J Theor Biol establishing the NK model, along with the key results for K=N-1 (uncorrelated landscapes with 2^N/(N+1) local optima) versus K=0 (single peak), plus Kauffman & Levin's 1987 paper on adaptive walks on rugged landscapes.

I'm also pulling together the rigorous mathematical treatments from Durrett & Limic (2003, Ann Probab) and Kaul & Jacobson (2006, Math Program), alongside the major empirical landscape studies—Weinreich's 2006 Science paper on constrained mutational paths, Szendro et al.'s 2013 review of empirical fitness landscapes, and Kryazhimskiy's 2014 Science paper on global epistasis and predictable adaptation.

Now I'm shifting to Kauffman's 1986 autocatalytic sets paper, which proposes that random chemical reaction systems with polymers undergo a phase transition into a giant connected autocatalytic set once catalytic complexity crosses a threshold, and noting Hordijk & Steel's follow-up formalization.

Also gathering supporting citations like Xavier & Hordijk 2020 on autocatalytic networks, and counterarguments from Lifson 1997, Vasas et al. 2010, and Orgel 2008 questioning metabolism-first scenarios and prebiotic metabolic cycles.

For Kauffman, I'm noting his three key claims: edge-of-chaos/K=2 Boolean networks, NK fitness landscapes, and autocatalytic sets.

Moving to Valiant, I'm tracing his evolvability framework—formalized as restricted PAC learning via statistical queries, where evolvable functions form a subset of SQ-learnable ones and parity functions are proven not evolvable, drawing on both his 2009 J ACM paper and the earlier 2007 MFCS conference version, plus related work by Feldman and Kanade.

I'm also considering his broader "ecorithms" thesis from the 2013 book framing evolution as PAC learning under computational constraints, distinguishing this from his original 1984 PAC learning paper which wasn't biological, and noting his more explicitly neuroscience-oriented work like the neuroidal model and memorization/association studies on realistic neural models.

For c3, there's the ecorithm thesis framing evolution, learning, and cognition as PAC-learning processes, with Feldman 2008 showing evolvability equals correlational SQ learnability — tying back to c1's result that parity isn't evolvable.

Moving to Chaitin next: c1 is his incompleteness theorem via algorithmic information theory, showing no formal system of complexity N can prove a statement about Kolmogorov complexity exceeding N+c, citing his 1974 paper on information-theoretic limits.

Then there's the "metabiology" bridge — Chaitin's claim that evolution is a random walk in software space, with fitness growth bounded by the Busy Beaver function. He argues cumulative random evolution reaches that fitness level in quadratic time versus exponential for exhaustive search, drawing from his 2009 Bull EATCS paper and 2012 book "Proving Darwin."

I'm also tracking the follow-up formalizations: Chaitin's 2011 and 2013 papers refining the proof, plus Hernández-Orozco, Hernández-Quiroz, and Zenil's 2018 Artificial Life work on decidability limits in open-ended evolution, which extends this line of reasoning.

I'm also weighing other candidate claims: the metabiology thesis on open-ended evolution reaching Omega's bits, and the incompleteness-based argument that no fixed formal system can capture biological creativity since complexity bounds can't be proven beyond the system's own limits — essentially Chaitin's view that mathematics itself is too weak to fully formalize biology.

I'll settle on three claims: c1 as the busy-beaver fitness theorem showing cumulative random evolution reaches BB(N) complexity in roughly N-squared time, c2 as Chaitin's 1979 algorithmic definition of life, and c3 as the incompleteness-based claim that no fixed formal system can bound the complexity of what evolution produces, framing evolution as inherently open-ended creativity tied to the Omega fitness variant.

I'm also trying to pin down a DOI for Chaitin's 2009 paper "Evolution of mutating software" in Bull EATCS, but it looks like no DOI exists for that one.

Moving to von Neumann: his universal constructor and self-reproducing automaton work (Theory of Self-Reproducing Automata, 1966, ed. Burks) requires a universal constructor plus a description tape that's both copied and interpreted, anticipating the genotype/phenotype split that Watson-Crick later confirmed biologically. This was proved concretely when Burks completed the 29-state cellular automaton design.

I'm checking minimal replicators like the Lincoln-Joyce RNA system where the molecule serves dual roles without true separation, plus Kriegman's kinematic work. For reliable computation, I'm recalling von Neumann's 1956 multiplexing theorem with majority organs achieving error rates below ~0.0073 per component, cross-referencing Pippenger's noisy gate networks.

I'm also tracing related work on noise limits by Dobrushin-Ortyanov, biological evidence from Winograd-Cowan on reliable computation amid noise, and empirical studies like Faisal et al. on synaptic noise in the nervous system. Then I'm moving to von Neumann's idea of a complexity threshold in cellular automata, below which organisms degenerate and above which synthesis becomes explosive, from his 1949 lectures.

I'll set aside the game theory angle and other von Neumann claims, settling on the three main ones. Then moving to Rosen, I'm noting his (M,R)-systems papers from 1958 in Bulletin of Mathematical Biophysics, with the claim that these systems are closed to efficient causation.

For the formal theorem, I'm tracing Rosen's 1991 "Life Itself," where he argues closure to efficient causation implies non-simulability—organisms can't be reduced to mechanisms since they lack a largest computable model. I'm noting this claim's contested status, along with supporting literature like Louie's 2009 book and the Letelier et al. 2006 paper formalizing (M,R) systems in terms of organizational invariance and metabolic closure.

I'm also recalling the counterarguments: Chu and Ho's 2006 Artificial Life paper challenging Rosen's central proof from a category-theoretic angle, and Mossio, Longo, and Stewart's 2009 attempt to give closure to efficient causation a computable formulation.

I recall Chu & Ho's paper "Against the Possibility of Artificial Life: Robert Rosen's Central Proof Revisited" questioned whether Rosen's proof is actually sound, possibly identifying a flaw in his argument. I should also check Louie's categorical treatment of (M,R) systems and Mossio et al.'s work on computable expressions to verify how the debate actually resolved.

For anticipatory systems, Rosen's 1985 book argues living systems hold internal predictive models and adjust current behavior based on anticipated futures. I can point to concrete empirical tests: Mitchell et al.'s 2009 Nature study on anticipatory lactose-to-maltose shifts in E. coli, and Tagkopoulos, Liu & Tavazoie's 2008 Science paper on predictive behavior in microbial genetic networks.

Now I'm moving to Maturana-Varela's autopoiesis concept—the idea that a living system is a self-producing network of processes that regenerate and constitute itself as a unity in space—citing their 1980 Autopoiesis and Cognition and checking the DOI for the chapter.

I'm also pulling in Bitbol & Luisi 2004 on autopoiesis and cognition, and considering Maturana's claim that life itself is cognition—looking for ways to test that against bacterial chemotaxis evidence versus counterarguments from Barandiaran, Egbert, and Boden. On closure, I'm weighing Varela's operational closure of the nervous system and his 1975 calculus for self-reference as a formal grounding.

I'm also weighing Raichle's default mode network work (PNAS 2001) as supporting evidence, while noting the counterargument from stimulus-driven activity accounts.

I could reference Lettvin, Maturana, McCulloch & Pitts' 1959 frog-vision paper as empirical grounding for Maturana's ideas, and I'm moving on to England's dissipative adaptation framework, citing his 2013 statistical physics of self-replication paper and its formal treatment of heat dissipation in replicators.

I should be careful here since I'm reconstructing this from memory rather than quoting the paper directly, so I'll flag that this is a paraphrase and note it holds only under the idealized assumptions (Markovian dynamics, Crooks fluctuation theorem) used in the original derivation.

I'm also trying to recall relevant empirical work for context: Perunov, Marsland, England's 2016 PRX paper on statistical physics of adaptation, possible connections to Kempes et al.'s work on thermodynamic tradeoffs in bacterial growth, and Lynch & Marinov's work on bioenergetic costs.

Dissipative adaptation theory predicts systems evolve toward states that better absorb and dissipate work from external drives, formalized through transition probability ratios tied to entropy production, with supporting empirical work from Kachman, Owen, England (2017) on chemical search dynamics and Horowitz & England (2017) on self-tuning reaction networks — though I should note the critiques of how broadly this framework applies.

I need to be careful here: the claim isn't universally valid, since it relies on Markovian assumptions, specific initial conditions, and ensemble-level statements, and Jarzynski/Crooks-type inequalities don't automatically imply adaptive behavior occurs. The Perunov paper itself acknowledges these caveats, framing dissipative adaptation as a tendency rather than a strict law.

I should also bring in the broader origin-of-life angle — England's "dissipative adaptation" idea, popularized by Wolchover's Quanta piece suggesting driven matter under light should be expected to self-organize into life-like structures, essentially framing life as a thermodynamically favored outcome rather than an improbable fluke.

I'll settle on c1 as England's self-replication statistical physics paper, c2 as the Perunov formal inequality, and c3 as the broader 2015 dissipative-adaptation conjecture about life's origin, with test cases drawn from Kachman/Horowitz and Boekhoven-style dissipative self-assembly experiments.

Moving to Prigogine: c1 is the minimum entropy production theorem from his 1945/1947 near-equilibrium linear regime work, noting the original French title for verification.

I should note the formal statement—minimizing entropy production under linear Onsager reciprocity constraints—and flag the key limitations identified by Landauer (1975) and Jaynes (1980), who both questioned the theorem's validity outside the linear regime. There's also the biological application in Prigogine & Wiame's 1946 work worth citing.

I'm noting the Brusselator's Hopf and Turing bifurcation conditions, then checking empirical confirmations: the BZ reaction, the CIMA reaction Turing patterns from Castets et al. 1990 and Ouyang & Swinney 1991, and glycolytic oscillations as a biological example.

Against this, I'm weighing that the Brusselator itself isn't a realistic chemical mechanism and its biological extension to "dissipative structures as the origin of order" remains speculative. I'm considering pairing this with Nicolis and Prigogine's order-through-fluctuations principle from their 1977 book, along with minimum entropy production and the Prigogine-Wiame framework.

Then there's the Glansdorff-Prigogine universal evolution criterion from their 1964 Physica paper, which claims a general stability condition for nonequilibrium systems — but I recall this criterion faced serious criticism for not actually being universal, with Keizer and Fox showing its stability claims only hold in limited cases.

I should check these DOIs to confirm titles and validity before continuing.

I see the Eigen & Schuster title confirmed in Crossref as "A principle of natural self-organization" (Part A on hypercycle emergence). The Durrett-Limic DOI isn't working though, so I'll need to search for that one next.

I'm confirming the Durrett-Limic citation and settling on Rosen's Anticipatory Systems, citing it as the 1985 original with the 2012 second edition DOI, noting that the DOI actually points to the reprint rather than the original Pergamon publication.

For Chaitin, I'm using "Life as Evolving Software" (2012) in A Computable Universe to support the metabiology claim, and for von Neumann's self-reproducing automata I'm leaving the source DOI null since the available DOI is only for a review, keeping Pesavento's verified DOI as a proof reference instead.

I still have several more checks to run—Chaitin's 1979 life definition, Valiant's PAC learning, Rosen, Chu & Ho, Mossio, Letelier, Maturana-Varela, England, Prigogine, Kauffman, Nowak, and the Eigen empirical work—so I'll space these out with delays to avoid hitting rate limits.

_Tools used: Shell ×9, UpdateCurrentStep_

_Turn ended: aborted_
