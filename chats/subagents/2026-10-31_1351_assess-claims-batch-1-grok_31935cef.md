# Subagent: Assess claims batch-1 (grok)

- **Parent chat:** [let's do the same thing for mike levin's works that we did for darwin and thomps](../2026-10-31_1314_let-s-do-the-same-thing-for-mike-levin-s-works-that-we-did-f.md)
- **Started:** 2026-10-31 13:51 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 14:01 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `31935cef-bb7e-4c5e-b873-7d00f57200a0`

---

### 2026-10-31 13:51 — Turn 1 (User)

> Read and follow /Users/jdietz/Documents/GitHub/dev/delphisci/books/levin-papers/assessment/INSTRUCTIONS.md exactly. Your input batch is /Users/jdietz/Documents/GitHub/dev/delphisci/books/levin-papers/assessment/inputs/batch-1.json. Write your output to /Users/jdietz/Documents/GitHub/dev/delphisci/books/levin-papers/assessment/raw/grok/batch-1.json. Do not write any other file.

**Assistant:**

I'll follow the Levin assessment instructions and score only the claims in batch 1.

The public simulation code and the papers’ own measurements are enough to score the batch. I’ll write only the batch-1 assessment file.

Scored all 45 claims and wrote them to `books/levin-papers/assessment/raw/grok/batch-1.json`.

Verdicts:
- **resolvable-now:** 3
- **partially-resolvable:** 16
- **needs-new-data:** 20
- **not-empirically-resolvable:** 6

The three resolvable-now claims are active-inference simulation results whose solver is the public SPM morphogenesis routine. Wet-lab results from the planarian, Xenopus tumor, and nicotine papers are only partly checkable from published summaries, because embryo- and animal-level measurements are not deposited.

Hardest to score: the free-energy uniqueness guarantee, which is close to true by how the model is defined; the current SPM demo, which defaults to 16 cells with the bisection path switched off; the planarian head-shape model, whose C++ source was not released; and the Xenopus claim that remote voltage acts through bacterial butyrate and HDAC1, where the incidence contrasts are published and the mediator measurements are not.

_Tools used: GetDynamicTools, Glob, Grep ×10, Read ×5, Shell ×13, UpdateCurrentStep ×5, WebSearch ×7, Write_
