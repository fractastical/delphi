# Making claims and math queryable: the delphisci MCP server

- **Started:** 2026-10-30 21:22 UTC-4 (EDT)
- **Last activity:** 2026-10-30 21:35 UTC-4 (EDT)
- **User messages:** 2
- **Subagents:** 0
- **Transcript ID:** `06a78db4-bb53-4975-b8f9-44d2717a03a5`

## Conversation

### 2026-10-30 21:22 — Turn 1 (User)

> how can we make this nanopub infra claim queryable so we can easisy access the math (wincluding some sort of embedded ranking)

**Assistant:**

I'll look at how nanopubs and claims are currently stored in the repo before suggesting a query design.

I need to look into the codebase to understand what this nanopub infrastructure claim refers to before responding.

The "math" probably lives in `math-bio-theorems/`, so I'll look at that, plus one claim and one assessment nanopub and the build scripts.

"The math" likely refers to math-bio theorems, so I should look into that.

I notice the math claims publish notation as plain LaTeX strings, but the theorem-readiness rankings only exist in JSON rather than as nanopubs, unlike the Darwin side which has proper assessment nanopubs with hasScore per dimension. I'm thinking the fix is to publish theorem-readiness assessments as nanopubs similarly, add typed math literals, and build a SPARQL query to rank them.

I recall that knowledgepixels supports publishing SPARQL queries as nanopubs through their grlc-query mechanism, which turns into live API endpoints — that could serve as the embedded ranking mechanism. I also want to verify whether the top5 assessments' claim IDs actually match the 21 published claims, since entries like hardy-weinberg and kermack-mckendrick don't seem to be among them, and I should test querying the production endpoint directly to confirm it's actually live and queryable.


The math claims are live on production, but theorem-readiness scores only exist in local JSON, not published. I'll check what's visible on the public SPARQL endpoint versus what's in the ranking files.

Math's duplicated across multiple repos/graphs. There's a gap though: ranking scores aren't published, and the top5 rankings use thinker ids like hardy-weinberg, kermack-mckendrick, berg-purcell, kingman that don't match the 21 published claims under fisher, hamilton, kimura, maynard smith, turing—only turing and kimura seem to overlap.

Notation is stored as plain strings, so I could type it as LaTeX or add MathML and split out the assumptions separately. For the embedded ranking, I'm thinking of publishing per-claim theorem-readiness assessments mirroring Darwin's LLMClaimAssessment pattern with a rubric nanopub, then a grlc query nanopub that computes a weighted-mean ranking aggregated across assessors—this becomes a stable API URL via Knowledge Pixels' grlc query template support, hitting an endpoint under query.knowledgepixels.com.

I should store per-dimension scores and rubric weights in the rubric nanopub but compute rank only in the query, since rank is relative and shifts as new claims get added—maybe cache a snapshot with a timestamp instead of baking it in. I want to verify this ranking pattern actually works against Darwin's data first, checking if the assessments are published and testing a query for hasScore under dataset-resolvability.


The SPARQL endpoint already returns LaTeX notation for published claims, but ranking data is the missing piece. I'll check if the Darwin assessment pattern with per-dimension scores is live so I can build a working ranking query.

Since the Darwin assessments aren't signed yet, I have enough to propose a plan rather than wait. The user wants to know "how," so I should give a concrete proposal and offer to build it: dedupe the notation query with DISTINCT, and split the mixed notation string into separate equations since it currently blends several formulas with prose like "for Malthusian fitness m."

For math, I'd give each equation its own literal with a proper datatype (maybe a LaTeX IRI or delphi:latex), pull assumptions out into delphi:assumption triples instead of leaving them buried in prose, and optionally link to Lean formalizations via delphi:formalizedAs.

For ranking, most top-5 picks per thinker reference unpublished claims like Hardy-Weinberg or Kingman, so I need to score the actual 21 published claims against the theorem-readiness rubric and publish them as LLMClaimAssessment nanopubs mirroring the Darwin generator's per-dimension structure with dct:isPartOf, plus publish the rubric itself with weights as its own nanopub. Rank shouldn't be hardcoded since it should be computed dynamically in the query as new claims or assessors are added, though an overall score per assessor could be stored for convenience.

I'm also thinking I should publish the ranking SPARQL itself as a grlc query nanopub so claim-graph.html can hit a stable API URL for CSV/JSON output. The weighted mean would need to join dimension weights from the rubric nanopub using something like a delphi:weight property on each concept — but I'm not sure that property exists in the ontology yet, so I need to check the Darwin rubric trig file to confirm.

The math is already queryable, but the ranking isn't. The 21 math claims are live on the production nanopub network, and a SPARQL query to `https://query.knowledgepixels.com/repo/full` returns their LaTeX `skos:notation`. The theorem-readiness scores exist only as local JSON, so nothing can rank the claims yet.

## Problems I found

1. **The rankings don't line up with the published claims.**
   - `math-bio-theorems/assessments/top5-gpt.json` and `top5-gemini.json` rank *thinkers*, not claims.
   - Most of the top picks (Hardy–Weinberg, Kermack–McKendrick, Berg–Purcell, Kingman) aren't among the 21 published claims. Only Turing and Kimura overlap.
   - Neither file is a nanopub.
2. **Rubric weights are only in prose.** In the Darwin rubric nanopub, the weights appear as text like `"Weight 0.2. Can the claim..."`. A query can't compute a weighted mean from that.
3. **The math is one string per claim.** Each claim's `skos:notation` mixes several equations with English (for example `... = V_A(m) for Malthusian fitness m`). The assumptions are buried in the `delphi:context` paragraph. So you can fetch the math but can't filter on it, for example "proved claims whose assumptions include a deterministic large-population limit".
4. **Darwin assessments aren't live either.** A ranking query over the Darwin `dataset-resolvability` assessments returned no rows, so those are also still unsigned and unpublished.

## Proposal

**1. Make the math structured.** In `build-nanopubs.mts`, emit:
- one `skos:notation` per equation, typed as LaTeX, with prose moved to `rdfs:comment`;
- one `delphi:assumption` per assumption;
- a proof-status value such as proved, open or false-as-stated;
- a link to a Lean theorem where one exists.

Because nanopubs can't be changed, this means publishing new versions that supersede the current ones (`npx:supersedes`).

**2. Publish per-claim theorem-readiness assessments.** Score each of the 21 claims with the rubric in `inputs/rubric.json`, using several assessor models. Reuse the shape that `generate-assessments.mjs` already produces for Darwin:
- one parent `delphi:LLMClaimAssessment` per claim and assessor, holding the overall score and verdict;
- five child assessments (one per dimension), each with a `delphi:hasScore` and linked to the parent by `dct:isPartOf`.

**3. Publish the rubric with machine-readable weights**, for example `<…theorem-readiness-0.1.0-proof-status> delphi:weight 0.25`. I haven't confirmed the Delphi ontology has a weight property. If it doesn't, we should propose one upstream rather than invent it.

**4. Compute the rank in the query, not in the data.** Don't store `rank: 3` in a nanopub. It goes stale as soon as a claim or assessor is added, and it can't be edited afterwards. Store dimension scores and weights, and let the query do this:

```sparql
PREFIX delphi: <https://w3id.org/delphi/ontology/>
PREFIX dct:    <http://purl.org/dc/terms/>
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?claim ?label
       (SAMPLE(?notation) AS ?math)
       (SUM(?w * ?s) / COUNT(DISTINCT ?assessor) AS ?readiness)
       (COUNT(DISTINCT ?assessor) AS ?assessors)
WHERE {
  GRAPH ?c { ?claim a delphi:Claim ; rdfs:label ?label ; skos:notation ?notation . }
  GRAPH ?a {
    ?claim delphi:hasAssessment ?dim .
    ?dim dct:isPartOf ?parent ; dct:subject ?dimConcept ; delphi:hasScore ?s .
    ?parent delphi:assessmentType "theorem-readiness/0.1.0" ;
            <http://www.w3.org/ns/prov#wasAttributedTo> ?assessor .
  }
  GRAPH ?r { ?dimConcept delphi:weight ?w . }
}
GROUP BY ?claim ?label
ORDER BY DESC(?readiness)
```

Two refinements belong in the real version:
- Filter to nanopubs that haven't been retracted or superseded.
- Report disagreement between assessors (for example the gap between the highest and lowest score) next to the mean. The two existing top-5 lists already disagree on order.

**5. Publish the query itself as a nanopub.** Knowledge Pixels can serve a published SPARQL query as a fixed web address under `query.knowledgepixels.com/api/...` that returns JSON or CSV. Anyone, including `docs/claim-graph.html` and the Discord agent, can then fetch the ranked list with its math in one request without writing SPARQL. That's the "embedded ranking", and the ranking method itself becomes citable and versioned. I haven't published one of these yet, so the exact address format still needs checking.

The first runnable step is items 2 and 3: score the 21 claims, generate the assessment and rubric nanopubs, and test the query against a local triple store before publishing. Publishing to production uses your ORCID signing key and can't be undone, so I'd stop for your sign-off before that step.

I've only found the weights described in prose, not in a clean machine-readable format, but I've gathered enough to write the answer now.

_Tools used: Grep ×2, Read, Shell ×7_

### 2026-10-30 21:31 — Turn 2 (User)

> let's make an agent "MCP" or somethinbg ilke that at least with a readme telling agents how to use this in the repo somehow?

**Assistant:**

I'll build a small MCP server in the repo that wraps the public nanopub SPARQL endpoint, add a README for agents, and register it in Cursor. First I'll check the existing Node setup and conventions.

I'm thinking about building a small MCP server for this, with a README and Cursor registration, scoped to querying the public SPARQL endpoint. I'm sketching out tools like search_claims and get_claim, but running into the issue that ranking requires assessment data that isn't publicly published, so I need to figure out a fallback.

I'm wondering whether to support loading local trig files for unsigned assessments so ranking can work before publishing, which adds complexity around parsing. Before going further, I should check the agent and darwin-origin package.json files, the Node version, and whether the MCP SDK package is actually installable given network constraints.

I'm planning out an MCP server structure with tools for raw SPARQL queries, searching claims by text/domain, retrieving full claim details with nanopub URIs and assessments, and ranking results.

For `rank_claims`, I'm considering averaging parent hasScore across assessors, noting that math-bio domain lacks assessments so far. For local mode, I'm weighing options between n3 Store queries versus using Oxigraph, which offers lightweight wasm-based SPARQL support that could let local and network modes share the same query logic.

One snag: unsigned nanopubs all reuse the same temp graph name, so loading multiple files into one store would cause collisions. I'm planning to rewrite each file's temp graph IRI to something unique per file before loading, and to only load directories ending in "unsigned" to avoid double-counting duplicate signed/unsigned content.

For the tool set, I'm sketching out `sparql`, `search_claims`, `get_claim`, `rank_claims`, and a `describe`/`stats` tool for orientation, plus deciding to register everything in the project's MCP config and add README/AGENTS docs.

I'll also add a CLI mode so agents without MCP access can still use these queries directly, sharing a core lib across `mcp/lib.mjs`, `mcp/server.mjs`, and `mcp/cli.mjs` — keeping the whole thing reasonably compact before installing dependencies.


I'll create an `mcp/` folder with an MCP server (supporting both live nanopub queries and local `.trig` files), a CLI fallback, and an `AGENTS.md` pointing to it. Starting with installing dependencies.

I should check the oxigraph API and confirm whether the MCP SDK's registerTool works with zod v4 - I think SDK 1.32 or so added that support. I want to verify by testing oxigraph loading a trig file.

The SPARQL engine (`oxigraph`) returns the same JSON format as the public endpoint, so local and network results can share one code path. Writing the query library now.

Both Oxigraph and the other source return SPARQL JSON, so I can unify the results. For local loading, I'm figuring out which directories under the nanopubs path actually hold unsigned content, using a rule based on folder naming, and trying to tally the Darwin unsigned claim count.

I also need to make sure network queries stay scoped to delphi claims specifically — the existing filter might not be enough since the upstream network could include other people's claims, so I should add a domain filter via the pubinfo graph linked to the assertion. I should test query timing since filtering text across the whole repo could be slow, watch for duplicate rows (likely from re-signed promoted nanopubs, though DISTINCT should fix that), and check how retracted or superseded nanopubs are flagged on the network side.

Writing search query...

I'm deciding to keep the temp nanopub path with its trailing slash and instead post-process in JS, converting URIs back to repo-relative file paths for reporting when they start with the local base. I'm also checking that the head graph includes the publication info predicate, then moving on to writing a case-insensitive text filter using CONTAINS and LCASE.

For getClaim, I'm expanding short IDs into full resource URIs and writing a query that joins assertion graphs to the head graph to pull all triples where the claim is the subject, planning to also fetch associated assessments.

Writing assessment query...

Now I'm designing rankClaims to aggregate assessors and scores per claim, with parameters for type, domain, limit, and minimum assessor count.

Still writing query logic...

I'm also noting a potential duplicate issue: if the same assessment shows up across multiple graphs due to network duplication, the averages could get skewed, so I need to account for that when grouping assessors.

The simplest fix is to pull distinct claim/assessment/assessor/score/verdict rows first, then handle label joins and ranking separately in JS rather than cramming it all into one SPARQL query.

For the type parameter in the rank tool, I'm leaning toward making it optional—if omitted, I'll surface the available assessment types via the overview tool rather than forcing a default, since guessing the wrong type could silently produce misleading rankings.

Now I'm sketching the overview query, which aggregates claim counts per domain and tracks how many have math notation attached by joining claims with their parent assessment's domain property.

For assessment types, I'm counting distinct top-level assessments (excluding sub-assessments linked via isPartOf) per type, along with their associated claims, filtering within each named graph so isPartOf stays scoped correctly.

Now I'm thinking through source configuration: should "network" vs "local" vs "test" be selectable, and what should the default be? Local includes unpublished drafts while network only has published data, so I'm leaning toward defaulting to "local" since agents are working within the repo, even though it means results won't clearly indicate publication status.

For the SPARQL tool itself, I'm making sure it's read-only by relying on the query-only method rather than exposing update capabilities, and deciding to cache the local store in memory with cheap mtime checks to detect file changes and trigger reloads. For results, I'm planning to return rows as simple JSON objects with proper type conversion for numeric values, and I'm starting to sketch out how the network fetch should work.

I realize there's no ranking data for math claims yet since theorem-readiness assessments don't exist, so I'll leave that honest rather than fabricate results, and just note it as a follow-up step. Now I'm ready to actually write the lib.mjs file.

I need to fix the dimension key logic so it strips the parent type prefix correctly when deriving the sub-key from the resolvability type string.

Local mode works and is fast (about 0.5s over 763 files). Now the network mode:

Working locally and fast. The fields return full IRIs, so I should compact them using known prefixes for readability — I'll add a small helper to shorten things like rdfs:label in the claim fields. Now let me test this over the network.

Network mode works too. It confirms that no assessments are published yet, so the ranking is local-only for now. Next I'll write the MCP server and CLI wrapper.

Networking checks out and performs well. Now I'm moving to the MCP server and CLI setup, checking how the registerTool API works in SDK 1.32 and verifying zod v4 compatibility.

I should double check that the destructuring defaults handle the undefined options correctly, then move on to updating package.json and testing the server through an MCP client handshake.

Everything works end to end over MCP and the CLI. Last step is wiring it up: Cursor config, the agent README, and a root `AGENTS.md`.

Good, everything checks out. Now I need to verify other files: the mcp.json at repo root, the README in the mcp directory, AGENTS.md, and whether node_modules folders are accidentally tracked in git since the root lacks a .gitignore.

I'll add a pointer from the main README and run a last check of the CLI's positional arguments and domain filter.

I should add a pointer in the README's "Querying nanopubs" section since it's already modified with uncommitted changes, so a small addition should be fine. I also want to verify the rank CLI's positional argument and domain filter work correctly with a quick test.

I added a `delphisci` MCP server in `mcp/`, plus a matching CLI and an `AGENTS.md` at the repo root that tells agents how to use it. I tested every tool through a real MCP client and the CLI, against both the repo files and the public nanopub network. It works, but math claims can't be ranked yet because they have no assessments.

The server has five read-only tools:
- **`delphi_overview`**: start here. It shows claims per domain, how many have math, and which assessment types can be ranked.
- **`delphi_search_claims`**: finds claims by text or domain (for example `turing` or `math`). The text search also looks inside the LaTeX. A `mathOnly` option limits results to claims with formal statements.
- **`delphi_get_claim`**: returns one claim by short id (for example `fisher-kpp-speed`) with its math, assumptions, proposed test and sources. It also returns every assessment, with per-dimension scores.
- **`delphi_rank_claims`**: this is the ranking. For each claim it takes one overall score per assessor and returns the mean, the number of assessors, the spread (highest minus lowest, so you can see disagreement) and verdict counts. The rank is computed when you query, never stored, so it stays correct as claims and assessors are added.
- **`delphi_sparql`**: raw SPARQL queries for anything the other tools don't cover.

Every tool takes a `source`:
- **`local`** (the default) loads the repo's unsigned `.trig` files, about 760 of them, in roughly half a second. This includes drafts and assessments that aren't published yet.
- **`network`** queries what is actually published on the nanopub network.

Agents without MCP can run the same queries with `node mcp/cli.mjs search fixation --math-only`, `... claim fisher-kpp-speed`, or `... rank dataset-resolvability/0.1.0`.

**Setup:** run `cd mcp && npm install` once (already done on your machine). Cursor reads `.cursor/mcp.json`; you may need to enable `delphisci` under Settings → MCP or reload the window. `mcp/README.md` also covers Claude Code and other MCP clients. I added a one-line pointer to it in the main `README.md`.

**What it shows today:**
- **Darwin claims rank locally.** All 247 are ranked by two assessors on dataset-resolvability; the Weald denudation claim is first at 0.94.
- **The 21 math claims are searchable with their LaTeX, locally and on the network,** but they have no per-claim assessments, so they don't rank yet.
- **No assessments are published to the network yet,** so ranking with `source: "network"` returns nothing for now.

Nothing is committed. The natural next step is to score the 21 math claims on the theorem-readiness rubric as assessment nanopubs, in the same shape as Darwin's. After that, `delphi_rank_claims` with type `theorem-readiness/0.1.0` would rank the math claims with no code changes.

That covers it. I should mention that Cursor will need a reload or to enable this in MCP settings, and nothing has been committed yet.

_Tools used: Shell ×8, StrReplace ×4, Write ×8_
