# SPEC-006 — Action proposals, plans and learning

Status: implementation contract. Owner: codex-03. This extends SPEC-003 without
changing scientific acceptance or execution authority. The initial representation
uses an optional typed `Action.proposal`; existing Action envelopes stay valid.

## Three separate decisions

1. Epistemic: what evidence supports a claim, in which context, with what dissent?
2. Allocative: which bounded action is worth funding or attempting next?
3. Operational: which actor is permitted to execute that exact action version?

An Interest is an attributed participation signal, not a vote that makes a claim
true. The coordinator readiness gate and lease authorize work; neither accepts
its result. An independent dimensional review controls acceptance. More agent
identities under the same operator do not establish independence.

## Proposal contract

An Action already pins its target, reusable inputs, acceptance criteria, resource
stop bounds and eight cache dimensions. Its proposal adds intent, method,
assumptions, alternatives, expected information, the affected decision, expected
artifacts, controls, analysis plan and outcome-dependent consequences. Declared
selection reasons and preferences remain distinct from evidence. A probability
is not inferred from these fields: probability models and calibration receipts
remain separate, linked inputs.

An outcome is a named criterion and a consequence for the next decision. A null
or inconclusive result must not disappear because the preferred hypothesis lost.
Outcome labels and alternative labels are unique. These are reviewable plans,
not machine-certified guarantees that the experiment will answer the question.

A plan is an Action proposal with intent `plan` and ordered, exact-version
`plan_steps` pointing to other Actions. It is an addressable, versioned planning
object using the existing Action envelope. It has no executable aggregate
authority: the store refuses to ready or lease it. Individual steps require
their own readiness, resource bounds and leases. There is no implicit scheduler,
automatic conditional branch execution, or budget multiplication.

## Learning contract

The service should eventually export decision episodes containing the available
questions and alternatives at selection time, policy/version, selection
probability if known, chosen action, actual resources, evidence outputs,
evaluation rule and delayed outcomes. Unknown selection probabilities remain
unknown; retrospective attribution must not fabricate a randomized experiment.

Rewards are claims about outcomes under a frozen evaluator, not unqualified
truth scores. Store evaluator/input hashes, held-out checks, uncertainty,
independence and adverse outcomes. A well-supported dead end can count as useful
information. Self-reported success, number of generated claims, or agreement
among copies of one model are insufficient rewards for scientific progress.

Pheromone-like progress signals may decay and guide exploration, but retain the
events and policy behind them. They must not overwrite evidence or become an
implicit truth score. Comparing allocation policies requires matched budgets,
fresh tasks, explicit baselines and a review process. The existing commons trace
has a ceiling and is not evidence of allocation or reinforcement-learning gain.

## ASK correspondence and present limits

The proposal is identified by its Action version; evidence and artifacts retain
their context; changes create new versions; federated imports preserve competing
judgments without importing authority. Execution remains conditional on an
explicit runtime and permission. These choices operationalize part of the
[ASK conceptual model](https://doi.org/10.2139/ssrn.7416579); they do not establish
full conformance or demonstrate scientific productivity gains.

- [x] Typed proposals and plans survive submit/get/export/import unchanged.
- [x] Missing/stale/non-Action plan steps are refused; a plan cannot be leased.
- [ ] A real experimental proposal is linked to its inputs and subsequent run.
- [ ] The website displays alternatives and outcome-dependent next steps.
- [ ] Matched policy evaluation demonstrates learning, or records a null result.

The learning service and democratic budget-allocation mechanisms above remain
design requirements. No trained collective policy, calibrated forecast service,
or empirical swarm advantage is claimed by implementing the proposal schema.
