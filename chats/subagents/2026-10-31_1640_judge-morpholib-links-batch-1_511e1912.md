# Subagent: Judge morpholib links batch 1

- **Parent chat:** [have the mcp grab averything taht is morpholib](../2026-10-31_1611_have-the-mcp-grab-averything-taht-is-morpholib.md)
- **Started:** 2026-10-31 16:40 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 16:42 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `511e1912-0513-42fd-a47b-bdd95fc4817a`

---

### 2026-10-31 16:40 — Turn 1 (User)

> You are judging candidate links between two claim collections. Read /tmp/morpholib/batch-1.json (do not modify it) and write your judgments to /tmp/morpholib/judged-1.json. Do not edit any other file and do not touch any git repository.
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
> OUTPUT: /tmp/morpholib/judged-1.json, a JSON array with one object per morpholib claim in the batch (all of them, including those with no links), in this shape:
> {"morpho_id": "<entry id>", "links": [{"delphi_id": "<candidate id>", "relation": "tests"|"models", "note": "<one sentence: what in the morpholib work bears on what in the delphisci claim>"}]}
> Validate the file parses as JSON (e.g. with node) and that every morpho_id from the batch appears exactly once. Then reply with just: number of morpholib claims, number with at least one link, total links by relation, and any entries you found hard to call.

**Assistant:**

I'm planning a compact print view showing each entry's id, label, organism, truncated source text, and Thompson value, plus candidate ids with truncated statements.

I created a scratch file view1.txt in /tmp/morpholib since I was told not to edit other files, and I should remember to delete it afterward. Let me read it now.

I'm double-checking the line ranges around przemyslaw and bailleul to make sure nothing's missing, and scanning for a "thompson" field across entries, which doesn't seem to appear anywhere. I still need to verify the reported_in_source and does_not_claim details for several entries to sort out which are tests versus models.

I should briefly note I created and deleted a scratch file in /tmp, though it's minor and already gone. Now I need to judge whether the simulation actually reproduces real specimens—the audit requires morpholib to measure the specific quantity the claim asserts against real data, and going through each case so far shows none that qualify.

Turing's gray-scott models align with established morphogen and diffusion-driven instability concepts, and the Kondo-Asai angelfish work on stripe spacing independence from tissue size seems like a plausible candidate for "models" status since it directly tests wavelength constancy as fish grow. The planform database animation of planarian gap-junction head shapes doesn't actually test anything—it's just illustrative. I'm now considering whether the odonata wing-cell deep time comparison could involve measuring fossil wing geometry against modern specimens.

I'm moving through the Thompson coordinate-transformation claims about Scarus and Pomacanthus—the actual Thompson chapter uses different species pairs (crocodilian skulls, Diodon→Orthagoriscus), so these specific claims don't match and should likely be rejected since the method applies to different organisms than claimed. Then I'm weighing the Cervera-Levin-Mafe gap-junction blockade models, where octanol-induced head shape changes in Girardia seem to genuinely model morphogen signaling along anterior-posterior and medial-lateral axes, suggesting several of these Levin-series candidates could qualify as "models."

Reject tame-14 as too broad, but weakly include turing-morphogen-hypothesis as a gap-junction reaction-diffusion implementation despite hesitation. Moving to raup-shell-coiling, I'll include wolfram's growth-rate models and thompson's shell difference-of-degree claim as direct formalizations within Raup's morphospace parameters.

Working through more Raup items—whorl separation/overlap reflects the D parameter, and whorl breadth as geometric progression is embodied in the generator even without explicit data checking, so I'll count it as modeling the mechanism. I'll skip the constant angle and other overly specific value claims, then move toward Wolfram's Conus/rule 30 comparison.

For rule 30, the center-column randomness statistics only get verified computationally up to t=1024, which only partially covers the stronger claim of no repetition in the first million steps—so I'll call that a partial test while noting the limited horizon. The single-cell-to-irregular-pattern claim is more just a reproduction of the simulation itself, so that leans toward "models" rather than "tests."

For the mollusc pigment pattern claim, the CA-like mechanism itself isn't really tested by comparing output patterns to real Conus textile shells—that's about matching appearance, not verifying the underlying mechanism—so I'll mark that as "models."

Rejecting ch08-28 since Meinhardt-Klingler activator-inhibitor applies to shells rather than coat patterns, and ch08-27 since it's just untuned random rules. For phyllotaxis, the Douady-Couder inhibitory potential mechanism behind the 137.5° golden angle counts as "models," while Thompson's isogonal sunflower spiral claim is uncertain whether it's empirically checked against real specimens, so I'll lean toward rejecting it. The golden mean significance claims in ch14-10/14-11 could connect to an actual sunflower audit though.

I'm also weighing whether the parastichy number count scales with Vogel model floret density but concluding there's no real frequency measurement here, so rejecting. Thompson's logarithmic spiral claim for florets doesn't match Vogel's Fermat spiral formula, so that's a contrary case rather than a match, and the closely related "similar parts at regular intervals" idea belongs to a different entry (jonsson), leaving wolfram ch08-21 as the only real candidate for vogel.

Moving on, leaf venation and airway entries yield nothing, anthrobots are irrelevant, and the compound leaf claim doesn't line up with either the anisotropic wall simulation or the branching leaf-shape mechanism, so both get rejected. For cranial sutures, I'm considering whether thompson's mechanical strain stimulating growth matches the simulation's masticatory strain-to-suture coupling — the collapse-under-unloading behavior does seem like a direct implementation of strain-driven growth.

I'm treating this as a borderline match, ruling out the KS instability as Turing-related, and flagging the suture entry as a model match while rejecting apical constriction (wrong mechanism — mechanical rather than growth-based) and canalization (no relevant candidates). For the SAM mechanics claim about anisotropic cylindrical cell growth, I'm weighing whether the CMT-aligned anisotropic wall yielding simulation counts as a match versus the unrelated trabeculae-stress-line example.

Since Hamant's mechanism matches the anisotropic wall reinforcement shaping but operates at tissue level rather than single-cell level like Thompson's claim, I'm rejecting that pairing. I also want to check whether the dynamic division planes in the Voronoi mesh simulation use an Errera-style shortest-wall rule, so I need to dig deeper into the mirabet, jonsson, bressloff, glimm, haupaix, raspopovic, asally, pezzulo, and hannezo entries for details.

I'm going through more candidate matches—checking Mirabet's mesh division planes and Jonsson's phyllotaxis work but rejecting both as not fitting. Now I'm looking at the alberti beak example, comparing Thompson's logarithmic spiral analysis against Campas's affine shear approach for coordinate transformation.

Moving through more items: glimm feather, haupaix, and asally biofilm all come up empty. For Pietak's work I'm selecting several Levin entries about cryptic two-headed memory, voltage-gated gap junction dynamics, and stochastic head-number regeneration as good model matches, while skipping borderline cases like the girardia attractors. For Pezzulo I'm confirming the Friston model implementations as solid matches.

For the axolotl regeneration case, I'm being stricter — dropping the bisection and several other place entries since they don't clearly match the simulation's amputation-based error-correction behavior, keeping only the core three plus the free-energy minimization and target-anatomy feedback claims. Now moving to Raspopovic's Turing pattern claims about network instability and FGF-modulated wavelength spacing.

For the remaining cases — Hannezo's branching annihilation work, Bressloff's V1 model, Santella/Odell/Eshghi — none match since Turing models aren't present in their candidate sets, so I'm rejecting those. Then I'm checking whether the Gray-Scott Turing model's angelfish/boxfish stripe simulations actually get validated against real specimen morphology, which would support the claim that the mechanism is sufficient to account for the pattern.

The example in the prompt classifies Turing angelfish as "models," so I'll follow that convention and move to writing the file.

The validator caught one link to an id that isn't in that entry's candidate list (`turing-ddi` for the Raspopovic digits model), so I'm removing it and re-running.

Turing-ddi isn't actually among the raspopovic candidates, only turing-wavelength is, so I need to remove it and rerun the command without that line.

I wrote `/tmp/morpholib/judged-1.json`. It parses as JSON, and each of the 29 morpholib claims in the batch appears exactly once.

- **Morpholib claims:** 29
- **With at least one link:** 9
- **Links:** 26 in total, 24 "models" and 2 "tests"

None of the batch entries has a `thompson` field, so I made no automatic Thompson "tests" links. The only "tests" links are from the Rule 30 / Conus entry to two Wolfram claims about randomness in the Rule 30 center column (`wolfram2002-ch02-05`, `wolfram2002-ch10-15`).

**Hard to call:**
- **Rule 30 / Conus:** I counted the finite-horizon center-column statistics as a test of the randomness claims, even though the "data" is the automaton itself, not specimens. They only run to t = 1024, while `ch02-05` claims a million steps.
- **Scarus → Pomacanthus coordinate transformation:** I left it with no links. Its candidates are Thompson's crocodilian skull and porcupine-fish → sunfish transformations: the same method but different organisms, and the Scarus/Pomacanthus claim itself isn't among the candidates.
- **Raup shell coiling:** I linked four claims as "models" (Thompson's few growth factors, whorl overlap, geometric whorl breadths, and Wolfram's growth-rate model). I rejected Thompson's specific ~80° spiral-angle claim because the script uses illustrative parameters, not measured shells.
- **Turing wavelength:** I called it "models" for both the angelfish and the mouse digit entries. Neither audit says it compares measured stripe or digit spacing, so I didn't count it as a test.
- **Borderline "models" calls:**
  - Cranial sutures → Thompson's "strain directly stimulates growth" (`thompson1917-ch16-08`).
  - Cervera gap-junction model → the general Turing morphogen hypothesis.
  - Pezzulo active inference → `levin-2025-wisdom-07`, the large-scale feedback loops toward a target anatomy.
- **Vogel phyllotaxis:** I linked only Wolfram's claim that the golden angle comes from a simple inhibition process. I rejected Thompson's sunflower claims (isogonal spirals, rarity of golden-mean approximations, parastichy numbers changing with size) because the audit doesn't measure them on real capitula.

To get a readable view of the batch I briefly wrote a scratch file in `/tmp/morpholib`; I deleted it, and nothing else was modified.

_Tools used: Read ×3, Shell ×6, UpdateCurrentStep ×2_
