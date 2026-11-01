# Proposing approaches to open problems

You are one of several agents, each from a different model provider, asked independently to
propose ways the delphisci agent swarm could attack each open problem in
[`../problems.json`](../problems.json). You see only the problems file and the repo; you do not
see other agents' proposals. Write your proposals to `problems/approaches/<model-slug>.json`, where
`<model-slug>` is the slug you are told to use.

Each approach becomes a nanopublication (`delphir:approach/<problem-id>--<model-slug>--<n>`),
signed with the operator's key and published, so it must meet `BEST_PRACTICES.md` section 2:
nothing fabricated, no placeholder text, every DOI or URL real.

## What a good approach is

An approach is a concrete plan the swarm could start tomorrow with the tools it has:

- Lean 4 formalization (`claim-sources/thompson-growth-form/lean/INSTRUCTIONS.md` shows the standard).
- Exhaustive or large-scale computation (cellular automata, ODE sweeps, enumeration).
- Pre-registered data tests (`test-data/claim-tests/README.md`): hypothesis, pass and fail
  criteria, admissible datasets and inference method fixed before looking at data.
- The organisms layer (`test-data/organisms/`): 782 taxa resolved to GBIF, NCBI, Wikidata, PBDB.
- INDRA CoGEx (molecular statements with evidence), Nebius folds, `frontier_simulate` (bounded
  bioelectric and mechanobiology previews), the morpholib MorphoEval pipeline.

Propose 2 to 4 approaches per problem. They should differ in kind (a proof route and a data route,
or two proof strategies that fail differently), not be rephrasings. For each, say what would be
decisive: the artifact or measurement that settles the problem or a well-defined piece of it, and
what result would show the approach has failed. Be specific about the mathematics or statistics.
Name the lemma structure, the null model, the estimator, the dataset, the sample size needed.

Rank honestly. `difficulty` is your estimate of the chance the swarm completes the approach as
stated within about a month of agent time: `"tractable"` (> 50%), `"hard"` (10–50%),
`"long-shot"` (< 10%). Say what the swarm lacks if it lacks something (lab access, a dataset
that is not public, mathematics beyond current automation).

## Citations

Only cite a DOI or URL you have verified resolves (fetch it). The build resolves every link
again and drops the ones that fail into `dropped-links.json`; a dropped link weakens your
approach but a fabricated one would have been published under someone's name. If you are not
sure of a DOI, give the author, year and title in `note` and leave `doi` out.

## Output format

```json
{
  "model": "<model-slug>",
  "provider": "<OpenAI | Google | xAI | Anthropic>",
  "generated": "<ISO timestamp>",
  "approaches": [
    {
      "problem": "<problem id from problems.json>",
      "n": 1,
      "title": "<short title, under 90 characters>",
      "kind": "proof | computation | data-test | simulation | formalization | mixed",
      "method": "<one or two paragraphs: exactly what to do and how>",
      "steps": ["<step 1>", "<step 2>", "..."],
      "decisive_result": "<the artifact or measurement that settles it, and the stated threshold>",
      "failure_signature": "<what result shows this approach has failed>",
      "tools": ["lean4", "gbif", "indra-cogex", "..."],
      "datasets": [{ "name": "...", "url": "https://...", "note": "what is used from it" }],
      "references": [{ "doi": "10....", "note": "author year title" }],
      "difficulty": "tractable | hard | long-shot",
      "missing": "<what the swarm lacks, or null>"
    }
  ]
}
```

Write the file with valid JSON and nothing else. Do not edit `problems.json` or any other file.
