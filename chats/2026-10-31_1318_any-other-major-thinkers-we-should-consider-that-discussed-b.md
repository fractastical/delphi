# any other major thinkers we should consider that discussed bio-math?

- **Started:** 2026-10-31 13:18 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:19 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `233d2f8d-9b51-408f-bf8d-9686cdeca30d`

## Conversation

### 2026-10-31 13:18 — Turn 1 (User)

> any other major thinkers we should consider that discussed bio-math?

**Assistant:**

I'll check which thinkers are already covered so the suggestions don't repeat them.

I should check which thinkers are already covered in math-bio-claims, along with the related books by Darwin, Thompson, and Wolfram, before suggesting other major figures to consider.

Yes. Right now `math-bio-claims/` covers Fisher, Turing, Kimura, Hamilton and Maynard Smith, and the book projects cover Darwin, Thompson and Wolfram. That is almost all population genetics and evolutionary game theory, plus Turing's morphogenesis. Ecology, physiology, epidemiology and scaling are missing entirely. Here are the thinkers I'd add, grouped by the gap each fills.

**Finishing population genetics**
- **Sewall Wright**: adaptive landscapes, F-statistics, the shifting-balance theory. The shifting-balance theory is still disputed, and his long argument with Fisher pairs well with the Fisher claims you already have.
- **J. B. S. Haldane**: a new beneficial mutation fixes with probability about \(2s\), where \(s\) is its selective advantage. He also introduced the cost of selection ("Haldane's dilemma") and Haldane's rule. That mix of proved results and empirical regularities is useful for testing the distinction between theorems and claims.
- **George Price**: the Price equation. It is an exact identity, so it's an easy candidate for a Lean proof, and it underlies Hamilton's rule.
- **John Kingman**: the coalescent, which is proved mathematics and is the basis of modern genome inference.

**Ecology (currently absent)**
- **Lotka and Volterra**: the predator–prey and competition equations. The conserved quantity in the predator–prey model can be formalized in Lean. Lotka's *Elements of Physical Biology* (1925) is public domain in the US, so it could become a `books/` project the way Thompson is.
- **Robert May**: the 1972 result that ecosystems become less stable as they get more complex, and chaos in the logistic map. Mathematically it's a theorem about random matrices, but whether real ecosystems behave that way is contested. That makes it a good case for showing that a proof doesn't establish that organisms satisfy the assumptions.
- **MacArthur and Wilson**: island biogeography, plus Gause and MacArthur on competitive exclusion.
- **Richard Levins**: metapopulation models.

**Physiology, neuroscience and bioelectricity**
- **Hodgkin and Huxley**: the model of how a nerve fires an action potential. It fits the bioelectric claims, and ion channels can be grounded in INDRA.
- **Michaelis–Menten and Hill**: equations for enzyme reaction rates and cooperative binding.
- **John Hopfield (1974)**: kinetic proofreading, a molecular-level claim that fits INDRA well.
- **Arthur Winfree and Yoshiki Kuramoto**: biological clocks and synchronization of oscillators.

**Scaling (follows on from Thompson's chapter on magnitude)**
- **Kleiber, and West–Brown–Enquist**: metabolic rate scales with body mass to the 3/4 power. The empirical exponent and the network-based derivation of it are both disputed, so these would make strong candidates for the assessments and `claim-tests/`. The organism datasets could test them directly.

**Epidemiology and molecular evolution**
- **Kermack and McKendrick**: the SIR model and the threshold theorem (an epidemic spreads only when the basic reproduction number \(R_0 > 1\)).
- **Manfred Eigen**: quasispecies and the error threshold for how much mutation a replicating population can tolerate.

**Development and computation (ties to Wolfram and Thompson)**
- **Gierer and Meinhardt**: local activation with long-range inhibition, which extends Turing's work.
- **Aristid Lindenmayer**: L-systems for modelling how plants grow.
- **Stuart Kauffman**: random Boolean networks and NK fitness landscapes.
- **John von Neumann**: self-reproducing automata.

If I had to pick five, I'd take Wright, Haldane, Lotka–Volterra, May and Hodgkin–Huxley. Together they fill the biggest gaps, and they include both clean proved results that could go to Lean and disputed claims worth assessing. Lotka's book is also the most natural next `books/` project. I can draft key-claim entries for any of these in the existing `key-claims.json` format.

Beyond Fisher, Turing, Kimura, Hamilton, and Maynard Smith, I'm thinking about who else deserves inclusion, grouped by theme, weighing which claims are formally provable and Lean-friendly. Sewall Wright stands out for his shifting balance theory, F-statistics, and adaptive landscapes work, pairing naturally with Fisher's contributions.

Haldane offers strong material with his beneficial mutation fixation probability, cost of selection, and Haldane's rule, while Lotka-Volterra dynamics give a clean provable case with conserved quantities. May's stability-complexity work makes a good contested test case, and Price's equation is a trivially provable identity perfect for Lean. I'm also weighing Eigen's quasispecies theory, Kermack-McKendrick's SIR threshold theorem, Kauffman's NK landscapes tying back to Wolfram, and Lindenmayer's L-systems connecting to the Thompson/Wolfram thread already covered.

Continuing down the list, Gierer-Meinhardt extends Turing patterns through local activation and lateral inhibition, Winfree's biological clocks connect to Kuramoto phase dynamics, and West-Brown-Enquist's 3/4 metabolic scaling law is a great contested-derivation case tying to Thompson's magnitude arguments. I'm also noting Kingman's coalescent and Hardy-Weinberg as proven math trivially formalizable in Lean, plus Wright-Fisher/Moran models, Ewens sampling formula, Nowak's evolutionary dynamics, MacArthur-Wilson island biogeography, Hopfield's kinetic proofreading as a good INDRA fit, and Michaelis-Menten/Hill kinetics, with Fibonacci phyllotaxis already covered by Thompson and Douady-Couder.

Now I'm thinking about book project candidates alongside Thompson's work — Murray's Mathematical Biology, Lotka's Elements of Physical Biology (1925, likely public domain), and possibly Fisher's Genetical Theory of Natural Selection, though I'm unsure about its copyright status since the University of Adelaide hosts it with permission rather than as confirmed public domain, so I should be cautious there and stick with Lotka as the safer claim.

I'm also weighing which topics would fill real gaps in the repo — population genetics is well covered via Wright and Haldane, but ecology, neuroscience/bioelectricity, scaling laws, and epidemiology are largely missing. I want to distinguish candidates with clean, provable results suited for formalization from more contested ones better suited for critical assessment, then present a short recommended list with reasoning, using grouped bullets rather than a table since the content isn't simple short facts.

_Tools used: Shell_
