# MorphoSwarm Studio — judge and teammate dossier

A crawlable, plain-text summary of what this system is, how it was built, what it
measured, and what it does **not** establish. Written to be combined with write-ups
from other team members.

**Live site:** https://studio.morphoswarm.ai · **Repository:** https://github.com/kganjam/delphi-frontier
· **Agent endpoint (MCP):** `https://studio.morphoswarm.ai/mcp`

Every number in these files was read from the site's own published data snapshot
(`site/data/snapshot.json`, fetched over HTTPS from the live site on 2026-11-01,
snapshot label `7d83f2d56c3b`) or from a receipt file named beside the number. Where
a figure is unknown, these pages say unknown rather than estimating it.

## Read one file instead

**[SUMMARY.md](SUMMARY.md)** consolidates pages 01 to 10 below into a single document, with
the full measured accounting of tokens, agents, models, commits and compute. If you only
open one file, open that one.

## Contents

| File | What it covers |
|---|---|
| [01-how-the-system-was-built.md](01-how-the-system-was-built.md) | Architecture, the build process, who built what, the specs, the open goal list |
| [02-resources-and-compute.md](02-resources-and-compute.md) | GPUs, CPUs, model calls, telemetry, and the costs we cannot account for |
| [03-what-the-system-does.md](03-what-the-system-does.md) | The product: studio, frontier, knowledge, evidence, MCP |
| [04-motivation-and-prior-art.md](04-motivation-and-prior-art.md) | Why organism design, why Lean, what we build on, how we differ |
| [05-lean-for-biology.md](05-lean-for-biology.md) | The formal core: five proof families, mutants, receipts, limits |
| [06-simulations-across-scales.md](06-simulations-across-scales.md) | 31 recorded runs across 9 scales, and the coupling layer that refuses bridges |
| [07-evidence-and-validation.md](07-evidence-and-validation.md) | What was actually checked, what failed, and the review-correction ledger |
| [08-rubric-evidence-map.md](08-rubric-evidence-map.md) | Each judging criterion mapped to specific artifacts, with the gaps stated |
| [09-resources-and-acknowledgements.md](09-resources-and-acknowledgements.md) | People, partners, open-source code, source texts, data and compute — the resources this work is built on |
| [10-agent-and-compute-usage.md](10-agent-and-compute-usage.md) | Measured agent, GPU, CPU and model usage: who ran what, and what is not measured |
| [11-models-and-sponsor-services.md](11-models-and-sponsor-services.md) | Every biological model, LLM and sponsor service actually called, each with a receipt |
| [12-limbless-mouse.md](12-limbless-mouse.md) | A sourced answer to a judge's question: how would you make a limbless mouse? |
| [ASKS.md](ASKS.md) | Request tracker: every request this session, open items first, with status |

The live design-space version of page 12, with the route map and three computed studies, is at
**https://studio.morphoswarm.ai/#/studio/limbless-mouse**.

## The one-paragraph version

Biological engineering spans molecules to ecosystems, and the models at each scale were
built by different communities with incompatible units, assumptions and contexts. We
built a shared workspace where a design goal — engineer toward a flying fish — forces
those models to meet, and where every junction is either checked, labelled as an
assumption, or **refused**. Underneath it is a Lean 4 proof base so that the laws being
reused are stated exactly and checked mechanically. Around it is a record layer where
claims carry their conditions and review status, and an MCP endpoint so other agents can
read and contribute. The flying fish is an engineering candidate, not a viable organism;
the value we claim is the method, the evidence trail, and the map of what is missing.

## What we do not claim

- No biological validation. No organism was built, and no wet-lab experiment was run.
- No measured advantage for multi-agent over single-agent work. We ran no controlled arm.
- No calibrated bridge between biological scales exists today; every cross-scale coupling
  is refused or labelled assumption-level.
- Total provider spend and total model usage are unknown; only named receipts are reported.
