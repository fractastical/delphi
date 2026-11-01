# Delphi Frontier site

Static workspace in `site/` (vanilla JS, no bundler, no npm step). Vendored libraries, each with its licence file: KaTeX 0.16.47 (MIT, equations) and three.js 0.170.0 (MIT, used only by the actual-GLB viewer `site/js/model-viewer.js`; see `site/vendor/three/VENDOR.json`). The only build step is the data snapshot.

    python3 scripts/build_site.py          # writes site/data/{snapshot,catalog.json,docs/} and copies verified artifacts into site/artifacts/
    python3 scripts/build_site.py --check  # exit 1 if committed data is stale
    cd site && python3 -m http.server      # preview (snapshot mode; no /api)

The builder reads tracked repository files only, records a sha256 for every input, and copies a video, mesh or archive into `site/artifacts/` only when its bytes equal the declared digest. A snapshot label is derived from the input digests.

## Views (hash routes; selection and the source drawer live in the hash so Back works)
Home (sourced anatomy beside the actual 3D candidates, printable models, two entry paths), Studio (project, one panel per MorphoSwarm scale, design assurance map, design review of a pinned Project, life-cycle panel, bounded simulation preview, local drafts), Frontier (open-questions whiteboard plus the live question table), Knowledge (claims with equations, infinite scroll over the catalog, graph, catalog), Engineering (candidate workspace, solver, printable forms, recorded results), Evidence (sources, disagreements, replayable results, artifacts), Simulations (manifest cards with verified video, equations, sources and limitations), Belief (truth, forecast, priority and decision kept apart; solver), System (tabs: overview, how it was built, specs, work, resources, receipts, runtime, connect), About (overview, team, documentation, inspirations, generative biology; modules `about.js` and `generative.js` are root's).

## Data and adapters (`site/js/adapters.js`)
`/api/health` decides live vs snapshot; live also needs `GET /api/session` (an anonymous public-read session is enough for reads). Current live reads: `/api/catalog` (cursor, `kind`, `query`), `/api/record` (exact pin), `/api/events`, `/api/artifacts`, `/api/discovery`, `/api/graph`, `/api/media`, `/api/counts`, `/api/system`, `/api/attention`, `/api/design/context` (exact Project pin, cursor). Current live calculations (CSRF from `GET /api/session`, header `X-CSRF-Token`): `POST /api/engineering/solve`, `POST /api/beliefs/solve`, `POST /api/simulations/run` (bounded preview). Shapes are normalised once in `adapters.js`; an API error that is an object is rendered as text, never as `[object Object]`. Snapshot fallbacks read `data/*.json` and say so. An interface a node does not serve throws `Unavailable`; the UI says so and shows no result.

## Honesty rules enforced in code
Upstream labels are never local acceptance. Approach/scales on questions are site-assigned until a record carries `approach`/`scales`/`context_tags` (record values win). No owner unless a record names one. Engineering checks never pass on qualitative flags (C4, C6a), and C2/C5 need explicit opt-in assumptions. The page's arithmetic is preliminary and defers to the corrected solver. Counts shown are counts of records or of receipt-backed quantities, each with the note the receipt attaches (for example GPU container seconds are not kernel seconds); a quantity with no receipt is shown as unknown, never as zero.

## Tests
`tests/test_site_browser.py` (Playwright, canned-route mocks for live shapes): every view renders, whiteboard selection/Back, filters, drawer, KaTeX, no fake pass, mobile and wide-desktop overflow, malformed data, infinite scroll with retry, design review threads, simulation previews, viewer and printable-model controls. `tests/test_model_viewer.py` covers the GLB viewer. Run every browser or server test under `systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600`.

## Live QA
`tests/test_site_live.sh` (+ `tests/site_live_driver.py`) starts a scratch PostgreSQL instance and the real web service on random ports, seeds records with `frontier.seed`, signs in with `POST /api/session` plus Origin (a browser form login cannot work: `Referrer-Policy: no-referrer` makes form POSTs carry `Origin: null`), and drives the real UI: live catalog and lexical search, pinned record drawer, events table, and the solver (feasible, unsat with conflict, unknown with rho/CL unset). Needs a Python with z3 (see the pin in the engineering docs).

## Not built or not wired (current)
- Formalization proposal checker (`POST /api/formalize/propose`): not built in the site.
- Annotation, Project and design-challenge submission: drafts stay in the browser and export JSON; the page never holds a credential (`POST /v1/design/reviews` needs a bearer token).
- Agent-by-agent timeline: not built; the tree holds role and count receipts only (System, "How it was built").
- Artifact download links appear only for artifacts that declare `availability: downloadable` with an https URI, plus files this build copies after a digest check.

### Historical (earlier state, kept for context)
Early in the build the Belief solver had no web route, the attention API was not delivered, and no counts were shown; those routes and the receipt-backed counters now exist as listed above.

## Live scratch checks (added 2026-10-31)

`tests/test_site_live.sh` runs the site against a scratch PostgreSQL and the real web service. With `SITE_E2E_DESIGN=1` it also writes a Project
(`project-flying-fish-mission`), a structured challenge and a reply through the Store, and `SITE_E2E_DRIVER=site_live_design_driver.py` checks that the
design review panel draws them by exact pin with none resolved, and that every About route draws. These are scratch records, not the production node's
seeded challenges. Mocked-live browser tests (`tests/test_site_browser.py`) cover the shapes the scratch node cannot easily produce (long ids, errors, 503s).
