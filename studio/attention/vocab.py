"""Independent source vocabularies. Values keep the vocabulary they came from; nothing is silently translated.

STORE    : read from frontier.models at import time, so it cannot drift from the store.
REGISTER : the morphoswarm open-problems register's own labels (carried in Problem.original.register_record).
ATTENTION: this layer's own labels.
`translate` refuses unless an explicit entry exists in MAPPINGS; MAPPINGS is empty on purpose.
"""
from __future__ import annotations

from typing import get_args

from frontier import models as M


def _lit(model, field):
    return tuple(get_args(model.model_fields[field].annotation))


STORE = {
    "problem_kind": _lit(M.Problem, "problem_kind"),
    "completeness": _lit(M.Problem, "completeness"),
    "evidence_kind": _lit(M.Evidence, "evidence_kind"),
    "signal": _lit(M.Interest, "signal"),
    "verification_status": _lit(M.ResourceOffer, "verification_status"),
    "assessment_decision": _lit(M.Assessment, "decision"),
    "event_type": tuple(get_args(M.EventType)),
}
REGISTER = {"importance": ("foundational", "significant", "specialist"), "tractability": ("near-term", "medium-term", "long-term")}
# DECLARED direction, a policy assumption of this layer, not a register fact: higher number = ranks earlier.
REGISTER_DIRECTION = {"importance": {"foundational": 3, "significant": 2, "specialist": 1},
                      "tractability": {"near-term": 3, "medium-term": 2, "long-term": 1}}
REGISTER_DIRECTION_NOTE = ("importance: foundational > significant > specialist; tractability: near-term > medium-term > long-term. "
                           "The second is a feasibility preference, not a statement about scientific value.")
ATTENTION = {
    "unlock_kind": ("logical_necessity", "empirical_relevance", "proposed_connection"),
    "action_type": ("proof", "evidence_retrieval", "reanalysis", "simulation", "measurement", "review", "consolidation"),
    "utility_status": ("declared", "unknown"),
    "unlock_relation": ("design_requirement", "theory_challenge"),
}
VOCABULARIES = {"frontier-store": STORE, "morphoswarm-register": REGISTER, "attention": ATTENTION}
MAPPINGS: dict[tuple, str] = {}     # (src_vocab, src_field, value, dst_vocab, dst_field) -> value. Deliberately empty.


class VocabularyError(ValueError):
    pass


class NoTranslation(VocabularyError):
    pass


def tag(vocabulary: str, field: str, value: str) -> dict:
    """A value that remembers where it came from. Rejects a value that is not in that vocabulary."""
    allowed = VOCABULARIES.get(vocabulary, {}).get(field)
    if allowed is None:
        raise VocabularyError(f"unknown vocabulary/field {vocabulary}.{field}")
    if value not in allowed:
        raise VocabularyError(f"{value!r} is not a {vocabulary}.{field} value; allowed {allowed}")
    return {"vocabulary": vocabulary, "field": field, "value": value}


def translate(src: dict, dst_vocabulary: str, dst_field: str) -> dict:
    """Only through an explicit MAPPINGS entry. Equal-looking names are not equal definitions."""
    key = (src["vocabulary"], src["field"], src["value"], dst_vocabulary, dst_field)
    if key not in MAPPINGS:
        raise NoTranslation(f"no declared mapping {src['vocabulary']}.{src['field']}={src['value']!r} -> {dst_vocabulary}.{dst_field}")
    return tag(dst_vocabulary, dst_field, MAPPINGS[key])
