# Flying zebrafish: literature check of SPEC.md numbers

Checked 2026-10-31 by the Research agent (speed pass, ~15 min). Verdict "ok" = within ~20% of literature.
Only **two** items need change (marked **ADJUST**); a few more are notes.

## Sources used
- [Z1] Zebrafish adult morphometrics, 61 adults (SL 2.98 cm mean): https://krishikosh.egranth.ac.in/server/api/core/bitstreams/69e2ac88-ae57-41e1-bee3-6d0620935cac/content (Table 3: MBD 0.78, CPD 0.33, ED 0.17, pre-opercular 0.56, DFBL 0.27, AFBL 0.50, CFL 0.75 cm)
- [Z2] Zebra danio facts (depth 3.4-4.2 in SL; head 2.7x eye) http://www.dictionaryoffish.com/zebrafish.htm ; BdFISH (SL = 4.0-4.2 HL, 3.6-4.1 body depth) https://bn.bdfish.org/2015/03/
- [Z3] FishBase Danio rerio (cross-section compressed; pelvics abdominal, before dorsal origin; 10-12 branched anal rays; max 3.8 cm SL): https://www.fishbase.se/physiology/Danio_rerio
- [Z4] Parichy et al. 2009, staging by SL (adult phenotype >= 19 mm SL): https://pmc.ncbi.nlm.nih.gov/articles/PMC4108942/
- [F1] Davenport 1994, Rev Fish Biol Fisheries 4:184-214, doi:10.1007/BF00044128
- [F2] Davenport 2003, J Fish Biol (wing length <= 76% SL; pectoral leading edge fixed at 24% SL from snout), doi:10.1046/j.1095-8649.2003.00041.x ; Davenport 1992 JMBA (wing length <= 78-79% SL), doi:10.1017/S0025315400048761
- [F3] Fish 1990, J Zool 221:391-403 "Wing design and scaling of flying fish", doi:10.1111/j.1469-7998.1990.tb04009.x (PDF https://www.wcupa.edu/sciences-mathematics/biology/fFish/documents/1990JZWing%20design.pdf)
- [F4] Park & Choi 2010, J Exp Biol 213:3269-3279 (Cypselurus hiraii wind tunnel; NOT Bioinspir. Biomim.), doi:10.1242/jeb.046052
- [F5] Cheilopogon exsiliens, FAO/FoTX: https://fishesoftexas.org/taxa/cheilopogon-exsiliens/ ; C. melanurus: https://fishesoftexas.org/taxa/cheilopogon-melanurus/ ; C. heterurus: https://fishesoftexas.org/taxa/cheilopogon-heterurus/

## (1) Adult zebrafish (fractions of SL)

| Quantity | SPEC value | Found | Source | Verdict |
|---|---|---|---|---|
| Max body depth | 0.24 SL | 0.26 (male 0.24, female 0.27); lit. range 0.24-0.28 | Z1, Z2 | ok (0.25 is fine) |
| Body width | 0.13 SL | not found in a citable source; FishBase: cross-section "compressed" | Z3 | ok / unverified (keep) |
| Head length | 0.25 SL | 0.24-0.25 (SL = 4.0-4.2 HL); pre-opercular length alone 0.19 | Z2, Z1 | ok |
| Eye diameter | 0.07 SL | 0.057 SL (Z1 measured); 0.27 HL x 0.25 = 0.068 (Z2) | Z1, Z2 | ok (0.06-0.07; 0.065 compromise). Keep 0.07 if eyes should read clearly at 80 mm |
| Caudal peduncle depth | 0.10 SL | 0.11 | Z1 | ok |
| Pelvic fin insertion | x = -0.42 SL | "abdominal, before origin of dorsal" (about 0.40-0.45) | Z3 | ok |
| Dorsal fin base | -0.50 to -0.64 SL (0.14 SL long) | base length 0.09 SL (0.27/2.98) | Z1 | **ADJUST to -0.53 to -0.62 SL (base ~0.09-0.10 SL)**. 0.14 is ~55% too long |
| Anal fin base | -0.57 to -0.76 SL (0.19 SL long) | base length 0.17 SL | Z1 | ok |
| Caudal fin length | ~22 mm at SL 80 (0.275 SL) | 0.25 SL (0.75/2.98) | Z1 | ok |
| Dorsal / anal fin height | small, 0.8-1.0 mm thick | dorsal fin length 0.16 SL, anal 0.16 SL | Z1 | ok (heights ~13 mm at SL 80) |
| Adult size | SL 80 mm | real adults 19-38 mm SL (scaled up x2-4 for printing) | Z4, Z3 | ok (just a scale-up) |

## (2) Flying fish (Exocoetidae)

| Quantity | SPEC value | Found | Source | Verdict |
|---|---|---|---|---|
| Pectoral fin length / SL | 0.70 | Cheilopogon exsiliens 0.53-0.75; C. melanurus 0.39-0.78; C. heterurus 0.67-0.77; hard cap 0.76-0.79 (tips hit tail beat) | F5, F2 | ok (0.70 near upper-normal; do not exceed 0.76) |
| Pectoral insertion x | -0.25 SL | leading edge of pectoral base fixed at ~0.24 SL from snout | F2 | ok |
| Pectoral insertion height | z = +0.04 SL (high on flank) | "high" insertion qualitatively; no number found | F1, F4 | ok (unverified) |
| Pectoral aspect ratio | implied ~10 (span ~120, area ~1300-1500 mm2) | 9.0-10.7 (Cypselurus hiraii); Fish 1990 genus AR 3-17, Exocoetus up to ~20 | F4, F3 | ok |
| Pectoral mean chord | (16+8)/2 = 12 mm = 0.15 SL | 24-28 mm at SL 205 = 0.12-0.14 SL (about 10-11 mm at SL 80) | F4 | ok (+15%, within tolerance; AR ~10 needs chord ~12 at 120 span) |
| Total span / SL | ~120/80 = 1.5 (incl. spread geometry) | 1.14-1.27 SL (span 233-261 mm at SL ~205) | F4 | **NOTE: SPEC span is ~20-30% wider than Park & Choi.** Fine for display, but see bbox note below |
| Pectoral share of wing area | not stated | 76-77% (Cypselurus, Hirundichthys, Danichthys), 82-84% Parexocoetus/Fodiator, 92% Exocoetus | F3 | info |
| Pectoral sweep | 25-35 deg | "slightly swept back"; tips tapered/pointed | F4 | ok |
| Pectoral dihedral | 5-10 deg | 7-22 deg tested (natural ~7-12) | F4 | ok |
| Pectoral incidence (angle of attack vs body axis) | not specified | 8-15 deg (Breder 1930 sketch: 17 deg) | F4 | add: tilt wing leading edge up 8-12 deg |
| Pelvic fin length / SL | 0.40 | C. exsiliens 0.33-0.50; C. heterurus 0.30-0.37 | F5 | ok |
| Pelvic fin insertion x | -0.50 SL | snout-to-pelvic-origin 0.52-0.59 SL (C. exsiliens, C. melanurus) | F5 | ok (could be -0.55; 10% off) |
| Pelvic area share | not specified | 20-35% of total lateral fin area; pelvic incidence 2-5 deg | F1, F4 | check: pelvic wing area per side should stay under ~1/3 of the pectoral area |
| Pelvic spread angle | ~60 deg | not quantified in literature found | n/a | ok (unverified) |
| Tail lobe ratio (lower:upper) | lower lobe 1.3x upper (length) | hypocaudal lobe = 60.6-64.0% of caudal AREA (all genera) => lower:upper area 1.5-1.8; lobe length ratio ~1.25-1.35 | F3, F1 | ok |
| Body depth / SL (flying fish) | 0.24 (zebrafish) | Cheilopogon 0.16-0.20; Cypselurus comatus 0.17-0.20; Exocoetus 0.19-0.22 | F5 | note: zebrafish base is deeper by ~25%; intentional. If the fish looks too fat, 0.22 SL max is a good compromise |
| Head length / SL (flying fish) | 0.25 | 0.20-0.27 | F5 | ok |
| Caudal peduncle depth (flying fish) | 0.10 | 0.063-0.077 | F5 | zebrafish value kept; fine |
| Body cross-section | flatter belly | "nearly rectangular, almost flat ventrally"; Cypselurus ventrally flattened, Exocoetus rounded | F5, F4 | ok |
| Dorsal fin origin (flying fish) | -0.50 SL | 0.64-0.72 SL (far back); zebrafish ~0.52 | F5 | keep zebrafish |
| Wing loading | not specified | rises with size (positive allometry); Park & Choi fish: mass 0.04-0.06 kg at SL ~205 mm, plotted vs SL (value not extracted); Fish 1990 scaling exponent 0.36-0.53 | F3, F4 | n/a for a print |

### Geometry notes for the wing agent
- **Bounding box:** pectoral length 56 mm at ~80 deg spread gives ~55 mm projected each side plus the body half-width (~5 mm) = ~120 mm, with dihedral less. This is right at the 120 mm Y limit. Keep dihedral >= 5 deg or sweep >= 30 deg, or trim wing to 0.68 SL (54 mm).
- Wings are thin membranes with a stiff leading edge; all fin rays on the LOWER surface, upper surface smooth (Park & Choi). So put the ray grooves on the ventral side only; keep the dorsal face smooth and cambered.
- Wing tips are pointed (tapered), not rounded.

## (3) Open-licensed 3D meshes / CT (information only, nothing downloaded)

| Item | URL | Licence / access |
|---|---|---|
| AGGRC Flexi Zebrafish (printable STL) | https://www.printables.com/model/1326849-aggrc-flexi-zebrafish | CC BY-SA 4.0, free STL download. Best direct print mesh, but a cartoon/flexi design, not morphometrically accurate |
| Danio CT scan, Danionidae (Sketchfab, Florida Museum oVert) | https://sketchfab.com/FloridaMuseum/collections/fish-diversity-ct-scans-c3b000466be24245a6bdfb2cd2aa0ccf | Check licence per model on Sketchfab (oVert models are generally CC); download may need login |
| Cheilopogon (Cypselurus) melanurus UF:Fish:111151 whole-body CT series | https://www.morphosource.org/biological_specimens/000S23956 | MorphoSource: free account; media is "open download" or "restricted" per file; raw CT needs segmentation (no ready mesh) |
| Zebrafish head CT (UTCT/DigiMorph), 914 slices | https://doi.org/10.18738/t8/uxhqxy ; https://www.digimorph.org/specimens/Danio_rerio/ | UT Austin dataset, acknowledge UTCT and NSF IIS-9874781; head only |
| JS Gauthier zebrafish models (embryo/larva; "72 hours" is paid) | https://sketchfab.com/jsgauthier/models | Free ones have no stated CC licence; larval stages, wrong shape. Do not use |
| NIH 3D | https://3d.nih.gov | Human medical models only for this search; no fish found |

Repo cross-check: `test-data/organisms/merged/taxa.json` has Exocoetidae (gbif:2968) (not queried in detail; no numbers needed from it).

## Summary of changes recommended
1. **Dorsal fin base**: -0.53 to -0.62 SL (about 0.09-0.10 SL long), not -0.50 to -0.64.
2. **Bounding-box risk**: pectoral wing at 80 deg spread is ~120 mm across; reduce wing length to 0.68 SL or increase sweep/dihedral so Y < 120 mm.
3. Optional: add 8-12 deg wing incidence (leading edge up); ray texture on lower surface only; pelvic insertion -0.55 SL.
4. Eye 0.07 SL is 20% above the measured 0.057-0.068: acceptable, 0.065 if convenient.
