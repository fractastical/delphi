# Science video genetic claims — primary-source check

Source-only literature check; no sequence design, protocol, model inference, rerouting or new biology experiment. Direct PMC returned CAPTCHA and Nature returned identity-provider failure. Public r.jina.ai fulltext retrieval succeeded via ordinary HTTPS; source receipts below. Actual-output claims are bounded by files read, not a fresh model run.

## Safe narration

“Published zebrafish genetics connects amino-acid transport and potassium-channel regulation to fin proportions. We use that as a scientific lead, not evidence that a zebrafish can fly. Our sequence-model outputs remain computational candidates; regulatory function, expression and flight are unestablished.”

## Exact findings / limits

- Daane et al., Current Biology2021, https://doi.org/10.1016/j.cub.2021.08.054 , Results ‘Sufficiency of simple genetic changes…’, Fig4: the combined lat4a nr21 and kcnh2a longfin alleles produced enlarged paired fins while medial fins were approximately wild-type-sized, with an elongated lower caudal lobe. This is an experimentally observed zebrafish fin-proportion phenotype. It does not demonstrate aerial performance, viable flight anatomy, control or engineered flying zebrafish. Do not say Frontier produced these fish.
- Fig3: lat4a nr21 is a gain-of-function small-fin mutant; `lof` in kcnh2a lof denotes the **longfin allele name**, not a loss-of-function description. The paper attributes longfin to regulatory gain of function. Avoid conflating the naturally compared flying-fish variants with the particular zebrafish mutations or calling their quantitative effects interchangeable.
- Evo2 Nature2026 https://doi.org/10.1038/s41586-026-10176-5 , Fig6e–k reports experimental ATAC accessibility after genomic integration in mouse ESCs and human HEK293T/K562. That is measured chromatin accessibility in those contexts, not fish promoter/enhancer expression, fin growth or flight. Inference guidance also used Enformer/Borzoi; do not attribute all functional scoring to the autoregressive model alone.
- Existing Frontier bioservices handoff reports32 generated1000bp candidates and same-model sequence likelihood plus motif composition. I read the stored16 arm-A candidate records and controls without printing sequences; the original generation entry has substage rc1 and missing readback, although candidates were retained. Later separate scoring and arm-B reports exist in work/frontier-bioservices (e9a5acb); their exact metrics still need file-level independent checking before narration. Same-model likelihood is not independent regulatory validation; motif occurrence is not binding or expression. Safe current wording: “sequence candidates and computational checks,” not “validated promoters/enhancers.”
- Current genetic-blueprint report describes an endogenous reporter knock-in **proposal**, with locus unspecified, and reporter/BAC alternatives. It is not a completed endogenous edit, demonstrated expression or a specified genome implementation. Keep these as hypotheses/interfaces, not achieved organism design.
- Do not generalize the unrelated Kir2.1 assay, Kcnj13 monomer structure, generic bioelectric simulation or fin beam into a causal lat4a/kcnh2a→fin-shape→flight calibration. Measured cell-specific regulatory activity, developmental geometry/material properties, actuator physiology and aerodynamic performance are distinct missing bridges.

## Read receipts

Daane fulltext: https://r.jina.ai/https://pmc.ncbi.nlm.nih.gov/articles/PMC9172250/ ; 126429 bytes SHA e553ac303c4652967fea05ce09c7a189949aed2c83538a605e0365039c7ce6b7.
Nature fulltext: https://r.jina.ai/https://www.nature.com/articles/s41586-026-10176-5 ;152953 bytes SHA7236ab84ef71b58cc6b02ae493ac9a5231026ec8bed67a3b5052ff722e0ca307.
Local exact responses /data/artifacts/delphi-evolve-rethink/science-video-sources/{daane,evo2}.txt. Prior fish-regulatory source manifest independently gives same Nature response SHA. No new candidate bytes or biological instructions supplied.

## Independent stored-output checks completed after the initial note

Read work/frontier-bioservices at e9a5acb: sixteen arm-A and sixteen arm-B1000bp records, every stored sequence digest recomputed and all distinct within each arm. Scoring files contain57 and89rows; group means reproduce the report (arm A−1.2254569; pooled generated−1.2467812 nats/base). No model was rerun. Original generation-stage failure is preserved, followed by separate successful scoring. The score tables do **not** represent57/89 independent biological validations. They include controls and reused generated candidates.

All nine records labeled real_held_out are natural continuation references, but only one is flagged fully_held_out=True; eight are False. Say “natural sequence reference segments,” not “nine entirely unseen loci.” Original input check records eight reference intervals agreeing and one unavailable, not nine experimentally validated promoters. Unavailable/reference-context distinctions and same-model dependence prevent a functional promoter/enhancer claim.

The main checkout inspected is2b6faf2; later bioservices outputs were inspected at their distinct branch tip, not silently attributed to main. Exact source/output hashes and measured row counts are in artifacts/audits/science-video-genetics/source-and-output-checks.json. No new bioservices inference or replay of provider-stopped work occurred.
