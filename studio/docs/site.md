# Delphi Frontier site

Static, dependency-free workspace in `site/` (vanilla JS, vendored KaTeX 0.16.47, MIT). No build step beyond the data snapshot.

    python3 scripts/build_site.py          # writes site/data/{snapshot,catalog.json,docs/}
    python3 scripts/build_site.py --check  # exit 1 if committed data is stale
    cd site && python3 -m http.server      # preview

## Views (hash routes; selection and the source drawer live in the hash so Back works)
Frontier (open-questions whiteboard: goal -> constraints -> questions -> literature/theory, direction/approach/scale filters, table alternative), Knowledge (claims with equations, claim graph, flying-fish equations, catalog), Engineering (scales and couplings, candidate workspace, constraint flags, open questions, solver/simulation adapters), Evidence (sources by read level, disagreements, replayable results, artifacts index, what could not be obtained), Work (runtime, declared MCP tools, plan as written), Belief (separation of truth/forecast/priority/decision, factor-graph structure, local scratch arithmetic).

## Data and adapters (`site/js/adapters.js`)
`/api/health` decides live vs snapshot. Live: `/api/catalog`, `/api/record`, `/api/events`, `/api/artifacts`, `POST /api/engineering/solve` (CSRF from `/api/session`; header name `X-CSRF-Token` is an assumption to confirm). Snapshot fallbacks read `data/*.json`. Pending interfaces throw `Unavailable`; the UI says so and shows no result.

## Honesty rules enforced in code
Upstream labels are never local acceptance. Approach/scales on questions are site-assigned until a record carries `approach`/`scales`/`context_tags` (record values win). No owner unless a record names one. Engineering checks never pass on qualitative flags (C4, C6a), and C2/C5 need explicit opt-in assumptions. The page's arithmetic is preliminary and defers to the corrected solver. No counts of tests, jobs or progress are shown.

## Tests
`tests/test_site_browser.py` (Playwright): all views render, whiteboard selection/Back, filters, drawer + Escape, KaTeX, no fake pass, mobile overflow, malformed/missing data.
