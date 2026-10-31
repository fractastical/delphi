# 90-second pitch — MorphoSwarm Frontier: a design studio on a shared scientific frontier

**Release pitched:** `12eb390` on `codex/frontier-demo-20261031`, the **public deployed
release** — live at `https://frontier.morphoswarm.ai/` (HTTP 200), API `{"mode":"live",
"service":"delphi-frontier","status":"ok"}`. **Not `origin/main`.**

**Live counts, with their receipt.** `POST /v1/read/search`, cursor-paginated at limit 50:
**912 Claims (19 pages), 261 Problems (6 pages), 6 Evidence, 5 Actions.** Re-run before
presenting; these move.

---

## The script

> **MorphoSwarm Frontier is a design studio sitting on a shared scientific frontier.**
>
> The foundation is **Delphi** — the claims and evidence layer. **912 claims and 261 open
> problems**, live right now, each a typed record with its source and its scope rather than a
> paragraph of prose.
>
> The studio is where you bring a design goal. Our **featured project is a flying fish**: can you
> design one that is *evolutionarily* possible, not merely aerodynamic?
>
> An agent turns that goal into **sourced constraints** — wing loading, aspect ratio, launch
> speed, longitudinal stability — each tied to its paper and to the population it was measured
> over. Where no published number exists, the constraint says so rather than inventing one.
>
> Constraints drive **models and simulations**, which produce **artifacts**: candidate geometries,
> glide traces, reaction-diffusion fields, print-ready meshes. Every artifact carries its inputs.
>
> Checking candidates **generates new open problems** — the gaps the constraints could not close.
> Those return to the frontier as typed Problems carrying what would settle them, what would
> refute them, and when to stop.
>
> And because it is all records, **the evidence is reusable by the next project**. The flying fish
> is one study on a frontier built to hold many.
>
> Attention is the scarce resource, so we model it: what is known, what is open, what an answer
> would unlock, what it would cost.
>
> On coordination we follow the organisers' own regime map — where one channel dominates, it buys
> provenance and auditability rather than better discrimination. That is what we built, and all we
> claim.

**~215 words ≈ 87 s.**

## On screen, and what it rests on

| beat | artifact | status |
|---|---|---|
| live store | `frontier.morphoswarm.ai`, API healthy | **verified**, HTTP 200 |
| 912 claims / 261 problems | `POST /v1/read/search`, paginated | **verified with receipt**; re-run before the room |
| constraints | `exocoetid_check.py`, 8 constraints, each with its derivation population | **verified**: 71 tests exit 0 |
| simulations | 8 `.mp4` incl. `glide_fixed_launch`, `rd_fields`, `fin_mechanics`, `delta_notch_replay` | **present on the release**; I have not viewed them |
| geometry | **12 STL mesh files** — `A-precursor-short-fin`, `B-two-wing-glider`, `C-four-wing-glider`, plus stands, designs and renders | **files exist. NO PHYSICAL PRINT HAS OCCURRED.** Say "mesh files ready to print", never "printed forms" |
| attention | `attention/` package — profiles, links, forecast, ledger | **present on the release** |
| open problems | 261 live, typed | **verified with receipt** |

## Wording rules

- **Never "printed forms" or "three printed parts".** Nothing has been printed. The honest phrase
  is *"print-ready mesh files"*.
- **Never quote a test-function count as passing tests.** Cite a run: the constraint checker is
  *71 tests, exit 0, re-run from the durable copy*.
- **Live counts need a fresh receipt.** They change; an old number is a wrong number.
- **No swarm or collective gain assertion.**
- **Do not pitch the refutation ledger as the product**, and do not say "not one novelty claim
  survived". The ledger is how we work, not what we sell.
- Where a constraint rests on a source read only at abstract level, the output says so. That is a
  feature; present it as one.

## Framing rules

- **The product is MorphoSwarm Frontier**: a **design studio** plus a **shared scientific
  frontier**. Lead with that.
- **Delphi is the foundation** — the claims and evidence layer the studio stands on.
- **Flying Fish is the FEATURED PROJECT, not the platform's scope.** It demonstrates the loop;
  it does not define it. If a listener leaves thinking we built a fish simulator, the pitch
  failed.
- **Darwin, Thompson and Wolfram are optional secondary lenses**, available if a question invites
  them. They are **not** the thesis and should not open the pitch.
- The loop is the thesis: **goal → sourced constraints → models and simulations → artifacts →
  new open problems → evidence reusable by the next project.**
