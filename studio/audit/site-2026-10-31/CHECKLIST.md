# Audit checklist (recheck on the actual deployed release)
Recheck each on https://frontier.morphoswarm.ai after `/api/system` shows the fixing release SHA; do not accept a local build. Record release SHA and Seattle time in the result.
- [ ] F-1: first ID cell height < 30 px at 1440 and 390; no truncated column header; no clipped table; right panel populated on load.
- [ ] F-2: `#/evidence` scrollHeight < 8,000 px at 1440 with the artifacts index collapsed/paged; in-page nav reaches all six sections.
- [ ] F-3: anonymous `#/work` says public read-only (matches `/api/session`); release SHA shown with its "author report" label.
- [ ] F-4: GET of all 12 `snapshot.documents[].href` and `data/results/designs.csv` is 200 with sha256 equal to the snapshot value; every `doc:` drawer opens, no console 404.
- [ ] F-5: click anywhere on a row, or Enter on a focused row, selects it; `#/frontier/F001` shows F001 detail; focus visible on rows.
- [ ] M-1: at 390 px the nav shows a scroll cue or wraps; no half-cut label.
- [ ] M-2: phone `#/evidence` and `#/simulations` have jump links or collapsed sections.
- [ ] M-3: a 300-character query shows a plain "query too long (max 200)" message; search loading state has an indicator.
- [ ] M-4: helper text meets 4.5:1.
- [ ] Open items from "Not covered" are re-run before anyone says every page was reviewed.
