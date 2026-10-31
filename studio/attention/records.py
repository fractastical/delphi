"""Read-only helpers over exported store records (frontier-record-0.1 envelopes) and events."""
from __future__ import annotations

from collections import defaultdict


def heads(records: list[dict]) -> dict:
    """{(namespace, kind, id): {'head': record, 'versions': n, 'ambiguous': bool}}.
    Head = a version that no other version lists as its predecessor. Several heads (a fork) are flagged, and the one with the
    latest created_at is used; the view says so rather than hiding it."""
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        by[(r["namespace"], r["kind"], r["id"])].append(r)
    out = {}
    for k, rs in by.items():
        preds = {r.get("predecessor") for r in rs}
        hs = [r for r in rs if r["version"] not in preds] or rs
        hs.sort(key=lambda r: (r["created_at"], r["version"]))
        out[k] = {"head": hs[-1], "versions": len(rs), "ambiguous": len(hs) > 1}
    return out


def normalise_events(events: list[dict]) -> list[tuple]:
    """Accept envelopes or Store.events rows {'sequence','envelope'}; return [(sequence|None, envelope)] in a stable order."""
    out = []
    for e in events:
        env = e["envelope"] if "envelope" in e else e
        if env.get("kind") != "Event":
            continue
        out.append((e.get("sequence"), env))
    out.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0, t[1]["payload"]["witnessed_at"], t[1]["version"]))
    return out


def ref_key(ref: dict) -> tuple:
    return (ref["namespace"], ref["kind"], ref["id"], ref["version"])
