# Biology and model execution usage

[`results/resources/bio-model-usage.json`](../results/resources/bio-model-usage.json) is a receipt-bounded inventory of selected biology-related model, simulation, embedding, review, and speech executions. It names the provider/model, observed status, recorded usage, and exact evidence/result file hashes where available.

## Reading the ledger

- Provider execution status and scientific outcome are separate. For example, the first Evo2 smoke job reached provider state `COMPLETED`, while its runner result was `failed`; the first NCA comparison completed computation but passed 0 of 48 design-target predicates.
- A listed count is scoped to its receipt. The 49 Gemini embedding requests cover the discovery index; four Gemini bioservices calls cover the separate protocol/data-access review. The audit's two smaller per-model ledgers are subsets of that four-call record and are not counted again.
- One Nebius Scientific AI OpenFold2 operation succeeded for a source-native zebrafish Kcnj13 monomer. Its receipt reports `upstream-source-not-nim`, so it is not BioNeMo/NIM use. Its monomer prediction and model-internal confidence do not establish ion-channel function or phenotype.
- The local ESM2 record is a 256-row CPU pilot. The 6,789 variants refer to the matched source assays, not the number scored by that pilot.
- BETSE, Morpheus, and OpenMM entries are simulations, not pretrained-model inference. Their controls or successful process exits do not establish biological validity or molecular-to-tissue transfer.
- MiniMax covers seven new TTS API calls for the final video revision only; reused audio is excluded. No spend value is inferred.
- BioNeMo/NIM execution remains unestablished in this receipt scope. Actual billing and total provider-wide LLM usage remain unknown.

The ledger is intentionally not a project-wide compute or cost report. See [`hackathon-usage.json`](../results/resources/hackathon-usage.json) for the broader resource snapshot; its own scopes and limitations still apply.
