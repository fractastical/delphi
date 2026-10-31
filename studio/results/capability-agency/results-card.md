# Capability and collaboration pilot

**Design.** Three repeats compared one serial analyst, isolated specialists, and specialists sharing pinned response artifacts. Every role received the same two public-source tasks and deterministic calculations. The measured construct was evidence synthesis and verification, not discovery: the packet itself stated the source fit, stiffness range, and measurement method. [V3 preregistration](preregistration-v3.json)

**Result.** All 27 V3 requests returned valid JSON. Every individual answer and every condition-by-repeat aggregate scored **16/16** under the frozen deterministic rubric. The three condition means were equal at **16/16**; no collaboration or agency advantage was measured. This is a ceiling result on an answer-explicit pilot, not a scaling result.

**Communication check.** The run passed 9 pinned prior artifacts to the serial analyst, 9 peer artifacts to collaborating specialists, and none to isolated specialists. The communication treatment executed, but the score ceiling left no room to distinguish it.

**Resource accounting.** V3 used 53,802 reported tokens. The separate V2 attempt used 49,626 tokens across 27 HTTP 200 requests, but all 27 were truncated by `MAX_TOKENS` and scored zero; do not pool V2 with V3. The neutral JSON configuration check used 31 reported tokens on its successful attempt; two earlier HTTP 400 attempts returned no usage metadata. Total known Google API usage is 103,459 tokens across 57 requests, including smoke attempts. **USD spend is unknown** because no billing meter was available.

**Sources and receipts.** [Growth paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7864885/) · [fin mechanics paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868929/) · [V3 results and per-call receipts](runs/capability-agency-pilot-20261031-v3/post_run_summary.json) · [V2 null-run receipt](runs/capability-agency-pilot-20261031-v2/post_run_summary.json) · [neutral smoke receipt](neutral_smoke_summary.json)
