# Pilot prompt template

The runner sends a fresh stateless OpenRouter request for each scheduled actor turn (temperature 0, maximum 400 output tokens, pinned seed per replicate, price-sorted provider routing). It uses this system instruction for all arms and repeats:

> You are one analyst in a controlled public-data science evaluation. Use only the supplied public input packet and its deterministic calculator/unit-algebra outputs. Do not browse, call other models, inspect files, or introduce facts that are not in the packet. Return one JSON object matching the response contract exactly, with both task objects. Cite each task by the DOI string in the packet. Choose only a `decision_code` listed in the packet. Do not add markdown, quotations, confidence claims, or explanatory prose outside the JSON.

Each user message contains, in order:

1. `condition_id`, `replicate_id`, `turn_id`, and the actor role.
2. The identical full `public_input_packet.json` for every arm.
3. If the condition permits it, the exact JSON text and SHA-256 of prior pinned response artifacts. Single-analyst turns see their own earlier responses. Isolated specialists see no earlier response. Collaborating specialists see the prior specialists' responses in order. Rendered user prompts above 9,000 UTF-8 bytes are rejected before a request is sent.
4. The instruction to independently evaluate both tasks, use any included prior notes critically, and choose a next action in each `decision_code` field.

The role labels are:

- `single_analyst`: cover both tasks and integrate all evidence directly.
- `quantitative_analyst`: attend to the rates, units, arithmetic, and uncertainty.
- `source_auditor`: attend to what was measured, the experiment, and the boundary of its claims.
- `model_coupler`: attend to the mapping from measured quantities to model inputs and the next evidence needed.

All roles receive the whole packet and the same tools. Roles differ only in emphasis. The collaboration treatment changes only whether other actors' pinned artifacts are included; it does not add source information or tools.
