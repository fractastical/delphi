# site/

The Delphi website. Two parts live side by side here:

- **The portal**, imported unchanged from
  [kavitakoolkarni-bio/delphi-portal](https://github.com/kavitakoolkarni-bio/delphi-portal)
  (live at <https://kavitakoolkarni-bio.github.io/delphi-portal/>), commit `ad8e85e`:
  `index.html`, `platform.html`, `data/`, `.nojekyll`. Edit these in the portal repo and copy them
  over; don't restyle them here.
- **The claims atlas**, built from this repo by `` scripts: `claim-graph.html`,
  `theorems.html`, `claims-query.html`, `problems.html`, `team.html`, plus `claims.json`,
  `problems.json`, `export/`, `thumbs/`, `team/`. Don't edit these by hand; rebuild them.

## Shared look

`css/delphi.css` carries the portal's design tokens (paper / ink / rule / accent / specimen, light and
dark) and the components the atlas pages share (header, sub-navigation, buttons, badges, tables,
footer). The theme toggle uses the portal's `localStorage` key (`delphi-theme-blue-pink-v1`), so a
visitor's choice carries across portal and atlas. Old variable names (`--gold`, `--blue`, …) are
aliased to the tokens at the bottom of the `:root` block so page CSS can migrate gradually.

The header and footer are partials in `scripts/site/templates/partials/`, filled into each
template's `<!--__SITE_HEAD__-->` / `<!--__SITE_FOOT__-->` by `scripts/site/chrome.mjs`
(`team.html` does the same in `build-team-page.py`).

## Rebuild

From the repo root:

```sh
cd engine
node scripts/site/build-claim-graph.mjs     # claim-graph, claims-query, theorems, claims.json, export
node problems/build/build-site.mjs          # problems.html, problems.json
python3 scripts/site/build-team-page.py     # team.html
```

## Refresh the portal

Copy `index.html`, `platform.html`, `data/` and `.nojekyll` from a fresh checkout of the portal repo,
and record the new commit above. If the portal changes its tokens, update the matching values in
`css/delphi.css`.
