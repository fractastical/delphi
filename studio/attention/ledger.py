"""Live action ledger: one row per Action version, state replayed from the store's events. Descriptive only.

The store coordinates leases and records outcomes; it meters nothing (SPEC-003). So `consumed` is reported as not recorded, and the
estimate comes only from an applied annotation. A transition outside SPEC-003's diagram is FLAGGED, not rejected or corrected.
"""
from __future__ import annotations

from .records import normalise_events, ref_key
from frontier.models import aware_time

STATE_OF = {"action_ready": "ready", "action_leased": "leased", "action_running": "running", "action_submitted": "submitted",
            "action_accepted": "accepted", "action_disputed": "disputed", "action_failed": "failed", "action_blocked": "blocked",
            "action_expired": "expired", "action_cancelled": "cancelled"}
LEGAL = {  # SPEC-003 'action_state' diagram, from the spec text; the code is authoritative and may differ
    "proposed": {"ready", "cancelled", "failed", "blocked"}, "ready": {"leased", "blocked", "cancelled", "failed"},
    "leased": {"running", "blocked", "failed", "cancelled", "expired"}, "running": {"submitted", "blocked", "failed", "cancelled", "expired"},
    "submitted": {"accepted", "disputed", "failed"}, "blocked": {"ready"}, "expired": {"leased", "ready"},
    "accepted": set(), "disputed": set(), "failed": set(), "cancelled": set()}


def action_ledger(records: list[dict], events: list[dict], now: str, annotations: dict | None = None, local_status: dict | None = None) -> list[dict]:
    """annotations: {problem_version: verified annotation dict} only for applied (non-stale) annotations.
    local_status: {version: status}; an Action whose local state is imported_unreviewed was produced elsewhere and has no local lifecycle."""
    annotations = annotations or {}
    present = {(r["namespace"], r["kind"], r["id"], r["version"]) for r in records}
    actions = [r for r in records if r["kind"] == "Action"]
    by_target: dict[tuple, list] = {}
    for seq, env in normalise_events(events):
        by_target.setdefault(ref_key(env["payload"]["target"]), []).append((seq, env))
    t_now = aware_time(now)
    rows = []
    for a in sorted(actions, key=lambda r: (r["id"], r["created_at"])):
        evs = by_target.get(ref_key({"namespace": a["namespace"], "kind": "Action", "id": a["id"], "version": a["version"]}), [])
        state, flags, lease = "proposed", [], None
        history = []
        for seq, env in evs:
            p = env["payload"]
            st = STATE_OF.get(p["event_type"])
            history.append({"sequence": seq, "event_type": p["event_type"], "witnessed_at": p["witnessed_at"], "actor": p["actor"], "operator": p["operator"]})
            if p["event_type"] == "action_leased":
                lease = {"actor": p["actor"], "operator": p["operator"], "lease_until": p["details"].get("lease_until"), "lease_id": p["details"].get("lease_id")}
            if st is None:
                continue
            if st not in LEGAL[state]:
                flags.append(f"unexpected transition {state} -> {st} at sequence {seq}")
            state = st
        st_local = (local_status or {}).get(a["version"]) if local_status is not None else None
        witnessed_types = {env["payload"]["event_type"] for _, env in evs}
        # imported if the local state says so OR the store witnessed a record_imported event for this exact version (the web path passes no local states)
        imported = st_local == "imported_unreviewed" or "record_imported" in witnessed_types
        basis = ("record_imported event" if "record_imported" in witnessed_types else "record_proposed event" if "record_proposed" in witnessed_types
                 else "local_status only" if st_local is not None else "no event witnessed")
        if imported and not evs_lifecycle(evs):
            state = "imported_no_local_lifecycle"
        live = bool(lease and lease["lease_until"] and state in ("leased", "running") and aware_time(lease["lease_until"]) > t_now)
        reviewer_ops = sorted({h["operator"] for h in history if h["event_type"] == "action_reviewed"})
        if reviewer_ops and lease and lease["operator"] in reviewer_ops:
            flags.append("reviewed by the operator that held the lease")
        tp = a["payload"]["target"]
        est = None
        ann = annotations.get(tp["version"])
        if ann and ann.get("next_action"):
            est = ann["next_action"]["resource_estimate"]
        times = [aware_time(h["witnessed_at"]) for h in history]
        counts = {t: sum(1 for h in history if h["event_type"] == t) for t in ("action_leased", "action_expired", "action_failed", "action_blocked", "action_cancelled", "action_disputed")}
        outcome = {  # DATA ONLY: what happened, as the store witnessed it. No weight, no decay, no score is computed here.
            "final_state": (None if state == "imported_no_local_lifecycle" else state), "terminal": state in ("accepted", "disputed", "failed", "cancelled"), "path": [h["event_type"] for h in history],
            "n_leases": counts["action_leased"], "n_expired": counts["action_expired"], "n_failed": counts["action_failed"], "n_blocked": counts["action_blocked"],
            "n_cancelled": counts["action_cancelled"], "n_disputed": counts["action_disputed"],
            "first_witnessed_at": history[0]["witnessed_at"] if history else None, "last_witnessed_at": history[-1]["witnessed_at"] if history else None,
            "elapsed_seconds_first_to_last_event": (max(times) - min(times)).total_seconds() if times else None,
            "resources_consumed": "not recorded by the store"}
        rows.append({
            "record_local_status": st_local, "imported": imported, "lifecycle_basis": basis,
            "inputs_resolution": [{"ref": i, "status": ("exact_version_present" if (i.get("namespace"), i.get("kind"), i.get("id"), i.get("version")) in present else "not_in_this_snapshot")}
                                  for i in (a["payload"].get("inputs") or []) if isinstance(i, dict)],
            "proposal": a["payload"].get("proposal"), "plans": a["payload"].get("plans"),      # root-added fields: passed through verbatim, unvalidated
            "outcome": outcome, "key": f"{a['namespace']}/Action/{a['id']}", "action": {k: a[k] for k in ("namespace", "kind", "id", "version")}, "target": tp, "title": a["payload"]["title"],
            "state": state, "lease": lease, "lease_live_at_now": live, "reviewer_operators": reviewer_ops,
            "cost_stop_bounds_text": a["payload"]["cost_stop_bounds"], "inputs": a["payload"].get("inputs"), "estimate": est,
            "consumed": "not recorded by the store (it meters nothing)", "events": history, "flags": flags,
        })
    return rows


def evs_lifecycle(evs) -> bool:
    """True when the store witnessed any action_* lifecycle event for this version (record_imported / record_proposed are not lifecycle)."""
    return any(env["payload"]["event_type"] in STATE_OF for _, env in evs)
