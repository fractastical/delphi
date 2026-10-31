# Claims, actions, evidence and artifacts

An Action may pin `inputs` to exact Claim and Evidence versions. These become
`uses` edges in the graph. Evidence may pin its producing Action with
`produced_by`; both must target the same Claim or Problem. The database checks
that referenced versions exist, are readable, and satisfy the current-version
policy. Existing records without these optional fields keep their original bytes
and hashes.

Evidence has an explicit declared `relation`: supports, refutes, qualifies,
reproduces, context_only, or unspecified. It retains its distinct evidence kind:
observed, predicted, simulated, formal, or source_assessment. An evidence relation
does not change review status. Claim origin is source_statement, derived,
hypothesis, or unknown; omission means unknown, not measured.

An `artifacts` entry carries a title, SHA256, byte size, media type, role,
availability, licence assertion, and a credential-free HTTPS pointer or matching
`urn:sha256:` identifier. Roles cover inputs, outputs, code, environment,
protocol, logs, certificates and geometry. The store does not fetch URLs, execute
code, inspect files, or establish redistribution rights. Submission continues
to return `artifact_bytes_verified: false`. A later byte-check receipt must say
which bytes were read, how they were obtained and which check ran. A hash alone
does not establish measurement, correctness or replication.

OpenResearch run records fit this path as execution provenance. An adapter must
preserve its actual run and code identifiers and distinguish supervisor-reported
completion from a captured process exit. Output hashes, input hashes, environment
and random seeds must be added from actual artifacts if absent from the run
record. The OpenResearch software licence is not a licence for experiment data.
A local run identifier is not a publicly retrievable artifact; the content-addressed
bundle must travel with the record or its absence must remain explicit.

Count imported records, declared reuse, executed reuse and independently reviewed
reuse separately. Two Action records naming the same Claim show declared reuse.
They do not prove either action ran or benefited. The demonstration must join
actual run receipts and output artifacts to those actions before reporting
executed reuse; a controlled comparison is needed for a claim of benefit.

`ArtifactIndex(store).search()` discovers artifact declarations by literal text,
role and evidence kind, with bounded pages and query-bound cursors. Every result
includes the Evidence version, target, producing action, applicability context,
assumptions, limitations, source dependence and local review status. It respects
the same namespace visibility as record reads. It includes historical versions
and marks whether each remains a head. Repeated bytes in different contexts are
kept separate; the count is declarations, not independent observations. The first
implementation scans stored JSON metadata; large-corpus performance is unmeasured.

The questions whiteboard uses optional Problem `approach`, `scales` and
`context_tags`. `design_goal` asks what a desired capability requires;
`theory_fit` asks whether a model explains known biology. `literature_gap`,
`challenge` and `measurement` connect sources, disagreement and discriminating
tests. Existing `dependencies` link exact records, and Action `inputs` record
reuse. These directions complement each other: a proposed explanation can become
a design constraint, whose failed prediction opens a new challenge. The tags do
not make a recorded question actionable; its acceptance, falsifiers, next action
and stop bounds are still required. Developmental and evolutionary layers are
process contexts rather than spatial length scales.

For printed fish, artifact provenance must distinguish biological dimensions and
mass from display scale, resin volume and deliberately thickened fins. Candidate
selection follows the constraint and simulation results. Printable geometry is
not biological reachability, and a source envelope is not a universal law.
