"""Structured Project challenges and exact-version discussion projections.

Reviews are ordinary authored Annotation records. They do not settle biology,
vote on a design, or change a Project's review/acceptance state.
"""
from __future__ import annotations

import re

from .models import Draft, Ref
from .store import FrontierError, Store

MAX_CONTEXT_ITEMS = 50
_CURSOR = re.compile(r"^(0|[1-9][0-9]{0,2}):(0|[1-9][0-9]{0,4})$")


def validate_design_review_draft(draft: dict) -> dict:
    """Return a validated, specifically structured Project challenge Annotation draft."""
    parsed = Draft.model_validate(draft)
    if parsed.kind != "Annotation":
        raise FrontierError("A design review draft must be an Annotation")
    payload = parsed.payload
    review = payload.get("design_review")
    if payload.get("kind") != "challenge" or not isinstance(review, dict):
        raise FrontierError("A design review must be a structured challenge Annotation")
    if payload.get("anchor", {}).get("record", {}).get("kind") != "Project":
        raise FrontierError("A design review must anchor an exact Project version")
    return parsed.model_dump()


def submit_design_review(store: Store, token: str, key: str, draft: dict) -> dict:
    """Submit through Store's regular authenticated/idempotent proposal path."""
    validated = validate_design_review_draft(draft)
    return store.submit(token, key, validated)


def project_design_context(store: Store, target: dict, *, token: str | None = None, limit: int = 20,
                          cursor: str | None = None) -> dict:
    """Return a bounded page of discussion anchored to an exact Project and its exact member pins.

    Cursor is ``anchor-index:annotation-offset`` over a stable Project/member
    anchor list. Concurrent new annotations may shift offset pages; each row
    still carries its immutable exact ref and readers can restart from page 1.
    """
    if not 1 <= limit <= MAX_CONTEXT_ITEMS:
        raise FrontierError(f"Context limit must be 1..{MAX_CONTEXT_ITEMS}")
    project_ref = Ref.model_validate(target)
    if project_ref.kind != "Project":
        raise FrontierError("Design context target must pin a Project")
    anchor_index, annotation_offset = 0, 0
    if cursor is not None:
        match = _CURSOR.fullmatch(cursor)
        if not match:
            raise FrontierError("Invalid design-context cursor")
        anchor_index, annotation_offset = map(int, match.groups())
        if annotation_offset > 10000:
            raise FrontierError("Design-context cursor offset exceeds 10000")

    exact = project_ref.model_dump()
    project = store.get(exact, token=token)
    members = store.project_members(exact, token=token)
    anchors = [exact] + [m["ref"] for m in project["record"]["payload"]["members"]]
    if anchor_index >= len(anchors) and cursor is not None:
        raise FrontierError("Design-context cursor is past the pinned member list")

    annotations, withheld, anchors_read = [], 0, 0
    next_cursor = None
    for i in range(anchor_index, len(anchors)):
        if len(annotations) >= limit:
            next_cursor = f"{i}:{0 if i != anchor_index else annotation_offset}"
            break
        offset = annotation_offset if i == anchor_index else 0
        page_limit = limit - len(annotations)
        page = store.annotations_for(anchors[i], token=token, limit=page_limit, offset=offset)
        anchors_read += 1
        withheld += page["withheld_unlicensed"]
        member_index = None if i == 0 else i - 1
        for item in page["annotations"]:
            record = item["record"]
            reply_to = record["payload"].get("reply_to")
            item["anchor_ref"] = anchors[i]
            item["member_index"] = member_index
            item["thread_root_ref"] = reply_to or item["ref"]
            annotations.append(item)
        if page["truncated"]:
            next_cursor = f"{i}:{page['next_offset']}"
            break

    if next_cursor is None and anchor_index + anchors_read < len(anchors):
        next_cursor = f"{anchor_index + anchors_read}:0"
    return {
        "schema": "frontier.project.design-context/1",
        "project": project,
        "members": members,
        "annotations": annotations,
        "pagination": {"limit": limit, "returned": len(annotations), "anchors_read": anchors_read,
                       "anchors_total": len(anchors), "cursor": cursor, "next_cursor": next_cursor,
                       "truncated": next_cursor is not None},
        "withheld_unlicensed": withheld,
        "interpretation": "Annotations are authored challenges or replies, not votes, answers, biological validation, or project resolution. Every anchor is an exact version.",
    }
