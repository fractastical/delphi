# Motivation, prior art and how we differ

Companion to https://frontier.morphoswarm.ai/#/about/inspirations

## Why design a whole organism

Designing one forces every model to meet every other one. The gaps that appear are a map
of what is unknown, and that map is useful whether or not the fish ever flies. We treat
**the gap list as the scientific output**, not as an embarrassment to be smoothed over.

## Why Lean is the foundation

Every other capability depends on laws stated exactly, with their conditions attached.
Lean makes the assumptions explicit and checks the reasoning for **every** value
satisfying them, not just the ones that were plotted. Once a law is formalised, solvers
can use it, generators can be constrained by it, and a second project can reuse it without
re-deriving or misreading it.

The honest scale check: what is formalised so far is textbook-level — similarity scaling,
unit bookkeeping, a beam bound, steady diffusion. These are not yet biological mechanisms.
Their value today is as a worked pattern for how a law, its assumptions and its checks are
stored, and as the base that harder laws will use.

## What we build on

- **Form, function and development.** Observable biological form connects to mathematical
  mechanism; evolutionary plausibility stays a question requiring evidence. Darwin's own
  discussion of flying fish is one of the project's cited sources.
- **Multiscale mechanobiology.** A body of work treats forces, cell behaviour and tissue
  structure as one connected problem rather than three. That framing shapes how we model a
  fin, which must grow, carry load and move fluid at once. Transferring any such model to
  a fish still needs its own calibration — which is exactly why our coupling layer refuses
  the transfer until one exists.
- **Knowledge that carries its context.** The ASK framing motivates addressable,
  traceable, contestable knowledge whose applicability travels with it. We apply that
  discipline to design actions and computational artifacts, not only to assertions.
- **Generative models of mechanism.** Physics-informed diffusion and simulator surrogates
  show how forward simulation can train a generative model. Structure prediction makes the
  same point we keep making: many candidates, then filter and test. Generators propose;
  equations, independent checks and experiments decide.
- **Computationally designed organisms.** Organisms designed in simulation and then built
  are the precedent for the loop we want to make routine — with the evidence trail kept.
- **Open, contestable claim networks.** The idea of a claim as a record with conditions,
  and of nanopublications as one import format whose provenance we preserve.

## How we differ

1. **Refusal is a first-class result.** Most pipelines connect models and hope. Ours
   publishes the junctions it will not make and why: of 13 proposed couplings, **4 are
   refused and 5 run only as labelled assumptions**. No calibration is registered today,
   so every cross-scale bridge is refused or assumption-level.
2. **Mechanically checked laws under the design, not around it.** The solver's conflict
   certificate is itself checked by Lean, and a corrupted certificate is rejected.
3. **The record refuses to accept.** There is no accept tool. Proposing returns
   `proposed`. Review and identity are separable from the record by design.
4. **Receipts everywhere, including for failures.** Nine failed GPU jobs, a quota refusal,
   an unconverged design variant and a stopped protocol are all published.
5. **The gap map is the product.** A design that exposes which measurement would most
   reduce uncertainty is more reusable than a design that claims to be finished.

## What a flying fish is, in this project

An **engineering candidate**. Its geometry, equations and simulations can be inspected.
A viable engineered organism has not been established, and reachability from a halfbeak
ancestor is explicitly listed as unestablished with no evolutionary model attached.
