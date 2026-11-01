# Fish life cycle: source and equation layer

Status: proposed, single-operator (Claude Sonnet 5.5 session), unreviewed. Zebrafish (*Danio rerio*) only; it is a model organism, not a flying fish. Nothing here says a living whole-fish bioprint is feasible or infeasible: no source read supports either.

## What this is for
An end-to-end organism design needs, per life stage, growth, maintenance and locomotion, plus the constraints a living printed construct would face (oxygen supply, cell viability, scaffold mechanics and maturation). This layer records which of those have a primary source, a named equation, or measured numbers for zebrafish, and which are **unknown**. `data/fish-lifecycle/assurance.json` is the region-assurance map.

## Sources (8 read; 1 not used)
Each has a full citation, licence note, read level and hash in `data/fish-lifecycle/sources.json`. All quotes are at most 25 words and were checked to occur verbatim in the source text at build time.

| id | source | read | what it gives |
| --- | --- | --- | --- |
| parichy2009 | Parichy et al., Dev Dyn 238:2975-3015 (2009), doi:10.1002/dvdy.22113 | full text (author manuscript; not stored: no licence stated) | stage definitions, size milestones (Table 4), SL-HAA regressions, growth by temperature |
| aman2018 | Aman, Fulbright, Parichy, eLife 7:e37001 (2018) | full text, CC BY | scale (squamation) sequence and Fgf dependence; qualitative |
| daane2018 | Daane et al., Sci Rep 8:10391 (2018) | full text, CC BY | fin regeneration and calcineurin; qualitative |
| mateus2020 | Mateus et al., Cell Rep 30:4292-4302.e7 (2020) | full text, CC BY-NC-ND (not stored) | exponential BMP gradient in the pectoral fin bud, 48-78 hpf |
| stackley2011 | Stackley et al., PLoS One 6:e25652 (2011) | full text, CC BY (text only; per-stage values are in figures not read) | embryo respiration rises linearly 3-48 hpf |
| konadu2023 | Konadu et al., Front Physiol 14:1272366 (2023) | full text, CC BY | oxygen consumption per animal: 5 dpf, larva, adult |
| grimes2014 | Grimes et al., J R Soc Interface 11:20131124 (2014) | full text, CC BY (equations are images: text not read) | diffusion with consumption; diffusion limit in tumour spheroids |
| mukasheva2024 | Mukasheva et al., Front Bioeng Biotechnol 12:1444986 (2024) | full text, CC BY | scaffold pore-size windows by tissue; ranges disagree |

Not used: Loh and Choong 2013 (scaffold porosity): not open access and the PMC record disallows download, so nothing was taken. Kimmel et al. 1995 (embryo stages) is not open access and was not read; Parichy cites it.

## Named equations and parameters
Full list with units, contexts and quotes: `data/fish-lifecycle/equations.json`.

* **Exponential morphogen gradient** (Mateus 2020): `C(s) = C0 exp(-s/lambda)`, BMP-signalling reporter in the zebrafish pectoral fin bud, lambda about 28 um (about 5 cell diameters) at 60 hpf; fits 48-78 hpf and fails after 78 hpf by the authors' account. The authors claim the gradients scale with fin size; the quantitative relation was not extracted here.
* **Steady-state diffusion with constant consumption** (Grimes 2014), `D * Laplacian(C) = a`: setup read in the paper's words; D = 2e-9 m^2/s is *assumed* close to water, a = 7.29 +/- 1.4 e-7 m^3 kg^-1 s^-1 and r_l = 233 +/- 22 um were fitted to DLD1 (human colorectal) spheroids. The paper also states diffusion limits are typically 100-200 um.
* **Diffusion limit**: sphere `r_l = sqrt(6 D C0 / a)`; slab, one-sided supply `L = sqrt(2 D C0 / a)`, supplied from both faces total thickness `2L`. **Derived here** from the stated boundary conditions and verified symbolically in the tests; not copied from the typeset equation.
* **Size indexes development better than age** (Parichy): logistic regressions, all R^2 > 0.5 for size; temperature and density add R^2 < 0.05 after size. **SL = 3.56 HAA + 4.40** (R^2 0.98, HAA > 0.5 mm).
* **Growth rate** (a measured mean, not a law): 0.45 +/- 0.009 mm/day at 24 C, 0.54 +/- 0.011 mm/day at 33 C. No growth law (von Bertalanffy, Gompertz, other) was found in the text read, so none is asserted.
* **Oxygen consumption** (measured, no equation): 5 dpf 126 +/- 4.6 pmol/min/embryo; larvae 0.6-0.9 cm 94.4 +/- 8.3 pmol/min/larva; adult 160 pmol/min/animal.

## Stage and interface JSON
`data/fish-lifecycle/stages.json` (schema `fish-lifecycle-stages-0.1`, connector-local): embryo (to about 72 hpf at 28.5 C), larva, juvenile (entry at SSL 11.0 mm: complete squamation and loss of the larval fin fold), adult (sexual maturity apparent from 17.5 mm SL males, 18.3 mm SL females), each with size milestones (parsed from Parichy Table 4, a dash kept as missing), growth, metabolism, fin and scale events and locomotion, plus an `interfaces` list of exchange quantities with `usable_for` and `not_for`.

## Bounded sizing check (borrowed parameters)
`data/fish-lifecycle/nutrient_diffusion_check.json`. Inverting the paper's own r_l = 233 um gives C0/a = 4.524 s; for a flat solid supplied from both faces that is a total thickness of about **269 um** (244-294 um across the paper's uncertainty on r_l). Zebrafish body height (HAA, Table 4) is 0.52 mm at the MMA milestone, 0.78 mm at pelvic-fin bud (PB) and 2.02 mm at the juvenile entry, i.e. 1.93x to 7.51x that limit.

**This is a sizing aid, not a feasibility statement.** It uses consumption fitted to human tumour spheroids, an assumed diffusion constant, uniform consumption and no perfusion. Real fish tissue is vascularised and its consumption is unknown. It shows the scale of the constraint and why vascularisation, not just printing, is a gap.

## Region assurance (summary)
| process | what exists | status |
| --- | --- | --- |
| staging by size | Parichy Table 4 (larva to juvenile), adult maturity sizes | measured in fish |
| growth rate | two temperature means (larva) | measured in fish; no law |
| fin outgrowth law | BMP gradient 48-78 hpf (embryo); regeneration (adult) | modelled and fit (embryo); qualitative (adult) |
| scale formation | invariant row/column sequence, Fgf dependence | observed, qualitative |
| oxygen consumption | embryo trend, larva, adult | measured in fish; adult value suspect |
| nutrient diffusion constraint | spheroid model | **borrowed, not fish** |
| cell viability in printing | none read | **unknown** |
| scaffold mechanics and maturation | pore-size windows only | **borrowed, not fish; ranges disagree** |
| locomotion | none read | **unknown at every stage** |
| whole-organism bioprint | none | **not claimed** |

## Disagreements and flags kept
* Konadu calls 5 dpf fish embryos; Parichy ends the embryo period at about 72 hpf, so by Parichy they are larvae.
* Parichy's text puts squamation onset at about 8.1 mm SL while Table 4 lists posterior squamation onset at 9.6 SSL (different measures).
* Konadu's adult value (160 pmol/min/animal) is close to the 5 dpf per-animal value although an adult is far heavier: unit or normalisation looks suspect; it is not used for sizing and not resolved.
* Bone scaffold pore windows differ across the cited works (50-700, 100-600, 200-600 um).

## Not done
No locomotion, juvenile or adult growth series, volumetric tissue oxygen consumption, fish-cell viability thresholds, scaffold stiffness or degradation, or quantitative fin and scale growth laws; no flying-fish stage boundaries. Open-access bioprinting viability papers were found by search but not read. No review beyond one operator.

## Rebuild
`PYTHONPATH=. python3 -m engineering.lifecycle.build --noredist <dir with PMC3030279_efetch.xml and PMC7109522_fulltext.xml>`; tests: `python3 -m pytest engineering/lifecycle/tests -q`.
