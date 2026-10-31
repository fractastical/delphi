# Subagent: Builder B5: neuro, physiology, systems

- **Parent chat:** [Math-meets-biology thinkers, theorem claims as nanopubs](../2026-10-30_1844_math-meets-biology-thinkers-theorem-claims-as-nanopubs.md)
- **Started:** 2026-10-30 18:49 UTC-4 (EDT)
- **Last activity:** 2026-10-30 18:54 UTC-4 (EDT)
- **Final status:** aborted
- **Transcript ID:** `413f3209-5091-4c42-b667-79450c265291`

---

### 2026-10-30 18:49 — Turn 1 (User)

> You are a BUILDER agent in a Project Delphi multi-agent pipeline that evaluates which major thinkers in mathematical biology have claims that are testable and could reach theorem status. Your job is ONLY to extract and document claims precisely. You must NOT score or rank anything (separate assessor agents from other providers do that; builder != assessor).
> 
> Workspace: /Users/jdietz/Documents/GitHub/dev/delphisci/math-bio-theorems
> - Roster: inputs/roster.json — your batch is "B1-evolution-popgen" (10 thinkers).
> - Rubric (for context only, do not score): inputs/rubric.json
> - MorphoEval Lean law index: inputs/morphoeval_math_laws.tsv (columns: law_id, label, source, leanVerified). Grep it for your thinkers (author names, law names) to fill lean_coverage. Note: all entries are flagged leanVerified=true but the Lean proofs may be generic lemmas, so just record matches, don't over-interpret.
> 
> For EACH thinker produce exactly 3 claims: their most central, distinctive mathematical-biology claims (e.g. for Fisher: the Fundamental Theorem of Natural Selection, Fisher–KPP traveling wave speed, Fisher's geometric model / runaway sexual selection or sex-ratio principle). Prefer claims that are well-known and that a researcher would associate with the person. Mix kinds when natural (a proved model theorem, an empirical law, a conjecture/principle).
> 
> Ontology mapping: each claim will become a delphi:TestableHypothesis (subclass of delphi:Hypothesis) with delphi:proposedTest, prov:wasDerivedFrom the source DOI. A claim is a belief, not a fact.
> 
> Write ONE file: claims/B1-evolution-popgen.json with this exact schema:
> {
>   "batch": "B1-evolution-popgen",
>   "builder": {"agent": "builder-B1", "model": "claude-sonnet-5-5-high"},
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
>           "notes": "anything an assessor should know, e.g. disputes about interpretation (Price/Ewens reading of FTNS), or null"
>         }
>       ]
>     }
>   ]
> }
> 
> HARD RULES (from the project's BEST_PRACTICES — no dummy data):
> 1. NEVER fabricate DOIs, citations, studies, or formalizations. For each source_doi, verify it via Crossref: `curl -s "https://api.crossref.org/works/<DOI>" | python3 -c 'import sys,json; m=json.load(sys.stdin)["message"]; print(m["title"], m.get("issued"))'` and confirm the title/year match the work. If you cannot verify, set source_doi to null and doi_verified false (keep the source_citation). You can also search Crossref: `curl -s "https://api.crossref.org/works?query.bibliographic=<url-encoded title author year>&rows=3"`. Many pre-1950 works do have DOIs (e.g. Fisher 1937 Annals of Eugenics 10.1111/j.1469-1809.1937.tb02153.x) — check, don't assume.
> 2. No placeholders (TODO, TBD, example.org, lorem). Every field must be real content or null.
> 3. Be honest about uncertainty and disputes; evidence_against must be substantive.
> 4. Validate the final file parses: `python3 -c "import json;d=json.load(open('claims/B1-evolution-popgen.json'));print(len(d['thinkers']), sum(len(t['claims']) for t in d['thinkers']))"` must print `10 30`.
> 
> Do not edit any other files. When done, reply with: the file path, the count of claims, the number of DOIs verified vs null, and any thinker where you were unsure of the canonical claims.

**Assistant:**

That search was too broad, so I should narrow it down to grep specifically for author names within the source column.

I'm checking for other related terms like Fisher-KPP, traveling wave, Lotka, Price, and drift to see if those also show up in the source.

I'm noting that Lean coverage is essentially absent for my thinkers, though there's a tangential connection via Hannezo's Moran model work—the martingale property of drift frequency matching fixation probability could loosely relate to Kimura's neutral fixation probability of 1/N.

Now I'm selecting claims and tracking down DOIs. For Fisher, I'm weighing the Fundamental Theorem of Natural Selection from the 1930 book (likely no DOI), the Fisher-KPP equation (1937, DOI available), and the sex ratio principle versus the 1918 biometrical genetics paper—leaning toward FTNS, KPP, and sex ratio as the three claims despite the book lacking a clean DOI. For Haldane, I'm starting with the cost of selection/substitution load paper from 1957 Journal of Genetics, which has a solid DOI, and continuing to work out the second claim.

For c3, I'm considering Wright's equilibrium distribution formula for allele frequency under drift, mutation, and selection (1937 PNAS), tying into the adaptive landscape concept. I'll settle on c1 as shifting balance theory citing both 1931 and 1932 papers, with c2 covering the stationary distribution formula.

Then for Hardy-Weinberg, I'm weighing claims: c1 as the one-generation equilibrium result citing Hardy 1908 and Weinberg 1908, and c2 covering the related point about allele frequencies remaining constant absent evolutionary forces, trying to avoid redundancy between the two claims.

I'm trying to pin down the exact citation for Weinberg's work, but I'm uncertain whether it's the 1901 twin differential method or the 1912 ascertainment correction paper, so I should flag this for verification rather than assert it confidently.

I'll settle on Weinberg's twin method and his ascertainment/proband correction for his other two contributions, flagging the DOI uncertainty and noting Hardy and Weinberg's 1908 papers could be split apart. For Kimura, I'm noting the neutral theory paper (Kimura 1968, Nature) establishing substitution rate equals mutation rate under neutrality, alongside his 1962 Genetics paper on fixation probability via diffusion approximation.

For the third Kimura contribution, I'm weighing the Kimura-Crow infinite alleles heterozygosity formula (1964 Genetics) against the two-parameter substitution model (1980 J Mol Evol), deciding the former is a stronger claim and going with the first three papers. Moving to Price, I'm confirming the 1970 Nature paper introducing the Price equation, then considering his 1972 paper on the covariance/selection theorem as the second contribution.

For the third Price reference, I'm weighing several candidates—his 1971 extension of covariance selection mathematics, his connection to group selection or the Maynard Smith-Price ESS work, and his posthumous 1995 "Nature of Selection" paper—trying to settle on which best represents a distinct third contribution.

Moving to Hamilton now: his first claim is clearly Hamilton's rule (rb>c) from 1964, and his second is likely the 1967 extraordinary sex ratios paper introducing local mate competition.

Now I'm weighing options for a third Hamilton contribution — the geometry of the selfish herd (1971), the senescence paper (1966) showing selection force declines with age, or the Red Queen/parasite hypothesis. I'm leaning toward picking one of these well-known mathematical results as the third claim.

For Maynard Smith, I'm outlining his contributions: the ESS concept from Maynard Smith & Price 1973, the Hawk-Dove game with its mixed ESS proportion when cost exceeds value (citing the 1974 J Theor Biol paper), and considering his 1978 work on the cost of sex as a third claim.

I'll settle on c1 ESS from Maynard Smith & Price 1973 with Hawk-Dove as the illustrative model, c2 hitchhiking, c3 the two-fold cost of sex — explaining it as asexual mutants doubling in frequency per generation relative to sexuals when offspring numbers are equal. Moving on to Ewens, c1 is the Ewens sampling formula from his 1972 Theoretical Population Biology paper.

For c2, I'm weighing options: the Ewens-Watterson neutrality test, his 1960s diffusion/pseudo-distribution papers, his Population Genetics book, or possibly his 1969 Nature paper on mean fitness and additive fitnesses.

For c3, I'm leaning toward Ewens' 1989 paper giving an interpretation and proof of the fundamental theorem of natural selection, connecting it to his earlier work on mean fitness increasing under additive fitness.

For c2, the Ewens–Watterson homozygosity test relies on a key fact derivable from the ESF: conditional on the number of distinct alleles k, the frequency distribution is independent of θ, making k a sufficient statistic for θ under neutrality — this traces to Ewens 1972 and Watterson's 1978 Genetics paper on the homozygosity test.

Moving to Kingman, I'm noting his coalescent papers — the 1982 Stochastic Processes and their Applications piece and the companion "On the genealogy of large populations" — establishing that the genealogy of n sampled genes converges to a coalescent process with pairwise merging rates.

For c2, I'm weighing Kingman's 1961 work on mean fitness increasing under selection in multi-allele models, versus his 1978 house-of-cards mutation-selection balance paper, trying to settle on which gives the cleanest citation.

For c3, Kingman's 1982 papers establish the coalescent itself — both the universality result that it's the limit of exchangeable Cannings models with finite offspring variance, and the genealogical partition-valued process description.

I'm also recalling Kingman's 1978 "Random partitions in population genetics" (Proc R Soc Lond A 361:1-20), which establishes that the Ewens sampling formula is the unique partition structure satisfying a sampling consistency / species-sampling property tied to the infinite-alleles model.

I'm trying to pin down other Kingman results I could cite: the 1982 coalescent paper (Stoch Proc Appl), the genealogy universality result showing exchangeable Cannings models converge to the same limiting coalescent, and this 1978 partition structure characterization. I want to make sure I hedge appropriately given uncertainty about exact titles and DOIs before committing to specific citations.

I'm uncertain about the exact Kingman 1961 multilocus result on mean fitness, so I'll reconsider my pairing: keep c3 as Kingman's partition structure characterization of the Ewens sampling formula, and reconsider c2 as possibly the coalescent's expected time to the most recent common ancestor.

Actually, I think a better c2 is Kingman's 1982 exchangeability result showing how variance in offspring number rescales effective population size, which naturally connects to the universality of the Kingman coalescent — and this is empirically testable via cases like highly fecund marine species where multiple-merger (Λ-)coalescents arise instead, per Eldon & Wakeley 2006. So I'll pair c1 as the coalescent's definition and convergence for Wright-Fisher models, with c2 covering this universality claim and its empirical challenge. Now I need to verify the DOIs for these citations.

_Tools used: Shell ×8, UpdateCurrentStep_

_Turn ended: aborted_
