# Exact-commit review: r4-daane-printfix at bd2fcf31ca46 (fit and balance print only)

Reviewer: an independent AI agent process (not a lab or human). Exact commit `bd2fcf31ca469b7063db0b86815fb568003dd822`, read-only worktree. Own code: `launchable-fish-review-run/revcheck.py`
(output `r4-daane-printfix-bd2fcf31ca46-check.json`) and `wallzone.py`. The acceptance criteria are the ones I stated before the commit existed; a failure is reported as a failure.
Not done: slicing, supports, peel, printer fit, any print or weighing, the catch's stress, dynamics for r4 (07's r1 results do not carry over), the GLB and images.

## Criteria and results
| # | Criterion (stated beforehand) | Result |
|---|---|---|
| a | **Chirality.** R print vertex set not identical to L; fish-frame R is the exact y-mirror of L; both print transforms det +1; positive stored volume | **PASS** for all 7 L/R pairs (pectoral, pelvic keys -1..+4). R print = L print with z negated (checked for pectoral and pelvic dec+2), not identical; both dets +1; every part has 0 negative-determinant transforms. r3 had 0 of 7 printable pairs |
| b | **Integrity.** Hashes, closure, volume/mass/CG/inertia, assembly | **PASS.** All STL sha256 match the manifest; 0 open edges, 0 duplicate directed edges on every part; volumes, CG and Iyy equal the manifest; dry assembly 20.3346 g, CG (63.607, 0, 4.057) mm, equal to the manifest. Units mm. The r4 body equals the frozen r3 body from byte 81 (header differs); the `_L` fins equal r3's |
| c | **Wall.** No sampled wall reading under 0.45 mm unless explained; none in the catch liner region | **FAIL in the catch region** (details below). Reported unchanged |
| d | **Zip.** Members hash to the listed STLs | **PASS.** `download.json` sha256 and byte count match the zip (2,269,148 bytes); the 6 STLs match the manifest part hashes; `SHA256SUMS` lists 10 files with 0 mismatches; the zip's manifest equals the repo manifest and its sha matches `download.json` |
| e | **Claims.** Untested, fit/balance only, no flight or launch-survival claim | **PASS.** The label and `download.json` say "LAUNCH PROTOTYPE, UNTESTED, OVERWEIGHT; fit/balance test print; printer compatibility not claimed"; `ASSEMBLY.md` says not flight-ready, never printed, weighed, glided or thrown; `KNOWN_DEFECTS.json` records the R-file defect in r1 to r3 and where it was found and fixed |

## Criterion c in detail
* My sampler (inward ray from sampled face centroids, exit face must face along the ray) on the whole body, 7,430 rays: median 0.499 mm; 3 readings below 0.45 mm, 2 below 0.40 mm, minimum 0.115 mm. Dense sampling of all 11,759 faces with centroid x between 12 and 28 mm: 10,596 wall readings, **21 below 0.45 mm, 17 below 0.30 mm, minimum 0.097 mm**, all at x 18.8–20.3, |y| about 6 mm, z 8.4–9.1.
* One thin reading examined face by face: a small face on the body's lateral flank at about (19.3, -5.95, 8.75) whose inward ray meets, 0.116 mm away, a long triangle spanning y from -6.1 to +6.1 at z about 8.65 (the slot roof). So these are **feather edges where the slot roof meets the curved flank at the two side openings of the nominal catch slot (x = 20 mm)**, not a uniformly thin wall. At the slot centre the top wall is about 2.1 mm (vertical line at x = 20, y = 0: outer top 10.91 mm, slot roof 8.80 mm).
* So the manifest's "edge-limited" label describes something real, but the consequence is the one it does not state: the slot's lateral openings end in edges as thin as 0.1 mm, where the band strands run. A 0.1 mm feature will not print reliably and will chip, and chipped or sharp resin edges at the band exit can cut the band. It is in the launch path, not a structural root.
* The manifest's own two flagged points, (25.01, -7.53, -5.45) and (18.38, 6.39, 8.15) mm at 0.309 mm, I did not examine individually; the second lies in the same x band as the thin region.
* I did not decide whether the thin edges lie on the load path of the liner; there is still no stress calculation for the catch (peak catch force on the ballasted assembly 6–29 N across the module's scenarios, from earlier arithmetic).

## Decision
* **Fit and balance print: acceptable as disclosed.** Criteria a, b, d and e pass on this exact commit, and a printed set will be a mirror pair. Expect the slot side edges to print rough or chip; inspect and dress them before any band is run through, and do not use the printed catch as evidence of anything.
* **Not cleared for launch.** Criterion c fails in the catch region, the catch has no load calculation, the set is 20.33 g dry against a 10.5 g budget (13.5 g on this fin area per `ASSEMBLY.md`), and nothing here is a dynamics, printer or flight result.
* This does not change the earlier findings: replication, empirical relevance and flight survival remain insufficient.
