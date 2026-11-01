# Subagent: Repository: /Users/jdietz/Documents/GitHub/dev/delphisci. This is a bibliographi

- **Parent chat:** [let's do the same thing for mike levin's works that we did for darwin and thomps](../2026-10-31_1314_let-s-do-the-same-thing-for-mike-levin-s-works-that-we-did-f.md)
- **Started:** 2026-10-31 13:26 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:28 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `7ff5ffd1-99d7-44b5-9e19-a5b2197a4698`

---

### 2026-10-31 13:26 — Turn 1 (User)

> Repository: /Users/jdietz/Documents/GitHub/dev/delphisci. This is a bibliographic task: recording the published scientific claims of a peer-reviewed open-access (CC BY) cell-biology paper so they can later be checked against public datasets. Read /Users/jdietz/Documents/GitHub/dev/delphisci/books/levin-papers/extraction/INSTRUCTIONS.md fully and follow it exactly.
> 
> Your assigned paper: `2024-anthrobots` (Gumuskaya et al. 2024, Motile Living Biobots Self-Construct from Adult Human Somatic Progenitor Seed Cells, Advanced Science; about 14,000 words). File: books/levin-papers/inputs/2024-anthrobots.txt. Read the whole file (in chunks). Focus on the paper's findings and interpretations; skip protocol detail as the instructions say.
> 
> Output file: /Users/jdietz/Documents/GitHub/dev/delphisci/books/levin-papers/extraction/C-2024-anthrobots.json
> 
> Do not write or edit any other file. Do not read other files under books/levin-papers/extraction/ except INSTRUCTIONS.md. Report back the output path, the number of claims, and any unverified quotes.

**Assistant:**

Writing the claims file now.

I'm aiming for around 15-20 claims drawn from the main text, and I need to copy quotes exactly, watching out for special characters like hyphens. I'll verify containment with a script once I draft the claims, starting with the idea of self-construction from a single adult cell.

Next, I'm noting the claim about plasticity in adult human cells not being restricted to amphibian or embryonic systems, which reads as an empirical generalization. Then I'm capturing the finding that culturing in a low-viscosity environment induces a polarity switch, pushing cilia outward and triggering motility by day 7, with spheroids becoming motile after showing none at day 0.

I'm also flagging the hedged mechanistic hypothesis that lower viscosity may prompt basal layer cells to migrate inward while apical cells take over the cortex, as well as the result that higher viscosity decreases both motility and size, suggesting low-viscosity conditions favor larger, more functional bots. Finally I'm noting that seeding density serves as another control knob for modulating bot size and maturation timeline.

Continuing through the results, I see the sigmoidal motility profile peaking around day 10, the ciliobrevin experiment confirming motility is cilia-driven since blocking cilia sharply reduced movement, and the unsupervised clustering analysis that identified four statistically distinct movement types.

I'm noting that the clustering reveals circular, linear, curvilinear, and "eclectic" as the four movement types, and the Markov transition analysis shows these types are stable with low inter-type conversion rates, suggesting each bot has its own distinct motility fingerprint. Circular motion emerges as the most stable pattern, followed by linear/curvilinear, while eclectic movement behaves more transiently.

For morphotypes, I want to use the summary showing three major morphotypes organized by a developmental decision tree where the first split is based on size and shape, with size and smoothness being the top distinguishing characteristics.

Type 2 bots are significantly more ciliated than types 1 and 3, while type 3 bots show a significantly more polarized cilia distribution with the least extra-cluster noise compared to the other two. On size and shape, type 1 bots are smaller and smoother/more spherical, type 2 bots are the largest and least uniformly shaped, and type 3 falls somewhere in between.

I'm weighing whether to add claims about aspect ratio (which doesn't differ significantly across morphotypes) and the statistical correspondence between morphotype and movement patterns, trying to keep the total claim count reasonable for a paper of this length.

Claim 14 explains the proposed mechanism for morphotype 1's lack of movement — the spherical shape with evenly distributed cilia likely causes propulsion forces to cancel each other out radially, resulting in little net motion. Claim 15 touches on the consistency of the morphogenesis process and how final Anthrobot form breaks down into discrete character types.

I'm also noting line 58's finding that linear bots show higher bilateral symmetry, supporting the hypothesis linking movement type to distinct symmetry profiles, and the follow-up interpretation that these synthetic forms may recapitulate some fundamental biological property.

Next, I'm formulating claim 18 about scratch traversal from line 63—that Anthrobots efficiently move across damaged tissue, with bots exhibiting higher rotational tendency or speed achieving greater unique coordinate coverage.

Claim 19 covers the quadratic gyration effect on scratch-trajectory similarity (line 64), noting p=0.006 and the idea that there's an optimal gyration range for maximizing correlation.

Claim 20 addresses superbot gap closure (line 69), describing substantial tissue regrowth within 72 hours of inoculation, forming a stitch beneath the "superbot bridge."

Claim 21 notes the gap closure density was statistically indistinguishable from full (100%) recovery and occurred solely at the superbot inoculation site, distinct from surrounding scratch area.

Claim 22 examines whether passive mechanical contact alone could induce repair, testing agarose loading on neuronal scratches for 4 days, which produced no repair effect.

Claim 23 highlights that Xenobots and Anthrobots, despite vastly different genomes, ages, and tissue origins, converge on similar morphologies, pointing to generic laws of morphogenesis beyond species-specific genetics.

Claim 24 compares behavioral statistics between the two platforms, noting both show low linear-to-circular interconversion rates and strikingly high consistency of circular behavior (95% for Xenobots, 92% for Anthrobots).

Claim 25 notes the unpredictability of trachea-derived cells migrating to heal neural tissue — a result no existing molecular or tissue-level model could have anticipated given these cells' normal physiological roles.

Claim 26 addresses superbot formation: fusion into variably-sized collectives can be controlled by adjusting how many Anthrobots are cultured together, but this fusion is time-limited, occurring only while the basal layer remains exposed following dissolution.

Claim 27 looks forward to personalized, patient-derived Anthrobots that could be deployed safely in vivo without provoking an immune response, since they originate from adult human tissue.

Claim 28 extends the prediction to other ciliated cell sources — like oviductal epithelia or brain ependymal cells — for generating future Anthrobots, with non-ciliated cell types potentially usable when autonomous motility isn't required.

For claim 29, I'm tagging it as historical-inference: the finding that identical genomes can produce diverse morphologies across environments speaks to evolutionary developmental biology, suggesting these morphogenetic competencies could shape how anatomical and functional features evolve.

Claim 30 is a conclusion about correlating specific forms with modes of autonomous motile function, mapping out the discrete character space of form and function.

I'm checking for overlaps — the finding about target morphology not being inferable overlaps with earlier claims, so I'll skip it and let claims 13, 25, and 2 cover that ground, along with lifespan details and apical cilia orientation mechanics already folded into claim 3b. With about 26 claims extracted against a roughly 9,500-word main text, that lands within the target range of 15-30 for a long document, so I'm settling near 24 total, deciding whether to drop the seeding density finding.

Now I need to be careful transcribing the special characters exactly as they appear in the source — the hyphen-like dashes in compound terms, the curly quotation marks around certain phrases, and the apostrophe in "tissues' normal" — before writing out the final JSON.

I'm uncertain about the exact line numbers, like whether the "This may be attributable" reference is on line 51 or 52, so I'll let the verification script check and correct the line numbering.

All quotes are verbatim; some line numbers were off by one and three labels exceed 90 characters. Fixing both.

All quotes are found now, so I just need to fix the line numbers and shorten labels 2, 3, and 11 that exceed 90 characters. I'll write a quick script to auto-set the line numbers from the found positions, then manually trim the long labels.

I extracted 29 claims from `2024-anthrobots` into `/Users/jdietz/Documents/GitHub/dev/delphisci/books/levin-papers/extraction/C-2024-anthrobots.json`. There are no unverified quotes. A script confirmed that the file parses as JSON and that every quote appears verbatim on its recorded line once whitespace is collapsed. It also confirmed every quote is at most 70 words and every label at most 90 characters.

- **Self-construction and plasticity:** a single adult lung cell grows into a motile Anthrobot. The authors interpret this as showing that this kind of plasticity isn't limited to amphibian or embryonic cells.
- **Culture conditions:** low viscosity may cause the spheroids to turn inside out so the cilia face outward. Higher viscosity reduces motility and size. Seeding density works as a control knob, motility starts on a sigmoidal curve peaking around day 10, and ciliobrevin shows the movement is driven by cilia.
- **Behaviour and shape:** there are four movement types, with stable circular motion and transient "eclectic" motion. There are three morphotypes arranged as a decision tree. Non-moving, linear and circular bots map onto morphotypes 1, 2 and 3. Linear movers are more bilaterally symmetric about their direction of travel.
- **Neural scratch assays:** coverage of the scratch depends on rotational tendency and speed, and edge-tracking peaks at an intermediate gyration. Fused bots ("superbots") close the neuronal gap only where they are placed, restoring normal tissue density. An agarose block providing passive mechanical loading does not cause repair.
- **Interpretations and predictions:** the authors compare Anthrobots with Xenobots and argue for generic laws of morphogenesis. They say the neural repair could not have been predicted from current models, and that superbot fusion depends on exposed basal layers. They predict immune-safe personalized bots, bots made from other ciliated cells, and evolutionary implications.

I skipped protocol detail and minor measurements such as lifespan and aspect-ratio equality.

_Tools used: Read ×2, Shell ×2, UpdateCurrentStep ×4, Write_
