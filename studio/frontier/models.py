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
KINDS = ("Problem", "Claim", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Event")
Kind = Literal["Problem", "Claim", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Event"]
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


PAYLOADS = {c.__name__: c for c in (Claim, Problem, Evidence, Assessment, Action, Actor, ResourceOffer, Interest, Event)}


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
    return edges
