# 90-second pitch — agentic engineering, end to end

**Release pitched:** `12eb390` on `codex/frontier-demo-20261031`, the **public deployed
release** — live at `https://frontier.morphoswarm.ai/` (HTTP 200), API `{"mode":"live",
"service":"delphi-frontier","status":"ok"}`. **Not `origin/main`.**

**Live counts, with their receipt.** `POST /v1/read/search`, cursor-paginated at limit 50:
**912 Claims (19 pages), 261 Problems (6 pages), 6 Evidence, 5 Actions.** Re-run before
presenting; these move.

---

## The script

> Take a concrete engineering goal: **design an evolutionarily possible flying fish.**
>
> An agent turns that into **sourced constraints** — wing loading, aspect ratio, launch speed,
> longitudinal stability — each tied to the paper it came from and the population it was measured
> over. Where no number exists, the constraint says so instead of inventing one.
>
> Those constraints drive **models and simulations**, and the simulations produce **artifacts**:
> candidate geometries, glide traces, reaction-diffusion fields, mesh files you could take to a
> printer. Every artifact carries its inputs.
>
> Checking the candidates **produces new open problems** — the gaps the constraints couldn't
> close. Those go back into the store as typed Problems, each carrying what would settle it,
> what would refute it, and when to stop.
>
> And the evidence is **reusable across projects**, because it's stored as records rather than
> prose. The same store holds **912 claims and 261 open problems** right now.
>
> Attention is the scarce resource, so it's modelled explicitly: what's known, what's open, what
> an answer would unlock, and what it would cost.
>
> On coordination we follow the organisers' own regime map. Where one channel dominates, they
> found coordination buys interpretation, provenance and auditability — not better
> discrimination. **That is what we built and that is all we claim.**

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
