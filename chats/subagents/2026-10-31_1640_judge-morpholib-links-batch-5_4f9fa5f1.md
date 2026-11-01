# Subagent: Judge morpholib links batch 5

- **Parent chat:** [have the mcp grab averything taht is morpholib](../2026-10-31_1611_have-the-mcp-grab-averything-taht-is-morpholib.md)
- **Started:** 2026-10-31 16:40 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 16:42 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `4f9fa5f1-3b8f-4024-8a24-74552cfff905`

---

### 2026-10-31 16:40 — Turn 1 (User)

> You are judging candidate links between two claim collections. Read /tmp/morpholib/batch-5.json (do not modify it) and write your judgments to /tmp/morpholib/judged-5.json. Do not edit any other file and do not touch any git repository.
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
> OUTPUT: /tmp/morpholib/judged-5.json, a JSON array with one object per morpholib claim in the batch (all of them, including those with no links), in this shape:
> {"morpho_id": "<entry id>", "links": [{"delphi_id": "<candidate id>", "relation": "tests"|"models", "note": "<one sentence: what in the morpholib work bears on what in the delphisci claim>"}]}
> Validate the file parses as JSON (e.g. with node) and that every morpho_id from the batch appears exactly once. Then reply with just: number of morpholib claims, number with at least one link, total links by relation, and any entries you found hard to call.

**Assistant:**

I'm trying to figure out whether the zhang-sorting entry connects models studying bubble sort in cell arrays with the competency-based evolutionary search paper, and whether that shared mechanism actually supports the claim that competency accelerates evolutionary search.

For youtube-channel-math, I'm checking whether the gap-junction coupling equation really formalizes Levin's claim about cells sharing sensing information through gap junctions, but it feels like a weak match, so I'm leaning toward rejecting the link.

For the Holstein case, I'm considering whether the audit tests the Turing wavelength hypothesis against real coat pattern data, examining whether the spacing is set by reaction rates rather than tissue size, and tracing which models and chapters this connects to.

Then I move through several 1917 entries, mapping which ones test growth-rate claims, organ-size ratios, plaice k-values, bipolar field lines in asters, and surface tension mechanisms — flagging which links need closer inspection before confirming.

For t1917-018, I'm weighing whether to mark it as testing ch07-04 only, or whether it also models ch07-06's Lami tension-angle balance, since the figure comparing angle versus tension could go either way depending on how strictly "models" is interpreted.

I'm looking at t1917-022 on minimal-area partitions, weighing candidates like the Errera least area wall and ch08-01, but I'm still unsure whether the audit actually measures this—I need more details, so I'll pull up the full entries for 008, 022, and Holstein before continuing.

I want to pull fuller details for a handful of specific entries—Holstein, 008, 019, 022, 040, 041, 057, 033, and youtube-channel-math—printing every field except candidates so I can see the complete picture for each.

Counting through all 26 entries, I confirm the list is complete. Now I'm going through each one deciding whether it needs flagging, starting with zhang and youtube which seem fine as is, though youtube touches on something trickier around gap-junction equations.

For bos, I'm weighing whether the Holstein coat pattern test should count as testing the Turing wavelength prediction or the morphogen hypothesis more broadly — deciding to keep it strict and tie it to the wavelength test and DDI model rather than the broader claim. For 008, I'm noting it tests the plaice weight-length relationships.

For the thompson weight-length claim, I'm deciding whether ch03-17's peak-k observation counts as relevant — it's borderline, so I'll fold in ch03-19, ch03-16, and ch02-01 instead, flagging ch03-17 as uncertain. For 010, I'm matching the "restoration as lawful growth" claim to both ch03-30 and ch03-31 since the latter explicitly ties regeneration to the same growth curve. For 012, I'm linking it only to ch04-02, noting it's unpublished with a null score but still counts as a test.

Moving to 014, I'm testing ch05-10, but rejecting ch12-01 since it explicitly disclaims mechanism even though it geometrically implies a Delaunay form. For 018, I'm linking it to ch07-04, and treating ch07-06 as modeled since the Lami tension-angle balance implements that mechanism, while rejecting the broader ch07-01. Now I'm weighing 019 against ch07-08's claim about regular hexagons only forming with equal cell sizes versus ch07-09's pressed-cell geometry.

I'm leaning toward including ch07-09 since it directly predicts hexagon formation, but I'll stay strict and skip ch07-08 despite corneal endothelium being a classic case, since I'm unsure the audit measures size variance, and I'll also skip ch07-04's angle claim for the same reason. For 022, I'm connecting it to ch08-14's pollen tetrad example within the broader claim about hollow and aggregate structures.

For 022 I'll include ch08-02 on least-area tissue partitions but flag it as uncertain. For 023, otolith structure clearly ties to ch09-04, though I'm skipping the Liesegang rings connection since it's unclear if that matches the claim about non-periodic concentric rings. 024 maps to ch09-10, and 027 connects to the shell geometry chapters—log spirals, whorl breadth progression in Nautilus, and the roughly 80° angle claim.

I'm weighing whether 11-05's shape-invariant growth (the defining property of log spirals) duplicates 11-08 and 11-01 enough to skip it, and leaning toward leaving it out to avoid redundancy. For 028, I'll include ch11-08 for the whorl breadth measurement but skip the septa minimal-surfaces connection to ch11-20 since matching it to the specific claim about septa meeting the shell wall feels too uncertain.

For 029, ch12-05's Fusulina ratio and ch12-04's log spirals both get tested, while ch12-06 is explicitly proven algebraically rather than tested — though the mass-proportional growth model still applies there. For 031, ch13-04's spiral angle comparison across Ovis ammon (~75°) and the Scinde wild goat (<70°) counts as tested since it's directly measuring the species differences shown in the figure.

For 032, I'm weighing whether the mammoth tusk spiral claim (ch13-14) and the teeth log spiral claim (ch13-13) hold up — the teeth claim checks out since it's about unequal accretion producing a spiral, but the tusk claim is shakier since it also asserts elephants share the same spiral pattern, which isn't directly tested.

For 033, I'm looking at parastichy number claims — ch14-05's point about numbers rising with size (like 21/34 to 34/55) matches the cascade measurements, so that tests. The golden-angle rarity claim (ch14-11) doesn't hold against a single sunflower measurement, and the inhibition-process explanation for 137.5° degrees (ch08-21) isn't something the morphological library actually models, so I'm rejecting both of those.

Moving to 034, Thompson's claim that eggs are prolate and never oblate (ch15-01) checks out against the data. The pointed-egg-size claim (ch15-02) isn't directly supported by the Biggins/Deeming data, and testing internal consistency of Thompson's equation (ch15-06) is really a modeling question rather than a data test, so I'm setting that aside along with the cause claim that's explicitly undemonstrated (ch15-05).

For 040, I'm checking whether any claims about related organisms or human/ape skull profiles apply to Dürer's human profile variation — nothing seems to fit cleanly, so I'm leaning toward rejecting all of them here.

Now I'm thinking about the general Cartesian coordinate transformation claim (ch17-04) and whether it should link to the skull and pelvis test cases. Since it's framed as a broad rule with each specific case as an instance, I'll apply it to 051, 054, 055, and 058, but skip it for 040 and 057 since those involve within-species profile and scapula variation rather than cross-species comparisons.

For 055, I'm wrestling with whether the rabbit-from-rhinoceros flexure case counts as testing the geometric claim or the phylogenetic kinship claim — since morphological testing doesn't validate relatedness assertions, I'll reject that link but keep it flagged as a hard case, while still including ch17-04 for the geometric transformation itself. For 058 I'm linking both ch17-16 and ch17-04, and for 057 I'm still working out whether anything applies.

I've written `/tmp/morpholib/judged-5.json`. It parses with node, every `morpho_id` from the batch appears exactly once, and every link uses an id from that entry's own candidates.

- **Morpholib claims:** 26
- **With at least one link:** 22
- **Links:** 37 in total, 33 "tests" and 4 "models"
- **No links:** `zhang-sorting-morphogenesis`, `levin-youtube-channel-math`, `t1917-040` and `t1917-057`

**Hard to call:**
- **`zhang-sorting-morphogenesis`:** I rejected `levin-2023-competency-04` and `levin-2023-goals-16`. One uses bubble-sorting cells and the other is about delayed gratification, but both make claims about different systems: evolutionary search and an evolved neural cellular automaton.
- **`levin-youtube-channel-math`:** I rejected the gap-junction claims such as `levin-2019-boundary-17`. The coupling equation sits next to them, but no organism data is involved, and those claims are qualitative "larger Self" statements rather than the formula.
- **`bos-taurus-turing-wavelength`:** I linked `turing-wavelength` and `wolfram2002-ch08-28` as tests (a negative result) and `turing-ddi` as models. I left out the broad `turing-morphogen-hypothesis`.
- **`t1917-008`:** I linked `ch02-01`, the plaice k = W/L³ check, but not `ch03-17`, the claim that k peaks near maturity. I couldn't tell whether the audit checks the peak.
- **`t1917-014`:** I rejected `ch12-01` (forams as fluid drops) because the audit explicitly disclaims the surface-tension mechanism.
- **`t1917-018`:** I linked `ch07-06` as models, because the Lami balance infers tensions rather than measuring them.
- **`t1917-019`:** I linked `ch07-09` (packed cells form hexagons) but not `ch07-08` (hexagons are regular only where cells are equal) or the 120° claim, since the batch doesn't say those were measured.
- **`t1917-022`:** The batch has no source or scope text, so the link to `ch08-02` (the least-area partition rule) is a guess.
- **`t1917-028`:** I didn't link `ch11-20` (septa as minimal surfaces). A septum overlay exists, but the batch doesn't say it tests that.
- **`t1917-032`:** I rejected `ch13-14`, since it claims elephant and mammoth tusks share one spiral and only a mammoth tusk was measured.
- **`t1917-033`:** I linked only `ch14-05`, the parastichy cascade. I rejected `wolfram2002-ch08-21`, because a Vogel fit is not the inhibition mechanism that claim proposes.
- **Coordinate-transformation entries (`t1917-051`, `054`, `055`, `058`):** I linked the general Cartesian-transformation claim `ch17-04` as tests. I didn't link it for `040` (human profiles) or `057` (human scapulae), because those compare forms within one species rather than related organisms. For `055` I rejected `ch17-13`: the claim is mainly about kinship (rhinoceroses and rabbits), which the audit doesn't test.

_Tools used: Read ×3, Shell ×3, UpdateCurrentStep ×2, Write_
