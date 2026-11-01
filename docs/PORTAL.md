# site/

The Delphi website. Two parts live side by side here:

- **The portal**, imported unchanged from
  [kavitakoolkarni-bio/delphi-portal](https://github.com/kavitakoolkarni-bio/delphi-portal)
  (also live at <https://kavitakoolkarni-bio.github.io/delphi-portal/>), commit `ad8e85e`
  (the portal repo's `main` as of 2026-11-01): `index.html`, `platform.html`, `data/` (1,256 files),
  `.nojekyll`. That import matches the portal tree byte for byte. Edit these in the portal repo and
  copy them over; don't restyle them here.

GitHub Pages publishes this `docs/` directory, with `CNAME` set to `delphibio.org`. The
homepage `index.html` is `Delphi_Product_Platform.html` from
[kavitakoolkarni-bio/morpholib-delphi-branch](https://github.com/kavitakoolkarni-bio/morpholib-delphi-branch)
`delphi-new/` at `d8449d0` (2026-11-01). On Pages, its `/v1/product` calls fall back to `data/`.
`platform.html` remains the earlier Lean for Biology page, also at `/platform/`. The
mission-control dashboard stays on its Cloudflare worker.
- **The claims atlas**, built from this repo by `` scripts: `claim-graph.html`,
  `theorems.html`, `claims-query.html`, `problems.html`, `team.html`, `deck/index.html` (the project
  overview deck, the header's About link), `blog/<post>.html` (posts, every count computed by
  `scripts/site/build-blog.mjs` from its template; `blog/index.html` is the hand-kept list of posts),
  plus `claims.json`, `problems.json`, `export/`, `thumbs/`, `team/`. Don't edit these by hand; rebuild them.

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
node scripts/site/build-overview-deck.mjs   # deck/index.html (after build-claim-graph; reads claims.json)
node scripts/site/build-blog.mjs            # blog/science-claw-2026.html (after build-claim-graph; reads claims.json)
```

## Refresh the portal

Copy `index.html`, `platform.html`, `data/` and `.nojekyll` from a fresh checkout of the portal repo
into `docs/`, and record the new commit above. Then regenerate `docs/platform/index.html` as
`platform.html` plus `<base href="/">`. If the portal changes its tokens, update the matching values in
`css/delphi.css`.
