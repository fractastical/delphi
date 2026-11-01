# Subagent: Judge morpholib links batch 2

- **Parent chat:** [have the mcp grab averything taht is morpholib](../2026-10-31_1611_have-the-mcp-grab-averything-taht-is-morpholib.md)
- **Started:** 2026-10-31 16:40 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 16:41 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `3c91422c-3e15-4a7a-829c-2a45954df925`

---

### 2026-10-31 16:40 — Turn 1 (User)

> You are judging candidate links between two claim collections. Read /tmp/morpholib/batch-2.json (do not modify it) and write your judgments to /tmp/morpholib/judged-2.json. Do not edit any other file and do not touch any git repository.
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
> OUTPUT: /tmp/morpholib/judged-2.json, a JSON array with one object per morpholib claim in the batch (all of them, including those with no links), in this shape:
> {"morpho_id": "<entry id>", "links": [{"delphi_id": "<candidate id>", "relation": "tests"|"models", "note": "<one sentence: what in the morpholib work bears on what in the delphisci claim>"}]}
> Validate the file parses as JSON (e.g. with node) and that every morpho_id from the batch appears exactly once. Then reply with just: number of morpholib claims, number with at least one link, total links by relation, and any entries you found hard to call.

**Assistant:**

Let me keep reading to check whether Thompson's fields appear more fully elsewhere, since the first instance didn't include them.

I haven't found a thompson field yet, so I should keep scanning the remaining entries to check for one.

I'm counting through the list of names and confirm 29 entries total, with no Thompson reference appearing among them.

Now I need to double-check the Thompson field presence and does_not_claim status, plus verify the full reported_in_source details for the ambiguous entries: caleo, richman, shyer, painter, steinberg, graner, and farhadifar.

Going through each candidate now—the Nijhout eyespot case doesn't match since it's about evolved NCA mechanisms producing French flag patterns rather than the models in question, so I'm ruling it out. Moving on to check the Caleo Cajal dendritic candidate against Rall's work.

For the 3/2 power law comparison, I reject it since this is diameter conservation while the other reference is about tree trunk diameter versus height—superficially similar but different laws. The blood vessel minimum-effort principle is a closer call since it shares optimization logic with Cajal's minimum wiring for dendrites, but since the claim is specifically about blood vessels I'm rejecting that match too.

For feugier canalization, there's no real connection to leaf branching patterns, so that's a zero as well. The graner CPM cell sorting case looks more promising though—there's a genuine match with the surface-tension-driven minimal-area model of cell aggregates, so I'm checking whether this simulation actually implements that principle in a way that would satisfy the audit.

I'm now weighing whether to also link the more generic surface-tension-at-cell-boundary references, but since those are too broad I'll stick with just the one specific match. Moving to the painter case, the Turing reaction-diffusion model for angelfish stripes is a clean match since it's explicitly modeling local activation and long-range inhibition, so I'll include that. The clock-and-wavefront and coral septa cases don't hold up under scrutiny—Cooke-Zeeman is kinematic rather than collective, and the coral fossula doesn't actually reflect septal partitioning the way the claim requires, so both get rejected.

For gyrification, I'm debating whether differential growth rate claims for the blastoderm really transfer to cortical folding—since Richman's mechanism is about cortical plate vs. subcortex growth rather than a uniform sheet, I'll reject that link too. Karbowski and Ermentrout spirals don't have viable connections either, so those are zeroed out, and now I'm checking the stereom spicule case against claims about external forces shaping calcite structure.

For riedel, I'm weighing whether Kuramoto coupling in the segmentation clock really matches the claim that individual cells can't oscillate alone—in Kuramoto models cells still oscillate individually but lose synchrony without coupling, so the entrainment-via-coupling mechanism partially overlaps but isn't a clean match.

Given the ambiguity against the Hubaud excitable-dynamics framing, I'll decide to reject this one despite the close conceptual overlap.

For the diatom case, Sumper's phase separation model is strikingly similar to Thompson's vesicle-froth mechanism — silica precipitates in the gaps between hexagonally packed polyamine droplets, forming the lattice shell pattern.

Moving to Honda's tree branching model: since Wolfram's 137.5° rule just uses the angle as a parameter without modeling the underlying inhibition process, I'll reject that pairing, but Honda's recursive dichotomous branching does look like a direct match to Wolfram's substitution growth rules for plant branching.

Checking the other candidates for Honda, none fit well — leaf-shape derivations and overly general claims about genetic programs don't apply. Thompson's point that lengthening an axis affects leaf exposure more than divergence angle is tangentially related to Honda & Fisher's optimization of branching angles for leaf exposure, but since Honda's model is about tree branching rather than phyllotactic divergence, I'll reject this connection too.

Moving to Steinberg's differential adhesion hypothesis, I'm checking Thompson's discussions of physical laws shaping egg segmentation and surface tension at cell boundaries — none of these directly address sorting behavior from adhesion differences, so I'm coming up empty there as well. For Brodland's differential interfacial tension hypothesis, Thompson's note that surface tension at a cell boundary depends on what it contacts seems like the closest match, since DITH similarly ties interfacial tension to cortical tension and neighbor adhesion governing sorting and form — though Thompson's framing is about a single cell rather than multicellular sorting.

Weighing consistency with how I handled Graner's model, I'm deciding whether to include this same Thompson reference for Brodland's DITH since both decompose tension by contact type, and leaning toward including it as a weak but defensible link.

For the ventral furrow question, I'm concluding it's active constriction forces rather than differential growth, so it doesn't satisfy the test and gets rejected. Moving on to check Farhadifar's model against hexagonal cell packing patterns.

Regular hexagons only hold when cells are equal-sized with uniform tensions—otherwise Lewis's law describes how cell area relates to polygon side count as sizes vary. I'm uncertain whether the audit compares this to real specimen micrographs or just to vertex-model simulations, so I'll classify it under "models" to be safe.

Checking the remaining candidates: pentaradial symmetry, coccolith, and the hexactinellid sections all turn up zero relevant matches. For the villi formation case, I'm rejecting it across multiple chapters since Shyer's mechanism involves muscle-driven folding rather than differential growth or surface-to-volume scaling, and the morphology library only prescribes the muscle geometry rather than testing it against the gut tube's geodesics.

Moving on, trushko's cyst work doesn't match — different meaning of cysts entirely. For lauschke, I'm weighing whether the ex vivo presomitic mesoderm scaling result counts as a test of collective behavior or fixed-length-scale hierarchical development claims, but it doesn't directly address either assertion, so I'm rejecting both pairings. Now checking baker's bistable model against the collective development framework.

Moving to Lewis's 2003 delayed autorepression model with Delta-Notch coupling for synchronization — this is cell-autonomous, so it doesn't fit either comparison and gets rejected; dubrulle also yields nothing. For wolpert, I'm examining whether the positional gradient model counts as a Turing-type reaction-diffusion mechanism — Wolpert explicitly distances himself from Turing periodicity, but his morphogen is still a diffusing synthesis-degradation gradient, so I'm weighing whether that partially satisfies the general morphogen hypothesis versus the specific Turing self-organization claim.

Checking Levin's French flag model in neural cellular automata — different mechanism than Turing, so reject. Richman's wavelength is set by mechanical thickness and moduli rather than Turing dynamics, so that's a reject too. Ermentrout's Fisher-KPP wave model doesn't apply here, and Painter's domain-growth stripe-doubling scenario would relate to Turing wavelength conservation but isn't among the candidates being matched, so nothing to record there either. Time to write these conclusions to the file.

I've written `/tmp/morpholib/judged-2.json`. It parses as JSON and lists each of the 29 morpholib claims exactly once.

- **Morpholib claims:** 29.
- **Claims with at least one link:** 5.
- **Links by relation:** 7 "models" and 0 "tests". No entry in this batch has a `thompson` field, and none of the audits checks a delphisci claim's own assertion against specimen data.

The seven links:
- **Graner cell sorting** models `thompson1917-ch07-01` (cell aggregates shaped by surface tension) and `thompson1917-ch01-06` (surface tension depends on what the cell touches).
- **Painter stripes** models `turing-morphogen-hypothesis` and `wolfram2002-ch08-28` (local activation with longer-range inhibition).
- **Sumper diatom** models `thompson1917-ch09-14` (silica collecting between packed vesicles).
- **Brodland interfacial tension** models `thompson1917-ch01-06`.
- **Farhadifar vertex model** models `thompson1917-ch07-08` (hexagons are regular only with equal cells and uniform forces).

Hard calls:
- **Sumper diatom → `thompson1917-ch09-14`:** kept. Silica depositing between close-packed droplets is essentially Thompson's mechanism, but his claim is about radiolarians, not diatoms.
- **Farhadifar → `thompson1917-ch07-08`:** kept as "models". It might be "tests" if the audit counts polygon sides on the real micrograph, but the batch doesn't say. That micrograph is mouse tissue, not fly.
- **Brodland and Graner → `thompson1917-ch01-06`:** kept, though Thompson's claim is about a single free cell such as an amoeba rather than tissue sorting.
- **Riedel Delta-Notch → `levin-2024-collective-11` (segmentation clock needs a cell collective):** rejected. The Kuramoto coupling does model entrainment, but it assumes each cell oscillates on its own, which is what the Levin claim denies.
- **Richman cortical folding → `thompson1917-ch03-03` and `ch02-12`:** rejected. Folding by differential growth is close to Thompson's mechanism, but his claims are about blastoderm folds and how surface area keeps pace with volume.
- **Caleo dendrites → `thompson1917-ch02-02` and `ch15-13`:** rejected. Rall's 3/2 law is a different 3/2 law from Thompson's trunk scaling, and the minimum-cost claim is about blood vessels.
- **Shyer gut villi → `thompson1917-ch02-12` and `ch10-04`:** rejected.
- **Lauschke somite scaling → `wolfram2002-ch08-23`:** rejected. The result arguably counts against Wolfram's fixed length scale but doesn't test his claim about hierarchical development.

_Tools used: Read ×3, Shell ×3, UpdateCurrentStep ×2_
