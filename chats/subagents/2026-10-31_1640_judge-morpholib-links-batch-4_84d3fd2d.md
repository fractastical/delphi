# Subagent: Judge morpholib links batch 4

- **Parent chat:** [have the mcp grab averything taht is morpholib](../2026-10-31_1611_have-the-mcp-grab-averything-taht-is-morpholib.md)
- **Started:** 2026-10-31 16:40 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 16:42 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `84d3fd2d-2c71-4c99-96e6-3e2a42451231`

---

### 2026-10-31 16:40 — Turn 1 (User)

> You are judging candidate links between two claim collections. Read /tmp/morpholib/batch-4.json (do not modify it) and write your judgments to /tmp/morpholib/judged-4.json. Do not edit any other file and do not touch any git repository.
> 
> BACKGROUND
> - Each entry in the batch is a MorphoEval ("morpholib") claim: a simulation script in github.com/fractastical/morpholib implementing a published model (fields: label, organism, reported_in_source = what the source papers reported, does_not_claim, papers, thompson = if present, the specific D'Arcy Thompson 1917 claim the audit tests). Its verdict/score is an audit of whether the simulation faithfully reproduces real specimens.
> - Each entry has `candidates`: delphisci claims (id, label, statement, notation) from Darwin's Origin, Thompson's On Growth and Form, Wolfram's NKS, Michael Levin's papers, and math-biology (Turing, Fisher, etc). These were preselected by TF-IDF text similarity, so many are spurious.
> 
> TASK
> For each morpholib claim, keep only candidates where the morpholib work genuinely bears on the delphisci claim's specific assertion, with one relation:
> - "tests": the morpholib audit measures or checks, on real specimens or data, the very quantity/pattern the delphisci claim asserts (e.g. delphisci says spiral shells are logarithmic spirals; morpholib fits log spirals to real Nautilus shells). A morpholib claim with a `thompson` field is a test of that Thompson claim; link it as "tests" to the delphisci Thompson claim(s) that say the same thing.
> - "models": the morpholib simulation implements the mechanism the delphisci claim proposes (or a direct formalisation of it), but does not check the delphisci claim's specific assertion against data (e.g. delphisci says a Turing activator-inhibitor mechanism makes stripes; morpholib runs a Turing model of angelfish stripes).
> Reject: shared topic only (both about leaves, both about shells), shared words, or the delphisci claim being about a different question on the same organism. Be strict: most candidates should be rejected, and many morpholib claims will have zero links. Do not invent ids that are not in that entry's candidates list.
> 
> OUTPUT: /tmp/morpholib/judged-4.json, a JSON array with one object per morpholib claim in the batch (all of them, including those with no links), in this shape:
> {"morpho_id": "<entry id>", "links": [{"delphi_id": "<candidate id>", "relation": "tests"|"models", "note": "<one sentence: what in the morpholib work bears on what in the delphisci claim>"}]}
> Validate the file parses as JSON (e.g. with node) and that every morpho_id from the batch appears exactly once. Then reply with just: number of morpholib claims, number with at least one link, total links by relation, and any entries you found hard to call.

**Assistant:**

I'm checking each candidate entry against the source material—papilio colour adaptation doesn't hold up, pavement cell shapes don't match the fluting or 120° examples well enough, and coral also seems to lack a solid link, so I'm rejecting these so far while continuing through the list.

For stromatolite spacing, the diffusion-based mechanism differs enough from Turing dynamics that I'll reject it too. Physarum's surface tension taxes don't fit either. For the planarian work, Beane's ivermectin-induced double-head result seems like a plausible match for the bioelectric model claim, but the voltage-as-instructive-variable claim is too specific to the pump-swapping experiment, so I'll reject that one while keeping the agential model link. Kondo's work fits well with both the morphogen hypothesis and reaction-diffusion models, so I'll accept those.

Willshaw has no match here. For Sharon's leaf waves, Thompson's chapter on folds from differential growth rates seems related mechanistically—buckling from unequal expansion—but that example is about blastoderm folding, not leaf edges specifically, so I'm weighing whether the general principle still counts or if it's too strict a mismatch to credit.

For Romanesco, the phyllotaxis claims reiterate spiral arrangement but don't test angular precision, so I'm rejecting those matches. Grieneisen has nothing. For the wasp comb, Thompson attributes hexagonal geometry to surface tension on semi-fluid wax rather than design, while the modern claim is about stigmergic building behavior—a different mechanism—so I need to check the full entry details, including whether Darwin's claim about wax economy might actually align with a "shared-wall pulp economy" argument. Somitoid has nothing. For sponge spicules, Thompson attributes form to external physical forces rather than chemistry, while the modern explanation invokes silicatein filaments with crystallographic control.

For tendrils, Thompson's explanation involves unequal growth and circumnutation, which explicitly excludes the newer intrinsic-curvature mechanism from differential growth or fiber overwinding, so I'm rejecting that match. The termite case doesn't hold up either since the modern mechanism isn't really reaction-diffusion morphogen patterning in tissue. The Hentschel limb case does work with Turing-type morphogen models. For the lung, Thompson's Laplace wall stress relates to a different claim about vessel thickness, so that's a reject too. I still need to check the remaining entries and look at full details for the null cases.

I should check the full content of the null-REP entries like papilio, wasp comb, termite, vibrio, and sponge, along with any Thompson fields, printing all keys except candidates.

I don't see any Thompson fields present. I've covered about 25 of the 29 entries, so I should double-check the remaining ones by listing their ids, and also revisit the angiogenesis entry since its candidate list got cut off.

No angiogenesis to address here. On Murray's law, I'm connecting it to Thompson's principle of vessels arranged for minimal effort and wall surface—it's essentially the direct mathematical formalization of minimizing pumping work plus volume cost. I need to check whether the audit actually tests this against real retinal data, since the claim of "faithfully reproducing human retinal network" structure needs scrutiny—it's likely comparing against retinal bifurcation patterns without independent morphometric confirmation of some details.

I'm working through whether Murray's 1926 branching-angle optimum and Roux's rules about small branches at large angles should both be labeled "models," given the uncertainty about actual data comparisons—Murray's angle theory does predict near-90° angles for small branches, which aligns with Zamir/Sherman retinal measurements, so I'll lean toward "models" for all three while flagging this as uncertain. Then shifting to the wasp comb example, Thompson attributes the hexagonal geometry to surface tension in semi-fluid wax rather than deliberate insect design, which competes with the stigmergic building-rule explanation as the behavioral alternative mechanism.

I'm now weighing Darwin's claim that comb is maximally economical of wax against a model computing material savings from shared hexagonal walls—since Darwin's claim concerns honeybee wax while this concerns wasp pulp, I'm leaning toward rejecting the match due to the organism mismatch, though I'll note it as a borderline case. Similarly, the 120°-wall-junction claim for hexagonal combs seems too broadly stated to count as a real test, and there are no matches for the Bi vertex or Vibrio cases. For Tozluoglu, though, I'm confident that Thompson's idea of folds arising from local differences in sheet growth rate maps directly onto differential growth positioning folds in planar epithelial tissue, so that one counts as "models," while the more general external-form-from-growth-ratio claim is too vague to count.

I'm now considering Sharon's leaf-wave work alongside Tozluoglu—both implement the same mechanism of unequal growth in an initially uniform sheet producing folds, so despite Thompson's claim being specifically about blastoderm, I'll link both as valid implementations, flagging the match as a harder case given the organism and context differences. Moving on to hair follicle spacing, I'm thinking through how the Turing wavelength and morphogen hypothesis ideas connect to the WNT/DKK reaction-diffusion pair setting follicle spacing.

I'm checking whether Dkk1 overexpression data, which reduces follicle numbers through parameter changes, counts as testing or just modeling, and I'll keep it under models since it's a simulation match rather than a direct data comparison. For Kondo's stripe-insertion work, I'm confirming turing-ddi and the morphogen hypothesis apply as models, noting turing-wavelength isn't among the candidate concepts for this one despite the clear wavelength-constancy-during-growth phenomenon being demonstrated. Then I shift to Nakamasu's work on animal coat patterns, linking it to the short-range activation and long-range inhibition framework from Wolfram's chapter on local activation and longer-range suppression.

Moving through Hentschel, I'm again assigning turing-ddi and turing-morphogen-hypothesis as the relevant models. For Hubaud, I'm recalling the 2017 finding that isolated presomitic mesoderm cells fail to oscillate at low density due to excitable YAP gating, while collective behavior at high density restores oscillation -- this directly supports the Levin 2024 claim about collective dynamics being necessary for the segmentation clock, so I'm marking it as a model match. Now I'm working through the Bischof Picasso references, mapping them to several Levin papers on taming, gluing, boundaries, and wisdom/feedback loops, including the scrambled-face example and the idea that closed-loop goal-directed systems reduce error compared to open-loop ones, while also noting that Morpholib's craniofacial landmark tracking traces back to Vandenberg 2012.

The claim asserts cell collectives pursue target morphologies, and the morpholib simulation directly implements that goal-directed process for Picasso-style faces, so that leans toward "models" rather than "tests".

For Kriegman's xenobot work, morpholib similarly implements the AFPO phase-randomization voxel pipeline and the dorsal inversion locomotion collapse scenario as simulations of the claim rather than independent tests of it, so those also count as models.

I continue sorting other xenobot claims: self-repair after mechanical laceration models, kinematic self-replication from glue-17 models, but hydrodynamics-matching gaits is only partially covered since morpholib doesn't claim full hydrodynamics, and several interpretive claims about shape-based transfer or spontaneous contractions get skipped as not implemented. For Beane, agential-12 also models the claim.

For Physarum, I reject the glue-01 reference since adaptive network morphology there addresses a different question. Petroff, Forterre, and Pringle's Romanesco work have no matching claims, so I'm ready to write the file now.

I judged all 29 MorphoEval claims and wrote the results to `/tmp/morpholib/judged-4.json`. The file parses as JSON, lists every claim from the batch exactly once and uses only ids from each claim's own candidate list.

- **Morpholib claims:** 29
- **With at least one link:** 11
- **Links by relation:** 24 "models", 0 "tests". No entry in this batch has a `thompson` field. For the rest, I couldn't confirm that an audit checks the delphisci claim's exact assertion against data.

**Hard to call:**
- **Murray vascular cube law:** I linked three Thompson blood-vessel claims as "models": minimum effort and wall surface (ch15-13), the cos x = L/L′ branching angle (ch15-15) and Roux's rules (ch15-14). If the audit fits angles to real retinal bifurcations, the last two could count as "tests".
- **Picasso tadpole (`bischof`):** this one tracks craniofacial landmarks against Vandenberg et al. (2012). I linked the "scrambled faces become normal frogs" claims (tame-12, glue-18) and two broader ones as "models". It could be "tests" if the audit counts as checking real specimens.
- **Thompson ch03-03 (folds come from unequal growth in a uniform sheet):** I linked it as "models" to both the wing-disc folding and the lettuce leaf-edge claims. Thompson's statement is about blastoderm folds, so a stricter reading would drop the leaf-edge link.
- **Rejected despite overlap:**
  - **Wasp comb:** Thompson ch07-12 says surface tension shapes combs. The wasp-comb simulation uses a behavioural building rule instead, and Darwin's claim that combs economise wax maximally is about hive-bee wax, not wasp paper pulp.
  - **Sponge spicules:** Uriz's crystal-templating idea contradicts Thompson ch09-09 (spicule form comes from external forces) rather than modelling it.
  - **Tendrils:** Thompson ch13-10 explains twining by circumnutation, which the tendril audit says it does not cover.
  - **Planarian bioelectricity:** Levin's octanol / *G. dorotocephala* head-shape claims are a different experiment from Beane's H,K-ATPase head-polarity switch.

_Tools used: Read ×3, Shell ×4, UpdateCurrentStep ×3, Write_
