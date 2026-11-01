# Independent review: print-v4 display props, frozen commit 8a3e7a376206cb5d2da37abde4f586819bd61e6f

Reviewer: claude-13, an independent AI agent process (not a human or lab review). Own code (`launchable-fish-review-run/pv4check.py`, `pv4-standall.py`), read-only worktree at the exact commit, single-threaded numpy under a 4 GiB / TasksMax 128 cap. Output: `pv4-8a3e7a376206-check.json`.
**Failed attempt kept:** the first run (`pv4-attempt1-oom-killed.log`) was killed by my own 4 GiB cap during the reinforced-file wall sampling (ray-cast chunk too large); it produced no receipt. The second run used smaller chunks and completed (`pv4-attempt2.log`, EXIT=0). Nothing else changed between runs.

## Verdict
**Both display props (smooth STL + stand) are acceptable to publish as display/print props, labelled "not printed, not weighed, no flight or biological-validity claim".** No blocking finding. The scale-relief STLs pass topology only; their walls are ungated by design and must say so. The earlier r4 glider findings are untouched and stand: catch-wall FAIL (min 0.097 mm), dry 20.33 g / ballasted 26.07 g vs 10.5 g, no launch clearance. Nothing here concerns r5.

## Recomputed (own parser, exact float32 vertices)
Hash/length/hash of records: sha256 of all six STLs equal the claims; `downloads.json` 16 of 16 entries match hash and size; manifest, downloads, law index and candidate.json hashes equal the handoff (888680209d82, ca9cf1b6c3f3, 12ba707e679c, a6455a3ddfcb).
| file | tris | open/dup edges | edge comps | nonmanifold verts | volume mm3 | mass g (1220) |
|---|---|---|---|---|---|---|
| prop.stl | 44066 | 0/0 | 1 | 0 | 9837.011 | 12.001 |
| prop-scales.stl | 176170 | 0/0 | 1 | 0 | 10417.258 | 12.709 |
| prop-stand.stl | 1624 | 0/0 | 1 | 0 | 13019.145 | 15.883 |
| reinforced.stl | 50358 | 0/0 | 1 | 0 | 12704.658 | 15.500 |
| reinforced-scales.stl | 173570 | 0/0 | 1 | 0 | 13243.061 | 16.157 |
| reinforced-stand.stl | 1844 | 0/0 | 1 | 0 | 13405.316 | 16.354 |
All volumes positive (outward winding), 0 repeated-vertex or <1e-10 mm2 faces, all finite. Volumes and masses equal the claims. Bounding boxes: display 96.67 x 114.87 x 28.08 mm, reinforced 97.23 x 115.66 x 29.04 mm (fit the stated 120 mm box); stands 60 x 60 x 24.33 / 25.71 mm. Sliver triangles (<1e-6 mm2): 8 / 26 on the smooth props, 213 / 223 on relief, 0 on stands: equal the law-index counts, reported not gated. Mass is calculated from volume at the manufacturer's solid density (assumption: resin, cure and printer unchosen), not weighed.
Walls (own inward-ray sampler, valid exit-normal hits only, ~10,100-11,900 of 12,000 samples): display smooth min 1.1999 mm, reinforced smooth 1.7999 mm (rules 1.0 and 1.5, membranes 1.2 and 1.8): pass, matching the builder's 1.2000/1.8000. Stands, all faces: min 3.56 / 3.59 mm (builder reports 1.26 / 1.66; my number is higher because ~12% of faces give no valid exit hit and are not counted by me; both exceed the rule, so no conflict on the verdict but I did NOT reproduce the builder's stand minimum).
Mirror: parity test at 6000 random points (214-258 inside points on props, ~900 on stands), mirror about y = 0: 0 mismatches on all four smooth/stand files. Low power for a 1e-5 volume asymmetry (the builder's volume metric is the finer test; not recomputed).
Source linkage: candidate.json hash equals the one the manifest cites. Status wording in the handoff is accurate (display props, no glide, no biological validity).

## Non-blocking findings
1. Relief walls are 0.0035-0.0047 mm by the builder's own account (0.2-0.4 mm texture) and I did not gate them: any page/download must say relief is texture, ungated, and may not print or survive handling as drawn.
2. Needle-tip stoutness, vertex-cluster rule: NOT recomputed by me (their metric is material-in-a-ball; I checked topology and walls only). The law-index "recomputed" entry for it is their claim.
3. The frozen v3b glide-pose prop uses the same camber with a 1.2x membrane and a 3,000-sample minimum of 1.079 mm; dense check not run by me (not in scope of this commit). Withheld glide-pose v4 variant (db03fe60...) not reviewed.
4. Law index: the builder-record check `min_wall_dense` is their record, which I reproduced for the props not the stands.
## Not checked
Slicing, supports, printer fit, a print, weighing, structural adequacy of fins (reinforced gusset: euler_bernoulli_fin_root is inspired_only, no beam check run), self-intersection, GLB/PNG contents, site integration.
