# Request tracker

Every request made in this working session, with its real status. Kept here so nothing is
carried only in conversation. **Open items are listed first.**

Status words: **done** (finished and verified) · **live** (done and deployed to the public
site) · **running** (a harness is actively working on it) · **open** (not started or
blocked) · **partial** (some delivered, some not).

---

## Open and partial — what still needs doing

| # | Request | Status | Where it stands |
|---|---|---|---|
| 9 | Playwright pass over **the rest of the site**, beyond About and Lean proofs | **open** | The first pass covered About, blog, Documentation, Motivation and Lean proofs. Studio, Frontier, Knowledge, Evidence, Engineering, Simulations and System have not had a critique pass in this session. Assigned to a dedicated harness. |
| 6 | Use **Argon** to help review | **partial** | Identified as `gemini-4-argon` on the Gemini API and wired into every harness brief for design critique. The blog review itself was run on `gemini-3.8-flash`, not Argon. An Argon pass over the About and blog pages is outstanding. |
| 15 | Use **Kimi** | **open** | Not located. The Nebius Scientific AI MCP exposes 69 tools, all scientific models and no chat LLM. `api.studio.nebius.com` and `api.tokenfactory.nebius.com` both rejected our credentials (401 with the workbench key, 400 with the IAM token). The Gemini model list contains no Kimi. Needs an endpoint or key name. |
| 23 | Fill in the **"Resources we are thankful for" slide** | **partial** | Content written and published as [09-resources-and-acknowledgements.md](09-resources-and-acknowledgements.md). The deck file itself was not found on this machine or in the two teammate repositories searched, so it could not be edited directly. Needs the file location. |
| 11 | More equations, simulations, claims and designs across scales | **running** | Ten harnesses. Ongoing. |
| 17 | Keep enriching the site with claims, modelling, sims, perturbations, experiment designs | **running** | Same ten harnesses. |
| 26 | More Xenobot work: sims, equations, modelling, heavy Nebius and Google use | **running** | Three dedicated harnesses: `ff-xeno`, `ff-voxgpu`, `ff-xenomodel`. |

---

## Delivered

### The site

| # | Request | Status | Evidence |
|---|---|---|---|
| 1 | Add a **blog** to the About section | **live** | `/#/about/blog` — four posts, built from `docs/blog/*.md` through the site snapshot |
| 2 | Improve **Motivation, Documentation, Overview, Lean proofs**: readable and user-friendly, technical depth kept | **live** | Overview gained an at-a-glance strip and three reading routes; Documentation regrouped into five sections with blurbs; Lean proofs gained a plain-language gloss per family with detail folded; Motivation rewritten with jump links |
| 3 | **Depth on Lean** | **live** | Lean proofs page plus the "Lean for biology" post: 5 families, 37 statements, 17 of 17 mutants, the solver-to-proof bridge, and what Lean cannot tell you |
| 4 | **Depth on stitching sims across scales** | **live** | The "Stitching simulations across scales" post and dossier file 06: 31 runs, 13 couplings, 4 refused, zero registered calibrations |
| 5 | **Depth on the evaluation** | **live** | The "How we evaluated the work" post and dossier file 07: receipts, mutants, controls, the unconverged v3b fin, the attestation check that failed its own corpus |
| 7 | Use **Playwright** | **done** | Screenshots and overflow checks at 1440 and 390 px, against both a local server and the live site; zero console errors |
| 21 | "I'm not seeing the improvements" | **live** | Correct — the work was on a branch. Ported onto `main`, full suite re-run (123 passed, 0 failed), released through the deploy tool with health checks and automatic rollback |
| 22 | Do not name the **Shenoy Lab**; implicit is fine | **live** | The card now describes multiscale mechanobiology as a framing and links to our own mechanics runs |
| — | Use more horizontal space; fix two run-together links | **live** | Blog index is two columns from 1180 px (1812 px tall down to 1345 px); the Motivation closing links now use the standard row |

### Documentation for teammates and judges

| # | Request | Status | Evidence |
|---|---|---|---|
| 20 | **Markdown files** covering how the system was built and the About pages, crawlable, with detail useful against the judging rubric, plus the links | **done** | Ten files in `docs/dossier/`, listed in [README.md](README.md) |
| 27 | These must **not be on the website**, repo only | **done** | Verified: 0 dossier files among the 848 site snapshot inputs, none published as a site document |
| 28 | A markdown of **agent usage**, and all the links | **done** | [10-agent-and-compute-usage.md](10-agent-and-compute-usage.md) |

### Agents, compute and research

| # | Request | Status | Evidence |
|---|---|---|---|
| 8 | Review the **codex-03 prompts** for context | **done** | 153 messages extracted and read; they shaped the blog topics and the honesty framing |
| 10 | Start **additional workers** to keep maxxing Nebius, Google, BioNeMo and bio-service calls | **done** | Ten harnesses, each with its own worktree, branch, job prefix and status file |
| 12 | **Counts** of agents, swarms, GPU jobs, CPU sims and bio/LLM calls, running and queued | **done** | Reported, and now recorded in file 10 |
| 13 | Why can we not get a **GPU for Evo** | **done** | No capacity problem. The prepared Evo 2 bundle was never submitted because the worker holding it died. Evo jobs have since run |
| 14 | Spawn **five harnesses** with a goal of useful cross-scale simulations | **done** | Five spawned, then five more added |
| 16 | **Zebrafish into a flying fish** as a separate project | **running** | `ff-zf2ff`, new files only, branch `claude/zf2ff-20261101` |
| 18 | Use the **Max plans before the Allen plans** | **done** | All harnesses run on `max_gmail`, `max_outlook1` and `max_outlook` |
| 19 | Review the **studio flying-fish page**, find modelling gaps, start jobs to fill them | **done** | `studio-gap-report.md`. Key finding: the page shows models at 4 of 11 scales while the site's own manifests cover 9 of 11 — the panel never learned about the recorded simulations |
| 24 | Update on **resource maxxing** | **done** | Reported; GPU jobs went from 0 to 28 in this campaign |
| 25 | How far did the **Xenobots** get | **done** | A 12-engine catalogue, real licence findings, an audited Voxelyze run, and voxcraft-sim blocked on device-side `cudaDeviceSynchronize` removed in CUDA 12 |

---

## Standing constraints

Carried into every harness brief:

- Max subscription accounts before the Allen account.
- 1 GPU per job, at most 2 per harness, only jobs the harness itself named, never another
  team's.
- New files and own branch only; never `main`; never the live site worktrees.
- A simulation is never an observation; every result carries a receipt and a scope line.
- Report failures. A precise failure receipt beats a vague success.
