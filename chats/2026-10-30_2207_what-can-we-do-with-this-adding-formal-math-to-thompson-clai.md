# What can we do with this? Adding formal math to Thompson claims

- **Started:** 2026-10-30 22:07 UTC-4 (EDT)
- **Last activity:** 2026-10-30 23:10 UTC-4 (EDT)
- **User messages:** 5
- **Subagents:** 0
- **Transcript ID:** `013fd3ac-fc8a-4f13-ba0c-62a1f641b134`

## Conversation

### 2026-10-30 22:07 — Turn 1 (User)

> what can we do with this?

**Assistant:**

I'll take a quick look at the README and the MCP overview so I can give you a concrete answer.

"This" is a bit ambiguous here since there's no attached file, so it's probably referring to the repo itself. I'll take a quick look at the README and project overview to figure out what to suggest, keeping things brief.

I notice there's a truth/ directory that isn't mentioned in AGENTS, so let me take a quick look at it.

This repo is a library of candidate biological laws, each published as a nanopublication: a small, signed, citable RDF record. You can query and rank those claims, add new source texts, assess claims, and publish the results. Right now it holds about 560 claims across four domains.

| Domain | Claims | With formal math |
|---|---|---|
| Thompson, *On Growth and Form* (1917) | 291 | 0 |
| Darwin, *Origin of Species* (1859) | 247 | 0 |
| Population genetics / evolutionary theory theorems | 18 | 18 |
| Reaction-diffusion / Turing patterns | 3 | 3 |

The only assessment type so far is `dataset-resolvability/0.1.0`. It has 494 assessments covering all 247 Darwin claims, from two assessors.

**What you can do now:**

- **Query and rank claims.** Search for claims (for example, "which Darwin claims are about variation under domestication?"), pull up a single claim with its source, or rank claims by how well their datasets resolve. You can do this through the `delphisci` MCP server or `node mcp/cli.mjs`. It can search either the local drafts or what's actually published on the network.
- **Browse visually.** `docs/claim-graph.html` is an interactive claim graph with sliders for the P and T thresholds. `docs/claims-query.html` lets you filter, sort and export claims as CSV or JSON.
- **Use the Discord agent.** `agent/` holds a bot that can answer questions about the claims in chat.

**Where the obvious gaps are:**

1. **Finish Thompson.** Its 291 claims are drafts with no assessments yet. The next steps are running dataset-resolvability on them, as was done for Darwin, and then publishing them.
2. **Start Wolfram NKS.** The folders are set up, but there's no `claims.json` yet.
3. **Add formal statements.** None of the Darwin or Thompson claims have math. Thompson's are good candidates, since his scaling and allometry laws can be written as equations.
4. **Prove theorems in Lean 4.** The README names this as a goal, and nothing has been built for it yet. The 21 math-biology theorems are the natural starting point.
5. **Test claims across organisms.** The README also calls for simulating each law in many organisms and checking it against that organism's own data. This hasn't started.
6. **Add assessment types.** Ranking only works on dataset-resolvability today. A second type, such as empirical support, would make the rankings more meaningful.
7. **Finish truth-scoring.** `truth/` has a batch workflow for blind truth scores. So far only six Thompson claims have been scored.

If "this" meant one particular file or tool rather than the whole repo, tell me which one. Otherwise, I'd start with assessing Thompson or the Lean formalization. Publishing to production signs with your ORCID key and can't be undone, so I'll check with you before any publish step.

I should keep my answer brief, and maybe ask the user to clarify what exactly they're referring to.

_Tools used: Read, Shell ×2_

### 2026-10-30 22:11 — Turn 2 (User)

> no?

**Assistant:**

The "no?" is ambiguous — they might be referring to something else entirely, or disagreeing with my assumption. Let me check terminals and git status to figure out what "this" actually refers to.

There are a few candidates it could be referring to—the orx dashboard (OpenResearch) that started recently, the docs server, or morpholib. Rather than guessing further, I should just ask the user directly which one they mean, offering these as options.


It sounds like "this" referred to something else — currently open are the OpenResearch dashboard on port 4791, the docs server on port 8765 serving problem-graph.html, and the morpholib repo you cloned earlier. Let me know which one you mean.

_Tools used: AskQuestion, Shell_

### 2026-10-30 22:54 — Turn 3 (User)

> how com ethe thompson didn't fhave forma math?

**Assistant:**

I'll check how the Thompson claims were extracted and whether the math field was ever filled in.

I should check how the Thompson claims were extracted and whether a math field exists, looking at the extraction instructions and the claims.json fields.

The Thompson claims have plenty of math. It just never got its own field, so the overview's math count reads 0.

The MCP server counts a claim as having math only if its nanopub carries a `skos:notation` triple with a LaTeX formula in it. The math-biology theorems have a `notation` field that `math-bio-theorems/build-nanopubs.mts` writes into that triple. The Thompson pipeline never had one:

- **The extraction schema has no formula field.** The fields are `claim`, `quote`, `claim_kind`, `scope`, `measurable_quantities`, `candidate_data` and `resolvability_triage`. On math, `thompson-growth-form/extraction/INSTRUCTIONS.md` says only:

```68:71:thompson-growth-form/extraction/INSTRUCTIONS.md
  recorded as he made it. Where he states a mathematical relation, state it (e.g.
  "surface varies as the square and volume as the cube of length"). Make it
  self-contained (no "this", "the above").
```

  It also says to avoid quotes "that are mostly formula notation". So the math went into the English text of each claim.
- **`thompson-growth-form/build/generate.mjs` never writes `skos:notation`.** Even a formula in the data wouldn't show up as math.

The relations are in there. 67 of the 291 claims are tagged `mathematical-law`, for example:

- **Weight and length:** weight varies as the cube of length, \(W = kL^3\).
- **Tree buckling:** tree diameter must grow as the 3/2 power of height, \(d \propto h^{3/2}\).
- **Speed and size:** swimming, flying and walking speeds all vary as the square root of linear size, \(v \propto L^{1/2}\).

Fixing it would take three steps:

1. Add an optional `notation` field holding LaTeX, and fill it for the 67 `mathematical-law` claims plus any other claim that states a relation.
2. Emit it as `skos:notation` in `generate.mjs`, the same way the math-biology build does.
3. Regenerate the drafts. The Thompson claims are still unsigned drafts, so this changes nothing that's been published.

Each formula should match what Thompson actually wrote, not a modern restatement, because the extraction rules forbid adding later knowledge. Some claims, like the logarithmic spirals and Cartesian transformations, will need their own notation and can't be written as simple power laws. Want me to go ahead?

So the extraction schema never had a notation field, and generate.mjs doesn't emit skos:notation since the math is stated in prose instead. There are 67 mathematical-law claims that could be candidates for this, so I should offer to add it.

_Tools used: Shell ×3_

### 2026-10-30 22:58 — Turn 4 (User)

> sure

**Assistant:**

I'll read the Thompson build scripts to see where the new field fits.

I should check generate.mjs, merge.mjs, and claims.json to figure out whether notation belongs in the extraction files as the source of truth, with merge.mjs then producing claims.json.

There's a `nanopubs/signed` folder and a manifest, so I'll check whether any Thompson claims have already been published before I change them.

A signed folder exists, so the Thompson nanopubs were actually signed — I should check the manifest to confirm whether they were actually published, since earlier I assumed they were just drafts.

I need to correct myself — these were published to the test registry, not production, so my earlier statement was wrong. Since adding notation changes content and produces new trusty URIs, I should regenerate the unsigned files without republishing, but that leaves the signed directory and manifest mismatched with the old version, creating an inconsistency I need to flag for production.

For storing notation, I'm deciding against embedding it directly in the extraction rows since they lack stable ids, and instead favor a separate `extraction/notation.json` file keyed by claim id, merged in during merge.mjs with validation that each id exists — cleaner and easier to review.

Now I need to tackle the actual LaTeX writing: pulling all claims tagged as mathematical-law along with other claims containing relational language, so I can review the full set of 291 claims and identify candidates for formalization.


Correction: the 291 Thompson claims were actually signed and published to the test registry about an hour ago, not just drafted—though nothing's on production, and adding math will change their content, requiring new trusty URIs and re-publishing to test only. I'll regenerate the unsigned drafts without publishing, then pull every relation-stating claim to write its formula.

I have the 193 candidates. Before drafting, I'll check how the math-biology claims write their notation so the Thompson formulas follow the same style.

I need to identify which claims state a genuine quantitative relation expressible as a formula, skipping the purely qualitative ones, and write LaTeX for those while staying faithful to Thompson's original notation rather than modern exponents. I should double-check a few claims against the source text to confirm the formula matches what Thompson actually wrote.

I should spot-check a handful of the claims against Thompson's original text—items like 03-30, 15-06, 15-11, 15-15, 05-11, 08-03, 08-04, 08-06, 12-05, and 11-08—to confirm the notation matches his actual symbols, since these were carefully extracted but worth verifying with a quick search through the source.


I'll format Thompson's notation the same terse inline LaTeX style used in the math-biology text, then check the source for his original symbols on claims that quote formulas.

I've drafted formulas for about 70 claims. One check remains: whether Thompson himself gives the autocatalytic curve as an equation, so I don't attribute a modern form to him.

I'm checking the cylinder/sphere radius relationship in note 05-11, confirming the height formula and the 0.27R fraction against the one-eighth diameter claim, then noting 15-06 generalizes this with T and T′ before moving on to write up the result.

Now I'm planning the notation file, deciding to key entries by id since that matches the assessments convention, while noting merge should validate that every notation id actually exists. I'm then drafting candidate claims for selection — covering the cube-square scaling of weight, height, and strength relations from chapter 2, plus the proportionality between muscular work and body size versus energy supply rate.

I continue drafting more entries: flight speed scaling and the near-constant factor for doubling body size, the independence of projectile velocity and jump height from body length, swimming/flight/walking velocity scaling, and the surface-to-mass ratio claims — including how organisms maintain a roughly constant S/M ratio despite growth, and how cell division helps preserve that ratio by increasing total surface area when a volume splits.

I'm wary of chapter 3's growth-rate-ratio claims about constant form, since Thompson's phrasing is ambiguous about which ratio stays fixed, so I decide to skip those entries rather than risk misformalizing them. I keep the simpler mass-scaling relation and the constant k = W/L^3 as a density-like coefficient.

For chapter 21, I'm noting the velocity relation across temperature steps giving a Q10 factor around 2-3. For chapter 23, I'm modeling the seasonal growth curve as an average trend plus a sine wave whose amplitude shrinks toward zero as the growth rate itself declines, rather than assuming a fixed exponential damping term.

For chapter 27, I'm considering whether to describe Thompson's comparison to autocatalytic reactions using the standard kx(a-x) growth equation, while flagging that this is only an analogy rather than a literal mechanism — I want to verify this against the source text later. For chapter 30, I'm noting the inverse-square relation between volume and temperature, generalized to an arbitrary power-law balance between the two. For chapter 16, I'm recalling the empirical shift in brain-to-body ratio from about 1/8 at birth to roughly 1/50 by adulthood.

These seem like plain data points rather than laws, so I'll skip them. Moving to Delaunay surfaces, I'm capturing the constant mean curvature condition and listing the surfaces of revolution it produces — plane, sphere, cylinder, catenoid, unduloid, and nodoid. I'm also noting the geometric results for spherical cap formation, including the 2:1 radius ratio, the 30° half-angle, and the resulting height formula, plus the Plateau-Rayleigh instability criterion where a jet becomes unstable once its wavelength exceeds its circumference.

Then on the surface-tension scaling argument, the claim doesn't specify an explicit power law, so I'll skip it rather than guess. For the triple junction problems, I'm noting the 120° equilibrium angle for symmetric wall meetings and working through the Young-Dupré/Neumann triangle relation, including the degenerate case where one tension dominates enough that two cells only touch at a point.

Moving to hexagonal packing, six neighbors naturally give 120° angles throughout. Then for the rhombic dodecahedron, I'm checking whether 109°28′ (arccos(-1/3)) correctly describes the obtuse angle of its rhombic faces, since this shape minimizes surface area for space-filling cells of given volume.

Next I'm working through minimal bisecting partitions perpendicular to the longest axis, and how successive cuts should be made at right angles to minimize total dividing area. I'm also considering when corner or octant cuts become favorable depending on the volume fraction, and working out specific cut angles and distances — like the 55°22′ arc, the 62.5°–90° range for anticlinal divisions, and the triangular versus quadrilateral cell division points at roughly 1.345 and 1.517 times the base radius.

For n cells I'm counting partition types (n−3, giving 13 for 8 cells), then moving to geodesic curvature conditions — spicules and fibres following geodesics with κ_g = 0 — and the characteristic angles at triradiate (120°) and tetraradiate (~109°28′) junctions per Plateau's rules. I'm also parametrizing geodesics on cylinders as rings, lines, and helices, and noting how they tighten as a cone narrows.

Now I'm working through logarithmic spirals: r = a e^(θ cot α), where α=90° gives a circle and α→0 gives a radial line, arising from constant growth-rate ratios in shoots and self-similarity under rotation-scaling. I'm connecting this to gnomonic growth (whole similar to whole-plus-gnomon) and geometric progressions in whorl breadths, as seen in Nautilus shells.

Checking numbers, for Nautilus α≈80° gives a whorl ratio b_{n+1}/b_n = e^(2π cot α) ≈ 3.03, matching observed values around 3, with ammonites spanning α≈80-85°. I consider describing the full shell generating curve with scaling, rotation, and translation, but decide it's too vague to formalize without Thompson's specifics, so I move on to noting that whorls touch or overlap.

Whether successive whorls separate, touch, or overlap depends on the ratio λ=e^(2π cot α) between outer and inner border growth rates—essentially a critical ratio condition I decide not to formalize. I similarly skip trying to pin down how the apical angle relates to the translation/growth ratio. For the lines of growth, I work out that if radius scales as r(θ,t)=t·f(θ), choosing f(θ)=cosθ produces coaxial circles passing through the umbo, which matches Thompson's description of growth lines as circles touching at a common point.

Moving to the logarithmic spiral case, I verify a numerical example: if successive chamber widths grow by a factor of 1.5, the implied apical angle α is about 86°, since e^(2π cot86°) works out to roughly 1.55, confirming the relationship. Exponential growth in mass (dM/dt ∝ M) implies chamber volumes form a constant ratio sequence. I note that constant growth-rate ratios on opposite sides of the shell (v_a/v_p = const) also force a logarithmic spiral, whether in plane or as a helicospiral—the shell is planar specifically when the angular range φ_max−φ_min equals π.

Turning to phyllotaxis, I decide to skip the modern conformal-mapping treatment relating cylindrical helices to log spirals and isogonal intersection angles as too anachronistic for Thompson's era. I focus instead on the Fibonacci recurrence—if a pair (F_n, F_{n+1}) of parastichies appears, all lower Fibonacci pairs are also present—and on the leaf-divergence condition: when there are between two and three leaves per turn of the genetic spiral, the parastichy pairs follow the Fibonacci series 1, 2, 3, 5, 8, 13...

I also note the convergence of successive Fibonacci ratios 1/2, 2/3, 3/5, 5/8... toward (√5−1)/2 ≈ 0.618, and skip rarer cases like 8/13 and raw data tables. Moving to the mechanics of tissue tension, I capture the generalized pressure-tension balance equation, the relation P = T/R showing thickness proportional to radius at constant pressure, the combined curvature-tension formula, and the roughly 6–7 ratio between left and right pressures matching thickness ratios—skipping Roux's angular arguments for now.

For the skeletal and geometric chapters, I note the cosine relation between leaf lengths, skip a minimal-effort case, and bypass the hollow cylinder moment of inertia formula since it's more modern engineering than Thompson's original focus. I include the proportionality between wall thickness and bending moment (maximal at mid-length), the alignment of trabeculae along orthogonal principal stress directions, the proportionality of spinal height to bending moment, and the recurring pattern of three processes meeting at 120° angles.

Moving into the coordinate transformation chapter, I capture Thompson's core idea of simple smooth mappings between related forms — like the sheep, ox, and giraffe comparison where equal-length proportions scale by roughly 2/3 and 1/3 under a transformation that stretches one axis while leaving the other fixed. I also note the begonia example where angles stay in constant proportion to each other, skip the ambiguous logarithmic grid-area point, and start considering the relationship between stiffness, depth, and thickness scaling.

For surfaces, I'm cataloging cases of constant mean curvature — the unduloid, membranes, and the septum minimal surface under uniform pressure — alongside the red blood cell as a counterexample where curvature isn't constant. I also flag Sachs's rule about surfaces meeting rigid walls at right angles, while skipping the minimal-area and pronuclei-path examples as less essential.

Going through the remaining chapters, most entries without explicit formulas I'm marking to skip, including growth rate functions, gravity-driven drops, and various coordinate transformation examples like the concentric circles and hyperbolas case already covered elsewhere. I'm tallying up roughly 70 included items so far and double-checking a few borderline chapter three entries.

Since Thompson doesn't give an explicit autocatalytic formula, I'll skip that item and move to writing the notation.json file, using full ids for clarity rather than stripped prefixes, and being careful to properly escape backslashes in the JSON strings.


I'll leave the autocatalytic curve claim (`ch03-27`) without math since Thompson never equations it, and the angles/ratios I checked match the text. Now writing the verified formulas into a new `extraction/notation.json`.

I'm noticing the "van't Hoff" apostrophe issue in section ch03-21 needs fixing for proper LaTeX formatting, since an apostrophe in math mode gets read as prime notation. I also want to simplify the growth temperature coefficient equation for clarity.

Now I'll wire the field through `merge.mjs` (with validation) and `generate.mjs`.

Now I'll run the merge and generate steps, then parse every draft to check it's valid TriG.

I should check whether INSTRUCTIONS.md needs a brief note, and confirm no other files depend on the claims.json schema since undefined fields just drop from JSON.stringify. Then I'll run the merge and generate steps, verify the git diff only adds the notation field, and double check the TriG output parses correctly with n3.

All 291 drafts parse, 71 of them carry `skos:notation`, and `claims.json` only gained the new lines. Last, I'll confirm the MCP server picks the math up.

I notice the commit moved from 8ad9c20 to fca611e, so someone else pushed changes. Moving on to check the MCP overview now.

71 of the 291 Thompson claims now have formal math, and the MCP overview now reports `claimsWithMath: 71` for Thompson. Nothing was signed or published.

**What changed:**
- **New file, `thompson-growth-form/extraction/notation.json`:** holds the LaTeX for each claim, keyed by claim id, in the same terse style as the math-biology claims.
- **`build/merge.mjs`:** merges those formulas into `claims.json` and fails if a key doesn't match a real claim.
- **`build/generate.mjs`:** writes each formula as `skos:notation` in the claim's nanopub.

All 291 regenerated drafts parse as valid TriG. Apart from the new formulas, `claims.json` is unchanged.

**What got math:** I only formalized relations Thompson actually states, and used his symbols where he gives them. For example, the egg equation is \(p_n + T/r + T'/r' = P\), heart-wall thickness is \(t(1/r + 1/r') = C\), and the best arterial branching angle satisfies \(\cos x = L/L'\). Some claims needed geometry rather than power laws: the logarithmic spiral \(r = ae^{\theta\cot\alpha}\), the 120° and 109°28′ junction angles, and the numbers for minimal-area cell partitions. The angles and ratios I checked against the source text match.

**What I left out, on purpose:**
- **The autocatalytic growth curve (`ch03-27`):** Thompson compares growth to autocatalytic reactions but never writes the equation. Adding a logistic formula would put later knowledge into his claim.
- **Purely qualitative claims:** these say surface tension shapes cells without stating any relation.
- **Thinly specified claims:** the parameters of turbinate shells and the human-versus-ape skull deformation, where any formula I wrote would be mine rather than his.
- **Bare data:** for example, brain weight falling from 1/8 to 1/50 of body weight.

These are judgment calls in a hand-written list, so the file is worth a skim before anything is published.

**Before publishing:** the 291 versions on the test registry don't include the math. Regenerating the drafts changes all of them, because each one gets a new timestamp, not just the 71 with formulas. So the next test publish would put up new versions of every Thompson claim. The changes are uncommitted, and `generate.mjs` says not to sign drafts built from uncommitted files. The order is commit, regenerate, then publish to test. I haven't committed or published anything.

I should also consider whether INSTRUCTIONS.md needs updating for future extractions, but I'll skip that since it's a separate concern from the notation work and just note it in passing.

_Tools used: Read ×3, Shell ×9, StrReplace ×5, Write_

### 2026-10-30 23:08 — Turn 5 (User)

> yes do it

**Assistant:**

I'll commit the math changes, rebuild the drafts from that clean commit, and publish them to the test registry only.

"Do it" means commit, regenerate, and publish to the test registry — publishing there is fine since the guidance only asks for confirmation before production. I should scope the commit to just the Thompson-related files: the build output, extraction notation, and claims, while checking git status to see what else is untracked and whether the nanopubs directory was part of the earlier commit.

I'll leave the nanopubs directory untracked as before, and only commit the build outputs, claims.json, and notation.json so the dirty check comes back clean. Then I can proceed to generate, dry-run, and publish.

The commit went in, the drafts rebuilt from a clean tree, and all 291 signed and verified in a dry run. Publishing to test now.

All 291 were accepted. I'll check that the math shows up on the network, not just locally.

Let me quickly check the network for Thompson math, though indexing might not have caught up yet.

The network source likely hits the production query service rather than test, so I should check the mcp README to confirm what "network" means here.

The "network" query hitting the production service makes sense as empty, but the test registry fetch path looks wrong. I should try different test registry URL formats.

The test registry is serving the new versions. The one I fetched, `epilogue-03`, has no formula, so I'll check a claim that does.

Epilogue-03 likely has no notation, as expected. Let me check a math-heavy one like ch15-11 to be sure.

I committed the math changes as `ee86522`, rebuilt all 291 Thompson nanopubs from that commit, and published them to the **test** registry. All 291 were accepted. Nothing went to production, and I didn't push the commit.

I fetched one of the published claims back from the test registry to check. The heart-wall claim (`ch15-11`) now carries its formula, \(t(1/r + 1/r') = C\), as `skos:notation`. The new trusty URIs are recorded in `nanopubs/manifest.jsonl`, which now has 582 entries: the 291 old versions and 291 new ones.

- **The old versions are still on test.** Nanopubs can't be deleted, and nothing marks the earlier 291 as superseded. Test is a sandbox, so this probably doesn't matter. If you want it marked, we can publish a supersession notice for each old version.
- **The `network` search won't show these yet.** It queries the production endpoint, so a network search of Thompson's math returns nothing until the claims are promoted.
- **Production is your call.** Promoting would run `node build/publish.mjs --registry production --dir nanopubs/unsigned`. That signs with your ORCID key and can't be undone. Production only accepts URIs already published to test, and the new versions now qualify. I'd skim `extraction/notation.json` first, since the choice of which claims got math, and how each was written, is my judgment.
- **The nanopub files are still uncommitted.** I committed only the build scripts, `claims.json` and the new notation file. The `nanopubs/` folder has never been committed for Thompson, and I left it that way.

The old 291 test versions aren't retracted, but that's fine since they're test-only; production promotion would use the new URIs going forward. I should also note the nanopubs directory remains untracked and the commit hasn't been pushed yet.

_Tools used: Shell ×7_
