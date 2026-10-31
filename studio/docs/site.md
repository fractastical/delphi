# Delphi Frontier site

Static, dependency-free workspace in `site/` (vanilla JS, vendored KaTeX 0.16.47, MIT). No build step beyond the data snapshot.

    python3 scripts/build_site.py          # writes site/data/{snapshot,catalog.json,docs/}
    python3 scripts/build_site.py --check  # exit 1 if committed data is stale
    cd site && python3 -m http.server      # preview

## Views (hash routes; selection and the source drawer live in the hash so Back works)
Frontier (open-questions whiteboard: goal -> constraints -> questions -> literature/theory, direction/approach/scale filters, table alternative), Knowledge (claims with equations, claim graph, flying-fish equations, catalog), Engineering (scales and couplings, candidate workspace, constraint flags, open questions, solver/simulation adapters), Evidence (sources by read level, disagreements, replayable results, artifacts index, what could not be obtained), Work (runtime, declared MCP tools, plan as written), Belief (separation of truth/forecast/priority/decision, factor-graph structure, local scratch arithmetic).

## Data and adapters (`site/js/adapters.js`)
`/api/health` decides live vs snapshot; live also needs `GET /api/session` -> `authenticated`. Live shapes (read from `frontier/web.py`, normalised once in `adapters.js`): catalog `{results:[{record,local_status,is_head,why_matched}],search_mode,next_cursor}`, record `{record,local_status,is_head}`, events `{events:[{sequence,envelope}],next_cursor}`, artifacts `{items:[{artifact,...}]}`, solver per `docs/engineering-api.md`. Live: `/api/catalog`, `/api/record`, `/api/events`, `/api/artifacts`, `POST /api/engineering/solve` (CSRF from `GET /api/session`, header `X-CSRF-Token`; request fields are decimal strings, <= 12 places, checked client-side). Snapshot fallbacks read `data/*.json`. Pending interfaces throw `Unavailable`; the UI says so and shows no result.

## Honesty rules enforced in code
Upstream labels are never local acceptance. Approach/scales on questions are site-assigned until a record carries `approach`/`scales`/`context_tags` (record values win). No owner unless a record names one. Engineering checks never pass on qualitative flags (C4, C6a), and C2/C5 need explicit opt-in assumptions. The page's arithmetic is preliminary and defers to the corrected solver. No counts of tests, jobs or progress are shown.

## Tests
`tests/test_site_browser.py` (Playwright): all views render, whiteboard selection/Back, filters, drawer + Escape, KaTeX, no fake pass, mobile overflow, malformed/missing data.

## Live QA
`tests/test_site_live.sh` (+ `tests/site_live_driver.py`) starts a scratch PostgreSQL instance and the real web service on random ports, seeds records with `frontier.seed`, signs in with `POST /api/session` plus Origin (a browser form login cannot work: `Referrer-Policy: no-referrer` makes form POSTs carry `Origin: null`), and drives the real UI: live catalog and lexical search, pinned record drawer, events table, and the solver (feasible, unsat with conflict, unknown with rho/CL unset). Needs a Python with z3 (see the pin in the engineering docs).

## Not wired (named, not hidden)
Beliefs: `frontier/beliefs_api.py` exists but no web route is registered, so the Belief view's request button still reports the adapter as not connected. Attention API: not delivered. Artifact download: the link appears only for an artifact that declares `availability: downloadable` with an https URI; the scratch node holds no artifacts, so only the formatter is unit-tested.
