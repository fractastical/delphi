# Claim extraction instructions: Aristotle's biological works

Source texts: `claim-sources/aristotle-biology/inputs/<work>.txt`, one file per work, in the Oxford
translation (1910–1912), described in `claim-sources/aristotle-biology/inputs/sources.json`:

| key | work | translator |
|---|---|---|
| `ha` | *The History of Animals* (*Historia Animalium*), Books I–IX | D'Arcy Wentworth Thompson |
| `pa` | *On the Parts of Animals* (*De Partibus Animalium*), Books I–IV | William Ogle |
| `ga` | *On the Generation of Animals* (*De Generatione Animalium*), Books I–V | Arthur Platt |

Each file has one paragraph per line, `## Book N` lines for books and `### Part N` lines for the
translator's chapters (Generation of Animals Books II–V have no chapter headings). Line numbers
below refer to these files.

Goal: list every **major claim** Aristotle makes in your assigned range, so that a later step can
check which of them can be resolved with modern scientific datasets, and later tests can say how
often he was right. Each claim becomes one nanopublication, so each must be a single,
self-contained proposition.

## What counts as a major claim

- A statement about animals that Aristotle asserts: an anatomical or behavioural pattern across a
  group ("all animals with blood have a heart"), a fact he states about a named kind of animal
  ("the octopus copulates by means of one of its arms"), a life-history regularity (gestation,
  litter size, lifespan, breeding season), a physiological or developmental mechanism, or one of
  his general principles of biology (that nature does nothing in vain, that parts exist for the
  sake of their function, that the male supplies the form and the female the matter).
- Prefer the generalization to the instance, and the claim to the catalogue. Where a passage
  lists many animals sharing a trait, record the general claim and name the animals in `scope`.
  Keep a claim about a single named animal when Aristotle states it as a fact of its own, it is
  striking or famous (the hectocotylus, the placenta of the smooth dogfish, the cuckoo laying in
  other birds' nests, bees' generation), or it is concrete enough to check (counts, sizes,
  durations, presence or absence of an organ).
- Include his explanations (why a part exists, how an embryo forms) as claims of their own,
  separate from the facts they explain.
- Exclude claims he reports from others ("some say", "fishermen assert") unless he endorses them;
  if he rejects a view, record his counter-claim. Exclude transitions, plans of the work,
  references to his lost works and rhetorical asides.
- Aim for roughly one claim per 600–800 words: about 25–40 per 20,000-word range. Do not pad.
  Do not duplicate within your range; where a claim recurs, take its clearest statement once.

## Output

Write a JSON array to the output file named in your task, UTF-8, pretty-printed. Each element:

```json
{
  "work": "ha",
  "book": "II",
  "section": "Part 15",
  "label": "Animals with blood all have a heart",
  "claim": "Every animal that has blood has a heart.",
  "quote": "<a verbatim excerpt you have located in inputs/ha.txt>",
  "line": 290,
  "claim_kind": "empirical-generalization",
  "scope": "Aristotle's 'sanguineous' animals (roughly the vertebrates)",
  "measurable_quantities": ["presence of a heart across vertebrate taxa"],
  "candidate_data": "Comparative anatomy compiled in Uberon and the Phenoscape Knowledgebase; Open Tree of Life for taxon coverage.",
  "resolvability_triage": "testable-with-existing-data"
}
```

The example's `label`, `claim`, `line`, `section` and `quote` are placeholders; never copy them.

Field rules:

- `work`: `ha`, `pa` or `ga`.
- `book`: Roman numeral of the book (`I`–`IX`).
- `section`: the `### Part N` heading in force at the quote, copied exactly (e.g. `"Part 15"`), or
  `""` where the book has no part headings.
- `label`: ≤ 90 characters, plain, no trailing period.
- `claim`: one proposition in clear modern English that is **faithful to what Aristotle says**.
  Do not correct him and do not import modern knowledge (no genes, cells, evolution, oxygen);
  a wrong claim is recorded exactly as he made it, which is the point. Keep his hedges ("for the
  most part", "as a rule") and his quantifiers ("all", "no", "only"). Render his groups plainly
  but faithfully: "animals with blood", "bloodless animals", "testaceans (shelled molluscs and
  the like)", "selachians (cartilaginous fishes)", "viviparous quadrupeds". Make it
  self-contained (no "this", "the above", "such animals").
- `quote`: a **verbatim, contiguous** excerpt from the work's text file that states or most
  directly supports the claim, ≤ 70 words, all from one line (one paragraph). Copy exactly,
  including the translator's punctuation and spelling. Never stitch two non-adjacent passages,
  never paraphrase, never add ellipses. **Verify every quote** by searching the file (e.g. with
  `rg -F` on a distinctive fragment, then reading the line) before you write it.
- `line`: the line number in the work's text file where the quote is.
- `claim_kind`: one of
  - `empirical-generalization`: a pattern or fact claimed to hold in nature (anatomy, behaviour,
    life history, distribution), including facts about one named kind of animal;
  - `mechanism`: a causal or physiological process (how digestion, respiration, generation or
    development happens; why a part has the form it has, when the reason is a physical process);
  - `historical-inference`: a claim about what happened in the past (rare in Aristotle);
  - `prediction`: something that, on his account, should (or should not) be observed under given
    conditions (e.g. what follows if a part is removed);
  - `conceptual`: definitional, classificatory or methodological, or a teleological principle not
    itself empirical (e.g. that nature does nothing in vain, that the final cause comes first).
- `scope`: which animals or settings the claim covers, with a modern gloss of his group names in
  parentheses where one is clear (e.g. "cetaceans: dolphin, porpoise, whale").
- `measurable_quantities`: what one would measure to test it (empty array if conceptual).
- `candidate_data`: one sentence naming the **kinds** of modern data that could bear on it, naming
  real, well-known resources where you are confident they exist (e.g. AnAge, PanTHERIA, the
  Amniote Life-History Database, AVONET, FishBase, SeaLifeBase, EltonTraits, AmphiBIO, Phenoscape,
  MorphoSource, GBIF, Open Tree of Life, the Animal Diversity Web). Never invent a dataset name,
  accession or DOI. Use "none known" if none.
- `resolvability_triage`: your first-pass guess, one of `testable-with-existing-data`,
  `testable-with-new-data`, `partly-testable`, `not-empirically-testable`. This is a builder's
  triage, not an assessment; someone else will assess it.

Before finishing, re-open your output file and check that it parses as JSON and that every
`quote` occurs verbatim on line `line` of the named work's text file (after collapsing runs of
whitespace). Report back: the output path, the number of claims per book, and any quotes you could
not verify.
