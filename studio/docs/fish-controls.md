# Fish control-knob dataset

Status: proposed, single operator, unreviewed. Measured and published numbers only: nothing generated, imputed or converted between sources.

## What this is
`data/fish-controls/knobs.json` lists 51 control knobs in the shape `{variable, unit, observations, fit/residuals, validity domain, taxon/context, source/locator}`. Three kinds, never mixed:

| kind | n | what it is |
| --- | --- | --- |
| `observed_and_fitted_here` | 8 | Specimen observations from Daane 2021 Data S1A, kept in `daane2021_s1a_observations.csv`, with a fit made here, per-specimen residuals and leave-one-out error |
| `published_fit_only` | 36 | A fit printed in Fish 1990 (Tables I-III). **Raw data unavailable**: the paper measured 199 specimens and does not publish them |
| `published_summary_only` | 7 | A mean or range printed in the text of Fish 1990 (pectoral share of wing area by genus; pooled hypocaudal share) |

## Daane 2021 Data S1A (observations)
Source: the article's supplement `mmc2.xlsx` (`https://ars.els-cdn.com/content/image/1-s2.0-S0960982221011908-mmc2.xlsx`, sha256 `1ac98650...2279`), sheet `A - fin measurement`: 109 preserved specimens from the Harvard Museum of Comparative Zoology: flying fish 49, flying halfbeak 19, halfbeak 22, needlefish 19, with SL, pectoral and pelvic fin length in cm. `NA` cells stay empty (12 pelvic values missing in flying fish, 4 in flying halfbeak, 2 in halfbeak). The workbook is not stored; the per-specimen numbers are, with attribution.
* **One sheet cell is corrupt:** specimen 1 (*Hirundichthys rondeleti*) has pelvic/SL = 2.4e-16 where 6.9 / 23 = 0.30. All ratios here are recomputed from the lengths. (The print worker found the same cell independently; this build reproduced their group sizes and ratio medians.)
* **Fits** (`daane2021_s1a_fits.json`): log10-log10 ordinary least squares of fin length on SL, bootstrap 95% interval on the slope (2,000 resamples, seed 20261031), leave-one-out RMSE in log10 units, residuals per specimen. Usable means R^2 >= 0.8 and n >= 15. The flying halfbeak pelvic relation has R^2 = 0.02 (slope interval -0.64 to 0.51): **no relation detected**, flagged weak.
* Reading: the group differences are mostly in the multiplicative constant, the fin/SL ratio (pectoral median 0.69 in flying fish against 0.27, 0.14 and 0.09 in flying halfbeaks, halfbeaks and needlefish), not in the slope: the flying-fish pectoral slope against SL is about 1.06 (interval 1.02-1.10, R^2 0.98, SL 1.7-24 cm). The paper's statement that flying-fish pectoral length "increases rapidly" with body size is about Figure 1B; this dataset does not contradict it, and I have not re-derived the paper's own plot.
* Pooling: species and sizes are pooled within each group; per-species relations may differ.

## Fish 1990 (published fits, raw data unavailable)
Source: Fish FE (1990) J Zool 221:391-403, the author-hosted PDF (sha256 `1efed334...f8ea`, 13 pages, scanned). Not stored. The tables were read from **page images**, because the OCR text is wrong in places (for example Exocoetus wing-area interval). Table I (length, wing span, wing area, hypocaudal area against mass; 6 genera), Table II (wing loading, with observed ranges), Table III (aspect ratio, with observed ranges), and the pectoral and hypocaudal shares from the text. Table IV was not read.
* Form: `y = a * M^b`, reduced major axis, M in kg. Units are not printed in the table headers; they are **inferred from magnitude** (length and span m, areas m^2) and labelled so.
* The scan prints several `a` values without a decimal point (`0460`). `a_printed` is kept beside the restored `a`; the tests check the restoration by magnitude and check every printed P mark against its confidence interval.
* Kept inconsistencies: the text gives 11.7 N/m^2 for "a 0.001 kg" fish while the smallest specimen mass is 0.003 kg; the text gives an aspect-ratio maximum of 16.9 while Table III lists up to 19.9.

## Not converted, not claimed
S1A is fin length against **standard length**; Fish 1990 is size against **body mass**. No conversion between them is made. Nothing here is a flight-performance claim, a construction recommendation, or a statement about any other taxon.

## Licence and redistribution
Crossref lists the Elsevier open-access user licence for the Daane version of record (from 2022-11-22) and TDM licences; the terms were **not read**, and the supplement states no licence. Whether storing the per-specimen numbers is permitted is unresolved: root decides. The Fish 1990 PDF has no stated licence; its published numbers are kept with locators.

## Rebuild
`PYTHONPATH=. python3 -m connectors.fish_controls.build` (fetches both files, refuses if a pinned hash changed). Tests: `python3 -m pytest tests/test_fish_controls.py -q`.
