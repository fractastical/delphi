"""Wire contracts. Schema validity never establishes scientific acceptance."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "frontier-record-0.1"
POLICY = "frontier-independent-review-0.1"
MAX_RECORD_BYTES = 65536
MAX_BUNDLE_BYTES = 2_000_000
MAX_BUNDLE_RECORDS = 100
KINDS = ("Problem", "Claim", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Event",
         "Project", "Annotation")
Kind = Literal["Problem", "Claim", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Event",
               "Project", "Annotation"]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")]
Short = Annotated[str, Field(min_length=1, max_length=3000)]
Text = Annotated[str, Field(min_length=1, max_length=12000)]
Strings = Annotated[list[Short], Field(max_length=40)]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical(value).encode()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def aware_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Ref(Model):
    namespace: Identifier
    kind: Kind
    id: Identifier
    version: Digest


class TimeClaim(Model):
    value: str | None
    basis: Literal["declared", "witnessed", "unknown"]

    @model_validator(mode="after")
    def valid_time(self):
        if self.value is not None:
            aware_time(self.value)
        if (self.value is None) != (self.basis == "unknown"):
            raise ValueError("Unknown times need null values; known times need a basis")
        return self


class Source(Model):
    uri: Short | None
    locator: Short | None
    source_version: Short | None
    content_sha256: Digest | None
    content_available: bool
    access: Short
    license: Short | None


class Claim(Model):
    title: Short
    statement: Text
    context: Text
    assumptions: Strings
    limitations: Strings
    source: Source
    source_record_version: Short | None = None
    prior_review: dict[str, Any] = Field(default_factory=dict)
    origin: Literal["source_statement", "derived", "hypothesis", "unknown"] = "unknown"


ACTIONABILITY = ("acceptance_criteria", "falsifiers", "next_action", "cost_stop_bounds")
Scale = Literal["molecular", "macromolecular", "subcellular", "cellular", "tissue", "organ", "neural",
                "organism", "developmental", "collective", "ecological", "evolutionary"]


class Problem(Model):
    """A sourced question. `completeness` separates having a problem from being able to act on it.

    A curated open-problems register states what is unknown and why it matters; it does not say
    what would settle the question, what would refute an answer, what to do next, or when to stop.
    Those four fields are what an Action needs, and they are the real frontier. Requiring them at
    import time does not create them -- it only keeps sourced problems out of the store. So a
    `recorded` Problem may omit all four, an `actionable` Problem must carry all four, and
    `Store.submit` refuses an Action whose target is still `recorded`. The gap is then a count
    this node can report about itself rather than an absence nobody can see.
    """

    title: Short
    known_state: Text
    question: Text
    # `curated_question` is a question a curator wrote down, with citations the curator attached. It does not say the field states
    # this as an open problem (`sourced_field_open_problem`), nor that the project has this gap (`project_gap`). Added after the
    # register import labelled 250 curator questions as sourced field problems; the existing values are unchanged.
    problem_kind: Literal["project_gap", "computational_open_question", "sourced_field_open_problem", "resolved_scope_correction",
                          "curated_question"]
    novelty_status: Short
    data_access: Text
    completeness: Literal["recorded", "actionable"] = "actionable"
    acceptance_criteria: Strings = Field(default_factory=list)
    falsifiers: Strings = Field(default_factory=list)
    next_action: Text | None = None
    required_capabilities: Strings
    cost_stop_bounds: Text | None = None
    downstream_uses: Strings
    dependencies: list[Ref] = Field(default_factory=list, max_length=30)
    source: Source
    original: dict[str, Any] = Field(default_factory=dict)
    approach: Literal["design_goal", "theory_fit", "literature_gap", "challenge", "measurement", "unknown"] = "unknown"
    scales: list[Scale] = Field(default_factory=list, max_length=12)
    context_tags: Strings = Field(default_factory=list)

    @model_validator(mode="after")
    def actionability(self):
        absent = [f for f in ACTIONABILITY if not getattr(self, f)]
        if self.completeness == "actionable" and absent:
            raise ValueError("An actionable problem needs all of " + ", ".join(absent))
        if len(set(self.scales)) != len(self.scales) or len(set(self.context_tags)) != len(self.context_tags):
            raise ValueError("Repeated problem scales or context tags")
        return self


class ArtifactRef(Model):
    """A declared artifact pointer. A digest in a record is not a byte verification.

    The store never fetches these URIs. Public HTTPS or content-addressed URNs
    avoid exporting a worker's local path or embedding access credentials.
    Availability and licence are assertions by the submitting actor.
    """

    title: Short
    uri: Short
    sha256: Digest
    byte_size: int = Field(ge=0, le=10**13, strict=True)
    media_type: Annotated[str, Field(min_length=3, max_length=150, pattern=r"^[\w.+-]+/[\w.+-]+$")]
    role: Literal["input", "output", "code", "environment", "protocol", "log", "certificate", "geometry"]
    availability: Literal["referenced", "downloadable", "unavailable"]
    license: Short | None = None

    @model_validator(mode="after")
    def artifact_uri(self):
        parts = urlsplit(self.uri)
        if self.uri.startswith("urn:sha256:"):
            if self.uri != "urn:sha256:" + self.sha256 or self.availability == "downloadable":
                raise ValueError("A content URN must match its digest and is not a download URL")
        elif (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
              or parts.query or parts.fragment or any(ord(c) < 33 for c in self.uri)):
            raise ValueError("Artifact pointers need credential-free HTTPS without query/fragment, or a SHA256 URN")
        return self


class Evidence(Model):
    target: Ref
    evidence_kind: Literal["observed", "predicted", "simulated", "formal", "source_assessment"]
    source: Source
    created_time: TimeClaim
    retrieved_time: TimeClaim
    method: Text
    context: Text
    assumptions: Strings
    provenance: dict[str, Any]
    source_dependence: dict[str, Any]
    uncertainty: Text
    limitations: Strings = Field(min_length=1)
    local_id: Short | None = None
    provider_assessment: dict[str, Any] | None = None
    relation: Literal["supports", "refutes", "qualifies", "reproduces", "context_only", "unspecified"] = "unspecified"
    produced_by: Ref | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def target_kind(self):
        if self.target.kind not in {"Claim", "Problem"}:
            raise ValueError("Evidence must pin a Claim or Problem")
        if self.produced_by is not None and self.produced_by.kind != "Action":
            raise ValueError("Evidence produced_by must pin an Action")
        if len({(a.sha256, a.role) for a in self.artifacts}) != len(self.artifacts):
            raise ValueError("Duplicate artifact digest and role")
        return self


DIMENSIONS = ("source_fidelity", "target_fidelity", "applicability", "computational_replay_formal_check", "statistical_adequacy", "independent_replication", "empirical_relevance")


class Dimension(Model):
    status: Literal["unreviewed", "passed", "failed", "not_applicable", "insufficient"]
    reviewer: Identifier
    rationale: Short
    evidence_links: list[Ref] = Field(max_length=30)


class Assessment(Model):
    target: Ref
    policy_version: Literal["frontier-independent-review-0.1"] = POLICY
    decision: Literal["accepted", "disputed", "rejected", "unreviewed"]
    dimensions: dict[str, Dimension]
    independence_rationale: Text
    limitations: Strings = Field(min_length=1)

    @model_validator(mode="after")
    def complete_dimensions(self):
        if set(self.dimensions) != set(DIMENSIONS):
            raise ValueError("All seven named dimensions are required")
        return self


class ActionAlternative(Model):
    label: Identifier
    description: Text
    tradeoff: Text


class ActionOutcome(Model):
    label: Identifier
    criterion: Text
    decision_consequence: Text


class ActionProposal(Model):
    """Reasons and prospective outcomes, never an execution permission or result."""
    intent: Literal["analysis", "simulation", "experiment", "curation", "replication", "formalization", "design", "plan"]
    method: Text
    assumptions: Strings
    alternatives: list[ActionAlternative] = Field(min_length=1, max_length=12)
    expected_information: Text
    decision_context: Text
    expected_outputs: Strings = Field(min_length=1)
    controls: Strings = Field(min_length=1)
    analysis_plan: Text
    outcomes: list[ActionOutcome] = Field(min_length=1, max_length=12)
    selection_basis: Literal["manual", "declared_utility", "forecast", "policy", "exploration"]
    selection_rationale: Text
    limitations: Strings = Field(min_length=1)
    plan_steps: list[Ref] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def coherent(self):
        for rows in (self.alternatives, self.outcomes):
            if len({r.label for r in rows}) != len(rows):
                raise ValueError("Alternative and outcome labels must be unique")
        if (self.intent == "plan") != bool(self.plan_steps):
            raise ValueError("Only plan proposals carry steps; a plan needs at least one step")
        if any(r.kind != "Action" for r in self.plan_steps):
            raise ValueError("Plan steps must pin Action records")
        if len({r.version for r in self.plan_steps}) != len(self.plan_steps):
            raise ValueError("Duplicate plan step version")
        return self


class Action(Model):
    target: Ref
    title: Short
    acceptance_criteria: Strings = Field(min_length=1)
    required_capabilities: Strings
    cost_stop_bounds: Text
    cache_key: dict[str, str]
    inputs: list[Ref] = Field(default_factory=list, max_length=30)
    proposal: ActionProposal | None = None

    @model_validator(mode="after")
    def complete_cache(self):
        if set(self.cache_key) != {"target", "input", "code", "model", "environment", "parameters", "scope", "acceptance_policy"}:
            raise ValueError("Cache key must pin all eight input/policy dimensions")
        if any(not v or len(v) > 1000 for v in self.cache_key.values()):
            raise ValueError("Cache dimensions must be bounded nonempty strings")
        if self.cache_key["target"] != self.target.version or self.cache_key["acceptance_policy"] != POLICY:
            raise ValueError("Cache target/policy must match action")
        if any(r.kind not in {"Claim", "Evidence"} for r in self.inputs):
            raise ValueError("Action inputs must pin Claim or Evidence records")
        if len({r.version for r in self.inputs}) != len(self.inputs):
            raise ValueError("Duplicate action input version")
        return self


class Actor(Model):
    display_name: Short
    operator_identifier: Identifier
    capabilities: Strings
    identity_verification: Literal["declared", "operator_configured"]


class ResourceOffer(Model):
    operator_identifier: Identifier
    capability: Short
    amount: float = Field(gt=0)
    unit: Short
    available_from: str
    available_until: str
    restrictions: Strings = Field(min_length=1)
    terms: Text
    verification_status: Literal["unverified", "declared", "checked"]
    verification_reference: Short | None

    @model_validator(mode="after")
    def window(self):
        if aware_time(self.available_until) <= aware_time(self.available_from):
            raise ValueError("Invalid resource time window")
        if self.verification_status == "checked" and not self.verification_reference:
            raise ValueError("Checked resource requires a reference, still subject to local review")
        return self


class Interest(Model):
    target: Ref
    signal: Literal["following", "can_contribute", "resource_offer", "blocked_by_this"]
    explanation: Text
    downstream_reference: Short | None = None

    @model_validator(mode="after")
    def blocking(self):
        if self.signal == "blocked_by_this" and not self.downstream_reference:
            raise ValueError("Blocking requires a downstream link")
        return self


EventType = Literal["record_proposed", "record_imported", "fork_detected", "review_recorded", "acceptance_changed", "action_ready", "action_leased", "action_running", "action_submitted", "action_reviewed", "action_accepted", "action_disputed", "action_failed", "action_blocked", "action_expired", "action_cancelled"]


class Event(Model):
    event_type: EventType
    target: Ref
    actor: Identifier
    operator: Identifier
    witnessed_at: str
    details: dict[str, Any]


# ---------------------------------------------------------------------------------------------------------------------
# Project and Annotation. Both are ordinary append-only records: they are written only through Store.submit (authenticated
# contributor, issuer == actor), are `proposed` until an independent operator reviews them, and carry no field by which they
# could mark themselves accepted, resolved, validated or causally bridged. A pin is an exact version; membership declares where
# a record is applicable, it never infers a causal link between members.
# ---------------------------------------------------------------------------------------------------------------------
Unsigned = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,8})(\.[0-9]{1,12})?$")]
Decimal = Annotated[str, Field(max_length=40, pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$")]
DottedPath = Annotated[str, Field(min_length=1, max_length=200,
                                  pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_-]+|\[[0-9]{1,4}\]){0,12}$")]
MemberKinds = {"Claim", "Problem", "Action", "Evidence"}
BRIDGE_KINDS = {"Evidence", "Claim"}


class ArtifactPin(Model):
    """Evidence ref plus the sha256 of one of ITS declared artifacts. The store checks the digest is listed in that Evidence
    version's `artifacts`; it never fetches bytes, so this is a pointer check, not a byte verification."""
    evidence: Ref
    sha256: Digest

    @model_validator(mode="after")
    def evidence_kind(self):
        if self.evidence.kind != "Evidence":
            raise ValueError("An artifact pin anchors an Evidence ref")
        return self


class ScaleCoverage(Model):
    scale: Scale
    status: Literal["implemented_model", "source_only", "unimplemented", "unknown"]
    note: Short


class Member(Model):
    ref: Ref
    role: Literal["mission", "subsystem", "evidence", "measurement", "design", "context", "gap"]
    subsystem: Short
    scale: Scale | None = None
    relationship: Literal["supports", "constrains", "depends_on", "informs", "challenges", "implements", "measures",
                          "context_for"]
    applicability: Text   # a DECLARATION of where the member applies, never an inferred causal bridge
    causal_bridge: Literal["none_declared", "assumed", "calibrated"] = "none_declared"
    calibration: Ref | None = None
    rationale: Text
    artifact: ArtifactPin | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.ref.kind not in MemberKinds:
            raise ValueError("A project member pins a Claim, Problem, Action or Evidence")
        if (self.causal_bridge == "calibrated") != (self.calibration is not None):
            raise ValueError("A calibrated bridge needs a calibration ref; any other bridge value must not carry one")
        if self.calibration is not None and self.calibration.kind not in BRIDGE_KINDS:
            raise ValueError("A calibration ref pins Evidence or a Claim")
        if self.artifact is not None and (self.ref.kind != "Evidence" or self.artifact.evidence != self.ref):
            raise ValueError("A member artifact pin must be the member's own Evidence ref plus a digest")
        return self


class Quantity(Model):
    name: Short
    unit: Short
    comparator: Literal["<=", ">=", "==", "<", ">"]
    value: Decimal


class Requirement(Model):
    id: Identifier
    kind: Literal["function", "constraint", "validation", "safety", "non_goal"]
    text: Text
    quantity: Quantity | None = None
    source_member: int | None = Field(default=None, ge=0, le=59)
    stage: Literal["declared", "proposed"] = "proposed"


class OpenQuestion(Model):
    text: Text
    problem: Ref | None = None
    blocks: list[Annotated[int, Field(ge=0, le=59)]] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def problem_kind(self):
        if self.problem is not None and self.problem.kind != "Problem":
            raise ValueError("An open question links a Problem")
        if len(set(self.blocks)) != len(self.blocks):
            raise ValueError("Repeated blocked member index")
        return self


class Project(Model):
    title: Short
    mission: Text
    source: Source
    limitations: Strings = Field(min_length=1)
    scale_coverage: list[ScaleCoverage] = Field(min_length=1, max_length=12)
    members: list[Member] = Field(default_factory=list, max_length=60)
    requirements: list[Requirement] = Field(default_factory=list, max_length=40)
    open_questions: list[OpenQuestion] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def coherent(self):
        scales = [c.scale for c in self.scale_coverage]
        if len(set(scales)) != len(scales):
            raise ValueError("Repeated scale in scale_coverage")
        if len({m.ref.version for m in self.members}) != len(self.members):
            raise ValueError("Repeated member version")
        if any(m.scale is not None and m.scale not in scales for m in self.members):
            raise ValueError("A member scale must be one of the declared scale_coverage scales")
        if len({r.id for r in self.requirements}) != len(self.requirements):
            raise ValueError("Repeated requirement id")
        n = len(self.members)
        if any(r.source_member is not None and r.source_member >= n for r in self.requirements):
            raise ValueError("Requirement source_member is not a member index")
        if any(i >= n for q in self.open_questions for i in q.blocks):
            raise ValueError("Open-question blocks index is not a member index")
        return self


class NamedSubsystem(Model):
    type: Literal["named_subsystem"]
    name: Annotated[str, Field(min_length=1, max_length=200)]


class MeshPart(Model):
    type: Literal["mesh_part"]
    part_id: Annotated[str, Field(min_length=1, max_length=200)]
    artifact_sha256: Digest | None = None


class ImageRect(Model):
    """Normalized rectangle in [0,1]^2 of the artifact image; exact decimal strings, a UI anchor, not a measurement."""
    type: Literal["image_rect"]
    x: Unsigned
    y: Unsigned
    w: Unsigned
    h: Unsigned

    @model_validator(mode="after")
    def inside_unit_square(self):
        from fractions import Fraction
        x, y, w, h = (Fraction(v) for v in (self.x, self.y, self.w, self.h))
        if w <= 0 or h <= 0 or x + w > 1 or y + h > 1:
            raise ValueError("Rectangle must have positive size and lie inside the unit square")
        return self


class EquationSymbol(Model):
    type: Literal["equation_symbol"]
    symbol: Annotated[str, Field(min_length=1, max_length=80)]
    equation_id: Annotated[str, Field(min_length=1, max_length=200)] | None = None


class ParameterPath(Model):
    type: Literal["parameter_path"]
    path: DottedPath


Region = Annotated[NamedSubsystem | MeshPart | ImageRect | EquationSymbol | ParameterPath, Field(discriminator="type")]


class Anchor(Model):
    record: Ref
    artifact: ArtifactPin | None = None
    region: Region | None = None
    frame: Literal["ui_anchor", "declared_biological"] = "ui_anchor"
    frame_declaration: Text | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.record.kind == "Event":
            raise ValueError("Events are transaction receipts and are not annotated")
        if self.artifact is not None and (self.record.kind != "Evidence" or self.artifact.evidence != self.record):
            raise ValueError("An artifact anchor requires the anchored record to be that Evidence")
        if isinstance(self.region, MeshPart) and self.region.artifact_sha256 is not None and (
                self.artifact is None or self.artifact.sha256 != self.region.artifact_sha256):
            raise ValueError("A mesh-part artifact digest must equal the anchored artifact digest")
        if (self.frame == "declared_biological") != (self.frame_declaration is not None):
            raise ValueError("Only a declared_biological frame carries a frame_declaration, and it must")
        if self.frame == "declared_biological" and self.region is None:
            raise ValueError("A declared biological frame needs a region")
        return self


class ProposedEdit(Model):
    """A proposal as data. Nothing here changes the anchored record or artifact."""
    target_path: DottedPath
    proposed: Any
    rationale: Text

    @model_validator(mode="after")
    def bounded(self):
        if len(canonical(self.proposed)) > 8000:
            raise ValueError("Proposed value exceeds 8000 bytes")
        return self


class DesignReview(Model):
    """A falsifiable, authored challenge tied to one exact Project annotation anchor."""
    dimension: Literal["biology", "geometry", "aerodynamics", "genotype_bridge", "manufacturing", "materials",
                      "physiology", "behavior", "ecology", "validation", "other"]
    member_index: int | None = Field(default=None, ge=0, le=59, strict=True)
    evidence_basis: Literal["observed", "source", "simulation", "formal", "assumption", "unknown"]
    scope: Text
    evidence_refs: list[Ref] = Field(default_factory=list, max_length=12)
    alternative: Text
    falsifiable_next_test: Text

    @model_validator(mode="after")
    def evidence_kinds(self):
        if any(r.kind not in {"Claim", "Evidence"} for r in self.evidence_refs):
            raise ValueError("Design-review evidence refs pin Claims or Evidence")
        if len({r.version for r in self.evidence_refs}) != len(self.evidence_refs):
            raise ValueError("Repeated design-review evidence ref")
        return self


class Annotation(Model):
    kind: Literal["comment", "question", "challenge", "proposed_edit"]
    body: Text
    anchor: Anchor
    reply_to: Ref | None = None
    proposed_edit: ProposedEdit | None = None
    design_review: DesignReview | None = None

    @model_validator(mode="after")
    def coherent(self):
        if (self.kind == "proposed_edit") != (self.proposed_edit is not None):
            raise ValueError("A proposed_edit annotation carries a proposed_edit, and only it does")
        if self.reply_to is not None and self.reply_to.kind != "Annotation":
            raise ValueError("reply_to pins an Annotation")
        if self.design_review is not None and (self.kind != "challenge" or self.anchor.record.kind != "Project" or self.reply_to is not None):
            raise ValueError("A structured design review is a challenge anchored to an exact Project version")
        return self


PAYLOADS = {c.__name__: c for c in (Claim, Problem, Evidence, Assessment, Action, Actor, ResourceOffer, Interest, Event,
                                    Project, Annotation)}


class Draft(Model):
    namespace: Identifier
    kind: Kind
    id: Identifier
    issuer: Identifier
    source_uri: Short
    visibility: Literal["public", "private"] = "public"
    predecessor: Digest | None = None
    payload: dict[str, Any]

    @model_validator(mode="after")
    def typed_payload(self):
        PAYLOADS[self.kind].model_validate(self.payload)
        if len(canonical(self.model_dump()).encode()) > MAX_RECORD_BYTES:
            raise ValueError("Record exceeds byte limit")
        return self


class Record(Draft):
    schema_version: Literal["frontier-record-0.1"] = SCHEMA
    created_at: str
    version: Digest

    @model_validator(mode="after")
    def integrity(self):
        aware_time(self.created_at)
        if digest(self.model_dump(exclude={"version"})) != self.version:
            raise ValueError("Record digest mismatch")
        return self


def make_record(draft: Draft, created_at: str | None = None) -> dict:
    body = {**draft.model_dump(), "schema_version": SCHEMA, "created_at": created_at or now()}
    return Record(**body, version=digest(body)).model_dump()


def ref(record: dict) -> dict:
    return {k: record[k] for k in ("namespace", "kind", "id", "version")}


def references(record: dict) -> list[tuple[str, dict]]:
    """Only explicit typed relationships; no inference from free text."""
    p = record["payload"]
    edges = []
    if "target" in p:
        edges.append(("targets", p["target"]))
    for item in p.get("dependencies", []):
        edges.append(("depends_on", item))
    if record["kind"] == "Action":
        for item in p.get("inputs", []):
            edges.append(("uses", item))
        for item in (p.get("proposal") or {}).get("plan_steps", []):
            edges.append(("plans_step", item))
    if record["kind"] == "Evidence" and p.get("produced_by") is not None:
        edges.append(("produced_by", p["produced_by"]))
    for dimension in p.get("dimensions", {}).values():
        for item in dimension["evidence_links"]:
            edges.append(("review_evidence", item))
    if record["kind"] == "Project":
        for m in p["members"]:
            edges.append(("project_member", m["ref"]))
            if m.get("calibration"):
                edges.append(("project_calibration", m["calibration"]))
            if m.get("artifact"):
                edges.append(("project_member_artifact", m["artifact"]["evidence"]))
        for q in p["open_questions"]:
            if q.get("problem"):
                edges.append(("project_open_question", q["problem"]))
    if record["kind"] == "Annotation":
        edges.append(("annotates", p["anchor"]["record"]))
        if p["anchor"].get("artifact"):
            edges.append(("annotates_artifact", p["anchor"]["artifact"]["evidence"]))
        if p.get("reply_to"):
            edges.append(("replies_to", p["reply_to"]))
        for item in (p.get("design_review") or {}).get("evidence_refs", []):
            edges.append(("design_review_evidence", item))
    return edges
