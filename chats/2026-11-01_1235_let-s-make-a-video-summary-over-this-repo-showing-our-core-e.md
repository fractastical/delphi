# let's make a video summary over this repo showing our core estats simaiorl to wh

- **Started:** 2026-11-01 12:35 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 12:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `806d7285-825d-4e26-8d04-ed2fd22ae36f`

## Conversation

### 2026-11-01 12:35 — Turn 1 (User)

> let's make a video summary over this repo showing our core estats simaiorl to what is in teh animated gif but as a singe linkable video

**Assistant:**

I'll look through the repo for the animated GIF and the core stats it shows, then turn that into one linkable video.

The README animations are separate GIFs. I'll look at how those cards are drawn and what the current numbers are, then make one video in the same style.

The GIFs are scoreboard cards. I’ll pull the current counts from the claim files and render them as one video in that same layout.

The scoreboard cards are the model. I’ll compute the current counts from the claim graph and render them as one video in that layout.

The standing card is the one to match: white layout, the seal, and the live counts. I’ll build that as one video from the claim graph, then link it from the README.

The title card is in place. The standing card’s bars failed to draw, and the table still needs a pass so the columns and the legend fit.

The standing card is now one 26-second video, in the same white layout as the summary GIFs.

[assets/delphi-where-it-stands.mp4](assets/delphi-where-it-stands.mp4) is 1920×1080, about 674 KB. The README shows the closing card, and that image links to the video. It opens on a title, then counts up to the card below. Figures are read from `docs/claims.json` (built 2026-11-01 15:21 UTC) and the merged taxon inventory.

| | |
|---|---:|
| claims | 1,763 |
| live nanopublications | 880 |
| theorems | 91 (73 Lean, 18 literature) |
| tested against data | 174 (93 supports, 37 mixed, 30 refutes, 14 inconclusive) |
| of those, on organisms | 90 |
| animal taxa | 1,036 |

The bars give a claim its proof color when it has one, and the data verdict otherwise, so a theorem that was also tested is gold in the bar and still counted in the tested column. The faithfulness line is 33 of 174 checked, 5 not representative, 6 contested.

One figure is ahead of the README table: the card says **17** tests awaiting data, counted from `result.json` files with status `preregistered`. The table generated at 15:21 UTC says 16. Rebuild the video with `python3 scripts/site/build-summary-video.py`.

_Tools used: GetDynamicTools, Glob ×5, Grep ×8, Read ×23, Shell ×13, StrReplace ×10, Write, delphi_overview_
