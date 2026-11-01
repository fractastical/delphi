"""Hashing, time, and validation against the Frontier models that live in THIS repository."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha_obj(obj) -> str:
    return hashlib.sha256(canon(obj).encode()).hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def iso_utc(ms: int | None = None) -> str:
    dt = datetime.now(timezone.utc) if ms is None else datetime.fromtimestamp(ms / 1000, timezone.utc)
    return dt.isoformat()


def validate_draft(draft: dict, created_at: str | None = None) -> dict:
    """Validate with the real `frontier.models` and the real store licence gate; return the made record.

    Pass `created_at` to pin the record timestamp so the record, and anything derived from it, is reproducible.
    The licence gate is `frontier.store._unlicensed_available_content`: the same function the store applies at
    submit, import, get and export. It is private by naming convention; if root renames it this raises, loudly.
    """
    from frontier import models, store
    d = models.Draft.model_validate(draft)
    record = models.make_record(d, created_at=created_at)
    return {"record": record, "licence_gate_offenders": store._unlicensed_available_content([record])}
