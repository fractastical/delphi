"""Attention annotation: typed unlock edges, a bounded next action, bounded cost and explicit utilities for ONE Problem version.

It is a separate content-hashed document, pinned to the exact Problem version it describes, because the store cannot hold these
fields (extra='forbid'; SPEC-001 'Known defect'). A change to the Problem makes the annotation STALE and the view stops applying it.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from frontier.models import Digest, Identifier, Model, Ref, Short, Strings, Text, aware_time, canonical, digest
from . import vocab

SCHEMA = "frontier-attention-annotation-0.1"
UnlockKind = Literal["logical_necessity", "empirical_relevance", "proposed_connection"]
ActionType = Literal["proof", "evidence_retrieval", "reanalysis", "simulation", "measurement", "review", "consolidation"]
UnlockRelation = Literal["design_requirement", "theory_challenge"]
assert UnlockRelation.__args__ == vocab.ATTENTION["unlock_relation"]
assert UnlockKind.__args__ == vocab.ATTENTION["unlock_kind"] and ActionType.__args__ == vocab.ATTENTION["action_type"]


class UnlockEdge(Model):
    """Resolving the Problem would inform either another Problem/Claim (`target`) or a named decision (`decision_id`).
    `independent_group` names the result the edge descends from: edges in one group are not additive."""
    kind: UnlockKind
    target: Ref | None = None
    decision_id: Identifier | None = None
    independent_group: Identifier
    provenance: Short
    relation: UnlockRelation | None = None          # WHY it matters on the whiteboard: top-down requirement, or bottom-up challenge to a theory
    reason: Text | None = None                      # in words: which requirement it would settle, or which prediction of which theory it tests

    @model_validator(mode="after")
    def one_end(self):
        if self.relation is not None and not self.reason:
            raise ValueError("An edge with a relation must say why in `reason`")
        if self.relation == "theory_challenge" and (self.target is None or self.target.kind != "Claim"):
            raise ValueError("A theory_challenge edge targets the theory as an exact Claim version")
        if (self.target is None) == (self.decision_id is None):
            raise ValueError("An unlock edge names exactly one of target or decision_id")
        if self.target is not None and self.target.kind not in {"Problem", "Claim"}:
            raise ValueError("An unlock target must be a Problem or Claim version")
        return self


class DecisionModel(Model):
    """utility_status 'unknown' is a first-class answer: no numbers may be present. 'declared' needs prior, utilities and sources."""
    utility_status: Literal["declared", "unknown"]
    description: Short
    unit: Short | None = None
    prior: dict[str, float] | None = None
    utilities: dict[str, dict[str, float]] | None = None
    prior_source: Short | None = None
    utility_source: Short | None = None

    @model_validator(mode="after")
    def coherent(self):
        numbers = (self.unit, self.prior, self.utilities, self.prior_source, self.utility_source)
        if self.utility_status == "unknown":
            if any(x is not None for x in numbers):
                raise ValueError("An unknown-utility decision must carry no unit, prior, utilities or sources")
            return self
        if any(x is None for x in numbers):
            raise ValueError("A declared decision needs unit, prior, utilities, prior_source and utility_source")
        from .voi import check
        check(self.prior, self.utilities)
        return self


class ResourceEstimate(Model):
    unit: Short
    amount: float = Field(gt=0)
    basis: Literal["estimate"]


class BoundedAction(Model):
    action_type: ActionType
    summary: Short
    input_hashes: list[Digest] = Field(min_length=1, max_length=40)
    resource_estimate: ResourceEstimate
    stop_rule: Text
    acceptance_criterion: Text
    reviewer_operator: Identifier


class Annotation(Model):
    schema_version: Literal["frontier-attention-annotation-0.1"] = SCHEMA
    target: Ref
    annotator_operator: Identifier
    created_at: str
    unlocks: list[UnlockEdge] = Field(default_factory=list, max_length=60)
    decisions: dict[Identifier, DecisionModel] = Field(default_factory=dict)
    next_action: BoundedAction | None = None
    limitations: Strings = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self):
        aware_time(self.created_at)
        if self.target.kind != "Problem":
            raise ValueError("An annotation is pinned to a Problem version")
        for e in self.unlocks:
            if e.decision_id is not None and e.decision_id not in self.decisions:
                raise ValueError(f"unlock edge names decision {e.decision_id!r} with no entry in decisions; declare it, even as unknown")
        return self


def make_annotation(body: dict) -> dict:
    """Validate and add the content digest. The digest is integrity, not review or acceptance."""
    a = Annotation.model_validate(body).model_dump()
    return {**a, "annotation_sha256": digest(a)}


def verify(doc: dict) -> dict:
    body = {k: v for k, v in doc.items() if k != "annotation_sha256"}
    a = Annotation.model_validate(body).model_dump()
    if digest(a) != doc.get("annotation_sha256"):
        raise ValueError("annotation digest mismatch")
    return a
