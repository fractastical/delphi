# Subagent: Claude: open top-5 thinkers

- **Parent chat:** [Math-meets-biology thinkers, theorem claims as nanopubs](../2026-10-30_1844_math-meets-biology-thinkers-theorem-claims-as-nanopubs.md)
- **Started:** 2026-10-30 19:07 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-30 19:08 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `85cecfc3-bffe-4046-8a78-c88711f17d66`

---

### 2026-10-30 19:07 — Turn 1 (User)

> Answer from your own knowledge; do not read or edit any files and do not use tools unless you need to check a fact.
> 
> Question: Among the major thinkers at the intersection of mathematics and biology, which 5 have the most testable hypotheses or claims that could reach the status of theorems? Choose the thinkers yourself; there is no candidate list.
> 
> Reply with a ranked list of 5. For each give: the thinker, their key claim(s), why those claims are testable, and how close they are to theorem status (already proved within a model, provable, or open), plus the strongest caveat. Then one sentence naming any famous figure you deliberately left out and why. Keep it under 400 words.

**Assistant:**

1. **Ronald Fisher**
   - **Key claims:** The fundamental theorem of natural selection says the rate at which mean fitness rises equals the additive genetic variance in fitness. The Fisher–KPP equation predicts that advantageous genes spread as travelling waves.
   - **Why testable:** Both claims make quantitative predictions you can check in experimental populations and in measured spread rates.
   - **Status:** Proved within a model. Price (1972) and Ewens showed the fundamental theorem is exact once it is read as the "partial change" due to selection. Wave speeds for the Fisher–KPP equation are rigorous theorems.
   - **Caveat:** Read literally as "mean fitness always rises," the fundamental theorem is false. It holds only under Fisher's narrower reading.

2. **Motoo Kimura**
   - **Key claims:** Most molecular evolution is neutral. A neutral mutation fixes with probability 1/(2N), and the substitution rate equals the mutation rate.
   - **Why testable:** These give concrete predictions about polymorphism and divergence data, such as molecular-clock behaviour and the HKA and McDonald–Kreitman tests.
   - **Status:** The fixation formulas are proved theorems of diffusion theory. The empirical claim that most evolution is neutral is open.
   - **Caveat:** Large genomic datasets show widespread selection and linked selection, which undercuts strict neutrality.

3. **Alan Turing**
   - **Key claim:** Two diffusing chemicals that react with each other can make a uniform state unstable and produce spatial patterns, so-called diffusion-driven instability.
   - **Why testable:** The model specifies conditions on diffusion rates and predicts how wavelengths scale. These have been seen in the CIMA chemical reaction (1990) and in digit patterning in mice (Sheth et al., 2012).
   - **Status:** The linear instability is a proved theorem. What happens nonlinearly once the pattern forms is partly proved and partly open.
   - **Caveat:** Even when an organism matches the pattern, that doesn't prove a Turing mechanism made it. Other mechanisms can produce similar patterns.

4. **W. D. Hamilton**
   - **Key claim:** Hamilton's rule: an altruistic trait is favoured when rB > C, where r is relatedness, B the benefit to the recipient and C the cost to the actor.
   - **Why testable:** You can estimate r, B and C in the field, for example in social insects or in cooperating microbes.
   - **Status:** Derived via the Price equation, the rule is a provable identity in general form. It also holds exactly in the special case of additive, weak selection.
   - **Caveat:** In its general form it is close to a tautology and doesn't predict much. Nowak, Tarnita and Wilson (2010) argued it adds little beyond standard population genetics.

5. **Manfred Eigen**
   - **Key claims:** Quasispecies theory and the error threshold: above a critical mutation rate, roughly the inverse of genome length, genetic information is lost.
   - **Why testable:** It predicts limits on how large RNA virus genomes can get, and that drugs raising the mutation rate could push a virus to extinction ("lethal mutagenesis").
   - **Status:** The threshold is proved for single-peak fitness landscapes.
   - **Caveat:** The sharp threshold disappears on more realistic, smoother landscapes, and the lethal-mutagenesis evidence is mixed.

I deliberately left out D'Arcy Thompson because his work on growth and form is brilliant geometric description, not a set of hypotheses that could become theorems.

I should answer directly within the word limit, and no tools are actually needed here. I'm leaning toward Fisher's fundamental theorem of natural selection as the example to discuss, noting its history through Price and Ewens' more restricted interpretation.

Other candidates worth weighing: Kimura's neutral theory with its fixation probability formula from diffusion models, Turing's reaction-diffusion instability (later confirmed in chemical reactions and mouse digit patterning), Hamilton's rule derivable via the Price equation (though contested as tautological), and Eigen's error threshold/quasispecies model. I'll also consider Maynard Smith's ESS, Lotka-Volterra, or the Kingman coalescent, but settle on ranking Fisher, Kimura, Turing, Hamilton, and Eigen as the strongest set, while noting D'Arcy Thompson's geometric work as more descriptive than hypothesis-driven.
