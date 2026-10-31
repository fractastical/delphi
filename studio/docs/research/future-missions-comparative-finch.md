# Proposed future mission (scoping only): comparative finch beaks

**Owner:** fable-lead · 2026-10-31 · branch `work/frontier-specs` · **single-reader, NOT Codex-reviewed.**
**Status: SCOPING ONLY — a proposed future mission, not scheduled and not built.** No finch simulation,
no Draft records, and no new store writes here. **Gated:** this waits until root has delivered
(reviewed/imported) the flying-fish **source claims and actionable questions** first
(`data/research/frontier-drafts.json`). This card exists so the mission is indexed, not started.

**Read-level of every finch source below: `listing`** — bibliographic leads supplied by the user; the
primaries were **not read** in this bounded scope. Nothing here asserts a finding; topics are stated as
leads to be verified on read. No fabricated results.

## First, the distinction the user flagged — do not conflate

- **Darwin's finches** = Galápagos ground/tree finches (*Geospiza* and relatives); the **adaptive-radiation,
  beak shape/size** system. **This mission is about these.** Note the contrast with flying fish: here the
  **selective pressure is actually measured** (the Grants' long-term drought-selection data), which the
  flying-fish predator-escape story never was.
- **Zebra finch** (*Taeniopygia guttata*) = a distinct lab **songbird** model for vocal learning and some
  developmental genetics. **Not this mission.** Do **not** cite zebra-finch developmental/vocal results as
  Darwin's-finch beak evidence; they are different organisms and different literatures.

## Scales × evidence type (the user's three distinct types; reuse the fish coupling contract)

Same engine as flying fish — reachability under measured constraints: `Problem(actionable) → Action
(acceptance + falsifier + stop) → Evidence → independent review` — and the same discipline that kept
Daane's **genetic association** separate from a **functional/developmental** result. Keep these three
evidence types distinct and never silently bridge them:

| Scale (SPEC-026) | Evidence type | Primary leads (listing; unread) | Model availability |
|---|---|---|---|
| Molecular (1) | **genetic association** | ALX1 ↔ beak **shape**, Nature 2015, doi:10.1038/nature14181; HMGA2 ↔ beak **size** | GWAS/association in wild *Geospiza* — association, **not** a developmental mechanism or a function proof |
| Cellular/developmental (4/9) | **developmental model** | *lead not in the supplied set* — the developmental signaling-to-shape body (e.g. BMP4 / calmodulin, Abzhanov lineage) is a **separate** layer **to source**, distinct from the GWAS association | a mechanism of how beak dimensions are built; must not be equated with the association hits |
| Organ (6) | **mechanics** | beak-stress **FEM** PMC2830229; scaling/**shear** (D'Arcy Thompson transformations) PMC2840476; **geometry–dynamics** form↔function↔evolution PNAS 2021, PMC8609615 | structural/mechanical models of the beak under bite load; the analogue of the flying-fish C1–C6 envelopes |
| Organism/evolution (8/11) | measured selection | the Grants' field selection series (lead) | the one layer where selection is quantified (unlike flying fish) |

**Model-availability caveat:** genetic association (ALX1/HMGA2) ≠ developmental model ≠ mechanics (FEM /
shear / geometry-dynamics). A GWAS hit does not set a parameter in a beak-mechanics model, and a mechanics
model does not establish a developmental cause — exactly the cross-scale-bridge discipline used for the
fish. Any coupling across these is a proposed transfer until reviewed.

## Broader design-primitives catalog — SUGGESTED ONLY (not scoped, not built)

Each is a candidate "form primitive" that could reuse the **fish coupling contract** (a measured
morphometric envelope + a genetic-association layer + a mechanics/developmental model, kept distinct),
one future mission at a time. Listed to show the pattern generalises, **not** as commitments:

- **Teeth** — shape/wear/occlusion; FEM bite mechanics; enamel/dentine development.
- **Claws** — curvature ↔ substrate/behaviour; keratin mechanics.
- **Fins** — the flying-fish mission (done at scoping grade; the worked example).
- **Scales** — armour/hydrodynamics; patterning genetics.
- **Patterning** — pigment/stripe/spot (reaction–diffusion); a developmental-model-heavy primitive.
- **Behaviour** — only where it is measurable and coupled to a form (e.g. finch feeding ↔ beak); otherwise out.

## What this card is NOT
Not a finch sim, not a Draft record, not a claim of any finch finding, not scheduled. The finch primaries
are unread leads. The next action is **none until root delivers the fish source-claims/actionable-questions**;
then a single finch mission could be scoped the same way, starting with a brief **read** of the five leads
above at better than `listing` grade.
