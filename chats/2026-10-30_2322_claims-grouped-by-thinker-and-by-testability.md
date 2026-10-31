# Claims grouped by thinker and by testability

- **Started:** 2026-10-30 23:22 UTC-4 (EDT)
- **Last activity:** 2026-10-30 23:32 UTC-4 (EDT)
- **User messages:** 2
- **Subagents:** 0
- **Transcript ID:** `e1b218ed-6945-42cf-9dc6-871a2d416134`

## Conversation

### 2026-10-30 23:22 — Turn 1 (User)

> use delphi_graph to group claims by thinker."

**Assistant:**

I need to group claims by thinker using delphi_graph, so let me first check the tool's schema to understand how it works.

Claim graph grouped by thinker (snapshot built 2026-10-31 03:09, 889 claims total):

| Thinker | Claims | Mean truth | Mean disagreement | Mean testability | Published | Statuses |
|---|---|---|---|---|---|---|
| Stephen Wolfram | 330 | 0.597 | 0.117 | — | 0 | 330 untested |
| D'Arcy Wentworth Thompson | 291 | 0.497 | 0.140 | 0.627 | 0 | 291 untested |
| Charles Darwin | 247 | 0.684 | 0.105 | 0.632 | 247 | 247 untested |
| Motoo Kimura | 5 | 0.905 | 0.046 | — | 5 | 4 proved, 1 untested |
| John Maynard Smith | 5 | 0.963 | 0.038 | — | 5 | 5 proved |
| Ronald A. Fisher | 4 | 0.954 | 0.042 | — | 4 | 4 proved |
| W. D. Hamilton | 4 | 0.774 | 0.107 | — | 4 | 2 proved, 2 refuted |
| Alan Turing | 3 | 0.762 | 0.150 | — | 3 | 1 proved, 1 partial, 1 untested |

Observations:

- The three book-extraction projects (Wolfram, Thompson, Darwin) account for 868 of 889 claims; only Darwin's are published to the production registry. Wolfram and Thompson are still entirely unpublished drafts.
- The `math-bio-theorems` thinkers (Kimura, Maynard Smith, Fisher, Hamilton, Turing) have the highest mean truth scores and lowest model disagreement, consistent with their claims being formal theorems rather than prose mechanisms.
- Thompson's claims have the lowest mean truth (0.497) and the highest disagreement among the large groups, so that set is the most contested by the models.
- Hamilton is the only thinker with refuted claims (2 of 4).
- Testability scores only exist for Thompson and Darwin; Wolfram and the theorem claims have none yet.

Truth scores here are model-derived and unpublished, so they reflect the local `docs/claims.json` snapshot rather than nanopub-backed assessments.

_Tools used: GetDynamicTools, delphi_graph_

### 2026-10-30 23:24 — Turn 2 (User)

> now tesatability?

**Assistant:**

I want to understand testability patterns, so I'll query the graph sorted by testability to find top claims, then group by kind and by work to see how testability varies across categories.

Testability is only scored for the two book projects, Darwin (0.632 mean) and Thompson (0.627 mean); Wolfram and the math-bio theorem claims have no testability scores yet. Within those two, the picture by claim kind:

| Kind | Claims | Mean testability | Mean truth |
|---|---|---|---|
| mathematical-law | 67 | 0.708 | 0.580 |
| empirical-generalization | 173 | 0.696 | 0.658 |
| historical-inference | 61 | 0.669 | 0.631 |
| prediction | 91 | 0.610 | 0.498 |
| mechanism | 156 | 0.551 | 0.508 |
| conceptual | 51 | 0.359 | 0.522 |

Quantitative laws and concrete empirical generalizations score most testable; mechanisms and especially conceptual claims least.

Top 10 most testable claims (all 889, sorted by testability):

| Testability | Truth | Claim | Thinker |
|---|---|---|---|
| 0.977 | 0.015 | Perissodactyls more closely related to hares/rabbits than other ungulates (`thompson1917-ch17-13`) | Thompson |
| 0.946 | 0.950 | Human stature: fast in infancy, steady in childhood, quickens in teens (`thompson1917-ch03-05`) | Thompson |
| 0.945 | 0.020 | Denudation of the Weald implies ~300 My since the late Chalk (`darwin1859-ch09-03`) | Darwin |
| 0.935 | 0.300 | Parahippus is a divergent offshoot, not on the line to Equus (`thompson1917-ch17-15`) | Thompson |
| 0.930 | 0.120 | Arizona tree rings show a 150-year climate periodicity (`thompson1917-ch03-24`) | Thompson |
| 0.921 | 0.805 | Eggs are prolate spheroids, never oblate (`thompson1917-ch15-01`) | Thompson |
| 0.921 | 0.815 | Human/anthropoid skulls show divergent, not linear, change (`thompson1917-ch17-17`) | Thompson |
| 0.906 | 0.935 | Boys' and girls' growth-velocity curves differ mainly in phase (`thompson1917-ch03-08`) | Thompson |
| 0.902 | 0.045 | Chromosome numbers mostly lie between 6 and 16 (`thompson1917-ch04-13`) | Thompson |
| 0.898 | 0.795 | Weight varies as the cube of linear dimensions during growth (`thompson1917-ch03-07`) | Thompson |

Notable pattern: several of the most testable claims are also the ones models rate most likely false (Weald denudation at 300 My, Perissodactyl–Leporidae affinity, chromosome numbers 6–16, 150-year tree-ring cycle). High testability plus low truth marks claims that have effectively been tested by later science and failed, which makes them good candidates for an explicit `refuted` status rather than `untested`. Conversely, high-testability, high-truth claims (stature growth curve, sex differences in growth velocity, cube law) are the cheapest to confirm against modern datasets.

Also worth noting: the two logarithmic-spiral claims (`thompson1917-ch11-08`, `-10`) are highly testable (0.89) but have the largest model disagreement in this list (0.55 and 0.49), with GPT-5.6 Sol at ~0.23 and Grok 4.7 at ~0.75, so they are the clearest cases where actually measuring shells would settle a live disagreement.

_Tools used: delphi_graph ×3_
