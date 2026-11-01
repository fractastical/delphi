# Independent review of the two reuse-study proposals

Scope: scientific context, typed proposal/bundle integrity, and local Chromium
desktop/mobile rendering. No owner files, live records, scientific runs, review
decisions or provider jobs were changed by this reviewer.

Reviewed owner commits `f4508e8`, `4ad1de9` and `f0e4538`, followed by root's
integrated **87aa45ea4d160b728e0f24cd9d01986aa8d2d429**. The final check uses
that commit's actual generated snapshot, catalog, HTML and app/studio code,
not the earlier local authored-data projection. Raw checks, screenshot hashes
and a read-only replay script are under `artifacts/audits/additional-projects/`.

## Scientific and data boundaries

- [x] Flying Fish remains first and the sole featured project; the two new pages
  are secondary Reuse studies.
- [x] Both Project drafts and the two-record bundle validate; record and bundle
  digests are intact. Members and related questions match the exact committed
  snapshot catalog. Every member says `causal_bridge=none_declared`.
- [x] At the reviewed commit, both pages are authored proposals with null live
  Project IDs and runners. Requirements/instruments are proposed; no calibrated
  bridge, accepted result, stored Project or new scientific run is implied.
- [x] The 2020 contractile Xenopus pipeline and 2021 ciliary Xenopus platform
  remain distinguishable. Neither supplies parameters for this proposed runner.
- [x] Lee/Wolgemuth's cultured MDCK context and Bai/Zeng's generic continuum
  epithelial sheet remain distinct from fish, clinical healing and this project.
- [x] Morpheus, BETSE, motor-clutch, NCA and ERK examples are named as reusable
  tools with limits. The zebrafish-scale ERK card explicitly identifies a different
  tissue and an absent motility coupling. This is deliberate source-context reuse,
  not inherited fish geometry or biological transfer.
- [x] No fish viewer/mesh, genetic panel, fish assurance widgets or runnable fish
  controls appear in either new project main. The fish page retains its eleven
  scale links. Switching from fish back to a reuse study is checked separately.

The final prepared bundle digest is
`29cabd0892acd33fccbf86c79e46819d21c080bb69f6793066d1f3ee74e58943`.
Schema validity and catalog identity do not establish live-store identity. Root
owns authenticated reissuance, current-head repinning, import and receipt-driven
status updates; those steps are outside this review's checks. Later live import
must not be retroactively attributed to this pre-import snapshot.

## Findings corrected before integration

The first source wording attributed the claim that signaling modifies rather
than produces closure to both epithelial abstracts. That conclusion belongs to
[Lee and Wolgemuth](https://doi.org/10.1371/journal.pcbi.1002007), not the
[Bai and Zeng abstract](https://doi.org/10.1038/s41598-023-33111-4). Owner06
corrected the attribution and retained the missing signaling coupling.

Protrusion-off and passive no-motion endpoints initially treated any remaining
motion as a solver defect. They now state force-balanced/no-other-drive conditions
and require diagnosis of unexpected motion. Numerical refinement is paired from
the same initial state; stochastic seed variability is reported rather than
classified as numerical failure. Cell-count conservation is conditional on no
birth/death. These are proposed controls; owner09/15 must freeze actual model
conditions and tolerances before a run.

Bai's license is now null rather than repeating an unverified grant from a brief.
The public full text was recovered through ordinary HTTPS Jina after direct web
challenge/fallback failures. PMID/title/abstract identities were also read from
NCBI EFetch XML. Source response hashes, methods and reading scopes are in
`source-checks.json`; full article caches remain private. No paper reproduction
or independent biological confirmation was performed.

The inherited project-list notes no longer claim the Project schema is pending
or that authored proposals require a stored Project before appearing.

## Browser checks and resolved navigation finding

Both project routes, Studio selection, exact original-record links, Back,
Flying Fish and the unknown-project fallback were exercised at **1440×900** and
**390×900**. No horizontal overflow or JavaScript page errors occurred. Sources
retain their correct URLs; proposed status and tool-transfer limits are visible.
Final viewport screenshots were also viewed directly.

The earlier `f0e4538` projection exposed a real scroll defect: opening projects
from the list retained 609–1,937 pixels of old scroll, placing their headings
404–1,459 pixels above the viewport. Root changed app route identity to `route.path`
and neutralized the global fish-specific footer. On actual integrated `87aa45e`,
all four opens have scrollY=0 and visible headings. The old observations remain
in `render-f0e4538/receipt.json`; the final observations are separate in
`integrated-87aa45e/receipt.json`.

No unresolved blocker was found within this scope after these corrections.
This is not a general security audit, live deployment/store check, non-Chromium
test or validation of tissue mechanics. No full test suite was run. The local
process tree was capped at 1 CPU, 2 GiB, 128 tasks and 600 seconds; focused Ruff
was run. Scientific work in progress by other workers is not counted as completed
by these pages or this report.
