# make sure that the form labs info on how to print is in the issue

- **Started:** 2026-10-31 19:31 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 19:32 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `846f016c-6804-4820-a9d0-eade491d5112`

## Conversation

### 2026-10-31 19:31 — Turn 1 (User)

> make sure that the form labs info on how to print is in the issue

**Assistant:**

I'll start by finding the issue and the Formlabs printing info.

The request is unclear about which issue they mean regarding Form Labs printing info, so I should look through the repo and GitHub issues to find the relevant one.

Issues #58 ("actually print wings") and #46 (WP5, Formlabs profile) are the likely candidates. I'll read both.

That gh issue view command returned nothing, which is odd—let me retry it with the --json flag instead.

Issue #58 ("actually print wings") has only a title. I'll look for the Formlabs "how to print" information in the repo.

Issue #58 "actually print wings" looks nearly empty, so that's likely the target, but I still need to find the Formlabs PreForm printing instructions — I should search the repo for that info, possibly in hackathon docs or recent chats.

The specific Formlabs printing info isn't in the repo, just generic material. The user might be referencing something from the hackathon, like the PreForm API demo, which I don't have access to. I could research Formlabs' public PreForm API docs and add findings to #58, but first let me check recent transcripts for any mention of "print" to resolve the ambiguity.

The repo doesn't have the Formlabs print instructions. #3 and #46 only mention them in passing. I'll pull them from Formlabs' public docs.

Since this Formlabs printing info isn't in the repo, I should gather it from public documentation and add it to issue #58, which currently only has a title. I'll research the PreForm API and related details so I can properly fill in the issue body as requested.

I'm weighing whether to edit the issue body directly or just add a comment, since the body is empty and a comment feels less intrusive and more reversible. I'll go with posting a comment instead of modifying the original body.

I added the Formlabs print instructions to issue #58 ("actually print wings") as [a comment](https://github.com/fractastical/delphi/issues/58#issuecomment-6550620991). I assumed #58 was the issue you meant, since it had only a title and nothing on printing.

The repo had no Formlabs print instructions, only passing mentions in #3 and #46. So I wrote the comment from Formlabs' public docs, not from the hackathon demo. If you have notes from the demo, such as the printer model, which resins are on site, or API access details, they should be added too.

The comment covers:
- **Printing by hand in PreForm:** pick the resin and layer height, orient the part, add supports, then upload to the queue or print now.
- **Printing from a script:** the PreForm API and its Python SDK, started with File > Start PreForm Server on `localhost:44388`, then sent with `print_scene`.
- **`print_now=False`:** I flagged this as the safe setting, because leaving it out starts the job at once on a ready printer.
- **Rules for a flexible membrane in Flexible 50A resin:** use the standard build platform, not the Flex one. It also lists support and wall-thickness limits. A hollow spar and a thin membrane are both close to those limits.
- **A to-do list:** get API access, find out what's on site, run the quickstart, print the wing from #45, and publish the print run as a nanopub.

I posted a comment instead of editing the issue body, so nothing was overwritten. If you'd rather have it in the body, I can move it.

_Tools used: Grep ×5, Shell ×5, WebSearch ×2_
