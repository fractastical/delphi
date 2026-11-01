# Search and ranking came back empty even though the overview reports 1,190 claims

- **Started:** 2026-10-31 17:41 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 17:44 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `9c07018f-83f7-4728-877f-4b503ea6cf55`

## Conversation

### 2026-10-31 17:41 — Turn 1 (User)

> Search and ranking came back empty even though the overview reports 1,190 claims. Checking whether that's a bad argument on my side or a server bug.
> ==
> thisis what i just hard from our mcp server

**Assistant:**

I'll reproduce this with the CLI and look at the server code for how search and rank filter claims.

There's a discrepancy here - search and ranking return empty while the overview shows 1,190 claims. I should dig into the MCP server code and test it via the CLI to figure out what's going wrong.

The numbers add up to 1190 locally, confirming that's the TriG-indexed claims count since Aristotle isn't in nanopubs yet. Search with no arguments returns results fine locally, so the user's call must have passed some argument—maybe a domain filter. I should check the server's search and rank handlers to see how domain arguments are processed.


The unfiltered search returns 1,190 claims, matching the sum across the six indexed domains (Aristotle's 512 have no nanopubs yet). I'll now check how search and rank parse their filters, since the empty result likely stems from an argument issue.

I'm realizing the domain filter only matches lowercase slug substrings, so full thinker names like "Charles Darwin" won't match unless lowercased properly, and names with apostrophes like "D'Arcy Thompson" could fail too. Also the type filter seems to need an exact versioned string, so something like "dataset-resolvability" without a version would return nothing — I should test this directly.


The store isn't empty—1,190 matches align with local TriG data. Next I'll test argument shapes likely to yield an empty result: a thinker name as `domain`, a type without a version, and the Aristotle claims.

The server behaves correctly for valid arguments, but empty results trace back to specific argument combinations — some legitimate, like domain "thompson" with 0.1.0 being darwin-only, but others look like actual bugs, such as claim-test/0.1.0 being listed as rankable yet returning a rank of 0, likely because its assessments lack a hasScore field. I want to verify that assumption and also check what happens with darwin and 0.2.0.


Search and rank both function correctly with valid arguments. One issue stands out though: `claim-test/0.1.0` appears rankable in the overview but returns nothing when actually ranked, which looks like a real server bug—I'll dig into why.

Most likely the problem was the arguments you sent, but the server makes it easy to get wrong: it returns an empty list without saying why, and it has one real gap. With valid arguments, search and rank both return claims, from local files and from the published network.

**What returns empty, and why:**

- **`domain` matches the domain IRI, not the thinker's name.** `"darwin"`, `"thompson"` and `"math"` work. `"Charles Darwin"` returns nothing, because the IRI is `.../domain/darwin-origin-1859`.
- **`text` is matched as one exact substring.** `"natural selection"` finds claims, but `"selection variation"` finds none. The words are not searched separately.
- **Aristotle returns nothing.** The 1,190 in the overview is the sum over the six domains that have nanopubs. Aristotle's 512 claims are only in `claims.json` and the claim graph (whose total is 1,702), so search and rank can't see them yet.
- **`type` needs the full versioned string.** `"dataset-resolvability"` returns nothing; `"dataset-resolvability/0.1.0"` works.
- **Each version covers different domains.** Version 0.1.0 has only Darwin, and version 0.2.0 has only Thompson, Wolfram and Levin. So 0.1.0 with `domain: "thompson"` is correctly empty, and so is 0.2.0 with `domain: "darwin"`.

**The server bug:** the overview lists `claim-test/0.1.0` as a rankable type (134 assessments), but ranking by it always returns nothing. Those assessments record a verdict and evidence but no score, and `rankClaims` in `mcp/lib.mjs` only keeps assessments that have a score. Claim-test verdicts are available through `delphi_claim_tests`.

**Calls that work:**

- `delphi_search_claims` with `{ "domain": "darwin" }`, or with `{ "mathOnly": true }`
- `delphi_rank_claims` with `{ "type": "dataset-resolvability/0.2.0", "domain": "thompson" }`

If you tell me the exact arguments you used, I can tell you which of these it was. I can also change the server so empty results explain themselves:

- Unknown types would get an error listing the valid ones.
- Score-less types like `claim-test` would be left out of the rankable list, or point to `delphi_claim_tests`.
- A `domain` that matches nothing would get the list of available domains.

I'm realizing claim-test assessments use verdicts instead of scores, so rank silently returns empty for them — that's really a server gap since the overview lists them as rankable. I'm weighing whether to fix this so empty results explain themselves (unknown type, no scored assessments, or empty domain filter listing available domains instead), though the user's actual question was just about diagnosing bad argument vs server bug.

I also notice the overview's 1,190 count excludes Aristotle's 512 (which has no nanopubs), while the graph reports 1,702.

_Tools used: Grep ×2, Read ×2, Shell ×3_
